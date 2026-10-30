"""Transport security and recovery over real PostgreSQL; no mocked domain facade."""
from uuid import uuid4
from fastapi.testclient import TestClient
from dga.main import create_app
from dga.shared.config import Settings
from tests.test_laboratory_imports import Files
from tests.test_sample_reception import reception_context, CHANGED_PASSWORD

ROUTE = '/api/laboratory/imports'


def test_receipt_http_requires_current_session_csrf_and_private_integrity_checked_download(database_url):
    engine, identity, actor = reception_context(database_url)
    files = Files()
    settings = Settings(database_url=database_url, cookie_secure=False, auth_allowed_origins='http://testserver')
    with TestClient(create_app(settings, file_store=files)) as client:
        assert client.get(ROUTE+'/template').status_code == 401
        login = client.post('/api/auth/login', headers={'Origin':'http://testserver'},
            json=dict(username='reception-admin', password=CHANGED_PASSWORD)).json()
        headers = {'Origin':'http://testserver', 'X-CSRF-Token':login['csrf_token'],
                   'Idempotency-Key':str(uuid4())}
        body = dict(format_version=1,input_format='XLSX',purpose='HISTORICAL')
        assert client.post(ROUTE, json=body).status_code == 403
        assert client.post(ROUTE, json=body|{'unexpected':'secret'}, headers=headers).status_code == 422
        assert client.get(ROUTE+'/operations/'+headers['Idempotency-Key']).json()['state']=='REJECTED'
        headers['Idempotency-Key']=str(uuid4())
        result = client.post(ROUTE,json=body,headers=headers)
        assert result.status_code == 201, result.text
        batch = result.json()['batch']
        assert client.get(ROUTE+'/operations/'+headers['Idempotency-Key']).json()['state']=='COMPLETED'
        target = ROUTE+'/'+batch['id']+'/files'
        key = str(uuid4())
        upload_headers = headers|{'Idempotency-Key':key,
            'Content-Type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
        params = dict(role='WORKBOOK',filename='原始 Ω.xlsx')
        assert client.post(target,params=params,content=b'bytes',
            headers=upload_headers|{'Content-Type':'text/plain'}).status_code == 415
        received = client.post(target,params=params,content=b'original exact bytes',headers=upload_headers)
        assert received.status_code == 201, received.text
        assert received.json()['operation']['result']['outcome']=='FILE_RECEIVED'
        assert client.get(ROUTE+'/'+batch['id']).json()['manifest_state']=='COMPLETE'
        original_path = target+'/'+received.json()['file']['id']+'/original'
        original = client.get(original_path)
        assert original.content == b'original exact bytes'
        assert original.headers['cache-control']=='private, no-store'
        assert original.headers['x-content-type-options']=='nosniff'
        assert "filename*=UTF-8''%E5%8E%9F" in original.headers['content-disposition']
        reviewed=client.post(ROUTE+'/'+batch['id']+'/revisions',headers=headers|{'Idempotency-Key':str(uuid4())},
            json=dict(expected_revision=1,reason='Confirm metadata',metadata=dict(purpose='DAILY')))
        assert reviewed.status_code==200,reviewed.text
        assert reviewed.json()['batch']['revision']==2
        assert client.get(ROUTE+'/'+batch['id']+'/revisions').json()['total']==2
        files.objects[next(iter(files.objects))]=b'corrupted'
        failed = client.get(original_path)
        assert failed.status_code == 503 and failed.json()=={'code':'object_storage_unavailable'}
        assert 'object_key' not in result.text+received.text
        assert client.post(ROUTE+'/'+batch['id']+'/validate',headers=headers).status_code==404
    engine.dispose()



def test_strict_http_rejects_reserved_argument_names_and_large_bodies_without_leaking_payload(database_url):
    engine, _, actor = reception_context(database_url)
    files=Files()
    with TestClient(create_app(Settings(database_url=database_url,cookie_secure=False,
        auth_allowed_origins='http://testserver'),file_store=files)) as client:
        login=client.post('/api/auth/login',headers={'Origin':'http://testserver'},
            json=dict(username='reception-admin',password=CHANGED_PASSWORD)).json()
        headers={'Origin':'http://testserver','X-CSRF-Token':login['csrf_token'],'Idempotency-Key':str(uuid4())}
        body=dict(input_format='XLSX',purpose='DAILY')
        for reserved in ('idempotency_key','actor','writing','command'):
            rejected=client.post(ROUTE,json=body|{reserved:'secret'},headers=headers|{'Idempotency-Key':str(uuid4())})
            assert rejected.status_code==422 and 'secret' not in rejected.text
        assert client.get(ROUTE).json()['total']==0
        batch=client.post(ROUTE,json=body,headers=headers).json()['batch']
        target=ROUTE+'/'+batch['id']+'/files'
        too_large=client.post(target,params=dict(role='WORKBOOK',filename='large.xlsx'),
            content=b'x'*(10*1024*1024+1),headers=headers|{'Content-Type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})
        assert too_large.status_code==413
        assert client.get(target).json()['total']==0 and not files.objects
        oversized=client.post(ROUTE,content=b' '*(32*1024*1024+1),headers=headers|{'Content-Type':'application/json'})
        assert oversized.status_code==413 and oversized.json()['code']=='import_request_size'
    engine.dispose()





def test_http_model_rejection_is_durable_before_explicit_corrected_intent(database_url):
    """Only an authoritative durable rejection permits a new, explicit intent."""
    engine,_,actor=reception_context(database_url)
    files=Files()
    with TestClient(create_app(Settings(database_url=database_url,cookie_secure=False,
        auth_allowed_origins='http://testserver'),file_store=files)) as client:
        login=client.post('/api/auth/login',headers={'Origin':'http://testserver'},
            json=dict(username='reception-admin',password=CHANGED_PASSWORD)).json()
        headers={'Origin':'http://testserver','X-CSRF-Token':login['csrf_token']}
        key=str(uuid4())
        bad=dict(input_format='XLSX',purpose='DAILY',source_timezone='america/chicago')
        rejected=client.post(ROUTE,json=bad,headers=headers|{'Idempotency-Key':key})
        assert rejected.status_code==422
        assert rejected.json()['disposition']=='DURABLE_REJECTED'
        operation=client.get(ROUTE+'/operations/'+key).json()
        assert operation['state']=='REJECTED' and operation==rejected.json()['operation']
        assert client.post(ROUTE,json=bad,headers=headers|{'Idempotency-Key':key}).json()==rejected.json()
        corrected=bad|{'source_timezone':'America/Chicago'}
        assert client.post(ROUTE,json=corrected,headers=headers|{'Idempotency-Key':key}).status_code==409
        assert client.get(ROUTE).json()['total']==0
        good_key=str(uuid4())
        created=client.post(ROUTE,json=corrected,headers=headers|{'Idempotency-Key':good_key})
        assert created.status_code==201 and client.get(ROUTE).json()['total']==1
        # A rejected different payload/action cannot overwrite an existing completed key.
        conflict=client.post(ROUTE,json=bad,headers=headers|{'Idempotency-Key':good_key})
        assert conflict.status_code==409 and 'disposition' not in conflict.json()
        assert client.get(ROUTE+'/operations/'+good_key).json()['state']=='COMPLETED'
        batch_id=created.json()['batch']['id']
        revision_key=str(uuid4())
        bad_revision=client.post(ROUTE+'/'+batch_id+'/revisions',json=dict(expected_revision=True,reason='Invalid revision',metadata=dict(purpose='HISTORICAL')),
            headers=headers|{'Idempotency-Key':revision_key})
        assert bad_revision.status_code==422 and bad_revision.json()['disposition']=='DURABLE_REJECTED'
        assert client.get(ROUTE+'/operations/'+revision_key).json()['state']=='REJECTED'
        assert client.get(ROUTE+'/'+batch_id).json()['revision']==0
        # Malformed JSON has no authoritative model rejection proof.
        unproven_key=str(uuid4())
        unproven=client.post(ROUTE,content=b'{broken',
            headers=headers|{'Idempotency-Key':unproven_key,'Content-Type':'application/json'})
        assert unproven.status_code==422 and 'disposition' not in unproven.json()
        assert client.get(ROUTE+'/operations/'+unproven_key).status_code==404
        # Invalid NUL-bearing input is fingerprinted, never written into PostgreSQL JSONB.
        nul_key=str(uuid4())
        nul=client.post(ROUTE,json=bad|{'source_timezone':'Bad\u0000Zone'},
            headers=headers|{'Idempotency-Key':nul_key})
        assert nul.status_code==422 and nul.json()['disposition']=='DURABLE_REJECTED'
    engine.dispose()





import pytest


@pytest.mark.parametrize('database_url',['head'],indirect=True)
def test_http_never_emits_rejection_proof_for_unknown_commit(database_url):
    from contextlib import contextmanager
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from dga.laboratory.public import LaboratoryImports, LaboratoryError, import_http_router

    class FaultEngine:
        armed=False
        @contextmanager
        def begin(self):
            fail_commit=self.armed
            committed=getattr(self,'committed',False)
            self.armed=False
            with engine.begin() as c:
                yield c
                if fail_commit and not committed:
                    raise ConnectionError('Rollback instead of known COMMIT')
            if fail_commit and committed:
                raise ConnectionError('Durable COMMIT response lost')

    engine,_,actor=reception_context(database_url)
    boundary=FaultEngine()
    imports=LaboratoryImports(boundary,Files())
    # Public router with a known authenticated actor fixture; current identity checks
    # still execute in the real database. Main-app CSRF/session tests run separately.
    app=FastAPI()
    async def error_response(request,error):
        return JSONResponse(dict(code=error.code),status_code=error.status)
    app.add_exception_handler(LaboratoryError,error_response)
    app.include_router(import_http_router(imports,lambda:actor,lambda:actor))
    with TestClient(app) as client:
        for committed in (False,True):
            key=str(uuid4())
            boundary.armed,boundary.committed=True,committed
            bad=dict(input_format='XLSX',purpose='DAILY',source_timezone='america/chicago')
            unknown=client.post(ROUTE,json=bad,headers={'Idempotency-Key':key})
            assert unknown.status_code==503
            assert unknown.json()=={'code':'import_write_unknown'}
            query=client.get(ROUTE+'/operations/'+key)
            assert query.status_code==(200 if committed else 404)
            if committed:
                assert query.json()['state']=='REJECTED'
            confirmed=client.post(ROUTE,json=bad,headers={'Idempotency-Key':key})
            assert confirmed.status_code==422 and confirmed.json()['disposition']=='DURABLE_REJECTED'
    engine.dispose()



def test_http_validation_review_preview_and_current_authorization(database_url):
    from tests.laboratory_import_fixtures import setup,receive
    from tests.identity_seed import seed_legacy_user
    from tests.test_sample_reception import INITIAL_PASSWORD
    engine,identity,admin,imports,files,batch,sample,test,_=setup(database_url)
    receive(imports,admin,batch,[sample],[test])
    user=seed_legacy_user(database_url,'staging-http','Staging HTTP analyst',INITIAL_PASSWORD,['analyst'])
    original=identity.login('staging-http',INITIAL_PASSWORD)
    identity.change_password(original.token,INITIAL_PASSWORD,CHANGED_PASSWORD)
    with TestClient(create_app(Settings(database_url=database_url,cookie_secure=False,
            auth_allowed_origins='http://testserver'),file_store=files)) as client:
        session=client.post('/api/auth/login',headers={'Origin':'http://testserver'},
            json=dict(username='staging-http',password=CHANGED_PASSWORD)).json()
        headers={'Origin':'http://testserver','X-CSRF-Token':session['csrf_token'],'Idempotency-Key':str(uuid4())}
        url=ROUTE+'/'+str(batch['id'])
        assert client.post(url+'/validations',json=dict(expected_revision=2)).status_code==403
        queued=client.post(url+'/validations',json=dict(expected_revision=2),headers=headers)
        assert queued.status_code==202 and queued.json()['job']['state']=='QUEUED'
        assert imports.process_next('http-validation')
        preview=client.get(url+'/samples').json();row=preview['items'][0]
        assert preview['validation_current'] and preview['total']==1
        assert client.get(url+'/samples/'+row['id']).json()['tests']['total']==1
        revision=dict(expected_revision=2,reason='HTTP one-row review',changes=[dict(row_id=row['id'],values=dict(notes='HTTP revised note'))])
        changed=client.post(url+'/revisions',json=revision,headers=headers|{'Idempotency-Key':str(uuid4())})
        assert changed.status_code==200 and changed.json()['batch']['revision']==3
        assert client.get(url+'/samples').json()['stale']
        bad_key=str(uuid4())
        bad=client.post(url+'/revisions',json=revision|dict(changes=[dict(row_id=row['id'],values=dict(source_note=['object']))]),
            headers=headers|{'Idempotency-Key':bad_key})
        assert bad.status_code==422 and bad.json()['disposition']=='DURABLE_REJECTED'
        assert client.get(ROUTE+'/operations/'+bad_key).json()['state']=='REJECTED'
        identity.change_roles(admin,user,add=['field_engineer'],remove=['analyst'],expected_revision=0)
        for path in ('/samples','/samples/'+row['id'],'/unassigned-tests','/issues','/revisions'):
            assert client.get(url+path).status_code==403
        assert client.post(url+'/validations',json=dict(expected_revision=3),headers=headers|{'Idempotency-Key':str(uuid4())}).status_code==403
        assert client.post(url+'/revisions',json=revision,headers=headers|{'Idempotency-Key':str(uuid4())}).status_code==403
    engine.dispose()
