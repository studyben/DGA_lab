"""Public identity application interface. HTTP and trusted operator tools use this seam."""
from dataclasses import dataclass
import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from enum import StrEnum
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


def _append_audit(
    connection: Connection,
    *,
    occurred_at: datetime,
    action_code: str,
    result: str,
    actor_user_id: UUID | None = None,
    claimed_username: str | None = None,
    entity_id: UUID | None = None,
) -> None:
    connection.execute(
        text(
            """INSERT INTO audit_logs
            (id,actor_user_id,claimed_username,action_code,result,occurred_at,entity_id)
            VALUES (:id,:actor,:claimed,:action,:result,:time,:entity)"""
        ),
        {
            'id': uuid4(),
            'actor': actor_user_id,
            'claimed': claimed_username,
            'action': action_code,
            'result': result,
            'time': occurred_at,
            'entity': entity_id,
        },
    )


class AuditTrail:
    """Append business audit events inside the caller's database transaction."""

    def __init__(self, *, clock: Callable[[], datetime] | None = None):
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def append(
        self,
        connection: Connection,
        actor: ActorContext,
        action: StrEnum,
        *,
        entity_id: UUID,
        result: str = 'SUCCESS',
    ) -> None:
        if result not in {'SUCCESS', 'FAILURE'}:
            raise ValueError('invalid_audit_result')
        _append_audit(
            connection,
            occurred_at=self._clock(),
            action_code=action.value,
            result=result,
            actor_user_id=actor.user_id,
            entity_id=entity_id,
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
        _append_audit(
            connection,
            occurred_at=self._clock(),
            action_code=action,
            result=result,
            actor_user_id=user,
            claimed_username=claimed,
            entity_id=entity,
        )

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
            c.execute(text("INSERT INTO users(id,username,display_name,password_hash,credential_kind) VALUES (:id,:username,:name,:hash,'RECOVERY')"),
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
            valid_password = _password_ok(password, (user['password_hash'] or DUMMY_HASH) if user else DUMMY_HASH)
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
                action_code,result,occurred_at,entity_id,before_value,after_value
                FROM audit_logs ORDER BY occurred_at,id LIMIT :limit'''),
                {'limit': limit}).mappings()]

    def _authorized(self, c, actor, permission):
        user = c.execute(text('SELECT * FROM users WHERE id=:id AND user_status=\'ACTIVE\' FOR UPDATE'), {'id': actor.user_id}).mappings().first()
        if not user:
            raise IdentityError('permission_denied', 403)
        require_permission(self._actor(c, user), permission)

    def provision_user(self, actor: ActorContext, username: str, display_name: str, password: str, roles: list[str]) -> UUID:
        """Provision a local recovery administrator, never ordinary employee passwords."""
        _validate_password(password)
        username = username.strip().lower()
        if not 1 <= len(username) <= 80 or not 1 <= len(display_name) <= 150:
            raise IdentityError('invalid_user', 422)
        with self._management_transaction(actor, 'USER_CREATE', None) as c:
            # Serialize uniqueness checking without exposing a database exception to callers.
            c.execute(text('SELECT pg_advisory_xact_lock(30003)'))
            self._authorized(c, actor, 'identity.manage')
            if 'system_admin' not in roles:
                raise IdentityError('local_admin_required', 422)
            if 'management_readonly' in roles:
                raise IdentityError('legacy_role_not_assignable', 422)
            if c.execute(text('SELECT 1 FROM users WHERE lower(username)=:username'), {'username': username}).first():
                raise IdentityError('username_taken', 409)
            user_id = uuid4()
            c.execute(text("INSERT INTO users(id,username,display_name,password_hash,credential_kind) VALUES (:id,:username,:name,:hash,'RECOVERY')"),
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
        with self._management_transaction(actor, 'ROLES_CHANGE', user_id) as c:
            c.execute(text('SELECT pg_advisory_xact_lock(30003)'))
            current = self._manager(c, actor)
            user = self._target(c, user_id)
            before = self._actor(c, user).roles
            self._roles_policy(c, current, user, roles)
            if 'system_admin' not in roles:
                self._protect_local_admin(c, user_id)
            self._assign_roles(c, user_id, roles, actor.user_id)
            c.execute(text('UPDATE users SET revision=revision+1,updated_at=:now WHERE id=:id'),
                      {'now': self._clock(), 'id': user_id})
            self._identity_event(c, current, 'ROLES_CHANGE', user_id,
                                 {'roles': sorted(before)}, {'roles': sorted(set(roles))})

    def _target(self, c, user_id):
        row = c.execute(text('SELECT * FROM users WHERE id=:id FOR UPDATE'), {'id': user_id}).mappings().first()
        if not row:
            raise IdentityError('user_not_found', 404)
        return row

    def _manager(self, c, actor):
        user = self._target(c, actor.user_id)
        current = self._actor(c, user)
        if user['user_status'] != 'ACTIVE' or current.must_change_password or not current.permissions.intersection(
                {'identity.manage', 'identity.ordinary.manage', 'identity.am.manage'}):
            raise IdentityError('permission_denied', 403)
        return current

    def role_migration_impact(self) -> list[dict]:
        """Read-only trusted operator preview; works against the pre-0025 schema."""
        from .policy import POLICY
        with self._engine.connect().execution_options(isolation_level='REPEATABLE READ') as c:
            result = []
            for user in c.execute(text('SELECT * FROM users ORDER BY username,id')).mappings():
                actor = self._actor(c, user)
                proposed = set()
                for role in actor.roles:
                    if role in POLICY:
                        proposed.update(POLICY[role])
                    else:
                        proposed.update(c.execute(text('''SELECT p.permission_code FROM permissions p
                            JOIN role_permissions rp ON rp.permission_id=p.id JOIN roles r ON r.id=rp.role_id
                            WHERE r.role_code=:role'''), {'role': role}).scalars())
                result.append({'user_id': str(user['id']), 'username': user['username'],
                    'status': user['user_status'], 'roles': sorted(actor.roles),
                    'added_permissions': sorted(proposed - actor.permissions),
                    'removed_permissions': sorted(actor.permissions - proposed),
                    'requires_explicit_mapping': 'management_readonly' in actor.roles})
            return result

    def _user_view(self, c, user):
        return {**{key: user[key] for key in ('id', 'username', 'display_name', 'user_status',
                'revision', 'credential_kind', 'blocked_until', 'last_login_at')},
                'roles': sorted(self._actor(c, user).roles)}

    def user_detail(self, actor: ActorContext, user_id: UUID) -> dict:
        with self._engine.begin() as c:
            c.execute(text('SELECT pg_advisory_xact_lock(30003)'))
            current = self._manager(c, actor)
            user = self._target(c, user_id)
            return {**self._user_view(c, user), 'actions': self._available_actions(c, current, user)}

    def _available_actions(self, c, actor, user):
        actions = []
        try:
            self._ordinary_policy(c, actor, user)
            actions.append('profile')
            for status in ('ACTIVE', 'LOCKED', 'DISABLED'):
                if status == user['user_status'] and not (status == 'ACTIVE' and user['blocked_until']):
                    continue
                if user['user_status'] == 'DISABLED' and 'identity.manage' not in actor.permissions:
                    continue
                if status != 'ACTIVE':
                    try:
                        self._protect_local_admin(c, user['id'])
                    except IdentityError:
                        continue
                actions.append('status:' + status)
        except IdentityError:
            pass
        old = self._actor(c, user).roles
        for code in c.execute(text('SELECT role_code FROM roles WHERE is_active ORDER BY role_code')).scalars():
            requested = old - {code} if code in old else old | {code}
            try:
                self._roles_policy(c, actor, user, requested)
                if 'system_admin' not in requested:
                    self._protect_local_admin(c, user['id'])
                actions.append('roles:' + code)
            except IdentityError:
                continue
        return actions

    def update_profile(self, actor: ActorContext, user_id: UUID, display_name: str,
                       *, expected_revision: int) -> None:
        display_name = display_name.strip()
        if not 1 <= len(display_name) <= 150:
            raise IdentityError('invalid_user', 422)
        with self._management_transaction(actor, 'PROFILE_CHANGE', user_id) as c:
            c.execute(text('SELECT pg_advisory_xact_lock(30003)'))
            current = self._manager(c, actor)
            user = self._target(c, user_id)
            self._ordinary_policy(c, current, user)
            if user['revision'] != expected_revision:
                raise IdentityError('stale_user', 409)
            c.execute(text('UPDATE users SET display_name=:name,revision=revision+1,updated_at=:now WHERE id=:id'),
                      {'name': display_name, 'now': self._clock(), 'id': user_id})
            self._identity_event(c, current, 'PROFILE_CHANGE', user_id,
                                 {'display_name': user['display_name']}, {'display_name': display_name})

    def list_users(self, actor: ActorContext, *, query: str = '', status: str | None = None,
                   role: str | None = None, page: int = 1) -> dict:
        if len(query) > 150 or not 1 <= page <= 100000 or status not in {None, 'ACTIVE', 'LOCKED', 'DISABLED'}:
            raise IdentityError('invalid_user_query', 422)
        condition = '''FROM users u WHERE position(lower(:query) in lower(u.username||' '||u.display_name))>0
            AND (CAST(:status AS text) IS NULL OR u.user_status=:status)
            AND (CAST(:role AS text) IS NULL OR EXISTS (SELECT 1 FROM user_roles ur JOIN roles r ON r.id=ur.role_id
                WHERE ur.user_id=u.id AND r.role_code=:role AND r.is_active))'''
        params = {'query': query.strip(), 'status': status, 'role': role, 'offset': (page-1)*20}
        with self._engine.begin() as c:
            c.execute(text('SELECT pg_advisory_xact_lock(30003)'))
            self._manager(c, actor)
            total = c.execute(text('SELECT count(*) ' + condition), params).scalar_one()
            rows = c.execute(text('SELECT u.* ' + condition + ' ORDER BY u.username,u.id LIMIT 20 OFFSET :offset'), params).mappings()
            return {'items': [self._user_view(c, user) for user in rows], 'total': total, 'page': page}

    def role_catalog(self, actor: ActorContext) -> list[dict]:
        with self._engine.begin() as c:
            c.execute(text('SELECT pg_advisory_xact_lock(30003)'))
            self._manager(c, actor)
            return [dict(row) for row in c.execute(text('''SELECT r.role_code,r.role_name,
                r.role_code<>'management_readonly' AS assignable,
                coalesce(array_agg(p.permission_code ORDER BY p.permission_code)
                  FILTER(WHERE p.permission_code IS NOT NULL),ARRAY[]::varchar[]) AS permissions
                FROM roles r LEFT JOIN role_permissions rp ON rp.role_id=r.id
                LEFT JOIN permissions p ON p.id=rp.permission_id WHERE r.is_active
                GROUP BY r.id ORDER BY r.role_code''')).mappings()]

    def _roles_policy(self, c, actor, user, requested):
        old = self._actor(c, user).roles
        if 'identity.manage' not in actor.permissions:
            if (user['id'] == actor.user_id or old.intersection({'system_admin', 'lab_admin'})
                    or user['credential_kind'] == 'RECOVERY'):
                raise IdentityError('permission_denied', 403)
            delta = set(requested) ^ old
            if 'identity.ordinary.manage' in actor.permissions:
                if delta.intersection({'system_admin', 'lab_admin', 'management_readonly'}):
                    raise IdentityError('permission_denied', 403)
            elif not delta.issubset({'asset_manager'}):
                raise IdentityError('permission_denied', 403)
        if 'management_readonly' in requested and 'management_readonly' not in old:
            raise IdentityError('legacy_role_not_assignable', 422)

    def _identity_event(self, c, actor, action, user_id, before, after):
        c.execute(text('''INSERT INTO audit_logs(id,actor_user_id,action_code,result,occurred_at,
            entity_id,before_value,after_value) VALUES (:id,:actor,:action,'SUCCESS',:time,:entity,
            CAST(:before AS jsonb),CAST(:after AS jsonb))'''),
            {'id': uuid4(), 'actor': actor.user_id, 'action': action, 'time': self._clock(),
             'entity': user_id, 'before': json.dumps(before), 'after': json.dumps(after)})

    @contextmanager
    def _management_transaction(self, actor, action, user_id):
        try:
            with self._engine.begin() as c:
                yield c
        except IdentityError:
            # Business rollback must not erase evidence of a rejected management attempt.
            with self._engine.begin() as c:
                existing = c.execute(text('SELECT id FROM users WHERE id=:id'), {'id': actor.user_id}).scalar()
                self._audit(c, action, 'FAILURE', existing, entity=user_id)
            raise

    def change_roles(self, actor: ActorContext, user_id: UUID, *, add: list[str], remove: list[str],
                     expected_revision: int) -> None:
        with self._management_transaction(actor, 'ROLES_CHANGE', user_id) as c:
            c.execute(text('SELECT pg_advisory_xact_lock(30003)'))
            current = self._manager(c, actor)
            user = self._target(c, user_id)
            before = self._actor(c, user).roles
            if set(add) & set(remove):
                raise IdentityError('invalid_roles', 422)
            available = set(c.execute(text('SELECT role_code FROM roles WHERE is_active')).scalars())
            if not (set(add) | set(remove)).issubset(available):
                raise IdentityError('invalid_roles', 422)
            attempted = set(add) | set(remove)
            if 'identity.manage' not in current.permissions:
                if 'identity.ordinary.manage' in current.permissions:
                    denied = attempted.intersection({'system_admin', 'lab_admin', 'management_readonly'})
                else:
                    denied = attempted - {'asset_manager'}
                if denied:
                    raise IdentityError('permission_denied', 403)
            # Validate attempted deltas too: even a no-op cannot smuggle privileged roles.
            self._roles_policy(c, current, user, before | set(add))
            self._roles_policy(c, current, user, before - set(remove))
            after = (before | set(add)) - set(remove)
            if user['revision'] != expected_revision:
                raise IdentityError('stale_user', 409)
            if 'system_admin' not in after:
                self._protect_local_admin(c, user_id)
            self._assign_roles(c, user_id, list(after), current.user_id)
            c.execute(text('UPDATE users SET revision=revision+1,updated_at=:now WHERE id=:id'),
                      {'now': self._clock(), 'id': user_id})
            self._identity_event(c, current, 'ROLES_CHANGE', user_id,
                                 {'roles': sorted(before)}, {'roles': sorted(after)})

    def _ordinary_policy(self, c, actor, user):
        if 'identity.manage' in actor.permissions:
            return
        if ('identity.ordinary.manage' not in actor.permissions
                or self._actor(c, user).roles.intersection({'system_admin', 'lab_admin'})
                or user['credential_kind'] == 'RECOVERY'):
            raise IdentityError('permission_denied', 403)

    def set_status(self, actor: ActorContext, user_id: UUID, status: str,
                   *, expected_revision: int | None = None) -> None:
        if status not in {'ACTIVE', 'LOCKED', 'DISABLED'}:
            raise IdentityError('invalid_status', 422)
        with self._management_transaction(actor, 'STATUS_CHANGE', user_id) as c:
            c.execute(text('SELECT pg_advisory_xact_lock(30003)'))
            current = self._manager(c, actor)
            user = self._target(c, user_id)
            self._ordinary_policy(c, current, user)
            if user['user_status'] == 'DISABLED' and status != 'DISABLED' and 'identity.manage' not in current.permissions:
                raise IdentityError('permission_denied', 403)
            if expected_revision is not None and expected_revision != user['revision']:
                raise IdentityError('stale_user', 409)
            if status != 'ACTIVE':
                self._protect_local_admin(c, user_id)
            c.execute(text('UPDATE users SET user_status=:status,failed_logins=0,blocked_until=NULL,revision=revision+1,updated_at=:now WHERE id=:id'),
                      dict(id=user_id, status=status, now=self._clock()))
            if status != 'ACTIVE':
                c.execute(text('DELETE FROM auth_sessions WHERE user_id=:id'), {'id': user_id})
            self._identity_event(c, current, 'STATUS_CHANGE', user_id,
                                 {'status': user['user_status']}, {'status': status})

    def _protect_local_admin(self, c, user_id):
        # Every account mutation holds advisory lock 30003 before reading this set.
        administrators = set(c.execute(text('''SELECT u.id FROM users u
            JOIN user_roles ur ON ur.user_id=u.id JOIN roles r ON r.id=ur.role_id
            WHERE u.user_status='ACTIVE' AND u.password_hash IS NOT NULL
              AND u.password_hash<>'' AND r.role_code='system_admin' AND r.is_active''')).scalars())
        if administrators == {user_id}:
            raise IdentityError('last_local_admin', 409)

    def recover_local_admin(self, username: str, password: str) -> None:
        """Trusted server operator only. Never expose as an HTTP password-reset route."""
        _validate_password(password)
        with self._engine.begin() as c:
            c.execute(text('SELECT pg_advisory_xact_lock(30003)'))
            user = c.execute(text('''SELECT * FROM users WHERE lower(username)=:username
                FOR UPDATE'''), {'username': username.strip().lower()}).mappings().first()
            if (not user or not user['password_hash'] or user['user_status'] == 'DISABLED'
                    or 'system_admin' not in self._actor(c, user).roles):
                raise IdentityError('local_recovery_unavailable', 409)
            c.execute(text('''UPDATE users SET password_hash=:password,must_change_password=TRUE,
                user_status='ACTIVE',failed_logins=0,blocked_until=NULL,revision=revision+1,updated_at=:now WHERE id=:id'''),
                {'password': HASHER.hash(password), 'id': user['id'], 'now': self._clock()})
            c.execute(text('DELETE FROM auth_sessions WHERE user_id=:id'), {'id': user['id']})
            self._audit(c, 'LOCAL_ADMIN_RECOVERY', 'SUCCESS', entity=user['id'])
