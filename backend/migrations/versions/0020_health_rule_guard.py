"""Enforce retained rule lifecycle without changing previously applied migration."""
from alembic import op

revision = '0020_health_rule_guard'
down_revision = '0019_health_rules'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE FUNCTION guard_health_rule() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Health rules cannot be deleted'; END IF;
      IF NEW.id<>OLD.id OR NEW.created_by<>OLD.created_by OR NEW.created_at<>OLD.created_at
        OR NEW.revision<>OLD.revision+1 THEN RAISE EXCEPTION 'Invalid rule revision'; END IF;
      IF OLD.state='RETIRED' THEN RAISE EXCEPTION 'Retired rule is immutable'; END IF;
      IF OLD.state='ACTIVE' THEN
        IF NEW.state<>'RETIRED' OR (to_jsonb(NEW)-'state'-'revision')<>(to_jsonb(OLD)-'state'-'revision')
          THEN RAISE EXCEPTION 'Active rule content is immutable'; END IF;
      ELSIF NEW.state='DRAFT' THEN
        IF NEW.approved_by IS NOT NULL OR NEW.approved_at IS NOT NULL
          THEN RAISE EXCEPTION 'Draft cannot have approval'; END IF;
      ELSIF NEW.state='ACTIVE' THEN
        IF (to_jsonb(NEW)-'state'-'revision'-'approved_by'-'approved_at')<>
           (to_jsonb(OLD)-'state'-'revision'-'approved_by'-'approved_at')
          THEN RAISE EXCEPTION 'Activation cannot change content'; END IF;
      ELSE RAISE EXCEPTION 'Invalid rule state transition'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER health_rule_guard BEFORE UPDATE OR DELETE ON health_rule_versions
      FOR EACH ROW EXECUTE FUNCTION guard_health_rule();
    """)


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM health_rule_versions)
      THEN RAISE EXCEPTION 'Retained rules prevent downgrade'; END IF; END $$;
      DROP TRIGGER health_rule_guard ON health_rule_versions;
      DROP FUNCTION guard_health_rule();""")
