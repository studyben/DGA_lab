"""Join the existing site-export audit and identity/OIDC migration histories."""

revision = '0030_merge_export_identity'
down_revision = ('0025_site_export_audit', '0029_oidc_callback')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
