"""Shared local identity, sessions and append-only authentication audit."""
from uuid import NAMESPACE_URL, uuid5

from alembic import op
from sqlalchemy import text

revision = '0002_identity'
down_revision = '0001_baseline'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''
        CREATE TABLE users (
            id UUID PRIMARY KEY, username VARCHAR(80) NOT NULL,
            display_name VARCHAR(150) NOT NULL, password_hash TEXT NOT NULL,
            must_change_password BOOLEAN NOT NULL DEFAULT TRUE,
            user_status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
                CHECK (user_status IN ('ACTIVE','LOCKED','DISABLED')),
            failed_logins INTEGER NOT NULL DEFAULT 0 CHECK (failed_logins >= 0),
            blocked_until TIMESTAMPTZ, last_login_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE UNIQUE INDEX users_username_ci ON users(lower(username));
        CREATE TABLE roles (id UUID PRIMARY KEY, role_code VARCHAR(40) UNIQUE NOT NULL,
            role_name VARCHAR(100) NOT NULL, is_active BOOLEAN NOT NULL DEFAULT TRUE);
        CREATE TABLE permissions (id UUID PRIMARY KEY, permission_code VARCHAR(80) UNIQUE NOT NULL);
        CREATE TABLE user_roles (user_id UUID REFERENCES users(id), role_id UUID REFERENCES roles(id),
            assigned_by UUID REFERENCES users(id), assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY(user_id,role_id));
        CREATE TABLE role_permissions (role_id UUID REFERENCES roles(id), permission_id UUID REFERENCES permissions(id),
            PRIMARY KEY(role_id,permission_id));
        CREATE TABLE auth_sessions (
            token_hash CHAR(64) PRIMARY KEY, user_id UUID NOT NULL REFERENCES users(id),
            csrf_token TEXT NOT NULL, expires_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX auth_sessions_user ON auth_sessions(user_id);
        CREATE TABLE audit_logs (
            id UUID PRIMARY KEY, actor_user_id UUID REFERENCES users(id),
            claimed_username VARCHAR(80), action_code VARCHAR(50) NOT NULL,
            result VARCHAR(30) NOT NULL, occurred_at TIMESTAMPTZ NOT NULL,
            entity_id UUID, CHECK (result IN ('SUCCESS','FAILURE'))
        );
        CREATE INDEX audit_logs_time ON audit_logs(occurred_at,id);
        CREATE FUNCTION forbid_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Audit records are append only'; END $$;
        CREATE TRIGGER audit_append_only BEFORE UPDATE OR DELETE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION forbid_audit_mutation();
    ''')
    permissions = ['assets.read', 'assets.write', 'laboratory.read', 'laboratory.write',
                   'laboratory.finalize', 'analysis.read', 'analysis.write', 'identity.manage', 'audit.read']
    roles = {
        'system_admin': ('系统管理员', permissions),
        'asset_manager': ('Asset Manager', ['assets.read', 'assets.write', 'analysis.read']),
        'lab_admin': ('实验室管理员', ['assets.read', 'laboratory.read', 'laboratory.write', 'laboratory.finalize', 'analysis.read']),
        'analyst': ('分析员', ['assets.read', 'laboratory.read', 'laboratory.write', 'analysis.read']),
        'field_engineer': ('现场工程师', ['assets.read', 'analysis.read']),
        'management_readonly': ('管理只读', ['assets.read', 'laboratory.read', 'analysis.read']),
    }
    connection = op.get_bind()
    for permission in permissions:
        connection.execute(text('INSERT INTO permissions VALUES (:id,:code)'),
                           {'id': uuid5(NAMESPACE_URL, 'dga:permission:' + permission), 'code': permission})
    for code, (name, grants) in roles.items():
        role_id = uuid5(NAMESPACE_URL, 'dga:role:' + code)
        connection.execute(text('INSERT INTO roles(id,role_code,role_name) VALUES (:id,:code,:name)'),
                           {'id': role_id, 'code': code, 'name': name})
        for permission in grants:
            connection.execute(text('INSERT INTO role_permissions VALUES (:role,:permission)'),
                               {'role': role_id, 'permission': uuid5(NAMESPACE_URL, 'dga:permission:' + permission)})


def downgrade():
    op.execute('DROP TABLE audit_logs,auth_sessions,user_roles,role_permissions,permissions,roles,users; DROP FUNCTION forbid_audit_mutation();')
