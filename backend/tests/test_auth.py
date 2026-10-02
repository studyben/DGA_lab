from uuid import uuid4
import pytest

from fastapi.testclient import TestClient

from dga.main import create_app
from dga.shared.config import Settings
from dga.shared.auth.public import IdentityService
from sqlalchemy import create_engine, text
from tests.identity_seed import seed_legacy_user

ORIGIN = {'Origin': 'http://127.0.0.1:8080'}
INITIAL = 'Initial test passphrase 43!'
CHANGED = 'Changed test passphrase 87!'


@pytest.fixture(autouse=True)
def clean_identity(database_url):
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text('TRUNCATE auth_sessions,user_roles,audit_logs,users CASCADE'))
    engine.dispose()


def test_failed_login_and_password_change_are_audited_without_secrets(database_url):
    from dga.shared.auth.public import IdentityError
    engine = create_engine(database_url)
    service = IdentityService(engine)
    service.bootstrap_admin('admin', 'Admin', INITIAL)
    with pytest.raises(IdentityError):
        service.login('unknown', INITIAL)
    with pytest.raises(IdentityError):
        service.login('admin', 'incorrect')
    initial = service.login('admin', INITIAL)
    changed = service.change_password(initial.token, INITIAL, CHANGED)
    events = service.audit_events(changed.actor)
    failures = [event for event in events if event['action_code'] == 'LOGIN' and event['result'] == 'FAILURE']
    assert len(failures) == 2
    assert failures[0]['actor_user_id'] is None
    assert str(failures[1]['actor_user_id']) == str(changed.actor.user_id)
    assert all(event['occurred_at'].tzinfo is not None for event in events)
    assert INITIAL not in str(events) and CHANGED not in str(events) and changed.token not in str(events)
    assert any(event['action_code'] == 'PASSWORD_CHANGE' and event['result'] == 'SUCCESS' for event in events)
    engine.dispose()


def test_first_login_password_change_and_logout(database_url):
    engine = create_engine(database_url)
    service = IdentityService(engine)
    username = 'first-' + uuid4().hex
    service.bootstrap_admin(username, 'Test administrator', INITIAL)
    try:
        with TestClient(create_app(Settings(database_url=database_url, cookie_secure=False))) as client:
            assert client.get('/api/auth/session').status_code == 401
            response = client.post('/api/auth/login', json={'username': username, 'password': INITIAL}, headers=ORIGIN)
            assert response.status_code == 200
            assert response.json()['must_change_password'] is True
            assert 'httponly' in response.headers['set-cookie'].lower()
            csrf = response.json()['csrf_token']
            changed = client.post('/api/auth/password', json={'current_password': INITIAL, 'new_password': CHANGED},
                                  headers={**ORIGIN, 'X-CSRF-Token': csrf})
            assert changed.status_code == 200
            assert changed.json()['must_change_password'] is False
            assert client.get('/api/auth/session').json()['actor']['username'] == username
            assert client.post('/api/auth/logout', headers={**ORIGIN, 'X-CSRF-Token': changed.json()['csrf_token']}).status_code == 204
            assert client.get('/api/auth/session').status_code == 401
    finally:
        engine.dispose()


@pytest.mark.parametrize('allowed_origin', ['http://127.0.0.1:8080', 'http://localhost:5173'])
def test_csrf_origin_validation_and_password_error_redaction(database_url, allowed_origin):
    engine = create_engine(database_url)
    service = IdentityService(engine)
    service.bootstrap_admin('admin', 'Admin', INITIAL)
    with TestClient(create_app(Settings(database_url=database_url, cookie_secure=False,
                                      auth_allowed_origins=allowed_origin))) as client:
        payload = {'username': 'admin', 'password': INITIAL}
        origin = {'Origin': allowed_origin}
        assert client.post('/api/auth/login', json=payload).status_code == 403
        assert client.post('/api/auth/login', json=payload, headers={'Origin': 'https://evil.example'}).status_code == 403
        login = client.post('/api/auth/login', json=payload, headers=origin)
        csrf = login.json()['csrf_token']
        old_cookie = client.cookies.get('dga_session')
        data = {'current_password': INITIAL, 'new_password': CHANGED}
        assert client.post('/api/auth/password', json=data, headers=origin).status_code == 403
        assert client.post('/api/auth/password', json=data, headers={**origin, 'X-CSRF-Token': 'wrong'}).status_code == 403
        assert client.post('/api/auth/password', json=data,
                           headers=[(b'Origin', allowed_origin.encode()), (b'X-CSRF-Token', b'\xff')]).status_code == 403
        invalid = client.post('/api/auth/password', json={**data, 'new_password': 'secret-short'}, headers={**origin, 'X-CSRF-Token': csrf})
        assert invalid.status_code == 422 and 'secret-short' not in invalid.text and INITIAL not in invalid.text
        changed = client.post('/api/auth/password', json=data, headers={**origin, 'X-CSRF-Token': csrf})
        assert changed.status_code == 200
        assert client.cookies.get('dga_session') != old_cookie
        with pytest.raises(Exception, match='session_expired'):
            service.session(old_cookie)
        assert client.post('/api/auth/logout', headers={**origin, 'X-CSRF-Token': csrf}).status_code == 403
    engine.dispose()


def test_expiry_throttle_recovery_and_single_bootstrap(database_url):
    from datetime import datetime, timedelta, timezone
    from dga.shared.auth.public import IdentityError
    engine = create_engine(database_url)
    now = [datetime(2026, 1, 1, tzinfo=timezone.utc)]
    service = IdentityService(engine, clock=lambda: now[0], session_hours=1)
    service.bootstrap_admin('admin', 'Admin', INITIAL)
    with pytest.raises(IdentityError, match='already_initialized'):
        service.bootstrap_admin('second', 'Second', INITIAL)
    for _ in range(5):
        with pytest.raises(IdentityError, match='invalid_credentials'):
            service.login('admin', 'incorrect')
    with pytest.raises(IdentityError, match='invalid_credentials'):
        service.login('admin', INITIAL)
    now[0] += timedelta(minutes=16)
    session = service.login(' ADMIN ', INITIAL)
    now[0] += timedelta(hours=1)
    with pytest.raises(IdentityError, match='session_expired'):
        service.session(session.token)
    assert service.login('admin', INITIAL).actor.username == 'admin'
    engine.dispose()


def test_password_rotation_cookie_respects_remaining_absolute_lifetime(database_url):
    from datetime import datetime, timedelta, timezone
    from http.cookies import SimpleCookie
    engine = create_engine(database_url)
    earlier = datetime.now(timezone.utc) - timedelta(hours=7)
    service = IdentityService(engine, clock=lambda: earlier)
    service.bootstrap_admin('admin', 'Admin', INITIAL)
    original = service.login('admin', INITIAL)
    with TestClient(create_app(Settings(database_url=database_url, cookie_secure=False, session_hours=24))) as client:
        client.cookies.set('dga_session', original.token)
        response = client.post('/api/auth/password', headers={**ORIGIN, 'X-CSRF-Token': original.csrf_token},
            json={'current_password': INITIAL, 'new_password': CHANGED})
        assert response.status_code == 200
        assert datetime.fromisoformat(response.json()['expires_at']) == original.expires_at
        cookie = SimpleCookie(response.headers['set-cookie'])['dga_session']
        assert 3500 < int(cookie['max-age']) <= 3600
    engine.dispose()


def test_parallel_password_change_allows_only_one_winner(database_url):
    from concurrent.futures import ThreadPoolExecutor
    from dga.shared.auth.public import IdentityError
    engine = create_engine(database_url)
    service = IdentityService(engine)
    service.bootstrap_admin('admin', 'Admin', INITIAL)
    initial = service.login('admin', INITIAL)
    def change():
        try:
            return service.change_password(initial.token, INITIAL, CHANGED)
        except IdentityError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: change(), range(2)))
    winners = [value for value in results if value is not None]
    assert len(winners) == 1
    assert not service.session(winners[0].token).actor.must_change_password
    with pytest.raises(IdentityError):
        service.session(initial.token)
    engine.dispose()


@pytest.mark.parametrize('role,lab_allowed,asset_write', [
    ('system_admin', True, True), ('asset_manager', True, False), ('lab_admin', True, True),
    ('analyst', True, False), ('field_engineer', True, False), ('management_readonly', True, False),
    ('management', True, False),
])
def test_roles_enforced_at_public_module_and_http_seams(database_url, role, lab_allowed, asset_write):
    from dga.shared.auth.public import IdentityError, require_permission
    engine = create_engine(database_url)
    service = IdentityService(engine)
    service.bootstrap_admin('admin', 'Admin', INITIAL)
    login = service.login('admin', INITIAL)
    admin = service.change_password(login.token, INITIAL, CHANGED).actor
    seed_legacy_user(database_url, 'member', 'Member', INITIAL, [role])
    with TestClient(create_app(Settings(database_url=database_url, cookie_secure=False))) as client:
        assert client.get('/api/modules').status_code == 401
        assert client.get('/api/laboratory/access').status_code == 401
        response = client.post('/api/auth/login', json={'username': 'member', 'password': INITIAL}, headers=ORIGIN)
        assert client.get('/api/assets/access').json()['code'] == 'password_change_required'
        client.post('/api/auth/password', json={'current_password': INITIAL, 'new_password': CHANGED},
                    headers={**ORIGIN, 'X-CSRF-Token': response.json()['csrf_token']})
        assert client.get('/api/assets/access').status_code == 200
        assert client.get('/api/condition-analysis/access').status_code == 200
        assert client.get('/api/laboratory/access').status_code == (200 if lab_allowed else 403)
        modules = [module['code'] for module in client.get('/api/modules').json()]
        assert ('laboratory' in modules) == lab_allowed
        actor = service.session(client.cookies.get('dga_session')).actor
        if asset_write:
            require_permission(actor, 'assets.write')
        else:
            with pytest.raises(IdentityError, match='permission_denied'):
                require_permission(actor, 'assets.write')
    engine.dispose()


def test_account_status_and_role_changes_take_effect_on_existing_sessions(database_url):
    from dga.shared.auth.public import IdentityError
    from dga.shared.auth.public import require_permission
    engine = create_engine(database_url)
    service = IdentityService(engine)
    admin_id = service.bootstrap_admin('admin', 'Admin', INITIAL)
    login = service.login('admin', INITIAL)
    admin = service.change_password(login.token, INITIAL, CHANGED).actor
    member_id = seed_legacy_user(database_url, 'member', 'Member', INITIAL, ['lab_admin'])
    first = service.login('member', INITIAL)
    member = service.change_password(first.token, INITIAL, CHANGED)
    require_permission(service.session(member.token).actor, 'laboratory.write')
    service.set_roles(admin, member_id, ['field_engineer'])
    with pytest.raises(IdentityError, match='permission_denied'):
        require_permission(service.session(member.token).actor, 'laboratory.write')
    for status in ['LOCKED', 'DISABLED']:
        service.set_status(admin, member_id, status)
        with pytest.raises(IdentityError):
            service.login('member', CHANGED)
        with pytest.raises(IdentityError):
            service.session(member.token)
        service.set_status(admin, member_id, 'ACTIVE')
    assert service.login('member', CHANGED).actor.username == 'member'
    with pytest.raises(IdentityError):
        service.provision_user(member.actor, 'bypass', 'Bypass', INITIAL, ['system_admin'])
    # A different local recovery administrator must remain before demotion.
    service.provision_user(admin, 'recovery', 'Recovery administrator', INITIAL, ['system_admin'])
    service.set_roles(admin, admin_id, ['field_engineer'])
    with pytest.raises(IdentityError, match='permission_denied'):
        service.audit_events(admin)  # Stale formerly-admin context must not keep authority.
    engine.dispose()
