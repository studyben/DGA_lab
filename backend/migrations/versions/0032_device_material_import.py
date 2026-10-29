"""Extend retained asset provenance to material text identities and equipment UUIDs."""
from alembic import op

revision = '0032_device_material_import'
down_revision = '0031_site_import'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE asset_import_sources ALTER COLUMN target_id DROP NOT NULL,
            ADD COLUMN target_key varchar(120) REFERENCES asset_materials(material_number),
            ADD COLUMN confirmed_warning_ids jsonb NOT NULL DEFAULT '[]'::jsonb
                CHECK(jsonb_typeof(confirmed_warning_ids)='array');
        ALTER TABLE asset_import_sources DROP CONSTRAINT asset_import_sources_kind_check;
        ALTER TABLE asset_import_sources ADD CONSTRAINT asset_import_sources_kind_target_check CHECK (
            (kind IN ('CUSTOMER','SITE','ASSET') AND target_id IS NOT NULL AND target_key IS NULL)
            OR (kind='MATERIAL' AND target_id IS NULL AND target_key IS NOT NULL));
        CREATE INDEX asset_import_sources_material ON asset_import_sources(kind,target_key);
    """)


def downgrade():
    op.execute("""DO $$ BEGIN
        IF EXISTS(SELECT 1 FROM asset_import_batches WHERE format_version=2 AND mode='ASSETS')
            OR EXISTS(SELECT 1 FROM asset_import_sources WHERE kind IN ('ASSET','MATERIAL') OR target_key IS NOT NULL)
        THEN RAISE EXCEPTION 'Retained equipment/material imports require forward recovery'; END IF;
        END $$;
        DROP INDEX asset_import_sources_material;
        ALTER TABLE asset_import_sources DROP CONSTRAINT asset_import_sources_kind_target_check,
            DROP COLUMN target_key,DROP COLUMN confirmed_warning_ids,
            ALTER COLUMN target_id SET NOT NULL;
        ALTER TABLE asset_import_sources ADD CONSTRAINT asset_import_sources_kind_check
            CHECK(kind IN ('CUSTOMER','SITE'));
    """)
