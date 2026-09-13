from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text

from dga.laboratory.public import LaboratoryConfiguration, MethodVersionInput
from dga.laboratory.public import LaboratoryError
from dga.laboratory.public import InstrumentInput, CalibrationInput
from dga.shared.auth.public import IdentityError
from pydantic import ValidationError
from dga.laboratory.public import PackageInput
from dga.laboratory.public import QaExecution
from tests.test_laboratory_workbench import workbench_context, make_workbench, RecordingObjectStore, _moisture


def method_input(version='LAB-TEST-1', **overrides):
    payload = dict(test_type='MOISTURE', display_name='Lab approved test configuration',
                   version_label=version, fields=[dict(code='MOISTURE', display_name='微水',
                   unit_code=None, display_decimal_places=2, detection_limit='0.01')])
    payload.update(overrides)
    return MethodVersionInput(**payload)


def test_create_method_and_preserve_previous_test_version(workbench_context):
    engine, _, actor, sample = workbench_context
    config = LaboratoryConfiguration(engine)
    first = config.create_method(actor, method_input())
    bench = make_workbench(engine, RecordingObjectStore())
    record = bench.add_test(actor, sample.barcode_value, _moisture(first['id'], value='8.50'))
    second = config.create_method(actor, method_input('LAB-TEST-2', fields=[dict(
        code='MOISTURE', display_name='New label', unit_code=None, display_decimal_places=1)]))
    config.set_method_active(actor, first['id'], False)
    current = bench.load(actor, sample.barcode_value)
    assert current.tests[0].id == record.id
    assert current.tests[0].method.version_label == 'LAB-TEST-1'
    assert current.tests[0].method.fields[0].display_decimal_places == 2
    assert second['id'] != first['id']
    with pytest.raises(LaboratoryError, match='configured_precision_exceeded'):
        bench.add_test(actor, sample.barcode_value, _moisture(second['id'], value='8.51'))


def test_method_controls_validate_range_and_qualifier(workbench_context):
    engine, _, actor, sample = workbench_context
    config = LaboratoryConfiguration(engine)
    method = config.create_method(actor, method_input(fields=[dict(code='MOISTURE', display_name='微水',
        unit_code='TEST-UNIT', allowed_qualifiers=['EQ'], minimum='1', maximum='10')]))
    bench = make_workbench(engine, RecordingObjectStore())
    with pytest.raises(LaboratoryError, match='configured_range_exceeded'):
        bench.add_test(actor, sample.barcode_value, _moisture(method['id'], value='11'))
    record = bench.add_test(actor, sample.barcode_value, _moisture(method['id'], value='10'))
    assert record.method.fields[0].unit_code == 'TEST-UNIT'
    assert record.method.fields[0].allowed_qualifiers == ('EQ',)


def test_calibration_at_measurement_time_is_saved_not_recomputed(workbench_context):
    engine, _, actor, sample = workbench_context
    config = LaboratoryConfiguration(engine)
    method = config.create_method(actor, method_input())
    instrument = config.create_instrument(actor, InstrumentInput(code='M-01', name='Moisture meter'))
    config.add_calibration(actor, instrument['id'], CalibrationInput(
        calibrated_on=date(2026, 1, 1), expires_on=date(2026, 8, 2), outcome='VALID'))
    bench = make_workbench(engine, RecordingObjectStore())
    record = bench.add_test(actor, sample.barcode_value,
        replace(_moisture(method['id'], value='8.50'), instrument_id=instrument['id']))
    assert record.quality_snapshot['calibration']['status'] == 'EXPIRED'
    config.add_calibration(actor, instrument['id'], CalibrationInput(
        calibrated_on=date(2026, 8, 3), expires_on=date(2027, 8, 3), outcome='VALID'))
    assert bench.load(actor, sample.barcode_value).tests[0].quality_snapshot == record.quality_snapshot
    assert config.catalog(actor)['instruments'][0]['code'] == 'M-01'


def test_configuration_rejects_untrusted_or_incoherent_input(workbench_context):
    engine, _, actor, _ = workbench_context
    config = LaboratoryConfiguration(engine)
    with pytest.raises(IdentityError):
        config.create_method(replace(actor, permissions=frozenset({'laboratory.read'})), method_input())
    for value in ('NaN', 'Infinity', '-1', '1000000000000'):
        with pytest.raises(ValidationError):
            method_input(fields=[dict(code='MOISTURE', display_name='微水', detection_limit=value)])
    with pytest.raises(ValidationError):
        method_input(fields=[])
    config.create_method(actor, method_input())
    with pytest.raises(LaboratoryError, match='configuration_duplicate'):
        config.create_method(actor, method_input())


def test_qa_warning_acknowledgement_and_report_evidence(workbench_context):
    from dga.laboratory.public import LaboratoryReports
    from dga.shared.auth.public import AuditTrail
    engine, _, actor, sample = workbench_context
    config = LaboratoryConfiguration(engine)
    method = config.create_method(actor, method_input(qa_checks=[dict(code='BLANK', label='空白检查')]))
    store = RecordingObjectStore()
    bench = make_workbench(engine, store)
    record = bench.add_test(actor, sample.barcode_value, _moisture(method['id'], value='8.50'))
    warnings = bench.load(actor, sample.barcode_value).finalization_assessment.warning_codes
    assert len(warnings) == 1
    with pytest.raises(LaboratoryError, match='warnings_not_acknowledged'):
        bench.finalize(actor, sample.barcode_value)
    bench.finalize(actor, sample.barcode_value, warnings)
    claim = LaboratoryReports(engine, AuditTrail(), store).claim_next_report('test', lease_seconds=30)
    assert claim.snapshot['quality_evidence'][0]['test_id'] == str(record.id)
    assert claim.snapshot['quality_evidence'][0]['qa_results'][0]['status'] == 'NOT_RUN'
    assert claim.snapshot['selected_results'][0]['method']['fields'][0]['display_decimal_places'] == 2
    assert claim.snapshot['acknowledged_warning_codes'] == list(warnings)


def test_package_required_types_are_checked_at_finalization(workbench_context):
    engine, _, actor, sample = workbench_context
    config = LaboratoryConfiguration(engine)
    method = config.create_method(actor, method_input())
    package = config.create_package(actor, PackageInput(code='ANNUAL-1', name='Annual', items=[
        dict(test_type='MOISTURE', method_version_id=method['id'], required=True)]))
    config.apply_package(actor, sample.barcode_value, package['id'])
    with pytest.raises(LaboratoryError, match='package_plan_conflict'):
        config.apply_package(actor, sample.barcode_value, package['id'])
    bench = make_workbench(engine, RecordingObjectStore())
    assert bench.load(actor, sample.barcode_value).finalization_assessment.required_missing_test_types == ('MOISTURE',)
    with pytest.raises(LaboratoryError, match='required_tests_missing'):
        bench.finalize(actor, sample.barcode_value)
    bench.add_test(actor, sample.barcode_value, _moisture(method['id'], value='8.50'))
    assert bench.finalize(actor, sample.barcode_value).testing_status == 'FINALIZED'
    with pytest.raises(LaboratoryError, match='sample_finalized'):
        config.apply_package(actor, sample.barcode_value, package['id'])


def test_changed_qa_evidence_requires_fresh_acknowledgement(workbench_context):
    engine, _, actor, sample = workbench_context
    config = LaboratoryConfiguration(engine)
    method = config.create_method(actor, method_input(qa_checks=[dict(code='BLANK', label='空白检查')]))
    bench = make_workbench(engine, RecordingObjectStore())
    submission = replace(_moisture(method['id'], value='8.50'), qa_results=(QaExecution(code='BLANK', status='FAIL', note='retry'),))
    record = bench.add_test(actor, sample.barcode_value, submission)
    before = bench.load(actor, sample.barcode_value).finalization_assessment.warning_codes
    bench.update_test(actor, sample.barcode_value, record.id, submission)
    with pytest.raises(LaboratoryError, match='warnings_not_acknowledged'):
        bench.finalize(actor, sample.barcode_value, before)
    bench.update_test(actor, sample.barcode_value, record.id, replace(submission, qa_results=(QaExecution(code='BLANK', status='PASS'),)))
    assert bench.load(actor, sample.barcode_value).finalization_assessment.warning_codes == ()


@pytest.mark.parametrize('expires,outcome,status', [
    (date(2026,8,3),'VALID','VALID'), (date(2026,8,2),'VALID','EXPIRED'),
    (None,'VALID','UNKNOWN'), (date(2027,1,1),'FAILED','FAILED'),
])
def test_calibration_boundaries(workbench_context, expires, outcome, status):
    engine, _, actor, sample = workbench_context
    config = LaboratoryConfiguration(engine)
    method = config.create_method(actor, method_input())
    instrument = config.create_instrument(actor, InstrumentInput(code='I1', name='Test instrument'))
    config.add_calibration(actor, instrument['id'], CalibrationInput(calibrated_on=date(2026,1,1), expires_on=expires, outcome=outcome))
    config.add_calibration(actor, instrument['id'], CalibrationInput(calibrated_on=date(2026,9,1), expires_on=date(2027,9,1), outcome='VALID'))
    bench = make_workbench(engine, RecordingObjectStore())
    record = bench.add_test(actor, sample.barcode_value, replace(_moisture(method['id'], value='8.50'), instrument_id=instrument['id']))
    assert record.quality_snapshot['calibration']['status'] == status
    assert len(bench.load(actor, sample.barcode_value).finalization_assessment.warning_codes) == (0 if status=='VALID' else 1)
