"""Retain derived health evidence, never mutable current-state pointers."""
from alembic import op
revision = '0021_health_evaluations'
down_revision = '0020_health_rule_guard'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE health_evaluations(
      id UUID PRIMARY KEY, subject_id UUID NOT NULL REFERENCES formal_assets(id),
      fingerprint VARCHAR(64) NOT NULL, evaluated_at TIMESTAMPTZ NOT NULL,
      evidence JSONB NOT NULL, UNIQUE(subject_id,fingerprint));
      CREATE TRIGGER health_evaluations_immutable BEFORE UPDATE OR DELETE ON health_evaluations
      FOR EACH ROW EXECUTE FUNCTION forbid_audit_mutation();''')


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM health_evaluations)
      THEN RAISE EXCEPTION 'Retained health evidence prevents downgrade'; END IF; END $$;
      DROP TABLE health_evaluations;""")
