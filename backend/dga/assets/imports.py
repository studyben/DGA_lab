"""Asset-owned retained import batches and atomic new-asset application commands."""
import hashlib
import json
import logging
from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import text

from dga.shared.auth.public import AuditTrail, require_permission
from dga.shared.files import FileStore
from .import_workbook import parse, template, WorkbookError, MAX_BYTES
from .import_validation import validate, summary, issue
from .lifecycle import fail

logger = logging.getLogger(__name__)
XLSX_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


class ImportAction(StrEnum):
    SUBMIT = 'ASSET_IMPORT_SUBMIT'
    PUBLISH = 'ASSET_IMPORT_PUBLISH'


class AssetImports:
    def __init__(self, engine, files: FileStore, *, clock=None):
        self._engine, self._files = engine, files
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._audit = AuditTrail(clock=self._clock)

    def submit(self, actor, *, filename, content):
        require_permission(actor, 'assets.import')
        if not isinstance(filename, str) or not filename.lower().endswith('.xlsx') or not 1 <= len(filename) <= 200 or any(ord(ch) < 32 for ch in filename):
            fail('invalid_import_filename', 422)
        if not isinstance(content, bytes) or not 0 < len(content) <= MAX_BYTES:
            fail('import_file_size', 413)
        state, issues = 'STAGED', []
        try:
            rows = parse(content)
        except WorkbookError as error:
            rows, issues, state = [], error.issues, 'FAILED'
        batch_id = uuid4()
        key = f'asset-imports/{batch_id}/source.xlsx'
        self._files.put(object_key=key, content=content, content_type=XLSX_TYPE)
        try:
            with self._engine.begin() as c:
                c.execute(text('''INSERT INTO asset_import_batches
                    (id,filename,sha256,object_key,byte_size,state,source_rows,issues,summary,created_by,created_at)
                    VALUES (:id,:filename,:sha,:key,:size,:state,CAST(:rows AS jsonb),CAST(:issues AS jsonb),CAST(:summary AS jsonb),:actor,:at)'''),
                    dict(id=batch_id, filename=filename, sha=hashlib.sha256(content).hexdigest(),
                         key=key, size=len(content), rows=json.dumps(rows), actor=actor.user_id, at=self._clock(),
                         state=state, issues=json.dumps(issues), summary=json.dumps(summary(rows, issues))))
                self._audit.append(c, actor, ImportAction.SUBMIT, entity_id=batch_id)
        except Exception:
            try:
                self._files.delete(object_key=key)
            except Exception:
                logger.error('Import source cleanup required: %s', key)
            raise
        return self.get(actor, batch_id)

    def get(self, actor, batch_id):
        require_permission(actor, 'assets.import')
        with self._engine.connect() as c:
            row = c.execute(text('SELECT * FROM asset_import_batches WHERE id=:id'), {'id': batch_id}).mappings().first()
            if row is None:
                fail('import_not_found', 404)
            return {k: v for k, v in row.items() if k not in ('source_rows', 'object_key')}

    def template(self, actor):
        require_permission(actor, 'assets.import')
        with self._engine.connect().execution_options(isolation_level='REPEATABLE READ') as c:
            materials = c.execute(text('SELECT * FROM asset_materials ORDER BY material_number LIMIT 500')).mappings().all()
            sites = c.execute(text('''SELECT s.id AS site_id,s.site_name,c.id AS customer_id,c.customer_name,p.product_line
                FROM sites s JOIN customers c ON c.id=s.customer_id
                LEFT JOIN site_product_lines p ON p.site_id=s.id ORDER BY s.site_name,s.id,p.product_line LIMIT 500''')).mappings().all()
            return template(sites, materials)

    def list_batches(self, actor, *, query='', page=1):
        require_permission(actor, 'assets.import')
        if not isinstance(query, str) or len(query) > 200 or type(page) is not int or not 1 <= page <= 100000:
            fail('invalid_import_search', 422)
        with self._engine.connect().execution_options(isolation_level='REPEATABLE READ') as c:
            where = "FROM asset_import_batches WHERE position(lower(:q) in lower(filename || ' ' || id::text))>0"
            params = dict(q=query.strip(), offset=(page-1)*20)
            count = c.execute(text('SELECT count(*) '+where), params).scalar_one()
            batches = c.execute(text('SELECT id,filename,state,created_at,summary '+where+' ORDER BY created_at DESC,id DESC LIMIT 20 OFFSET :offset'), params).mappings().all()
            return {'batches': [dict(b) for b in batches], 'total': count, 'page': page}

    def validate_next(self):
        """Trusted worker seam. Row claim and result commit together; crash releases claim."""
        with self._engine.begin() as c:
            batch = c.execute(text("SELECT * FROM asset_import_batches WHERE state='STAGED' ORDER BY created_at,id FOR UPDATE SKIP LOCKED LIMIT 1")).mappings().first()
            if batch is None:
                return False
            state, failure = 'VALIDATED', None
            try:
                with c.begin_nested():
                    rows, issues, counts = validate(c, batch['source_rows'], self._clock())
            except Exception:
                rows = []
                issues = [issue(0, 'validation', '校验服务暂不可用；请联系管理员恢复服务后重新上传文件。')]
                counts = summary(rows, issues)
                state, failure = 'FAILED', 'validation_unavailable'
                logger.error('Import validation failed for batch %s', batch['id'])
            c.execute(text("UPDATE asset_import_batches SET state=:state,failure_code=:failure,rows=CAST(:rows AS jsonb),issues=CAST(:issues AS jsonb),summary=CAST(:summary AS jsonb),validation_revision=1 WHERE id=:id"),
                      {'rows': json.dumps(rows), 'issues': json.dumps(issues), 'summary': json.dumps(counts), 'id': batch['id'], 'state': state, 'failure': failure})
            return True

    def publish(self, actor, batch_id, *, validation_revision, acknowledge_warnings=False):
        """Create the entire new-asset batch atomically, never update existing assets."""
        require_permission(actor, 'assets.import')
        with self._engine.begin() as c:
            c.execute(text('SELECT pg_advisory_xact_lock(110011)'))
            batch = c.execute(text('SELECT * FROM asset_import_batches WHERE id=:id FOR UPDATE'), {'id': batch_id}).mappings().first()
            if batch is None:
                fail('import_not_found', 404)
            if batch['state'] != 'PUBLISHED':
                if batch['state'] != 'VALIDATED':
                    fail('import_not_validated')
                if validation_revision != batch['validation_revision']:
                    fail('import_stale_validation')
                # Catalog and site provisioning may not use the graph advisory lock.
                # Hold reference tables stable through the complete creation transaction.
                c.execute(text('LOCK TABLE asset_materials,sites,site_product_lines IN SHARE MODE'))
                rows, issues, counts = validate(c, batch['source_rows'], self._clock())
                if rows != batch['rows'] or issues != batch['issues']:
                    c.execute(text('''UPDATE asset_import_batches SET rows=CAST(:rows AS jsonb),
                        issues=CAST(:issues AS jsonb),summary=CAST(:summary AS jsonb),
                        validation_revision=validation_revision+1 WHERE id=:id'''),
                        dict(rows=json.dumps(rows), issues=json.dumps(issues), summary=json.dumps(counts), id=batch_id))
                else:
                    self._create_assets(c, actor, batch, acknowledge_warnings)
        return self.get(actor, batch_id)

    def _create_assets(self, c, actor, batch, acknowledge_warnings):
        batch_id = batch['id']
        if batch['summary']['error_count']:
            fail('import_has_errors')
        if batch['summary']['warning_count'] and acknowledge_warnings is not True:
            fail('import_warnings_unacknowledged')
        rows = batch['rows']
        ids = {r['values']['record_key']: uuid4() for r in rows}
        assets, installations = [], []
        for row in rows:
            v = row['values']
            asset_id = ids[v['record_key']]
            number = 'AST-' + asset_id.hex.upper()
            assets.append({**v, 'id': asset_id, 'number': number})
            installations.append(dict(id=uuid4(), asset=asset_id, parent=ids.get(v['parent_record_key']),
                                      site=v['site_id'], repair=v['location_kind'] == 'REPAIR_CENTER', at=v['effective_at']))
            row.update(asset_id=str(asset_id), system_asset_number=number)
        c.execute(text('''INSERT INTO formal_assets
            (id,system_asset_number,asset_type,serial_number,model,material_number,lifecycle_status,
             product_line,machine_type,power_mw,energy_mwh,equipment_name,tag_number,commissioning_date,battery_manufacturer)
            VALUES (:id,:number,:asset_type,:serial_number,:model,:material_number,:status,
             :product_line,:machine_type,:power_mw,:energy_mwh,:equipment_name,:tag_number,:commissioning_date,:battery_manufacturer)'''), assets)
        c.execute(text('''INSERT INTO asset_installations
            (id,asset_id,parent_asset_id,site_id,repair_center,valid_from)
            VALUES (:id,:asset,:parent,:site,:repair,:at)'''), installations)
        c.execute(text("""UPDATE asset_import_batches SET state='PUBLISHED',rows=CAST(:rows AS jsonb),
            published_by=:actor,published_at=:at WHERE id=:id"""),
            dict(rows=json.dumps(rows), actor=actor.user_id, at=self._clock(), id=batch_id))
        self._audit.append(c, actor, ImportAction.PUBLISH, entity_id=batch_id)
