from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from pydantic import ValidationError

from dga.assets.public import AssetDirectory
from dga.laboratory.public import LaboratoryConfiguration, MethodVersionInput, LaboratoryTrendSource
from dga.laboratory.public import SampleRegistry, ReceiveSample, SampleIdentityStatus, MoistureResultInput, QualifiedMeasurement, ResultQualifier
from dga.shared.auth.public import AuditTrail
from dga.condition_analysis.public import TransformerTrends, TrendQuery
from tests.test_laboratory_workbench import workbench_context, make_workbench, RecordingObjectStore, _moisture


def configured_method(engine, actor, version='TREND-1', unit='TEST-UNIT'):
    return LaboratoryConfiguration(engine).create_method(actor, MethodVersionInput(
        test_type='MOISTURE', display_name='Test configuration', version_label=version,
        fields=[dict(code='MOISTURE', display_name='微水', unit_code=unit)]))


def query(engine, actor, asset_id, **filters):
    return TransformerTrends(AssetDirectory(engine), LaboratoryTrendSource(engine)).query(
        actor, asset_id, TrendQuery(test_type='MOISTURE', analyte='MOISTURE', **filters))


def test_only_finalized_selected_report_result_enters_physical_transformer_trend(workbench_context):
    engine, _, actor, sample = workbench_context
    method = configured_method(engine, actor)
    bench = make_workbench(engine, RecordingObjectStore())
    first = bench.add_test(actor, sample.barcode_value, _moisture(method['id'], value='8'))
    second = bench.add_test(actor, sample.barcode_value, _moisture(method['id'], value='99'))
    assert query(engine, actor, sample.formal_asset_id)['points'] == []
    bench.select_report_result(actor, sample.barcode_value, first.id)
    bench.finalize(actor, sample.barcode_value)
    result = query(engine, actor, sample.formal_asset_id)
    assert [p['test_id'] for p in result['points']] == [first.id]
    assert result['statistics']['mean']['value'] == Decimal('8')
    assert result['asset'].id == sample.formal_asset_id
    assert AssetDirectory(engine).equipment_detail(actor, sample.formal_asset_id)['equipment']['asset_type'] == 'TRANSFORMER'
    assert result['points'][0]['site_name'] == 'Prairie Sun'
    assert second.id != result['points'][0]['test_id']


def add_point(engine, actor, asset_id, method, day, value, qualifier='EQ', at=None):
    at = at or datetime(2026, 8, 1, 12, tzinfo=timezone.utc) + timedelta(days=day)
    sample = SampleRegistry(engine, AssetDirectory(engine), AuditTrail()).receive(actor, ReceiveSample(
        sampled_at=at, received_at=at, site_name='input', equipment_serial='input', notes=None,
        container_count=1, identity_status=SampleIdentityStatus.ASSOCIATED, formal_asset_id=asset_id))
    bench = make_workbench(engine, RecordingObjectStore())
    submission = replace(_moisture(method, value='1'), measured_at=at,
        result=MoistureResultInput(QualifiedMeasurement(ResultQualifier(qualifier), None if value is None else Decimal(value))))
    record = bench.add_test(actor, sample.barcode_value, submission)
    warnings = bench.load(actor, sample.barcode_value).finalization_assessment.warning_codes
    bench.finalize(actor, sample.barcode_value, warnings)
    return sample, record


def test_comparability_groups_and_qualifiers_are_not_pooled(workbench_context):
    engine, _, actor, sample = workbench_context
    first = configured_method(engine, actor)
    second = configured_method(engine, actor, 'TREND-2')
    different_unit = configured_method(engine, actor, 'TREND-3', 'OTHER-UNIT')
    missing = configured_method(engine, actor, 'TREND-4', None)
    for day, method, value, qualifier in [(0, first['id'], '10', 'EQ'), (1, first['id'], None, 'ND'),
            (2, second['id'], '100', 'EQ'), (3, different_unit['id'], '999', 'EQ'),
            (4, missing['id'], '88', 'EQ')]:
        add_point(engine, actor, sample.formal_asset_id, method, day, value, qualifier)
    result = query(engine, actor, sample.formal_asset_id)
    group = next(g for g in result['groups'] if g['method_version_id'] == first['id'])
    selected = query(engine, actor, sample.formal_asset_id, group_id=group['id'])
    assert selected['statistics']['mean']['value'] == Decimal('10')
    assert selected['latest']['qualifier'] == 'ND'
    assert selected['latest_numeric']['value'] == Decimal('10')
    assert 'qualified_result' in selected['points'][1]['exclusion_reasons']
    assert 'different_method' in selected['points'][2]['exclusion_reasons']
    assert 'different_unit' in selected['points'][3]['exclusion_reasons']
    assert 'missing_unit' in selected['points'][4]['exclusion_reasons']
    LaboratoryConfiguration(engine).set_method_active(actor, first['id'], False)
    assert query(engine, actor, sample.formal_asset_id, group_id=group['id'])['statistics'] == selected['statistics']


def test_statistics_use_actual_elapsed_time_and_trailing_three_numeric_points(workbench_context):
    engine, _, actor, sample = workbench_context
    method = configured_method(engine, actor)
    for day, value in [(0, '2'), (1, '4'), (3, '8')]:
        add_point(engine, actor, sample.formal_asset_id, method['id'], day, value)
    result = query(engine, actor, sample.formal_asset_id)
    stats = result['statistics']
    assert stats['minimum']['value'] == Decimal('2')
    assert stats['maximum']['value'] == Decimal('8')
    assert abs(stats['mean']['value'] - Decimal('4.666666666667')) < Decimal('0.000000000001')
    assert stats['delta']['value'] == Decimal('4')
    assert stats['annualized_change']['value'] == Decimal('730.5')
    assert stats['regression_slope']['value'] == Decimal('730.5')
    assert stats['moving_mean']['value'] == stats['mean']['value']
    assert result['points'][0]['delta']['reason'] == 'need_two_numeric_points'
    assert result['points'][1]['moving_mean']['reason'] == 'need_three_numeric_points'


def test_insufficient_and_equal_time_statistics_are_explicit(workbench_context):
    engine, _, actor, sample = workbench_context
    method = configured_method(engine, actor)
    empty = query(engine, actor, sample.formal_asset_id)
    assert empty['statistics']['mean'] == {'value': None, 'reason': 'no_numeric_points'}
    for value in ('0', '10'):
        add_point(engine, actor, sample.formal_asset_id, method['id'], 0, value)
    result = query(engine, actor, sample.formal_asset_id)
    assert result['statistics']['mean']['value'] == Decimal('5')
    assert result['statistics']['annualized_change'] == {'value': None, 'reason': 'same_sampling_time'}
    assert result['statistics']['regression_slope'] == {'value': None, 'reason': 'need_distinct_sampling_times'}
    assert result['latest_time_tied'] is True


def test_chicago_date_filter_and_dst_elapsed_time(workbench_context):
    engine, _, actor, sample = workbench_context
    method = configured_method(engine, actor)
    # Chicago spring change: 23 real hours between local midnights.
    for instant, value in [('2026-03-08T06:00:00+00:00', '10'), ('2026-03-09T05:00:00+00:00', '33')]:
        add_point(engine, actor, sample.formal_asset_id, method['id'], 0, value, at=datetime.fromisoformat(instant))
    result = query(engine, actor, sample.formal_asset_id, start_date='2026-03-08', end_date='2026-03-08')
    assert len(result['points']) == 1
    both = query(engine, actor, sample.formal_asset_id)
    assert abs(both['statistics']['annualized_change']['value'] - Decimal('8766')) < Decimal('0.000001')


@pytest.mark.parametrize('fields', [dict(test_type='OTHER', analyte='H2'),
    dict(test_type='MOISTURE', analyte='H2'), dict(start_date='2026-09-02', end_date='2026-09-01'),
    dict(end_date='9999-12-31')])
def test_invalid_query_is_rejected(fields):
    with pytest.raises(ValidationError):
        TrendQuery(**(dict(test_type='MOISTURE', analyte='MOISTURE') | fields))


def test_http_requires_session_and_validates_query(workbench_context, database_url):
    from fastapi.testclient import TestClient
    from dga.main import create_app
    from dga.shared.config import Settings
    from tests.test_laboratory_workbench import CHANGED_PASSWORD
    engine, identity, actor, sample = workbench_context
    url = f'/api/condition-analysis/transformers/{sample.formal_asset_id}/trends'
    with TestClient(create_app(Settings(database_url=database_url, cookie_secure=False))) as client:
        assert client.get(url).status_code == 401
        session = identity.login('workbench-admin', CHANGED_PASSWORD)
        client.cookies.set('dga_session', session.token)
        response = client.get(url)
        assert response.status_code == 200
        assert response.headers['cache-control'] == 'no-store'
        assert response.json()['asset']['id'] == str(sample.formal_asset_id)
        assert client.get(url, params={'analyte': 'bad'}).status_code == 422
        assert client.get('/api/condition-analysis/transformers/not-a-uuid/trends').status_code == 422


def test_default_group_tracks_latest_observation_not_first_group_appearance(workbench_context):
    engine, _, actor, sample = workbench_context
    first = configured_method(engine, actor)
    second = configured_method(engine, actor, 'TREND-2')
    for day, method in [(0, first), (1, second), (2, first)]:
        add_point(engine, actor, sample.formal_asset_id, method['id'], day, '2')
    assert query(engine, actor, sample.formal_asset_id)['selected_group']['method_version_id'] == first['id']


def test_withdrawal_and_refinalization_refresh_selected_result(workbench_context):
    engine, _, actor, original = workbench_context
    method = configured_method(engine, actor)
    sample, record = add_point(engine, actor, original.formal_asset_id, method['id'], 0, '4')
    bench = make_workbench(engine, RecordingObjectStore())
    bench.withdraw_finalization(actor, sample.barcode_value, 'Correct reading')
    assert query(engine, actor, sample.formal_asset_id)['points'] == []
    bench.update_test(actor, sample.barcode_value, record.id, _moisture(method['id'], value='7'))
    bench.finalize(actor, sample.barcode_value)
    assert query(engine, actor, sample.formal_asset_id)['latest']['value'] == Decimal('7')


@pytest.mark.parametrize('qualifier,value', [('ND', None), ('LT', '5'), ('GT', '20')])
def test_qualified_results_are_visible_but_never_numeric(workbench_context, qualifier, value):
    engine, _, actor, sample = workbench_context
    method = configured_method(engine, actor)
    add_point(engine, actor, sample.formal_asset_id, method['id'], 0, value, qualifier)
    result = query(engine, actor, sample.formal_asset_id)
    assert result['latest']['qualifier'] == qualifier
    assert result['numeric_count'] == 0
    assert result['statistics']['mean']['value'] is None


def test_analysis_only_actor_and_forbidden_actor(workbench_context):
    from dga.shared.auth.public import IdentityError
    from dga.assets.public import AssetQueryError
    from uuid import uuid4
    engine, _, actor, sample = workbench_context
    reader = replace(actor, permissions=frozenset({'analysis.read'}))
    assert query(engine, reader, sample.formal_asset_id)['points'] == []
    with pytest.raises(IdentityError):
        query(engine, replace(actor, permissions=frozenset({'laboratory.read'})), sample.formal_asset_id)
    with pytest.raises(AssetQueryError, match='asset_not_found'):
        query(engine, reader, uuid4())


def test_duplicate_serial_and_replacement_never_join_physical_histories(database_url):
    from uuid import UUID
    from dga.assets.public import AssetLifecycle, AssetQueryError
    from tests.test_asset_import import import_context, workbook, new_rows
    engine, actor, imports, _ = import_context(database_url)
    try:
        rows = new_rows()
        rows[1]['serial_number'] = 'REUSED-SERIAL'
        rows.append(dict(record_key='spare', serial_number='REUSED-SERIAL', material_number='IMPORT-TX',
            product_line='PV', machine_type='TRANSFORMER', status='SPARE', location_kind='REPAIR_CENTER',
            effective_at='2025-01-01T09:00:00Z'))
        batch = imports.submit(actor, filename='trends.xlsx', content=workbook(rows))
        imports.validate_next()
        preview = imports.get(actor, batch['id'])
        result = imports.publish(actor, batch['id'], validation_revision=preview['validation_revision'], acknowledge_warnings=True)
        ids = {r['values']['record_key']: UUID(r['asset_id']) for r in result['rows']}
        method = configured_method(engine, actor)
        old_sample, old_record = add_point(engine, actor, ids['tx'], method['id'], 0, '3')
        new_sample, new_record = add_point(engine, actor, ids['spare'], method['id'], 1, '90')
        lifecycle = AssetLifecycle(engine)
        lifecycle.replace_transformer(actor, ids['tx'], replacement_id=ids['spare'],
            effective_at=datetime(2026, 8, 3, tzinfo=timezone.utc), reason='test replacement',
            expected_revision=0, replacement_revision=0)
        old = query(engine, actor, ids['tx'])
        new = query(engine, actor, ids['spare'])
        assert [p['test_id'] for p in old['points']] == [old_record.id]
        assert [p['test_id'] for p in new['points']] == [new_record.id]
        assert old['points'][0]['site_name'] == old_sample.site_name
        assert new['points'][0]['site_name'] == new_sample.site_name
        assert old['asset'].serial_number == new['asset'].serial_number
        assert old['asset'].id != new['asset'].id
        with pytest.raises(AssetQueryError, match='transformer_required'):
            query(engine, actor, ids['root'])
    finally:
        engine.dispose()


def test_dga_and_breakdown_voltage_use_their_selected_typed_fields(workbench_context):
    from tests.test_laboratory_workbench import _dga
    from dga.laboratory.public import TestSubmission as Submission, TestType as Kind, BreakdownVoltageResultInput
    engine, _, actor, sample = workbench_context
    config = LaboratoryConfiguration(engine)
    dga = config.create_method(actor, MethodVersionInput(test_type='DGA', display_name='Test DGA', version_label='T-DGA',
        fields=[dict(code=c, display_name=c, unit_code='TEST-GAS') for c in ('H2','CH4','C2H2','C2H4','C2H6','CO','CO2')]))
    voltage = config.create_method(actor, MethodVersionInput(test_type='BREAKDOWN_VOLTAGE', display_name='Test voltage', version_label='T-BDV',
        fields=[dict(code='BREAKDOWN_VOLTAGE', display_name='Voltage', unit_code='TEST-V')]))
    bench = make_workbench(engine, RecordingObjectStore())
    bench.add_test(actor, sample.barcode_value, _dga(dga['id']))
    bench.add_test(actor, sample.barcode_value, Submission(test_type=Kind.BREAKDOWN_VOLTAGE,
        method_version_id=voltage['id'], measured_at=datetime(2026,8,3,tzinfo=timezone.utc),
        instrument_name=None, notes=None, result=BreakdownVoltageResultInput(QualifiedMeasurement(ResultQualifier.EQ, Decimal('30')))))
    bench.finalize(actor, sample.barcode_value)
    trends = TransformerTrends(AssetDirectory(engine), LaboratoryTrendSource(engine))
    for kind, analyte, value in [('DGA','H2','10.125'), ('DGA','CO','120'), ('BREAKDOWN_VOLTAGE','BREAKDOWN_VOLTAGE','30')]:
        result = trends.query(actor, sample.formal_asset_id, TrendQuery(test_type=kind, analyte=analyte))
        assert result['statistics']['mean']['value'] == Decimal(value)
        assert len(result['points']) == 1


def test_placeholder_and_unknown_group_have_no_numeric_statistics(workbench_context):
    from uuid import UUID
    engine, _, actor, sample = workbench_context
    add_point(engine, actor, sample.formal_asset_id, UUID('66000000-0000-0000-0000-000000000002'), 0, '9')
    result = query(engine, actor, sample.formal_asset_id)
    assert result['groups'] == []
    assert 'placeholder_method' in result['points'][0]['exclusion_reasons']
    assert result['numeric_count'] == 0
    method = configured_method(engine, actor)
    add_point(engine, actor, sample.formal_asset_id, method['id'], 1, '3')
    selected = query(engine, actor, sample.formal_asset_id, group_id='unavailable')
    assert selected['selected_group'] is None
    assert selected['numeric_count'] == 0


@pytest.mark.parametrize('damage', ['null_numeric', 'unknown_qualifier', 'missing_fields'])
def test_corrupt_retained_source_is_explicitly_unavailable_not_empty(workbench_context, damage):
    import json
    from sqlalchemy import text
    from dga.laboratory.public import LaboratoryError
    engine, _, actor, original = workbench_context
    method = configured_method(engine, actor)
    sample, _ = add_point(engine, actor, original.formal_asset_id, method['id'], 0, '4')
    # Deliberate corruption at the retained-storage boundary, not a private-table assertion.
    with engine.begin() as c:
        snapshot = c.execute(text('SELECT report_snapshot FROM laboratory_reports WHERE oil_sample_id=:id'), {'id': sample.id}).scalar_one()
        result = snapshot['selected_results'][0]
        if damage == 'missing_fields':
            result['method']['fields'] = []
        elif damage == 'null_numeric':
            result['result']['result']['value'] = None
        else:
            result['result']['result']['qualifier'] = 'UNKNOWN'
        c.execute(text('UPDATE laboratory_reports SET report_snapshot=CAST(:snapshot AS jsonb) WHERE oil_sample_id=:id'),
                  {'snapshot': json.dumps(snapshot), 'id': sample.id})
    with pytest.raises(LaboratoryError, match='trend_snapshot_unavailable') as error:
        query(engine, actor, sample.formal_asset_id)
    assert error.value.status == 503
