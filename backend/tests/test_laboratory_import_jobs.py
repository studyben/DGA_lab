"""Durable staging validation through the laboratory public application boundary."""
from uuid import uuid4
import pytest
from dga.laboratory.public import LaboratoryImports, LaboratoryError
from tests.test_laboratory_imports import Files
from tests.test_sample_reception import reception_context


def test_queue_uses_only_confirmed_working_manifest_and_freezes_exact_operation(database_url):
    engine,_,actor=reception_context(database_url)
    imports=LaboratoryImports(engine,Files())
    batch=imports.create(actor,idempotency_key=str(uuid4()),input_format='XLSX',purpose='DAILY')['batch']
    missing_key=str(uuid4())
    with pytest.raises(LaboratoryError,match='active_files_incomplete'):
        imports.validate(actor,batch['id'],idempotency_key=missing_key,expected_revision=0)
    assert imports.operation(actor,missing_key)['state']=='REJECTED'
    imports.receive_file(actor,batch['id'],idempotency_key=str(uuid4()),role='WORKBOOK',filename='original.xlsx',
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',content=b'not parsed during queue')
    key=str(uuid4())
    queued=imports.validate(actor,batch['id'],idempotency_key=key,expected_revision=1)
    assert queued['job']['state']=='QUEUED' and queued['job']['input_revision']==1
    assert queued['operation']['result']['outcome']=='QUEUED'
    assert queued['batch']['business_state']=='STAGED'
    assert queued['batch']['validation_current'] is False
    again=imports.validate(actor,batch['id'],idempotency_key=key,expected_revision=1)
    assert again['operation']['result']==queued['operation']['result']
    assert again['job']['id']==queued['job']['id']
    with pytest.raises(LaboratoryError,match='validation_in_progress'):
        imports.validate(actor,batch['id'],idempotency_key=str(uuid4()),expected_revision=1)
    assert 'object_key' not in str(queued) and 'request_actor' not in str(queued)
    engine.dispose()



def test_expired_worker_lease_reclaims_and_fences_old_token_and_failed_can_requeue(database_url):
    from datetime import datetime,timedelta,timezone
    engine,_,actor=reception_context(database_url)
    now=[datetime(2026,10,30,tzinfo=timezone.utc)]
    imports=LaboratoryImports(engine,Files(),clock=lambda:now[0])
    batch=imports.create(actor,idempotency_key=str(uuid4()),input_format='XLSX',purpose='DAILY')['batch']
    imports.receive_file(actor,batch['id'],idempotency_key=str(uuid4()),role='WORKBOOK',filename='source.xlsx',
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',content=b'evidence')
    imports.validate(actor,batch['id'],idempotency_key=str(uuid4()),expected_revision=1)
    first=imports.claim_validation('worker-one',lease_seconds=2)
    assert first['input_revision']==1
    imports.heartbeat(first,phase='READING',done=0,total=8)
    assert imports.get(actor,batch['id'])['current_job']['state']=='RUNNING'
    assert imports.claim_validation('worker-two',lease_seconds=2) is None
    now[0]+=timedelta(seconds=3)
    second=imports.claim_validation('worker-two',lease_seconds=2)
    assert second['job_id']==first['job_id'] and second['claim_token']!=first['claim_token']
    with pytest.raises(LaboratoryError,match='stale_validation_claim'):
        imports.heartbeat(first,phase='READING',done=8,total=8)
    imports.fail_validation(second,'storage_unavailable')
    failed=imports.get(actor,batch['id'])
    assert failed['current_job']['error_code']=='storage_unavailable'
    assert failed['validation_state']=='FAILED' and not failed['validation_current']
    new=imports.validate(actor,batch['id'],idempotency_key=str(uuid4()),expected_revision=1)
    assert new['job']['id']!=first['job_id']
    engine.dispose()



@pytest.mark.parametrize('format',['XLSX','CSV_PAIR'])
@pytest.mark.parametrize('recover_a',[False,True])
def test_abandoned_private_a_receipt_never_blocks_or_replaces_b_validation(database_url,format,recover_a):
    from datetime import datetime,timedelta,timezone
    from threading import Event
    from concurrent.futures import ThreadPoolExecutor
    from dga.shared.auth.public import IdentityError
    from tests.identity_seed import seed_legacy_user
    from tests.test_sample_reception import INITIAL_PASSWORD,CHANGED_PASSWORD
    from tests.laboratory_import_fixtures import setup,receive,queued
    class Crash(BaseException): pass
    class BoundaryFiles(Files):
        armed=False
        block=False
        def __init__(self):
            super().__init__();self.entered=Event();self.release=Event();self.reads=[]
        def put(self,**values):
            super().put(**values)
            if self.armed:
                self.armed=False
                raise Crash('Original provider wrote before uploader stopped')
        def get(self,**values):
            data=super().get(**values)
            if self.block:
                self.block=False;self.entered.set()
                assert self.release.wait(15)
            self.reads.append(data)
            return data
    files=BoundaryFiles()
    now=[datetime(2026,11,1,tzinfo=timezone.utc)]
    engine,identity,b,imports,_,batch,sample,test,_=setup(database_url,format=format,files=files,clock=lambda:now[0])
    user_id=seed_legacy_user(database_url,'staging-a','A source uploader',INITIAL_PASSWORD,['lab_admin'])
    login=identity.login('staging-a',INITIAL_PASSWORD)
    a=identity.change_password(login.token,INITIAL_PASSWORD,CHANGED_PASSWORD).actor
    role='WORKBOOK' if format=='XLSX' else 'SAMPLES'
    suffix='.xlsx' if format=='XLSX' else '.csv'
    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' if format=='XLSX' else 'text/csv'
    key=str(uuid4());old_content=b'A independent original retained but not selected'
    values=dict(role=role,filename='a-original'+suffix,content_type=mime,content=old_content)
    files.armed=True
    with pytest.raises(Crash): imports.receive_file(a,batch['id'],idempotency_key=key,**values)
    pending=imports.list_files(b,batch['id'])['items'][0]
    assert pending['state']=='PENDING' and not pending['active']
    with pytest.raises(LaboratoryError,match='import_file_not_found'):
        imports.original(b,batch['id'],pending['id'])
    identity.change_roles(b,user_id,add=['field_engineer'],remove=['lab_admin'],expected_revision=0)
    with pytest.raises(LaboratoryError,match='import_operation_not_found'): imports.operation(b,key)
    own=receive(imports,b,batch,[sample|{'source_note':'B selected source evidence'}],[test])
    queued(imports,b,batch);assert imports.process_next('b-first')
    assert imports.samples(b,batch['id'])['items'][0]['raw_values']['source_note']=='B selected source evidence'
    assert imports.get(b,batch['id'])['validation_current']
    queued(imports,b,batch)
    files.block=True
    with ThreadPoolExecutor(max_workers=1) as pool:
        running=pool.submit(imports.process_next,'b-racing')
        try:
            assert files.entered.wait(10)
            assert imports.get(b,batch['id'])['current_job']['state']=='RUNNING'
            now[0]+=timedelta(seconds=61)
            with pytest.raises(IdentityError):
                imports.receive_file(a,batch['id'],idempotency_key=key,**values)
            if recover_a:
                identity.change_roles(b,user_id,add=['lab_admin'],remove=['field_engineer'],expected_revision=1)
                late=imports.receive_file(a,batch['id'],idempotency_key=key,**values)
                assert late['file']['state']=='RECEIVED' and not late['file']['active']
                assert imports.samples(b,batch['id'])['stale']
        finally: files.release.set()
        if recover_a:
            with pytest.raises(LaboratoryError,match='stale_validation_claim'): running.result()
        else: assert running.result()
    if recover_a:
        queued(imports,b,batch);assert imports.process_next('b-current-recheck')
    current=imports.get(b,batch['id'])
    assert current['validation_current'] and current['manifest_state']=='COMPLETE'
    assert {f['id'] for f in current['active_files']}=={r['file']['id'] for r in own}
    assert imports.samples(b,batch['id'])['items'][0]['raw_values']['source_note']=='B selected source evidence'
    assert old_content in files.objects.values() and old_content not in files.reads
    assert imports.list_files(b,batch['id'])['total']==len(own)+1
    with pytest.raises(LaboratoryError,match='import_operation_not_found'): imports.operation(b,key)
    if recover_a:
        assert imports.original(b,batch['id'],pending['id'])['content']==old_content
        assert imports.operation(a,key)['state']=='COMPLETED'
    else:
        assert next(f for f in imports.list_files(b,batch['id'])['items'] if f['id']==pending['id'])['state']=='PENDING'
    engine.dispose()



@pytest.mark.parametrize('fault',['audit','rollback','committed','serialization','deadlock'])
def test_completion_commit_and_audit_faults_keep_recoverable_job_without_partial_rows(database_url,fault):
    from contextlib import contextmanager
    from datetime import datetime,timedelta,timezone
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError
    from dga.shared.auth.public import AuditTrail
    from tests.laboratory_import_fixtures import setup,receive,queued
    now=[datetime(2026,11,1,tzinfo=timezone.utc)]
    engine,identity,actor,_,files,batch,sample,test,_=setup(database_url,clock=lambda:now[0])
    class Boundary:
        pending=None
        def __getattr__(self,name): return getattr(engine,name)
        @contextmanager
        def begin(self):
            outcome=None
            with engine.begin() as c:
                yield c
                outcome=self.pending;self.pending=None
                if outcome=='rollback': raise ConnectionError('Completion not committed')
            if outcome=='committed': raise ConnectionError('Completion COMMIT response lost')
    boundary=Boundary()
    class FaultAudit(AuditTrail):
        armed=True
        def append(self,c,actor,action,**values):
            if str(action)=='LAB_IMPORT_VALIDATION_COMPLETED' and self.armed:
                self.armed=False
                if fault=='audit': raise ConnectionError('Audit interrupted completion transaction')
                if fault in ('serialization','deadlock'):
                    c.execute(text("DO $$ BEGIN RAISE EXCEPTION USING ERRCODE='"+('40001' if fault=='serialization' else '40P01')+"'; END $$"))
                super().append(c,actor,action,**values)
                boundary.pending=fault
                return
            super().append(c,actor,action,**values)
    imports=LaboratoryImports(boundary,files,audit=FaultAudit(),clock=lambda:now[0])
    receive(imports,actor,batch,[sample],[test]);queue=queued(imports,actor,batch)
    with pytest.raises((ConnectionError,SQLAlchemyError)): imports.process_next('faulted-completion')
    current=imports.get(actor,batch['id'])
    if fault=='committed':
        assert current['validation_current']
        assert imports.samples(actor,batch['id'])['total']==1
        assert imports.process_next('no-duplicate') is False
    else:
        assert current['validation_state']=='RUNNING'
        assert imports.samples(actor,batch['id'])['total']==0
        now[0]+=timedelta(seconds=121)
        assert imports.process_next('lease-recovered')
    after=imports.get(actor,batch['id'])
    assert after['validation_current'] and after['current_job']['id']==queue['job']['id']
    assert imports.samples(actor,batch['id'])['total']==1
    row=imports.samples(actor,batch['id'])['items'][0]
    assert imports.sample(actor,batch['id'],row['id'])['tests']['total']==1
    assert len([e for e in identity.audit_events(actor) if e['action_code']=='LAB_IMPORT_VALIDATION_COMPLETED'])==1
    assert imports.list_files(actor,batch['id'])['total']==2 and len(files.objects)==2
    engine.dispose()



@pytest.mark.parametrize('moment',['before_claim','during_read'])
def test_requester_revocation_prevents_current_validation_and_other_writer_can_recheck(database_url,moment):
    from tests.identity_seed import seed_legacy_user
    from tests.test_sample_reception import INITIAL_PASSWORD,CHANGED_PASSWORD
    from tests.laboratory_import_fixtures import setup,receive,queued
    from dga.shared.auth.public import IdentityError
    class RevokeFiles(Files):
        revoke=None
        reads=0
        def get(self,**values):
            self.reads+=1
            if self.revoke:
                action=self.revoke;self.revoke=None;action()
            return super().get(**values)
    files=RevokeFiles()
    engine,identity,b,imports,_,batch,sample,test,_=setup(database_url,files=files)
    user_id=seed_legacy_user(database_url,'requester-a','Queued requester',INITIAL_PASSWORD,['analyst'])
    login=identity.login('requester-a',INITIAL_PASSWORD)
    a=identity.change_password(login.token,INITIAL_PASSWORD,CHANGED_PASSWORD).actor
    receive(imports,b,batch,[sample],[test])
    key=str(uuid4())
    imports.validate(a,batch['id'],idempotency_key=key,expected_revision=2)
    def revoke(): identity.change_roles(b,user_id,add=['field_engineer'],remove=['analyst'],expected_revision=0)
    if moment=='before_claim': revoke()
    else: files.revoke=revoke
    imports.process_next('current-authority')
    current=imports.get(b,batch['id'])
    assert current['validation_state']=='FAILED' and current['current_job']['error_code']=='requester_not_authorized'
    assert imports.samples(b,batch['id'])['total']==0
    if moment=='before_claim': assert files.reads==0
    with pytest.raises(IdentityError): imports.operation(a,key)
    with pytest.raises(LaboratoryError,match='import_operation_not_found'): imports.operation(b,key)
    queued(imports,b,batch);assert imports.process_next('authorized-current-writer')
    assert imports.get(b,batch['id'])['validation_current'] and imports.samples(b,batch['id'])['total']==1
    engine.dispose()


def test_parallel_same_intent_queue_and_claim_do_not_duplicate_job_or_result(database_url):
    from concurrent.futures import ThreadPoolExecutor
    from tests.laboratory_import_fixtures import setup,receive
    engine,identity,actor,imports,_,batch,sample,test,_=setup(database_url)
    receive(imports,actor,batch,[sample],[test])
    key=str(uuid4())
    def queue(_): return imports.validate(actor,batch['id'],idempotency_key=key,expected_revision=2)
    with ThreadPoolExecutor(4) as pool: results=list(pool.map(queue,range(4)))
    assert len({x['job']['id'] for x in results})==1
    assert len([e for e in identity.audit_events(actor) if e['action_code']=='LAB_IMPORT_VALIDATION_QUEUED'])==1
    with ThreadPoolExecutor(2) as pool:
        claims=list(pool.map(lambda n:imports.claim_validation('claim-'+str(n)),range(2)))
    active=[x for x in claims if x is not None]
    assert len(active)==1
    imports.fail_validation(active[0],'validation_unavailable')
    engine.dispose()



def test_hash_failure_marks_same_revision_old_preview_stale_then_explicit_recheck_recovers(database_url):
    from tests.laboratory_import_fixtures import setup,receive,queued
    engine,_,actor,imports,files,batch,sample,test,_=setup(database_url)
    originals=receive(imports,actor,batch,[sample],[test]);queued(imports,actor,batch);imports.process_next('hash-baseline')
    row=imports.samples(actor,batch['id'])['items'][0]
    file=originals[0]['file'];key=f"lab-imports/{batch['id']}/{file['id']}/source"
    original=files.objects[key];files.objects[key]=b'wrong bytes'
    queued(imports,actor,batch);assert imports.process_next('hash-failure')
    state=imports.get(actor,batch['id'])
    assert state['validation_state']=='FAILED' and not state['validation_current']
    old=imports.samples(actor,batch['id'])
    assert old['stale'] and old['items'][0]['id']==row['id']
    files.objects[key]=original
    queued(imports,actor,batch);imports.process_next('hash-recovered')
    assert imports.get(actor,batch['id'])['validation_current']
    assert imports.samples(actor,batch['id'])['items'][0]['id']==row['id']
    assert imports.original(actor,batch['id'],file['id'])['content']==original
    engine.dispose()
