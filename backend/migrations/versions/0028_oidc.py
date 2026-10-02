"""Encrypted immutable OIDC candidates and single-use browser-bound flows."""
from alembic import op

revision = '0028_oidc'
down_revision = '0027_site_basics'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''
        CREATE TABLE oidc_config_versions (
            id uuid PRIMARY KEY, issuer text NOT NULL, client_id varchar(200) NOT NULL,
            secret_cipher text NOT NULL, created_by uuid NOT NULL REFERENCES users(id),
            created_at timestamptz NOT NULL
        );
        CREATE TRIGGER oidc_config_immutable BEFORE UPDATE OR DELETE ON oidc_config_versions
            FOR EACH ROW EXECUTE FUNCTION forbid_audit_mutation();
        CREATE TABLE oidc_active (
            singleton boolean PRIMARY KEY DEFAULT TRUE CHECK (singleton),
            config_id uuid REFERENCES oidc_config_versions(id), revision integer NOT NULL DEFAULT 0
        );
        INSERT INTO oidc_active(singleton) VALUES (TRUE);
        CREATE TABLE oidc_flows (
            state_hash char(64) PRIMARY KEY, browser_hash char(64) NOT NULL,
            config_id uuid NOT NULL REFERENCES oidc_config_versions(id),
            purpose varchar(10) NOT NULL CHECK (purpose IN ('TEST','LOGIN')),
            admin_id uuid REFERENCES users(id), admin_session_hash char(64),
            verifier_cipher text NOT NULL, nonce text NOT NULL,
            issued_at timestamptz NOT NULL, expires_at timestamptz NOT NULL,
            consumed_at timestamptz, active_revision integer,
            CHECK ((purpose='TEST' AND admin_id IS NOT NULL AND admin_session_hash IS NOT NULL)
                OR (purpose='LOGIN' AND admin_id IS NULL AND admin_session_hash IS NULL))
        );
        CREATE INDEX oidc_flows_expiry ON oidc_flows(expires_at);
        CREATE TABLE oidc_test_proofs (
            id uuid PRIMARY KEY, config_id uuid NOT NULL REFERENCES oidc_config_versions(id),
            admin_id uuid NOT NULL REFERENCES users(id), issuer text NOT NULL, subject varchar(255) NOT NULL,
            verified_at timestamptz NOT NULL, expires_at timestamptz NOT NULL
        );
        CREATE TABLE external_identities (
            issuer text NOT NULL, subject varchar(255) NOT NULL,
            user_id uuid NOT NULL REFERENCES users(id), created_at timestamptz NOT NULL,
            PRIMARY KEY(issuer,subject), UNIQUE(user_id,issuer)
        );
    ''')


def downgrade():
    raise RuntimeError('Retained identity/OIDC configuration evidence requires reviewed forward recovery')
