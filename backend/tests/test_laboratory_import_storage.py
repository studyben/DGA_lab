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

