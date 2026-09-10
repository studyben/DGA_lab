from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from dga.assets.public import AssetDirectory
from dga.laboratory.public import (
    BreakdownVoltageResultInput,
    DgaResultInput,
    LaboratoryError,
    LaboratoryWorkbench,
    MoistureResultInput,
    QualifiedMeasurement,
    RawAttachment,
    ReceiveSample,
    ResultQualifier,
    SampleIdentityStatus,
    SampleRegistry,
    TestSubmission as LaboratoryTestSubmission,
    TestType as LaboratoryTestType,
    TestingStatus,
    UpdateSampleBasics,
)
from dga.shared.auth.public import AuditTrail, IdentityError, IdentityService
from dga.main import create_app
from dga.shared.config import Settings


ASSET_ID = UUID('44000000-0000-0000-0000-000000000001')
INITIAL_PASSWORD = 'Workbench initial passphrase 43!'
CHANGED_PASSWORD = 'Workbench changed passphrase 87!'


class RecordingObjectStore:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.objects: dict[str, bytes] = {}

    def put(self, *, object_key: str, content: bytes, content_type: str) -> None:
        if self.fail:
            raise OSError('object store unavailable')
        self.objects[object_key] = content

    def delete(self, *, object_key: str) -> None:
        self.objects.pop(object_key, None)


def make_workbench(engine, store, **kwargs):
    audit = AuditTrail()
    return LaboratoryWorkbench(
        engine,
        SampleRegistry(engine, AssetDirectory(engine), audit),
        audit,
        store,
        **kwargs,
    )


@pytest.fixture
def workbench_context(database_url):
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                'TRUNCATE asset_installations,formal_assets,sites,customers,'
                'auth_sessions,user_roles,audit_logs,users CASCADE'
            )
        )
        connection.execute(text('UPDATE test_method_versions SET is_active=TRUE'))
        connection.execute(
            text("INSERT INTO customers(id,customer_name) VALUES ('11000000-0000-0000-0000-000000000001','Prairie Solar LLC')")
        )
        connection.execute(
            text("INSERT INTO sites(id,customer_id,site_name,location_text) VALUES ('22000000-0000-0000-0000-000000000001','11000000-0000-0000-0000-000000000001','Prairie Sun','Texas, USA')")
        )
        connection.execute(
            text(
                """INSERT INTO formal_assets
                (id,system_asset_number,asset_type,serial_number,model,material_number,lifecycle_status)
                VALUES (:asset,'SYS-TX-002','TRANSFORMER','TX-CURRENT-2002','TX-4400','MAT-TX-41','IN_SERVICE')"""
            ),
            {'asset': ASSET_ID},
        )
        connection.execute(
            text(
                """INSERT INTO asset_installations
                (id,asset_id,parent_asset_id,site_id,valid_from,valid_to)
                VALUES ('55000000-0000-0000-0000-000000000001',:asset,NULL,
                        '22000000-0000-0000-0000-000000000001','2020-01-01T00:00:00Z',NULL)"""
            ),
            {'asset': ASSET_ID},
        )
    identity = IdentityService(engine)
    identity.bootstrap_admin('workbench-admin', 'Workbench Admin', INITIAL_PASSWORD)
    first = identity.login('workbench-admin', INITIAL_PASSWORD)
    actor = identity.change_password(first.token, INITIAL_PASSWORD, CHANGED_PASSWORD).actor
    sample = SampleRegistry(engine, AssetDirectory(engine), AuditTrail()).receive(
        actor,
        ReceiveSample(
            sampled_at=datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
            received_at=datetime(2026, 8, 2, 9, 0, tzinfo=timezone.utc),
            site_name='ignored',
            equipment_serial='ignored',
            notes='annual sample',
            container_count=2,
            identity_status=SampleIdentityStatus.ASSOCIATED,
            formal_asset_id=ASSET_ID,
        ),
    )
    yield engine, identity, actor, sample
    engine.dispose()


TestType = LaboratoryTestType
TestSubmission = LaboratoryTestSubmission
TestType.__test__ = False
TestSubmission.__test__ = False
TestingStatus.__test__ = False


def _dga(method_id, *, h2='10.125', qualifier=ResultQualifier.EQ):
    values = {
        code: QualifiedMeasurement(ResultQualifier.EQ, Decimal(value))
        for code, value in {
            'H2': h2,
            'CH4': '11.250',
            'C2H2': '0.125',
            'C2H4': '4.500',
            'C2H6': '5.750',
            'CO': '120.000',
            'CO2': '900.000',
        }.items()
    }
    values['H2'] = QualifiedMeasurement(qualifier, None if qualifier == ResultQualifier.ND else Decimal(h2))
    return TestSubmission(
        test_type=TestType.DGA,
        method_version_id=method_id,
        measured_at=datetime(2026, 8, 3, 15, 30, tzinfo=timezone.utc),
        instrument_name='GC-01',
        notes='first pass',
        result=DgaResultInput(**{key.lower(): value for key, value in values.items()}),
    )


def _moisture(method_id, *, value='8.500'):
    return TestSubmission(
        test_type=TestType.MOISTURE,
        method_version_id=method_id,
        measured_at=datetime(2026, 8, 3, 16, 0, tzinfo=timezone.utc),
        instrument_name='MOISTURE-01',
        notes=None,
        result=MoistureResultInput(
            QualifiedMeasurement(ResultQualifier.EQ, Decimal(value))
        ),
    )


def test_same_barcode_accepts_multiple_typed_dga_results(workbench_context):
    engine, _, actor, sample = workbench_context
    with engine.begin() as connection:
        connection.execute(
            text("""UPDATE test_method_fields SET unit_code='TEST-UNIT',
            display_decimal_places=3,detection_limit=0.5
            WHERE method_version_id='66000000-0000-0000-0000-000000000001' AND field_code='H2'""")
        )
    workbench = make_workbench(engine, RecordingObjectStore())
    loaded = workbench.load(actor, sample.barcode_value)
    dga_method = next(method for method in loaded.methods if method.test_type == TestType.DGA)

    first = workbench.add_test(actor, sample.barcode_value, _dga(dga_method.id))
    second = workbench.add_test(actor, sample.barcode_value, _dga(dga_method.id, h2='12.500'))

    assert first.id != second.id
    assert first.test_type == TestType.DGA
    assert first.result.h2.value == Decimal('10.125')
    assert second.result.h2.value == Decimal('12.500')
    reloaded = workbench.load(actor, sample.barcode_value)
    assert [record.id for record in reloaded.tests] == [first.id, second.id]
    assert [field.code for field in dga_method.fields] == [
        'H2', 'CH4', 'C2H2', 'C2H4', 'C2H6', 'CO', 'CO2'
    ]
    assert dga_method.fields[0].unit_code == 'TEST-UNIT'
    assert dga_method.fields[0].display_decimal_places == 3
    assert dga_method.fields[0].detection_limit == Decimal('0.500000')


def test_one_report_result_can_be_selected_per_test_type(workbench_context):
    engine, identity, actor, sample = workbench_context
    workbench = make_workbench(engine, RecordingObjectStore())
    method = next(
        item for item in workbench.load(actor, sample.barcode_value).methods
        if item.test_type == TestType.DGA
    )
    first = workbench.add_test(actor, sample.barcode_value, _dga(method.id))
    second = workbench.add_test(
        actor,
        sample.barcode_value,
        _dga(method.id, h2='12.500'),
    )

    workbench.select_report_result(actor, sample.barcode_value, first.id)
    first_selection = workbench.load(actor, sample.barcode_value)
    assert [record.selected_for_report for record in first_selection.tests] == [True, False]

    workbench.select_report_result(actor, sample.barcode_value, second.id)
    workbench.select_report_result(actor, sample.barcode_value, second.id)
    second_selection = workbench.load(actor, sample.barcode_value)
    assert [record.selected_for_report for record in second_selection.tests] == [False, True]
    selection_events = [
        event for event in identity.audit_events(actor)
        if event['action_code'] == 'REPORT_RESULT_SELECTED'
    ]
    assert [event['entity_id'] for event in selection_events] == [first.id, second.id]


def test_changing_a_selected_test_type_clears_its_report_selection(workbench_context):
    engine, identity, actor, sample = workbench_context
    workbench = make_workbench(engine, RecordingObjectStore())
    methods = {
        item.test_type: item
        for item in workbench.load(actor, sample.barcode_value).methods
    }
    record = workbench.add_test(actor, sample.barcode_value, _dga(methods[TestType.DGA].id))
    workbench.select_report_result(actor, sample.barcode_value, record.id)

    changed = workbench.update_test(
        actor,
        sample.barcode_value,
        record.id,
        _moisture(methods[TestType.MOISTURE].id),
    )

    assert changed.test_type == TestType.MOISTURE
    assert changed.selected_for_report is False
    assert [
        event['action_code'] for event in identity.audit_events(actor)
        if event['action_code'] == 'REPORT_RESULT_CLEARED'
    ] == ['REPORT_RESULT_CLEARED']


def test_report_selection_rejects_missing_removed_and_read_only_access(workbench_context):
    engine, _, actor, sample = workbench_context
    workbench = make_workbench(engine, RecordingObjectStore())
    method = next(
        item for item in workbench.load(actor, sample.barcode_value).methods
        if item.test_type == TestType.DGA
    )
    record = workbench.add_test(actor, sample.barcode_value, _dga(method.id))
    workbench.remove_test(actor, sample.barcode_value, record.id, 'invalid run')

    with pytest.raises(LaboratoryError) as removed:
        workbench.select_report_result(actor, sample.barcode_value, record.id)
    assert removed.value.code == 'test_not_found'

    read_only = replace(actor, permissions=frozenset({'laboratory.read'}))
    with pytest.raises(IdentityError, match='permission_denied'):
        workbench.select_report_result(read_only, sample.barcode_value, record.id)


def test_report_selection_rejects_a_test_owned_by_another_barcode(workbench_context):
    engine, _, actor, sample = workbench_context
    registry = SampleRegistry(engine, AssetDirectory(engine), AuditTrail())
    other_sample = registry.receive(
        actor,
        ReceiveSample(
            sampled_at=datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc),
            received_at=datetime(2026, 8, 5, 9, 0, tzinfo=timezone.utc),
            site_name='ignored',
            equipment_serial='ignored',
            notes='another oil sample',
            container_count=1,
            identity_status=SampleIdentityStatus.ASSOCIATED,
            formal_asset_id=ASSET_ID,
        ),
    )
    workbench = make_workbench(engine, RecordingObjectStore())
    method = next(
        item for item in workbench.load(actor, other_sample.barcode_value).methods
        if item.test_type == TestType.DGA
    )
    other_test = workbench.add_test(
        actor, other_sample.barcode_value, _dga(method.id)
    )

    with pytest.raises(LaboratoryError) as captured:
        workbench.select_report_result(actor, sample.barcode_value, other_test.id)
    assert captured.value.code == 'test_not_found'


def test_database_rejects_two_selected_active_results_of_one_type(workbench_context):
    engine, _, actor, sample = workbench_context
    workbench = make_workbench(engine, RecordingObjectStore())
    method = next(
        item for item in workbench.load(actor, sample.barcode_value).methods
        if item.test_type == TestType.DGA
    )
    first = workbench.add_test(actor, sample.barcode_value, _dga(method.id))
    second = workbench.add_test(actor, sample.barcode_value, _dga(method.id, h2='12.500'))
    workbench.select_report_result(actor, sample.barcode_value, first.id)

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text('UPDATE laboratory_tests SET selected_for_report=TRUE WHERE id=:id'),
                {'id': second.id},
            )

    selected = [
        record.id for record in workbench.load(actor, sample.barcode_value).tests
        if record.selected_for_report
    ]
    assert selected == [first.id]


def test_database_rejects_finalized_status_without_finalizer_metadata(workbench_context):
    engine, _, actor, sample = workbench_context

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE oil_samples SET testing_status='FINALIZED' WHERE id=:id"),
                {'id': sample.id},
            )

    assert make_workbench(
        engine, RecordingObjectStore()
    ).load(actor, sample.barcode_value).testing_status == TestingStatus.OPEN


def test_concurrent_report_selections_leave_one_current_result(workbench_context):
    engine, _, actor, sample = workbench_context
    workbench = make_workbench(engine, RecordingObjectStore())
    method = next(
        item for item in workbench.load(actor, sample.barcode_value).methods
        if item.test_type == TestType.DGA
    )
    records = [
        workbench.add_test(actor, sample.barcode_value, _dga(method.id, h2=value))
        for value in ('10.125', '12.500')
    ]

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(
            lambda record: workbench.select_report_result(
                actor, sample.barcode_value, record.id
            ),
            records,
        ))

    selected = [
        record for record in workbench.load(actor, sample.barcode_value).tests
        if record.selected_for_report
    ]
    assert len(selected) == 1
    assert selected[0].id in {record.id for record in records}


def test_multiple_results_require_selection_before_overall_finalization(workbench_context):
    engine, _, actor, sample = workbench_context
    workbench = make_workbench(engine, RecordingObjectStore())
    method = next(
        item for item in workbench.load(actor, sample.barcode_value).methods
        if item.test_type == TestType.DGA
    )
    first = workbench.add_test(actor, sample.barcode_value, _dga(method.id))
    workbench.add_test(actor, sample.barcode_value, _dga(method.id, h2='12.500'))

    with pytest.raises(LaboratoryError) as missing:
        workbench.finalize(actor, sample.barcode_value)
    assert missing.value.code == 'report_result_selection_required'
    assert missing.value.details == {'test_types': ['DGA']}

    workbench.select_report_result(actor, sample.barcode_value, first.id)
    finalized = workbench.finalize(actor, sample.barcode_value)

    assert finalized.testing_status == TestingStatus.FINALIZED
    assert finalized.testing_finalized_by == actor.user_id
    assert finalized.testing_finalized_at is not None
    with pytest.raises(LaboratoryError, match='sample_finalized'):
        workbench.add_test(actor, sample.barcode_value, _dga(method.id))
    with pytest.raises(LaboratoryError, match='sample_finalized'):
        workbench.select_report_result(actor, sample.barcode_value, first.id)


def test_pending_identity_and_empty_testing_block_finalization_and_are_audited(workbench_context):
    engine, identity, actor, sample = workbench_context
    workbench = make_workbench(engine, RecordingObjectStore())

    with pytest.raises(LaboratoryError) as empty:
        workbench.finalize(actor, sample.barcode_value)
    assert empty.value.code == 'no_active_tests'
    assert workbench.load(actor, sample.barcode_value).finalization_assessment.blocking_codes == (
        'no_active_tests',
    )

    pending = SampleRegistry(engine, AssetDirectory(engine), AuditTrail()).receive(
        actor,
        ReceiveSample(
            sampled_at=datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc),
            received_at=datetime(2026, 8, 5, 9, 0, tzinfo=timezone.utc),
            site_name='Unconfirmed site',
            equipment_serial='UNKNOWN-TX',
            notes=None,
            container_count=1,
            identity_status=SampleIdentityStatus.IDENTITY_PENDING,
        ),
    )
    method = next(
        item for item in workbench.load(actor, pending.barcode_value).methods
        if item.test_type == TestType.DGA
    )
    workbench.add_test(actor, pending.barcode_value, _dga(method.id))
    with pytest.raises(LaboratoryError) as unconfirmed:
        workbench.finalize(actor, pending.barcode_value)
    assert unconfirmed.value.code == 'sample_identity_not_confirmed'

    attempts = [
        event for event in identity.audit_events(actor)
        if event['action_code'] == 'LAB_TESTING_FINALIZATION_ATTEMPT'
    ]
    assert [event['result'] for event in attempts] == ['FAILURE', 'FAILURE']


def test_single_result_is_auto_selected_and_label_can_be_reprinted_after_finalization(workbench_context):
    engine, identity, actor, sample = workbench_context
    registry = SampleRegistry(engine, AssetDirectory(engine), AuditTrail())
    workbench = make_workbench(engine, RecordingObjectStore())
    method = next(
        item for item in workbench.load(actor, sample.barcode_value).methods
        if item.test_type == TestType.DGA
    )
    record = workbench.add_test(actor, sample.barcode_value, _dga(method.id))

    finalized = workbench.finalize(actor, sample.barcode_value)
    registry.record_label_print(actor, sample.barcode_value)

    assert finalized.finalization_assessment.ready is True
    assert [(item.id, item.selected_for_report) for item in finalized.tests] == [
        (record.id, True)
    ]
    assert [event.event_type.value for event in finalized.finalization_history] == ['FINALIZED']
    actions = [event['action_code'] for event in identity.audit_events(actor)]
    assert 'REPORT_RESULT_SELECTED' in actions
    assert 'BARCODE_LABEL_PRINTED' in actions


def test_removing_a_selected_result_audits_selection_clear(workbench_context):
    engine, identity, actor, sample = workbench_context
    workbench = make_workbench(engine, RecordingObjectStore())
    method = next(
        item for item in workbench.load(actor, sample.barcode_value).methods
        if item.test_type == TestType.DGA
    )
    record = workbench.add_test(actor, sample.barcode_value, _dga(method.id))
    workbench.select_report_result(actor, sample.barcode_value, record.id)

    workbench.remove_test(actor, sample.barcode_value, record.id, 'invalid selected run')

    actions = [event['action_code'] for event in identity.audit_events(actor)]
    assert actions[-2:] == ['LAB_TEST_REMOVED', 'REPORT_RESULT_CLEARED']


def test_finalized_data_survives_0006_downgrade_and_reupgrade_as_open(workbench_context):
    engine, _, actor, sample = workbench_context
    workbench = make_workbench(engine, RecordingObjectStore())
    method = next(
        item for item in workbench.load(actor, sample.barcode_value).methods
        if item.test_type == TestType.DGA
    )
    record = workbench.add_test(actor, sample.barcode_value, _dga(method.id))
    workbench.finalize(actor, sample.barcode_value)

    config = Config('alembic.ini')
    command.downgrade(config, '0005_laboratory_test_entry')
    with engine.connect() as connection:
        assert connection.execute(
            text('SELECT testing_status FROM oil_samples WHERE id=:id'),
            {'id': sample.id},
        ).scalar_one() == 'OPEN'
    command.upgrade(config, 'head')

    reloaded = workbench.load(actor, sample.barcode_value)
    assert reloaded.testing_status == TestingStatus.OPEN
    assert [(item.id, item.selected_for_report) for item in reloaded.tests] == [
        (record.id, False)
    ]


def test_finalization_locks_all_scientific_data_mutations(workbench_context):
    engine, _, actor, sample = workbench_context
    workbench = make_workbench(engine, RecordingObjectStore())
    method = next(
        item for item in workbench.load(actor, sample.barcode_value).methods
        if item.test_type == TestType.DGA
    )
    record = workbench.add_test(actor, sample.barcode_value, _dga(method.id))
    workbench.finalize(actor, sample.barcode_value)

    operations = (
        lambda: workbench.update_test(
            actor, sample.barcode_value, record.id, _dga(method.id, h2='14.000')
        ),
        lambda: workbench.remove_test(actor, sample.barcode_value, record.id, 'incorrect'),
        lambda: workbench.update_sample(
            actor,
            sample.barcode_value,
            UpdateSampleBasics(
                sample.sampled_at,
                sample.received_at,
                sample.site_name,
                sample.equipment_serial,
                'changed after finalization',
            ),
        ),
    )
    for operation in operations:
        with pytest.raises(LaboratoryError) as captured:
            operation()
        assert captured.value.code == 'sample_finalized'


def test_reasoned_withdrawal_restores_editing_and_supports_refinalization(workbench_context):
    engine, identity, actor, sample = workbench_context
    workbench = make_workbench(engine, RecordingObjectStore())
    method = next(
        item for item in workbench.load(actor, sample.barcode_value).methods
        if item.test_type == TestType.DGA
    )
    record = workbench.add_test(actor, sample.barcode_value, _dga(method.id))
    workbench.finalize(actor, sample.barcode_value)

    with pytest.raises(LaboratoryError, match='withdrawal_reason_required'):
        workbench.withdraw_finalization(actor, sample.barcode_value, '   ')
    no_finalize = replace(actor, permissions=frozenset({'laboratory.read', 'laboratory.write'}))
    with pytest.raises(IdentityError, match='permission_denied'):
        workbench.withdraw_finalization(no_finalize, sample.barcode_value, 'correction')

    reopened = workbench.withdraw_finalization(
        actor, sample.barcode_value, '仪器数据导入有误，需要修正'
    )
    changed = workbench.update_test(
        actor, sample.barcode_value, record.id, _dga(method.id, h2='14.000')
    )
    refinalized = workbench.finalize(actor, sample.barcode_value)

    assert reopened.testing_status == TestingStatus.OPEN
    assert reopened.testing_finalized_by is None
    assert reopened.testing_finalized_at is None
    assert reopened.finalization_history[-1].reason == '仪器数据导入有误，需要修正'
    assert changed.result.h2.value == Decimal('14.000')
    assert refinalized.testing_status == TestingStatus.FINALIZED
    assert [event.event_type.value for event in refinalized.finalization_history] == [
        'FINALIZED', 'WITHDRAWN', 'FINALIZED'
    ]
    actions = [event['action_code'] for event in identity.audit_events(actor)]
    assert 'LAB_TESTING_FINALIZATION_WITHDRAWN' in actions


def test_warning_codes_require_confirmation_without_implementing_qa_rules(workbench_context):
    engine, _, actor, sample = workbench_context
    workbench = make_workbench(
        engine,
        RecordingObjectStore(),
        warning_source=lambda _tests: ('QA_REVIEW_REQUIRED',),
    )
    method = next(
        item for item in workbench.load(actor, sample.barcode_value).methods
        if item.test_type == TestType.DGA
    )
    workbench.add_test(actor, sample.barcode_value, _dga(method.id))

    with pytest.raises(LaboratoryError) as warning:
        workbench.finalize(actor, sample.barcode_value)
    assert warning.value.code == 'warnings_not_acknowledged'
    assert warning.value.details == {'warning_codes': ['QA_REVIEW_REQUIRED']}

    finalized = workbench.finalize(
        actor,
        sample.barcode_value,
        acknowledged_warning_codes=('STALE_CLIENT_WARNING', 'QA_REVIEW_REQUIRED'),
    )
    assert finalized.testing_status == TestingStatus.FINALIZED


def test_concurrent_finalization_has_one_success_and_one_stable_conflict(workbench_context):
    engine, identity, actor, sample = workbench_context
    workbench = make_workbench(engine, RecordingObjectStore())
    method = next(
        item for item in workbench.load(actor, sample.barcode_value).methods
        if item.test_type == TestType.DGA
    )
    workbench.add_test(actor, sample.barcode_value, _dga(method.id))

    def finalize_once():
        try:
            workbench.finalize(actor, sample.barcode_value)
            return 'FINALIZED'
        except LaboratoryError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _index: finalize_once(), range(2)))

    assert sorted(outcomes) == ['FINALIZED', 'sample_already_finalized']
    attempts = [
        event for event in identity.audit_events(actor)
        if event['action_code'] == 'LAB_TESTING_FINALIZATION_ATTEMPT'
    ]
    assert sorted(event['result'] for event in attempts) == ['FAILURE', 'SUCCESS']


def test_http_adapter_exposes_selection_finalization_details_and_withdrawal(workbench_context):
    engine, _, actor, sample = workbench_context
    workbench = make_workbench(engine, RecordingObjectStore())
    method = next(
        item for item in workbench.load(actor, sample.barcode_value).methods
        if item.test_type == TestType.DGA
    )
    first = workbench.add_test(actor, sample.barcode_value, _dga(method.id))
    workbench.add_test(actor, sample.barcode_value, _dga(method.id, h2='12.500'))
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
        headers = {
            'Origin': 'http://127.0.0.1:8080',
            'X-CSRF-Token': login.json()['csrf_token'],
        }
        blocked = client.post(
            f'/api/laboratory/samples/{sample.barcode_value}/finalization',
            headers=headers,
            json={'acknowledged_warning_codes': []},
        )
        assert blocked.status_code == 422
        assert blocked.json() == {
            'code': 'report_result_selection_required',
            'details': {'test_types': ['DGA']},
        }
        selected = client.put(
            f'/api/laboratory/samples/{sample.barcode_value}/report-result',
            headers=headers,
            json={'test_id': str(first.id)},
        )
        assert selected.status_code == 200
        finalized = client.post(
            f'/api/laboratory/samples/{sample.barcode_value}/finalization',
            headers=headers,
            json={'acknowledged_warning_codes': []},
        )
        assert finalized.status_code == 200
        assert finalized.json()['testing_status'] == 'FINALIZED'
        withdrawn = client.post(
            f'/api/laboratory/samples/{sample.barcode_value}/finalization-withdrawals',
            headers=headers,
            json={'reason': 'correct the selected report result'},
        )
        assert withdrawn.status_code == 200
        assert withdrawn.json()['testing_status'] == 'OPEN'


def test_object_store_failure_does_not_create_a_test_record(workbench_context):
    engine, _, actor, sample = workbench_context
    workbench = make_workbench(engine, RecordingObjectStore(fail=True))
    method = next(item for item in workbench.load(actor, sample.barcode_value).methods if item.test_type == TestType.DGA)

    with pytest.raises(OSError, match='object store unavailable'):
        workbench.add_test(
            actor,
            sample.barcode_value,
            _dga(method.id),
            RawAttachment('raw.csv', 'text/csv', b'instrument,raw,data'),
        )

    assert workbench.load(actor, sample.barcode_value).tests == ()


def test_three_typed_results_preserve_qualifiers_and_support_edit_and_remove(workbench_context):
    engine, identity, actor, sample = workbench_context
    store = RecordingObjectStore()
    workbench = make_workbench(engine, store)
    methods = {method.test_type: method for method in workbench.load(actor, sample.barcode_value).methods}

    dga = workbench.add_test(actor, sample.barcode_value, _dga(methods[TestType.DGA].id))
    moisture = workbench.add_test(
        actor,
        sample.barcode_value,
        TestSubmission(
            TestType.MOISTURE,
            methods[TestType.MOISTURE].id,
            datetime(2026, 8, 3, 16, 0, tzinfo=timezone.utc),
            'MOISTURE-01',
            None,
            MoistureResultInput(QualifiedMeasurement(ResultQualifier.ND, None)),
        ),
    )
    breakdown = workbench.add_test(
        actor,
        sample.barcode_value,
        TestSubmission(
            TestType.BREAKDOWN_VOLTAGE,
            methods[TestType.BREAKDOWN_VOLTAGE].id,
            datetime(2026, 8, 3, 16, 30, tzinfo=timezone.utc),
            'BDV-01',
            None,
            BreakdownVoltageResultInput(
                QualifiedMeasurement(ResultQualifier.GT, Decimal('80'))
            ),
        ),
        RawAttachment('raw-result.csv', 'text/csv', b'voltage,result\n80,GT'),
    )

    changed = workbench.update_test(
        actor,
        sample.barcode_value,
        dga.id,
        _dga(methods[TestType.DGA].id, qualifier=ResultQualifier.ND),
    )
    workbench.remove_test(actor, sample.barcode_value, moisture.id, 'duplicate entry')
    loaded = workbench.load(actor, sample.barcode_value)

    assert changed.result.h2 == QualifiedMeasurement(ResultQualifier.ND, None)
    assert [record.id for record in loaded.tests] == [dga.id, breakdown.id]
    assert breakdown.attachments[0].filename == 'raw-result.csv'
    assert list(store.objects.values()) == [b'voltage,result\n80,GT']
    assert [event['action_code'] for event in identity.audit_events(actor)][-5:] == [
        'LAB_TEST_CREATED',
        'LAB_TEST_CREATED',
        'LAB_TEST_CREATED',
        'LAB_TEST_UPDATED',
        'LAB_TEST_REMOVED',
    ]


def test_sample_basics_can_be_corrected_while_testing_is_open(workbench_context):
    engine, _, actor, sample = workbench_context
    workbench = make_workbench(engine, RecordingObjectStore())

    updated = workbench.update_sample(
        actor,
        sample.barcode_value,
        UpdateSampleBasics(
            sampled_at=datetime(2026, 8, 1, 13, 0, tzinfo=timezone.utc),
            received_at=datetime(2026, 8, 2, 9, 0, tzinfo=timezone.utc),
            site_name=sample.site_name,
            equipment_serial=sample.equipment_serial,
            notes='corrected sampling time',
        ),
    )

    assert updated.sample.sampled_at == datetime(2026, 8, 1, 13, 0, tzinfo=timezone.utc)
    assert updated.sample.notes == 'corrected sampling time'


@pytest.mark.parametrize(
    'measurement,error',
    [
        (QualifiedMeasurement(ResultQualifier.ND, Decimal('1')), 'nd_must_not_have_value'),
        (QualifiedMeasurement(ResultQualifier.LT, None), 'qualifier_requires_value'),
        (QualifiedMeasurement(ResultQualifier.EQ, Decimal('-1')), 'negative_result'),
    ],
)
def test_qualifier_and_value_combinations_are_validated(workbench_context, measurement, error):
    engine, _, actor, sample = workbench_context
    workbench = make_workbench(engine, RecordingObjectStore())
    method = next(item for item in workbench.load(actor, sample.barcode_value).methods if item.test_type == TestType.MOISTURE)
    submission = TestSubmission(
        TestType.MOISTURE,
        method.id,
        datetime(2026, 8, 3, 16, 0, tzinfo=timezone.utc),
        None,
        None,
        MoistureResultInput(measurement),
    )

    with pytest.raises(LaboratoryError) as captured:
        workbench.add_test(actor, sample.barcode_value, submission)
    assert getattr(captured.value, 'code', None) == error


def test_finalized_status_blocks_result_mutation(workbench_context):
    engine, _, actor, sample = workbench_context
    workbench = make_workbench(engine, RecordingObjectStore())
    method = next(item for item in workbench.load(actor, sample.barcode_value).methods if item.test_type == TestType.DGA)
    workbench.add_test(actor, sample.barcode_value, _dga(method.id))
    workbench.finalize(actor, sample.barcode_value)

    with pytest.raises(LaboratoryError) as captured:
        workbench.add_test(actor, sample.barcode_value, _dga(method.id))
    assert getattr(captured.value, 'code', None) == 'sample_finalized'
    assert workbench.load(actor, sample.barcode_value).testing_status.value == 'FINALIZED'


def test_historical_result_still_loads_after_its_method_is_disabled(workbench_context):
    engine, _, actor, sample = workbench_context
    workbench = make_workbench(engine, RecordingObjectStore())
    method = next(item for item in workbench.load(actor, sample.barcode_value).methods if item.test_type == TestType.DGA)
    created = workbench.add_test(actor, sample.barcode_value, _dga(method.id))
    with engine.begin() as connection:
        connection.execute(
            text('UPDATE test_method_versions SET is_active=FALSE WHERE id=:id'),
            {'id': method.id},
        )

    loaded = workbench.load(actor, sample.barcode_value)

    assert loaded.tests[0].id == created.id
    assert loaded.tests[0].method.is_active is False
    MoistureResultInput,
