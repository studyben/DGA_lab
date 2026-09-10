"""Official asset identity and time-bounded installation paths."""

from alembic import op


revision = "0003_official_assets"
down_revision = "0002_identity"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE customers (
            id UUID PRIMARY KEY,
            customer_name VARCHAR(200) NOT NULL
        );

        CREATE TABLE sites (
            id UUID PRIMARY KEY,
            customer_id UUID NOT NULL REFERENCES customers(id),
            site_name VARCHAR(200) NOT NULL,
            location_text VARCHAR(300)
        );
        CREATE INDEX sites_customer ON sites(customer_id);

        CREATE TABLE formal_assets (
            id UUID PRIMARY KEY,
            system_asset_number VARCHAR(80) UNIQUE NOT NULL,
            asset_type VARCHAR(40) NOT NULL
                CHECK (asset_type IN ('WHOLE_UNIT','TRANSFORMER')),
            serial_number VARCHAR(160) NOT NULL,
            model VARCHAR(120),
            material_number VARCHAR(120),
            lifecycle_status VARCHAR(30) NOT NULL
                CHECK (lifecycle_status IN
                    ('COMMISSIONING','IN_SERVICE','OUT_OF_SERVICE','RETIRED','MERGED'))
        );
        -- Serial numbers are deliberately not unique. Source systems can reuse them,
        -- and callers must disambiguate with the returned asset context.
        CREATE INDEX formal_assets_serial_ci ON formal_assets(lower(serial_number));

        CREATE TABLE asset_installations (
            id UUID PRIMARY KEY,
            asset_id UUID NOT NULL REFERENCES formal_assets(id),
            parent_asset_id UUID REFERENCES formal_assets(id),
            site_id UUID REFERENCES sites(id),
            valid_from TIMESTAMPTZ NOT NULL,
            valid_to TIMESTAMPTZ,
            CHECK ((parent_asset_id IS NULL) <> (site_id IS NULL)),
            CHECK (parent_asset_id IS NULL OR parent_asset_id <> asset_id),
            CHECK (valid_to IS NULL OR valid_to > valid_from)
        );
        CREATE INDEX asset_installations_history
            ON asset_installations(asset_id,valid_from,valid_to);
        CREATE INDEX asset_installations_parent_history
            ON asset_installations(parent_asset_id,valid_from,valid_to);
        CREATE UNIQUE INDEX asset_installations_one_current
            ON asset_installations(asset_id) WHERE valid_to IS NULL;
        """
    )


def downgrade():
    op.execute(
        "DROP TABLE asset_installations,formal_assets,sites,customers"
    )
