from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import create_engine, text

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
    UpdateSampleBasics,
)
from dga.shared.auth.public import AuditTrail, IdentityService


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


def test_same_barcode_accepts_multiple_typed_dga_results(workbench_context):
    engine, _, actor, sample = workbench_context
    with engine.begin() as connection:
        connection.execute(
            text("""UPDATE test_method_fields SET unit_code='TEST-UNIT',
            display_decimal_places=3,detection_limit=0.5
            WHERE method_version_id='66000000-0000-0000-0000-000000000001' AND field_code='H2'""")
        )
    workbench = LaboratoryWorkbench(engine, AuditTrail(), RecordingObjectStore())
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


def test_object_store_failure_does_not_create_a_test_record(workbench_context):
    engine, _, actor, sample = workbench_context
    workbench = LaboratoryWorkbench(engine, AuditTrail(), RecordingObjectStore(fail=True))
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
    workbench = LaboratoryWorkbench(engine, AuditTrail(), store)
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
    workbench = LaboratoryWorkbench(engine, AuditTrail(), RecordingObjectStore())

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
    workbench = LaboratoryWorkbench(engine, AuditTrail(), RecordingObjectStore())
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
    workbench = LaboratoryWorkbench(engine, AuditTrail(), RecordingObjectStore())
    method = next(item for item in workbench.load(actor, sample.barcode_value).methods if item.test_type == TestType.DGA)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE oil_samples SET testing_status='FINALIZED' WHERE id=:id"),
            {'id': sample.id},
        )

    with pytest.raises(LaboratoryError) as captured:
        workbench.add_test(actor, sample.barcode_value, _dga(method.id))
    assert getattr(captured.value, 'code', None) == 'sample_finalized'
    assert workbench.load(actor, sample.barcode_value).testing_status.value == 'FINALIZED'
    MoistureResultInput,
