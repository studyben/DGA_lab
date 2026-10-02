from fastapi.testclient import TestClient
from dga.main import create_app
from dga.shared.config import Settings
from tests.test_identity_management import identity, CHANGED
from tests.test_oidc import KEY, oidc_context
from urllib.parse import parse_qs, urlsplit


def test_oidc_configuration_http_requires_admin_csrf_and_never_echoes_secret(identity, database_url):
    settings = Settings(database_url=database_url, cookie_secure=False, auth_allowed_origins='http://testserver',
        oidc_encryption_key=KEY, oidc_allowed_hosts='tenant.example',
        oidc_callback_url='http://127.0.0.1:18118/api/auth/oidc/callback')
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/auth/oidc/available').json() == {'enabled': False}
        assert client.get('/api/auth/oidc/configuration').status_code == 401
        login = client.post('/api/auth/login', headers={'Origin': 'http://testserver'},
            json={'username': 'admin', 'password': CHANGED}).json()
        headers = {'Origin': 'http://testserver', 'X-CSRF-Token': login['csrf_token']}
        body = {'issuer': 'https://tenant.example', 'client_id': 'client', 'client_secret': 'never-echo-this'}
        path = '/api/auth/oidc/candidates'
        assert client.post(path, json=body).status_code == 403
        created = client.post(path, json=body, headers=headers)
        assert created.status_code == 201
        view = client.get('/api/auth/oidc/configuration')
        assert view.headers['cache-control'] == 'no-store'
        assert 'never-echo-this' not in view.text + created.text
        assert view.json()['active_id'] is None
        assert client.post('/api/auth/oidc/start').status_code == 403
        callback = client.get('/api/auth/oidc/callback?state=bad&code=secret-code', follow_redirects=False)
        assert callback.status_code == 303
        assert 'secret-code' not in callback.headers['location']
        assert client.get('/api/auth/session').status_code == 200


def test_http_test_activate_login_cookie_and_callback_replay(oidc_context, database_url):
    service, admin, candidate, state = oidc_context
    settings = Settings(database_url=database_url, cookie_secure=False, auth_allowed_origins='http://127.0.0.1:18118',
        oidc_encryption_key=KEY, oidc_allowed_hosts='tenant.example',
        oidc_callback_url='http://127.0.0.1:18118/api/auth/oidc/callback')
    with TestClient(create_app(settings, oidc_provider=service._provider)) as client:
        client.cookies.set('dga_session', admin.token)
        headers = {'Origin': 'http://127.0.0.1:18118', 'X-CSRF-Token': admin.csrf_token}
        def finish(response):
            assert response.status_code == 200
            assert 'HttpOnly' in response.headers['set-cookie']
            assert 'SameSite=lax' in response.headers['set-cookie']
            query = parse_qs(urlsplit(response.json()['authorization_url']).query)
            state['nonce'] = query['nonce'][0]
            path = '/api/auth/oidc/callback?state=' + query['state'][0] + '&code=code'
            return client.get(path, follow_redirects=False), path
        proof_response, path = finish(client.post(f'/api/auth/oidc/candidates/{candidate}/test', headers=headers))
        assert proof_response.headers['location'] == '/settings/sso?oidc=tested'
        assert client.get('/api/auth/session').json()['actor']['id'] == str(admin.actor.user_id)
        proof = client.get('/api/auth/oidc/configuration').json()['proofs'][0]
        payload = {'config_id': str(candidate), 'proof_id': proof['id'], 'expected_revision': 0}
        assert client.post('/api/auth/oidc/activate', json=payload).status_code == 403
        assert client.post('/api/auth/oidc/activate', headers=headers, json=payload).status_code == 200
        assert client.get(path, follow_redirects=False).headers['location'].endswith('oidc_flow_invalid')
        client.cookies.clear()
        response, path = finish(client.post('/api/auth/oidc/start', headers={'Origin': 'http://127.0.0.1:18118'}))
        assert response.headers['location'] == '/assets'
        assert 'Max-Age=28800' in response.headers['set-cookie']
        session = client.get('/api/auth/session').json()
        assert session['roles'] == ['field_engineer']
        assert session['local_password_available'] is False
        assert client.get('/api/auth/oidc/configuration').status_code == 403
        assert client.get(path, follow_redirects=False).headers['location'].endswith('oidc_flow_invalid')
