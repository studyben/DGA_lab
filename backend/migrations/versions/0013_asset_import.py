"""Add new-asset import staging without changing legacy asset identities."""
from uuid import NAMESPACE_URL, uuid5
from alembic import op
from sqlalchemy import text

revision = '0013_asset_import'
down_revision = '0012_asset_history_permission'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE asset_materials (
          material_number VARCHAR(120) PRIMARY KEY,
          model VARCHAR(120) NOT NULL,
          asset_type VARCHAR(30) NOT NULL CHECK(asset_type IN ('WHOLE_UNIT','TRANSFORMER'))
        );
        INSERT INTO asset_materials
          SELECT material_number,min(model),min(asset_type) FROM formal_assets
          WHERE material_number IS NOT NULL AND btrim(material_number)<>''
          GROUP BY material_number
          HAVING count(DISTINCT (model,asset_type))=1 AND bool_and(model IS NOT NULL AND btrim(model)<>'');
        CREATE TABLE asset_import_batches (
          id UUID PRIMARY KEY,
          filename VARCHAR(200) NOT NULL,
          sha256 CHAR(64) NOT NULL,
          object_key TEXT NOT NULL UNIQUE,
          byte_size INTEGER NOT NULL,
          state VARCHAR(20) NOT NULL CHECK(state IN ('STAGED','VALIDATED','FAILED','PUBLISHED')),
          source_rows JSONB NOT NULL,
          rows JSONB NOT NULL DEFAULT '[]',
          issues JSONB NOT NULL DEFAULT '[]',
          summary JSONB NOT NULL DEFAULT '{}',
          validation_revision INTEGER NOT NULL DEFAULT 0,
          created_by UUID NOT NULL REFERENCES users(id),
          created_at TIMESTAMPTZ NOT NULL,
          published_by UUID REFERENCES users(id),
          published_at TIMESTAMPTZ,
          failure_code TEXT,
          CHECK ((state='PUBLISHED')=(published_by IS NOT NULL AND published_at IS NOT NULL))
        );
        CREATE INDEX asset_import_pending ON asset_import_batches(created_at) WHERE state='STAGED';
    """)
    permission = uuid5(NAMESPACE_URL, 'dga:permission:assets.import')
    op.get_bind().execute(text("INSERT INTO permissions VALUES (:id,'assets.import')"), {'id': permission})
    op.get_bind().execute(text("INSERT INTO role_permissions SELECT id,:id FROM roles WHERE role_code='system_admin'"), {'id': permission})


def downgrade():
    # Retained source/result audit must not be silently discarded by downgrade.
    op.execute("DO $$ BEGIN IF EXISTS(SELECT 1 FROM asset_import_batches) THEN RAISE EXCEPTION 'Retained import batches require explicit archival before downgrade'; END IF; END $$")
    op.execute("DROP TABLE asset_import_batches; DROP TABLE asset_materials")
    op.execute("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE permission_code='assets.import')")
    op.execute("DELETE FROM permissions WHERE permission_code='assets.import'")
