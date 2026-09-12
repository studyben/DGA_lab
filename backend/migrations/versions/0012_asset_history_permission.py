"""Separate historical correction authority from routine asset updates."""
from uuid import NAMESPACE_URL, uuid5
from alembic import op
from sqlalchemy import text

revision = '0012_asset_history_permission'
down_revision = '0011_asset_lifecycle'
branch_labels = None
depends_on = None


def upgrade():
    permission = uuid5(NAMESPACE_URL, 'dga:permission:assets.history.correct')
    op.get_bind().execute(text('INSERT INTO permissions(id,permission_code) VALUES (:id,\'assets.history.correct\')'), {'id': permission})
    op.get_bind().execute(text("INSERT INTO role_permissions(role_id,permission_id) SELECT id,:id FROM roles WHERE role_code='system_admin'"), {'id': permission})


def downgrade():
    op.execute("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE permission_code='assets.history.correct')")
    op.execute("DELETE FROM permissions WHERE permission_code='assets.history.correct'")
