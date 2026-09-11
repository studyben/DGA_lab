from dataclasses import replace
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import text

import pytest
from dga.assets.public import AssetDirectory
from dga.laboratory.public import SampleRegistry
from dga.laboratory.public import ReceiveSample, SampleIdentityStatus, LaboratoryError
from dga.shared.auth.public import AuditTrail, IdentityError
from tests.test_laboratory_workbench import workbench_context, make_workbench, RecordingObjectStore, _dga, ASSET_ID
from tests.test_sample_reception import reception_context, WHOLE_UNIT_ID, TRANSFORMER_ID


def test_asset_reader_gets_laboratory_owned_summary_not_raw_results(workbench_context):
    engine, _, actor, sample = workbench_context
    # The shared test database may retain method deactivations from earlier suites.
    # Method administration is not implemented yet; prepare catalog fixture explicitly.
    with engine.begin() as connection:
        connection.execute(text("UPDATE test_method_versions SET is_active=true WHERE test_type='DGA'"))
    registry = SampleRegistry(engine, AssetDirectory(engine), AuditTrail())
    workbench = make_workbench(engine, RecordingObjectStore())
    method = next(m for m in workbench.load(actor, sample.barcode_value).methods if m.test_type == 'DGA')
    first = workbench.add_test(actor, sample.barcode_value, _dga(method.id))
    workbench.add_test(actor, sample.barcode_value, _dga(method.id))
    workbench.remove_test(actor, sample.barcode_value, first.id, reason='复测替代')
    reader = replace(actor, permissions=frozenset({'assets.read'}))
    result = registry.asset_test_history(reader, ASSET_ID)
    assert result['total'] == 1
    assert result['samples'][0]['barcode_value'] == sample.barcode_value
    assert result['samples'][0]['test_types'] == ['DGA']
    assert result['samples'][0]['test_count'] == 1
    assert 'result' not in result['samples'][0]
    assert registry.asset_test_history(reader, UUID(int=0))['total'] == 0
    assert registry.asset_test_history(reader, ASSET_ID, barcode='nonexistent')['total'] == 0
    with pytest.raises(IdentityError):
        registry.asset_test_history(replace(actor, permissions=frozenset()), ASSET_ID)


def test_historical_ancestry_survives_removal_and_duplicate_serials(database_url):
    engine, _, actor = reception_context(database_url)
    registry = SampleRegistry(engine, AssetDirectory(engine), AuditTrail())
    try:
        sample = registry.receive(actor, ReceiveSample(
            sampled_at=datetime(2025, 1, 1, tzinfo=timezone.utc), received_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            site_name='ignored', equipment_serial='ignored', notes=None, container_count=1,
            identity_status=SampleIdentityStatus.ASSOCIATED, formal_asset_id=TRANSFORMER_ID))
        with engine.begin() as c:
            c.execute(text("UPDATE asset_installations SET valid_to='2025-06-01' WHERE asset_id=:id"), {'id': TRANSFORMER_ID})
            c.execute(text("""INSERT INTO formal_assets(id,system_asset_number,asset_type,serial_number,lifecycle_status)
                VALUES (:id,'DUPLICATE','TRANSFORMER','TX-CURRENT-2002','IN_SERVICE')"""), {'id': UUID(int=123)})
        assert registry.asset_test_history(actor, WHOLE_UNIT_ID)['samples'][0]['barcode_value'] == sample.barcode_value
        assert registry.asset_test_history(actor, TRANSFORMER_ID)['total'] == 1
        assert registry.asset_test_history(actor, UUID(int=123))['total'] == 0
        assert registry.asset_test_history(actor, WHOLE_UNIT_ID, page=2, page_size=1)['samples'] == []
        assert registry.asset_test_history(actor, WHOLE_UNIT_ID, test_type='DGA')['total'] == 0
        with pytest.raises(LaboratoryError, match='invalid_asset_history_query'):
            registry.asset_test_history(actor, WHOLE_UNIT_ID, page=0)
    finally:
        engine.dispose()
