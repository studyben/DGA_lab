"""Immutable test package templates and per-sample plans."""
from alembic import op

revision = '0018_lab_packages'
down_revision = '0017_lab_instruments'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
      CREATE TABLE laboratory_packages (
        id UUID PRIMARY KEY, code VARCHAR(40) UNIQUE NOT NULL, name VARCHAR(120) NOT NULL,
        items JSONB NOT NULL, created_by UUID NOT NULL REFERENCES users(id),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
      );
      CREATE TRIGGER package_append_only BEFORE UPDATE OR DELETE ON laboratory_packages
        FOR EACH ROW EXECUTE FUNCTION forbid_audit_mutation();
      ALTER TABLE oil_samples ADD COLUMN package_snapshot JSONB;
      ALTER TABLE laboratory_operation_events DROP CONSTRAINT laboratory_operation_events_action_code_check;
      ALTER TABLE laboratory_operation_events ADD CONSTRAINT laboratory_operation_events_action_code_check
        CHECK (action_code IN ('SAMPLE_ASSET_ASSOCIATED','SAMPLE_CONTAINER_CHANGED','PACKAGE_APPLIED'));
    """)


def downgrade():
    op.execute("""
      DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM laboratory_packages) OR
           EXISTS (SELECT 1 FROM oil_samples WHERE package_snapshot IS NOT NULL)
        THEN RAISE EXCEPTION 'Retained package evidence prevents downgrade'; END IF;
      END $$;
      ALTER TABLE oil_samples DROP COLUMN package_snapshot;
      ALTER TABLE laboratory_operation_events DROP CONSTRAINT laboratory_operation_events_action_code_check;
      ALTER TABLE laboratory_operation_events ADD CONSTRAINT laboratory_operation_events_action_code_check
        CHECK (action_code IN ('SAMPLE_ASSET_ASSOCIATED','SAMPLE_CONTAINER_CHANGED'));
      DROP TABLE laboratory_packages;
    """)
