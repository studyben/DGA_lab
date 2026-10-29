"""Add retained, versioned customer/site import without reinterpreting v1 rows."""
from alembic import op
revision = '0031_site_import'
down_revision = '0030_merge_export_identity'
branch_labels = None
depends_on = None

def upgrade():
    op.execute("""
    ALTER TABLE asset_import_batches ADD COLUMN format_version integer NOT NULL DEFAULT 1,
        ADD COLUMN mode text NOT NULL DEFAULT 'ASSETS', ADD COLUMN working_rows jsonb,
        ADD COLUMN catalog_digest text;
    ALTER TABLE sites ADD COLUMN source_note text CHECK (length(source_note)<=2000);
    CREATE TABLE asset_import_operations (
        actor_id uuid NOT NULL REFERENCES users(id), operation_key uuid NOT NULL,
        action text NOT NULL, request_digest text NOT NULL,
        batch_id uuid NOT NULL REFERENCES asset_import_batches(id), result jsonb NOT NULL,
        PRIMARY KEY(actor_id,operation_key));
    CREATE TABLE asset_import_revisions (
        id uuid PRIMARY KEY, batch_id uuid NOT NULL REFERENCES asset_import_batches(id),
        revision integer NOT NULL, actor_id uuid NOT NULL REFERENCES users(id),
        occurred_at timestamptz NOT NULL, reason text NOT NULL,
        before_value jsonb NOT NULL, after_value jsonb NOT NULL);
    CREATE TABLE asset_import_sources (
        id uuid PRIMARY KEY, batch_id uuid NOT NULL REFERENCES asset_import_batches(id),
        kind text NOT NULL CHECK(kind IN ('SITE','CUSTOMER')), target_id uuid NOT NULL,
        sheet text NOT NULL, row_number integer NOT NULL, source_note text,
        original_values jsonb NOT NULL, reviewed_values jsonb NOT NULL,
        actor_id uuid NOT NULL REFERENCES users(id), occurred_at timestamptz NOT NULL,
        revision integer NOT NULL, reason text NOT NULL,
        UNIQUE(batch_id,sheet,row_number), CHECK(length(source_note)<=2000));
    CREATE INDEX asset_import_sources_target ON asset_import_sources(kind,target_id);
    INSERT INTO role_permissions(role_id,permission_id)
        SELECT r.id,p.id FROM roles r CROSS JOIN permissions p
        WHERE r.role_code='lab_admin' AND p.permission_code='assets.import'
        ON CONFLICT DO NOTHING;
    """)

def downgrade():
    op.execute("""DO $$ BEGIN
        IF EXISTS(SELECT 1 FROM asset_import_batches WHERE format_version=2)
        THEN RAISE EXCEPTION 'Retained site imports require forward recovery'; END IF;
        END $$;
        DROP TABLE asset_import_sources,asset_import_revisions,asset_import_operations;
        ALTER TABLE asset_import_batches DROP COLUMN format_version,DROP COLUMN mode,
            DROP COLUMN working_rows,DROP COLUMN catalog_digest;
        ALTER TABLE sites DROP COLUMN source_note;
        DELETE FROM role_permissions WHERE role_id=(SELECT id FROM roles WHERE role_code='lab_admin')
            AND permission_id=(SELECT id FROM permissions WHERE permission_code='assets.import');
    """)
