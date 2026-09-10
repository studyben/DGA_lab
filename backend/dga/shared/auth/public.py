"""Public identity application interface. HTTP and trusted operator tools use this seam."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import token_urlsafe
from typing import Callable
from uuid import UUID, uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from sqlalchemy import Engine, text
from sqlalchemy.engine import Connection

HASHER = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
DUMMY_HASH = HASHER.hash(token_urlsafe(32))


class IdentityError(Exception):
    def __init__(self, code: str, status: int = 401):
        self.code, self.status = code, status
        super().__init__(code)


@dataclass(frozen=True)
class ActorContext:
    user_id: UUID
    username: str
    display_name: str
    roles: frozenset[str]
    permissions: frozenset[str]
    must_change_password: bool


def require_permission(actor: ActorContext, permission: str) -> None:
    if actor.must_change_password:
        raise IdentityError('password_change_required', 403)
    if permission not in actor.permissions:
        raise IdentityError('permission_denied', 403)


class AuditTrail:
    """Append business audit events inside the caller's database transaction."""

    def __init__(self, *, clock: Callable[[], datetime] | None = None):
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def append(
        self,
        connection: Connection,
        actor: ActorContext,
        action_code: str,
        *,
        entity_id: UUID,
    ) -> None:
        if not 1 <= len(action_code) <= 50:
            raise IdentityError('invalid_audit_event', 422)
        connection.execute(
            text(
                """INSERT INTO audit_logs
                (id,actor_user_id,action_code,result,occurred_at,entity_id)
                VALUES (:id,:actor,:action,'SUCCESS',:time,:entity)"""
            ),
            {
                'id': uuid4(),
                'actor': actor.user_id,
                'action': action_code,
                'time': self._clock(),
                'entity': entity_id,
            },
        )


@dataclass(frozen=True)
class Session:
    actor: ActorContext
    csrf_token: str
    expires_at: datetime
    token: str  # Transport secret: never serialize this record directly to JSON or logs.


def _token_hash(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def _password_ok(password: str, encoded: str) -> bool:
    try:
        return HASHER.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def _validate_password(password: str) -> None:
    if not 15 <= len(password) <= 128:
        raise IdentityError('password_length', 422)


class IdentityService:
    def __init__(self, engine: Engine, *, clock: Callable[[], datetime] | None = None, session_hours: int = 8):
        self._engine = engine
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lifetime = timedelta(hours=session_hours)

    def _audit(self, connection, action, result, user=None, claimed=None, entity=None):
        connection.execute(text('''INSERT INTO audit_logs
            (id,actor_user_id,claimed_username,action_code,result,occurred_at,entity_id)
            VALUES (:id,:actor,:claimed,:action,:result,:time,:entity)'''),
            dict(id=uuid4(), actor=user, claimed=claimed, action=action, result=result, time=self._clock(), entity=entity))

    def _actor(self, connection, user) -> ActorContext:
        roles = connection.execute(text('''SELECT r.role_code FROM roles r JOIN user_roles ur ON ur.role_id=r.id
            WHERE ur.user_id=:id AND r.is_active'''), {'id': user['id']}).scalars().all()
        grants = connection.execute(text('''SELECT DISTINCT p.permission_code FROM permissions p
            JOIN role_permissions rp ON rp.permission_id=p.id JOIN roles r ON r.id=rp.role_id
            JOIN user_roles ur ON ur.role_id=r.id WHERE ur.user_id=:id AND r.is_active'''), {'id': user['id']}).scalars().all()
        return ActorContext(user['id'], user['username'], user['display_name'], frozenset(roles), frozenset(grants), user['must_change_password'])

    def _new_session(self, connection, user) -> Session:
        token, csrf = token_urlsafe(32), token_urlsafe(32)
        expiry = self._clock() + self._lifetime
        connection.execute(text('INSERT INTO auth_sessions(token_hash,user_id,csrf_token,expires_at) VALUES (:hash,:id,:csrf,:expiry)'),
                           dict(hash=_token_hash(token), id=user['id'], csrf=csrf, expiry=expiry))
        return Session(self._actor(connection, user), csrf, expiry, token)

    def bootstrap_admin(self, username: str, display_name: str, password: str) -> UUID:
        """Trusted local operator operation only; refuses once any user exists."""
        _validate_password(password)
        username = username.strip().lower()
        if not 1 <= len(username) <= 80 or not 1 <= len(display_name) <= 150:
            raise IdentityError('invalid_user', 422)
        with self._engine.begin() as c:
            c.execute(text('SELECT pg_advisory_xact_lock(30003)'))
            if c.execute(text('SELECT 1 FROM users LIMIT 1')).first():
                raise IdentityError('already_initialized', 409)
            user_id = uuid4()
            c.execute(text('INSERT INTO users(id,username,display_name,password_hash) VALUES (:id,:username,:name,:hash)'),
                      dict(id=user_id, username=username, name=display_name, hash=HASHER.hash(password)))
            c.execute(text("INSERT INTO user_roles(user_id,role_id,assigned_by) SELECT :id,id,:id FROM roles WHERE role_code='system_admin'"), {'id': user_id})
            self._audit(c, 'BOOTSTRAP', 'SUCCESS', user_id, entity=user_id)
            return user_id

    def login(self, username: str, password: str) -> Session:
        username = username.strip().lower()
        if len(username) > 80 or len(password) > 128:
            raise IdentityError('invalid_credentials')
        session = None
        with self._engine.begin() as c:
            user = c.execute(text('SELECT * FROM users WHERE lower(username)=:name FOR UPDATE'), {'name': username}).mappings().first()
            valid_password = _password_ok(password, user['password_hash'] if user else DUMMY_HASH)
            if user and valid_password and user['user_status'] == 'ACTIVE' and (not user['blocked_until'] or user['blocked_until'] <= self._clock()):
                c.execute(text('UPDATE users SET failed_logins=0,blocked_until=NULL,last_login_at=:now WHERE id=:id'), dict(id=user['id'], now=self._clock()))
                session = self._new_session(c, user)
                self._audit(c, 'LOGIN', 'SUCCESS', user['id'], username)
            else:
                if user and user['user_status'] == 'ACTIVE' and (not user['blocked_until'] or user['blocked_until'] <= self._clock()):
                    failures = (0 if user['blocked_until'] else user['failed_logins']) + 1
                    c.execute(text('UPDATE users SET failed_logins=:count,blocked_until=:blocked WHERE id=:id'),
                              dict(id=user['id'], count=failures, blocked=self._clock() + timedelta(minutes=15) if failures >= 5 else None))
                self._audit(c, 'LOGIN', 'FAILURE', user['id'] if user else None, username)
        if session is None:
            raise IdentityError('invalid_credentials')
        return session

    def _resolve(self, c, token: str, *, lock: bool = False):
        # User lock is always acquired before session checks/mutations to serialize credential changes.
        user = c.execute(text('''SELECT u.* FROM users u JOIN auth_sessions s ON s.user_id=u.id
            WHERE s.token_hash=:hash''' + (' FOR UPDATE OF u' if lock else '')), {'hash': _token_hash(token)}).mappings().first()
        if not user or user['user_status'] != 'ACTIVE':
            raise IdentityError('session_expired')
        session = c.execute(text('SELECT * FROM auth_sessions WHERE token_hash=:hash AND expires_at>:now'),
                            dict(hash=_token_hash(token), now=self._clock())).mappings().first()
        if not session:
            raise IdentityError('session_expired')
        return user, session

    def session(self, token: str) -> Session:
        with self._engine.begin() as c:
            user, row = self._resolve(c, token)
            return Session(self._actor(c, user), row['csrf_token'], row['expires_at'], token)

    def change_password(self, token: str, current_password: str, new_password: str) -> Session:
        _validate_password(new_password)
        result = None
        with self._engine.begin() as c:
            user, _ = self._resolve(c, token, lock=True)
            if _password_ok(current_password, user['password_hash']) and not _password_ok(new_password, user['password_hash']):
                c.execute(text('UPDATE users SET password_hash=:hash,must_change_password=FALSE,updated_at=:now WHERE id=:id'),
                          dict(id=user['id'], hash=HASHER.hash(new_password), now=self._clock()))
                c.execute(text('DELETE FROM auth_sessions WHERE user_id=:id'), {'id': user['id']})
                result = self._new_session(c, {**user, 'must_change_password': False})
            self._audit(c, 'PASSWORD_CHANGE', 'SUCCESS' if result else 'FAILURE', user['id'])
        if not result:
            raise IdentityError('password_change_failed', 400)
        return result

    def logout(self, token: str) -> None:
        with self._engine.begin() as c:
            user = c.execute(text('SELECT u.id FROM users u JOIN auth_sessions s ON s.user_id=u.id WHERE s.token_hash=:hash FOR UPDATE OF u'), {'hash': _token_hash(token)}).scalar()
            deleted = c.execute(text('DELETE FROM auth_sessions WHERE token_hash=:hash RETURNING user_id'), {'hash': _token_hash(token)}).scalar()
            if deleted:
                self._audit(c, 'LOGOUT', 'SUCCESS', user)

    def audit_events(self, actor: ActorContext, *, limit: int = 100) -> list[dict]:
        if not 1 <= limit <= 500:
            raise IdentityError('invalid_limit', 422)
        with self._engine.begin() as c:
            self._authorized(c, actor, 'audit.read')
            return [dict(row) for row in c.execute(text('''SELECT id,actor_user_id,claimed_username,
                action_code,result,occurred_at,entity_id FROM audit_logs ORDER BY occurred_at,id LIMIT :limit'''),
                {'limit': limit}).mappings()]

    def _authorized(self, c, actor, permission):
        user = c.execute(text('SELECT * FROM users WHERE id=:id AND user_status=\'ACTIVE\' FOR UPDATE'), {'id': actor.user_id}).mappings().first()
        if not user:
            raise IdentityError('permission_denied', 403)
        require_permission(self._actor(c, user), permission)

    def provision_user(self, actor: ActorContext, username: str, display_name: str, password: str, roles: list[str]) -> UUID:
        """Operator/admin application command; not exposed as a public HTTP registration endpoint."""
        _validate_password(password)
        username = username.strip().lower()
        if not 1 <= len(username) <= 80 or not 1 <= len(display_name) <= 150:
            raise IdentityError('invalid_user', 422)
        with self._engine.begin() as c:
            # Serialize uniqueness checking without exposing a database exception to callers.
            c.execute(text('SELECT pg_advisory_xact_lock(30003)'))
            self._authorized(c, actor, 'identity.manage')
            if c.execute(text('SELECT 1 FROM users WHERE lower(username)=:username'), {'username': username}).first():
                raise IdentityError('username_taken', 409)
            user_id = uuid4()
            c.execute(text('INSERT INTO users(id,username,display_name,password_hash) VALUES (:id,:username,:name,:hash)'),
                      dict(id=user_id, username=username, name=display_name, hash=HASHER.hash(password)))
            self._assign_roles(c, user_id, roles, actor.user_id)
            self._audit(c, 'USER_CREATE', 'SUCCESS', actor.user_id, entity=user_id)
            return user_id

    def _assign_roles(self, c, user_id, roles, actor_id):
        available = {row['role_code']: row['id'] for row in c.execute(text('SELECT id,role_code FROM roles WHERE is_active')).mappings()}
        if not roles or not set(roles).issubset(available):
            raise IdentityError('invalid_roles', 422)
        c.execute(text('DELETE FROM user_roles WHERE user_id=:id'), {'id': user_id})
        for role in set(roles):
            c.execute(text('INSERT INTO user_roles(user_id,role_id,assigned_by) VALUES (:id,:role,:actor)'),
                      dict(id=user_id, role=available[role], actor=actor_id))

    def set_roles(self, actor: ActorContext, user_id: UUID, roles: list[str]) -> None:
        with self._engine.begin() as c:
            c.execute(text('SELECT pg_advisory_xact_lock(30003)'))
            self._authorized(c, actor, 'identity.manage')
            self._target(c, user_id)
            self._assign_roles(c, user_id, roles, actor.user_id)
            self._audit(c, 'ROLES_CHANGE', 'SUCCESS', actor.user_id, entity=user_id)

    def _target(self, c, user_id):
        if not c.execute(text('SELECT id FROM users WHERE id=:id FOR UPDATE'), {'id': user_id}).first():
            raise IdentityError('user_not_found', 404)

    def set_status(self, actor: ActorContext, user_id: UUID, status: str) -> None:
        if status not in {'ACTIVE', 'LOCKED', 'DISABLED'}:
            raise IdentityError('invalid_status', 422)
        with self._engine.begin() as c:
            c.execute(text('SELECT pg_advisory_xact_lock(30003)'))
            self._authorized(c, actor, 'identity.manage')
            self._target(c, user_id)
            c.execute(text('UPDATE users SET user_status=:status,failed_logins=0,blocked_until=NULL,updated_at=:now WHERE id=:id'),
                      dict(id=user_id, status=status, now=self._clock()))
            if status != 'ACTIVE':
                c.execute(text('DELETE FROM auth_sessions WHERE user_id=:id'), {'id': user_id})
            self._audit(c, 'STATUS_CHANGE', 'SUCCESS', actor.user_id, entity=user_id)
