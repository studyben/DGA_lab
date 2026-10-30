"""Typed staging validation through public laboratory and upstream owner protocols."""
import pytest
from uuid import uuid4
from dga.assets.public import AssetDirectory, AssetQueryError
from dga.laboratory.public import LaboratoryConfiguration, MethodVersionInput
from tests.test_sample_reception import reception_context, TRANSFORMER_ID, WHOLE_UNIT_ID


def test_physical_asset_lookup_uses_exact_ids_without_current_installation_guess(database_url):
    engine,_,actor=reception_context(database_url)
    assets=AssetDirectory(engine)
    by_id=assets.lookup_physical_transformer(actor,asset_id=TRANSFORMER_ID)
    by_number=assets.lookup_physical_transformer(actor,system_asset_number='SYS-TX-002')
    assert by_id==by_number and by_id.id==TRANSFORMER_ID
    assert assets.lookup_physical_transformer(actor,asset_id=TRANSFORMER_ID,
        system_asset_number='SYS-TX-002')==by_id
    with pytest.raises(AssetQueryError,match='transformer_required'):
        assets.lookup_physical_transformer(actor,asset_id=WHOLE_UNIT_ID)
    with pytest.raises(AssetQueryError,match='asset_identity_conflict'):
        assets.lookup_physical_transformer(actor,asset_id=TRANSFORMER_ID,system_asset_number='SYS-PV-001')
    with pytest.raises(AssetQueryError,match='asset_not_found'):
        assets.lookup_physical_transformer(actor,asset_id=uuid4())
    engine.dispose()


def test_import_catalog_is_a_narrow_coherent_lab_write_read(database_url):
    engine,_,actor=reception_context(database_url)
    configuration=LaboratoryConfiguration(engine)
    method=configuration.create_method(actor,MethodVersionInput(test_type='MOISTURE',
        display_name='Supplied staging method',version_label='S2-CATALOG',
        fields=[dict(code='MOISTURE',display_name='Source reading',unit_code='TEST-UNIT',
            display_decimal_places=3,allowed_qualifiers=['EQ','ND'])]))
    catalog=configuration.import_catalog(actor)
    entry=next(x for x in catalog['methods'] if x['id']==str(method['id']))
    assert entry['configuration']['fields'][0]['unit_code']=='TEST-UNIT'
    assert entry['fields'][0]['code']=='MOISTURE'
    assert {x['code'] for x in catalog['types']}=={'DGA','MOISTURE','BREAKDOWN_VOLTAGE'}
    assert not {'instruments','calibrations','packages'} & set(catalog)
    with engine.begin() as c:
        assert configuration.import_catalog(actor,connection=c)==catalog
        assert not c.closed
    engine.dispose()



@pytest.mark.parametrize('format',['CSV_PAIR','XLSX'])
def test_real_public_pipeline_retains_complete_tests_dates_lexemes_and_source_evidence(database_url,format):
    from tests.laboratory_import_fixtures import setup,receive,queued
    engine,_,actor,imports,files,batch,sample,test,method=setup(database_url,format=format)
    receive(imports,actor,batch,[sample],[test|{'report_selected':'TRUE'},
        test|{'external_test_id':'T-0002','result_value':'0','report_selected':'FALSE'}])
    key=str(uuid4())
    queue=imports.validate(actor,batch['id'],idempotency_key=key,expected_revision=imports.get(actor,batch['id'])['revision'])
    assert imports.process_next('public-pipeline')
    detail=imports.get(actor,batch['id'])
    assert detail['validation_state']=='COMPLETE' and detail['validation_current']
    page=imports.samples(actor,batch['id'])
    assert page['total']==1 and page['unassigned_test_total']==0
    row=page['items'][0]
    assert row['raw_values']['external_sample_id']=='00017'
    assert row['raw_values']['source_note']==sample['source_note']
    assert row['parsed_values']['temporal']['sampled_at']['precision']=='DATE'
    assert row['parsed_values']['temporal']['sampled_at']['utc_instant'] is None
    expanded=imports.sample(actor,batch['id'],row['id'])
    assert expanded['tests']['total']==2
    tests=expanded['tests']['items']
    assert {x['external_test_id'] for x in tests}=={'T-0001','T-0002'}
    first=next(x for x in tests if x['external_test_id']=='T-0001')
    assert first['parsed_values']['measurements']['MOISTURE']['value']=='1.230000'
    assert first['parsed_values']['source_evidence']['source_analyst']=='Original source scientist'
    assert imports.operation(actor,key)['result']==queue['operation']['result']
    assert imports.samples(actor,batch['id'])['items'][0]['related_test_count']==2
    assert detail['summary']['sample_count']==1 and detail['summary']['test_count']==2
    assert 'object_key' not in str(page)
    engine.dispose()




@pytest.mark.parametrize('value,qualifier,unit,expected',[
    ('0','EQ','TEST-UNIT',None),('','ND','TEST-UNIT',None),('0','ND','TEST-UNIT','qualifier_value_conflict'),
    ('','EQ','TEST-UNIT','missing_required_value'),('0','','TEST-UNIT','qualifier_required'),
    ('0.0000001','EQ','TEST-UNIT','result_precision_exceeded'),('1e-1001','EQ','TEST-UNIT','invalid_decimal'),
    ('1e-1000','EQ','TEST-UNIT','result_precision_exceeded'),('1e12','EQ','TEST-UNIT','result_out_of_range'),
    ('-1','EQ','TEST-UNIT','result_out_of_range'),('NaN','EQ','TEST-UNIT','invalid_decimal'),
    ('1','LT','WRONG','unit_mismatch'),('1','GT','','unit_required'),
    ('101','EQ','TEST-UNIT','configured_range_exceeded')])
def test_public_decimal_qualifiers_and_approved_units_remain_distinct(database_url,value,qualifier,unit,expected):
    from tests.laboratory_import_fixtures import setup,receive,queued
    engine,_,actor,imports,_,batch,sample,test,_=setup(database_url)
    receive(imports,actor,batch,[sample],[test|dict(result_value=value,result_qualifier=qualifier,result_unit=unit)])
    queued(imports,actor,batch);assert imports.process_next('decimal-cases')
    sample_row=imports.samples(actor,batch['id'])['items'][0]
    row=imports.sample(actor,batch['id'],sample_row['id'])['tests']['items'][0]
    codes={i['code'] for i in row['issues']}
    if expected: assert expected in codes and not sample_row['parsed_values']['checked']
    else:
        assert not any(i['severity']=='ERROR' for i in row['issues'])
        parsed=row['parsed_values']['measurements']['MOISTURE']
        assert parsed['value']==(value if qualifier!='ND' else None)
        assert parsed['qualifier']==qualifier
    assert row['raw_values']['result_value']==value
    engine.dispose()


def test_complete_seven_gas_rows_are_one_test_and_orphans_are_fully_paged(database_url):
    from tests.laboratory_import_fixtures import setup,receive,queued
    engine,_,actor,imports,_,batch,sample,test,_=setup(database_url)
    configuration=LaboratoryConfiguration(engine)
    codes=['H2','CH4','C2H2','C2H4','C2H6','CO','CO2']
    method=configuration.create_method(actor,MethodVersionInput(test_type='DGA',display_name='Synthetic DGA',
        version_label='DGA-'+uuid4().hex[:12],fields=[dict(code=c,display_name=c,unit_code='TEST-UNIT',
            display_decimal_places=6) for c in codes]))
    dga={k:v for k,v in test.items() if not k.startswith('result_')}
    dga.update(test_type='DGA',method_version_id=str(method['id']))
    for c in codes: dga.update({c.lower()+'_value':'1.230000',c.lower()+'_qualifier':'EQ',c.lower()+'_unit':'TEST-UNIT'})
    dga.update(h2_value='0',ch4_value='',ch4_qualifier='ND')
    orphans=[test|dict(external_sample_id='unknown',external_test_id='ORPHAN-'+str(i)) for i in range(21)]
    receive(imports,actor,batch,[sample],[dga]+orphans)
    queued(imports,actor,batch);assert imports.process_next('whole-tests')
    sample_row=imports.samples(actor,batch['id'])['items'][0]
    expanded=imports.sample(actor,batch['id'],sample_row['id'])
    assert expanded['tests']['total']==1
    assert set(expanded['tests']['items'][0]['parsed_values']['measurements'])==set(codes)
    first=imports.unassigned_tests(actor,batch['id'])
    second=imports.unassigned_tests(actor,batch['id'],page=2)
    assert first['total']==second['total']==21
    assert len(first['items'])==20 and len(second['items'])==1
    assert {x['external_test_id'] for x in first['items']+second['items']}=={'ORPHAN-'+str(i) for i in range(21)}
    assert imports.get(actor,batch['id'])['summary']['test_count']==22
    engine.dispose()



def test_empty_business_files_complete_with_blocking_issue_and_no_partial_preview(database_url):
    from tests.laboratory_import_fixtures import setup,receive,queued
    engine,_,actor,imports,_,batch,_,_,_=setup(database_url)
    receive(imports,actor,batch,[],[]);queued(imports,actor,batch)
    assert imports.process_next('empty-business')
    assert imports.get(actor,batch['id'])['validation_state']=='COMPLETE'
    assert imports.samples(actor,batch['id'])['total']==0
    assert imports.unassigned_tests(actor,batch['id'])['total']==0
    assert {x['code'] for x in imports.issues(actor,batch['id'])['items']}=={'no_business_rows'}
    engine.dispose()



def test_issue_locator_reaches_twenty_first_related_test_without_identity_guess(database_url):
    from tests.laboratory_import_fixtures import setup,receive,queued
    engine,_,actor,imports,_,batch,sample,test,_=setup(database_url)
    tests=[test|dict(external_test_id='TEST-'+str(i).zfill(4),report_selected='TRUE' if i==0 else 'FALSE',
        result_unit='WRONG' if i==20 else 'TEST-UNIT') for i in range(21)]
    receive(imports,actor,batch,[sample],tests);queued(imports,actor,batch);imports.process_next('issue-locator')
    problem=imports.issues(actor,batch['id'],code='unit_mismatch')['items'][0]
    assert problem['sample_row_id']==imports.samples(actor,batch['id'])['items'][0]['id']
    assert problem['test_page']==2 and problem['external_test_id']=='TEST-0020'
    expanded=imports.sample(actor,batch['id'],problem['sample_row_id'],test_page=problem['test_page'])
    assert expanded['tests']['items'][0]['id']==problem['row_id']
    assert expanded['tests']['items'][0]['raw_values']['result_unit']=='WRONG'
    engine.dispose()


def test_same_revision_recheck_keeps_old_results_stale_until_current_complete(database_url):
    from tests.laboratory_import_fixtures import setup,receive,queued
    engine,_,actor,imports,_,batch,sample,test,method=setup(database_url)
    receive(imports,actor,batch,[sample],[test]);first=queued(imports,actor,batch);imports.process_next('first-result')
    before=imports.get(actor,batch['id'])
    fingerprint=before['current_job']['catalog_fingerprint']
    assert before['current_job']['validation_as_of']
    row_id=imports.samples(actor,batch['id'])['items'][0]['id']
    LaboratoryConfiguration(engine).set_method_active(actor,method['id'],False)
    queued(imports,actor,batch)
    old=imports.samples(actor,batch['id'])
    assert old['stale'] and not old['validation_current'] and old['items'][0]['stale']
    assert old['items'][0]['id']==row_id
    claim=imports.claim_validation('failed-recheck')
    assert imports.samples(actor,batch['id'])['stale']
    imports.fail_validation(claim,'storage_unavailable')
    assert imports.get(actor,batch['id'])['validation_state']=='FAILED'
    assert imports.samples(actor,batch['id'])['stale']
    queued(imports,actor,batch);imports.process_next('fresh-recheck')
    current=imports.get(actor,batch['id'])
    assert current['validation_current'] and not current['stale']
    assert current['current_job']['catalog_fingerprint']!=fingerprint
    assert imports.samples(actor,batch['id'])['items'][0]['id']==row_id
    assert imports.issues(actor,batch['id'],code='method_inactive')['total']==1
    assert first['operation']['result']['outcome']=='QUEUED'
    engine.dispose()



@pytest.mark.parametrize('format',['CSV_PAIR','XLSX'])
def test_exact_500_samples_2000_complete_tests_and_one_sample_all_pages(database_url,format):
    from tests.laboratory_import_fixtures import setup,receive,queued,dga_method,dga_row
    from dga.laboratory.public import LaboratoryOperations,SampleRegistry
    from dga.shared.auth.public import AuditTrail
    engine,_,actor,imports,_,batch,sample,test,_=setup(database_url,format=format)
    assets=AssetDirectory(engine)
    operations=LaboratoryOperations(engine,SampleRegistry(engine,assets,AuditTrail()),assets,AuditTrail())
    formal_before=operations.dashboard(actor)['metrics']
    method=dga_method(engine,actor)
    samples=[sample|dict(external_sample_id='00017' if i==0 else 'S-'+str(i).zfill(4),
        source_note='sample evidence '+str(i)) for i in range(500)]
    base=dga_row(test,method)
    tests=[base|dict(external_test_id='FULL-'+str(i).zfill(4),h2_value=str(i),
        source_note='test evidence '+str(i),report_selected='TRUE' if i==0 else 'FALSE') for i in range(2000)]
    receive(imports,actor,batch,samples,tests);queued(imports,actor,batch)
    assert imports.process_next('full-capacity')
    result=imports.get(actor,batch['id'])
    assert result['validation_state']=='COMPLETE' and result['validation_current']
    assert result['summary']['sample_count']==500 and result['summary']['test_count']==2000
    observed=[]
    for page in range(1,26):
        part=imports.samples(actor,batch['id'],page=page)
        assert part['total']==500 and len(part['items'])==20
        observed.extend(part['items'])
    assert len({x['id'] for x in observed})==500
    assert {x['external_sample_id'] for x in observed}=={x['external_sample_id'] for x in samples}
    first=next(x for x in observed if x['external_sample_id']=='00017')
    assert first['related_test_count']==2000
    all_tests=[]
    for page in range(1,101):
        part=imports.sample(actor,batch['id'],first['id'],test_page=page)['tests']
        assert part['total']==2000 and len(part['items'])==20
        all_tests.extend(part['items'])
    assert len({x['id'] for x in all_tests})==2000
    assert {x['external_test_id'] for x in all_tests}=={x['external_test_id'] for x in tests}
    for row in all_tests:
        index=int(row['external_test_id'].split('-')[1])
        assert row['raw_values']['source_note']=='test evidence '+str(index)
        values=row['parsed_values']['measurements']
        assert len(values)==7 and values['H2']['value']==str(index)
        assert values['CH4']['value']=='0.000001'
    assert imports.unassigned_tests(actor,batch['id'])['total']==0
    if format=='CSV_PAIR':
        last=all_tests[-1]
        imports.revise(actor,batch['id'],idempotency_key=str(uuid4()),expected_revision=result['revision'],
            reason='Review two rows at full capacity',changes=[dict(row_id=first['id'],values=dict(source_note='Reviewed capacity sample')),
                dict(row_id=last['id'],values=dict(source_note='Reviewed capacity test'))])
        queued(imports,actor,batch);assert imports.process_next('reviewed-full-capacity')
        assert imports.get(actor,batch['id'])['summary']['test_count']==2000
        after=imports.sample(actor,batch['id'],first['id'],test_page=100)['tests']
        assert after['total']==2000 and after['items'][-1]['id']==last['id']
        assert after['items'][-1]['parsed_values']['source_note']=='Reviewed capacity test'
        assert after['items'][-1]['raw_values']['source_note']==last['raw_values']['source_note']
    assert operations.dashboard(actor)['metrics']==formal_before
    engine.dispose()


@pytest.mark.parametrize('limit',['samples','tests'])
def test_capacity_plus_one_is_file_issue_without_partial_rows(database_url,limit):
    from tests.laboratory_import_fixtures import setup,receive,queued
    engine,_,actor,imports,_,batch,sample,test,_=setup(database_url)
    samples=[sample|dict(external_sample_id='S-'+str(i)) for i in range(501)] if limit=='samples' else [sample]
    tests=[test|dict(external_test_id='T-'+str(i)) for i in range(2001)] if limit=='tests' else [test]
    receive(imports,actor,batch,samples,tests);queued(imports,actor,batch)
    assert imports.process_next('too-many-rows')
    assert imports.get(actor,batch['id'])['validation_state']=='COMPLETE'
    assert imports.samples(actor,batch['id'])['total']==0
    assert imports.unassigned_tests(actor,batch['id'])['total']==0
    assert imports.issues(actor,batch['id'])['severity_counts']['ERROR']>=1
    engine.dispose()



@pytest.mark.parametrize('raw,zone,precision,expected',[
    ('2026-01-15','', 'DATE',None),
    ('2026-01-15T12:00:00-06:00','','INSTANT',None),
    ('2026-01-15T12:00:00','','UNRESOLVED','timezone_required'),
    ('2026-03-08T02:30:00','America/Chicago','UNRESOLVED','nonexistent_local_time'),
    ('2026-11-01T01:30:00','America/Chicago','UNRESOLVED','ambiguous_local_time'),
    ('2026-07-01T12:00:00-06:00','America/Chicago','UNRESOLVED','offset_timezone_conflict'),
    ('','', 'MISSING','date_required')])
def test_public_temporal_rows_do_not_invent_instants(database_url,raw,zone,precision,expected):
    from tests.laboratory_import_fixtures import setup,receive,queued
    engine,_,actor,imports,_,batch,sample,test,_=setup(database_url)
    receive(imports,actor,batch,[sample|dict(sampled_at=raw,sampled_timezone=zone)],[test])
    queued(imports,actor,batch);imports.process_next('temporal-public')
    row=imports.samples(actor,batch['id'])['items'][0]
    value=row['parsed_values']['temporal']['sampled_at']
    assert value['raw']==raw and value['precision']==precision
    if expected: assert expected in {x['code'] for x in row['issues']}
    if precision!='INSTANT': assert value['utc_instant'] is None
    if precision=='DATE': assert value['local_time'] is None
    assert row['raw_values']['sampled_at']==raw
    engine.dispose()


@pytest.mark.parametrize('confirmed',[False,True])
def test_only_explicit_confirmed_batch_zone_can_resolve_source_local_time(database_url,confirmed):
    from tests.laboratory_import_fixtures import setup,receive,queued
    engine,_,actor,imports,_,batch,sample,test,_=setup(database_url)
    imports.revise(actor,batch['id'],idempotency_key=str(uuid4()),expected_revision=0,
        reason='Explicit batch source-zone decision',metadata=dict(source_timezone='America/Chicago',
        source_timezone_confirmed=confirmed))
    receive(imports,actor,batch,[sample|dict(sampled_at='2026-01-15T12:00:00')],[test])
    queued(imports,actor,batch);imports.process_next('batch-zone')
    time=imports.samples(actor,batch['id'])['items'][0]['parsed_values']['temporal']['sampled_at']
    assert time['precision']==('INSTANT' if confirmed else 'UNRESOLVED')
    if confirmed: assert '18:00:00' in time['utc_instant']
    else: assert time['utc_instant'] is None
    engine.dispose()


def test_numeric_xlsx_ids_and_times_are_retained_without_guessing_text_or_midnight(database_url):
    from tests.laboratory_import_fixtures import setup,receive,queued
    engine,_,actor,imports,_,batch,sample,test,_=setup(database_url,format='XLSX')
    receive(imports,actor,batch,[sample|dict(external_sample_id=17,sampled_at=46000)],[test])
    queued(imports,actor,batch);imports.process_next('numeric-source')
    row=imports.samples(actor,batch['id'])['items'][0]
    assert row['raw_values']['external_sample_id']=='17'
    assert row['raw_cell_types']['external_sample_id']=='NUMBER'
    codes={x['code'] for x in row['issues']}
    assert {'identifier_requires_text','timestamp_requires_text'}<=codes
    assert row['external_sample_id'] is None
    assert row['parsed_values']['temporal']['sampled_at']['utc_instant'] is None
    assert imports.unassigned_tests(actor,batch['id'])['total']==1
    engine.dispose()


def test_cross_lab_same_external_numbers_stay_distinct_and_same_lab_alias_duplicates_are_ambiguous(database_url):
    from tests.laboratory_import_fixtures import setup,receive,queued
    engine,_,actor,imports,_,batch,sample,test,_=setup(database_url)
    name='Separate '+uuid4().hex
    candidate=imports.source_labs(actor,exact_name=name)
    imports.revise(actor,batch['id'],idempotency_key=str(uuid4()),expected_revision=0,reason='Distinct source lab',
        source_labs=[dict(key='LAB_B',decision='NEW',proposed_name=name,source_kind='IN_HOUSE',
        confirm_distinct=True,candidate_digest=candidate['candidate_digest'],reason='Confirmed different laboratory')])
    receive(imports,actor,batch,[sample,sample|dict(source_lab_key='LAB_B',source_lab_name=name)],
        [test,test|dict(source_lab_key='LAB_B')])
    queued(imports,actor,batch);imports.process_next('cross-lab')
    rows=imports.samples(actor,batch['id'])['items']
    assert len(rows)==2 and len({x['source_lab_id'] for x in rows})==2
    assert {x['external_sample_id'] for x in rows}=={'00017'}
    assert all(x['related_test_count']==1 for x in rows)
    assert imports.issues(actor,batch['id'],code='duplicate_sample_key')['total']==0
    assert imports.get(actor,batch['id'])['summary']['source_origin']=='MIXED'
    source=next(x for x in imports.get(actor,batch['id'])['source_labs'] if x['source_lab_key']=='LAB_A')['source_lab_id']
    imports.revise(actor,batch['id'],idempotency_key=str(uuid4()),
        expected_revision=imports.get(actor,batch['id'])['revision'],reason='Explicit reference is same stable source',
        source_labs=[dict(key='LAB_B',decision='REFERENCE',source_lab_id=source,reason='Confirmed identity reference')])
    queued(imports,actor,batch);imports.process_next('duplicate-stable-source')
    assert imports.unassigned_tests(actor,batch['id'])['total']==2
    assert imports.issues(actor,batch['id'],code='duplicate_sample_key')['total']==2
    assert imports.issues(actor,batch['id'],code='ambiguous_sample_reference')['total']==2
    engine.dispose()


def test_source_note_overlength_and_pdf_declarations_are_visible_not_truncated_or_provided(database_url):
    from tests.laboratory_import_fixtures import setup,receive,queued
    engine,_,actor,imports,_,batch,sample,test,_=setup(database_url)
    note='😀'*2001
    receive(imports,actor,batch,[sample|dict(source_note=note,report_filenames='["source.pdf"]')],[test])
    queued(imports,actor,batch);imports.process_next('source-evidence')
    row=imports.samples(actor,batch['id'])['items'][0]
    assert row['raw_values']['source_note']==row['reviewed_values']['source_note']==note
    assert row['parsed_values']['reports']==[dict(filename='source.pdf',state='DECLARED_NOT_PROVIDED')]
    problems=imports.issues(actor,batch['id'])
    assert {'field_length_exceeded','report_file_not_provided'}<={x['code'] for x in problems['items']}
    engine.dispose()



@pytest.mark.parametrize('database_url',['head'],indirect=True)
def test_lab_writer_without_asset_permission_can_validate_with_row_issue(database_url):
    from sqlalchemy import text
    from tests.identity_seed import seed_legacy_user
    from tests.test_sample_reception import INITIAL_PASSWORD,CHANGED_PASSWORD
    from tests.laboratory_import_fixtures import setup,receive,queued
    engine,identity,admin,imports,_,batch,sample,test,_=setup(database_url)
    # Isolated role fixture only: model an authorized lab writer without assets.read.
    with engine.begin() as c:
        c.execute(text("DELETE FROM role_permissions WHERE role_id=(SELECT id FROM roles WHERE role_code='analyst') AND permission_id=(SELECT id FROM permissions WHERE permission_code='assets.read')"))
    seed_legacy_user(database_url,'no-asset-reader','Lab writer only',INITIAL_PASSWORD,['analyst'])
    login=identity.login('no-asset-reader',INITIAL_PASSWORD)
    actor=identity.change_password(login.token,INITIAL_PASSWORD,CHANGED_PASSWORD).actor
    receive(imports,actor,batch,[sample],[test]);queued(imports,actor,batch);imports.process_next('lab-without-asset-read')
    assert imports.get(actor,batch['id'])['validation_current']
    assert 'asset_lookup_not_authorized' in {x['code'] for x in imports.issues(actor,batch['id'])['items']}
    assert imports.samples(actor,batch['id'])['total']==1
    engine.dispose()
