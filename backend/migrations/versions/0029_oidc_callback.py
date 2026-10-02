"""Freeze the registered callback in each immutable OIDC candidate.

Existing candidates deliberately remain untestable until recreated: never infer
their tested callback from a mutable deployment default.
"""
from alembic import op

revision = '0029_oidc_callback'
down_revision = '0028_oidc'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE oidc_config_versions ADD COLUMN callback_url text')


def downgrade():
    raise RuntimeError('Retained identity/OIDC callback evidence requires reviewed forward recovery')
