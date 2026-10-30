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
    before=observations()
    assert sha256(before['pdf']).hexdigest()==case['pdf_sha256']
    command.upgrade(Config('alembic.ini'),'head')
    imports=LaboratoryImports(engine,files)
    candidate=imports.source_labs(actor,exact_name='Receipt source')
    batch=imports.create(actor,idempotency_key=str(uuid4()),input_format='CSV_PAIR',purpose='HISTORICAL',
        source_labs=[dict(key='SRC',decision='NEW',proposed_name='Receipt source',source_kind='THIRD_PARTY',
            reason='Explicit evidence source',confirm_distinct=True,candidate_digest=candidate['candidate_digest'])])['batch']
    for role in ('SAMPLES','TESTS'):
        imports.receive_file(actor,batch['id'],idempotency_key=str(uuid4()),role=role,
            filename=role.lower()+'.csv',content_type='text/csv',content=b'Unparsed retained evidence\n')
    imports.revise(actor,batch['id'],idempotency_key=str(uuid4()),expected_revision=2,
        reason='Purpose review only',metadata=dict(purpose='DAILY'))
    assert imports.get(actor,batch['id'])['manifest_state']=='COMPLETE'
    assert observations()==before
    assert reports.claim_next_report('receipt-non-effects',lease_seconds=60) is None
    with pytest.raises(DBAPIError,match='Retained laboratory imports require forward recovery'):
        command.downgrade(Config('alembic.ini'),'0033_lab_finalization_facts')
    assert imports.get(actor,batch['id'])['revision']==3
    assert bench.get_current_finalization(actor,case['barcode'])==before['facts']
    engine.dispose()


@pytest.mark.parametrize('database_url',['0033_lab_finalization_facts'],indirect=True)
def test_empty_0034_can_safely_downgrade_and_upgrade(database_url):
    command.upgrade(Config('alembic.ini'),'head')
    command.downgrade(Config('alembic.ini'),'0033_lab_finalization_facts')
    command.upgrade(Config('alembic.ini'),'head')

