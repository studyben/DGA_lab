"""Laboratory-owned private original staging; never calls formal sample/test writes."""
import hashlib
import json
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4
from pydantic import ValidationError
from sqlalchemy import text
from dga.shared.auth.public import AuditTrail, IdentityService, require_permission
from .errors import LaboratoryError
from .import_contracts import CreateImport


def dumped(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str, allow_nan=False)


def digest(value):
    return hashlib.sha256(dumped(value).encode('utf-8')).hexdigest()


def fail(code, status=422, **details):
    raise LaboratoryError(code, status, details=details or None)


class ImportAction(StrEnum):
    CREATE = 'LAB_IMPORT_CREATED'
    FILE_RESERVED = 'LAB_IMPORT_FILE_RESERVED'
    FILE_RECEIVED = 'LAB_IMPORT_FILE_RECEIVED'
    FILE_FAILED = 'LAB_IMPORT_FILE_FAILED'
    SOURCE = 'LAB_IMPORT_SOURCE_DOWNLOADED'
    REVISE = 'LAB_IMPORT_REVISED'


class LaboratoryImports:
    def __init__(self, engine, files, *, identities=None, audit=None, clock=None):
        self.engine, self.files = engine, files
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.identity = identities or IdentityService(engine)
        self.audit = audit or AuditTrail(clock=self.clock)

    def _authorize(self, c, actor):
        require_permission(actor, 'laboratory.write')
        return self.identity.authorize_current(c, actor, 'laboratory.write')

    def _intent(self, c, actor, key, action, payload):
        self._authorize(c, actor)
        try:
            key = str(UUID(str(key)))
        except (ValueError, TypeError, AttributeError):
            fail('invalid_import_input')
        c.execute(text('SELECT pg_advisory_xact_lock(520052,hashtext(:scope))'),
                  {'scope': str(actor.user_id) + ':' + key})
        previous = c.execute(text('''SELECT * FROM lab_import_operations
            WHERE actor_id=:actor AND operation_key=:key'''),
            dict(actor=actor.user_id, key=key)).mappings().first()
        fingerprint = digest(dict(action=action, payload=payload))
        if previous and (previous['action'] != action or previous['request_digest'] != fingerprint):
            fail('import_operation_conflict', 409)
        return key, fingerprint, previous

    def _complete(self, c, actor, key, action, payload, fingerprint, batch_id, result, *, state='COMPLETED'):
        now = self.clock()
        operation_id = uuid4()
        c.execute(text('''INSERT INTO lab_import_operations
            (id,actor_id,operation_key,action,batch_id,request_digest,state,request_snapshot,result,created_at,updated_at)
            VALUES (:id,:actor,:key,:action,:batch,:digest,:state,CAST(:payload AS jsonb),CAST(:result AS jsonb),:now,:now)'''),
            dict(id=operation_id, actor=actor.user_id, key=key, action=action, batch=batch_id,
                 digest=fingerprint, payload=dumped(payload), result=dumped(result), now=now, state=state))
        return operation_id

    @staticmethod
    def _op_view(row):
        return json.loads(dumped({k: row[k] for k in ('state', 'action', 'batch_id', 'result', 'error_code')}))

    def _bind_sources(self, c, actor, batch_id, choices):
        for name_key in sorted({x.proposed_name.casefold() for x in choices if x.decision == 'NEW'}):
            c.execute(text('SELECT pg_advisory_xact_lock(520053,hashtext(:key))'), {'key': name_key})
        references = {}
        for source_id in sorted({x.source_lab_id for x in choices if x.decision == 'REFERENCE'}, key=str):
            row = c.execute(text('SELECT * FROM laboratory_source_labs WHERE id=:id FOR SHARE'),
                            {'id': source_id}).mappings().first()
            if row is None:
                fail('invalid_source_decision', 422)
            references[source_id] = row
        for choice in choices:
            if choice.decision == 'NEW':
                candidates = c.execute(text('''SELECT id FROM laboratory_source_labs
                    WHERE name_key=:name ORDER BY id'''), {'name': choice.proposed_name.casefold()}).scalars().all()
                if choice.candidate_digest != digest([str(x) for x in candidates]):
                    fail('source_candidates_changed', 409, candidate_digest=digest([str(x) for x in candidates]),
                         exact_name_total=len(candidates))
                source_id = uuid4()
                c.execute(text('''INSERT INTO laboratory_source_labs
                    (id,display_name,name_key,source_kind,created_by,created_at)
                    VALUES (:id,:name,:key,:kind,:actor,:now)'''),
                    dict(id=source_id, name=choice.proposed_name, key=choice.proposed_name.casefold(),
                         kind=choice.source_kind, actor=actor.user_id, now=self.clock()))
            else:
                source_id = choice.source_lab_id
            c.execute(text('''INSERT INTO lab_import_lab_bindings
                (batch_id,source_lab_key,source_lab_id,confirmed_by,confirmed_at,reason)
                VALUES (:batch,:key,:source,:actor,:now,:reason)
                ON CONFLICT(batch_id,source_lab_key) DO UPDATE SET source_lab_id=:source,
                    confirmed_by=:actor,confirmed_at=:now,reason=:reason'''),
                dict(batch=batch_id, key=choice.key, source=source_id, actor=actor.user_id,
                     now=self.clock(), reason=choice.reason))

    def source_labs(self, actor, *, query='', exact_name=None, page=1):
        if (not isinstance(query, str) or len(query) > 200 or type(page) is not int or not 1 <= page <= 100000
                or exact_name is not None and (not isinstance(exact_name, str) or not 1 <= len(exact_name) <= 200)):
            fail('invalid_import_input')
        with self.engine.begin() as c:
            self._authorize(c, actor)
            params = dict(query=query.casefold(), exact=exact_name.strip().casefold() if exact_name else None,
                          offset=(page-1)*20)
            where = "WHERE strpos(name_key,:query)>0 AND (CAST(:exact AS text) IS NULL OR name_key=:exact)"
            total = c.execute(text('SELECT count(*) FROM laboratory_source_labs '+where), params).scalar_one()
            rows = c.execute(text('SELECT id,display_name,source_kind FROM laboratory_source_labs '+where+
                                  ' ORDER BY name_key,id LIMIT 20 OFFSET :offset'), params).mappings()
            result = dict(items=[json.loads(dumped(dict(x))) for x in rows], total=total, page=page, page_size=20)
            if exact_name is not None:
                ids = c.execute(text('SELECT id FROM laboratory_source_labs WHERE name_key=:exact ORDER BY id'),
                                params).scalars().all()
                result.update(exact_name_total=len(ids), candidate_digest=digest([str(x) for x in ids]))
            return result

    def reject_input(self, actor, *, idempotency_key, action, request, batch_id=None):
        """Bind a strict HTTP input rejection, never a business mutation.

        Invalid input is represented by its canonical digest only. This avoids storing
        invalid JSONB strings and keeps raw rejected fields out of shared audit. A
        normal command and this rejection have distinct digest namespaces.
        """
        require_permission(actor, 'laboratory.write')
        if action not in ('CREATE', 'REVISE') or not isinstance(request, dict):
            fail('invalid_import_input')
        from .import_contracts import ReviseImport
        try:
            (CreateImport if action == 'CREATE' else ReviseImport).model_validate(request)
        except ValidationError:
            pass
        else:
            # This method proves invalid input, not a general cancellation command.
            fail('invalid_import_input')
        route_batch = str(self._uuid(batch_id)) if action == 'REVISE' else None
        try:
            request_hash = digest(request)
        except (ValueError, TypeError, UnicodeError, RecursionError):
            fail('invalid_import_input')
        payload = dict(rejection_contract=1, raw_input_sha256=request_hash, route_batch_id=route_batch)
        with self.engine.begin() as c:
            key, fingerprint, old = self._intent(c, actor, idempotency_key, action, payload)
            if old:
                if old['state'] != 'REJECTED':
                    fail('import_operation_conflict', 409)
            else:
                rejected = dict(code='invalid_import_input', status=422, details=None)
                operation_id = self._complete(c, actor, key, action, payload, fingerprint, None,
                                              rejected, state='REJECTED')
                self.audit.append(c, actor, ImportAction.CREATE if action == 'CREATE' else ImportAction.REVISE,
                                  entity_id=operation_id, result='FAILURE',
                                  details=dict(code='invalid_import_input', rejection_contract=1))
        # Only a known committed rejection (and still-current actor) is returned.
        return self.operation(actor, key)

    def create(self, actor, *, idempotency_key, **values):
        require_permission(actor, 'laboratory.write')
        try:
            command = CreateImport(**values)
        except ValidationError:
            fail('invalid_import_input')
        payload = command.model_dump(mode='json')
        rejected = None
        with self.engine.begin() as c:
            key, fingerprint, old = self._intent(c, actor, idempotency_key, 'CREATE', payload)
            if old:
                batch_id = old['batch_id']
                if old['state'] == 'REJECTED':
                    rejected = old['result']
            else:
                try:
                    with c.begin_nested():
                        batch_id, now = uuid4(), self.clock()
                        c.execute(text('''INSERT INTO lab_import_batches
                            (id,format_version,input_format,purpose,source_timezone,source_timezone_confirmed,
                             created_by,updated_by,created_at,updated_at)
                            VALUES (:id,1,:format,:purpose,:zone,:confirmed,:actor,:actor,:now,:now)'''),
                            dict(id=batch_id, format=command.input_format, purpose=command.purpose,
                                 zone=command.source_timezone, confirmed=command.source_timezone_confirmed,
                                 actor=actor.user_id, now=now))
                        self._bind_sources(c, actor, batch_id, command.source_labs)
                        self._complete(c, actor, key, 'CREATE', payload, fingerprint, batch_id,
                                       dict(outcome='CREATED', batch_id=str(batch_id), applied_revision=0))
                        self.audit.append(c, actor, ImportAction.CREATE, entity_id=batch_id,
                                          details=dict(source_decisions=payload['source_labs']))
                except LaboratoryError as error:
                    rejected = dict(code=error.code, status=error.status, details=error.details)
                    operation_id = self._complete(c, actor, key, 'CREATE', payload, fingerprint, None, rejected, state='REJECTED')
                    self.audit.append(c, actor, ImportAction.CREATE, entity_id=operation_id, result='FAILURE',
                                      details=dict(code=error.code))
        if rejected:
            raise LaboratoryError(rejected['code'], rejected['status'], details=rejected['details'])
        return {'operation': self.operation(actor, key), 'batch': self.get(actor, batch_id)}

    def get(self, actor, batch_id):
        with self.engine.begin() as c:
            self._authorize(c, actor)
            row = c.execute(text('SELECT * FROM lab_import_batches WHERE id=:id FOR SHARE'), {'id': self._uuid(batch_id)}).mappings().first()
            if row is None:
                fail('import_not_found', 404)
            bindings = c.execute(text('''SELECT b.source_lab_key,b.source_lab_id,s.display_name,s.source_kind,
                b.reason,b.confirmed_by,b.confirmed_at FROM lab_import_lab_bindings b
                JOIN laboratory_source_labs s ON s.id=b.source_lab_id
                WHERE b.batch_id=:id ORDER BY b.source_lab_key'''), {'id': batch_id}).mappings().all()
            files, manifest_state = self._manifest(c, row)
            return json.loads(dumped(dict(row, manifest_state=manifest_state, active_files=files, source_labs=[dict(x) for x in bindings])))

    def list_batches(self, actor, *, page=1, q='', state=None, purpose=None,
                     created_from=None, created_to=None, actor_id=None, source_lab_id=None, **filters):
        from datetime import date, timedelta
        if (filters or type(page) is not int or not 1 <= page <= 100000
                or not isinstance(q, str) or len(q) > 200
                or state not in (None, 'NOT_REQUESTED', 'QUEUED', 'RUNNING', 'COMPLETE', 'FAILED')
                or purpose not in (None, 'HISTORICAL', 'DAILY')):
            fail('invalid_import_input')
        try:
            start = date.fromisoformat(created_from) if created_from else None
            end = date.fromisoformat(created_to) + timedelta(days=1) if created_to else None
            if start and end and start >= end:
                fail('invalid_import_input')
        except (ValueError, TypeError, OverflowError):
            fail('invalid_import_input')
        params = dict(q=q, state=state, purpose=purpose, start=start, end=end,
                      actor=self._uuid(actor_id) if actor_id else None,
                      source=self._uuid(source_lab_id) if source_lab_id else None, offset=(page-1)*20)
        where = """ WHERE (CAST(:state AS text) IS NULL OR b.validation_state=:state)
            AND (CAST(:purpose AS text) IS NULL OR b.purpose=:purpose)
            AND (CAST(:start AS date) IS NULL OR b.created_at >= CAST(:start AS date) AT TIME ZONE 'UTC')
            AND (CAST(:end AS date) IS NULL OR b.created_at < CAST(:end AS date) AT TIME ZONE 'UTC')
            AND (strpos(lower(CAST(b.id AS text)),lower(CAST(:q AS text)))>0 OR EXISTS(
                SELECT 1 FROM lab_import_files f WHERE f.batch_id=b.id AND strpos(lower(f.filename),lower(CAST(:q AS text)))>0))
            AND (CAST(:source AS uuid) IS NULL OR EXISTS(SELECT 1 FROM lab_import_lab_bindings s
                WHERE s.batch_id=b.id AND s.source_lab_id=:source))
            AND (CAST(:actor AS uuid) IS NULL OR b.created_by=:actor
                OR EXISTS(SELECT 1 FROM lab_import_files f WHERE f.batch_id=b.id AND f.received_by=:actor)
                OR EXISTS(SELECT 1 FROM lab_import_revisions r WHERE r.batch_id=b.id AND r.actor_id=:actor)
                OR EXISTS(SELECT 1 FROM lab_import_jobs j WHERE j.batch_id=b.id AND j.requested_by=:actor))"""
        with self.engine.begin() as c:
            self._authorize(c, actor)
            # A single statement gives total and page the same database snapshot.
            rows = c.execute(text("""WITH matching AS (
                SELECT b.*,f.received_file_count,f.active_file_count,
                    CASE WHEN f.roles=CASE b.input_format WHEN 'XLSX' THEN ARRAY['WORKBOOK']::text[]
                        ELSE ARRAY['SAMPLES','TESTS']::text[] END THEN 'COMPLETE'
                        WHEN cardinality(f.roles)>0 THEN 'PARTIAL' ELSE 'EMPTY' END AS manifest_state
                FROM lab_import_batches b CROSS JOIN LATERAL (
                    SELECT count(*) FILTER(WHERE state='RECEIVED') AS received_file_count,
                        count(*) FILTER(WHERE active AND state='RECEIVED') AS active_file_count,
                        coalesce(array_agg(role::text ORDER BY role) FILTER(WHERE active AND state='RECEIVED'),
                                 ARRAY[]::text[]) AS roles
                    FROM lab_import_files WHERE batch_id=b.id
                ) f"""+where+""")
                SELECT (SELECT count(*) FROM matching) AS total,
                       (SELECT jsonb_agg(to_jsonb(p)) FROM (SELECT * FROM matching
                        ORDER BY created_at DESC,id LIMIT 20 OFFSET :offset) p) AS items"""), params).mappings().one()
            return dict(items=rows['items'] or [], total=rows['total'], page=page, page_size=20)

    def operation(self, actor, key):
        try:
            key = str(UUID(str(key)))
        except (ValueError, TypeError, AttributeError):
            fail('invalid_import_input')
        with self.engine.begin() as c:
            self._authorize(c, actor)
            row = c.execute(text('''SELECT * FROM lab_import_operations
                WHERE actor_id=:actor AND operation_key=:key'''),
                dict(actor=actor.user_id, key=key)).mappings().first()
            if row is None:
                fail('import_operation_not_found', 404)
            return self._op_view(row)




    @staticmethod
    def _uuid(value):
        try:
            return UUID(str(value))
        except (ValueError, TypeError, AttributeError):
            fail('invalid_import_input')

    def _locked(self, c, batch_id):
        row = c.execute(text('SELECT * FROM lab_import_batches WHERE id=:id FOR UPDATE'),
                        {'id': self._uuid(batch_id)}).mappings().first()
        if row is None:
            fail('import_not_found', 404)
        return row

    @staticmethod
    def _manifest(c, batch):
        rows = [dict(x) for x in c.execute(text('''SELECT id,role,filename,byte_size,sha256
            FROM lab_import_files WHERE batch_id=:id AND active AND state='RECEIVED' ORDER BY role'''),
            {'id': batch['id']}).mappings()]
        required = {'WORKBOOK'} if batch['input_format'] == 'XLSX' else {'SAMPLES', 'TESTS'}
        roles = {x['role'] for x in rows}
        return rows, ('COMPLETE' if roles == required else 'PARTIAL' if rows else 'EMPTY')

    @staticmethod
    def _file(c, batch_id, file_id):
        from .import_files import FILE_COLUMNS
        row = c.execute(text('SELECT '+','.join(FILE_COLUMNS)+''' FROM lab_import_files
            WHERE id=:id AND batch_id=:batch'''), dict(id=file_id, batch=batch_id)).mappings().first()
        if row is None:
            fail('import_file_not_found', 404)
        return json.loads(dumped(dict(row)))

    def _snapshot(self, c, batch):
        files, state = self._manifest(c, batch)
        bindings = c.execute(text('''SELECT source_lab_key,source_lab_id FROM lab_import_lab_bindings
            WHERE batch_id=:id ORDER BY source_lab_key'''), {'id': batch['id']}).mappings()
        return json.loads(dumped(dict(purpose=batch['purpose'], source_timezone=batch['source_timezone'],
                    source_timezone_confirmed=batch['source_timezone_confirmed'],
                    source_labs=[dict(x) for x in bindings], active_files=files, manifest_state=state)))

    def _changed(self, c, batch, actor, reason, before, after):
        revision = batch['revision'] + 1
        c.execute(text("""UPDATE lab_import_jobs SET state='SUPERSEDED'
            WHERE batch_id=:id AND state IN('QUEUED','RUNNING')"""), {'id': batch['id']})
        c.execute(text("""UPDATE lab_import_batches SET revision=:revision,validated_revision=NULL,
            current_job_id=NULL,validation_state='NOT_REQUESTED',updated_by=:actor,updated_at=:now WHERE id=:id"""),
            dict(id=batch['id'], revision=revision, actor=actor.user_id, now=self.clock()))
        c.execute(text('''INSERT INTO lab_import_revisions
            (id,batch_id,revision,actor_id,occurred_at,reason,before_value,after_value)
            VALUES (:id,:batch,:revision,:actor,:now,:reason,CAST(:before AS jsonb),CAST(:after AS jsonb))'''),
            dict(id=uuid4(), batch=batch['id'], revision=revision, actor=actor.user_id, now=self.clock(),
                 reason=reason, before=dumped(before), after=dumped(after)))
        return revision

    def receive_file(self, actor, batch_id, **values):
        from .import_files import OriginalReceipts
        return OriginalReceipts(self).receive(actor, batch_id, **values)

    def list_files(self, actor, batch_id, *, page=1):
        if type(page) is not int or not 1 <= page <= 100000:
            fail('invalid_import_input')
        batch_id = self._uuid(batch_id)
        with self.engine.begin() as c:
            self._authorize(c, actor)
            if not c.execute(text('SELECT id FROM lab_import_batches WHERE id=:id'), {'id': batch_id}).scalar():
                fail('import_not_found', 404)
            total = c.execute(text('SELECT count(*) FROM lab_import_files WHERE batch_id=:id'), {'id': batch_id}).scalar_one()
            ids = c.execute(text('''SELECT id FROM lab_import_files WHERE batch_id=:id
                ORDER BY reserved_at,id LIMIT 20 OFFSET :offset'''), dict(id=batch_id, offset=(page-1)*20)).scalars().all()
            return dict(items=[self._file(c, batch_id, x) for x in ids], total=total, page=page, page_size=20)

    def original(self, actor, batch_id, file_id):
        from dga.shared.files import ObjectStorageError
        batch_id, file_id = self._uuid(batch_id), self._uuid(file_id)
        with self.engine.begin() as c:
            self._authorize(c, actor)
            row = c.execute(text('''SELECT * FROM lab_import_files WHERE id=:id AND batch_id=:batch AND state='RECEIVED'
                FOR SHARE'''), dict(id=file_id, batch=batch_id)).mappings().first()
            if row is None:
                fail('import_file_not_found', 404)
            try:
                content = self.files.get(object_key=row['object_key'])
            except Exception as error:
                raise ObjectStorageError('import_storage_unavailable') from error
            if len(content) != row['byte_size'] or hashlib.sha256(content).hexdigest() != row['sha256']:
                raise ObjectStorageError('import_source_integrity')
            self.audit.append(c, actor, ImportAction.SOURCE, entity_id=batch_id,
                              details=dict(file_id=str(file_id)))
            return dict(content=content, filename=row['filename'], content_type=row['content_type'])



    def revise(self, actor, batch_id, *, idempotency_key, **values):
        from .import_contracts import ReviseImport
        require_permission(actor, 'laboratory.write')
        batch_id = self._uuid(batch_id)
        try:
            command = ReviseImport(**values)
        except ValidationError:
            fail('invalid_import_input')
        payload = dict(batch_id=str(batch_id), **command.model_dump(mode='json'))
        rejected = None
        with self.engine.begin() as c:
            key, fingerprint, old = self._intent(c, actor, idempotency_key, 'REVISE', payload)
            if old and old['state'] == 'REJECTED':
                rejected = old['result']
            elif old is None:
                try:
                    with c.begin_nested():
                        batch = self._locked(c, batch_id)
                        if batch['revision'] != command.expected_revision:
                            fail('import_stale_revision', 409, current_revision=batch['revision'])
                        before = self._snapshot(c, batch)
                        if command.metadata:
                            patch = command.metadata.model_dump(exclude_unset=True)
                            if 'purpose' in patch and patch['purpose'] is None:
                                fail('invalid_import_input')
                            merged = {k: patch.get(k, batch[k]) for k in
                                      ('purpose', 'source_timezone', 'source_timezone_confirmed')}
                            try:
                                CreateImport(input_format=batch['input_format'], **merged)
                            except ValidationError:
                                fail('invalid_import_input')
                            c.execute(text('''UPDATE lab_import_batches SET purpose=:purpose,source_timezone=:zone,
                                source_timezone_confirmed=:confirmed WHERE id=:id'''),
                                dict(id=batch_id, purpose=merged['purpose'], zone=merged['source_timezone'],
                                     confirmed=merged['source_timezone_confirmed']))
                        self._bind_sources(c, actor, batch_id, command.source_labs)
                        if command.active_files:
                            allowed = {'WORKBOOK'} if batch['input_format'] == 'XLSX' else {'SAMPLES', 'TESTS'}
                            for role, file_id in command.active_files.items():
                                if role not in allowed:
                                    fail('import_role_not_supported', 415)
                                file = c.execute(text('''SELECT id,role,state FROM lab_import_files
                                    WHERE batch_id=:batch AND id=:id FOR UPDATE'''),
                                    dict(batch=batch_id, id=file_id)).mappings().first()
                                if not file or file['role'] != role:
                                    fail('import_file_not_found', 404)
                                if file['state'] != 'RECEIVED':
                                    fail('files_pending', 409, file_id=str(file_id))
                            c.execute(text('UPDATE lab_import_files SET active=false WHERE batch_id=:batch AND role=ANY(:roles)'),
                                      dict(batch=batch_id, roles=list(command.active_files)))
                            for file_id in command.active_files.values():
                                c.execute(text('UPDATE lab_import_files SET active=true WHERE id=:id'), {'id': file_id})
                        current = c.execute(text('SELECT * FROM lab_import_batches WHERE id=:id FOR SHARE'), {'id': self._uuid(batch_id)}).mappings().one()
                        after = self._snapshot(c, current)
                        if before == after:
                            fail('invalid_import_input')
                        revision = self._changed(c, current, actor, command.reason.strip(), before, after)
                        self._complete(c, actor, key, 'REVISE', payload, fingerprint, batch_id,
                                       dict(outcome='REVISED', batch_id=str(batch_id), applied_revision=revision))
                        self.audit.append(c, actor, ImportAction.REVISE, entity_id=batch_id,
                                          details=dict(revision=revision, reason=command.reason.strip(),
                                                       before=before, after=after))
                except LaboratoryError as error:
                    rejected = dict(code=error.code, status=error.status, details=error.details)
                    self._complete(c, actor, key, 'REVISE', payload, fingerprint, None, rejected, state='REJECTED')
                    self.audit.append(c, actor, ImportAction.REVISE, entity_id=batch_id, result='FAILURE',
                                      details=dict(code=error.code))
        if rejected:
            raise LaboratoryError(rejected['code'], rejected['status'], details=rejected['details'])
        return dict(operation=self.operation(actor, key), batch=self.get(actor, batch_id))

    def revision_history(self, actor, batch_id, *, page=1):
        if type(page) is not int or not 1 <= page <= 100000:
            fail('invalid_import_input')
        batch_id = self._uuid(batch_id)
        with self.engine.begin() as c:
            self._authorize(c, actor)
            self._locked(c, batch_id)
            params = dict(id=batch_id, offset=(page-1)*20)
            total = c.execute(text('SELECT count(*) FROM lab_import_revisions WHERE batch_id=:id'), params).scalar_one()
            rows = c.execute(text('''SELECT r.id,r.revision,r.actor_id,u.display_name,r.occurred_at,r.reason,
                r.before_value,r.after_value FROM lab_import_revisions r JOIN users u ON u.id=r.actor_id
                WHERE r.batch_id=:id ORDER BY r.revision DESC LIMIT 20 OFFSET :offset'''), params).mappings()
            return dict(items=[json.loads(dumped(dict(x))) for x in rows], total=total, page=page, page_size=20)



    def template(self, actor, *, format='XLSX', example=False, version=1):
        if format not in ('XLSX', 'CSV_PAIR') or type(example) is not bool or type(version) is not int or version != 1:
            fail('invalid_import_input')
        from .import_tables import build_template
        with self.engine.begin() as c:
            self._authorize(c, actor)
            return build_template(format, example)







