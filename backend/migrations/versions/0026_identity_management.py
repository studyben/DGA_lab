"""Account revisions, credential origin and safe audit details."""
from alembic import op

revision = '0026_identity_management'
down_revision = '0025_identity_roles'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''ALTER TABLE users ADD COLUMN revision integer NOT NULL DEFAULT 0,
        ADD COLUMN credential_kind varchar(10) NOT NULL DEFAULT 'LEGACY'
            CHECK (credential_kind IN ('LEGACY','RECOVERY','NONE')),
        ALTER COLUMN password_hash DROP NOT NULL;
        UPDATE users u SET credential_kind='RECOVERY' WHERE EXISTS
            (SELECT 1 FROM user_roles ur JOIN roles r ON r.id=ur.role_id
             WHERE ur.user_id=u.id AND r.role_code='system_admin');
        ALTER TABLE users ADD CONSTRAINT user_credential_consistent CHECK
            ((credential_kind='NONE' AND password_hash IS NULL AND NOT must_change_password)
             OR (credential_kind IN ('LEGACY','RECOVERY') AND password_hash IS NOT NULL));
        ALTER TABLE audit_logs ADD COLUMN before_value jsonb, ADD COLUMN after_value jsonb;
    ''')


def downgrade():
    raise RuntimeError('Retained identity/audit data requires reviewed forward recovery')
