"""Oil sample reception, immutable identity snapshots and shared barcodes."""

from alembic import op


revision = "0004_laboratory_reception"
down_revision = "0003_official_assets"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE SEQUENCE oil_sample_number_seq;

        CREATE TABLE oil_samples (
            id UUID PRIMARY KEY,
            sample_number VARCHAR(40) UNIQUE NOT NULL,
            barcode_value VARCHAR(40) UNIQUE NOT NULL,
            identity_status VARCHAR(30) NOT NULL
                CHECK (identity_status IN ('ASSOCIATED','IDENTITY_PENDING')),
            sampled_at TIMESTAMPTZ NOT NULL,
            received_at TIMESTAMPTZ NOT NULL,
            site_name VARCHAR(200) NOT NULL,
            equipment_serial VARCHAR(160) NOT NULL,
            notes VARCHAR(2000),
            formal_asset_id UUID,
            asset_snapshot JSONB,
            created_by UUID NOT NULL REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL,
            CHECK (received_at >= sampled_at),
            CHECK (
                (identity_status = 'ASSOCIATED'
                    AND formal_asset_id IS NOT NULL AND asset_snapshot IS NOT NULL)
                OR
                (identity_status = 'IDENTITY_PENDING'
                    AND formal_asset_id IS NULL AND asset_snapshot IS NULL)
            )
        );
        CREATE INDEX oil_samples_identity_status ON oil_samples(identity_status,received_at);
        CREATE INDEX oil_samples_formal_asset ON oil_samples(formal_asset_id)
            WHERE formal_asset_id IS NOT NULL;

        CREATE TABLE sample_containers (
            id UUID PRIMARY KEY,
            oil_sample_id UUID NOT NULL REFERENCES oil_samples(id),
            container_number VARCHAR(50) UNIQUE NOT NULL,
            ordinal SMALLINT NOT NULL CHECK (ordinal > 0),
            UNIQUE (oil_sample_id,ordinal)
        );
        CREATE INDEX sample_containers_sample ON sample_containers(oil_sample_id,ordinal);
        """
    )


def downgrade():
    op.execute("DROP TABLE sample_containers,oil_samples; DROP SEQUENCE oil_sample_number_seq")
