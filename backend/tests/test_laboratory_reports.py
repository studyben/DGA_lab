from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from dga.laboratory.public import LaboratoryError, LaboratoryReports, ReportState
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


def test_open_sample_report_is_unavailable(workbench_context):
    engine, _, actor, sample = workbench_context
    reports = LaboratoryReports(engine, AuditTrail())

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

    status = LaboratoryReports(engine, AuditTrail()).get_report_by_barcode(
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
    unavailable = LaboratoryReports(engine, AuditTrail()).get_report_by_barcode(
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

    status = LaboratoryReports(engine, AuditTrail()).get_report_by_barcode(
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
