from dga.condition_analysis.public import DeviceHealth
from dga.assets.public import AssetDirectory
from dga.laboratory.public import LaboratoryTrendSource
from tests.test_health_rules import rules, NOW, command
from tests.test_transformer_trends import configured_method, add_point
from tests.test_laboratory_workbench import workbench_context
import pytest


def health(engine):
    return DeviceHealth(engine, AssetDirectory(engine), LaboratoryTrendSource(engine), rules(engine), clock=lambda: NOW)


def test_no_finalized_results_is_unassessed(workbench_context):
    engine, _, actor, sample = workbench_context
    result = health(engine).query(actor, sample.formal_asset_id)
    assert result['status'] == 'UNASSESSED'
    assert result['incomplete'] is True
    assert result['sources'][0]['reason'] == 'no_finalized_results'


def test_latest_selected_result_and_immutable_rule_evidence(workbench_context):
    engine, _, actor, sample = workbench_context
    method = configured_method(engine, actor)
    service = rules(engine)
    draft = service.create(actor, command(method))
    service.activate(actor, draft['id'], 0, 'test')
    older, _ = add_point(engine, actor, sample.formal_asset_id, method['id'], 0, '1')
    latest, record = add_point(engine, actor, sample.formal_asset_id, method['id'], 1, '20')
    result = health(engine).query(actor, sample.formal_asset_id)
    assert result['status'] == 'WARNING' and result['incomplete'] is False
    assert len(result['sources']) == 1
    assert result['sources'][0]['measurement']['barcode'] == latest.barcode_value
    assert result['sources'][0]['rule']['id'] == str(draft['id'])
    service.retire(actor, draft['id'], 1, 'test')
    assert health(engine).query(actor, sample.formal_asset_id)['status'] == 'UNASSESSED'
    retained = health(engine).evaluation(actor, sample.formal_asset_id, result['evaluation_id'])
    assert retained['status'] == 'WARNING'


def test_current_parent_aggregates_child_and_detachment_removes_contribution(database_url):
    from tests.test_sample_reception import reception_context, WHOLE_UNIT_ID, TRANSFORMER_ID
    from dga.assets.public import AssetLifecycle
    from datetime import timedelta
    engine, _, actor = reception_context(database_url)
    try:
        method = configured_method(engine, actor)
        draft = rules(engine).create(actor, command(method))
        rules(engine).activate(actor, draft['id'], 0, 'test')
        add_point(engine, actor, TRANSFORMER_ID, method['id'], 1, '20')
        result = health(engine).query(actor, WHOLE_UNIT_ID)
        assert result['status'] == 'WARNING'
        assert result['own']['status'] == 'UNASSESSED'
        assert result['descendants']['status'] == 'WARNING'
        assert len(result['sources']) == 1
        AssetLifecycle(engine,clock=lambda:NOW).move(actor, TRANSFORMER_ID,
            destination='REPAIR_CENTER', effective_at=NOW-timedelta(hours=1), reason='test', expected_revision=0)
        assert health(engine).query(actor, WHOLE_UNIT_ID)['status']=='UNASSESSED'
        assert health(engine).query(actor, TRANSFORMER_ID)['status']=='WARNING'
    finally:
        engine.dispose()


def test_evidence_wrong_subject_and_no_permission_are_rejected(workbench_context):
    from uuid import uuid4
    from dataclasses import replace
    from dga.shared.auth.public import IdentityError
    from dga.condition_analysis.public import HealthError
    engine, _, actor,sample=workbench_context
    result=health(engine).query(actor,sample.formal_asset_id)
    with pytest.raises(HealthError,match='health_evaluation_not_found'):
        health(engine).evaluation(actor,uuid4(),result['evaluation_id'])
    with pytest.raises(IdentityError):
        health(engine).evaluation(replace(actor,permissions=frozenset()),sample.formal_asset_id,result['evaluation_id'])


def test_continuously_changing_results_fail_explicitly(workbench_context):
    from dataclasses import replace
    from decimal import Decimal
    from dga.condition_analysis.public import HealthError
    engine, _, actor,sample=workbench_context
    method=configured_method(engine,actor)
    add_point(engine,actor,sample.formal_asset_id,method['id'],0,'1')
    class UnstableSource:
        calls=0
        def finalized_measurements_for_assets(self,*args,**kwargs):
            self.calls+=1
            return tuple(replace(p,value=Decimal(self.calls)) for p in LaboratoryTrendSource(engine).finalized_measurements_for_assets(*args,**kwargs))
    source=UnstableSource()
    with pytest.raises(HealthError,match='health_inputs_changed'):
        DeviceHealth(engine,AssetDirectory(engine),source,rules(engine),clock=lambda:NOW).query(actor,sample.formal_asset_id)
    assert source.calls==6


def test_public_health_and_activation_work_with_single_connection_pool(workbench_context,database_url):
    from sqlalchemy import create_engine
    from dga.condition_analysis.public import HealthRules
    from dga.laboratory.public import LaboratoryConfiguration
    engine, _, actor,sample=workbench_context
    method=configured_method(engine,actor)
    limited=create_engine(database_url,pool_size=1,max_overflow=0,pool_timeout=.2)
    try:
        service=HealthRules(limited,LaboratoryConfiguration(limited),AssetDirectory(limited),clock=lambda:NOW)
        rule=service.create(actor,command(method))
        service.activate(actor,rule['id'],0,'test')
        assert DeviceHealth(limited,AssetDirectory(limited),LaboratoryTrendSource(limited),service,clock=lambda:NOW).query(actor,sample.formal_asset_id)['status']=='UNASSESSED'
    finally:
        limited.dispose()


@pytest.mark.parametrize('qualifier,value', [('ND',None),('LT','1'),('GT','100')])
def test_latest_qualified_result_never_falls_back(workbench_context, qualifier, value):
    engine, _, actor, sample = workbench_context
    method = configured_method(engine,actor)
    draft = rules(engine).create(actor,command(method))
    rules(engine).activate(actor,draft['id'],0,'test')
    add_point(engine,actor,sample.formal_asset_id,method['id'],0,'1')
    latest,_ = add_point(engine,actor,sample.formal_asset_id,method['id'],1,value,qualifier)
    result=health(engine).query(actor,sample.formal_asset_id)
    assert result['status']=='UNASSESSED'
    assert result['sources'][0]['reason']=='qualified_result'
    assert result['sources'][0]['measurement']['barcode']==latest.barcode_value


def test_latest_incompatible_method_and_ties_remain_visible(workbench_context):
    engine, _, actor, sample=workbench_context
    method=configured_method(engine,actor)
    other=configured_method(engine,actor,'other')
    draft=rules(engine).create(actor,command(method))
    rules(engine).activate(actor,draft['id'],0,'test')
    add_point(engine,actor,sample.formal_asset_id,method['id'],0,'1')
    add_point(engine,actor,sample.formal_asset_id,other['id'],1,'2')
    assert health(engine).query(actor,sample.formal_asset_id)['status']=='UNASSESSED'
    add_point(engine,actor,sample.formal_asset_id,method['id'],1,'20')
    result=health(engine).query(actor,sample.formal_asset_id)
    assert result['status']=='WARNING' and result['incomplete']
    assert len(result['sources'])==2
    assert all(s['latest_time_tied'] for s in result['sources'])


def test_changing_sources_are_retried_without_stale_evidence(workbench_context):
    engine, _, actor, sample=workbench_context
    method=configured_method(engine,actor)
    draft=rules(engine).create(actor,command(method))
    rules(engine).activate(actor,draft['id'],0,'test')
    add_point(engine,actor,sample.formal_asset_id,method['id'],0,'1')
    class ConcurrentSource:
        """Real public source, with one concurrent finalized write at its return boundary."""
        calls=0
        def finalized_measurements_for_assets(self,*args,**kwargs):
            points=LaboratoryTrendSource(engine).finalized_measurements_for_assets(*args,**kwargs)
            self.calls+=1
            if self.calls==1:
                add_point(engine,actor,sample.formal_asset_id,method['id'],1,'20')
            return points
    result=DeviceHealth(engine,AssetDirectory(engine),ConcurrentSource(),rules(engine),clock=lambda:NOW).query(actor,sample.formal_asset_id)
    assert result['status']=='WARNING'


def test_rule_retirement_during_source_read_is_retried(workbench_context):
    engine, _, actor, sample=workbench_context
    method=configured_method(engine,actor)
    service=rules(engine)
    draft=service.create(actor,command(method))
    service.activate(actor,draft['id'],0,'test')
    add_point(engine,actor,sample.formal_asset_id,method['id'],0,'20')
    class RetiringSource:
        calls=0
        def finalized_measurements_for_assets(self,*args,**kwargs):
            points=LaboratoryTrendSource(engine).finalized_measurements_for_assets(*args,**kwargs)
            self.calls+=1
            if self.calls==2:
                service.retire(actor,draft['id'],1,'test concurrent retirement')
            return points
    source=RetiringSource()
    result=DeviceHealth(engine,AssetDirectory(engine),source,service,clock=lambda:NOW).query(actor,sample.formal_asset_id)
    assert result['status']=='UNASSESSED'
    assert result['sources'][0]['reason']=='no_applicable_rule'
    assert source.calls==4


def test_health_http_auth_and_mutation_csrf(workbench_context,database_url):
    from fastapi.testclient import TestClient
    from dga.main import create_app
    from dga.shared.config import Settings
    from tests.test_laboratory_workbench import CHANGED_PASSWORD
    engine, identity, actor, sample=workbench_context
    with TestClient(create_app(Settings(database_url=database_url,auth_allowed_origins='http://localhost:8080'))) as client:
        path=f'/api/condition-analysis/health/{sample.formal_asset_id}'
        assert client.get(path).status_code==401
        session=identity.login('workbench-admin',CHANGED_PASSWORD)
        client.cookies.set('dga_session',session.token)
        assert client.get(path).json()['status']=='UNASSESSED'
        method=configured_method(engine,actor)
        payload=command(method).model_dump(mode='json')
        assert client.post('/api/condition-analysis/rules',json=payload).status_code==403
        result=client.post('/api/condition-analysis/rules',json=payload,headers={'X-CSRF-Token':session.csrf_token,'Origin':'http://localhost:8080'})
        assert result.status_code==201
        assert result.headers['cache-control']=='no-store'
        precise=payload|{'threshold':'999999999999.123456'}
        saved=client.post('/api/condition-analysis/rules',json=precise,headers={'X-CSRF-Token':session.csrf_token,'Origin':'http://localhost:8080'})
        assert saved.json()['threshold']=='999999999999.123456'


def test_priority_and_current_effective_period_not_sampling_period(workbench_context):
    from datetime import timedelta
    engine, _, actor, sample=workbench_context
    method=configured_method(engine,actor)
    service=rules(engine)
    for overrides in [dict(priority=1,severity='CRITICAL'),dict(priority=2,threshold='100',effective_from=NOW)]:
        rule=service.create(actor,command(method,**overrides))
        service.activate(actor,rule['id'],0,'test')
    add_point(engine,actor,sample.formal_asset_id,method['id'],0,'20')
    assert health(engine).query(actor,sample.formal_asset_id)['status']=='NORMAL'
    before=DeviceHealth(engine,AssetDirectory(engine),LaboratoryTrendSource(engine),service,clock=lambda:NOW-timedelta(seconds=1))
    assert before.query(actor,sample.formal_asset_id)['status']=='CRITICAL'


def test_withdrawal_refreshes_and_evidence_deduplicates(workbench_context):
    from tests.test_laboratory_workbench import make_workbench, RecordingObjectStore
    engine, _, actor, original=workbench_context
    method=configured_method(engine,actor)
    draft=rules(engine).create(actor,command(method))
    rules(engine).activate(actor,draft['id'],0,'test')
    sample,_=add_point(engine,actor,original.formal_asset_id,method['id'],0,'20')
    first=health(engine).query(actor,original.formal_asset_id)
    assert health(engine).query(actor,original.formal_asset_id)['evaluation_id']==first['evaluation_id']
    make_workbench(engine,RecordingObjectStore()).withdraw_finalization(actor,sample.barcode_value,'test')
    current=health(engine).query(actor,original.formal_asset_id)
    assert current['status']=='UNASSESSED' and current['evaluation_id']!=first['evaluation_id']
    assert health(engine).evaluation(actor,original.formal_asset_id,first['evaluation_id'])['status']=='WARNING'


def test_overlapping_historical_installation_fails_instead_of_wrong_parent_health(database_url):
    from tests.test_sample_reception import reception_context, WHOLE_UNIT_ID, TRANSFORMER_ID, SITE_ID
    from sqlalchemy import text
    from uuid import uuid4
    from dga.assets.public import AssetQueryError
    engine, _, actor=reception_context(database_url)
    try:
        # Simulate legacy overlapping finite history at the owner storage boundary.
        with engine.begin() as c:
            c.execute(text('''INSERT INTO asset_installations(id,asset_id,site_id,valid_from,valid_to)
                VALUES(:id,:asset,:site,'2026-01-01Z','2027-01-01Z')'''),dict(id=uuid4(),asset=TRANSFORMER_ID,site=SITE_ID))
        with pytest.raises(AssetQueryError,match='ambiguous_asset_hierarchy'):
            health(engine).query(actor,WHOLE_UNIT_ID)
    finally:
        engine.dispose()
