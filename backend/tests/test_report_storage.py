"""Report lifecycle acceptance against isolated MinIO and Azurite, never cloud resources."""

import os
import subprocess
import sys
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from hashlib import sha256
from typing import Callable

import pytest
import psycopg
from fastapi.testclient import TestClient
from pydantic import SecretStr

from dga.laboratory.public import LaboratoryReports
from dga.laboratory.report_worker import ReportWorker
from dga.main import create_app
from dga.shared.auth.public import AuditTrail, IdentityService, IdentityError
from dga.shared.files import FileStore, ObjectStorageError
from dga.shared.file_store_factory import create_file_store
from tests.storage_fixtures import storage_case
from tests.test_laboratory_workbench import workbench_context, make_workbench, _dga, TestType, CHANGED_PASSWORD
from tests.test_storage_workflows import login_headers


@dataclass
class ObservedFiles:
    """Observe bytes crossing the external FileStore boundary; persist through the real provider."""

    delegate: FileStore
    uploaded: dict[str, bytes] = field(default_factory=dict)
    before_put: Callable[[], None] | None = None
    after_put: Callable[[], None] | None = None
    before_delete: Callable[[], None] | None = None

    def put(self, *, object_key: str, content: bytes, content_type: str) -> None:
        if self.before_put:
            self.before_put()
        self.delegate.put(object_key=object_key, content=content, content_type=content_type)
        self.uploaded[object_key] = content
        if self.after_put:
            self.after_put()

    def get(self, *, object_key: str) -> bytes:
        return self.delegate.get(object_key=object_key)

    def delete(self, *, object_key: str) -> None:
        if self.before_delete:
            self.before_delete()
        self.delegate.delete(object_key=object_key)


@pytest.fixture
def report_context(storage_case, workbench_context):
    engine, _, actor, sample = workbench_context
    files = ObservedFiles(create_file_store(storage_case.settings))
    workbench = make_workbench(engine, files)
    method = next(m for m in workbench.load(actor, sample.barcode_value).methods if m.test_type == TestType.DGA)
    workbench.add_test(actor, sample.barcode_value, _dga(method.id))
    reports = LaboratoryReports(engine, AuditTrail(), files)
    try:
        yield storage_case, engine, actor, sample, files, workbench, reports
    finally:
        for key in files.uploaded:
            storage_case.store.delete(object_key=key)


def test_worker_pdf_is_downloadable_from_a_separate_configured_api(report_context):
    case, _, actor, sample, files, workbench, reports = report_context
    path = f'/api/laboratory/reports/by-barcode/{sample.barcode_value}'
    with TestClient(create_app(case.settings)) as api:
        headers = login_headers(api, 'workbench-admin', CHANGED_PASSWORD)
        queued = api.post(f'/api/laboratory/samples/{sample.barcode_value}/finalization',
                          headers=headers, json={'acknowledged_warning_codes': []})
        assert queued.status_code == 200
        assert api.get(path).json()['state'] == 'QUEUED'
        assert api.get(path + '/file').json()['code'] == 'report_not_ready'

    worker = ReportWorker(reports, files, clock=lambda: datetime(2026, 8, 6, tzinfo=timezone.utc))
    assert worker.process_one('provider-report-worker')
    key, expected = next(iter(files.uploaded.items()))
    assert expected.startswith(b'%PDF-')
    assert case.store.get(object_key=key) == expected

    # This app creates its own adapter and connection pool from configuration.
    with TestClient(create_app(case.settings)) as api:
        assert api.get(path + '/file').status_code == 401
        login_headers(api, 'workbench-admin', CHANGED_PASSWORD)
        assert api.get(path).json()['state'] == 'READY'
        for disposition in ('inline', 'attachment'):
            response = api.get(path + '/file', params={'disposition': disposition})
            assert response.status_code == 200
            assert response.content == expected
            assert response.headers['content-type'] == 'application/pdf'
            assert response.headers['content-disposition'] == f'{disposition}; filename="{sample.barcode_value}.pdf"'
            assert response.headers['cache-control'] == 'private, no-store'
            assert response.headers['x-content-type-options'] == 'nosniff'
        workbench.withdraw_finalization(actor, sample.barcode_value, 'correct test result')
        assert api.get(path).json()['state'] == 'UNAVAILABLE'
        assert api.get(path + '/file').json()['code'] == 'report_unavailable'


@pytest.mark.parametrize('failure_type', [ObjectStorageError, OSError])
def test_storage_outage_is_failed_and_retry_after_recovery_delivers_pdf(report_context, failure_type):
    case, _, actor, sample, files, workbench, reports = report_context
    workbench.finalize(actor, sample.barcode_value)
    path = f'/api/laboratory/reports/by-barcode/{sample.barcode_value}'

    def storage_outage():
        assert reports.get_report_by_barcode(actor, sample.barcode_value).state == 'GENERATING'
        raise failure_type('isolated transport failure: secret-marker')

    files.before_put = storage_outage
    worker = ReportWorker(reports, files)
    assert worker.process_one('outage-worker')
    with TestClient(create_app(case.settings)) as api:
        headers = login_headers(api, 'workbench-admin', CHANGED_PASSWORD)
        status = api.get(path)
        assert status.json()['state'] == 'FAILED'
        assert status.json()['error_code'] == 'object_storage_unavailable'
        assert 'secret-marker' not in status.text
        blocked = api.get(path + '/file')
        assert blocked.status_code == 409
        assert blocked.json()['code'] == 'report_failed'
        assert api.post(path + '/retry').status_code == 403
        retry = api.post(path + '/retry', headers=headers)
        assert retry.status_code == 200
        assert retry.json()['state'] == 'QUEUED'
        files.before_put = None
        assert worker.process_one('recovered-worker')
        assert api.get(path).json()['state'] == 'READY'
        response = api.get(path + '/file')
        assert response.status_code == 200
        assert response.content == next(iter(files.uploaded.values()))


@pytest.mark.parametrize('damage', ['missing', 'same-size-corruption', 'truncated', 'permission-denied'])
def test_missing_or_corrupt_pdf_is_not_served_or_audited_as_a_download(report_context, damage):
    case, engine, actor, sample, files, workbench, reports = report_context
    workbench.finalize(actor, sample.barcode_value)
    assert ReportWorker(reports, files).process_one('integrity-worker')
    key, original = next(iter(files.uploaded.items()))
    settings = case.settings
    if damage == 'missing':
        case.store.delete(object_key=key)
        expected_error = 'object_storage_unavailable'
    elif damage == 'permission-denied':
        credential = 'azure_blob_emulator_key' if case.container is not None else 'object_store_secret_key'
        settings = settings.model_copy(update={credential: SecretStr('YmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmI=')})
        expected_error = 'object_storage_unavailable'
    else:
        damaged = b'!' + original[1:] if damage == 'same-size-corruption' else original[:-1]
        case.store.put(object_key=key, content=damaged, content_type='application/pdf')
        expected_error = 'report_integrity_failure'
    with TestClient(create_app(settings)) as api:
        login_headers(api, 'workbench-admin', CHANGED_PASSWORD)
        response = api.get(f'/api/laboratory/reports/by-barcode/{sample.barcode_value}/file')
        assert response.status_code == 503
        assert response.json()['code'] == expected_error
        assert response.headers['cache-control'] == 'no-store'
        assert key not in response.text
    assert not any(event['action_code'] == 'LAB_REPORT_DOWNLOADED'
                   for event in IdentityService(engine).audit_events(actor))


@pytest.mark.parametrize('cleanup_fails', [False, True])
def test_proven_stale_upload_is_cleaned_best_effort_and_never_served(report_context, cleanup_fails):
    case, _, actor, sample, files, workbench, reports = report_context
    workbench.finalize(actor, sample.barcode_value)

    def withdraw_during_upload():
        assert reports.get_report_by_barcode(actor, sample.barcode_value).state == 'GENERATING'
        workbench.withdraw_finalization(actor, sample.barcode_value, 'correct during rendering')

    def cleanup_outage():
        raise ObjectStorageError('isolated cleanup unavailable')

    files.after_put = withdraw_during_upload
    files.before_delete = cleanup_outage if cleanup_fails else None
    worker = ReportWorker(reports, files)
    assert worker.process_one('stale-worker')
    stale_key, stale_bytes = next(iter(files.uploaded.items()))
    if cleanup_fails:
        assert case.store.get(object_key=stale_key) == stale_bytes
    else:
        with pytest.raises(ObjectStorageError):
            case.store.get(object_key=stale_key)
    with TestClient(create_app(case.settings)) as api:
        login_headers(api, 'workbench-admin', CHANGED_PASSWORD)
        path = f'/api/laboratory/reports/by-barcode/{sample.barcode_value}'
        assert api.get(path + '/file').json()['code'] == 'report_unavailable'
        files.after_put = None
        files.before_delete = None
        workbench.finalize(actor, sample.barcode_value)
        assert worker.process_one('current-worker')
        current_key = next(key for key in files.uploaded if key != stale_key)
        response = api.get(path + '/file')
        assert response.status_code == 200
        assert response.content == case.store.get(object_key=current_key)


@pytest.mark.parametrize('commit_succeeded', [False, True])
def test_uncertain_report_commit_retains_pdf_for_both_database_outcomes(report_context, monkeypatch, commit_succeeded):
    case, _, actor, sample, files, workbench, reports = report_context
    workbench.finalize(actor, sample.barcode_value)
    pending = False
    original_commit = psycopg.Connection.commit

    def arm_completion_fault():
        nonlocal pending
        # The object exists, but report completion has not committed yet.
        assert reports.get_report_by_barcode(actor, sample.barcode_value).state == 'GENERATING'
        pending = True

    def lose_commit_response(connection):
        nonlocal pending
        if pending:
            pending = False
            if commit_succeeded:
                original_commit(connection)
            else:
                connection.rollback()
            raise psycopg.OperationalError('isolated lost COMMIT response: secret-marker')
        original_commit(connection)

    files.after_put = arm_completion_fault
    monkeypatch.setattr(psycopg.Connection, 'commit', lose_commit_response)
    worker = ReportWorker(reports, files)
    assert worker.process_one('uncertain-worker')
    assert not pending
    key, expected = next(iter(files.uploaded.items()))
    assert case.store.get(object_key=key) == expected
    with TestClient(create_app(case.settings)) as api:
        headers = login_headers(api, 'workbench-admin', CHANGED_PASSWORD)
        path = f'/api/laboratory/reports/by-barcode/{sample.barcode_value}'
        status = api.get(path)
        assert status.json()['state'] == ('READY' if commit_succeeded else 'FAILED')
        assert 'secret-marker' not in status.text
        if not commit_succeeded:
            assert api.get(path + '/file').json()['code'] == 'report_failed'
            assert api.post(path + '/retry', headers=headers).status_code == 200
            files.after_put = None
            assert worker.process_one('reconciled-worker')
        response = api.get(path + '/file')
        assert response.status_code == 200
        assert response.content in files.uploaded.values()
        # Recovery must not remove evidence of the earlier uncertain completion.
        assert case.store.get(object_key=key) == expected


def test_report_read_and_retry_require_the_existing_business_permissions(report_context):
    _, engine, actor, sample, files, workbench, reports = report_context
    workbench.finalize(actor, sample.barcode_value)
    assert ReportWorker(reports, files).process_one('authorization-worker')
    denied = replace(actor, permissions=frozenset())
    with pytest.raises(IdentityError) as read_error:
        reports.read_report_file(denied, sample.barcode_value)
    assert (read_error.value.code, read_error.value.status) == ('permission_denied', 403)
    read_only = replace(actor, permissions=frozenset({'laboratory.read'}))
    with pytest.raises(IdentityError) as retry_error:
        reports.retry_report(read_only, sample.barcode_value)
    assert (retry_error.value.code, retry_error.value.status) == ('permission_denied', 403)
    assert not any(event['action_code'] == 'LAB_REPORT_DOWNLOADED'
                   for event in IdentityService(engine).audit_events(actor))


def test_pdf_size_metadata_is_enforced_even_when_hash_matches(report_context):
    case, _, actor, sample, files, workbench, reports = report_context
    workbench.finalize(actor, sample.barcode_value)
    claim = reports.claim_next_report('size-worker', lease_seconds=30)
    assert claim is not None
    content = b'%PDF-1.4 isolated size-check evidence'
    key = f'{case.prefix}/size-check.pdf'
    files.put(object_key=key, content=content, content_type='application/pdf')
    reports.complete_report(claim, object_key=key, content_sha256=sha256(content).hexdigest(),
                            byte_size=len(content) + 1, generated_at=datetime.now(timezone.utc))
    with TestClient(create_app(case.settings)) as api:
        login_headers(api, 'workbench-admin', CHANGED_PASSWORD)
        response = api.get(f'/api/laboratory/reports/by-barcode/{sample.barcode_value}/file')
        assert response.status_code == 503
        assert response.json()['code'] == 'report_integrity_failure'


def test_import_worker_validates_parsed_rows_without_blob_configuration(database_url):
    from tests.test_asset_import import import_context, workbook, new_rows

    engine, actor, imports, _ = import_context(database_url)
    try:
        batch = imports.submit(actor, filename='source.xlsx', content=workbook(new_rows()))
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(('OBJECT_STORE_', 'AZURE_BLOB_'))}
        env.update(DATABASE_URL=database_url, OBJECT_STORE_PROVIDER='azure')
        # Explicitly selected but incomplete Blob configuration must not block this worker.
        subprocess.run([sys.executable, '-m', 'dga.assets.import_worker', '--once'],
                       env=env, check=True, capture_output=True, timeout=20)
        assert imports.get(actor, batch['id'])['state'] == 'VALIDATED'
    finally:
        engine.dispose()
