"""OIDC custody/flow acceptance; isolated provider traffic is not real Okta acceptance."""
from sqlalchemy import create_engine
from dga.shared.auth.public import IdentityService, OidcService
from tests.test_identity_management import identity, CHANGED
import pytest
import httpx
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit
from authlib.jose import JsonWebKey, JsonWebToken
from dga.shared.auth.public import IdentityError

# Public test-only encryption key, never a deployment credential.
KEY = 'LbsTTNRHHGjNpCacJPmxNYIyFVwnX-uviZEgmPMMKaI='


def test_candidate_custody_is_redacted_persistent_and_does_not_change_local_login(identity, database_url):
    _, admin = identity
    engine = create_engine(database_url)
    oidc = OidcService(engine, encryption_key=KEY, allowed_hosts={'tenant.example'},
        callback_url='http://127.0.0.1:18118/api/auth/oidc/callback')
    candidate = oidc.save_candidate(admin.actor, issuer='https://tenant.example', client_id='test-client', client_secret='isolated-client-secret')
    view = oidc.configuration(admin.actor)
    assert view['active_id'] is None
    assert view['candidates'][0]['id'] == candidate
    assert view['candidates'][0]['secret_configured'] is True
    assert 'isolated-client-secret' not in str(view)
    reopened = OidcService(engine, encryption_key=KEY, allowed_hosts={'tenant.example'},
        callback_url='http://127.0.0.1:18118/api/auth/oidc/callback')
    assert reopened.configuration(admin.actor) == view
    assert IdentityService(engine).login('admin', CHANGED).actor.user_id == admin.actor.user_id
    engine.dispose()


@pytest.fixture
def oidc_context(identity, database_url):
    from dga.shared.auth.oidc_provider import OktaProvider
    _, admin = identity
    now = datetime.now(timezone.utc)
    private = JsonWebKey.generate_key('RSA', 2048, is_private=True, options={'kid': 'test-key'})
    state = {'nonce': '', 'patch': {}, 'requests': [], 'now': now}
    def transport(request):
        state['requests'].append(request)
        if state.get('failure') == 'timeout':
            raise httpx.ReadTimeout('sensitive remote detail')
        if state.get('failure') == 'redirect':
            return httpx.Response(302, headers={'Location': 'https://untrusted.example/secret'})
        if request.url.path.endswith('openid-configuration'):
            return httpx.Response(200, json=dict(issuer='https://tenant.example',
                authorization_endpoint='https://tenant.example/authorize', token_endpoint='https://tenant.example/token',
                jwks_uri=state.get('jwks_url', 'https://tenant.example/keys')))
        if request.url.path == '/keys':
            return httpx.Response(200, json={'keys': [private.as_dict(is_private=False)]})
        if request.url.path == '/token':
            from datetime import timedelta
            state['now'] += timedelta(seconds=state.get('latency', 0))
            payload = dict(iss='https://tenant.example', sub='employee-1', aud='test-client',
                nonce=state['nonce'], iat=int(state['now'].timestamp()), auth_time=int(state['now'].timestamp()),
                exp=int(state['now'].timestamp()) + 300, name='Test employee') | state['patch']
            payload = {k: v for k, v in payload.items() if v is not None}
            header = {'alg': 'RS256', 'kid': 'test-key'} if not state.get('missing_kid') else {'alg': 'RS256'}
            key = JsonWebKey.generate_key('RSA', 2048, is_private=True) if state.get('wrong_signature') else private
            if state.get('missing_kid'):
                key = key.as_pem(is_private=True)
            token = JsonWebToken(['RS256']).encode(header, payload, key).decode()
            return httpx.Response(200, json={'id_token': token, 'access_token': 'discard-me', 'token_type': 'Bearer'})
        raise AssertionError(request.url)
    engine = create_engine(database_url)
    provider = OktaProvider({'tenant.example'}, transport=httpx.MockTransport(transport))
    service = OidcService(engine, encryption_key=KEY, allowed_hosts={'tenant.example'},
        callback_url='http://127.0.0.1:18118/api/auth/oidc/callback', clock=lambda: state['now'], provider=provider)
    candidate = service.save_candidate(admin.actor, issuer='https://tenant.example', client_id='test-client', client_secret='test-secret')
    yield service, admin, candidate, state
    engine.dispose()


def start_test(context):
    service, admin, candidate, state = context
    flow = service.start_test(admin.token, candidate)
    query = parse_qs(urlsplit(flow['authorization_url']).query)
    state['nonce'] = query['nonce'][0]
    assert query['code_challenge_method'] == ['S256']
    assert query['prompt'] == ['login']
    assert query['max_age'] == ['0']
    assert query['scope'] == ['openid profile email']
    return flow, query['state'][0]


def test_verified_test_flow_is_one_use_and_does_not_replace_local_session(oidc_context):
    service, admin, candidate, state = oidc_context
    flow, challenge = start_test(oidc_context)
    proof = service.complete_test(challenge, flow['browser_binding'], 'code', admin.token)
    assert proof['config_id'] == candidate
    assert proof['subject'] == 'employee-1'
    assert service.configuration(admin.actor)['active_id'] is None
    with pytest.raises(IdentityError, match='oidc_flow_invalid'):
        service.complete_test(challenge, flow['browser_binding'], 'code', admin.token)
    sent = [request for request in state['requests'] if request.url.path == '/token']
    assert len(sent) == 1
    assert 'code_verifier=' in sent[0].content.decode()
    assert 'refresh_token' not in sent[0].content.decode()


@pytest.mark.parametrize('patch', [
    {'nonce': 'wrong'}, {'iss': 'https://other.example'}, {'aud': 'other-client'},
    {'aud': ['test-client', 'other'], 'azp': None}, {'azp': 'other'},
    {'exp': 1}, {'iat': 9999999999}, {'auth_time': 1}, {'sub': ''}, {'exp': None},
])
def test_invalid_claims_fail_and_consume_flow(oidc_context, patch):
    service, admin, _, state = oidc_context
    flow, challenge = start_test(oidc_context)
    state['patch'] = patch
    with pytest.raises(IdentityError, match='oidc_provider_rejected'):
        service.complete_test(challenge, flow['browser_binding'], 'code', admin.token)
    with pytest.raises(IdentityError, match='oidc_flow_invalid'):
        service.complete_test(challenge, flow['browser_binding'], 'code', admin.token)


def test_wrong_browser_does_not_exchange_code(oidc_context):
    service, admin, _, state = oidc_context
    flow, challenge = start_test(oidc_context)
    with pytest.raises(IdentityError, match='oidc_flow_invalid'):
        service.complete_test(challenge, 'other-browser', 'code', admin.token)
    assert not any(request.url.path == '/token' for request in state['requests'])


@pytest.mark.parametrize('flag,value', [('failure', 'timeout'), ('failure', 'redirect'),
    ('wrong_signature', True), ('missing_kid', True), ('jwks_url', 'https://untrusted.example/keys')])
def test_provider_failures_are_safe_and_not_followed(oidc_context, flag, value):
    service, admin, _, state = oidc_context
    flow, challenge = start_test(oidc_context)
    state[flag] = value
    with pytest.raises(IdentityError, match='oidc_provider_rejected') as error:
        service.complete_test(challenge, flow['browser_binding'], 'code', admin.token)
    assert 'sensitive' not in str(error.value)
    assert all(request.url.host == 'tenant.example' for request in state['requests'])
    with pytest.raises(IdentityError, match='oidc_flow_invalid'):
        service.complete_test(challenge, flow['browser_binding'], 'code', admin.token)


def test_expiry_rejects_before_exchange(oidc_context):
    from datetime import timedelta
    service, admin, _, state = oidc_context
    flow, challenge = start_test(oidc_context)
    state['now'] += timedelta(minutes=11)
    with pytest.raises(IdentityError, match='oidc_flow_invalid'):
        service.complete_test(challenge, flow['browser_binding'], 'code', admin.token)
    assert not any(request.url.path == '/token' for request in state['requests'])


def test_competing_callbacks_only_exchange_once(oidc_context):
    from concurrent.futures import ThreadPoolExecutor
    service, admin, _, state = oidc_context
    flow, challenge = start_test(oidc_context)
    def finish(_):
        try:
            service.complete_test(challenge, flow['browser_binding'], 'code', admin.token)
            return 'success'
        except IdentityError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as workers:
        assert sorted(workers.map(finish, range(2))) == ['oidc_flow_invalid', 'success']
    assert sum(r.url.path == '/token' for r in state['requests']) == 1


def test_missing_key_and_unsafe_issuer_leave_local_recovery_available(identity, database_url):
    _, admin = identity
    engine = create_engine(database_url)
    for key in (None, 'invalid-key'):
        service = OidcService(engine, encryption_key=key)
        with pytest.raises(IdentityError, match='oidc_not_configured'):
            service.save_candidate(admin.actor, issuer='https://tenant.example', client_id='client', client_secret='secret')
        assert IdentityService(engine).login('admin', CHANGED).actor.user_id == admin.actor.user_id
    service = OidcService(engine, encryption_key=KEY, allowed_hosts={'tenant.example'},
        callback_url='http://127.0.0.1:18118/api/auth/oidc/callback')
    for issuer in ('http://tenant.example', 'https://tenant.example.evil/', 'https://tenant.example@evil/',
                   'https://tenant.example:444', 'https://tenant.example?a=1'):
        with pytest.raises(IdentityError):
            service.save_candidate(admin.actor, issuer=issuer, client_id='client', client_secret='secret')
    engine.dispose()


def test_stale_administrator_cannot_save_or_complete_test(oidc_context, identity):
    service, admin, _, state = oidc_context
    identity_service, _ = identity
    from tests.test_identity_management import INITIAL
    identity_service.provision_user(admin.actor, 'backup', 'Backup', INITIAL, ['system_admin'])
    flow, challenge = start_test(oidc_context)
    identity_service.set_roles(admin.actor, admin.actor.user_id, ['field_engineer'])
    with pytest.raises(IdentityError, match='permission_denied'):
        service.save_candidate(admin.actor, issuer='https://tenant.example', client_id='client', client_secret='secret')
    with pytest.raises(IdentityError, match='permission_denied'):
        service.complete_test(challenge, flow['browser_binding'], 'code', admin.token)
    assert not any(r.url.path == '/token' for r in state['requests'])


def test_rejected_candidate_and_provider_attempts_have_safe_audit(oidc_context, identity):
    service, admin, _, state = oidc_context
    identity_service, _ = identity
    with pytest.raises(IdentityError):
        service.save_candidate(admin.actor, issuer='https://bad.example', client_id='client', client_secret='audit-secret-never-store')
    flow, challenge = start_test(oidc_context)
    state['failure'] = 'timeout'
    with pytest.raises(IdentityError):
        service.complete_test(challenge, flow['browser_binding'], 'code', admin.token)
    audit = identity_service.audit_events(admin.actor)
    assert any(event['action_code'] == 'OIDC_CANDIDATE_SAVE' and event['result'] == 'FAILURE' for event in audit)
    assert any(event['action_code'] == 'OIDC_TEST' and event['result'] == 'FAILURE' for event in audit)
    assert 'audit-secret-never-store' not in str(audit)


def test_new_token_issued_after_network_delay_is_valid(oidc_context):
    service, admin, _, state = oidc_context
    flow, challenge = start_test(oidc_context)
    state['latency'] = 2
    assert service.complete_test(challenge, flow['browser_binding'], 'code', admin.token)['subject'] == 'employee-1'


def test_handshake_expiring_during_exchange_is_rejected(oidc_context):
    service, admin, _, state = oidc_context
    flow, challenge = start_test(oidc_context)
    state['latency'] = 601
    with pytest.raises(IdentityError, match='oidc_flow_invalid'):
        service.complete_test(challenge, flow['browser_binding'], 'code', admin.token)


def test_token_expired_in_transit_is_rejected(oidc_context):
    service, admin, _, state = oidc_context
    flow, challenge = start_test(oidc_context)
    timestamp = int(state['now'].timestamp())
    state['latency'] = 2
    state['patch'] = {'iat': timestamp, 'exp': timestamp + 1}
    with pytest.raises(IdentityError, match='oidc_provider_rejected'):
        service.complete_test(challenge, flow['browser_binding'], 'code', admin.token)
