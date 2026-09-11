"""Official site capacities and dashboard classifications; unknowns stay null."""
from alembic import op

revision = '0009_asset_dashboard'
down_revision = '0005_laboratory_test_entry'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE sites
          ADD COLUMN grid_year INTEGER CHECK (grid_year BETWEEN 1900 AND 2200),
          ADD COLUMN grid_status VARCHAR(30) CHECK (grid_status IN ('NOT_STARTED','IN_PROGRESS','COMPLETED')),
          ADD COLUMN operation_status VARCHAR(30) CHECK (operation_status IN ('NOT_OPERATIONAL','PARTIAL','OPERATIONAL','DECOMMISSIONED')),
          ADD COLUMN commissioning_date DATE;
        CREATE TABLE site_product_lines (
          site_id UUID NOT NULL REFERENCES sites(id),
          product_line VARCHAR(3) NOT NULL CHECK (product_line IN ('PV','ESS')),
          power_mw NUMERIC(16,6) CHECK (power_mw >= 0),
          energy_mwh NUMERIC(16,6) CHECK (energy_mwh >= 0),
          PRIMARY KEY (site_id,product_line),
          CHECK (product_line = 'ESS' OR energy_mwh IS NULL)
        );
        ALTER TABLE formal_assets
          ADD COLUMN product_line VARCHAR(3) CHECK (product_line IN ('PV','ESS')),
          ADD COLUMN machine_type VARCHAR(40) CHECK (machine_type IN
            ('INVERTER_UNIT','INVERTER','ESS_SYSTEM','PCS_UNIT','PCS','BATTERY_CABINET','TRANSFORMER')),
          ADD COLUMN power_mw NUMERIC(16,6) CHECK (power_mw >= 0),
          ADD COLUMN energy_mwh NUMERIC(16,6) CHECK (energy_mwh >= 0),
          ADD CONSTRAINT asset_pv_energy CHECK (product_line IS DISTINCT FROM 'PV' OR energy_mwh IS NULL);
    """)


def downgrade():
    op.execute("""
        ALTER TABLE formal_assets DROP CONSTRAINT asset_pv_energy,
          DROP COLUMN product_line, DROP COLUMN machine_type,
          DROP COLUMN power_mw, DROP COLUMN energy_mwh;
        DROP TABLE site_product_lines;
        ALTER TABLE sites DROP COLUMN grid_year, DROP COLUMN grid_status,
          DROP COLUMN operation_status, DROP COLUMN commissioning_date;
    """)
