"""Versioned laboratory configuration, instruments and calibration evidence."""
from alembic import op

revision = '0016_lab_configuration'
down_revision = '0015_lab_operations'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        INSERT INTO permissions(id,permission_code)
        VALUES ('14000000-0000-0000-0000-000000000001','laboratory.configure');
        INSERT INTO role_permissions(role_id,permission_id)
        SELECT id,'14000000-0000-0000-0000-000000000001' FROM roles
        WHERE role_code IN ('system_admin','lab_admin');
        CREATE TABLE laboratory_type_settings (
            code VARCHAR(30) PRIMARY KEY, display_name VARCHAR(100) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE
        );
        INSERT INTO laboratory_type_settings VALUES
            ('DGA','DGA',TRUE),('MOISTURE','微水',TRUE),('BREAKDOWN_VOLTAGE','击穿电压',TRUE);
        ALTER TABLE test_method_versions ADD COLUMN configuration JSONB,
            ADD COLUMN created_by UUID REFERENCES users(id),
            ADD COLUMN created_at TIMESTAMPTZ;
        CREATE FUNCTION guard_managed_method() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.configuration IS NOT NULL AND
               (to_jsonb(OLD) - 'is_active') IS DISTINCT FROM (to_jsonb(NEW) - 'is_active')
            THEN RAISE EXCEPTION 'Method content is immutable; create a new version'; END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER managed_method_immutable BEFORE UPDATE ON test_method_versions
            FOR EACH ROW EXECUTE FUNCTION guard_managed_method();
    """)


def downgrade():
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM test_method_versions WHERE configuration IS NOT NULL)
          THEN RAISE EXCEPTION 'Retained laboratory configuration prevents downgrade'; END IF;
        END $$;
        DROP TRIGGER managed_method_immutable ON test_method_versions;
        DROP FUNCTION guard_managed_method();
        ALTER TABLE test_method_versions DROP COLUMN configuration,
            DROP COLUMN created_by,DROP COLUMN created_at;
        DROP TABLE laboratory_type_settings;
        DELETE FROM role_permissions WHERE permission_id='14000000-0000-0000-0000-000000000001';
        DELETE FROM permissions WHERE id='14000000-0000-0000-0000-000000000001';
    """)
