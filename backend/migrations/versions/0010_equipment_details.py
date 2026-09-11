"""Optional equipment presentation fields; legacy unknown values stay null."""
from alembic import op

revision = '0010_equipment_details'
down_revision = '0009_asset_dashboard'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''ALTER TABLE formal_assets
        ADD COLUMN equipment_name VARCHAR(200),
        ADD COLUMN tag_number VARCHAR(160),
        ADD COLUMN commissioning_date DATE,
        ADD COLUMN battery_manufacturer VARCHAR(200)''')


def downgrade():
    op.execute('''ALTER TABLE formal_assets DROP COLUMN battery_manufacturer,
        DROP COLUMN commissioning_date, DROP COLUMN tag_number, DROP COLUMN equipment_name''')
