from datetime import datetime, timezone

from dga.assets.public import AssetDirectory
from dga.laboratory.public import LaboratoryOperations, LaboratoryWorkbench, SampleRegistry, ReceiveSample, SampleIdentityStatus, LaboratoryError
from dga.shared.auth.public import AuditTrail
from tests.test_sample_reception import reception_context
from tests.test_laboratory_workbench import make_workbench, RecordingObjectStore, _dga, TestType
import pytest
from dataclasses import replace
from fastapi.testclient import TestClient
from dga.main import create_app
from dga.shared.config import Settings
from tests.test_sample_reception import CHANGED_PASSWORD
from dga.laboratory.public import LaboratoryReports


def test_empty_dashboard_and_chicago_creation_day(database_url):
    engine, _, actor = reception_context(database_url)
    now = datetime(2026, 3, 8, 7, tzinfo=timezone.utc)  # Chicago01:00, DST change day
    registry = SampleRegistry(engine, AssetDirectory(engine), AuditTrail(), clock=lambda: now)
    ops = LaboratoryOperations(engine, registry, AssetDirectory(engine), AuditTrail(), clock=lambda: now)
    empty = ops.dashboard(actor)
    assert empty['metrics'] == dict(detecting_samples=0, tests_created_today=0, samples_created_today=0, samples_created_total=0)
    assert empty['business_date'] == '2026-03-08'
    registry.receive(actor, ReceiveSample(
        datetime(2025, 6, 1, tzinfo=timezone.utc), datetime(2025, 6, 2, tzinfo=timezone.utc),
        'handwritten site', 'pending serial', None, 1, SampleIdentityStatus.IDENTITY_PENDING,
    ))
    assert ops.dashboard(actor)['metrics'] == dict(detecting_samples=0, tests_created_today=0, samples_created_today=1, samples_created_total=1)
    engine.dispose()


@pytest.mark.parametrize('day,instants', [
    ('2026-03-08', ['2026-03-08T05:59:59+00:00','2026-03-08T06:00:00+00:00','2026-03-09T04:59:59+00:00','2026-03-09T05:00:00+00:00']),
    ('2026-11-01', ['2026-11-01T04:59:59+00:00','2026-11-01T05:00:00+00:00','2026-11-02T05:59:59+00:00','2026-11-02T06:00:00+00:00']),
])
def test_chicago_dst_days_count_created_records_even_if_removed(database_url, day, instants):
    engine, _, actor = reception_context(database_url)
    samples = []
    for instant in instants:
        clock = lambda: datetime.fromisoformat(instant)
        registry = SampleRegistry(engine, AssetDirectory(engine), AuditTrail(), clock=clock)
        sample = registry.receive(actor, ReceiveSample(datetime(2025,6,1,tzinfo=timezone.utc),datetime(2025,6,2,tzinfo=timezone.utc),'site','sn',None,1,SampleIdentityStatus.IDENTITY_PENDING))
        samples.append(sample)
        store = RecordingObjectStore()
        bench = LaboratoryWorkbench(engine, registry, AuditTrail(), store, LaboratoryReports(engine, AuditTrail(), store), clock=clock)
        method = next(m for m in bench.load(actor, sample.barcode_value).methods if m.test_type == TestType.DGA)
        record = bench.add_test(actor, sample.barcode_value, _dga(method.id))
        bench.remove_test(actor, sample.barcode_value, record.id, 'removed but performed')
    ops = LaboratoryOperations(engine, registry, AssetDirectory(engine), AuditTrail(), clock=lambda: datetime.fromisoformat(day+'T12:00:00+00:00'))
    assert ops.dashboard(actor)['metrics'] == dict(detecting_samples=0, tests_created_today=2, samples_created_today=2, samples_created_total=4)
    assert {r['id'] for r in ops.ledger(actor, start_date=day, end_date=day)['samples']} == {samples[1].id,samples[2].id}
    engine.dispose()


def test_operational_http_and_query_validation(database_url):
    engine, _, actor = reception_context(database_url)
    ops = LaboratoryOperations(engine, None, None, AuditTrail())
    for query in ({'sort':'x;drop table'}, {'page':0}, {'start_date':'2026-01-02','end_date':'2026-01-01'}, {'start_date':'9999-12-31'}):
        with pytest.raises(LaboratoryError):
            ops.ledger(actor, **query)
    with TestClient(create_app(Settings(database_url=database_url, cookie_secure=False, auth_allowed_origins='http://testserver'))) as client:
        assert client.get('/api/laboratory/dashboard').status_code == 401
        client.post('/api/auth/login', headers={'Origin':'http://testserver'}, json={'username':'reception-admin','password':CHANGED_PASSWORD})
        response = client.get('/api/laboratory/dashboard')
        assert response.status_code == 200
        assert response.headers['cache-control'] == 'no-store'
        assert client.get('/api/laboratory/ledger?state=IDENTITY_PENDING').json()['total'] == 0
    engine.dispose()


def test_ledger_combines_filters_paginates_and_counts_created_not_measured_tests(database_url):
    engine, _, actor = reception_context(database_url)
    now = datetime(2026, 11, 1, 7, tzinfo=timezone.utc)
    registry = SampleRegistry(engine, AssetDirectory(engine), AuditTrail(), clock=lambda: now)
    ops = LaboratoryOperations(engine, registry, AssetDirectory(engine), AuditTrail(), clock=lambda: now)
    samples = [registry.receive(actor, ReceiveSample(
        datetime(2025, 6, 1, tzinfo=timezone.utc), datetime(2025, 6, 2, tzinfo=timezone.utc),
        'Prairie site', f'SN-{i}', None, 1, SampleIdentityStatus.IDENTITY_PENDING,
    )) for i in range(3)]
    bench = make_workbench(engine, RecordingObjectStore())
    method = next(m for m in bench.load(actor, samples[0].barcode_value).methods if m.test_type == TestType.DGA)
    record = bench.add_test(actor, samples[0].barcode_value, _dga(method.id))
    result = ops.ledger(actor, site='prairie', serial='sn-', state='IDENTITY_PENDING', sort='sample_number', direction='asc', page_size=1, page=2)
    assert result['total'] == 3
    assert result['samples'][0]['barcode_value'] == samples[1].barcode_value
    filtered = ops.ledger(actor, test_type='DGA', start_date='2026-11-01', end_date='2026-11-01')
    assert [r['id'] for r in filtered['samples']] == [samples[0].id]
    assert ops.dashboard(actor)['metrics']['detecting_samples'] == 1
    bench.remove_test(actor, samples[0].barcode_value, record.id, 'invalid result')
    assert ops.ledger(actor, test_type='DGA')['total'] == 0
    assert ops.dashboard(actor)['metrics']['detecting_samples'] == 0
    engine.dispose()
