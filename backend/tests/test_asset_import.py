from datetime import datetime, timezone
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from concurrent.futures import ThreadPoolExecutor

from openpyxl import Workbook
from sqlalchemy import text
import pytest
from dataclasses import replace
from dga.shared.auth.public import IdentityError
from dga.shared.files import UnavailableFileStore, ObjectStorageError
from dga.assets.public import AssetQueryError

from dga.assets.public import AssetImports, AssetLifecycle
from tests.test_sample_reception import reception_context, CUSTOMER_ID, SITE_ID, TRANSFORMER_ID


class MemoryFiles:
    def __init__(self):
        self.files = {}

    def put(self, *, object_key, content, content_type):
        self.files[object_key] = content

    def delete(self, *, object_key):
        self.files.pop(object_key, None)


def workbook(rows):
    book = Workbook()
    sheet = book.active
    sheet.title = 'Assets'
    columns = ['record_key', 'serial_number', 'material_number', 'product_line',
               'machine_type', 'status', 'location_kind', 'effective_at',
               'customer_id', 'site_id', 'parent_record_key']
    for row in rows:
        columns.extend(k for k in row if k not in columns)
    sheet.append(columns)
    for row in rows:
        sheet.append([row.get(k) for k in columns])
    output = BytesIO()
    book.save(output)
    return output.getvalue()


def new_rows():
    return [dict(record_key='root', serial_number='00001', material_number='IMPORT-UNIT',
                 product_line='PV', machine_type='INVERTER_UNIT', status='IN_SERVICE',
                 location_kind='SITE', effective_at='2025-01-01T08:00:00Z',
                 customer_id=str(CUSTOMER_ID), site_id=str(SITE_ID)),
            dict(record_key='tx', serial_number='00002', material_number='IMPORT-TX',
                 product_line='PV', machine_type='TRANSFORMER', status='IN_SERVICE',
                 location_kind='PARENT', effective_at='2025-01-01T09:00:00Z', parent_record_key='root')]


def import_context(database_url):
    engine, _, actor = reception_context(database_url)
    # Arrangement of known master data, not behavioral assertions against private tables.
    with engine.begin() as c:
        c.execute(text("DELETE FROM asset_materials WHERE material_number IN ('IMPORT-UNIT','IMPORT-TX')"))
        c.execute(text("INSERT INTO asset_materials VALUES ('IMPORT-UNIT','SG4400UD','WHOLE_UNIT'),('IMPORT-TX','TX-4400','TRANSFORMER')"))
        c.execute(text("INSERT INTO site_product_lines(site_id,product_line) VALUES (:site,'PV')"), {'site': SITE_ID})
    files = MemoryFiles()
    imports = AssetImports(engine, files, clock=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))
    return engine, actor, imports, files


def test_uploaded_hierarchy_is_previewed_without_publishing_assets(database_url):
    engine, actor, imports, files = import_context(database_url)
    before = AssetLifecycle(engine).catalog(actor)['total']
    content = workbook(new_rows())
    batch = imports.submit(actor, filename='首批.xlsx', content=content)
    assert batch['state'] == 'STAGED'
    assert content in files.files.values()
    assert imports.validate_next() is True
    preview = imports.get(actor, batch['id'])
    assert preview['state'] == 'VALIDATED'
    assert preview['summary'] == {'total_rows': 2, 'valid_rows': 2, 'warning_rows': 0, 'error_rows': 0, 'warning_count': 0, 'error_count': 0}
    assert preview['rows'][0]['values']['serial_number'] == '00001'
    assert AssetLifecycle(engine).catalog(actor)['total'] == before
    engine.dispose()


@pytest.mark.parametrize('change,field', [
    ({'material_number': 'MISSING'}, 'material_number'),
    ({'serial_number': 123}, 'serial_number'),
    ({'effective_at': '2025-01-01'}, 'effective_at'),
    ({'effective_at': '2027-01-01T00:00:00Z'}, 'effective_at'),
    ({'customer_id': '22000000-0000-0000-0000-000000000099'}, 'customer_id'),
    ({'site_id': 'missing'}, 'site_id'),
    ({'status': 'SPARE'}, 'status'),
    ({'machine_type': 'BATTERY_CABINET'}, 'machine_type'),
    ({'energy_mwh': 1}, 'energy_mwh'),
    ({'power_mw': -1}, 'power_mw'),
    ({'power_mw': '0.0000001'}, 'power_mw'),
    ({'commissioning_date': 'yesterday'}, 'commissioning_date'),
    ({'asset_id': 'existing'}, 'asset_id'),
])
def test_invalid_asset_values_produce_actionable_row_errors(database_url, change, field):
    engine, actor, imports, _ = import_context(database_url)
    rows = new_rows()
    rows[0].update(change)
    batch = imports.submit(actor, filename='invalid.xlsx', content=workbook(rows))
    imports.validate_next()
    preview = imports.get(actor, batch['id'])
    assert preview['summary']['error_rows'] >= 1
    assert any(i['row'] in (1, 2) and i['field'] == field and i['severity'] == 'ERROR' and i['message'] for i in preview['issues'])
    engine.dispose()


@pytest.mark.parametrize('variant', ['duplicate_key', 'missing_parent', 'cycle', 'earlier_child', 'duplicate_serial'])
def test_hierarchy_identity_and_serial_diagnostics(database_url, variant):
    engine, actor, imports, _ = import_context(database_url)
    rows = new_rows()
    if variant == 'duplicate_key':
        rows[1]['record_key'] = 'root'
    elif variant == 'missing_parent':
        rows[1]['parent_record_key'] = 'absent'
    elif variant == 'cycle':
        rows[0].update(location_kind='PARENT', parent_record_key='tx', customer_id=None, site_id=None)
    elif variant == 'earlier_child':
        rows[1]['effective_at'] = '2024-01-01T00:00:00Z'
    else:
        rows[1]['serial_number'] = 'TX-CURRENT-2002'
    batch = imports.submit(actor, filename='graph.xlsx', content=workbook(rows))
    imports.validate_next()
    preview = imports.get(actor, batch['id'])
    if variant == 'duplicate_serial':
        assert preview['summary']['error_count'] == 0
        assert preview['summary']['warning_rows'] == 1
        assert 'SYS-TX-002' in preview['issues'][0]['message']
    else:
        assert preview['summary']['error_count'] > 0
        assert any(i['field'] in ('record_key', 'parent_record_key', 'effective_at') for i in preview['issues'])
    engine.dispose()


@pytest.mark.parametrize('variant', ['not_zip', 'empty', 'formula', 'huge_xml', 'external_link', 'missing_header', 'too_many_rows', 'duplicate_header', 'far_column'])
def test_unsafe_or_invalid_workbook_is_retained_but_never_publishable(database_url, variant):
    engine, actor, imports, files = import_context(database_url)
    rows = new_rows()
    if variant == 'formula':
        rows[0]['serial_number'] = '=1+1'
    content = workbook(rows)
    if variant == 'not_zip':
        content = b'not an Excel workbook'
    elif variant in ('huge_xml', 'external_link'):
        stream = BytesIO(content)
        with ZipFile(stream, 'a', ZIP_DEFLATED) as archive:
            archive.writestr('xl/externalLinks/link1.xml' if variant == 'external_link' else 'huge.xml', b'x' * (11 * 1024 * 1024) if variant == 'huge_xml' else b'<x/>')
        content = stream.getvalue()
    elif variant == 'empty':
        content = workbook([])
    elif variant == 'too_many_rows':
        content = workbook(rows * 251)
    elif variant in ('missing_header', 'duplicate_header', 'far_column'):
        from openpyxl import load_workbook
        book = load_workbook(BytesIO(content))
        if variant == 'far_column':
            book['Assets']['XFD2'] = 'must not silently drop this asset field'
        else:
            book['Assets']['A1'] = 'serial_number' if variant == 'duplicate_header' else None
        stream = BytesIO()
        book.save(stream)
        content = stream.getvalue()
    batch = imports.submit(actor, filename='unsafe.xlsx', content=content)
    imports.validate_next()
    preview = imports.get(actor, batch['id'])
    assert preview['state'] == 'FAILED'
    assert preview['summary']['error_count'] > 0
    assert content in files.files.values()
    engine.dispose()


def test_upload_rejects_unauthorized_oversized_and_unavailable_storage(database_url):
    engine, actor, imports, files = import_context(database_url)
    with pytest.raises(IdentityError):
        imports.submit(replace(actor, permissions=frozenset({'assets.read', 'assets.write'})), filename='a.xlsx', content=workbook(new_rows()))
    with pytest.raises(AssetQueryError, match='import_file_size'):
        imports.submit(actor, filename='a.xlsx', content=b'x' * (2 * 1024 * 1024 + 1))
    with pytest.raises(ObjectStorageError):
        AssetImports(engine, UnavailableFileStore()).submit(actor, filename='a.xlsx', content=workbook(new_rows()))
    assert not files.files
    assert imports.validate_next() is False
    engine.dispose()


def ready_batch(imports, actor, rows=None):
    batch = imports.submit(actor, filename='publish.xlsx', content=workbook(rows or new_rows()))
    imports.validate_next()
    return imports.get(actor, batch['id'])


def test_publish_creates_queryable_hierarchy_without_changing_existing_assets(database_url):
    engine, actor, imports, _ = import_context(database_url)
    lifecycle = AssetLifecycle(engine)
    original = lifecycle.history(actor, TRANSFORMER_ID)
    batch = ready_batch(imports, actor)
    result = imports.publish(actor, batch['id'], validation_revision=batch['validation_revision'], acknowledge_warnings=False)
    assert result['state'] == 'PUBLISHED'
    root_id, child_id = [r['asset_id'] for r in result['rows']]
    assert root_id != child_id
    from uuid import UUID
    history = lifecycle.history(actor, UUID(child_id))
    assert history['location']['site_id'] == SITE_ID
    assert str(history['installations'][0]['parent_asset_id']) == root_id
    assert history['status'] == 'IN_SERVICE'
    assert lifecycle.history(actor, TRANSFORMER_ID) == original
    assert imports.get(actor, batch['id'])['published_by'] == actor.user_id
    engine.dispose()


def test_publish_revalidates_live_material_facts_before_creating_assets(database_url):
    engine, actor, imports, _ = import_context(database_url)
    batch = ready_batch(imports, actor)
    with engine.begin() as c:
        c.execute(text("UPDATE asset_materials SET model='Corrected model' WHERE material_number='IMPORT-TX'"))
    updated = imports.publish(actor, batch['id'], validation_revision=batch['validation_revision'])
    assert updated['state'] == 'VALIDATED'
    assert updated['validation_revision'] == batch['validation_revision'] + 1
    assert updated['rows'][1]['values']['model'] == 'Corrected model'
    assert AssetLifecycle(engine).catalog(actor)['total'] == 2
    result = imports.publish(actor, batch['id'], validation_revision=updated['validation_revision'])
    assert result['state'] == 'PUBLISHED'
    engine.dispose()


def test_publish_requires_current_warning_ack_and_concurrent_retries_share_result(database_url):
    engine, actor, imports, _ = import_context(database_url)
    rows = new_rows()
    rows[1]['serial_number'] = 'TX-CURRENT-2002'
    batch = ready_batch(imports, actor, rows)
    with pytest.raises(AssetQueryError, match='import_warnings_unacknowledged'):
        imports.publish(actor, batch['id'], validation_revision=batch['validation_revision'])
    with pytest.raises(AssetQueryError, match='import_stale_validation'):
        imports.publish(actor, batch['id'], validation_revision=0, acknowledge_warnings=True)
    def publish(_):
        return imports.publish(actor, batch['id'], validation_revision=batch['validation_revision'], acknowledge_warnings=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(publish, range(2)))
    assert first['rows'] == second['rows']
    assert first['state'] == second['state'] == 'PUBLISHED'
    assert AssetLifecycle(engine).catalog(actor)['total'] == 4
    engine.dispose()


def test_late_database_failure_rolls_back_all_assets_and_allows_retry(database_url):
    from sqlalchemy.exc import SQLAlchemyError
    engine, actor, imports, _ = import_context(database_url)
    batch = ready_batch(imports, actor)
    # System boundary fault: PostgreSQL rejects the second asset insert after the first succeeds.
    with engine.begin() as c:
        c.execute(text("ALTER TABLE formal_assets ADD CONSTRAINT import_test_failure CHECK(serial_number <> '00002')"))
    try:
        with pytest.raises(SQLAlchemyError):
            imports.publish(actor, batch['id'], validation_revision=batch['validation_revision'])
        assert AssetLifecycle(engine).catalog(actor)['total'] == 2
        assert imports.get(actor, batch['id'])['state'] == 'VALIDATED'
        assert all('asset_id' not in r for r in imports.get(actor, batch['id'])['rows'])
    finally:
        with engine.begin() as c:
            c.execute(text('ALTER TABLE formal_assets DROP CONSTRAINT import_test_failure'))
    assert imports.publish(actor, batch['id'], validation_revision=batch['validation_revision'])['state'] == 'PUBLISHED'
    engine.dispose()


def test_http_upload_preview_publish_requires_csrf_and_provides_reference_template(database_url):
    from fastapi.testclient import TestClient
    from dga.main import create_app
    from dga.shared.config import Settings
    from tests.test_sample_reception import CHANGED_PASSWORD
    engine, actor, imports, files = import_context(database_url)
    app = create_app(Settings(database_url=database_url, cookie_secure=False, auth_allowed_origins='http://testserver'), file_store=files)
    with TestClient(app) as client:
        assert client.get('/api/assets/imports').status_code == 401
        login = client.post('/api/auth/login', headers={'Origin': 'http://testserver'}, json={'username': 'reception-admin', 'password': CHANGED_PASSWORD}).json()
        headers = {'Origin': 'http://testserver', 'X-CSRF-Token': login['csrf_token'], 'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
        template = client.get('/api/assets/imports/template')
        assert template.status_code == 200
        from openpyxl import load_workbook
        book = load_workbook(BytesIO(template.content))
        assert 'Materials' in book.sheetnames
        assert 'IMPORT-TX' in [r[0] for r in book['Materials'].values]
        content = workbook(new_rows())
        assert client.post('/api/assets/imports?filename=a.xlsx', content=content, headers={'Origin': 'http://testserver'}).status_code == 403
        submitted = client.post('/api/assets/imports?filename=a.xlsx', content=content, headers=headers)
        assert submitted.status_code == 201
        batch_id = submitted.json()['id']
        imports.validate_next()
        preview = client.get(f'/api/assets/imports/{batch_id}').json()
        result = client.post(f'/api/assets/imports/{batch_id}/publish', headers={**headers, 'Content-Type': 'application/json'}, json={'validation_revision': preview['validation_revision'], 'acknowledge_warnings': False})
        assert result.status_code == 200
        assert result.headers.get('cache-control') == 'no-store'
        assert result.json()['state'] == 'PUBLISHED'
        listing = client.get('/api/assets/imports')
        assert listing.headers.get('cache-control') == 'no-store'
        assert listing.json()['batches'][0]['id'] == batch_id
    engine.dispose()


def test_import_does_not_rewrite_existing_oil_sample_snapshot(database_url):
    from dga.assets.public import AssetDirectory
    from dga.laboratory.public import SampleRegistry, ReceiveSample, SampleIdentityStatus
    from dga.shared.auth.public import AuditTrail
    engine, actor, imports, _ = import_context(database_url)
    samples = SampleRegistry(engine, AssetDirectory(engine), AuditTrail())
    sample = samples.receive(actor, ReceiveSample(sampled_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        received_at=datetime(2025, 6, 2, tzinfo=timezone.utc), site_name='ignored', equipment_serial='ignored',
        notes='snapshot preservation', container_count=1, identity_status=SampleIdentityStatus.ASSOCIATED,
        formal_asset_id=TRANSFORMER_ID))
    rows = new_rows()
    rows[1]['serial_number'] = 'TX-CURRENT-2002'
    batch = ready_batch(imports, actor, rows)
    result = imports.publish(actor, batch['id'], validation_revision=batch['validation_revision'], acknowledge_warnings=True)
    assert result['state'] == 'PUBLISHED'
    assert samples.find_by_barcode(actor, sample.barcode_value).asset_snapshot == sample.asset_snapshot
    engine.dispose()


def test_500_asset_rows_can_keep_the_template_reference_sheets(database_url):
    from openpyxl import load_workbook
    engine, actor, imports, _ = import_context(database_url)
    rows = [{**new_rows()[0], 'record_key': f'unit-{i}', 'serial_number': f'NEW-{i}',
             'power_mw': 1, 'equipment_name': 'unit', 'tag_number': f'TAG-{i}',
             'commissioning_date': '2025-01-01', 'battery_manufacturer': 'not applicable'} for i in range(500)]
    book = load_workbook(BytesIO(workbook(rows)))
    for name, width in [('Materials', 3), ('Sites', 5)]:
        tab = book.create_sheet(name)
        tab.append(['reference'] * width)
        for i in range(500):
            tab.append([f'value-{i}'] * width)
    output = BytesIO()
    book.save(output)
    batch = imports.submit(actor, filename='full.xlsx', content=output.getvalue())
    imports.validate_next()
    preview = imports.get(actor, batch['id'])
    assert preview['state'] == 'VALIDATED'
    assert preview['summary']['valid_rows'] == 500
    engine.dispose()


def test_worker_records_unexpected_validation_failure_without_losing_source(database_url):
    engine, actor, imports, files = import_context(database_url)
    batch = imports.submit(actor, filename='worker.xlsx', content=workbook(new_rows()))
    # Temporary schema unavailability is a database boundary fault, not an internal mock.
    with engine.begin() as c:
        c.execute(text('ALTER TABLE asset_materials RENAME TO import_test_unavailable'))
    try:
        assert imports.validate_next() is True
        result = imports.get(actor, batch['id'])
        assert result['state'] == 'FAILED'
        assert result['failure_code'] == 'validation_unavailable'
        assert result['summary']['error_count'] == 1
        assert files.files
    finally:
        with engine.begin() as c:
            c.execute(text('ALTER TABLE import_test_unavailable RENAME TO asset_materials'))
    engine.dispose()
