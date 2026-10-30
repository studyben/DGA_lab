"""Real historical migrations, with attested producer data and public outcomes."""
from hashlib import sha256
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from dga.laboratory.public import LaboratoryReports, LaboratoryTrendSource
from dga.shared.auth.public import AuditTrail
from tests.finalization_legacy import load_case
from tests.test_laboratory_workbench import make_workbench, RecordingObjectStore


@pytest.mark.parametrize('database_url', ['0032_device_material_import'], indirect=True)
def test_old_producer_retains_selected_only_facts_and_original_pdf(database_url):
    engine = create_engine(database_url)
    files = RecordingObjectStore()
    case, actor = load_case(engine, 'old71_placeholder_ready', files)
    old_file = LaboratoryReports(engine, AuditTrail(), files).read_report_file(actor, case['barcode']).content
    before = LaboratoryTrendSource(engine).finalized_measurements(actor, UUID('44000000-0000-0000-0000-000000000001'))
    command.upgrade(Config('alembic.ini'), 'head')
    bench = make_workbench(engine, files)
    view = bench.get_current_finalization(actor, case['barcode'])
    assert view.state == 'AVAILABLE' and view.schema_version == 1
    assert view.inventory_complete is False and view.active_test_ids is None
    assert view.adopted_test_ids == tuple(UUID(i) for i in case['selected_test_ids'])
    assert view.token == UUID(case['token'])
    assert LaboratoryTrendSource(engine).finalized_measurements(actor, before[0].asset_id) == before
    after = LaboratoryReports(engine, AuditTrail(), files).read_report_file(actor, case['barcode']).content
    assert after == old_file and sha256(after).hexdigest() == case['pdf_sha256']
    engine.dispose()



import copy
import json
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from dga.laboratory.public import LaboratoryError, SampleRegistry, ReceiveSample, SampleIdentityStatus
from dga.assets.public import AssetDirectory
from tests.finalization_legacy import corpus


@pytest.mark.parametrize('database_url', ['0032_device_material_import'], indirect=True)
@pytest.mark.parametrize('name', ['parent_dga_ready', 'parent_repeated_quality_ready',
                                  'parent_mixed_qualified_ready', 'parent_refinalized_ready', 'parent_failed', 'parent_queued'])
def test_parent_v1_cases_preserve_current_results_and_delivery(database_url, name):
    engine = create_engine(database_url)
    files = RecordingObjectStore()
    case, actor = load_case(engine, name, files)
    reports = LaboratoryReports(engine, AuditTrail(), files)
    status = reports.get_report_by_barcode(actor, case['barcode'])
    points = LaboratoryTrendSource(engine).finalized_measurements(actor, UUID('44000000-0000-0000-0000-000000000001'))
    original = reports.read_report_file(actor, case['barcode']).content if status.state.value == 'READY' else None
    command.upgrade(Config('alembic.ini'), 'head')
    view = make_workbench(engine, files).get_current_finalization(actor, case['barcode'])
    assert view.state == 'AVAILABLE' and view.inventory_complete is False and view.active_test_ids is None
    assert view.adopted_test_ids == tuple(UUID(i) for i in case['selected_test_ids'])
    assert reports.get_report_by_barcode(actor, case['barcode']) == status
    assert LaboratoryTrendSource(engine).finalized_measurements(actor, points[0].asset_id) == points
    if original is not None:
        assert reports.read_report_file(actor, case['barcode']).content == original
    with pytest.raises(DBAPIError, match='Retained laboratory finalization facts require forward recovery'):
        command.downgrade(Config('alembic.ini'), '0032_device_material_import')
    assert make_workbench(engine, files).get_current_finalization(actor, case['barcode']) == view
    engine.dispose()


@pytest.mark.parametrize('database_url', ['0032_device_material_import'], indirect=True)
@pytest.mark.parametrize('damage', ['json_null', 'json_array', 'schema', 'token', 'asset', 'time',
                                     'missing_envelope', 'fields', 'null_eq', 'qualifier', 'configuration', 'duplicate'])
def test_corrupt_legacy_facts_stay_explicit_without_rewriting_ready_pdf(database_url, damage):
    engine = create_engine(database_url)
    files = RecordingObjectStore()
    case, actor = load_case(engine, 'old71_placeholder_ready', files)
    original = LaboratoryReports(engine, AuditTrail(), files).read_report_file(actor, case['barcode']).content
    payload = copy.deepcopy(case['report_snapshot'])
    selected = payload['selected_results'][0]
    if damage == 'json_null': payload = None
    elif damage == 'json_array': payload = []
    elif damage == 'schema': payload['schema_version'] = 999
    elif damage == 'token': payload['finalization']['token'] = str(uuid4())
    elif damage == 'asset': payload['sample']['asset_snapshot']['formal_asset_id'] = str(uuid4())
    elif damage == 'time': payload['sample']['sampled_at'] = '2025-01-01T00:00:00Z'
    elif damage == 'missing_envelope': del payload['finalization']
    elif damage == 'fields': selected['method']['fields'] = []
    elif damage == 'null_eq': selected['result']['result']['value'] = None
    elif damage == 'qualifier': selected['result']['result']['qualifier'] = 'UNKNOWN'
    elif damage == 'configuration': selected['method']['configuration'] = {'test_type': 'BAD'}
    elif damage == 'duplicate': payload['selected_results'].append(copy.deepcopy(selected))
    with engine.begin() as c:
        c.execute(text('UPDATE laboratory_reports SET report_snapshot=CAST(:payload AS jsonb) WHERE oil_sample_id=:sample'),
                  {'payload': json.dumps(payload), 'sample': UUID(case['sample_id'])})
    command.upgrade(Config('alembic.ini'), 'head')
    view = make_workbench(engine, files).get_current_finalization(actor, case['barcode'])
    assert view.state == 'UNAVAILABLE' and view.unavailable_reason == 'invalid_finalization_facts'
    assert view.active_test_ids is None and view.adopted_test_ids is None
    assert LaboratoryReports(engine, AuditTrail(), files).read_report_file(actor, case['barcode']).content == original
    engine.dispose()



@pytest.mark.parametrize('database_url', ['0032_device_material_import'], indirect=True)
@pytest.mark.parametrize('asset_id', [123, [], {}, True, 1.5, ''],
                         ids=['integer', 'array', 'object', 'boolean', 'float', 'empty_string'])
def test_malformed_legacy_asset_id_is_unavailable_and_preserves_ready_pdf(database_url, asset_id):
    engine = create_engine(database_url)
    files = RecordingObjectStore()
    case, actor = load_case(engine, 'old71_placeholder_ready', files)
    reports = LaboratoryReports(engine, AuditTrail(), files)
    original = reports.read_report_file(actor, case['barcode']).content
    assert sha256(original).hexdigest() == case['pdf_sha256']
    payload = copy.deepcopy(case['report_snapshot'])
    payload['sample']['asset_snapshot']['formal_asset_id'] = asset_id
    with engine.begin() as c:
        c.execute(text('UPDATE laboratory_reports SET report_snapshot=CAST(:payload AS jsonb) WHERE oil_sample_id=:sample'),
                  {'payload': json.dumps(payload), 'sample': UUID(case['sample_id'])})
    command.upgrade(Config('alembic.ini'), 'head')
    view = make_workbench(engine, files).get_current_finalization(actor, case['barcode'])
    assert view.state == 'UNAVAILABLE' and view.unavailable_reason == 'invalid_finalization_facts'
    assert view.token == UUID(case['token']) and view.schema_version == 1
    assert view.inventory_complete is None and view.active_test_ids is None and view.adopted_test_ids is None
    saved = reports.read_report_file(actor, case['barcode']).content
    assert saved == original and sha256(saved).hexdigest() == case['pdf_sha256']
    engine.dispose()


@pytest.mark.parametrize('database_url', ['0032_device_material_import'], indirect=True)
def test_empty_fact_migration_can_downgrade_and_upgrade(database_url):
    command.upgrade(Config('alembic.ini'), 'head')
    command.downgrade(Config('alembic.ini'), '0032_device_material_import')
    command.upgrade(Config('alembic.ini'), 'head')


@pytest.mark.parametrize('database_url', ['0006_laboratory_finalization'], indirect=True)
def test_real_tokenless_upgrade_does_not_block_other_current_public_consumers(database_url):
    from tests.test_transformer_trends import query, configured_method, add_point
    from tests.test_device_health import health
    from tests.test_alarm_center import center
    from tests.test_health_rules import rules, command as rule_input
    engine = create_engine(database_url)
    files = RecordingObjectStore()
    tokenless, actor = load_case(engine, 'old71_placeholder_ready', files, finalized=False)
    with engine.begin() as c:
        c.execute(text("""UPDATE oil_samples SET testing_status='FINALIZED',
            testing_finalized_by=:actor,testing_finalized_at=:at WHERE id=:sample"""),
            {'actor': actor.user_id, 'at': datetime(2026, 8, 6, 12, tzinfo=timezone.utc), 'sample': UUID(tokenless['sample_id'])})
    command.upgrade(Config('alembic.ini'), '0007_laboratory_reports')
    assert LaboratoryReports(engine, AuditTrail(), files).get_report_by_barcode(actor, tokenless['barcode']).unavailable_reason == 'refinalization_required'
    command.upgrade(Config('alembic.ini'), '0032_device_material_import')
    current, actor = load_case(engine, 'parent_repeated_quality_ready', files)
    command.upgrade(Config('alembic.ini'), 'head')
    bench = make_workbench(engine, files)
    view = bench.get_current_finalization(actor, tokenless['barcode'])
    assert view.state == 'UNAVAILABLE' and view.unavailable_reason == 'missing_finalization_token'
    assert bench.get_current_finalization(actor, current['barcode']).state == 'AVAILABLE'
    physical = UUID('44000000-0000-0000-0000-000000000001')
    points = LaboratoryTrendSource(engine).finalized_measurements(actor, physical)
    assert {p.sample_id for p in points} == {UUID(current['sample_id'])}
    assert query(engine, actor, physical)['points'][0]['sample_id'] == UUID(current['sample_id'])
    assert health(engine).query(actor, physical)['sources'][0]['measurement']['sample_id'] == current['sample_id']
    second = uuid4()
    with engine.begin() as c:
        c.execute(text("""INSERT INTO formal_assets
            (id,system_asset_number,asset_type,serial_number,lifecycle_status)
            VALUES (:id,'SYS-ISOLATED-SECOND','TRANSFORMER','ISOLATED-SECOND','IN_SERVICE')"""), {'id': second})
        c.execute(text("""INSERT INTO asset_installations(id,asset_id,parent_asset_id,site_id,valid_from)
            VALUES (:id,:asset,NULL,'22000000-0000-0000-0000-000000000001','2020-01-01T00:00:00Z')"""),
            {'id': uuid4(), 'asset': second})
    method = configured_method(engine, actor, version='ISOLATED-LEGACY-COEXIST')
    rule = rules(engine).create(actor, rule_input(method))
    rules(engine).activate(actor, rule['id'], 0, 'Isolated qualification fixture')
    sample, _ = add_point(engine, actor, second, method['id'], 10, '20')
    alarms = center(engine).query(actor)
    assert len(alarms['items']) == 1 and alarms['items'][0]['asset_id'] == str(second)
    assert alarms['items'][0]['trigger']['measurement']['sample_id'] == str(sample.id)
    assert bench.get_current_finalization(actor, tokenless['barcode']) == view
    engine.dispose()



@pytest.mark.parametrize('database_url', ['0032_device_material_import'], indirect=True)
def test_configured_frozen_units_must_agree_with_saved_method_configuration(database_url):
    engine = create_engine(database_url)
    files = RecordingObjectStore()
    case, actor = load_case(engine, 'parent_repeated_quality_ready', files)
    payload = copy.deepcopy(case['report_snapshot'])
    payload['selected_results'][0]['method']['fields'][0]['unit_code'] = 'DIFFERENT-TEST-UNIT'
    with engine.begin() as c:
        c.execute(text('UPDATE laboratory_reports SET report_snapshot=CAST(:value AS jsonb) WHERE oil_sample_id=:id'),
                  {'value': json.dumps(payload), 'id': UUID(case['sample_id'])})
    command.upgrade(Config('alembic.ini'), 'head')
    view = make_workbench(engine, files).get_current_finalization(actor, case['barcode'])
    assert view.state == 'UNAVAILABLE' and view.unavailable_reason == 'invalid_finalization_facts'
    engine.dispose()

