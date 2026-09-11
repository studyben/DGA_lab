"""Additional browser-only equipment fixtures (not production asset import)."""
from sqlalchemy import text


def seed_equipment(engine):
    with engine.begin() as connection:
        connection.execute(text("""
            UPDATE formal_assets SET tag_number='ESS-01',commissioning_date='2020-06-01' WHERE system_asset_number='SYS-ESS-011';
            UPDATE formal_assets SET tag_number='PCS-01' WHERE system_asset_number='SYS-PCS-012';
            INSERT INTO formal_assets(id,system_asset_number,asset_type,serial_number,model,lifecycle_status,product_line,machine_type,power_mw,energy_mwh,tag_number,battery_manufacturer) VALUES
            ('30000000-0000-0000-0000-000000000013','SYS-BAT-013','WHOLE_UNIT','BAT-SERIAL-001','Battery demo','IN_SERVICE','ESS','BATTERY_CABINET',NULL,20,'BAT-01','示例电芯厂'),
            ('30000000-0000-0000-0000-000000000014','SYS-PCS-014','WHOLE_UNIT','PCS-SERIAL-001','PCS demo','IN_SERVICE','ESS','PCS',5,NULL,'PCS-BODY-01',NULL),
            ('30000000-0000-0000-0000-000000000015','SYS-MVT-015','TRANSFORMER','MVT-SERIAL-001','MVT demo','IN_SERVICE','ESS','TRANSFORMER',NULL,NULL,'MVT-01',NULL);
            INSERT INTO asset_installations VALUES
            ('50000000-0000-0000-0000-000000000013','30000000-0000-0000-0000-000000000013','30000000-0000-0000-0000-000000000011',NULL,'2020-01-01',NULL),
            ('50000000-0000-0000-0000-000000000014','30000000-0000-0000-0000-000000000014','30000000-0000-0000-0000-000000000012',NULL,'2020-01-01',NULL),
            ('50000000-0000-0000-0000-000000000015','30000000-0000-0000-0000-000000000015','30000000-0000-0000-0000-000000000012',NULL,'2020-01-01',NULL);
        """))
