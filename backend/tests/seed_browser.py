"""Destructive fixture setup exclusively for the isolated browser-test database."""
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from dga.assets.public import AssetDirectory
from dga.laboratory.public import ReceiveSample, SampleIdentityStatus, SampleRegistry
from dga.shared.config import Settings
from dga.shared.auth.public import AuditTrail, IdentityService


def main():
    value = Settings().database_url.get_secret_value()
    url = make_url(value)
    if (url.host, url.database, url.username) != ('db', 'dga_browser', 'dga_browser'):
        raise RuntimeError('Browser fixtures require the dedicated dga_browser database')
    engine = create_engine(value)
    try:
        with engine.begin() as connection:
            connection.execute(text(
                'TRUNCATE oil_samples,asset_installations,formal_assets,sites,customers,'
                'auth_sessions,user_roles,audit_logs,users CASCADE'
            ))
            connection.execute(text("ALTER SEQUENCE oil_sample_number_seq RESTART WITH 1"))
        service = IdentityService(engine)
        initial = 'Browser initial passphrase 42!'
        changed = 'Browser changed passphrase 84!'
        service.bootstrap_admin('browser-admin', '测试管理员', initial)
        login = service.login('browser-admin', initial)
        admin = service.change_password(login.token, initial, changed)
        service.provision_user(admin.actor, 'first-login', '首次登录测试', initial, ['lab_admin'])
        service.provision_user(admin.actor, 'field-user', '现场工程师', initial, ['field_engineer'])
        field = service.login('field-user', initial)
        service.change_password(field.token, initial, changed)
        with engine.begin() as connection:
            connection.execute(text("""
                INSERT INTO customers(id,customer_name) VALUES
                ('10000000-0000-0000-0000-000000000001','Prairie Solar LLC');
                INSERT INTO sites(id,customer_id,site_name,location_text) VALUES
                ('20000000-0000-0000-0000-000000000001',
                 '10000000-0000-0000-0000-000000000001','Prairie Sun','Texas, USA');
                INSERT INTO formal_assets
                    (id,system_asset_number,asset_type,serial_number,model,material_number,lifecycle_status)
                VALUES
                ('30000000-0000-0000-0000-000000000001','SYS-PV-001','WHOLE_UNIT',
                 'INV-UNIT-7788','SG4400UD','MAT-UNIT-44','IN_SERVICE'),
                ('40000000-0000-0000-0000-000000000001','SYS-TX-001','TRANSFORMER',
                 'TX-OLD-1001','TX-4400','MAT-TX-40','RETIRED'),
                ('40000000-0000-0000-0000-000000000002','SYS-TX-002','TRANSFORMER',
                 'TX-CURRENT-2002','TX-4400','MAT-TX-41','IN_SERVICE');
                INSERT INTO asset_installations
                    (id,asset_id,parent_asset_id,site_id,valid_from,valid_to)
                VALUES
                ('50000000-0000-0000-0000-000000000001',
                 '30000000-0000-0000-0000-000000000001',NULL,
                 '20000000-0000-0000-0000-000000000001','2020-01-01T00:00:00Z',NULL),
                ('50000000-0000-0000-0000-000000000002',
                 '40000000-0000-0000-0000-000000000001',
                 '30000000-0000-0000-0000-000000000001',NULL,
                 '2020-01-01T00:00:00Z','2024-01-01T00:00:00Z'),
                ('50000000-0000-0000-0000-000000000003',
                 '40000000-0000-0000-0000-000000000002',
                 '30000000-0000-0000-0000-000000000001',NULL,
                 '2024-01-01T00:00:00Z',NULL);
            """))
        registry = SampleRegistry(engine, AssetDirectory(engine), AuditTrail())
        sample = registry.receive(
            admin.actor,
            ReceiveSample(
                sampled_at=datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
                received_at=datetime(2026, 8, 2, 9, 0, tzinfo=timezone.utc),
                site_name='ignored',
                equipment_serial='ignored',
                notes='浏览器验收样品',
                container_count=2,
                identity_status=SampleIdentityStatus.ASSOCIATED,
                formal_asset_id='40000000-0000-0000-0000-000000000002',
            ),
        )
        if sample.barcode_value != 'DGA-20260802-000001':
            raise RuntimeError('Unexpected browser sample barcode')
        report_sample = registry.receive(
            admin.actor,
            ReceiveSample(
                sampled_at=datetime(2026, 8, 1, 14, 0, tzinfo=timezone.utc),
                received_at=datetime(2026, 8, 2, 10, 0, tzinfo=timezone.utc),
                site_name='ignored',
                equipment_serial='ignored',
                notes='条码报告浏览器验收样品',
                container_count=1,
                identity_status=SampleIdentityStatus.ASSOCIATED,
                formal_asset_id='40000000-0000-0000-0000-000000000002',
            ),
        )
        if report_sample.barcode_value != 'DGA-20260802-000002':
            raise RuntimeError('Unexpected browser report sample barcode')
        service.logout(admin.token)
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
