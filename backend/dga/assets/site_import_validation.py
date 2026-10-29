"""Customer/site validation belongs to assets; snapshot is rechecked at publication."""
from collections import Counter
import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import UUID
from sqlalchemy import text
from .site_import_workbook import problem, COLUMNS


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()

def catalog(c):
    customers=[dict(r) for r in c.execute(text('SELECT id,customer_name FROM customers ORDER BY id')).mappings()]
    sites=[dict(r) for r in c.execute(text('SELECT * FROM sites ORDER BY id')).mappings()]
    lines=[dict(r) for r in c.execute(text('SELECT * FROM site_product_lines ORDER BY site_id,product_line')).mappings()]
    return customers,sites,lines

def validate(c, source):
    customers,sites,lines=catalog(c)
    fingerprint=digest([customers,sites,lines])
    cm={str(r['id']):r for r in customers}; sm={str(r['id']):r for r in sites}
    rows=[]; issues=[]; keys={}; seen=set()
    new_names=Counter((r['sheet'],str(r['values'].get('customer_name' if r['sheet']=='Customers' else 'site_name','')).strip().casefold()) for r in source if r['values'].get('decision')=='NEW')
    for entry in source:
        v={k:(value.strip() if isinstance(value,str) and k!='source_note' else value) for k,value in entry['values'].items()}
        r=dict(sheet=entry['sheet'],row=entry['row'],values=v,candidates=[]); rows.append(r)
        def issue(field,message,code='invalid_value',severity='ERROR'):
            item=problem(message,sheet=r['sheet'],row=r['row'],field=field,code=code)
            item['severity']=severity; item['id']=digest([r['sheet'],r['row'],field,code,message])[:24]
            issues.append(item)
        key=v.get('record_key')
        if not isinstance(key,str) or not 1<=len(key)<=120 or (r['sheet'],key) in keys: issue('record_key','记录键必须为表内不同的文本，最多120字符。')
        keys[(r['sheet'],key)]=r
        for field in v.keys()-set(COLUMNS[r['sheet']]): issue(field,'不支持此写入字段。')
        note=v.get('source_note')
        if note is not None and (not isinstance(note,str) or len(note)>2000): issue('source_note','来源备注必须为文本，最多2000字符。')
        for field,value in v.items():
            if isinstance(value,str) and any(ord(ch)<32 and ch not in '\r\n\t' for ch in value): issue(field,'包含无效字符。')
        if v.get('decision') not in ('NEW','REFERENCE'): issue('decision','请明确选择NEW新增或REFERENCE引用。')
        if not isinstance(v.get('reason'),str) or not 1<=len(v['reason'])<=1000: issue('reason','请填写核对/新增原因，最多1000字符。')
        name_key='customer_name' if r['sheet']=='Customers' else 'site_name'
        name=v.get(name_key)
        if not isinstance(name,str) or not 1<=len(name)<=200: issue(name_key,'名称必填，最多200字符。')
        directory=customers if r['sheet']=='Customers' else sites
        r['candidates']=[json.loads(json.dumps(a,default=str)) for a in directory if isinstance(name,str) and a[name_key].strip().casefold()==name.casefold()]
        id_key='customer_id' if r['sheet']=='Customers' else 'site_id'
        if v.get('decision')=='REFERENCE':
            try: target=str(UUID(v.get(id_key)))
            except (ValueError,TypeError,AttributeError): target=None
            existing=(cm if r['sheet']=='Customers' else sm).get(target)
            if existing is None: issue(id_key,'请填写确实存在的完整正式UUID。')
            else:
                if (r['sheet'],target) in seen: issue(id_key,'同批不能多次引用同一记录。')
                seen.add((r['sheet'],target)); r['target_id']=target
        elif v.get('decision')=='NEW':
            if v.get(id_key): issue(id_key,'新增请留空已有编号。')
            if r['candidates']: issue(name_key,'发现同名已有资料；请核对差异并明确确认是不同实体。','same_name','WARNING')
        if r['sheet']=='Sites':
            ref=v.get('customer_ref')
            if not isinstance(ref,str) or not ref: issue('customer_ref','请引用已有客户UUID或NEW:客户记录键。')
            elif not ref.startswith('NEW:'):
                if ref not in cm: issue('customer_ref','客户不存在，请明确引用或在客户表新增。')
            product_lines=v.get('product_lines')
            product_lines=product_lines.split(';') if isinstance(product_lines,str) else []
            if not product_lines or len(set(product_lines))!=len(product_lines) or set(product_lines)-{'PV','ESS'}: issue('product_lines','填写PV、ESS或PV;ESS。')
            for field in ('pv_power_mw','ess_power_mw','ess_energy_mwh'):
                value=v.get(field)
                if value in (None,''): v[field]=None; continue
                try:
                    number=Decimal(str(value))
                    if isinstance(value,bool) or not number.is_finite() or number<0 or number>=Decimal('10000000000') or number.as_tuple().exponent < -6: raise ValueError()
                    if ('PV' if field.startswith('pv_') else 'ESS') not in product_lines: raise ValueError()
                    v[field]=str(number)
                except (ValueError,InvalidOperation): issue(field,'容量须为所属产品线的非负有限数值，最多6位小数。')
            for field,allowed in [('grid_status',{'NOT_STARTED','IN_PROGRESS','COMPLETED'}),('operation_status',{'NOT_OPERATIONAL','PARTIAL','OPERATIONAL','DECOMMISSIONED'})]:
                if v.get(field) not in (None,'') and v[field] not in allowed: issue(field,'请选择已有现场状态。')
            if v.get('location_text') is not None and (not isinstance(v['location_text'],str) or len(v['location_text'])>300): issue('location_text','位置最多300字符。')
            if v.get('commissioning_date') not in (None,''):
                try:
                    if date.fromisoformat(v['commissioning_date']).isoformat()!=v['commissioning_date']: raise ValueError()
                except (ValueError,TypeError): issue('commissioning_date','日期必须为YYYY-MM-DD。')
    for r in rows:
        v=r['values']
        def final_issue(field,message,code='invalid_reference',severity='ERROR'):
            item=problem(message,sheet=r['sheet'],row=r['row'],field=field,code=code)
            item['severity']=severity; item['id']=digest([r['sheet'],r['row'],field,code,message])[:24]; issues.append(item)
        if r['sheet']=='Sites' and isinstance(r['values'].get('customer_ref'),str) and r['values']['customer_ref'].startswith('NEW:'):
            ref=keys.get(('Customers',v['customer_ref'][4:]))
            if ref is None: final_issue('customer_ref','同批客户记录键不存在。')
        if v.get('decision')=='REFERENCE' and r.get('target_id'):
            existing=(cm if r['sheet']=='Customers' else sm)[r['target_id']]
            if r['sheet']=='Customers':
                if v.get('customer_name')!=existing['customer_name']: final_issue('customer_name','提供名称与正式客户不同，将保留正式资料。','reference_difference','WARNING')
            else:
                ref=v.get('customer_ref')
                customer=keys.get(('Customers',ref[4:])) if isinstance(ref,str) and ref.startswith('NEW:') else None
                resolved=customer.get('target_id') if customer else ref
                if str(existing['customer_id'])!=resolved: final_issue('customer_ref','客户归属不一致；不能通过导入变更现场客户。')
                existing_lines={line['product_line']:line for line in lines if str(line['site_id'])==r['target_id']}
                requested=v.get('product_lines','').split(';') if isinstance(v.get('product_lines'),str) else []
                if not set(requested)<=set(existing_lines): final_issue('product_lines','已有现场未配置所需产品线，请先通过受控维护处理。')
                different=[]
                for field in ('site_name','location_text','commissioning_date','grid_status','operation_status'):
                    if v.get(field) not in (None,'') and str(v[field])!=str(existing[field]): different.append(field)
                for field,line,column in [('pv_power_mw','PV','power_mw'),('ess_power_mw','ESS','power_mw'),('ess_energy_mwh','ESS','energy_mwh')]:
                    if v.get(field) not in (None,''):
                        try:
                            old=existing_lines.get(line,{}).get(column)
                            if old is None or Decimal(v[field])!=old: different.append(field)
                        except (InvalidOperation,ValueError,TypeError): pass
                if different: final_issue('site_id','以下提供值与正式资料不同，引用时保留正式值：'+', '.join(different),'reference_difference','WARNING')
        if v.get('decision')=='NEW':
            name_key='customer_name' if r['sheet']=='Customers' else 'site_name'
            if isinstance(v.get(name_key),str) and new_names[(r['sheet'],v[name_key].casefold())]>1:
                final_issue(name_key,'同批存在同名新增资料，请确认是不同实体。','same_batch_name','WARNING')
        if r['sheet']=='Sites':
            for candidate in r['candidates']:
                candidate['customer_name']=cm[str(candidate['customer_id'])]['customer_name']
                candidate['lines']=[json.loads(json.dumps(line,default=str)) for line in lines if str(line['site_id'])==candidate['id']]
    errors={ (i['sheet'],i['row']) for i in issues if i['severity']=='ERROR'}
    warnings={ (i['sheet'],i['row']) for i in issues if i['severity']=='WARNING'}-errors
    counts=dict(total_rows=len(rows),valid_rows=len(rows)-len(errors|warnings),error_rows=len(errors),warning_rows=len(warnings),error_count=sum(i['severity']=='ERROR' for i in issues),warning_count=sum(i['severity']=='WARNING' for i in issues))
    return rows,issues,counts,fingerprint
