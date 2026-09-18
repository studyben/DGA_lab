"""Avoid advancing alarm generation for unchanged read-through observations."""
from alembic import op
revision = '0024_alarm_observation'
down_revision = '0023_alarm_acknowledgement'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE alarm_generation ADD COLUMN fingerprint text')


def downgrade():
    op.execute('ALTER TABLE alarm_generation DROP COLUMN fingerprint')
