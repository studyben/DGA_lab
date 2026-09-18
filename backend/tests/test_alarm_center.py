from dga.condition_analysis.public import AlarmCenter, AlarmQuery
from dga.assets.public import AssetDirectory
from dga.laboratory.public import LaboratoryTrendSource
from tests.test_laboratory_workbench import workbench_context
from tests.test_health_rules import rules, command, NOW
from tests.test_transformer_trends import configured_method, add_point
import pytest
from dataclasses import replace
from dga.shared.auth.public import IdentityError
from dga.condition_analysis.public import HealthError
from tests.test_laboratory_workbench import make_workbench, RecordingObjectStore
from tests.test_asset_search import official_assets


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


def test_later_normal_resolves_without_losing_acknowledgement(workbench_context):
    engine, _, actor, sample = workbench_context
    method, _, _, alarm = opened(workbench_context)
    ack = center(engine).acknowledge(actor,alarm['id'],0,'Investigating')
    normal, _ = add_point(engine,actor,sample.formal_asset_id,method['id'],1,'2')
    detail = center(engine).detail(actor,alarm['id'])
    assert detail['state']=='RESOLVED'
    assert detail['acknowledgement']==ack['acknowledgement']
    assert detail['recovery']['sources'][0]['measurement']['barcode']==normal.barcode_value
    assert [e['action'] for e in detail['events']]==['OPENED','ACKNOWLEDGED','RESOLVED']


def test_later_abnormal_updates_baseline_without_duplicating_or_losing_ack(workbench_context):
    engine, _, actor, sample = workbench_context
    method, _, _, alarm = opened(workbench_context)
    ack = center(engine).acknowledge(actor,alarm['id'],0,'seen')
    later, _ = add_point(engine,actor,sample.formal_asset_id,method['id'],2,'30')
    detail = center(engine).detail(actor,alarm['id'])
    assert detail['latest_abnormal'][0]['measurement']['barcode']==later.barcode_value
    assert detail['acknowledgement']==ack['acknowledgement']
    assert [e['action'] for e in detail['events']]==['OPENED','ACKNOWLEDGED','ABNORMAL_UPDATED']
    add_point(engine,actor,sample.formal_asset_id,method['id'],1,'2')
    assert center(engine).query(actor)['unresolved_count']==1
    assert len(center(engine).detail(actor,alarm['id'])['events'])==3


def test_rule_reinterpretation_after_recovery_does_not_create_new_episode(workbench_context):
    engine, _, actor, sample = workbench_context
    method, rule, _, alarm = opened(workbench_context)
    add_point(engine,actor,sample.formal_asset_id,method['id'],1,'2')
    assert center(engine).detail(actor,alarm['id'])['state']=='RESOLVED'
    rules(engine).retire(actor,rule['id'],1,'test change')
    changed=rules(engine).create(actor,command(method,threshold='1'))
    rules(engine).activate(actor,changed['id'],0,'test only')
    result=center(engine).query(actor,AlarmQuery(scope='all'))
    assert result['total']==1
    assert result['unresolved_count']==0
    add_point(engine,actor,sample.formal_asset_id,method['id'],2,'3')
    assert center(engine).query(actor)['unresolved_count']==1


def test_withdrawing_recovery_reopens_original_with_ack_and_immutable_history(workbench_context):
    engine, _, actor, sample = workbench_context
    method, _, _, alarm = opened(workbench_context)
    ack = center(engine).acknowledge(actor,alarm['id'],0,'seen')
    normal, _ = add_point(engine,actor,sample.formal_asset_id,method['id'],1,'2')
    assert center(engine).detail(actor,alarm['id'])['state']=='RESOLVED'
    make_workbench(engine,RecordingObjectStore()).withdraw_finalization(actor,normal.barcode_value,'correction')
    detail=center(engine).detail(actor,alarm['id'])
    assert detail['state']=='ACKNOWLEDGED'
    assert detail['acknowledgement']==ack['acknowledgement']
    assert detail['recovery'] is None
    assert [e['action'] for e in detail['events']]==['OPENED','ACKNOWLEDGED','RESOLVED','RECOVERY_INVALIDATED']
    assert detail['events'][2]['data']['recovery']['sources'][0]['measurement']['barcode']==normal.barcode_value


def test_invalid_old_recovery_consolidates_later_episode_without_false_clear(workbench_context):
    engine, _, actor, sample = workbench_context
    method, _, _, original = opened(workbench_context)
    normal, _ = add_point(engine,actor,sample.formal_asset_id,method['id'],1,'2')
    assert center(engine).detail(actor,original['id'])['state']=='RESOLVED'
    later, _ = add_point(engine,actor,sample.formal_asset_id,method['id'],2,'30')
    second = next(a for a in center(engine).query(actor)['items'] if a['id']!=original['id'])
    make_workbench(engine,RecordingObjectStore()).withdraw_finalization(actor,normal.barcode_value,'correct normal evidence')
    detail = center(engine).detail(actor,original['id'])
    assert detail['state']=='UNACKNOWLEDGED'
    assert detail['latest_abnormal'][0]['measurement']['barcode']==later.barcode_value
    other = center(engine).detail(actor,second['id'])
    assert other['superseded_by']==original['id']
    assert other['state']!='RESOLVED'
    assert other['events'][-1]['action']=='CONSOLIDATED'
    assert center(engine).query(actor)['unresolved_count']==1


@pytest.mark.parametrize('case,reason', [('same_time','not_later_sample'),('qualified','qualified_result'),
    ('other_method','different_method_or_unit'),('retired','no_applicable_rule'),('withdrawn','no_finalized_results')])
def test_non_recovery_reasons_are_explicit(workbench_context,case,reason):
    engine, _, actor, sample = workbench_context
    method, rule, oil, alarm = opened(workbench_context)
    if case=='same_time':
        add_point(engine,actor,sample.formal_asset_id,method['id'],0,'2')
    elif case=='qualified':
        add_point(engine,actor,sample.formal_asset_id,method['id'],1,None,'ND')
    elif case=='other_method':
        other=configured_method(engine,actor,'OTHER')
        r=rules(engine).create(actor,command(other))
        rules(engine).activate(actor,r['id'],0,'test')
        add_point(engine,actor,sample.formal_asset_id,other['id'],1,'2')
    elif case=='retired':
        rules(engine).retire(actor,rule['id'],1,'test')
        add_point(engine,actor,sample.formal_asset_id,method['id'],1,'2')
    else:
        make_workbench(engine,RecordingObjectStore()).withdraw_finalization(actor,oil.barcode_value,'correct')
    detail=center(engine).detail(actor,alarm['id'])
    assert detail['state']=='UNACKNOWLEDGED'
    assert detail['observation']['reason']==reason
    assert detail['trigger_currently_finalized']==(case!='withdrawn')
    events=len(detail['events'])
    assert len(center(engine).detail(actor,alarm['id'])['events'])==events


def test_filter_counts_history_and_pagination_use_same_population(workbench_context):
    from dga.condition_analysis.public import AlarmQuery
    engine, _, actor, sample=workbench_context
    method, _, _, original=opened(workbench_context)
    add_point(engine,actor,sample.formal_asset_id,method['id'],1,'2')
    center(engine).query(actor)
    add_point(engine,actor,sample.formal_asset_id,method['id'],2,'20')
    result=center(engine).query(actor,AlarmQuery(scope='all',page_size=1))
    assert result['total']==2 and result['unresolved_count']==1 and len(result['items'])==1
    assert center(engine).query(actor,AlarmQuery(scope='history'))['items'][0]['id']==original['id']
    current=center(engine).query(actor,AlarmQuery(scope='current',site='Prairie',equipment='TX-CURRENT'))
    assert current['total']==current['unresolved_count']==1
    assert center(engine).query(actor,AlarmQuery(site='missing'))['total']==0
    assert center(engine).query(actor,AlarmQuery(asset_id=sample.formal_asset_id))['total']==1
    assert center(engine).query(actor,AlarmQuery(from_date='2026-09-13'))['total']==0
    assert center(engine).query(actor,AlarmQuery(to_date='2026-09-12'))['total']==1


def test_alarm_http_session_validation_and_csrf(workbench_context,database_url):
    from fastapi.testclient import TestClient
    from dga.main import create_app
    from dga.shared.config import Settings
    from tests.test_laboratory_workbench import CHANGED_PASSWORD
    engine, identity, actor, _=workbench_context
    _, _, _, alarm=opened(workbench_context)
    url='/api/condition-analysis/alarms'
    with TestClient(create_app(Settings(database_url=database_url,cookie_secure=False,auth_allowed_origins='http://testserver'))) as client:
        assert client.get(url).status_code==401
        session=identity.login('workbench-admin',CHANGED_PASSWORD)
        client.cookies.set('dga_session',session.token)
        result=client.get(url)
        assert result.status_code==200 and result.headers['cache-control']=='no-store'
        assert result.json()['total']==1
        assert client.get(url,params={'scope':'invalid'}).status_code==422
        assert client.get(url,params={'from_date':'2026-09-20','to_date':'2026-09-01'}).status_code==422
        assert client.get(url,params={'test_type':'BREAKDOWN_VOLTAGE'}).status_code==200
        detail=client.get(url+'/'+alarm['id']).json()
        payload={'expected_revision':detail['revision'],'note':'Reviewing'}
        assert client.post(url+'/'+alarm['id']+'/acknowledgement',json=payload).status_code==403
        response=client.post(url+'/'+alarm['id']+'/acknowledgement',json=payload,headers={'X-CSRF-Token':session.csrf_token,'Origin':'http://testserver'})
        assert response.status_code==200 and response.json()['state']=='ACKNOWLEDGED'


def test_consolidation_preserves_newer_incompatible_abnormal_baseline(workbench_context):
    engine, _, actor, sample=workbench_context
    first, _, _, original=opened(workbench_context)
    normal, _=add_point(engine,actor,sample.formal_asset_id,first['id'],1,'2')
    assert center(engine).detail(actor,original['id'])['state']=='RESOLVED'
    second=configured_method(engine,actor,'SECOND')
    rule=rules(engine).create(actor,command(second))
    rules(engine).activate(actor,rule['id'],0,'test')
    abnormal, _=add_point(engine,actor,sample.formal_asset_id,second['id'],2,'20')
    center(engine).query(actor)
    add_point(engine,actor,sample.formal_asset_id,first['id'],3,'2')
    assert center(engine).query(actor)['unresolved_count']==1
    make_workbench(engine,RecordingObjectStore()).withdraw_finalization(actor,normal.barcode_value,'correction')
    detail=center(engine).detail(actor,original['id'])
    assert detail['state']=='UNACKNOWLEDGED'
    assert detail['latest_abnormal'][0]['measurement']['barcode']==abnormal.barcode_value
    assert center(engine).query(actor)['unresolved_count']==1


def test_detachment_changes_current_counts_not_trigger_snapshot_or_alarm(database_url):
    from dga.assets.public import AssetLifecycle
    from datetime import datetime, timezone
    from tests.test_sample_reception import reception_context, TRANSFORMER_ID
    from types import SimpleNamespace
    engine, identity, actor=reception_context(database_url)
    sample=SimpleNamespace(formal_asset_id=TRANSFORMER_ID)
    _, _, _, alarm=opened((engine,identity,actor,sample))
    original=center(engine).detail(actor,alarm['id'])
    parent=original['current_asset']['ancestor_ids'][0]
    assert center(engine).query(actor,AlarmQuery(asset_id=parent))['total']==1
    AssetLifecycle(engine,clock=lambda:NOW).move(actor,sample.formal_asset_id,destination='REPAIR_CENTER',
        effective_at=datetime(2026,9,1,tzinfo=timezone.utc),reason='repair',expected_revision=0)
    detail=center(engine).detail(actor,alarm['id'])
    assert detail['state']=='UNACKNOWLEDGED'
    assert detail['current_asset']['location_kind']=='REPAIR_CENTER'
    assert detail['trigger']['measurement']['sampling_context']['site_name']=='Prairie Sun'
    assert center(engine).query(actor,AlarmQuery(asset_id=parent))['total']==0
    assert center(engine).query(actor,AlarmQuery(asset_id=sample.formal_asset_id))['total']==1
    engine.dispose()


def test_recovery_survives_rule_retirement_but_refinalization_changes_token(workbench_context):
    engine, _, actor, sample=workbench_context
    method, rule, _, alarm=opened(workbench_context)
    normal, _=add_point(engine,actor,sample.formal_asset_id,method['id'],1,'2')
    detail=center(engine).detail(actor,alarm['id'])
    old_token=detail['recovery']['sources'][0]['measurement']['finalization_token']
    rules(engine).retire(actor,rule['id'],1,'test retirement')
    assert center(engine).detail(actor,alarm['id'])['state']=='RESOLVED'
    bench=make_workbench(engine,RecordingObjectStore())
    bench.withdraw_finalization(actor,normal.barcode_value,'refinalize')
    bench.finalize(actor,normal.barcode_value)
    detail=center(engine).detail(actor,alarm['id'])
    assert detail['state']=='UNACKNOWLEDGED'
    assert detail['observation']['sources'][0]['measurement']['finalization_token']!=old_token
    assert 'RECOVERY_INVALIDATED' in [e['action'] for e in detail['events']]


def test_tied_latest_qualified_source_prevents_recovery(workbench_context):
    engine, _, actor, sample=workbench_context
    method, _, _, alarm=opened(workbench_context)
    add_point(engine,actor,sample.formal_asset_id,method['id'],1,'2')
    add_point(engine,actor,sample.formal_asset_id,method['id'],1,None,'ND')
    assert center(engine).detail(actor,alarm['id'])['state']=='UNACKNOWLEDGED'


def test_multiple_invalidated_recoveries_persist_latest_baseline_before_recovery(workbench_context):
    engine, _, actor, sample=workbench_context
    first, _, _, alarm=opened(workbench_context)
    normal1,_=add_point(engine,actor,sample.formal_asset_id,first['id'],1,'2')
    center(engine).query(actor)
    second=configured_method(engine,actor,'SECOND')
    rule=rules(engine).create(actor,command(second))
    rules(engine).activate(actor,rule['id'],0,'test')
    add_point(engine,actor,sample.formal_asset_id,second['id'],2,'20')
    center(engine).query(actor)
    normal2,_=add_point(engine,actor,sample.formal_asset_id,second['id'],3,'2')
    center(engine).query(actor)
    add_point(engine,actor,sample.formal_asset_id,second['id'],4,'2')
    bench=make_workbench(engine,RecordingObjectStore())
    for oil in (normal1,normal2):
        bench.withdraw_finalization(actor,oil.barcode_value,'correction')
    result=center(engine).detail(actor,alarm['id'])
    assert result['state']=='RESOLVED'
    again=center(engine).detail(actor,alarm['id'])
    assert again['latest_abnormal']==result['latest_abnormal']
    assert again['events'][-1]['data']['state']=='RESOLVED'
    assert again['events'][-1]['data']['latest_abnormal']==again['latest_abnormal']


def test_late_tied_nd_invalidates_recovery(workbench_context):
    engine, _, actor, sample=workbench_context
    method, _, _, alarm=opened(workbench_context)
    add_point(engine,actor,sample.formal_asset_id,method['id'],1,'2')
    assert center(engine).detail(actor,alarm['id'])['state']=='RESOLVED'
    add_point(engine,actor,sample.formal_asset_id,method['id'],1,None,'ND')
    detail=center(engine).detail(actor,alarm['id'])
    assert detail['state']=='UNACKNOWLEDGED'
    assert detail['observation']['reason']=='qualified_result'
    assert detail['events'][-1]['action']=='RECOVERY_INVALIDATED'


def test_duplicate_serials_remain_separate_physical_alarm_episodes(official_assets):
    from tests.test_asset_lifecycle import lifecycle_context
    from tests.test_asset_search import DUPLICATE_TRANSFORMER_A_ID, DUPLICATE_TRANSFORMER_B_ID
    _,actor,_=lifecycle_context(official_assets)
    method=configured_method(official_assets,actor,'DUPLICATE-SERIAL')
    rule=rules(official_assets).create(actor,command(method))
    rules(official_assets).activate(actor,rule['id'],0,'test')
    for asset_id in (DUPLICATE_TRANSFORMER_A_ID,DUPLICATE_TRANSFORMER_B_ID):
        add_point(official_assets,actor,asset_id,method['id'],0,'20')
    result=center(official_assets).query(actor,AlarmQuery(equipment='TX-DUP-9009'))
    assert result['unresolved_count']==2
    assert {a['asset_id'] for a in result['items']}=={str(DUPLICATE_TRANSFORMER_A_ID),str(DUPLICATE_TRANSFORMER_B_ID)}


def test_replacement_normal_does_not_resolve_removed_transformer_alarm(official_assets):
    from dga.assets.public import AssetLifecycle
    from tests.test_asset_lifecycle import lifecycle_context,at
    from tests.test_asset_search import CURRENT_TRANSFORMER_ID,DUPLICATE_TRANSFORMER_B_ID,WHOLE_UNIT_ID
    _,actor,_=lifecycle_context(official_assets)
    method=configured_method(official_assets,actor,'REPLACEMENT')
    rule=rules(official_assets).create(actor,command(method))
    rules(official_assets).activate(actor,rule['id'],0,'test')
    add_point(official_assets,actor,CURRENT_TRANSFORMER_ID,method['id'],0,'20')
    alarm=center(official_assets).query(actor)['items'][0]
    lifecycle=AssetLifecycle(official_assets,clock=lambda:NOW)
    lifecycle.move(actor,DUPLICATE_TRANSFORMER_B_ID,destination='REPAIR_CENTER',effective_at=at(2026,8,2),reason='prepare',expected_revision=0)
    lifecycle.change_status(actor,DUPLICATE_TRANSFORMER_B_ID,status='SPARE',effective_at=at(2026,8,3),reason='ready',expected_revision=1)
    lifecycle.replace_transformer(actor,CURRENT_TRANSFORMER_ID,replacement_id=DUPLICATE_TRANSFORMER_B_ID,effective_at=at(2026,8,4),reason='replace',expected_revision=0,replacement_revision=2)
    add_point(official_assets,actor,DUPLICATE_TRANSFORMER_B_ID,method['id'],5,'2')
    assert center(official_assets).query(actor,AlarmQuery(asset_id=WHOLE_UNIT_ID))['unresolved_count']==0
    detail=center(official_assets).detail(actor,alarm['id'])
    assert detail['state']=='UNACKNOWLEDGED'
    assert detail['current_asset']['location_kind']=='REPAIR_CENTER'
    assert detail['trigger']['measurement']['sampling_context']['site_name']=='Prairie Sun'
