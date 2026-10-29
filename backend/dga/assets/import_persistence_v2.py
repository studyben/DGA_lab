"""Asset-owned row persistence inside the caller's publication transaction only."""
import json
from uuid import UUID, uuid4
from sqlalchemy import text


def dumped(value):
    return json.dumps(value, ensure_ascii=False, default=str)


def create_batch(c, actor, batch, rows, *, now, acknowledged_warning_ids):
    groups={sheet:[r for r in rows if r['sheet']==sheet] for sheet in ('Customers','Sites','Materials','Assets')}
    identities={}
    for sheet in ('Customers','Sites','Assets'):
        for row in groups[sheet]:
            target=UUID(str(row['target_id'])) if row['values']['decision']=='REFERENCE' else uuid4()
            identities[(sheet,row['values']['record_key'])]=target
            row['target_id']=str(target)
            if sheet=='Assets': row['system_asset_number']='AST-'+target.hex.upper()

    def customer_ref(value):
        return identities[('Customers',value[4:])] if value.startswith('NEW:') else UUID(value)

    def site_ref(reference):
        if not reference: return None
        return UUID(reference['site_id']) if reference['kind']=='EXISTING' else identities[('Sites',reference['record_key'])]

    for row in groups['Customers']:
        v=row['values']
        if v['decision']=='NEW':
            c.execute(text('INSERT INTO customers(id,customer_name) VALUES (:id,:name)'),dict(id=row['target_id'],name=v['customer_name']))
    for row in groups['Sites']:
        v=row['values']
        if v['decision']=='NEW':
            c.execute(text("""INSERT INTO sites(id,customer_id,site_name,location_text,commissioning_date,grid_status,operation_status,source_note)
                VALUES (:id,:customer,:name,:location,:date,:grid,:operation,:note)"""),
                dict(id=row['target_id'],customer=customer_ref(v['customer_ref']),name=v['site_name'],location=v.get('location_text') or None,
                     date=v.get('commissioning_date') or None,grid=v.get('grid_status') or None,operation=v.get('operation_status') or None,note=v.get('source_note') or None))
            for line in v['product_lines'].split(';'):
                c.execute(text('INSERT INTO site_product_lines(site_id,product_line,power_mw,energy_mwh) VALUES (:id,:line,:power,:energy)'),
                    dict(id=row['target_id'],line=line,power=v.get('pv_power_mw' if line=='PV' else 'ess_power_mw'),energy=v.get('ess_energy_mwh') if line=='ESS' else None))
    for row in groups['Materials']:
        v=row['values']; row['target_key']=v['material_number']
        if v['decision']=='NEW':
            c.execute(text('INSERT INTO asset_materials(material_number,model,asset_type) VALUES (:number,:model,:type)'),
                dict(number=v['material_number'],model=v['model'],type=v['asset_type']))
    for row in groups['Assets']:
        v=row['values']
        c.execute(text("""INSERT INTO formal_assets
            (id,system_asset_number,asset_type,serial_number,model,material_number,lifecycle_status,
             product_line,machine_type,power_mw,energy_mwh,equipment_name,tag_number,commissioning_date,battery_manufacturer)
            VALUES (:id,:number,:type,:serial,:model,:material,:status,:line,:machine,:power,:energy,:name,:tag,:date,:battery)"""),
            dict(id=row['target_id'],number=row['system_asset_number'],type=v['asset_type'],serial=v['serial_number'],model=v['model'],material=v['material_number'],
                 status=v['status'],line=v['product_line'],machine=v['machine_type'],power=v.get('power_mw'),energy=v.get('energy_mwh'),
                 name=v.get('equipment_name'),tag=v.get('tag_number'),date=v.get('commissioning_date') or None,battery=v.get('battery_manufacturer')))
    for row in groups['Assets']:
        v=row['values']; site=site_ref(row['references'].get('site'))
        parent=identities[('Assets',v['parent_record_key'])] if v.get('location_kind')=='PARENT' else None
        c.execute(text("""INSERT INTO asset_installations(id,asset_id,parent_asset_id,site_id,repair_center,valid_from)
            VALUES (:id,:asset,:parent,:site,:repair,:at)"""),
            dict(id=uuid4(),asset=row['target_id'],parent=parent,site=site if v['location_kind']=='SITE' else None,
                 repair=v['location_kind']=='REPAIR_CENTER',at=v['effective_at']))
        row['references']={'material':dict(kind='EXISTING',material_number=v['material_number'])}
        if site: row['references']['site']=dict(kind='EXISTING',site_id=str(site))
        if parent: row['references']['parent_asset_id']=str(parent)
        context=dict(row.get('resolved_context',{}),site_id=str(site) if site else None)
        if isinstance(context.get('customer_id'),str) and context['customer_id'].startswith('NEW:'):
            context['customer_id']=str(customer_ref(context['customer_id']))
        row['resolved_context']=context

    originals={(r['sheet'],r['row']):r['values'] for r in batch['source_rows']}
    kinds={'Customers':'CUSTOMER','Sites':'SITE','Materials':'MATERIAL','Assets':'ASSET'}
    for row in rows:
        v=row['values']; reviewed=dict(v)
        if row['sheet']=='Assets': reviewed['resolved_references']=row['references']
        params=dict(id=uuid4(),batch=batch['id'],kind=kinds[row['sheet']],target=row.get('target_id'),target_key=row.get('target_key'),sheet=row['sheet'],row=row['row'],note=v.get('source_note'),
                    original=dumped(originals[(row['sheet'],row['row'])]),reviewed=dumped(reviewed),actor=actor.user_id,at=now,revision=batch['validation_revision'],reason=v['reason'])
        columns='id,batch_id,kind,target_id,sheet,row_number,source_note,original_values,reviewed_values,actor_id,occurred_at,revision,reason'
        values=':id,:batch,:kind,:target,:sheet,:row,:note,CAST(:original AS jsonb),CAST(:reviewed AS jsonb),:actor,:at,:revision,:reason'
        # Preserve the old SITES writer contract for real0031 historical fixtures.
        if batch['mode']=='ASSETS':
            confirmations=[i['id'] for i in batch['issues'] if i['severity']=='WARNING' and i['id'] in acknowledged_warning_ids and (i.get('row',0)==0 or (i['sheet'],i['row'])==(row['sheet'],row['row']))]
            columns+=',target_key,confirmed_warning_ids'; values+=',:target_key,CAST(:confirmed AS jsonb)'
            params['confirmed']=dumped(confirmations)
        c.execute(text(f'INSERT INTO asset_import_sources({columns}) VALUES ({values})'),params)
    return rows


def targets(rows):
    kinds={'Customers':'CUSTOMER','Sites':'SITE','Materials':'MATERIAL','Assets':'ASSET'}
    return [dict(sheet=row['sheet'],row=row['row'],record_key=row['values']['record_key'],kind=kinds[row['sheet']],decision=row['values']['decision'],
                 **{k:row[k] for k in ('target_id','target_key','system_asset_number') if k in row}) for row in rows]
