"""Public behavior across the populated main -> combined laboratory upgrade."""
from datetime import datetime, timezone
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from dga.assets.public import AssetDirectory
from dga.laboratory.public import ReceiveSample, SampleIdentityStatus, SampleRegistry, LaboratoryReports, ReportState, LaboratoryOperations
from dga.laboratory.report_worker import ReportWorker
from dga.shared.auth.public import AuditTrail
from tests.test_asset_import import import_context, new_rows, workbook
from tests.test_laboratory_reports import MemoryFileStore
from tests.test_laboratory_reports import _queue_one
from tests.test_laboratory_workbench import workbench_context
from tests.test_laboratory_workbench import make_workbench, _dga, TestType
from tests.test_sample_reception import TRANSFORMER_ID


def test_populated_main_upgrade_preserves_assets_samples_imports_and_enables_reports(database_url, monkeypatch):
    # A fresh, isolated schema represents a populated 0013 installation. Never downgrade user data.
    schema = 'upgrade_' + uuid4().hex
    root = create_engine(database_url)
    with root.begin() as c:
        c.execute(text(f'CREATE SCHEMA {schema}'))
    isolated = make_url(database_url).update_query_dict({'options': f'-csearch_path={schema}'}).render_as_string(hide_password=False)
    monkeypatch.setenv('DATABASE_URL', isolated)
    engine = None
    try:
        config = Config('alembic.ini')
        command.upgrade(config, '0013_asset_import')
        engine, actor, imports, _ = import_context(isolated)
        batch = imports.submit(actor, filename='before-upgrade.xlsx', content=workbook(new_rows()))
        imports.validate_next()
        published = imports.publish(actor, batch['id'], validation_revision=1)
        registry = SampleRegistry(engine, AssetDirectory(engine), AuditTrail())
        sample = registry.receive(actor, ReceiveSample(
            sampled_at=datetime(2025, 6, 1, 12, tzinfo=timezone.utc),
            received_at=datetime(2025, 6, 2, 12, tzinfo=timezone.utc),
            site_name='ignored', equipment_serial='ignored', notes='preserve', container_count=2,
            identity_status=SampleIdentityStatus.ASSOCIATED, formal_asset_id=TRANSFORMER_ID,
        ))
        directory = AssetDirectory(engine)
        asset_before = directory.equipment_detail(actor, TRANSFORMER_ID)
        command.upgrade(config, 'head')
        assert registry.find_by_barcode(actor, sample.barcode_value) == sample
        operations = LaboratoryOperations(engine,registry,directory,AuditTrail()).sample_operations(actor,sample.barcode_value)
        assert operations['sample'] == sample
        assert operations['history'] == []
        assert all(c['status']=='RECEIVED' and c['revision']==0 for c in operations['containers'])
        assert directory.equipment_detail(actor, TRANSFORMER_ID) == asset_before
        assert imports.get(actor, batch['id']) == published
        files = MemoryFileStore()
        bench = make_workbench(engine, files)
        method = next(m for m in bench.load(actor, sample.barcode_value).methods if m.test_type == TestType.DGA)
        bench.add_test(actor, sample.barcode_value, _dga(method.id))
        bench.finalize(actor, sample.barcode_value)
        reports = LaboratoryReports(engine, AuditTrail(), files)
        assert ReportWorker(reports, files).process_one('upgrade-test')
        assert reports.get_report_by_barcode(actor, sample.barcode_value).state == ReportState.READY
        assert reports.read_report_file(actor, sample.barcode_value).content.startswith(b'%PDF')
        bench.withdraw_finalization(actor, sample.barcode_value, 'integration verification')
        assert reports.get_report_by_barcode(actor, sample.barcode_value).state == ReportState.UNAVAILABLE
        assert registry.find_by_barcode(actor, sample.barcode_value) == sample
    finally:
        if engine is not None:
            engine.dispose()
        with root.begin() as c:
            c.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        root.dispose()


def test_imported_repair_center_transformer_can_receive_sample_and_produce_report(database_url):
    engine, actor, imports, _ = import_context(database_url)
    row = dict(record_key='spare', serial_number='REPAIR-NEW', material_number='IMPORT-TX',
               product_line='PV', machine_type='TRANSFORMER', status='SPARE',
               location_kind='REPAIR_CENTER', effective_at='2025-01-01T08:00:00Z')
    batch = imports.submit(actor, filename='repair.xlsx', content=workbook([row]))
    imports.validate_next()
    result = imports.publish(actor, batch['id'], validation_revision=1)
    registry = SampleRegistry(engine, AssetDirectory(engine), AuditTrail())
    sample = registry.receive(actor, ReceiveSample(
        sampled_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        received_at=datetime(2025, 6, 2, tzinfo=timezone.utc),
        site_name='ignored', equipment_serial='ignored', notes=None, container_count=1,
        identity_status=SampleIdentityStatus.ASSOCIATED,
        formal_asset_id=UUID(result['rows'][0]['asset_id']),
    ))
    assert sample.asset_snapshot.site_id is None
    assert sample.asset_snapshot.location_kind == 'REPAIR_CENTER'
    files = MemoryFileStore()
    bench = make_workbench(engine, files)
    method = next(m for m in bench.load(actor, sample.barcode_value).methods if m.test_type == TestType.DGA)
    bench.add_test(actor, sample.barcode_value, _dga(method.id))
    bench.finalize(actor, sample.barcode_value)
    reports = LaboratoryReports(engine, AuditTrail(), files)
    assert ReportWorker(reports, files).process_one('repair-integration')
    assert reports.read_report_file(actor, sample.barcode_value).content.startswith(b'%PDF')
    assert registry.find_by_barcode(actor, sample.barcode_value).asset_snapshot == sample.asset_snapshot
    engine.dispose()


def test_lost_report_commit_response_preserves_downloadable_pdf(workbench_context, monkeypatch):
    import psycopg
    engine, actor, sample, files = _queue_one(workbench_context)
    reports = LaboratoryReports(engine, AuditTrail(), files)
    original_commit = psycopg.Connection.commit
    count = 0

    def commit_then_disconnect(connection):
        nonlocal count
        original_commit(connection)
        count += 1
        # First commit claims the queue; second commits the completed PDF.
        if count == 2:
            raise psycopg.OperationalError('simulated lost report COMMIT response')

    monkeypatch.setattr(psycopg.Connection, 'commit', commit_then_disconnect)
    assert ReportWorker(reports, files).process_one('commit-loss')
    assert reports.get_report_by_barcode(actor, sample.barcode_value).state == ReportState.READY
    assert reports.read_report_file(actor, sample.barcode_value).content.startswith(b'%PDF')
