"""Laboratory-owned staged interpretation; source evidence never becomes formal results."""
import hashlib
import json
import re
from collections import defaultdict
from decimal import Decimal,InvalidOperation
from uuid import UUID,uuid5
from dga.assets.public import AssetQueryError
from dga.shared.auth.public import IdentityError
from .import_time import decode_time

FIELDS={'DGA':('H2','CH4','C2H2','C2H4','C2H6','CO','CO2'),
        'MOISTURE':('MOISTURE',),'BREAKDOWN_VOLTAGE':('BREAKDOWN_VOLTAGE',)}
BOUNDS={'source_lab_name':200,'source_site_name':200,'source_whole_unit_serial':160,
        'source_transformer_serial':160,'system_asset_number':80,'source_method':160,
        'source_method_version':80,'source_instrument':160,'source_analyst':150,'source_qa':2000,
        'notes':2000,'source_note':2000,'sampled_at':80,'received_at':80,'measured_at':80,
        'sampled_timezone':100,'received_timezone':100,'measured_timezone':100}
for _prefix in ('h2','ch4','c2h2','c2h4','c2h6','co','co2','result'):
    BOUNDS[_prefix+'_unit']=40
DECIMAL=re.compile(r'^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE]([+-]?[0-9]+))?$')
IDENTIFIER=re.compile(r'^[A-Za-z][A-Za-z0-9_-]{0,79}$')


def empty(value):
    return value is None or value==''


def issue(row,code,field='',*,severity='ERROR',evidence=None,message=None):
    raw=row['reviewed_values'].get(field) if field else None
    if evidence is None: evidence=raw
    stable=dict(version=1,code=code,file_id=row['file_id'],sheet=row['sheet'],
        row=row['row_number'],field=field,evidence=evidence)
    fingerprint=hashlib.sha256(json.dumps(stable,sort_keys=True,ensure_ascii=False,
        separators=(',',':'),default=str).encode()).hexdigest()[:24]
    value=dict(id=fingerprint,version=1,code=code,severity=severity,file_id=row['file_id'],
        sheet=row['sheet'],row_number=row['row_number'],field=field,row_id=row['id'],
        external_sample_id=row['parsed_values'].get('external_sample_id'),
        external_test_id=row['parsed_values'].get('external_test_id'),raw_value=raw,
        message=message or ('资料需要核对：'+code),
        suggestion='依据保留的原件核对该字段和已明确批准的配置；不自动补值或合并。')
    if not any(x['id']==fingerprint for x in row['issues']): row['issues'].append(value)


def text_value(row,field,*,required=False,maximum=None,identifier=False):
    value=row['reviewed_values'].get(field)
    if empty(value):
        if required: issue(row,'missing_required_value',field)
        return None
    cell_type=row['raw_cell_types'].get(field,'TEXT') if field not in row['overrides'] else 'TEXT'
    if not isinstance(value,str) or cell_type!='TEXT':
        issue(row,'identifier_requires_text' if identifier else 'field_type_invalid',field)
        return None
    result=value.strip() if identifier else value
    if identifier and (not result or any(ord(x)<32 or ord(x)==127 for x in result)):
        issue(row,'invalid_identifier',field)
        return None
    if maximum is not None and len(result)>maximum:
        issue(row,'field_length_exceeded',field,evidence=maximum)
        return None
    if any((ord(x)<32 and x not in '\n\r\t') or ord(x)==127 for x in value):
        issue(row,'invalid_identifier' if identifier else 'field_control_invalid',field)
        return None
    return result


def boolean(row,field,*,required=False):
    value=row['reviewed_values'].get(field)
    if empty(value):
        if required: issue(row,'missing_required_value',field)
        return None
    if type(value) is bool: return value
    if isinstance(value,str) and value.strip().upper() in ('TRUE','FALSE'):
        return value.strip().upper()=='TRUE'
    issue(row,'boolean_invalid',field)
    return None


def temporal(row,field,snapshot,*,required=True):
    values=row['reviewed_values']
    parsed=decode_time(values.get(field),cell_type=row['raw_cell_types'].get(field,'TEXT')
        if field not in row['overrides'] else 'TEXT',
        row_zone=values.get(field.replace('_at','_timezone')),
        batch_zone=snapshot.get('source_timezone'),batch_zone_confirmed=snapshot.get('source_timezone_confirmed',False),
        required=required)
    for code in parsed['issue_codes']: issue(row,code,field)
    return parsed


def numeric(row,prefix,configuration=None,*,gas=False):
    value=row['reviewed_values'].get(prefix+'_value')
    q=row['reviewed_values'].get(prefix+'_qualifier')
    unit=row['reviewed_values'].get(prefix+'_unit')
    q=q.strip() if isinstance(q,str) else q
    unit=unit if isinstance(unit,str) else None
    result=dict(raw_value=value,qualifier=q or None,value=None,unit=unit,source_precision=None)
    if empty(q):
        issue(row,'gas_required' if gas and empty(value) else 'qualifier_required',prefix+'_qualifier')
    elif q not in ('EQ','ND','LT','GT'): issue(row,'qualifier_invalid',prefix+'_qualifier')
    decimal=None
    if q=='ND':
        if not empty(value): issue(row,'qualifier_value_conflict',prefix+'_value')
    elif empty(value):
        issue(row,'missing_required_value',prefix+'_value')
    else:
        token=value.strip() if isinstance(value,str) else ''
        match=DECIMAL.fullmatch(token) if len(token)<=128 else None
        exponent=match.group(1) if match else None
        if not match or (exponent and (len(exponent.lstrip('+-'))>4 or abs(int(exponent))>1000)):
            issue(row,'invalid_decimal',prefix+'_value')
        else:
            try: decimal=Decimal(token)
            except InvalidOperation: issue(row,'invalid_decimal',prefix+'_value')
            if decimal is not None:
                precision=max(0,-decimal.as_tuple().exponent)
                result['source_precision']=str(precision)
                if not decimal.is_finite() or decimal<0 or decimal>=Decimal('1e12'):
                    issue(row,'result_out_of_range',prefix+'_value');decimal=None
                elif precision>6:
                    issue(row,'result_precision_exceeded',prefix+'_value');decimal=None
                else: result['value']=str(decimal)
    if empty(unit): issue(row,'unit_required',prefix+'_unit')
    if configuration:
        approved=configuration.get('unit_code')
        if approved is None: issue(row,'method_not_configured','method_version_id')
        elif unit is not None and unit!=approved: issue(row,'unit_mismatch',prefix+'_unit',evidence=approved)
        if q in ('EQ','ND','LT','GT') and q not in configuration.get('allowed_qualifiers',('EQ','ND','LT','GT')):
            issue(row,'configured_qualifier_not_allowed',prefix+'_qualifier')
        if decimal is not None:
            places=configuration.get('display_decimal_places')
            if places is not None and max(0,-decimal.as_tuple().exponent)>places:
                issue(row,'configured_precision_exceeded',prefix+'_value',evidence=places)
            for bound,compare in (('minimum',lambda a,b:a<b),('maximum',lambda a,b:a>b)):
                if configuration.get(bound) is not None and compare(decimal,Decimal(str(configuration[bound]))):
                    issue(row,'configured_range_exceeded',prefix+'_value',evidence=[bound,configuration[bound]])
    return result


def validate_tables(tables,snapshot,catalog,assets,actor,*,progress=None):
    bindings={x['source_lab_key']:x for x in snapshot['bindings']}
    methods={str(x['id']):x for x in catalog['methods']}
    active_types={x['code'] for x in catalog['types'] if x['is_active']}
    rows=[]
    for table in tables:
        for raw in table.rows:
            row_id=str(uuid5(UUID(raw.file_id),raw.sheet+'\0'+str(raw.row_number)))
            overrides=snapshot.get('overrides',{}).get(row_id,{})
            reviewed={**raw.values,**overrides}
            row=dict(id=row_id,file_id=raw.file_id,sheet=raw.sheet,row_number=raw.row_number,
                raw_values=dict(raw.values),raw_cell_types=dict(raw.cell_types),overrides=dict(overrides),
                reviewed_values=reviewed,parsed_values={},issues=[],sample_row_id=None,
                source_lab_id=None,external_sample_id=None,external_test_id=None)
            rows.append(row)
            for problem in raw.problems:
                issue(row,problem['code'],problem.get('field',''))
    samples=[x for x in rows if x['sheet']=='油样信息']
    tests=[x for x in rows if x['sheet']=='检测结果']
    for row in rows:
        p=row['parsed_values']
        alias=text_value(row,'source_lab_key',required=True,maximum=80,identifier=True)
        if alias and not IDENTIFIER.fullmatch(alias): issue(row,'invalid_identifier','source_lab_key')
        p['source_lab_key']=alias
        sample_id=text_value(row,'external_sample_id',required=True,maximum=160,identifier=True)
        p['external_sample_id']=row['external_sample_id']=sample_id
        binding=bindings.get(alias)
        if binding:
            row['source_lab_id']=p['source_lab_id']=binding['source_lab_id']
            raw_name=row['reviewed_values'].get('source_lab_name')
            if raw_name and raw_name!=binding['display_name']:
                issue(row,'source_lab_name_difference','source_lab_name',severity='WARNING',evidence=binding['display_name'])
        else: issue(row,'source_lab_unconfirmed','source_lab_key')
        for field,bound in BOUNDS.items():
            if field in row['reviewed_values']: text_value(row,field,maximum=bound)
        p['notes']=row['reviewed_values'].get('notes')
        p['source_note']=row['reviewed_values'].get('source_note')
    asset_cache={}
    raw_samples=defaultdict(list);stable_samples=defaultdict(list)
    for sample_index,row in enumerate(samples):
        p=row['parsed_values'];v=row['reviewed_values']
        if p['source_lab_key'] and p['external_sample_id']:
            raw_samples[(p['source_lab_key'],p['external_sample_id'])].append(row)
        if row['source_lab_id'] and p['external_sample_id']:
            stable_samples[(row['source_lab_id'],p['external_sample_id'])].append(row)
        p['temporal']=dict(sampled_at=temporal(row,'sampled_at',snapshot),
            received_at=temporal(row,'received_at',snapshot,required=False))
        physical=p['physical_received']=boolean(row,'physical_received',required=True)
        count=v.get('container_count')
        if empty(count): count=0 if physical is False else None
        elif isinstance(count,str) and re.fullmatch('[0-9]{1,2}',count.strip()): count=int(count)
        elif type(count) is not int: count=None
        if count is None or not 0<=count<=20 or (physical is True and count==0):
            issue(row,'container_count_invalid','container_count')
        p['container_count']=count
        if physical is False and (not empty(v.get('received_at')) or count not in (None,0)):
            issue(row,'physical_receipt_conflict','physical_received')
        if physical is True and p['temporal']['received_at']['precision']!='INSTANT':
            issue(row,'physical_receipt_conflict','received_at')
        sampled,received=p['temporal']['sampled_at'],p['temporal']['received_at']
        if physical is True and sampled['utc_instant'] and received['utc_instant']:
            from datetime import datetime
            if datetime.fromisoformat(received['utc_instant'])<datetime.fromisoformat(sampled['utc_instant']):
                issue(row,'received_before_sampled','received_at')
        elif physical is True and sampled['precision']=='DATE':
            issue(row,'receipt_order_unverified','received_at',severity='WARNING')
        context=v.get('sampling_context')
        if context not in ('SITE','REPAIR_CENTER','OTHER'):
            issue(row,'missing_required_value' if empty(context) else 'sampling_context_invalid','sampling_context')
        p['sampling_context']=context
        p['reports']=[]
        reports=v.get('report_filenames')
        if not empty(reports):
            try:
                names=json.loads(reports)
                if (not isinstance(names,list) or len(names)>100 or len(set(names))!=len(names)
                    or any(not isinstance(n,str) or not 1<=len(n)<=255 or not n.lower().endswith('.pdf')
                           or any(ord(ch)<32 or ch in '/\\:' for ch in n) for n in names)):
                    raise ValueError()
                p['reports']=[dict(filename=n,state='DECLARED_NOT_PROVIDED') for n in names]
                if names: issue(row,'report_file_not_provided','report_filenames',severity='WARNING',evidence=names)
            except (ValueError,TypeError): issue(row,'report_filename_invalid','report_filenames')
        asset_id=v.get('formal_asset_id');number=v.get('system_asset_number')
        p['asset']=None
        if empty(asset_id) and empty(number):
            issue(row,'asset_identity_required','formal_asset_id')
        else:
            try:
                identity_key=(asset_id or None,number or None)
                if identity_key not in asset_cache:
                    try:
                        asset_cache[identity_key]=assets.lookup_physical_transformer(actor,asset_id=asset_id or None,
                            system_asset_number=number or None)
                    except (AssetQueryError,IdentityError) as error: asset_cache[identity_key]=error
                asset=asset_cache[identity_key]
                if isinstance(asset,Exception): raise asset
                p['asset']=dict(id=str(asset.id),system_asset_number=asset.system_asset_number,
                    serial_number=asset.serial_number,model=asset.model,historical_context=dict(status='UNVERIFIED'))
                if sampled['precision']=='INSTANT':
                    from datetime import datetime
                    try:
                        historical=assets.resolve_sampling_context(actor,asset.id,sampled_at=datetime.fromisoformat(sampled['utc_instant']))
                        p['asset']['historical_context']=dict(status='VERIFIED',site_name=historical.site_name,
                            customer_name=historical.customer_name,site_id=str(historical.site_id) if historical.site_id else None)
                    except AssetQueryError: issue(row,'historical_context_unverified','sampled_at',severity='WARNING')
                else: issue(row,'historical_context_unverified','sampled_at',severity='WARNING')
            except IdentityError: issue(row,'asset_lookup_not_authorized','formal_asset_id')
            except AssetQueryError as error:
                code={'asset_identity_conflict':'asset_identity_conflict','transformer_required':'asset_not_transformer',
                    'asset_not_found':'asset_unknown'}.get(error.code,'asset_unknown')
                issue(row,code,'formal_asset_id')
        if progress and ((sample_index+1)%100==0 or sample_index+1==len(samples)):
            progress(sample_index+1,len(rows))
    for group in list(raw_samples.values())+list(stable_samples.values()):
        if len(group)>1:
            evidence=sorted(x['id'] for x in group)
            for row in group: issue(row,'duplicate_sample_key','external_sample_id',evidence=evidence)
    duplicate_tests=defaultdict(list)
    for index,row in enumerate(tests):
        p=row['parsed_values'];v=row['reviewed_values']
        test_id=text_value(row,'external_test_id',required=True,maximum=160,identifier=True)
        row['external_test_id']=p['external_test_id']=test_id
        candidates=raw_samples.get((p['source_lab_key'],p['external_sample_id']),[])
        if len(candidates)==1:
            candidate=candidates[0]
            if candidate['source_lab_id'] and len(stable_samples.get(
                (candidate['source_lab_id'],candidate['external_sample_id']),[]))>1: candidates=[]
            elif test_id: row['sample_row_id']=candidate['id']
        if len(candidates)>1 or (len(candidates)==0 and
            any(x['code']=='duplicate_sample_key' for x in raw_samples.get((p['source_lab_key'],p['external_sample_id']),[{}])[0].get('issues',[]))):
            issue(row,'ambiguous_sample_reference','external_sample_id')
        elif not row['sample_row_id'] and test_id:
            issue(row,'sample_not_found','external_sample_id')
        if test_id and p['external_sample_id']:
            duplicate_tests[(row['source_lab_id'] or p['source_lab_key'],p['external_sample_id'],test_id)].append(row)
        kind=p['test_type']=v.get('test_type')
        p['temporal']=dict(measured_at=temporal(row,'measured_at',snapshot))
        p['source_evidence']={k:v.get(k) for k in ('source_method','source_method_version','source_instrument','source_analyst','source_qa')}
        for field in ('source_instrument','source_analyst','source_qa'):
            if empty(v.get(field)): issue(row,field+'_unprovided',field,severity='WARNING')
        selected=p['report_selected']=boolean(row,'report_selected')
        p['report_selection']='UNRESOLVED'
        p['measurements']={}
        if kind not in FIELDS or kind not in active_types:
            issue(row,'unsupported_test_type','test_type')
        else:
            method_id=v.get('method_version_id');method=None;configuration={}
            if empty(method_id): issue(row,'method_required','method_version_id')
            else:
                try: method=methods.get(str(UUID(method_id)))
                except (ValueError,TypeError,AttributeError): method=None
                if method is None: issue(row,'method_unknown','method_version_id')
                elif method['test_type']!=kind: issue(row,'method_type_mismatch','method_version_id')
                elif not method['is_active']: issue(row,'method_inactive','method_version_id')
                elif not isinstance(method['configuration'],dict): issue(row,'method_not_configured','method_version_id')
                else: configuration={x['code']:x for x in method['configuration'].get('fields',[]) if isinstance(x,dict) and 'code' in x}
            p['method_version_id']=str(method['id']) if method else None
            expected=FIELDS[kind]
            for code in expected:
                prefix=code.lower() if kind=='DGA' else 'result'
                if method and code not in configuration: issue(row,'method_not_configured','method_version_id')
                p['measurements'][code]=numeric(row,prefix,configuration.get(code),gas=kind=='DGA')
            unrelated=('result',) if kind=='DGA' else ('h2','ch4','c2h2','c2h4','c2h6','co','co2')
            for prefix in unrelated:
                for suffix in ('value','qualifier','unit'):
                    field=prefix+'_'+suffix
                    if not empty(v.get(field)): issue(row,'unexpected_result_field',field)
        if progress and ((index+1)%100==0 or index+1==len(tests)): progress(index+1+len(samples),len(rows))
    for group in duplicate_tests.values():
        if len(group)>1:
            for row in group: issue(row,'duplicate_test_key','external_test_id',evidence=sorted(x['id'] for x in group))
    for sample in samples:
        related=[x for x in tests if x['sample_row_id']==sample['id']]
        by_type=defaultdict(list)
        for row in related: by_type[row['parsed_values']['test_type']].append(row)
        if not related: issue(sample,'test_required')
        for kind,group in by_type.items():
            selected=[x for x in group if x['parsed_values']['report_selected'] is True]
            if len(group)==1 and group[0]['parsed_values']['report_selected'] is None:
                group[0]['parsed_values']['report_selection']='SINGLE_CANDIDATE'
            elif len(selected)==1:
                for row in group: row['parsed_values']['report_selection']='EXPLICIT_SELECTED' if row in selected else 'EXPLICIT_NOT_SELECTED'
            else:
                code='report_selection_conflict' if len(selected)>1 else 'report_selection_required'
                issue(sample,code,evidence=kind)
                for row in group: issue(row,code,'report_selected',evidence=kind)
        child_errors=sum(x['severity']=='ERROR' for row in related for x in row['issues'])
        child_warnings=sum(x['severity']=='WARNING' for row in related for x in row['issues'])
        sample['parsed_values'].update(related_test_count=len(related),related_error_count=child_errors,
            related_warning_count=child_warnings,checked=not child_errors and not any(x['severity']=='ERROR' for x in sample['issues']))
    for row in tests: row['parsed_values']['checked']=not any(x['severity']=='ERROR' for x in row['issues'])
    sample_pages={row['id']:index//20+1 for index,row in enumerate(sorted(samples,key=lambda r:(r['row_number'],r['id'])))}
    test_groups=defaultdict(list)
    for row in sorted(tests,key=lambda r:(r['row_number'],r['id'])): test_groups[row['sample_row_id']].append(row)
    test_pages={row['id']:index//20+1 for group in test_groups.values() for index,row in enumerate(group)}
    for row in rows:
        parent=row['id'] if row['sheet']=='油样信息' else row['sample_row_id']
        for item in row['issues']:
            item.update(external_sample_id=row['external_sample_id'],external_test_id=row['external_test_id'],
                sample_row_id=parent,sample_page=sample_pages.get(parent),
                test_page=test_pages.get(row['id']) if row['sheet']=='检测结果' and parent else None,
                unassigned_page=test_pages.get(row['id']) if row['sheet']=='检测结果' and not parent else None)
    issues=[x for row in rows for x in row['issues']]
    summary=dict(sample_count=len(samples),test_count=len(tests),unassigned_test_count=sum(not x['sample_row_id'] for x in tests),
        error_count=sum(x['severity']=='ERROR' for x in issues),warning_count=sum(x['severity']=='WARNING' for x in issues),
        checked_sample_count=sum(x['parsed_values']['checked'] for x in samples),purpose=snapshot['purpose'],capture_channel='BULK',
        source_origin=('MIXED' if len({x['source_kind'] for x in snapshot['bindings']})>1 else
                       next(iter({x['source_kind'] for x in snapshot['bindings']}),'UNCONFIRMED')))
    return dict(rows=rows,file_issues=[],summary=summary,
        context=dict(format_version=1,catalog_fingerprint=hashlib.sha256(json.dumps(catalog,sort_keys=True,default=str).encode()).hexdigest(),
            type_settings=catalog['types'],methods=[m for m in catalog['methods'] if str(m['id']) in
                {t['parsed_values'].get('method_version_id') for t in tests}],
            asset_evidence=[dict(sample_row_id=s['id'],identity=s['parsed_values'].get('asset')) for s in samples]))


