"""Analysis-owned alarm episodes and immutable transition history."""
from alembic import op

revision = '0022_alarm_episodes'
down_revision = '0021_health_evaluations'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE alarm_generation(id integer PRIMARY KEY CHECK(id=1),version bigint NOT NULL);
      INSERT INTO alarm_generation VALUES(1,0);
      CREATE TABLE alarm_episodes(
        id uuid PRIMARY KEY,asset_id uuid NOT NULL REFERENCES formal_assets(id),
        test_type text NOT NULL,analyte text NOT NULL,
        state text NOT NULL CHECK(state IN ('UNACKNOWLEDGED','ACKNOWLEDGED','RESOLVED')),
        revision integer NOT NULL DEFAULT 0,opened_at timestamptz NOT NULL,
        superseded_by uuid REFERENCES alarm_episodes(id),data jsonb NOT NULL);
      CREATE UNIQUE INDEX alarm_one_open ON alarm_episodes(asset_id,test_type,analyte)
        WHERE state<>'RESOLVED' AND superseded_by IS NULL;
      CREATE TABLE alarm_events(id uuid PRIMARY KEY,episode_id uuid NOT NULL REFERENCES alarm_episodes(id),
        revision integer NOT NULL,occurred_at timestamptz NOT NULL,action text NOT NULL,
        actor_id uuid REFERENCES users(id),data jsonb NOT NULL,UNIQUE(episode_id,revision));
      CREATE TRIGGER alarm_events_immutable BEFORE UPDATE OR DELETE ON alarm_events
        FOR EACH ROW EXECUTE FUNCTION forbid_audit_mutation();
      CREATE TRIGGER alarm_no_delete BEFORE DELETE ON alarm_episodes
        FOR EACH ROW EXECUTE FUNCTION forbid_audit_mutation();''')


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM alarm_episodes)
      THEN RAISE EXCEPTION 'Retained alarms prevent downgrade'; END IF; END $$;
      DROP TABLE alarm_events,alarm_episodes,alarm_generation;""")
