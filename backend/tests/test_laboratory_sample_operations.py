from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from dga.assets.public import AssetDirectory
from dga.laboratory.public import (
    LaboratoryOperations, LaboratoryError, ReceiveSample, SampleIdentityStatus,
    SampleRegistry, UpdateSampleBasics,
)
from dga.shared.auth.public import AuditTrail, IdentityError
from tests.test_sample_reception import reception_context, TRANSFORMER_ID, WHOLE_UNIT_ID
from tests.test_laboratory_workbench import make_workbench, RecordingObjectStore, _dga, TestType


@pytest.fixture
def context(database_url):
    engine, identity, actor = reception_context(database_url)
    registry = SampleRegistry(engine, AssetDirectory(engine), AuditTrail())
    sample = registry.receive(actor, ReceiveSample(
        datetime(2025,6,1,tzinfo=timezone.utc), datetime(2025,6,2,tzinfo=timezone.utc),
        'Raw handwritten site', 'Raw serial', 'original note', 2, SampleIdentityStatus.IDENTITY_PENDING,
    ))
    ops = LaboratoryOperations(engine, registry, AssetDirectory(engine), AuditTrail())
    yield engine, identity, actor, sample, ops
    engine.dispose()


def test_confirm_pending_identity_preserves_tests_barcode_and_audits_raw_facts(context):
    engine, identity, actor, sample, ops = context
    bench = make_workbench(engine, RecordingObjectStore())
    method = next(m for m in bench.load(actor,sample.barcode_value).methods if m.test_type==TestType.DGA)
    test = bench.add_test(actor,sample.barcode_value,_dga(method.id))
    before = ops.sample_operations(actor,sample.barcode_value)
    result = ops.confirm_identity(actor,sample.barcode_value,TRANSFORMER_ID,expected_revision=before['operations_revision'],reason=' verified plate ')
    assert result['sample'].id == sample.id
    assert result['sample'].barcode_value == sample.barcode_value
    assert result['sample'].containers == sample.containers
    assert result['sample'].equipment_serial == 'TX-CURRENT-2002'
    assert result['sample'].identity_status == SampleIdentityStatus.ASSOCIATED
    assert result['sample'].asset_snapshot.equipment_path[0].serial_number == 'INV-UNIT-7788'
    assert bench.load(actor,sample.barcode_value).tests[0].id == test.id
    assert result['history'][0]['before_value']['equipment_serial'] == 'Raw serial'
    assert result['history'][0]['reason'] == 'verified plate'
    assert str(result['history'][0]['actor_id']) == str(actor.user_id)
    assert any(e['action_code']=='SAMPLE_ASSET_ASSOCIATED' for e in identity.audit_events(actor))
    assert ops.ledger(actor,serial='INV-UNIT-7788')['total']==1
    with pytest.raises(LaboratoryError):
        ops.confirm_identity(actor,sample.barcode_value,TRANSFORMER_ID,expected_revision=1,reason='rebind')


def test_confirmation_rejects_stale_basics_wrong_asset_and_duplicate_race(context):
    engine, _, actor, sample, ops = context
    before = ops.sample_operations(actor,sample.barcode_value)
    bench = make_workbench(engine, RecordingObjectStore())
    bench.update_sample(actor,sample.barcode_value,UpdateSampleBasics(
        sample.sampled_at,sample.received_at,'corrected site','corrected serial','note',
    ))
    with pytest.raises(LaboratoryError, match='stale_sample'):
        ops.confirm_identity(actor,sample.barcode_value,TRANSFORMER_ID,expected_revision=before['operations_revision'],reason='stale')
    with pytest.raises(LaboratoryError, match='sample_requires_transformer'):
        ops.confirm_identity(actor,sample.barcode_value,WHOLE_UNIT_ID,expected_revision=1,reason='wrong type')
    def confirm():
        try:
            ops.confirm_identity(actor,sample.barcode_value,TRANSFORMER_ID,expected_revision=1,reason='race')
            return 'success'
        except LaboratoryError:
            return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: confirm(),range(2))) == ['conflict','success']
    assert len(ops.sample_operations(actor,sample.barcode_value)['history'])==1


def test_container_state_reason_revision_and_cross_sample_guards(context):
    engine, identity, actor, sample, ops = context
    container=sample.containers[0].id
    before=ops.sample_operations(actor,sample.barcode_value)
    assert before['containers'][0]['status']=='RECEIVED'
    assert before['history']==[]
    with pytest.raises(LaboratoryError):
        ops.change_container(actor,sample.barcode_value,container,'IN_USE',expected_revision=0,reason='  ')
    with pytest.raises(LaboratoryError):
        ops.change_container(actor,sample.barcode_value,uuid4(),'IN_USE',expected_revision=0,reason='wrong container')
    with pytest.raises(LaboratoryError):
        ops.change_container(actor,sample.barcode_value,'not-a-uuid','IN_USE',expected_revision=0,reason='invalid container')
    result=ops.change_container(actor,sample.barcode_value,container,'IN_USE',expected_revision=0,reason='start')
    assert result['containers'][0]['status']=='IN_USE'
    with pytest.raises(LaboratoryError, match='stale_container'):
        ops.change_container(actor,sample.barcode_value,container,'RETAINED',expected_revision=0,reason='stale')
    for revision,target in enumerate(['RETAINED','IN_USE','EXHAUSTED','DISPOSED'],start=1):
        result=ops.change_container(actor,sample.barcode_value,container,target,expected_revision=revision,reason=target)
    assert result['containers'][0]['allowed_targets']==[]
    assert len(result['history'])==5
    assert result['sample']==sample
    with pytest.raises(LaboratoryError,match='invalid_container_transition'):
        ops.change_container(actor,sample.barcode_value,container,'IN_USE',expected_revision=5,reason='terminal')
    assert sum(e['action_code']=='SAMPLE_CONTAINER_CHANGED' for e in identity.audit_events(actor))==5


def test_operations_permissions_have_no_partial_mutations(context):
    _,_,actor,sample,ops=context
    denied=replace(actor,permissions=frozenset())
    readonly=replace(actor,permissions=frozenset({'laboratory.read'}))
    with pytest.raises(IdentityError): ops.sample_operations(denied,sample.barcode_value)
    with pytest.raises(IdentityError): ops.confirm_identity(readonly,sample.barcode_value,TRANSFORMER_ID,expected_revision=0,reason='denied')
    with pytest.raises(IdentityError): ops.change_container(readonly,sample.barcode_value,sample.containers[0].id,'IN_USE',expected_revision=0,reason='denied')
    assert ops.sample_operations(actor,sample.barcode_value)['history']==[]


@pytest.mark.parametrize('path,targets',[
    ([],['IN_USE','RETAINED','BROKEN','DISPOSED']),
    (['IN_USE'],['RETAINED','EXHAUSTED','BROKEN','DISPOSED']),
    (['RETAINED'],['IN_USE','EXHAUSTED','BROKEN','DISPOSED']),
    (['IN_USE','EXHAUSTED'],['DISPOSED']),
    (['BROKEN'],['DISPOSED']),
    (['DISPOSED'],[]),
])
def test_container_transition_contract(context,path,targets):
    _,_,actor,sample,ops=context
    container=sample.containers[0].id
    result=ops.sample_operations(actor,sample.barcode_value)
    for revision,target in enumerate(path):
        result=ops.change_container(actor,sample.barcode_value,container,target,expected_revision=revision,reason='transition')
    assert result['containers'][0]['allowed_targets']==targets
    for target in {'RECEIVED','IN_USE','RETAINED','EXHAUSTED','BROKEN','DISPOSED'}-set(targets):
        with pytest.raises(LaboratoryError,match='invalid_container_transition'):
            ops.change_container(actor,sample.barcode_value,container,target,expected_revision=len(path),reason='illegal')


def test_disposal_after_finalization_preserves_report_and_ledger_tracks_current_report(context):
    from dga.laboratory.public import LaboratoryReports
    from dga.laboratory.report_worker import ReportWorker
    from tests.test_laboratory_reports import MemoryFileStore
    engine,_,actor,sample,ops=context
    ops.confirm_identity(actor,sample.barcode_value,TRANSFORMER_ID,expected_revision=0,reason='identify')
    files=MemoryFileStore()
    bench=make_workbench(engine,files)
    assert ops.ledger(actor)['samples'][0]['state']=='RECEIVED'
    method=next(m for m in bench.load(actor,sample.barcode_value).methods if m.test_type==TestType.DGA)
    bench.add_test(actor,sample.barcode_value,_dga(method.id))
    assert ops.ledger(actor)['samples'][0]['state']=='DETECTING'
    bench.finalize(actor,sample.barcode_value)
    assert ops.ledger(actor)['samples'][0]['state']=='COMPLETED'
    reports=LaboratoryReports(engine,AuditTrail(),files)
    ReportWorker(reports,files).process_one('operations-test')
    assert ops.ledger(actor)['samples'][0]['state']=='REPORTED'
    before=reports.read_report_file(actor,sample.barcode_value)
    result=ops.change_container(actor,sample.barcode_value,sample.containers[0].id,'DISPOSED',expected_revision=0,reason='physical disposal')
    assert result['testing_status']=='FINALIZED'
    assert reports.read_report_file(actor,sample.barcode_value)==before
    with pytest.raises(LaboratoryError):
        ops.confirm_identity(actor,sample.barcode_value,TRANSFORMER_ID,expected_revision=1,reason='cannot rebind')
    bench.withdraw_finalization(actor,sample.barcode_value,'correct results')
    assert ops.ledger(actor)['samples'][0]['state']=='DETECTING'
    bench.finalize(actor,sample.barcode_value)
    assert ops.ledger(actor)['samples'][0]['state']=='COMPLETED'


def test_concurrent_container_commands_only_apply_once(context):
    _,_,actor,sample,ops=context
    def change():
        try:
            ops.change_container(actor,sample.barcode_value,sample.containers[0].id,'IN_USE',expected_revision=0,reason='concurrent')
            return 'success'
        except LaboratoryError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _:change(),range(2)))==['stale_container','success']
    assert len(ops.sample_operations(actor,sample.barcode_value)['history'])==1


def test_downgrade_refuses_to_erase_retained_operations(context):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy.exc import DBAPIError
    _,_,actor,sample,ops=context
    ops.change_container(actor,sample.barcode_value,sample.containers[0].id,'IN_USE',expected_revision=0,reason='retain history')
    before=ops.sample_operations(actor,sample.barcode_value)
    with pytest.raises(DBAPIError,match='explicit archival'):
        command.downgrade(Config('alembic.ini'),'0014_merge_laboratory')
    assert ops.sample_operations(actor,sample.barcode_value)==before


def test_confirmation_works_with_one_connection_without_nested_checkout(context,database_url):
    from sqlalchemy import create_engine
    _,_,actor,sample,_=context
    engine=create_engine(database_url,pool_size=1,max_overflow=0,pool_timeout=0.1)
    directory=AssetDirectory(engine)
    ops=LaboratoryOperations(engine,SampleRegistry(engine,directory,AuditTrail()),directory,AuditTrail())
    try:
        result=ops.confirm_identity(actor,sample.barcode_value,TRANSFORMER_ID,expected_revision=0,reason='bounded pool')
        assert result['sample'].identity_status==SampleIdentityStatus.ASSOCIATED
    finally:
        engine.dispose()


def test_sample_operation_http_csrf_strict_input_and_audited_success(context,database_url):
    from fastapi.testclient import TestClient
    from dga.main import create_app
    from dga.shared.config import Settings
    from tests.test_sample_reception import CHANGED_PASSWORD
    _,_,_,sample,_=context
    path='/api/laboratory/operations/'+sample.barcode_value
    with TestClient(create_app(Settings(database_url=database_url,cookie_secure=False,auth_allowed_origins='http://testserver'))) as client:
        assert client.get(path).status_code==401
        session=client.post('/api/auth/login',headers={'Origin':'http://testserver'},json={'username':'reception-admin','password':CHANGED_PASSWORD}).json()
        headers={'Origin':'http://testserver','X-CSRF-Token':session['csrf_token']}
        response=client.get(path)
        assert response.status_code==200 and response.headers['cache-control']=='no-store'
        body={'formal_asset_id':str(TRANSFORMER_ID),'expected_revision':0,'reason':'confirmed'}
        assert client.post(path+'/identity',json=body).status_code==403
        for bad in ({**body,'expected_revision':True},{**body,'extra':'ignored'},{**body,'reason':'   '}):
            assert client.post(path+'/identity',headers=headers,json=bad).status_code==422
        confirmed=client.post(path+'/identity',headers=headers,json=body)
        assert confirmed.status_code==200
        assert confirmed.json()['sample']['identity_status']=='ASSOCIATED'
        container=path+'/containers/'+str(sample.containers[0].id)
        change={'target':'IN_USE','expected_revision':0,'reason':'started'}
        assert client.post(container,headers=headers,json=change).status_code==200
        assert client.post(container,headers=headers,json=change).status_code==409
