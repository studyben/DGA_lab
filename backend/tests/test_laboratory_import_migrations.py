"""Additive0034 migration and public formal non-effects in an isolated historical schema."""
from hashlib import sha256
from uuid import UUID, uuid4
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.exc import DBAPIError
from dga.assets.public import AssetDirectory
from dga.laboratory.public import (LaboratoryImports, LaboratoryReports, LaboratoryOperations,
    LaboratoryTrendSource, SampleRegistry)
from dga.shared.auth.public import AuditTrail
from tests.finalization_legacy import load_case
from tests.test_laboratory_workbench import make_workbench, RecordingObjectStore
from tests.test_device_health import health
from tests.test_alarm_center import center


@pytest.mark.parametrize('database_url',['0032_device_material_import'],indirect=True)
def test_0034_preserves_0033_facts_pdf_and_all_formal_public_queries(database_url):
    engine=create_engine(database_url)
    files=RecordingObjectStore()
    case,actor=load_case(engine,'parent_repeated_quality_ready',files)
    command.upgrade(Config('alembic.ini'),'0033_lab_finalization_facts')
    asset_id=UUID(case['public_measurements'][0]['asset_id'])
    assets=AssetDirectory(engine)
    registry=SampleRegistry(engine,assets,AuditTrail())
    operations=LaboratoryOperations(engine,registry,assets,AuditTrail())
    bench=make_workbench(engine,files)
    reports=LaboratoryReports(engine,AuditTrail(),files)
    def observations():
        # Health/alarm queries legitimately persist evaluation evidence. Compare business
        # meaning, not newly allocated evaluation IDs, and warm before staging.
        h=health(engine).query(actor,asset_id)
        return dict(sample=registry.find_by_barcode(actor,case['barcode']),
            ledger=operations.dashboard(actor)['metrics'],
            tests=registry.asset_test_history(actor,asset_id),
            workbench=bench.load(actor,case['barcode']),
            facts=bench.get_current_finalization(actor,case['barcode']),
            pdf=reports.read_report_file(actor,case['barcode']).content,
            report=reports.get_report_by_barcode(actor,case['barcode']),
            assets=assets.equipment_detail(actor,asset_id),
            dashboard=assets.dashboard(actor),
            measurements=LaboratoryTrendSource(engine).finalized_measurements(actor,asset_id),
            health={k:h[k] for k in ('status','incomplete','sources','own','descendants')},
            alarms=center(engine).query(actor)['items'])
    from dga.laboratory.public import LaboratoryConfiguration,MethodVersionInput
    from tests.laboratory_import_fixtures import receive,queued,csv_bytes,SAMPLES,TESTS
    method=LaboratoryConfiguration(engine).create_method(actor,MethodVersionInput(test_type='MOISTURE',
        display_name='Explicit isolated staging method',version_label='non-effects-'+uuid4().hex[:10],
        fields=[dict(code='MOISTURE',display_name='Synthetic field',unit_code='TEST-UNIT',display_decimal_places=6)]))
    before=observations()
    assert sha256(before['pdf']).hexdigest()==case['pdf_sha256']
    command.upgrade(Config('alembic.ini'),'head')
    imports=LaboratoryImports(engine,files)
    candidate=imports.source_labs(actor,exact_name='Receipt source')
    batch=imports.create(actor,idempotency_key=str(uuid4()),input_format='CSV_PAIR',purpose='HISTORICAL',
        source_labs=[dict(key='SRC',decision='NEW',proposed_name='Receipt source',source_kind='THIRD_PARTY',
            reason='Explicit evidence source',confirm_distinct=True,candidate_digest=candidate['candidate_digest'])])['batch']
    sample=dict(source_lab_key='SRC',source_lab_name='Receipt source',external_sample_id='00017',
        formal_asset_id=str(asset_id),sampled_at='2026-01-15',physical_received='FALSE',container_count='0',
        sampling_context='OTHER',source_note='Original source evidence')
    test=dict(source_lab_key='SRC',external_sample_id='00017',external_test_id='T-00017',test_type='MOISTURE',
        measured_at='2026-01-16',method_version_id=str(method['id']),result_value='1.230000',
        result_qualifier='EQ',result_unit='TEST-UNIT',source_method='Supplied',source_analyst='External analyst')
    originals=receive(imports,actor,batch,[sample],[test])
    queued(imports,actor,batch);assert imports.process_next('known-formal-baseline')
    row=imports.samples(actor,batch['id'])['items'][0]
    assert row['related_test_count']==1 and imports.get(actor,batch['id'])['validation_current']
    imports.revise(actor,batch['id'],idempotency_key=str(uuid4()),expected_revision=2,
        reason='Review staging only',changes=[dict(row_id=row['id'],values=dict(source_note='Reviewed source evidence'))])
    queued(imports,actor,batch);assert imports.process_next('revised-formal-baseline')
    assert imports.samples(actor,batch['id'])['items'][0]['parsed_values']['source_note']=='Reviewed source evidence'
    assert observations()==before
    # Invalid replacement yields only a complete blocking file issue, retaining originals.
    invalid=imports.receive_file(actor,batch['id'],idempotency_key=str(uuid4()),role='TESTS',
        filename='invalid.csv',content_type='text/csv',content=b'not,the,required,header\n')
    imports.revise(actor,batch['id'],idempotency_key=str(uuid4()),expected_revision=4,
        reason='Explicit invalid source selection',active_files=dict(TESTS=invalid['file']['id']))
    queued(imports,actor,batch);assert imports.process_next('invalid-formal-baseline')
    assert imports.get(actor,batch['id'])['current_job']['state']=='COMPLETE'
    assert imports.samples(actor,batch['id'])['total']==0 and imports.issues(actor,batch['id'])['total']>=1
    assert observations()==before
    # Real provider-byte mismatch is an infrastructure failure, never a partial result.
    selected=originals[0]['file'];object_key=f"lab-imports/{batch['id']}/{selected['id']}/source"
    retained=files.get(object_key=object_key);files.put(object_key=object_key,content=b'wrong bytes',content_type='text/csv')
    queued(imports,actor,batch);assert imports.process_next('failed-formal-baseline')
    assert imports.get(actor,batch['id'])['current_job']['state']=='FAILED'
    files.put(object_key=object_key,content=retained,content_type='text/csv')
    assert observations()==before
    assert imports.original(actor,batch['id'],selected['id'])['content']==retained
    assert reports.claim_next_report('staging-non-effects',lease_seconds=60) is None
    with pytest.raises(DBAPIError,match='Retained laboratory imports require forward recovery'):
        command.downgrade(Config('alembic.ini'),'0033_lab_finalization_facts')
    assert imports.get(actor,batch['id'])['revision']==5
    assert bench.get_current_finalization(actor,case['barcode'])==before['facts']
    engine.dispose()


@pytest.mark.parametrize('database_url',['0033_lab_finalization_facts'],indirect=True)
def test_empty_0034_can_safely_downgrade_and_upgrade(database_url):
    command.upgrade(Config('alembic.ini'),'head')
    command.downgrade(Config('alembic.ini'),'0033_lab_finalization_facts')
    command.upgrade(Config('alembic.ini'),'head')

