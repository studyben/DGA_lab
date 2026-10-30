"""Store immutable laboratory finalization facts independently of report requests."""
from alembic import op

revision = '0033_lab_finalization_facts'
down_revision = '0032_device_material_import'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE laboratory_finalization_facts (
            oil_sample_id UUID NOT NULL REFERENCES oil_samples(id),
            finalization_token UUID NOT NULL,
            snapshot_schema_version SMALLINT NOT NULL CHECK(snapshot_schema_version IN (1,2)),
            physical_asset_id UUID,
            sampled_at TIMESTAMPTZ NOT NULL,
            fact_snapshot JSONB NOT NULL,
            legacy_report_id UUID,
            PRIMARY KEY(oil_sample_id,finalization_token),
            CHECK(snapshot_schema_version=1 OR (
                physical_asset_id IS NOT NULL
                AND jsonb_typeof(fact_snapshot)='object'
                AND fact_snapshot->'schema_version'='2'::jsonb
                AND fact_snapshot->'sample'->>'oil_sample_id'=oil_sample_id::text
                AND fact_snapshot->'sample'->>'formal_asset_id'=physical_asset_id::text
                AND fact_snapshot->'finalization'->>'token'=finalization_token::text
            ) IS TRUE)
        );
        CREATE INDEX laboratory_finalization_facts_asset
            ON laboratory_finalization_facts(physical_asset_id,sampled_at,oil_sample_id);
        INSERT INTO laboratory_finalization_facts
            (oil_sample_id,finalization_token,snapshot_schema_version,physical_asset_id,
             sampled_at,fact_snapshot,legacy_report_id)
        SELECT s.id,r.finalization_token,r.snapshot_schema_version,s.formal_asset_id,
               s.sampled_at,r.report_snapshot,r.id
        FROM oil_samples s JOIN laboratory_reports r ON r.oil_sample_id=s.id
            AND r.finalization_token=s.testing_finalization_token
        WHERE s.testing_status='FINALIZED' AND s.testing_finalization_token IS NOT NULL;
        CREATE FUNCTION guard_finalization_fact() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Laboratory finalization facts are immutable';
        END $$;
        CREATE TRIGGER laboratory_finalization_facts_immutable
            BEFORE UPDATE OR DELETE ON laboratory_finalization_facts
            FOR EACH ROW EXECUTE FUNCTION guard_finalization_fact();
    """)


def downgrade():
    op.execute("""
        DO $$ BEGIN
            IF EXISTS(SELECT 1 FROM laboratory_finalization_facts)
            THEN RAISE EXCEPTION 'Retained laboratory finalization facts require forward recovery'; END IF;
        END $$;
        DROP TABLE laboratory_finalization_facts;
        DROP FUNCTION guard_finalization_fact();
    """)

