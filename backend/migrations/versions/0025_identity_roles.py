"""Confirmed business-role policy; retain legacy assignments and local credentials."""
from uuid import NAMESPACE_URL, uuid5
from alembic import op
from sqlalchemy import text

revision = '0025_identity_roles'
down_revision = '0024_alarm_observation'
branch_labels = None
depends_on = None


def upgrade():
    c = op.get_bind()
    for code in ('assets.site.edit', 'identity.ordinary.manage', 'identity.am.manage'):
        c.execute(text('INSERT INTO permissions(id,permission_code) VALUES (:id,:code)'),
                  {'id': uuid5(NAMESPACE_URL, 'dga:permission:' + code), 'code': code})
    c.execute(text("INSERT INTO roles(id,role_code,role_name) VALUES (:id,'management','管理层')"),
              {'id': uuid5(NAMESPACE_URL, 'dga:role:management')})
    c.execute(text("UPDATE roles SET role_name='实验室经理' WHERE role_code='lab_admin'"))
    read = {'assets.read', 'laboratory.read', 'analysis.read'}
    grants = {
        'asset_manager': read | {'assets.site.edit'},
        'management': read | {'assets.site.edit', 'identity.am.manage'},
        'field_engineer': read | {'analysis.acknowledge'},
        'analyst': read | {'laboratory.write', 'laboratory.finalize', 'analysis.acknowledge'},
        'lab_admin': read | {'assets.write', 'assets.site.edit', 'assets.history.correct',
            'laboratory.write', 'laboratory.finalize', 'laboratory.configure',
            'analysis.write', 'analysis.acknowledge', 'audit.read', 'identity.ordinary.manage'},
        'system_admin': set(c.execute(text('SELECT permission_code FROM permissions')).scalars()),
    }
    for role, permissions in grants.items():
        c.execute(text('DELETE FROM role_permissions WHERE role_id=(SELECT id FROM roles WHERE role_code=:role)'), {'role': role})
        for permission in sorted(permissions):
            c.execute(text('''INSERT INTO role_permissions(role_id,permission_id)
                SELECT r.id,p.id FROM roles r CROSS JOIN permissions p
                WHERE r.role_code=:role AND p.permission_code=:permission'''),
                {'role': role, 'permission': permission})
    # management_readonly remains unchanged, including its stable role identity.


def downgrade():
    raise RuntimeError('Role policy rollback requires reviewed account impact and forward recovery; no silent privilege rollback')
