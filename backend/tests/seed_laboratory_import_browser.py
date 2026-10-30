"""Additive two-writer fixture only for the dedicated isolated browser database."""
import json,os
from pathlib import Path
from uuid import uuid4
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
from dga.shared.config import Settings
from dga.shared.auth.public import IdentityService
from dga.shared.file_store_factory import create_file_store
from dga.laboratory.public import LaboratoryImports
from tests.identity_seed import seed_legacy_user


def prepare(settings,files,output,*,username='browser-admin',password='Browser changed passphrase 84!'):
    url=settings.database_url.get_secret_value()
    parsed=make_url(url)
    if (parsed.host,parsed.database,parsed.username)!=('db','dga_browser','dga_browser'):
        raise RuntimeError('Requires dedicated browser-test database')
    engine=create_engine(url)
    try:
        with engine.connect() as c:
            if tuple(c.execute(text('SELECT current_database(),current_user,current_schema()')).one())!=('dga_browser','dga_browser','public'):
                raise RuntimeError('Unexpected browser namespace')
        identity=IdentityService(engine);b=identity.login(username,password).actor
        a_name='pending-source-'+uuid4().hex[:10]
        initial='Browser pending fixture initial 52!';changed='Browser pending fixture changed 52!'
        seed_legacy_user(url,a_name,'Independent source receipt fixture',initial,['lab_admin'])
        login=identity.login(a_name,initial);a=identity.change_password(login.token,initial,changed).actor
        class StoppedUploader(BaseException):pass
        class InterruptedFiles:
            def put(self,**values):files.put(**values);raise StoppedUploader()
            def get(self,**values):return files.get(**values)
        imports=LaboratoryImports(engine,InterruptedFiles())
        batch=imports.create(b,idempotency_key=str(uuid4()),input_format='CSV_PAIR',purpose='HISTORICAL')['batch']
        key=str(uuid4())
        try:
            imports.receive_file(a,batch['id'],idempotency_key=key,role='SAMPLES',filename='a-retained.csv',
                content_type='text/csv',content=b'A independent pending original retained\n')
        except StoppedUploader:pass
        assert imports.list_files(b,batch['id'])['items'][0]['state']=='PENDING'
        output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(dict(batch_url='/lab/imports?batch='+str(batch['id']),
            b=dict(username=username,password=password),a_username=a_name,a_key=key)),encoding='utf-8')
    finally:engine.dispose()


if __name__=='__main__':
    settings=Settings()
    prepare(settings,create_file_store(settings),os.environ['LAB_IMPORT_TWO_WRITER_FIXTURE'])
