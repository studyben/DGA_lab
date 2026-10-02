"""Revisioned site basics and retained asset-owned change evidence."""
from alembic import op

revision = '0027_site_basics'
down_revision = '0026_identity_management'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''ALTER TABLE sites ADD COLUMN revision integer NOT NULL DEFAULT 0;
        CREATE TABLE site_basic_events (
            id uuid PRIMARY KEY, site_id uuid NOT NULL REFERENCES sites(id),
            actor_id uuid NOT NULL REFERENCES users(id), occurred_at timestamptz NOT NULL,
            before_value jsonb NOT NULL, after_value jsonb NOT NULL
        );
        CREATE INDEX site_basic_events_site ON site_basic_events(site_id,occurred_at,id);
        CREATE FUNCTION forbid_site_basic_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Site change evidence is append only'; END $$;
        CREATE TRIGGER site_basic_events_append_only BEFORE UPDATE OR DELETE ON site_basic_events
            FOR EACH ROW EXECUTE FUNCTION forbid_site_basic_mutation();
    ''')


def downgrade():
    op.execute('''DO $$ BEGIN IF EXISTS (SELECT 1 FROM site_basic_events) THEN
        RAISE EXCEPTION 'Retained site changes require reviewed forward recovery'; END IF; END $$;
        DROP TABLE site_basic_events; DROP FUNCTION forbid_site_basic_mutation();
        ALTER TABLE sites DROP COLUMN revision;''')
