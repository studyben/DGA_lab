"""One isolated public NO_REQUEST sample; never an import or acceptance-data seed."""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID
from sqlalchemy import create_engine, text
from dga.assets.public import AssetDirectory
from dga.laboratory.public import (
    SampleRegistry, ReceiveSample, SampleIdentityStatus, LaboratoryConfiguration, MethodVersionInput,
    FinalizationReportPolicy, LaboratoryWorkbench, LaboratoryReports, TestSubmission, TestType,
    MoistureResultInput, QualifiedMeasurement, ResultQualifier,
)
from dga.shared.auth.public import IdentityService, AuditTrail
from dga.shared.config import Settings
from dga.shared.files import UnavailableFileStore

ASSET = UUID('40000000-0000-0000-0000-000000000051')


def seed(engine, actor):
    url = engine.url
    if (url.host, url.database, url.username) != ('db', 'dga_browser', 'dga_browser'):
        raise RuntimeError('Finalization browser fixture requires isolated dga_browser database')
    with engine.begin() as c:
        existing = c.execute(text('SELECT barcode_value FROM oil_samples WHERE formal_asset_id=:id'), {'id': ASSET}).scalar_one_or_none()
        if existing:
            return existing
        c.execute(text("""INSERT INTO formal_assets
            (id,system_asset_number,asset_type,serial_number,model,lifecycle_status,product_line,machine_type)
            VALUES (:id,'SYS-TX-NOREQUEST-051','TRANSFORMER','TX-NOREQUEST-0051','Isolated TEST transformer','IN_SERVICE','PV','TRANSFORMER')"""), {'id': ASSET})
        c.execute(text("""INSERT INTO asset_installations
            (id,asset_id,parent_asset_id,site_id,valid_from)
            VALUES ('50000000-0000-0000-0000-000000000051',:id,NULL,
                    '20000000-0000-0000-0000-000000000001','2020-01-01T00:00:00Z')"""), {'id': ASSET})
    method = LaboratoryConfiguration(engine).create_method(actor, MethodVersionInput(
        test_type='MOISTURE', display_name='NO_REQUEST TEST method', version_label='NO-REQUEST-BROWSER-51',
        fields=[dict(code='MOISTURE', display_name='微水', unit_code='TEST-UNIT')]))
    at = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    sample = SampleRegistry(engine, AssetDirectory(engine), AuditTrail()).receive(actor, ReceiveSample(
        sampled_at=at, received_at=at, site_name='fixture', equipment_serial='fixture',
        notes='Isolated public NO_REQUEST browser evidence', container_count=1,
        identity_status=SampleIdentityStatus.ASSOCIATED, formal_asset_id=ASSET))
    # There is deliberately no file adapter/report request callback for this policy.
    files = UnavailableFileStore()
    audit = AuditTrail()
    bench = LaboratoryWorkbench(engine, SampleRegistry(engine, AssetDirectory(engine), audit), audit, files,
                                LaboratoryReports(engine, audit, files))
    bench.add_test(actor, sample.barcode_value, TestSubmission(
        TestType.MOISTURE, method['id'], at, None, None,
        MoistureResultInput(QualifiedMeasurement(ResultQualifier.EQ, Decimal('7.25')))))
    bench.finalize(actor, sample.barcode_value, report_policy=FinalizationReportPolicy.NO_REQUEST)
    return sample.barcode_value


def main():
    engine = create_engine(Settings().database_url.get_secret_value())
    try:
        if (engine.url.host, engine.url.database, engine.url.username) != ('db', 'dga_browser', 'dga_browser'):
            raise RuntimeError('Finalization browser fixture requires isolated dga_browser database')
        actor = IdentityService(engine).login('browser-admin', 'Browser changed passphrase 84!').actor
        print(seed(engine, actor))
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
