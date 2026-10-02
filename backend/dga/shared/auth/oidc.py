"""Identity-owned OIDC configuration custody and flow orchestration."""
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe, compare_digest
from urllib.parse import urlsplit
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError
from sqlalchemy import text

from .public import IdentityError, IdentityService, _token_hash


class CandidateInput(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)
    issuer: str = Field(min_length=1, max_length=500)
    client_id: str = Field(min_length=1, max_length=200)
    client_secret: SecretStr = Field(min_length=1, max_length=4096)


def checked_url(value, hosts):
    try:
        url = urlsplit(value)
        valid = (url.scheme == 'https' and url.hostname in hosts and url.port in (None, 443)
            and not url.username and not url.password and not url.query and not url.fragment
            and not any(c.isspace() for c in value) and '\\' not in value)
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise IdentityError('oidc_endpoint_not_allowed', 422)
    return value


class OidcService:
    def __init__(self, engine, *, encryption_key=None, allowed_hosts=(), callback_url='', clock=None, provider=None):
        self._engine = engine
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._identity = IdentityService(engine, clock=self._clock)
        self._hosts = frozenset(allowed_hosts)
        self._callback = callback_url
        self._provider = provider
        try:
            self._cipher = Fernet(encryption_key.encode()) if encryption_key else None
        except (ValueError, TypeError):
            self._cipher = None

    def _ready(self):
        url = urlsplit(self._callback)
        if not self._cipher or not self._hosts or not (
            (url.scheme == 'https' or (url.scheme == 'http' and url.hostname in {'127.0.0.1', 'localhost', '::1'}))
            and url.netloc and not url.username and not url.password and not url.query and not url.fragment
            and url.path == '/api/auth/oidc/callback'
        ):
            raise IdentityError('oidc_not_configured', 503)

    def _admin(self, c, actor):
        c.execute(text('SELECT pg_advisory_xact_lock(30003)'))
        self._identity._authorized(c, actor, 'identity.manage')

    def _decrypt(self, encrypted):
        self._ready()
        try:
            return self._cipher.decrypt(encrypted.encode()).decode()
        except (InvalidToken, ValueError, UnicodeError):
            raise IdentityError('oidc_key_unavailable', 503) from None

    def save_candidate(self, actor, **values):
        self._ready()
        with self._identity._management_transaction(actor, 'OIDC_CANDIDATE_SAVE', None) as c:
            self._admin(c, actor)
            try:
                body = CandidateInput(**values)
            except ValidationError:
                raise IdentityError('invalid_oidc_configuration', 422) from None
            checked_url(body.issuer, self._hosts)
            if body.issuer.endswith('/') or not body.client_id.strip() or not body.client_secret.get_secret_value().strip():
                raise IdentityError('invalid_oidc_configuration', 422)
            candidate_id = uuid4()
            c.execute(text('''INSERT INTO oidc_config_versions(id,issuer,client_id,secret_cipher,created_by,created_at)
                VALUES (:id,:issuer,:client,:secret,:actor,:now)'''), dict(id=candidate_id, issuer=body.issuer,
                client=body.client_id, secret=self._cipher.encrypt(body.client_secret.get_secret_value().encode()).decode(),
                actor=actor.user_id, now=self._clock()))
            self._identity._audit(c, 'OIDC_CANDIDATE_SAVE', 'SUCCESS', actor.user_id, entity=candidate_id)
            return candidate_id

    def configuration(self, actor):
        with self._engine.begin() as c:
            self._admin(c, actor)
            active = c.execute(text('SELECT config_id,revision FROM oidc_active WHERE singleton')).mappings().first()
            rows = c.execute(text('''SELECT id,issuer,client_id,created_at,created_by
                FROM oidc_config_versions ORDER BY created_at DESC,id DESC LIMIT 100''')).mappings()
            return {'active_id': active['config_id'] if active else None, 'revision': active['revision'] if active else 0,
                'candidates': [dict(row) | {'secret_configured': True} for row in rows]}

    def _adapter(self):
        from .oidc_provider import OktaProvider
        return self._provider or OktaProvider(self._hosts)

    def _config(self, c, config_id):
        row = c.execute(text('SELECT * FROM oidc_config_versions WHERE id=:id'), {'id': config_id}).mappings().first()
        if not row:
            raise IdentityError('oidc_config_not_found', 404)
        return {'id': row['id'], 'issuer': row['issuer'], 'client_id': row['client_id'],
            'client_secret': self._decrypt(row['secret_cipher'])}

    def _test_admin(self, c, session_token, admin_id=None):
        c.execute(text('SELECT pg_advisory_xact_lock(30003)'))
        user, session = self._identity._resolve(c, session_token, lock=True)
        actor = self._identity._actor(c, user)
        self._identity._authorized(c, actor, 'identity.manage')
        if admin_id is not None and actor.user_id != admin_id:
            raise IdentityError('oidc_flow_invalid', 400)
        return actor

    def start_test(self, session_token, config_id):
        self._ready()
        with self._engine.begin() as c:
            actor = self._test_admin(c, session_token)
            config = self._config(c, config_id)
        state, binding, nonce, verifier = [token_urlsafe(32) for _ in range(4)]
        url = self._adapter().authorization_url(config, callback=self._callback, state=state, nonce=nonce, verifier=verifier)
        with self._engine.begin() as c:
            self._test_admin(c, session_token, actor.user_id)
            # Ephemeral handshake secrets need no indefinite retention.
            c.execute(text('DELETE FROM oidc_flows WHERE expires_at<:now'), {'now': self._clock()})
            c.execute(text('''INSERT INTO oidc_flows(state_hash,browser_hash,config_id,purpose,admin_id,
                admin_session_hash,verifier_cipher,nonce,issued_at,expires_at)
                VALUES (:state,:browser,:config,'TEST',:admin,:session,:verifier,:nonce,:now,:expiry)'''),
                dict(state=_token_hash(state), browser=_token_hash(binding), config=config_id, admin=actor.user_id,
                    session=_token_hash(session_token), verifier=self._cipher.encrypt(verifier.encode()).decode(),
                    nonce=nonce, now=self._clock(), expiry=self._clock()+timedelta(minutes=10)))
        return {'authorization_url': url, 'browser_binding': binding}

    def _consume(self, state, binding, purpose, session_token=None):
        self._ready()
        if not state or not binding or len(state) > 200 or len(binding) > 200:
            raise IdentityError('oidc_flow_invalid', 400)
        with self._engine.begin() as c:
            # Serialize identity and flow transitions in the same order as management commands.
            c.execute(text('SELECT pg_advisory_xact_lock(30003)'))
            row = c.execute(text('SELECT * FROM oidc_flows WHERE state_hash=:state FOR UPDATE'),
                {'state': _token_hash(state)}).mappings().first()
            if (not row or row['consumed_at'] or row['expires_at'] <= self._clock()
                or row['purpose'] != purpose or not compare_digest(row['browser_hash'], _token_hash(binding))
                or (purpose == 'TEST' and not compare_digest(row['admin_session_hash'], _token_hash(session_token or '')))):
                raise IdentityError('oidc_flow_invalid', 400)
            # Commit consumption before external I/O, including subsequent provider failures.
            c.execute(text('UPDATE oidc_flows SET consumed_at=:now WHERE state_hash=:state'),
                {'now': self._clock(), 'state': row['state_hash']})
            return dict(row)

    def complete_test(self, state, binding, code, session_token):
        row = self._consume(state, binding, 'TEST', session_token)
        try:
            return self._complete_test(row, code, session_token)
        except IdentityError:
            with self._engine.begin() as c:
                self._identity._audit(c, 'OIDC_TEST', 'FAILURE', row['admin_id'], entity=row['config_id'])
            raise

    def _complete_test(self, row, code, session_token):
        with self._engine.begin() as c:
            self._test_admin(c, session_token, row['admin_id'])
            config = self._config(c, row['config_id'])
        if not isinstance(code, str) or not 1 <= len(code) <= 4096:
            raise IdentityError('oidc_provider_rejected', 400)
        verified = self._adapter().redeem(config, callback=self._callback, code=code, nonce=row['nonce'],
            verifier=self._decrypt(row['verifier_cipher']), issued_at=row['issued_at'], clock=self._clock)
        with self._engine.begin() as c:
            actor = self._test_admin(c, session_token, row['admin_id'])
            if row['expires_at'] <= self._clock():
                raise IdentityError('oidc_flow_invalid', 400)
            proof_id = uuid4()
            c.execute(text('''INSERT INTO oidc_test_proofs(id,config_id,admin_id,issuer,subject,verified_at,expires_at)
                VALUES (:id,:config,:admin,:issuer,:subject,:now,:expiry)'''), dict(id=proof_id, config=row['config_id'],
                    admin=actor.user_id, issuer=verified.issuer, subject=verified.subject, now=self._clock(),
                    expiry=self._clock()+timedelta(minutes=15)))
            self._identity._audit(c, 'OIDC_TEST', 'SUCCESS', actor.user_id, entity=row['config_id'])
            return {'proof_id': proof_id, 'config_id': row['config_id'], 'subject': verified.subject}
