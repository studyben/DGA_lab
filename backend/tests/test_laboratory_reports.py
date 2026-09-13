from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from dga.laboratory.public import (
    LaboratoryError,
    LaboratoryReports,
    ReportState,
    StaleReportClaim,
)
from dga.laboratory.report_worker import ReportWorker
from dga.main import create_app
from dga.shared.auth.public import AuditTrail
from dga.shared.config import Settings

from tests.test_laboratory_workbench import (
    CHANGED_PASSWORD,
    RecordingObjectStore,
    TestType,
    _dga,
    make_workbench,
    workbench_context,
)


class MemoryFileStore:
    def __init__(self, *, fail_put=False):
        self.objects = {}
        self.fail_put = fail_put

    def put(self, *, object_key, content, content_type):
        if self.fail_put:
            raise OSError('storage unavailable')
        self.objects[object_key] = content

    def get(self, *, object_key):
        return self.objects[object_key]

    def delete(self, *, object_key):
        self.objects.pop(object_key, None)


def _queue_one(workbench_context, store=None):
    engine, _, actor, sample = workbench_context
    store = store or MemoryFileStore()
    workbench = make_workbench(engine, store)
    method = next(
        item for item in workbench.load(actor, sample.barcode_value).methods
        if item.test_type == TestType.DGA
    )
    workbench.add_test(actor, sample.barcode_value, _dga(method.id))
    workbench.finalize(actor, sample.barcode_value)
    return engine, actor, sample, store


def test_open_sample_report_is_unavailable(workbench_context):
    engine, _, actor, sample = workbench_context
    reports = LaboratoryReports(engine, AuditTrail(), MemoryFileStore())

    status = reports.get_report_by_barcode(actor, sample.barcode_value)

    assert status.state == ReportState.UNAVAILABLE
    assert status.unavailable_reason == 'sample_not_finalized'
    assert status.generated_at is None


def test_finalization_atomically_queues_exact_snapshot(workbench_context):
    engine, _, actor, sample = workbench_context
    workbench = make_workbench(engine, RecordingObjectStore())
    method = next(
        item for item in workbench.load(actor, sample.barcode_value).methods
        if item.test_type == TestType.DGA
    )
    record = workbench.add_test(actor, sample.barcode_value, _dga(method.id))

    workbench.finalize(actor, sample.barcode_value)

    status = LaboratoryReports(engine, AuditTrail(), MemoryFileStore()).get_report_by_barcode(
        actor, sample.barcode_value
    )
    assert status.state == ReportState.QUEUED
    with engine.connect() as connection:
        row = connection.execute(
            text(
                """SELECT r.report_snapshot,r.snapshot_schema_version,
                r.finalization_token,r.generation_token,s.testing_finalization_token
                FROM laboratory_reports r JOIN oil_samples s ON s.id=r.oil_sample_id
                WHERE s.barcode_value=:barcode"""
            ),
            {'barcode': sample.barcode_value},
        ).mappings().one()
    snapshot = row['report_snapshot']
    assert row['snapshot_schema_version'] == 1
    assert row['finalization_token'] == row['testing_finalization_token']
    assert row['generation_token'] is not None
    assert snapshot['schema_version'] == 1
    assert snapshot['sample']['barcode'] == sample.barcode_value
    assert snapshot['sample']['asset_snapshot']['customer_name'] == 'Prairie Solar LLC'
    assert snapshot['sample']['asset_snapshot']['equipment_path'][-1]['serial_number'] == 'TX-CURRENT-2002'
    assert snapshot['acknowledged_warning_codes'] == []
    assert snapshot['selected_results'][0]['test_id'] == str(record.id)
    assert snapshot['selected_results'][0]['test_type'] == 'DGA'
    assert snapshot['selected_results'][0]['result']['h2'] == {
        'qualifier': 'EQ',
        'value': '10.125000',
    }
    assert snapshot['finalization']['token'] == str(row['finalization_token'])
    assert snapshot['finalization']['finalized_by_display_name'] == 'Workbench Admin'


def test_failed_finalization_does_not_queue_report(workbench_context):
    engine, _, actor, sample = workbench_context
    workbench = make_workbench(engine, RecordingObjectStore())

    with pytest.raises(LaboratoryError) as captured:
        workbench.finalize(actor, sample.barcode_value)

    assert captured.value.code == 'no_active_tests'
    with engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM laboratory_reports')).scalar_one() == 0


def test_withdrawal_invalidates_and_refinalization_reuses_current_row(workbench_context):
    engine, _, actor, sample = workbench_context
    workbench = make_workbench(engine, RecordingObjectStore())
    method = next(
        item for item in workbench.load(actor, sample.barcode_value).methods
        if item.test_type == TestType.DGA
    )
    record = workbench.add_test(actor, sample.barcode_value, _dga(method.id))
    workbench.finalize(actor, sample.barcode_value)
    with engine.connect() as connection:
        first = connection.execute(
            text('SELECT id,finalization_token,generation_token FROM laboratory_reports')
        ).mappings().one()

    workbench.withdraw_finalization(actor, sample.barcode_value, 'correct result')
    unavailable = LaboratoryReports(engine, AuditTrail(), MemoryFileStore()).get_report_by_barcode(
        actor, sample.barcode_value
    )
    assert unavailable.state == ReportState.UNAVAILABLE
    assert unavailable.unavailable_reason == 'sample_not_finalized'

    workbench.update_test(actor, sample.barcode_value, record.id, _dga(method.id, h2='14.000'))
    workbench.finalize(actor, sample.barcode_value)
    with engine.connect() as connection:
        second = connection.execute(
            text('SELECT id,finalization_token,generation_token,report_snapshot FROM laboratory_reports')
        ).mappings().one()
    assert second['id'] == first['id']
    assert second['finalization_token'] != first['finalization_token']
    assert second['generation_token'] != first['generation_token']
    assert second['report_snapshot']['selected_results'][0]['result']['h2']['value'] == '14.000000'


def test_report_queue_failure_rolls_back_finalization(workbench_context):
    engine, _, actor, sample = workbench_context

    class FailingReportLifecycle:
        def queue_current(self, *_args):
            raise RuntimeError('queue unavailable')

        def invalidate_current(self, *_args):
            raise AssertionError('not called')

    workbench = make_workbench(
        engine,
        RecordingObjectStore(),
        report_lifecycle=FailingReportLifecycle(),
    )
    method = next(
        item for item in workbench.load(actor, sample.barcode_value).methods
        if item.test_type == TestType.DGA
    )
    workbench.add_test(actor, sample.barcode_value, _dga(method.id))

    with pytest.raises(RuntimeError, match='queue unavailable'):
        workbench.finalize(actor, sample.barcode_value)

    with engine.connect() as connection:
        row = connection.execute(
            text(
                'SELECT testing_status,testing_finalization_token FROM oil_samples WHERE id=:id'
            ),
            {'id': sample.id},
        ).mappings().one()
        report_count = connection.execute(
            text('SELECT count(*) FROM laboratory_reports')
        ).scalar_one()
    assert row['testing_status'] == 'OPEN'
    assert row['testing_finalization_token'] is None
    assert report_count == 0


def test_pre_migration_finalization_token_requires_refinalization(workbench_context):
    engine, _, actor, sample = workbench_context
    with engine.begin() as connection:
        connection.execute(
            text(
                """UPDATE oil_samples SET testing_status='FINALIZED',
                testing_finalized_by=:actor,testing_finalized_at=:now,
                testing_finalization_token=NULL WHERE id=:sample"""
            ),
            {
                'actor': actor.user_id,
                'sample': sample.id,
                'now': datetime(2026, 8, 5, tzinfo=timezone.utc),
            },
        )

    status = LaboratoryReports(engine, AuditTrail(), MemoryFileStore()).get_report_by_barcode(
        actor, sample.barcode_value
    )

    assert status.state == ReportState.UNAVAILABLE
    assert status.unavailable_reason == 'refinalization_required'


def test_http_report_lookup_exposes_safe_current_state(workbench_context):
    engine, _, actor, sample = workbench_context
    settings = Settings(
        database_url=engine.url.render_as_string(hide_password=False),
        cookie_secure=False,
        auth_allowed_origins='http://127.0.0.1:8080',
    )

    with TestClient(create_app(settings)) as client:
        login = client.post(
            '/api/auth/login',
            headers={'Origin': 'http://127.0.0.1:8080'},
            json={'username': 'workbench-admin', 'password': CHANGED_PASSWORD},
        )
        assert login.status_code == 200
        response = client.get(
            f'/api/laboratory/reports/by-barcode/{sample.barcode_value}'
        )

    assert response.status_code == 200
    assert response.json() == {
        'barcode': sample.barcode_value,
        'state': 'UNAVAILABLE',
        'unavailable_reason': 'sample_not_finalized',
        'error_code': None,
        'requested_at': None,
        'generated_at': None,
    }


def test_worker_claim_completion_and_verified_file_read(workbench_context):
    engine, actor, sample, store = _queue_one(workbench_context)
    now = datetime(2026, 8, 6, 10, 0, tzinfo=timezone.utc)
    reports = LaboratoryReports(engine, AuditTrail(clock=lambda: now), store, clock=lambda: now)

    claim = reports.claim_next_report('worker-a', lease_seconds=30)
    assert claim is not None
    assert claim.snapshot['sample']['barcode'] == sample.barcode_value
    content = b'%PDF-1.4 test report'
    key = f'laboratory/reports/{claim.generation_token}/{claim.claim_token}.pdf'
    store.put(object_key=key, content=content, content_type='application/pdf')
    reports.complete_report(
        claim,
        object_key=key,
        content_sha256=sha256(content).hexdigest(),
        byte_size=len(content),
        generated_at=now,
    )

    status = reports.get_report_by_barcode(actor, sample.barcode_value)
    report_file = reports.read_report_file(actor, sample.barcode_value)
    assert status.state == ReportState.READY
    assert report_file.content == content
    assert report_file.filename == f'{sample.barcode_value}.pdf'
    assert report_file.generated_at == now


def test_expired_lease_is_reclaimed_and_stale_completion_is_rejected(workbench_context):
    engine, _, _, store = _queue_one(workbench_context)
    clock_value = [datetime(2026, 8, 6, 10, 0, tzinfo=timezone.utc)]
    reports = LaboratoryReports(
        engine, AuditTrail(), store, clock=lambda: clock_value[0]
    )
    stale = reports.claim_next_report('worker-a', lease_seconds=10)
    assert stale is not None
    clock_value[0] += timedelta(seconds=11)
    current = reports.claim_next_report('worker-b', lease_seconds=10)
    assert current is not None
    assert current.claim_token != stale.claim_token

    with pytest.raises(StaleReportClaim):
        reports.complete_report(
            stale,
            object_key='stale.pdf',
            content_sha256=sha256(b'stale').hexdigest(),
            byte_size=5,
            generated_at=clock_value[0],
        )


def test_failure_is_visible_and_retry_preserves_snapshot(workbench_context):
    engine, actor, sample, store = _queue_one(workbench_context)
    reports = LaboratoryReports(engine, AuditTrail(), store)
    claim = reports.claim_next_report('worker-a', lease_seconds=30)
    assert claim is not None
    reports.fail_report(claim, 'object_storage_unavailable')
    failed = reports.get_report_by_barcode(actor, sample.barcode_value)
    assert failed.state == ReportState.FAILED
    assert failed.error_code == 'object_storage_unavailable'

    retried = reports.retry_report(actor, sample.barcode_value)
    next_claim = reports.claim_next_report('worker-b', lease_seconds=30)
    assert retried.state == ReportState.QUEUED
    assert next_claim is not None
    assert next_claim.generation_token != claim.generation_token
    assert next_claim.snapshot == claim.snapshot


def test_retry_requires_finalize_permission(workbench_context):
    engine, actor, sample, store = _queue_one(workbench_context)
    reports = LaboratoryReports(engine, AuditTrail(), store)
    claim = reports.claim_next_report('worker-a', lease_seconds=30)
    assert claim is not None
    reports.fail_report(claim, 'render_failed')
    read_only = replace(actor, permissions=frozenset({'laboratory.read'}))

    with pytest.raises(Exception, match='permission_denied'):
        reports.retry_report(read_only, sample.barcode_value)


def test_checksum_mismatch_blocks_file_and_does_not_audit_download(workbench_context):
    engine, actor, sample, store = _queue_one(workbench_context)
    reports = LaboratoryReports(engine, AuditTrail(), store)
    claim = reports.claim_next_report('worker-a', lease_seconds=30)
    assert claim is not None
    store.put(object_key='current.pdf', content=b'changed', content_type='application/pdf')
    reports.complete_report(
        claim,
        object_key='current.pdf',
        content_sha256=sha256(b'original').hexdigest(),
        byte_size=len(b'original'),
        generated_at=datetime.now(timezone.utc),
    )

    with pytest.raises(LaboratoryError) as captured:
        reports.read_report_file(actor, sample.barcode_value)
    assert captured.value.code == 'report_integrity_failure'
    with engine.connect() as connection:
        audits = connection.execute(
            text("SELECT count(*) FROM audit_logs WHERE action_code='LAB_REPORT_DOWNLOADED'")
        ).scalar_one()
    assert audits == 0


def test_worker_moves_storage_failure_to_failed_and_success_to_ready(workbench_context):
    engine, actor, sample, _ = _queue_one(workbench_context)
    failing_store = MemoryFileStore(fail_put=True)
    reports = LaboratoryReports(engine, AuditTrail(), failing_store)
    worker = ReportWorker(reports, failing_store, lambda snapshot, generated_at: b'%PDF')

    assert worker.process_one('worker-a') is True
    assert reports.get_report_by_barcode(actor, sample.barcode_value).state == ReportState.FAILED

    working_store = MemoryFileStore()
    reports = LaboratoryReports(engine, AuditTrail(), working_store)
    reports.retry_report(actor, sample.barcode_value)
    worker = ReportWorker(reports, working_store, lambda snapshot, generated_at: b'%PDF')
    assert worker.process_one('worker-b') is True
    assert reports.get_report_by_barcode(actor, sample.barcode_value).state == ReportState.READY


def test_http_file_response_has_safe_inline_and_attachment_headers(workbench_context):
    engine, actor, sample, store = _queue_one(workbench_context)
    reports = LaboratoryReports(engine, AuditTrail(), store)
    claim = reports.claim_next_report('worker-a', lease_seconds=30)
    assert claim is not None
    content = b'%PDF current'
    store.put(object_key='http.pdf', content=content, content_type='application/pdf')
    reports.complete_report(
        claim,
        object_key='http.pdf',
        content_sha256=sha256(content).hexdigest(),
        byte_size=len(content),
        generated_at=datetime.now(timezone.utc),
    )
    settings = Settings(
        database_url=engine.url.render_as_string(hide_password=False),
        cookie_secure=False,
        auth_allowed_origins='http://127.0.0.1:8080',
    )

    with TestClient(create_app(settings, file_store=store)) as client:
        login = client.post(
            '/api/auth/login',
            headers={'Origin': 'http://127.0.0.1:8080'},
            json={'username': 'workbench-admin', 'password': CHANGED_PASSWORD},
        )
        assert login.status_code == 200
        inline = client.get(
            f'/api/laboratory/reports/by-barcode/{sample.barcode_value}/file?disposition=inline'
        )
        attachment = client.get(
            f'/api/laboratory/reports/by-barcode/{sample.barcode_value}/file?disposition=attachment'
        )

    assert inline.status_code == 200
    assert inline.content == content
    assert inline.headers['content-type'] == 'application/pdf'
    assert inline.headers['content-disposition'] == f'inline; filename="{sample.barcode_value}.pdf"'
    assert inline.headers['cache-control'] == 'private, no-store'
    assert inline.headers['x-content-type-options'] == 'nosniff'
    assert attachment.headers['content-disposition'] == f'attachment; filename="{sample.barcode_value}.pdf"'


def test_withdrawal_waits_for_inflight_download_then_blocks_new_reads(workbench_context):
    started, release = Event(), Event()

    class BlockingFileStore(MemoryFileStore):
        def get(self, *, object_key):
            started.set()
            assert release.wait(3)
            return super().get(object_key=object_key)

    store = BlockingFileStore()
    engine, actor, sample, _ = _queue_one(workbench_context, store)
    reports = LaboratoryReports(engine, AuditTrail(), store)
    claim = reports.claim_next_report('worker-a', lease_seconds=30)
    content = b'%PDF current'
    store.put(object_key='locked.pdf', content=content, content_type='application/pdf')
    reports.complete_report(
        claim,
        object_key='locked.pdf',
        content_sha256=sha256(content).hexdigest(),
        byte_size=len(content),
        generated_at=datetime.now(timezone.utc),
    )
    workbench = make_workbench(engine, store)

    with ThreadPoolExecutor(max_workers=2) as pool:
        download = pool.submit(reports.read_report_file, actor, sample.barcode_value)
        assert started.wait(2)
        withdrawal = pool.submit(
            workbench.withdraw_finalization,
            actor,
            sample.barcode_value,
            'invalidate report',
        )
        assert not withdrawal.done()
        release.set()
        assert download.result(timeout=3).content == content
        assert withdrawal.result(timeout=3).testing_status.value == 'OPEN'

    with pytest.raises(LaboratoryError) as captured:
        reports.read_report_file(actor, sample.barcode_value)
    assert captured.value.code == 'report_unavailable'
