"""Add audited identity confirmation and physical container lifecycle."""
from alembic import op

revision = '0015_lab_operations'
down_revision = '0014_merge_laboratory'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE oil_samples ADD operations_revision INTEGER NOT NULL DEFAULT 0 CHECK (operations_revision>=0);
        ALTER TABLE sample_containers ADD status VARCHAR(20) NOT NULL DEFAULT 'RECEIVED'
          CHECK (status IN ('RECEIVED','IN_USE','RETAINED','EXHAUSTED','BROKEN','DISPOSED'));
        ALTER TABLE sample_containers ADD revision INTEGER NOT NULL DEFAULT 0 CHECK (revision>=0);
        CREATE TABLE laboratory_operation_events (
          id UUID PRIMARY KEY,
          oil_sample_id UUID NOT NULL REFERENCES oil_samples(id),
          container_id UUID REFERENCES sample_containers(id),
          action_code VARCHAR(40) NOT NULL CHECK (action_code IN ('SAMPLE_ASSET_ASSOCIATED','SAMPLE_CONTAINER_CHANGED')),
          reason VARCHAR(500) NOT NULL CHECK(length(btrim(reason))>0),
          actor_id UUID NOT NULL REFERENCES users(id),
          occurred_at TIMESTAMPTZ NOT NULL,
          before_value JSONB NOT NULL,
          after_value JSONB NOT NULL,
          CHECK ((action_code='SAMPLE_CONTAINER_CHANGED')=(container_id IS NOT NULL))
        );
        CREATE TRIGGER laboratory_operations_immutable BEFORE UPDATE OR DELETE
          ON laboratory_operation_events FOR EACH ROW EXECUTE FUNCTION forbid_audit_mutation();
        CREATE INDEX laboratory_operations_sample ON laboratory_operation_events(oil_sample_id,occurred_at,id);
        CREATE INDEX oil_samples_created ON oil_samples(created_at,id);
        CREATE INDEX laboratory_tests_created ON laboratory_tests(created_at);
    """)


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM laboratory_operation_events) THEN
      RAISE EXCEPTION 'Retained laboratory operation history requires explicit archival before downgrade';
      END IF; END $$;
      DROP TABLE laboratory_operation_events;
      DROP INDEX oil_samples_created;
      DROP INDEX laboratory_tests_created;
      ALTER TABLE sample_containers DROP status, DROP revision;
      ALTER TABLE oil_samples DROP operations_revision;
    """)
