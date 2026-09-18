from dga.condition_analysis.public import AlarmCenter
from dga.assets.public import AssetDirectory
from dga.laboratory.public import LaboratoryTrendSource
from tests.test_laboratory_workbench import workbench_context
from tests.test_health_rules import rules, command, NOW
from tests.test_transformer_trends import configured_method, add_point
import pytest
from dataclasses import replace
from dga.shared.auth.public import IdentityError
from dga.condition_analysis.public import HealthError


def opened(context):
    engine, _, actor, sample = context
    method = configured_method(engine, actor)
    rule = rules(engine).create(actor, command(method))
    rules(engine).activate(actor, rule['id'], 0, 'isolated test')
    oil, _ = add_point(engine, actor, sample.formal_asset_id, method['id'], 0, '20')
    return method, rule, oil, center(engine).query(actor)['items'][0]


def center(engine):
    return AlarmCenter(engine, AssetDirectory(engine), LaboratoryTrendSource(engine), clock=lambda: NOW)


def test_current_warning_opens_one_traceable_alarm(workbench_context):
    engine, _, actor, sample = workbench_context
    method = configured_method(engine, actor)
    rule = rules(engine).create(actor, command(method))
    rules(engine).activate(actor, rule['id'], 0, 'isolated test')
    oil, _ = add_point(engine, actor, sample.formal_asset_id, method['id'], 0, '20')
    result = center(engine).query(actor)
    assert result['total'] == result['unresolved_count'] == 1
    alarm = result['items'][0]
    assert alarm['state'] == 'UNACKNOWLEDGED'
    assert alarm['trigger']['measurement']['barcode'] == oil.barcode_value
    assert alarm['trigger']['rule']['id'] == str(rule['id'])
    again = center(engine).query(actor)['items'][0]
    assert again['id'] == alarm['id']
    assert len(center(engine).detail(actor, alarm['id'])['events']) == 1


def test_acknowledgement_is_authorized_audited_and_does_not_clear_warning(workbench_context):
    engine, _, actor, _ = workbench_context
    _, _, _, alarm = opened(workbench_context)
    with pytest.raises(IdentityError):
        center(engine).acknowledge(replace(actor, permissions=frozenset({'analysis.read'})), alarm['id'], 0, 'seen')
    acknowledged = center(engine).acknowledge(actor, alarm['id'], 0, 'Investigating')
    assert acknowledged['state']=='ACKNOWLEDGED'
    assert acknowledged['severity']=='WARNING'
    assert acknowledged['acknowledgement']['actor_id']==str(actor.user_id)
    assert acknowledged['acknowledgement']['note']=='Investigating'
    assert center(engine).acknowledge(actor, alarm['id'], 0, 'retry')['acknowledgement']==acknowledged['acknowledgement']
    assert [e['action'] for e in center(engine).detail(actor,alarm['id'])['events']]==['OPENED','ACKNOWLEDGED']


def test_concurrent_refresh_and_acknowledge_deduplicate(workbench_context):
    from concurrent.futures import ThreadPoolExecutor
    engine, _, actor, _ = workbench_context
    _, _, _, alarm = opened(workbench_context)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: center(engine).query(actor),range(2)))
    assert all(r['total']==1 and r['items'][0]['id']==alarm['id'] for r in results)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: center(engine).acknowledge(actor,alarm['id'],0,'seen'),range(2)))
    assert results[0]['acknowledgement']==results[1]['acknowledgement']
    assert len(center(engine).detail(actor,alarm['id'])['events'])==2


def test_detail_during_acknowledgement_returns_coherent_timeline(workbench_context):
    from concurrent.futures import ThreadPoolExecutor
    engine, _, actor, _ = workbench_context
    _, _, _, alarm = opened(workbench_context)
    def read():
        details=[center(engine).detail(actor,alarm['id']) for _ in range(12)]
        for result in details:
            assert result['events'][-1]['data']['revision']==result['revision']
            assert result['events'][-1]['data']['state']==result['state']
    with ThreadPoolExecutor(max_workers=2) as pool:
        reader=pool.submit(read)
        writer=pool.submit(center(engine).acknowledge,actor,alarm['id'],0,'seen')
        reader.result()
        writer.result()


def test_invalid_acknowledgement_preserves_alarm(workbench_context):
    engine, _, actor, _ = workbench_context
    _, _, _, alarm = opened(workbench_context)
    with pytest.raises(HealthError,match='alarm_note_required'):
        center(engine).acknowledge(actor,alarm['id'],0,'   ')
    with pytest.raises(HealthError,match='alarm_revision_conflict'):
        center(engine).acknowledge(actor,alarm['id'],9,'seen')
    assert center(engine).detail(actor,alarm['id'])['state']=='UNACKNOWLEDGED'


def test_single_pool_no_rule_and_sampling_snapshot(workbench_context,database_url):
    from sqlalchemy import create_engine
    engine, _, actor, sample = workbench_context
    limited=create_engine(database_url,pool_size=1,max_overflow=0,pool_timeout=.2)
    try:
        assert center(limited).query(actor)['total']==0
        _, _, _, alarm=opened(workbench_context)
        observed=center(limited).detail(actor,alarm['id'])
        assert observed['trigger']['measurement']['finalization_token']
        assert observed['trigger']['measurement']['sampling_context']['site_name']=='Prairie Sun'
        assert observed['current_asset']['site_name']=='Prairie Sun'
    finally:
        limited.dispose()
