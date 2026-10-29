"""Optional structured metadata on existing append-only audit events."""
from alembic import op

revision = '0025_site_export_audit'
down_revision = '0024_alarm_observation'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE audit_logs ADD COLUMN details JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(details)='object')")


def downgrade():
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM audit_logs WHERE details <> '{}'::jsonb) THEN
            RAISE EXCEPTION 'Retained audit metadata requires explicit archival before downgrade';
        END IF;
    END $$""")
    op.execute('ALTER TABLE audit_logs DROP COLUMN details')
