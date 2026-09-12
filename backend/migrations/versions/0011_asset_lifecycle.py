"""Effective asset lifecycle changes and immutable audit evidence."""
from alembic import op

revision = '0011_asset_lifecycle'
down_revision = '0010_equipment_details'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''
        ALTER TABLE formal_assets ADD COLUMN lifecycle_revision INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE formal_assets DROP CONSTRAINT formal_assets_lifecycle_status_check;
        ALTER TABLE formal_assets ADD CHECK (lifecycle_status IN
            ('COMMISSIONING','IN_SERVICE','OUT_OF_SERVICE','RETIRED','MERGED','UNDER_REPAIR','SPARE'));
        ALTER TABLE asset_installations ADD COLUMN repair_center BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE asset_installations DROP CONSTRAINT asset_installations_check;
        ALTER TABLE asset_installations ADD CONSTRAINT asset_location_target CHECK
            ((parent_asset_id IS NOT NULL)::integer + (site_id IS NOT NULL)::integer + repair_center::integer = 1);
        CREATE TABLE asset_lifecycle_events (
            id UUID PRIMARY KEY,
            asset_id UUID NOT NULL REFERENCES formal_assets(id),
            related_asset_id UUID REFERENCES formal_assets(id),
            action VARCHAR(40) NOT NULL,
            effective_at TIMESTAMPTZ NOT NULL,
            occurred_at TIMESTAMPTZ NOT NULL,
            actor_id UUID NOT NULL REFERENCES users(id),
            reason VARCHAR(1000) NOT NULL CHECK (length(trim(reason)) > 0),
            before_value JSONB NOT NULL,
            after_value JSONB NOT NULL
        );
        CREATE INDEX asset_lifecycle_event_history ON asset_lifecycle_events(asset_id,effective_at);
        CREATE TRIGGER asset_events_append_only BEFORE UPDATE OR DELETE ON asset_lifecycle_events
            FOR EACH ROW EXECUTE FUNCTION forbid_audit_mutation();
    ''')


def downgrade():
    # Deliberately refuse destructive loss of lifecycle/audit history.
    raise RuntimeError('Restore a reviewed backup to downgrade asset lifecycle history')
