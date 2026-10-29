"""Real historical upgrades and guarded downgrade on disposable PostgreSQL schemas."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from dga.assets.public import AssetImports, AssetDirectory
from dga.laboratory.public import SampleRegistry
from dga.shared.auth.public import AuditTrail, IdentityService
from tests.identity_seed import seed_legacy_user
from tests.test_asset_import import workbook, new_rows
from tests.test_device_material_import import publication_document, ready, publish, context
from tests.test_sample_reception import CUSTOMER_ID, SITE_ID, WHOLE_UNIT_ID, TRANSFORMER_ID, INITIAL_PASSWORD, CHANGED_PASSWORD
from tests.test_site_import import Files, document as site_document, new_site


@pytest.mark.parametrize('database_url', ['0013_asset_import', '0030_merge_export_identity', '0031_site_import'], indirect=True)
def test_real_historical_upgrade_preserves_v1_states_asset_sample_and_source(database_url):
    engine = create_engine(database_url)
    user = seed_legacy_user(database_url, 'upgrade-admin', 'Upgrade administrator', INITIAL_PASSWORD, ['system_admin'])
    files = Files(); content = workbook(new_rows()); batches = {}
    snapshot = dict(formal_asset_id=str(TRANSFORMER_ID), customer_id=str(CUSTOMER_ID), customer_name='Historical customer',
        site_id=str(SITE_ID), site_name='Prairie Sun', site_location='Historical location', equipment_path=[
            dict(id=str(WHOLE_UNIT_ID), system_asset_number='OLD-UNIT', asset_type='WHOLE_UNIT', serial_number='OLD-UNIT-SERIAL', model='SG4400UD', material_number='IMPORT-UNIT', lifecycle_status='IN_SERVICE'),
            dict(id=str(TRANSFORMER_ID), system_asset_number='OLD-TX', asset_type='TRANSFORMER', serial_number='OLD-TX-SERIAL', model='TX-4400', material_number='IMPORT-TX', lifecycle_status='IN_SERVICE')])
    source_rows = [dict(row=i+2, values=v) for i,v in enumerate(new_rows())]
    old_rows = [dict(row=2, values=dict(new_rows()[0], serial_number='OLD-UNIT-SERIAL'), asset_id=str(WHOLE_UNIT_ID), system_asset_number='OLD-UNIT')]
    sample_id, container_id = uuid4(), uuid4()
    with engine.begin() as c:
        c.execute(text("INSERT INTO customers(id,customer_name) VALUES (:id,'Historical customer')"),dict(id=CUSTOMER_ID))
        c.execute(text("INSERT INTO sites(id,customer_id,site_name,location_text) VALUES (:id,:customer,'Prairie Sun','Historical location')"),dict(id=SITE_ID, customer=CUSTOMER_ID))
        c.execute(text("INSERT INTO site_product_lines(site_id,product_line) VALUES (:id,'PV')"),dict(id=SITE_ID))
        c.execute(text("INSERT INTO asset_materials VALUES ('IMPORT-UNIT','SG4400UD','WHOLE_UNIT'),('IMPORT-TX','TX-4400','TRANSFORMER')"))
        for asset, number, kind, serial, model, material, machine in [
            (WHOLE_UNIT_ID,'OLD-UNIT','WHOLE_UNIT','OLD-UNIT-SERIAL','SG4400UD','IMPORT-UNIT','INVERTER_UNIT'),
            (TRANSFORMER_ID,'OLD-TX','TRANSFORMER','OLD-TX-SERIAL','TX-4400','IMPORT-TX','TRANSFORMER')]:
            c.execute(text("""INSERT INTO formal_assets(id,system_asset_number,asset_type,serial_number,model,material_number,lifecycle_status,product_line,machine_type)
                VALUES (:id,:number,:kind,:serial,:model,:material,'IN_SERVICE','PV',:machine)"""),dict(id=asset,number=number,kind=kind,serial=serial,model=model,material=material,machine=machine))
        for asset, parent, site in [(WHOLE_UNIT_ID,None,SITE_ID),(TRANSFORMER_ID,WHOLE_UNIT_ID,None)]:
            c.execute(text("INSERT INTO asset_installations(id,asset_id,parent_asset_id,site_id,valid_from) VALUES (:id,:asset,:parent,:site,'2020-01-01T00:00:00Z')"),dict(id=uuid4(),asset=asset,parent=parent,site=site))
        c.execute(text("""INSERT INTO oil_samples(id,sample_number,barcode_value,identity_status,sampled_at,received_at,site_name,equipment_serial,formal_asset_id,asset_snapshot,created_by,created_at)
            VALUES (:id,'HISTORICAL-001','HISTORICAL-001','ASSOCIATED','2025-01-01T00:00:00Z','2025-01-02T00:00:00Z','Prairie Sun','OLD-TX-SERIAL',:asset,CAST(:snapshot AS jsonb),:actor,now())"""),dict(id=sample_id,asset=TRANSFORMER_ID,snapshot=json.dumps(snapshot),actor=user))
        c.execute(text("INSERT INTO sample_containers(id,oil_sample_id,container_number,ordinal) VALUES (:id,:sample,'HISTORICAL-001-C01',1)"),dict(id=container_id,sample=sample_id))
        for state in ['STAGED','VALIDATED','PUBLISHED']:
            batch = uuid4(); batches[state] = batch; key = f'historical/{batch}.xlsx'
            files.put(object_key=key,content=content,content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            c.execute(text("""INSERT INTO asset_import_batches(id,filename,sha256,object_key,byte_size,state,source_rows,rows,summary,validation_revision,created_by,created_at,published_by,published_at)
                VALUES (:id,'historical-v1.xlsx',:sha,:key,:size,:state,CAST(:source AS jsonb),CAST(:rows AS jsonb),CAST(:summary AS jsonb),:revision,:actor,now(),:publisher,:published_at)"""),dict(id=batch,sha=sha256(content).hexdigest(),key=key,size=len(content),state=state,source=json.dumps(source_rows),rows=json.dumps(old_rows if state=='PUBLISHED' else []),summary=json.dumps(dict(total_rows=2,valid_rows=2,warning_rows=0,error_rows=0,warning_count=0,error_count=0)),revision=0 if state=='STAGED' else 1,actor=user,publisher=user if state=='PUBLISHED' else None,published_at=datetime(2025,1,1,tzinfo=timezone.utc) if state=='PUBLISHED' else None))
    command.upgrade(Config('alembic.ini'),'head')
    identity = IdentityService(engine); first = identity.login('upgrade-admin',INITIAL_PASSWORD)
    actor = identity.change_password(first.token,INITIAL_PASSWORD,CHANGED_PASSWORD).actor
    imports = AssetImports(engine,files,clock=lambda: datetime(2026,1,1,tzinfo=timezone.utc))
    directory = AssetDirectory(engine); registry = SampleRegistry(engine,directory,AuditTrail())
    sample = registry.find_by_barcode(actor,'HISTORICAL-001'); asset = directory.equipment_detail(actor,TRANSFORMER_ID)
    assert sample.id == sample_id and sample.containers[0].id == container_id
    assert sample.asset_snapshot.customer_name == 'Historical customer'
    assert sample.asset_snapshot.equipment_path[-1].id == TRANSFORMER_ID
    old = imports.get(actor,batches['PUBLISHED'])
    assert old['rows'] == old_rows and 'format_version' not in old
    assert imports.publish(actor,batches['PUBLISHED'],validation_revision=1) == old
    for state,batch in batches.items():
        assert imports.get(actor,batch)['state'] == state
        assert imports.source_file(actor,batch)['content'] == content
    assert imports.validate_next()
    for state in ['STAGED','VALIDATED']:
        batch = batches[state]
        for _ in range(3):
            preview = imports.get(actor,batch)
            if preview['state']=='PUBLISHED': break
            imports.publish(actor,batch,validation_revision=preview['validation_revision'],acknowledge_warnings=True)
        assert imports.get(actor,batch)['state']=='PUBLISHED'
        assert imports.source_file(actor,batch)['content']==content
    result = publish(imports,actor,ready(imports,actor,publication_document()[0]))
    assert result['state']=='PUBLISHED' and len(result['operation_result']['targets'])==10
    assert registry.find_by_barcode(actor,'HISTORICAL-001')==sample
    assert directory.equipment_detail(actor,TRANSFORMER_ID)==asset
    engine.dispose()


@pytest.mark.parametrize('database_url', ['0031_site_import'], indirect=True)
def test_0031_sources_survive_0032_upgrade_and_safe_downgrade(database_url):
    engine, actor, imports, files = context(database_url)
    content = site_document([new_site(site_name='Retained historical SITES')])
    batch = imports.submit(actor,filename='sites.xlsx',content=content,format_version=2,mode='SITES',idempotency_key=str(uuid4()))
    imports.validate_next(); preview=imports.get(actor,batch['id'])
    revised=imports.revise(actor,batch['id'],expected_revision=preview['validation_revision'],changes=[dict(sheet='Sites',row=2,values=dict(source_note='Reviewed before0032'))],reason='Historical review',idempotency_key=str(uuid4()))
    result = publish(imports,actor,revised)
    pending=imports.submit(actor,filename='pending-sites.xlsx',content=site_document([new_site(site_name='Pending before0032')]),format_version=2,mode='SITES',idempotency_key=str(uuid4()))
    target = next(r['target_id'] for r in result['rows'] if r['sheet']=='Sites')
    command.upgrade(Config('alembic.ini'),'head')
    sources = AssetDirectory(engine).import_sources(actor,'SITE',target)
    assert sources['total']==1 and sources['sources'][0]['source_note'] == 'Reviewed before0032'
    assert sources['sources'][0]['original_values']['source_note']==new_site()['source_note']
    assert imports.revision_history(actor,batch['id'])['changes'][0]['reason']=='Historical review'
    assert imports.validate_next()
    assert publish(imports,actor,imports.get(actor,pending['id']))['state']=='PUBLISHED'
    command.downgrade(Config('alembic.ini'),'0031_site_import')
    assert imports.get(actor,batch['id'])['state']=='PUBLISHED'
    assert imports.source_file(actor,batch['id'])['content']==content
    with pytest.raises(Exception,match='Retained site imports require forward recovery'):
        command.downgrade(Config('alembic.ini'),'0030_merge_export_identity')
    command.upgrade(Config('alembic.ini'),'head')
    assert AssetDirectory(engine).import_sources(actor,'SITE',target)==sources
    engine.dispose()


@pytest.mark.parametrize('database_url', ['0031_site_import'], indirect=True)
@pytest.mark.parametrize('state',['empty','STAGED','VALIDATED','FAILED','PUBLISHED'])
def test_0032_downgrade_preserves_all_retained_asset_states(database_url,state):
    command.upgrade(Config('alembic.ini'),'head')
    if state=='empty':
        command.downgrade(Config('alembic.ini'),'0031_site_import')
        command.upgrade(Config('alembic.ini'),'head')
        return
    engine,actor,imports,files=context(database_url)
    content=publication_document()[0] if state!='FAILED' else b'invalid xlsx retained'
    batch=imports.submit(actor,filename='retained.xlsx',content=content,format_version=2,mode='ASSETS',idempotency_key=str(uuid4()))
    if state=='VALIDATED':
        imports.validate_next(); batch=imports.get(actor,batch['id'])
    if state=='PUBLISHED':
        imports.validate_next(); batch=publish(imports,actor,imports.get(actor,batch['id']))
    before=imports.get(actor,batch['id'])
    assert before['state']==state
    with pytest.raises(Exception,match='Retained equipment/material imports require forward recovery'):
        command.downgrade(Config('alembic.ini'),'0031_site_import')
    assert imports.get(actor,batch['id'])==before
    assert imports.source_file(actor,batch['id'])['content']==content
    if state=='PUBLISHED':
        target=next(t for t in batch['operation_result']['targets'] if t['kind']=='MATERIAL')
        assert AssetDirectory(engine).material_detail(actor,target['target_key'])['model']=='S2 approved unit'
    engine.dispose()
