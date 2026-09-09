from uuid import uuid4
import pytest

from fastapi.testclient import TestClient

from dga.main import create_app
from dga.shared.config import Settings
from dga.shared.auth.public import IdentityService
from sqlalchemy import create_engine, text

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


def test_csrf_origin_validation_and_password_error_redaction(database_url):
    engine = create_engine(database_url)
    service = IdentityService(engine)
    service.bootstrap_admin('admin', 'Admin', INITIAL)
    with TestClient(create_app(Settings(database_url=database_url, cookie_secure=False))) as client:
        payload = {'username': 'admin', 'password': INITIAL}
        assert client.post('/api/auth/login', json=payload).status_code == 403
        assert client.post('/api/auth/login', json=payload, headers={'Origin': 'https://evil.example'}).status_code == 403
        login = client.post('/api/auth/login', json=payload, headers=ORIGIN)
        csrf = login.json()['csrf_token']
        old_cookie = client.cookies.get('dga_session')
        data = {'current_password': INITIAL, 'new_password': CHANGED}
        assert client.post('/api/auth/password', json=data, headers=ORIGIN).status_code == 403
        assert client.post('/api/auth/password', json=data, headers={**ORIGIN, 'X-CSRF-Token': 'wrong'}).status_code == 403
        invalid = client.post('/api/auth/password', json={**data, 'new_password': 'secret-short'}, headers={**ORIGIN, 'X-CSRF-Token': csrf})
        assert invalid.status_code == 422 and 'secret-short' not in invalid.text and INITIAL not in invalid.text
        changed = client.post('/api/auth/password', json=data, headers={**ORIGIN, 'X-CSRF-Token': csrf})
        assert changed.status_code == 200
        assert client.cookies.get('dga_session') != old_cookie
        with pytest.raises(Exception, match='session_expired'):
            service.session(old_cookie)
        assert client.post('/api/auth/logout', headers={**ORIGIN, 'X-CSRF-Token': csrf}).status_code == 403
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
