"""Identity HTTP security contract using the real application and PostgreSQL."""
from fastapi.testclient import TestClient
import pytest

from dga.main import create_app
from dga.shared.config import Settings
from tests.identity_seed import seed_legacy_user
from tests.test_identity_management import identity, INITIAL, CHANGED


def test_manager_can_search_and_edit_with_csrf_and_conflict_feedback(identity, database_url):
    service, admin = identity
    member = seed_legacy_user(database_url, 'member', 'Member', INITIAL, ['field_engineer'])
    settings = Settings(database_url=database_url, cookie_secure=False, auth_allowed_origins='http://testserver')
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/auth/users').status_code == 401
        login = client.post('/api/auth/login', headers={'Origin': 'http://testserver'},
                            json={'username': 'admin', 'password': CHANGED}).json()
        headers = {'Origin': 'http://testserver', 'X-CSRF-Token': login['csrf_token']}
        users = client.get('/api/auth/users', params={'query': 'member'})
        assert users.status_code == 200
        assert users.headers['cache-control'] == 'no-store'
        assert users.json()['total'] == 1
        path = f'/api/auth/users/{member}/profile'
        body = {'display_name': 'Updated', 'expected_revision': 0}
        assert client.put(path, json=body).status_code == 403
        assert client.put(path, headers=headers, json={**body, 'user_status': 'ACTIVE'}).status_code == 422
        assert client.put(path, headers=headers, json=body).status_code == 200
        assert client.put(path, headers=headers, json=body).status_code == 409
        assert service.user_detail(admin.actor, member)['display_name'] == 'Updated'


def test_management_http_only_allows_am_delta_and_reports_available_actions(identity, database_url):
    service, admin = identity
    seed_legacy_user(database_url, 'management', 'Management', INITIAL, ['management'])
    first = service.login('management', INITIAL)
    service.change_password(first.token, INITIAL, CHANGED)
    member = seed_legacy_user(database_url, 'member', 'Member', INITIAL, ['analyst'])
    settings = Settings(database_url=database_url, cookie_secure=False, auth_allowed_origins='http://testserver')
    with TestClient(create_app(settings)) as client:
        login = client.post('/api/auth/login', headers={'Origin': 'http://testserver'},
                            json={'username': 'management', 'password': CHANGED}).json()
        headers = {'Origin': 'http://testserver', 'X-CSRF-Token': login['csrf_token']}
        path = f'/api/auth/users/{member}'
        detail = client.get(path)
        assert detail.status_code == 200
        assert detail.json()['actions'] == ['roles:asset_manager']
        assert client.get('/api/auth/roles').status_code == 200
        assert client.put(path+'/roles', headers=headers,
            json={'add': ['asset_manager'], 'remove': [], 'expected_revision': 0}).status_code == 200
        assert client.put(path+'/roles', headers=headers,
            json={'add': ['system_admin'], 'remove': [], 'expected_revision': 1}).status_code == 403
        assert client.put(path+'/status', headers=headers,
            json={'status': 'DISABLED', 'expected_revision': 1}).status_code == 403
        assert service.user_detail(admin.actor, member)['roles'] == ['analyst', 'asset_manager']


def test_recovery_account_http_never_accepts_ordinary_roles_or_echoes_password(identity, database_url):
    _, _ = identity
    settings = Settings(database_url=database_url, cookie_secure=False, auth_allowed_origins='http://testserver')
    with TestClient(create_app(settings)) as client:
        login = client.post('/api/auth/login', headers={'Origin': 'http://testserver'},
                            json={'username': 'admin', 'password': CHANGED}).json()
        headers = {'Origin': 'http://testserver', 'X-CSRF-Token': login['csrf_token']}
        body = {'username': 'backup', 'display_name': 'Backup', 'password': INITIAL}
        assert client.post('/api/auth/users/recovery', headers=headers, json={**body, 'roles': ['analyst']}).status_code == 422
        result = client.post('/api/auth/users/recovery', headers=headers, json=body)
        assert result.status_code == 201
        assert INITIAL not in result.text
        detail = client.get('/api/auth/users/' + result.json()['id']).json()
        assert detail['credential_kind'] == 'RECOVERY'
        assert detail['roles'] == ['system_admin']


@pytest.mark.parametrize('action,body', [
    ('profile', {'display_name': 'New', 'expected_revision': 0}),
    ('roles', {'add': ['analyst'], 'remove': [], 'expected_revision': 0}),
    ('status', {'status': 'DISABLED', 'expected_revision': 0}),
])
def test_all_management_writes_reject_bad_origin_and_csrf(identity, database_url, action, body):
    service, admin = identity
    member = seed_legacy_user(database_url, 'member', 'Member', INITIAL, ['field_engineer'])
    settings = Settings(database_url=database_url, cookie_secure=False, auth_allowed_origins='http://testserver')
    with TestClient(create_app(settings)) as client:
        login = client.post('/api/auth/login', headers={'Origin': 'http://testserver'},
                            json={'username': 'admin', 'password': CHANGED}).json()
        path = f'/api/auth/users/{member}/{action}'
        for headers in [
            {'Origin': 'https://untrusted.example', 'X-CSRF-Token': login['csrf_token']},
            {'Origin': 'http://testserver', 'X-CSRF-Token': 'invalid'},
        ]:
            assert client.put(path, headers=headers, json=body).status_code == 403
        assert service.user_detail(admin.actor, member)['revision'] == 0
