"""Separate operational acknowledgement from scientific rule write permission."""
from uuid import NAMESPACE_URL, uuid5
from alembic import op
from sqlalchemy import text
revision = '0023_alarm_acknowledgement'
down_revision = '0022_alarm_episodes'
branch_labels = None
depends_on = None


def upgrade():
    identifier = uuid5(NAMESPACE_URL, 'dga:permission:analysis.acknowledge')
    c = op.get_bind()
    c.execute(text('INSERT INTO permissions(id,permission_code) VALUES(:id,:code)'),dict(id=identifier,code='analysis.acknowledge'))
    c.execute(text("INSERT INTO role_permissions(role_id,permission_id) SELECT id,:permission FROM roles WHERE role_code IN ('system_admin','asset_manager','lab_admin','analyst','field_engineer')"),{'permission':identifier})


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM alarm_episodes)
      THEN RAISE EXCEPTION 'Retained alarms prevent downgrade'; END IF; END $$;
      DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE permission_code='analysis.acknowledge');
      DELETE FROM permissions WHERE permission_code='analysis.acknowledge';""")
