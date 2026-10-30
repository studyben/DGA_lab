"""Capture exact parent and historical v1 report producers on isolated PostgreSQL."""
import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from dga.assets.public import AssetDirectory
from dga.laboratory.public import (
    SampleRegistry, ReceiveSample, SampleIdentityStatus, LaboratoryReports, LaboratoryTrendSource,
    LaboratoryConfiguration, MethodVersionInput, BreakdownVoltageResultInput, MoistureResultInput,
    QualifiedMeasurement, ResultQualifier,
)
from dga.laboratory.report_worker import ReportWorker
from dga.shared.auth.public import AuditTrail
from tests.test_laboratory_workbench import (
    workbench_context, make_workbench, RecordingObjectStore, TestType, TestSubmission, _dga, _moisture,
)
PARENT = 'fcea999e313db51461cd9aefda66d70e6e34ed3b'
OLD = '71d8a9e23a4e2428937f604b8ef8e24c4fe272de'
OLD_BLOB = '12f2801b61df73b3d6e28003993a98653b2b0db7'
NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)
TABLES = (
    'customers', 'sites', 'formal_assets', 'asset_installations', 'test_method_versions',
    'test_method_fields', 'oil_samples', 'sample_containers', 'laboratory_tests',
    'dga_test_results', 'moisture_test_results', 'breakdown_voltage_test_results',
    'stored_objects', 'laboratory_test_attachments', 'laboratory_finalization_events', 'laboratory_reports',
)

def git(*args):
    root = Path(__file__).resolve().parents[2]
    return subprocess.check_output(['git', f'--work-tree={root}', *args], cwd=root)

def encoded(value):
    def default(item):
        return item.isoformat() if isinstance(item, datetime) else str(item)
    return json.dumps(value, default=default, ensure_ascii=False, sort_keys=True, indent=2)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--expected-parent', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.expected_parent != PARENT or git('diff', PARENT, '--', 'backend/dga/laboratory', 'backend/migrations').strip():
        raise RuntimeError('capture must precede producer/migration changes at approved parent')
    url = make_url(os.environ['TEST_DATABASE_URL'])
    if (url.host,url.database,url.username,url.port) != ('test-db','dga_test','dga_test',18551):
        raise RuntimeError('capture requires own18551 isolated database')
    if args.output.exists():
        raise RuntimeError('do not overwrite attested corpus')
    os.environ['DATABASE_URL'] = url.render_as_string(hide_password=False)
    probe = create_engine(url)
    with probe.connect() as c:
        assert c.execute(text('SELECT inet_server_port()')).scalar_one() == 18551
    probe.dispose()
    command.upgrade(Config('alembic.ini'), 'head')
    source = git('show', f'{OLD}:backend/dga/laboratory/reports.py')
    assert git('rev-parse', f'{OLD}:backend/dga/laboratory/reports.py').decode().strip() == OLD_BLOB
    cache = Path('../.cache/issue51-tests/old_reports_71d8a9e.py').resolve()
    cache.write_bytes(source)
    name = 'dga.laboratory._attested_legacy_reports'
    spec = importlib.util.spec_from_file_location(name, cache)
    old = importlib.util.module_from_spec(spec)
    sys.modules[name] = old
    spec.loader.exec_module(old)
    context = workbench_context.__wrapped__(os.environ['DATABASE_URL'])
    engine,identity,actor,initial = next(context)
    files = RecordingObjectStore()
    audit = AuditTrail(clock=lambda: NOW)
    reports = LaboratoryReports(engine,audit,files,clock=lambda: NOW)
    bench = make_workbench(engine,files,clock=lambda: NOW)
    registry = SampleRegistry(engine,AssetDirectory(engine),audit)
    methods = {m.test_type:m for m in bench.load(actor,initial.barcode_value).methods}
    config = LaboratoryConfiguration(engine)
    method = config.create_method(actor,MethodVersionInput(
        test_type='MOISTURE',display_name='Isolated capture method',version_label='CAPTURE-V1',
        fields=[dict(code='MOISTURE',display_name='微水',unit_code='TEST-UNIT',display_decimal_places=3)],
        qa_checks=[dict(code='BLANK',label='Isolated capture blank')]))
    cases = []
    sequence = 0
    def sample():
        nonlocal sequence
        sequence += 1
        return registry.receive(actor,ReceiveSample(
            sampled_at=datetime(2026,8,sequence,12,tzinfo=timezone.utc),
            received_at=datetime(2026,8,sequence,13,tzinfo=timezone.utc),
            site_name='ignored',equipment_serial='ignored',notes=f'Isolated corpus{sequence}',
            container_count=1,identity_status=SampleIdentityStatus.ASSOCIATED,formal_asset_id=initial.formal_asset_id))
    def finish(label,item,producer=reports,target='READY',active=bench):
        warnings = active.load(actor,item.barcode_value).finalization_assessment.warning_codes
        active.finalize(actor,item.barcode_value,warnings)
        if target == 'READY':
            assert ReportWorker(producer,files,clock=lambda: NOW).process_one('capture')
            assert reports.read_report_file(actor,item.barcode_value).content.startswith(b'%PDF')
        elif target == 'FAILED':
            claim = producer.claim_next_report('capture-failure',lease_seconds=30)
            producer.fail_report(claim,'isolated_capture_failure')
        with engine.connect() as c:
            row = dict(c.execute(text('SELECT * FROM laboratory_reports WHERE oil_sample_id=:id'),{'id':item.id}).mappings().one())
        case = dict(name=label,sample_id=str(item.id),barcode=item.barcode_value,caller_commit=PARENT,
            producer_commit=OLD if producer is not reports else PARENT,token=str(row['finalization_token']),
            report_snapshot=row['report_snapshot'],public_report=asdict(reports.get_report_by_barcode(actor,item.barcode_value)),
            selected_test_ids=[r['test_id'] for r in row['report_snapshot']['selected_results']])
        case['public_measurements'] = [asdict(p) for p in LaboratoryTrendSource(engine).finalized_measurements(actor,item.formal_asset_id) if p.sample_id==item.id]
        if row['object_key']:
            content = reports.read_report_file(actor,item.barcode_value).content
            case.update(object_key=row['object_key'],pdf_sha256=sha256(content).hexdigest(),pdf_size=len(content))
        cases.append(case)
        return case
    bench.add_test(actor,initial.barcode_value,_dga(methods[TestType.DGA].id))
    finish('parent_dga_ready',initial)
    item=sample()
    first=bench.add_test(actor,item.barcode_value,_moisture(method['id'],value='8.500'))
    bench.add_test(actor,item.barcode_value,_moisture(method['id'],value='9.500'))
    bench.select_report_result(actor,item.barcode_value,first.id)
    finish('parent_repeated_quality_ready',item)
    item=sample()
    bench.add_test(actor,item.barcode_value,_dga(methods[TestType.DGA].id,qualifier=ResultQualifier.ND))
    bench.add_test(actor,item.barcode_value,replace(_moisture(methods[TestType.MOISTURE].id),
        result=MoistureResultInput(QualifiedMeasurement(ResultQualifier.LT,Decimal('8.5')))))
    bench.add_test(actor,item.barcode_value,TestSubmission(TestType.BREAKDOWN_VOLTAGE,
        methods[TestType.BREAKDOWN_VOLTAGE].id,NOW,None,None,
        BreakdownVoltageResultInput(QualifiedMeasurement(ResultQualifier.GT,Decimal('80')))))
    finish('parent_mixed_qualified_ready',item)
    old_reports=old.LaboratoryReports(engine,audit,files,clock=lambda: NOW)
    old_bench=make_workbench(engine,files,report_lifecycle=old_reports,clock=lambda: NOW)
    item=sample()
    old_bench.add_test(actor,item.barcode_value,_moisture(methods[TestType.MOISTURE].id))
    finish('old71_placeholder_ready',item,producer=old_reports,active=old_bench)
    item=sample()
    bench.add_test(actor,item.barcode_value,_moisture(methods[TestType.MOISTURE].id))
    finish('parent_failed',item,target='FAILED')
    item=sample()
    record=bench.add_test(actor,item.barcode_value,_moisture(methods[TestType.MOISTURE].id))
    before=finish('parent_before_refinalization',item)
    bench.withdraw_finalization(actor,item.barcode_value,'Isolated attested correction')
    bench.update_test(actor,item.barcode_value,record.id,_moisture(methods[TestType.MOISTURE].id,value='12.500'))
    after=finish('parent_refinalized_ready',item)
    assert before['token'] != after['token']
    item=sample()
    bench.add_test(actor,item.barcode_value,_moisture(methods[TestType.MOISTURE].id))
    finish('parent_withdrawn',item)
    bench.withdraw_finalization(actor,item.barcode_value,'Isolated withdrawn fixture')
    cases[-1]['public_after_withdrawal']=asdict(reports.get_report_by_barcode(actor,item.barcode_value))
    item=sample()
    bench.add_test(actor,item.barcode_value,_moisture(methods[TestType.MOISTURE].id))
    finish('parent_queued',item,target='QUEUED')
    with engine.connect() as c:
        tables={table:c.execute(text(f'SELECT to_jsonb(t) FROM {table} t')).scalars().all() for table in TABLES}
    args.output.mkdir(parents=True)
    (args.output/'pdfs').mkdir()
    objects={}
    for key,content in files.objects.items():
        filename=f'pdfs/{sha256(content).hexdigest()}.pdf'
        (args.output/filename).write_bytes(content)
        objects[key]=filename
    payload=encoded(dict(actor=dict(id=str(actor.user_id),username=actor.username,display_name=actor.display_name),
                         cases=cases,tables=tables,objects=objects))
    (args.output/'cases.json').write_text(payload,encoding='utf-8')
    paths=['backend/dga/laboratory/'+p for p in ('reports.py','workbench.py','trends.py','report_pdf.py')]
    manifest=dict(schema=1,caller_commit=PARENT,historical_producer_commit=OLD,historical_reports_blob=OLD_BLOB,
        clock=NOW.isoformat(),migration_head='0032_device_material_import',
        parent_blobs={p:git('rev-parse',f'{PARENT}:{p}').decode().strip() for p in paths},
        command='python -m tests.capture_finalization_legacy --expected-parent '+PARENT+' --output tests/fixtures/finalization_legacy/v1',
        cases_text_sha256=sha256(payload.encode()).hexdigest(), captured_cases_file_sha256=sha256((args.output/'cases.json').read_bytes()).hexdigest(), case_count=len(cases),
        pdfs={p.name:sha256(p.read_bytes()).hexdigest() for p in (args.output/'pdfs').iterdir()},
        hash_definition='Text digest is UTF8 after LF normalization; captured raw-byte digest is provenance, not checkout equality. PDF byte digests are exact.',
        qualification='Actual identified producers. Withdrawn and pre-refinalization cases are historical observations, not current facts.')
    (args.output/'manifest.json').write_text(encoded(manifest),encoding='utf-8')
    print(encoded(dict(cases=len(cases),pdfs=len(objects),cases_text_sha256=manifest['cases_text_sha256'], captured_cases_file_sha256=manifest['captured_cases_file_sha256'],producer_source_unchanged=True,output=str(args.output.resolve()))))
    context.close()
if __name__ == '__main__':
    main()


