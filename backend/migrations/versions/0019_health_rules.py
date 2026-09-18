"""Versioned health rules and retained assessment evidence; no scientific seeds."""
from alembic import op

revision = '0019_health_rules'
down_revision = '0018_lab_packages'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
      CREATE TABLE health_rule_versions (
        id UUID PRIMARY KEY, name VARCHAR(160) NOT NULL,
        test_type VARCHAR(30) NOT NULL CHECK(test_type IN ('DGA','MOISTURE','BREAKDOWN_VOLTAGE')),
        analyte VARCHAR(30) NOT NULL, method_version_id UUID NOT NULL REFERENCES test_method_versions(id),
        unit VARCHAR(40) NOT NULL, asset_id UUID REFERENCES formal_assets(id),
        priority INTEGER NOT NULL CHECK(priority BETWEEN 0 AND 1000),
        effective_from TIMESTAMPTZ NOT NULL, effective_to TIMESTAMPTZ,
        operator VARCHAR(2) NOT NULL CHECK(operator IN ('GT','GE','LT','LE')),
        threshold NUMERIC(18,6) NOT NULL CHECK(threshold>=0),
        severity VARCHAR(20) NOT NULL CHECK(severity IN ('ATTENTION','WARNING','CRITICAL')),
        state VARCHAR(10) NOT NULL DEFAULT 'DRAFT' CHECK(state IN ('DRAFT','ACTIVE','RETIRED')),
        revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0),
        created_by UUID NOT NULL REFERENCES users(id), created_at TIMESTAMPTZ NOT NULL,
        approved_by UUID REFERENCES users(id), approved_at TIMESTAMPTZ,
        CHECK(effective_to IS NULL OR effective_to>effective_from),
        CHECK(state='DRAFT' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL))
      );
      CREATE TABLE health_rule_events (
        id UUID PRIMARY KEY, rule_id UUID NOT NULL REFERENCES health_rule_versions(id),
        actor_id UUID NOT NULL REFERENCES users(id), action VARCHAR(20) NOT NULL,
        reason TEXT NOT NULL, occurred_at TIMESTAMPTZ NOT NULL, before_value JSONB, after_value JSONB NOT NULL
      );
      CREATE TRIGGER health_rule_events_immutable BEFORE UPDATE OR DELETE ON health_rule_events
        FOR EACH ROW EXECUTE FUNCTION forbid_audit_mutation();
    """)


def downgrade():
    op.execute("""
      DO $$ BEGIN IF EXISTS(SELECT 1 FROM health_rule_versions)
        THEN RAISE EXCEPTION 'Retained health evidence prevents downgrade'; END IF; END $$;
      DROP TABLE health_rule_events;
      DROP TABLE health_rule_versions;
    """)
