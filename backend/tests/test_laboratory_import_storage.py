"""New laboratory receipt workflow over the existing opt-in isolated provider adapters."""
from hashlib import sha256
from uuid import uuid4
from dga.laboratory.public import LaboratoryImports
from tests.storage_fixtures import storage_case
from tests.test_sample_reception import reception_context


def test_staged_original_uses_configured_provider_and_reopens_exact_bytes(storage_case):
    case=storage_case
    engine,identity,actor=reception_context(case.settings.database_url.get_secret_value())
    imports=LaboratoryImports(engine,case.store)
    batch=imports.create(actor,idempotency_key=str(uuid4()),input_format='CSV_PAIR',purpose='HISTORICAL')['batch']
    key=str(uuid4())
    content=b'source_lab_key,external_sample_id\nLAB_A,00017\n'
    internal=None
    try:
        receipt=imports.receive_file(actor,batch['id'],idempotency_key=key,role='SAMPLES',
            filename='原始 samples.csv',content_type='text/csv',content=content)
        file=receipt['file']
        internal=f"lab-imports/{batch['id']}/{file['id']}/source"
        assert case.store.get(object_key=internal)==content
        assert file['sha256']==sha256(content).hexdigest()
        assert LaboratoryImports(engine,case.store).original(actor,batch['id'],file['id'])['content']==content
        again=imports.receive_file(actor,batch['id'],idempotency_key=key,role='SAMPLES',
            filename='原始 samples.csv',content_type='text/csv',content=content)
        assert again['operation']['result']==receipt['operation']['result']
        assert imports.get(actor,batch['id'])['revision']==1
        assert imports.list_files(actor,batch['id'])['total']==1
    finally:
        if internal:
            case.store.delete(object_key=internal)  # owned ephemeral provider fixture cleanup only
        engine.dispose()



import pytest
@pytest.mark.parametrize('format',['CSV_PAIR','XLSX'])
def test_configured_provider_runs_complete_staging_validation_job(storage_case,format):
    from tests.laboratory_import_fixtures import setup,receive,queued
    case=storage_case
    engine,_,actor,imports,_,batch,sample,test,_=setup(case.settings.database_url.get_secret_value(),format=format,files=case.store)
    originals=[]
    try:
        originals=receive(imports,actor,batch,[sample],[test,test|dict(external_test_id='RETEST-0002',result_value='0')])
        queued(imports,actor,batch)
        assert imports.process_next('configured-'+case.settings.object_store_provider+'-'+format)
        current=imports.get(actor,batch['id'])
        assert current['validation_current'] and current['current_job']['state']=='COMPLETE'
        row=imports.samples(actor,batch['id'])['items'][0]
        assert row['raw_values']['external_sample_id']=='00017'
        results=imports.sample(actor,batch['id'],row['id'])['tests']
        assert results['total']==2
        assert {x['raw_values']['external_test_id'] for x in results['items']}=={'T-0001','RETEST-0002'}
        assert {x['parsed_values']['measurements']['MOISTURE']['value'] for x in results['items']}=={'1.230000','0'}
        for original in originals:
            downloaded=imports.original(actor,batch['id'],original['file']['id'])
            assert sha256(downloaded['content']).hexdigest()==original['file']['sha256']
    finally:
        for item in originals:case.store.delete(object_key=f"lab-imports/{batch['id']}/{item['file']['id']}/source")
        engine.dispose()

