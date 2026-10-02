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
    callback_url: str | None = Field(default=None, max_length=500)


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
    def __init__(self, engine, *, encryption_key=None, allowed_hosts=(), callback_url='', callback_origins=(), clock=None, provider=None):
        self._engine = engine
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._identity = IdentityService(engine, clock=self._clock)
        self._hosts = frozenset(allowed_hosts)
        self._callback = callback_url
        try:
            default = urlsplit(callback_url)
            fallback = {f'{default.scheme}://{default.netloc}'} if default.netloc else set()
        except ValueError:
            fallback = set()
        self._callback_origins = frozenset(callback_origins or fallback)
        self._provider = provider
        try:
            self._cipher = Fernet(encryption_key.encode()) if encryption_key else None
        except (ValueError, TypeError):
            self._cipher = None

    def _ready(self):
        if not self._cipher or not self._hosts or not self._callback_origins:
            raise IdentityError('oidc_not_configured', 503)

    def _checked_callback(self, value):
        try:
            url = urlsplit(value)
            valid = (isinstance(value, str) and bool(url.netloc)
                and (url.scheme == 'https' or (url.scheme == 'http' and url.hostname in {'127.0.0.1', 'localhost', '::1'}))
                and f'{url.scheme}://{url.netloc}' in self._callback_origins
                and not url.username and not url.password and not url.query and not url.fragment
                and url.path == '/api/auth/oidc/callback' and '\\' not in value
                and not any(c.isspace() for c in value) and url.port != 0)
        except (ValueError, TypeError):
            valid = False
        if not valid:
            raise IdentityError('oidc_callback_not_allowed', 422)
        return value

    def _start_origin(self, config, origin):
        url = urlsplit(config['callback_url'])
        if origin is not None and origin != f'{url.scheme}://{url.netloc}':
            raise IdentityError('oidc_callback_origin_mismatch', 409)

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
            callback = self._checked_callback(body.callback_url if body.callback_url is not None else self._callback)
            if body.issuer.endswith('/') or not body.client_id.strip() or not body.client_secret.get_secret_value().strip():
                raise IdentityError('invalid_oidc_configuration', 422)
            candidate_id = uuid4()
            c.execute(text('''INSERT INTO oidc_config_versions(id,issuer,client_id,secret_cipher,created_by,created_at,callback_url)
                VALUES (:id,:issuer,:client,:secret,:actor,:now,:callback)'''), dict(id=candidate_id, issuer=body.issuer, callback=callback,
                client=body.client_id, secret=self._cipher.encrypt(body.client_secret.get_secret_value().encode()).decode(),
                actor=actor.user_id, now=self._clock()))
            self._identity._audit(c, 'OIDC_CANDIDATE_SAVE', 'SUCCESS', actor.user_id, entity=candidate_id)
            return candidate_id

    def configuration(self, actor):
        with self._engine.begin() as c:
            self._admin(c, actor)
            active = c.execute(text('SELECT config_id,revision FROM oidc_active WHERE singleton')).mappings().first()
            rows = c.execute(text('''SELECT id,issuer,client_id,created_at,created_by,callback_url
                FROM oidc_config_versions ORDER BY created_at DESC,id DESC LIMIT 100''')).mappings()
            proofs = [dict(r) for r in c.execute(text('''SELECT id,config_id,issuer,subject,verified_at,expires_at
                FROM oidc_test_proofs WHERE admin_id=:admin AND expires_at>:now ORDER BY verified_at DESC LIMIT 100'''),
                {'admin': actor.user_id, 'now': self._clock()}).mappings()]
            try:
                self._ready()
                ready = True
            except IdentityError:
                ready = False
            return {'active_id': active['config_id'] if active else None, 'revision': active['revision'] if active else 0,
                'candidates': [dict(row) | {'secret_configured': True} for row in rows],
                'proofs': proofs, 'deployment_ready': ready, 'default_callback_url': self._callback}

    def _adapter(self):
        from .oidc_provider import OktaProvider
        return self._provider or OktaProvider(self._hosts)

    def _config(self, c, config_id):
        row = c.execute(text('SELECT * FROM oidc_config_versions WHERE id=:id'), {'id': config_id}).mappings().first()
        if not row:
            raise IdentityError('oidc_config_not_found', 404)
        if not row['callback_url']:
            raise IdentityError('oidc_candidate_callback_required', 409)
        return {'id': row['id'], 'issuer': row['issuer'], 'client_id': row['client_id'],
            'client_secret': self._decrypt(row['secret_cipher']), 'callback_url': self._checked_callback(row['callback_url'])}

    def _test_admin(self, c, session_token, admin_id=None):
        c.execute(text('SELECT pg_advisory_xact_lock(30003)'))
        user, session = self._identity._resolve(c, session_token, lock=True)
        actor = self._identity._actor(c, user)
        self._identity._authorized(c, actor, 'identity.manage')
        if admin_id is not None and actor.user_id != admin_id:
            raise IdentityError('oidc_flow_invalid', 400)
        return actor

    def start_test(self, session_token, config_id, *, origin=None):
        self._ready()
        with self._engine.begin() as c:
            actor = self._test_admin(c, session_token)
            config = self._config(c, config_id)
            self._start_origin(config, origin)
        state, binding, nonce, verifier = [token_urlsafe(32) for _ in range(4)]
        url = self._adapter().authorization_url(config, callback=config['callback_url'], state=state, nonce=nonce, verifier=verifier)
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
        verified = self._adapter().redeem(config, callback=config['callback_url'], code=code, nonce=row['nonce'],
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

    def _active(self, c):
        c.execute(text('INSERT INTO oidc_active(singleton) VALUES (TRUE) ON CONFLICT DO NOTHING'))
        return c.execute(text('SELECT config_id,revision FROM oidc_active WHERE singleton FOR UPDATE')).mappings().one()

    def _proof(self, c, actor, proof_id):
        proof = c.execute(text('SELECT * FROM oidc_test_proofs WHERE id=:id'), {'id': proof_id}).mappings().first()
        if not proof or proof['admin_id'] != actor.user_id or proof['expires_at'] <= self._clock():
            raise IdentityError('oidc_test_required', 409)
        return proof

    def activate(self, actor, config_id, proof_id, *, expected_revision):
        self._ready()
        with self._identity._management_transaction(actor, 'OIDC_ACTIVATE', config_id) as c:
            self._admin(c, actor)
            config = self._config(c, config_id)
            checked_url(config['issuer'], self._hosts)
            proof = self._proof(c, actor, proof_id)
            if proof['config_id'] != config_id:
                raise IdentityError('oidc_test_required', 409)
            active = self._active(c)
            if type(expected_revision) is not int or active['revision'] != expected_revision:
                raise IdentityError('stale_oidc_configuration', 409)
            c.execute(text('UPDATE oidc_active SET config_id=:id,revision=revision+1 WHERE singleton'), {'id': config_id})
            self._identity._identity_event(c, actor, 'OIDC_ACTIVATE', config_id,
                {'config_id': str(active['config_id']) if active['config_id'] else None}, {'config_id': str(config_id)})

    def availability(self):
        try:
            self._ready()
        except IdentityError:
            return {'enabled': False}
        with self._engine.connect() as c:
            active = c.execute(text('SELECT config_id FROM oidc_active WHERE singleton')).scalar()
            if not active:
                return {'enabled': False}
            try:
                config = self._config(c, active)
                checked_url(config['issuer'], self._hosts)
            except IdentityError:
                return {'enabled': False}
            return {'enabled': True}

    def start_login(self, *, origin=None):
        self._ready()
        with self._engine.begin() as c:
            active = dict(self._active(c))
            if not active['config_id']:
                raise IdentityError('oidc_not_configured', 503)
            config = self._config(c, active['config_id'])
            self._start_origin(config, origin)
        state, binding, nonce, verifier = [token_urlsafe(32) for _ in range(4)]
        issued = self._clock()
        url = self._adapter().authorization_url(config, callback=config['callback_url'], state=state, nonce=nonce, verifier=verifier)
        with self._engine.begin() as c:
            current = self._active(c)
            if current['revision'] != active['revision']:
                raise IdentityError('stale_oidc_configuration', 409)
            c.execute(text('DELETE FROM oidc_flows WHERE expires_at<:now'), {'now': self._clock()})
            c.execute(text('''INSERT INTO oidc_flows(state_hash,browser_hash,config_id,purpose,
                verifier_cipher,nonce,issued_at,expires_at,active_revision)
                VALUES (:state,:browser,:config,'LOGIN',:verifier,:nonce,:now,:expiry,:revision)'''),
                dict(state=_token_hash(state), browser=_token_hash(binding), config=config['id'],
                    verifier=self._cipher.encrypt(verifier.encode()).decode(), nonce=nonce, now=issued,
                    expiry=issued+timedelta(minutes=10), revision=active['revision']))
        return {'authorization_url': url, 'browser_binding': binding}

    def complete_login(self, state, binding, code):
        row = self._consume(state, binding, 'LOGIN')
        try:
            return self._complete_login(row, code)
        except IdentityError:
            with self._engine.begin() as c:
                self._identity._audit(c, 'OIDC_LOGIN', 'FAILURE', entity=row['config_id'])
            raise

    def _complete_login(self, row, code):
        with self._engine.begin() as c:
            config = self._config(c, row['config_id'])
        if not isinstance(code, str) or not 1 <= len(code) <= 4096:
            raise IdentityError('oidc_provider_rejected', 400)
        verified = self._adapter().redeem(config, callback=config['callback_url'], code=code, nonce=row['nonce'],
            verifier=self._decrypt(row['verifier_cipher']), issued_at=row['issued_at'], clock=self._clock)
        verified_at = self._clock()
        with self._engine.begin() as c:
            c.execute(text('SELECT pg_advisory_xact_lock(30003)'))
            active = self._active(c)
            if active['config_id'] != row['config_id'] or active['revision'] != row['active_revision']:
                raise IdentityError('stale_oidc_configuration', 409)
            if row['expires_at'] <= verified_at:
                raise IdentityError('oidc_flow_invalid', 400)
            user_id = c.execute(text('''SELECT user_id FROM external_identities
                WHERE issuer=:issuer AND subject=:subject'''), {'issuer': verified.issuer, 'subject': verified.subject}).scalar()
            created = user_id is None
            if not user_id:
                if verified.login_hints and c.execute(text('SELECT 1 FROM users WHERE lower(username)=ANY(:hints)'),
                        {'hints': list(verified.login_hints)}).first():
                    raise IdentityError('oidc_link_required', 409)
                user_id = uuid4()
                c.execute(text('''INSERT INTO users(id,username,display_name,password_hash,credential_kind,must_change_password)
                    VALUES (:id,:username,:name,NULL,'NONE',FALSE)'''),
                    {'id': user_id, 'username': 'oidc-' + user_id.hex, 'name': verified.display_name})
                c.execute(text('''INSERT INTO external_identities(issuer,subject,user_id,created_at)
                    VALUES (:issuer,:subject,:user,:now)'''),
                    {'issuer': verified.issuer, 'subject': verified.subject, 'user': user_id, 'now': verified_at})
                c.execute(text("INSERT INTO user_roles(user_id,role_id) SELECT :id,id FROM roles WHERE role_code='field_engineer'"), {'id': user_id})
            user = self._identity._target(c, user_id)
            if user['user_status'] != 'ACTIVE':
                raise IdentityError('oidc_account_unavailable', 403)
            c.execute(text('UPDATE users SET last_login_at=:now WHERE id=:id'), {'id': user_id, 'now': verified_at})
            session = self._identity._new_session(c, user, expires_at=verified_at+timedelta(hours=8))
            if created:
                self._identity._identity_event(c, session.actor, 'OIDC_PROVISION', user_id, {},
                    {'roles': ['field_engineer'], 'issuer': verified.issuer, 'subject': verified.subject})
            self._identity._audit(c, 'OIDC_LOGIN', 'SUCCESS', user_id)
            return session

    def bind_identity(self, actor, user_id, proof_id, *, expected_revision):
        self._ready()
        with self._identity._management_transaction(actor, 'OIDC_BIND', user_id) as c:
            self._admin(c, actor)
            proof = self._proof(c, actor, proof_id)
            user = self._identity._target(c, user_id)
            if type(expected_revision) is not int or user['revision'] != expected_revision:
                raise IdentityError('stale_user', 409)
            if c.execute(text('''SELECT 1 FROM external_identities WHERE issuer=:issuer
                AND (subject=:subject OR user_id=:user)'''),
                    {'issuer': proof['issuer'], 'subject': proof['subject'], 'user': user_id}).first():
                raise IdentityError('oidc_identity_already_bound', 409)
            c.execute(text('''INSERT INTO external_identities(issuer,subject,user_id,created_at)
                VALUES (:issuer,:subject,:user,:now)'''), {'issuer': proof['issuer'], 'subject': proof['subject'],
                    'user': user_id, 'now': self._clock()})
            c.execute(text('UPDATE users SET revision=revision+1,updated_at=:now WHERE id=:id'),
                {'id': user_id, 'now': self._clock()})
            self._identity._identity_event(c, actor, 'OIDC_BIND', user_id, {},
                {'issuer': proof['issuer'], 'subject': proof['subject']})

    def callback(self, state, binding, code, session_token=''):
        with self._engine.connect() as c:
            purpose = c.execute(text('SELECT purpose FROM oidc_flows WHERE state_hash=:state'),
                {'state': _token_hash(state)}).scalar()
        if purpose == 'TEST':
            return {'purpose': purpose, 'proof': self.complete_test(state, binding, code, session_token)}
        if purpose == 'LOGIN':
            return {'purpose': purpose, 'session': self.complete_login(state, binding, code)}
        raise IdentityError('oidc_flow_invalid', 400)
