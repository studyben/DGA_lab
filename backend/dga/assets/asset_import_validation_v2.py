"""Asset-owned v2 master references and new equipment preview; no business writes."""
from collections import Counter
from typing import Literal, TypedDict
from uuid import UUID
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from sqlalchemy import text
from .lifecycle import location_at
from .public import AssetQueryError
from .v2_import_workbook import COLUMNS
from .import_validation import TEXT_LIMITS, KINDS
from .site_import_validation import digest, validate as validate_sites, catalog


class ExistingSiteReference(TypedDict):
    kind: Literal['EXISTING']
    site_id: str


class BatchReference(TypedDict):
    kind: Literal['BATCH']
    record_key: str


class ExistingMaterialReference(TypedDict):
    kind: Literal['EXISTING']
    material_number: str


def serial_key(value: str) -> str:
    """One Unicode caseless policy for catalog lookup and within-batch candidates."""
    return value.casefold()


def counts(rows, issues):
    errors={(i['sheet'],i['row']) for i in issues if i['severity']=='ERROR'}
    warnings={(i['sheet'],i['row']) for i in issues if i['severity']=='WARNING'}-errors
    by_kind={}
    for sheet in COLUMNS:
        entries=[r for r in rows if r['sheet']==sheet]
        by_kind[sheet]=dict(total_rows=len(entries),new_rows=sum(r['values'].get('decision')=='NEW' for r in entries),reference_rows=sum(r['values'].get('decision')=='REFERENCE' for r in entries),error_rows=sum(key[0]==sheet for key in errors),warning_rows=sum(key[0]==sheet for key in warnings))
    return dict(by_kind=by_kind,total_rows=len(rows),valid_rows=len(rows)-len(errors|warnings),error_rows=len(errors),
                warning_rows=len(warnings),error_count=sum(i['severity']=='ERROR' for i in issues),
                warning_count=sum(i['severity']=='WARNING' for i in issues))


def validate(c, source, now):
    snapshot=catalog(c)
    customers,sites,lines=snapshot
    masters=[r for r in source if r['sheet'] in ('Customers','Sites')]
    rows,issues,_,fingerprint=validate_sites(c,masters,snapshot=snapshot)
    material_catalog=[dict(r) for r in c.execute(text('SELECT * FROM asset_materials ORDER BY material_number')).mappings()]
    materials={r['material_number']:r for r in material_catalog}
    sm={str(r['id']):r for r in sites}
    for entry in source:
        if entry['sheet'] not in ('Materials','Assets'): continue
        v={k:(value.strip() if isinstance(value,str) and k!='source_note' else value) for k,value in entry['values'].items()}
        rows.append(dict(sheet=entry['sheet'],row=entry['row'],values=v,candidates=[],references={}))
    index={(r['sheet'],r['values'].get('record_key')):r for r in rows}
    source_values={(r['sheet'],r['row']):r['values'] for r in source}
    for item in issues:
        supplied=source_values[(item['sheet'],item['row'])]
        item['original_value']=supplied.get(item['field']); item['suggestion']=item['message']
        item['id']=digest([item['code'],item['sheet'],item['row'],item['field'],supplied,fingerprint])[:24]

    def problem(row,field,message,code='invalid_value',severity='ERROR',facts=None):
        original=source_values[(row['sheet'],row['row'])].get(field)
        issue_id=digest([code,row['sheet'],row['row'],field,row['values'].get('record_key'),original,facts])[:24]
        if any(item['id']==issue_id for item in issues): return
        issues.append(dict(id=issue_id,
            code=code,severity=severity,sheet=row['sheet'],row=row['row'],field=field,message=message,
            original_value=original,suggestion=message))

    keys=Counter((r['sheet'],r['values'].get('record_key')) for r in rows)
    numbers=Counter(r['values'].get('material_number') for r in rows if r['sheet']=='Materials')
    for row in rows:
        if row['sheet'] not in ('Materials','Assets'): continue
        v=row['values']
        limits=dict(TEXT_LIMITS,reason=1000,source_note=2000,model=120,asset_type=30,decision=9,material_ref=129,site_id=124,site_name=200,effective_at=80)
        required={'record_key','decision','reason'} | ({'material_number','model','asset_type'} if row['sheet']=='Materials' else {'serial_number','material_ref','product_line','machine_type','status','location_kind','effective_at'})
        for field in v.keys()-set(COLUMNS[row['sheet']]): problem(row,field,'不支持此写入字段。','invalid_column')
        for field,limit in limits.items():
            if field not in COLUMNS[row['sheet']]: continue
            value=v.get(field)
            if value in (None,''):
                if field in required: problem(row,field,'必填文本，不能留空。')
            elif not isinstance(value,str) or len(value)>limit or any(ord(ch)<32 and ch not in '\r\n\t' for ch in value):
                problem(row,field,f'请填写有效文本，最多{limit}字符。')
        if keys[(row['sheet'],v.get('record_key'))]>1: problem(row,'record_key','同表记录键必须不同。')
        if row['sheet']=='Materials':
            number=v.get('material_number'); existing=materials.get(number)
            if numbers[number]>1: problem(row,'material_number','同批物料号重复，请保留一条明确记录。','duplicate_material_number')
            if v.get('decision') not in ('NEW','REFERENCE'): problem(row,'decision','明确选择NEW或REFERENCE。')
            if v.get('asset_type') not in ('WHOLE_UNIT','TRANSFORMER'): problem(row,'asset_type','请选择受控资产类型WHOLE_UNIT或TRANSFORMER。')
            if v.get('decision')=='NEW' and existing: problem(row,'material_number','已有物料请明确REFERENCE，不得覆盖。','material_exists_choose_reference')
            if v.get('decision')=='REFERENCE':
                if existing is None: problem(row,'material_number','引用的物料不存在。','material_not_found')
                else:
                    for field in ('model','asset_type'):
                        if v.get(field)!=existing[field]: problem(row,field,'与已有物料不同，不能通过导入修改。','material_conflict',facts=existing)

    def site_ref(row,required=False):
        v=row['values']; value=v.get('site_id')
        if not value:
            if required: problem(row,'site_id','请填写现场UUID或NEW:现场记录键。','site_reference_required')
            return None,None
        if isinstance(value,str) and value.startswith('NEW:'):
            ref=dict(kind='BATCH',record_key=value[4:]); target=index.get(('Sites',value[4:])) if keys[('Sites',value[4:])]==1 else None
            if target:
                if target['values'].get('decision')=='REFERENCE' and target.get('target_id') in sm:
                    return ref,sm[target['target_id']]
                if target['values'].get('decision')=='NEW':
                    proposed=target['values']
                    return ref,dict(site_name=proposed.get('site_name'),customer_id=proposed.get('customer_ref'),
                                    product_lines=proposed.get('product_lines'),record_key=value[4:])
            problem(row,'site_id','同批现场记录键不存在、重复或尚未明确解析，请核对Sites。','batch_reference_not_found')
            return None,None
        try: target=str(UUID(value))
        except (ValueError,TypeError,AttributeError): target=None
        if target not in sm:
            problem(row,'site_id','现场不存在；请先导入或同时提供Sites。','site_not_found')
            return None,None
        return dict(kind='EXISTING',site_id=target),sm[target]

    for row in rows:
        if row['sheet']=='Materials':
            v=row['values']; number=v.get('material_number')
            if number in materials: row['candidates']=[materials[number]]
        if row['sheet']!='Assets': continue
        v=row['values']; ref=v.get('material_ref'); material=None
        if isinstance(ref,str) and ref.startswith('MATERIAL:'):
            row['references']['material']=dict(kind='EXISTING',material_number=ref[9:])
            material=materials.get(ref[9:])
            if material is None: problem(row,'material_ref','物料不存在，请明确提供Materials新增。','material_not_found')
        elif isinstance(ref,str) and ref.startswith('NEW:'):
            row['references']['material']=dict(kind='BATCH',record_key=ref[4:])
            target=index.get(('Materials',ref[4:])) if keys[('Materials',ref[4:])]==1 else None
            if target: material=target['values']
            else: problem(row,'material_ref','同批物料记录键不存在。','batch_reference_not_found')
        else: problem(row,'material_ref','填写MATERIAL:已有物料号或NEW:物料记录键。','invalid_material_ref')
        if material:
            v.update(model=material.get('model'),asset_type=material.get('asset_type'),material_number=material.get('material_number'))
        if v.get('decision')!='NEW': problem(row,'decision','设备只新增，必须明确NEW并填写原因。')
        if v.get('product_line') not in KINDS: problem(row,'product_line','请选择PV或ESS。')
        elif v.get('machine_type') not in KINDS[v['product_line']]: problem(row,'machine_type','机器类型不属于产品线。')
        if material and (v.get('machine_type')=='TRANSFORMER')!=(material.get('asset_type')=='TRANSFORMER'):
            problem(row,'machine_type','机器类型与受控物料资产类型不符。')
        try:
            instant=datetime.fromisoformat(v.get('effective_at'))
            if instant.tzinfo is None or instant>now: raise ValueError()
            v['effective_at']=instant.astimezone(timezone.utc).isoformat()
        except (ValueError,TypeError): problem(row,'effective_at','填写带时区且不晚于当前时间的完整时刻。','invalid_effective_at')
        for field in ('power_mw','energy_mwh'):
            value=v.get(field)
            if value in (None,''): v[field]=None; continue
            try:
                number=Decimal(str(value))
                if isinstance(value,bool) or not number.is_finite() or not 0<=number<Decimal('10000000000') or number.as_tuple().exponent < -6: raise ValueError()
                v[field]=str(number)
            except (ValueError,InvalidOperation): problem(row,field,'填写非负有限数值，最多6位小数且小于10000000000。')
        if v.get('product_line')=='PV' and v.get('energy_mwh') is not None: problem(row,'energy_mwh','PV设备不填写MWh。')
        if v.get('commissioning_date') not in (None,''):
            try:
                if date.fromisoformat(v['commissioning_date']).isoformat()!=v['commissioning_date']: raise ValueError()
            except (ValueError,TypeError): problem(row,'commissioning_date','日期必须为YYYY-MM-DD。')
        location=v.get('location_kind')
        if location not in ('SITE','PARENT','REPAIR_CENTER'): problem(row,'location_kind','请选择SITE、PARENT或REPAIR_CENTER。')
        allowed=('SPARE','UNDER_REPAIR','RETIRED') if location=='REPAIR_CENTER' else ('IN_SERVICE',)
        if v.get('status') not in allowed: problem(row,'status','状态与位置不一致。','status_location_conflict')
        if location=='SITE':
            if v.get('machine_type') not in ('INVERTER_UNIT','ESS_SYSTEM'): problem(row,'machine_type','只有整机或储能系统可直接归属现场。')
            if v.get('parent_record_key'): problem(row,'parent_record_key','SITE根设备不填写父键。')
        if location=='REPAIR_CENTER':
            for field in ('parent_record_key','site_id','site_name'):
                if v.get(field): problem(row,field,'维修中心独立设备不填写父键或现场。','status_location_conflict')
        if location=='PARENT' and not v.get('parent_record_key'): problem(row,'parent_record_key','必须填写同批父记录键。','missing_parent')
        name=v.get('site_name')
        if isinstance(name,str):
            row['candidates']=[dict(kind='SITE',**json.loads(json.dumps(site,default=str))) for site in sites if site['site_name'].strip().casefold()==name.casefold()]
        if v.get('location_kind')=='SITE':
            reference,site=site_ref(row,True)
            if reference: row['references']['site']=reference
            if not isinstance(name,str) or not name: problem(row,'site_name','SITE根设备须填写现场名称。')
            if site:
                available=site.get('product_lines')
                configured=set(available.split(';')) if isinstance(available,str) else {line['product_line'] for line in lines if str(line['site_id'])==str(site.get('id'))}
                if v.get('product_line') not in configured: problem(row,'site_id','现场未配置设备所需产品线，请通过受控维护处理。','site_product_line_missing')
                if isinstance(name,str) and name and name!=site['site_name']: problem(row,'site_name','名称与编号不同，请修正或明确确认采用该现场编号。','site_name_difference','WARNING',facts=[reference,site])
                row['resolved_context']=dict(site_name=site['site_name'],customer_id=str(site['customer_id']))
    def site_identity(reference):
        if not reference: return None
        if reference['kind']=='EXISTING': return reference['site_id']
        key=reference['record_key']
        master=index.get(('Sites',key)) if keys[('Sites',key)]==1 else None
        if master is None: return None
        if master['values'].get('decision')=='NEW': return ('BATCH',key)
        if master['values'].get('decision')=='REFERENCE' and master.get('target_id') in sm:
            return master['target_id']
        return None

    for row in rows:
        if row['sheet']!='Assets' or row['values'].get('location_kind')!='PARENT': continue
        current=row; visited=set(); root=None
        while current:
            identity=(current['sheet'],current['row'])
            if identity in visited or len(visited)>=100:
                problem(row,'parent_record_key','父子关系存在循环或超过100节点路径。','cyclic_installation'); break
            visited.add(identity)
            if current['values'].get('location_kind')!='PARENT':
                root=current; break
            key=current['values'].get('parent_record_key')
            parent=index.get(('Assets',key)) if keys[('Assets',key)]==1 else None
            if parent is None:
                problem(row,'parent_record_key','父记录键不存在或重复；仅引用本批明确设备。','missing_parent'); break
            if current['values'].get('product_line')!=parent['values'].get('product_line'):
                problem(row,'parent_record_key','父子设备产品线不一致。')
            try:
                if datetime.fromisoformat(current['values'].get('effective_at'))<datetime.fromisoformat(parent['values'].get('effective_at')):
                    problem(row,'effective_at','子设备不能早于父设备初始位置生效。','invalid_effective_at')
            except (ValueError,TypeError): pass  # already a scalar validation issue
            if parent['values'].get('status')!='IN_SERVICE':
                problem(row,'parent_record_key','不能安装在维修、备用或停用祖先下面。','parent_not_at_site')
            current=parent
        if not root: continue
        if root['values'].get('location_kind')!='SITE':
            problem(row,'parent_record_key','子设备祖先必须位于现场，不能继承维修中心。','parent_not_at_site'); continue
        inherited=root.get('references',{}).get('site')
        if site_identity(inherited) is None:
            problem(row,'site_id','根设备现场未解析；请先修正根设备的现场引用。','inherited_site_conflict')
        if inherited: row['references']['site']=inherited
        if root.get('resolved_context'): row['resolved_context']=dict(root['resolved_context'])
        v=row['values']; explicit=None
        if v.get('site_id'):
            explicit,_=site_ref(row)
            if not explicit or site_identity(explicit)!=site_identity(inherited):
                problem(row,'site_id','提供的现场与父设备继承现场不一致。','inherited_site_conflict')
        name=v.get('site_name'); actual=root.get('resolved_context',{}).get('site_name')
        if name and actual and name!=actual:
            if explicit and site_identity(explicit)==site_identity(inherited):
                problem(row,'site_name','名称不同，请修正或明确确认采用继承现场编号。','site_name_difference','WARNING',facts=[inherited,actual])
            else: problem(row,'site_name','名称与继承现场不一致，请修正或提供明确一致编号。','inherited_site_conflict')
    serials=Counter(serial_key(r['values']['serial_number']) for r in rows if r['sheet']=='Assets' and isinstance(r['values'].get('serial_number'),str))
    # PostgreSQL17 lower is not Unicode casefold. Stream compact catalog identities
    # through the same policy before loading candidate details; never prefilter away
    # exact non-ASCII matches or change their physical identity.
    candidate_ids=[]
    if serials:
        with c.execute(text('SELECT id,serial_number FROM formal_assets ORDER BY id'),execution_options={'yield_per':500}) as catalog_rows:
            candidate_ids=[asset.id for asset in catalog_rows if serial_key(asset.serial_number) in serials]
    assets=c.execute(text('SELECT * FROM formal_assets WHERE id=ANY(:ids) ORDER BY system_asset_number,id'),{'ids':candidate_ids}).mappings() if candidate_ids else ()
    candidates=[]
    for asset in assets:
        item={k:asset[k] for k in ('id','system_asset_number','serial_number','material_number','model','asset_type','product_line','lifecycle_status','lifecycle_revision')}
        item['kind']='ASSET'
        try: location=location_at(c,asset['id'],now)
        except AssetQueryError as error: location=dict(kind='UNKNOWN',path=[],site_id=None,label='位置无法核实',code=error.code)
        item['location']=location
        site=sm.get(str(location['site_id']))
        if site:
            item.update(site_name=site['site_name'],site_revision=site['revision'],location_text=site['location_text'],customer_id=site['customer_id'],customer_name=next(a['customer_name'] for a in customers if a['id']==site['customer_id']))
        candidates.append(json.loads(json.dumps(item,default=str)))
    path_ids={UUID(node['id']) for candidate in candidates for node in candidate['location']['path']}
    ancestry={str(a['id']):dict(a) for a in c.execute(text('SELECT id,lifecycle_revision,lifecycle_status,model,material_number FROM formal_assets WHERE id=ANY(:ids)'),{'ids':list(path_ids)}).mappings()} if path_ids else {}
    for candidate in candidates:
        for node in candidate['location']['path']:
            node.update(ancestry[node['id']])
            node['id']=str(node['id'])
    for row in rows:
        if row['sheet']!='Assets' or not isinstance(row['values'].get('serial_number'),str): continue
        serial=serial_key(row['values']['serial_number'])
        existing=[a for a in candidates if serial_key(a['serial_number'])==serial]
        others=[dict(kind='BATCH_ASSET',record_key=a['values'].get('record_key'),row=a['row'],serial_number=a['values']['serial_number'],model=a['values'].get('model'),material_number=a['values'].get('material_number'),product_line=a['values'].get('product_line'),status=a['values'].get('status'),location_kind=a['values'].get('location_kind'),resolved_context=a.get('resolved_context')) for a in rows if a['sheet']=='Assets' and a['row']!=row['row'] and isinstance(a['values'].get('serial_number'),str) and serial_key(a['values']['serial_number'])==serial]
        if existing or others:
            row['candidates'].extend(existing+others)
            problem(row,'serial_number','序列号重复；请核对候选并明确确认另一台物理设备，不覆盖或合并。','duplicate_serial','WARNING',facts=existing+others)
    ordered={(e['sheet'],e['row']):n for n,e in enumerate(source)}
    rows.sort(key=lambda r:ordered[(r['sheet'],r['row'])])
    return rows,issues,counts(rows,issues),digest([fingerprint,material_catalog,candidates])
