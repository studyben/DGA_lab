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
            if state.get('on_exchange'):
                state.pop('on_exchange')()
            state['now'] += timedelta(seconds=state.get('latency', 0))
            payload = dict(iss='https://tenant.example', sub='employee-1', aud='test-client',
                nonce=parse_qs(request.content.decode())['code'][0] if state.get('nonce_from_code') else state['nonce'],
                iat=int(state['now'].timestamp()), auth_time=int(state['now'].timestamp()),
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


def activate(context):
    service, admin, candidate, _ = context
    flow, challenge = start_test(context)
    proof = service.complete_test(challenge, flow['browser_binding'], 'code', admin.token)
    service.activate(admin.actor, candidate, proof['proof_id'], expected_revision=0)
    return proof


def employee_login(context):
    service, _, _, state = context
    flow = service.start_login()
    query = parse_qs(urlsplit(flow['authorization_url']).query)
    state['nonce'] = query['nonce'][0]
    return service.complete_login(query['state'][0], flow['browser_binding'], 'code')


def test_verified_employee_login_is_stable_least_privilege_and_absolute(oidc_context, identity):
    from datetime import timedelta
    service, admin, _, state = oidc_context
    identity_service, _ = identity
    activate(oidc_context)
    state['patch'] = {'roles': ['system_admin'], 'groups': ['admins']}
    first = employee_login(oidc_context)
    assert first.actor.roles == frozenset({'field_engineer'})
    provisioning = [e for e in identity_service.audit_events(admin.actor) if e['action_code'] == 'OIDC_PROVISION']
    assert len(provisioning) == 1
    assert provisioning[0]['after_value']['roles'] == ['field_engineer']
    assert first.expires_at == state['now'] + timedelta(hours=8)
    identity_service.change_roles(admin.actor, first.actor.user_id, add=['analyst'], remove=[], expected_revision=0)
    second = employee_login(oidc_context)
    assert second.actor.user_id == first.actor.user_id
    assert second.actor.roles == frozenset({'field_engineer', 'analyst'})
    assert len([e for e in identity_service.audit_events(admin.actor) if e['action_code'] == 'OIDC_PROVISION']) == 1
    state['now'] += timedelta(hours=7)
    # Reconstructed identity facade shares the injected verification clock, not sliding expiry.
    clocked = IdentityService(identity_service._engine, clock=lambda: state['now'], session_hours=24)
    assert clocked.session(first.token).expires_at == first.expires_at
    state['now'] += timedelta(hours=1)
    with pytest.raises(IdentityError, match='session_expired'):
        clocked.session(first.token)


def test_candidate_requires_recent_same_admin_proof_and_stale_activation_keeps_active(oidc_context, identity):
    from tests.test_identity_management import INITIAL
    service, admin, candidate, state = oidc_context
    identity_service, _ = identity
    proof = activate(oidc_context)
    another = service.save_candidate(admin.actor, issuer='https://tenant.example', client_id='another', client_secret='another-secret')
    with pytest.raises(IdentityError, match='oidc_test_required'):
        service.activate(admin.actor, another, proof['proof_id'], expected_revision=1)
    with pytest.raises(IdentityError, match='stale_oidc_configuration'):
        service.activate(admin.actor, candidate, proof['proof_id'], expected_revision=0)
    identity_service.provision_user(admin.actor, 'backup', 'Backup', INITIAL, ['system_admin'])
    first = identity_service.login('backup', INITIAL)
    backup = identity_service.change_password(first.token, INITIAL, CHANGED)
    with pytest.raises(IdentityError, match='oidc_test_required'):
        service.activate(backup.actor, candidate, proof['proof_id'], expected_revision=1)
    assert service.configuration(admin.actor)['active_id'] == candidate


def test_external_employee_cannot_change_password_and_disabled_account_cannot_login(oidc_context, identity):
    from tests.test_identity_management import INITIAL
    service, admin, _, _ = oidc_context
    identity_service, _ = identity
    activate(oidc_context)
    employee = employee_login(oidc_context)
    with pytest.raises(IdentityError, match='password_change_failed'):
        identity_service.change_password(employee.token, INITIAL, CHANGED)
    identity_service.set_status(admin.actor, employee.actor.user_id, 'DISABLED', expected_revision=0)
    with pytest.raises(IdentityError, match='oidc_account_unavailable'):
        employee_login(oidc_context)


@pytest.mark.parametrize('hints', [ {'preferred_username': 'employee@example.com'},
    {'preferred_username': 'different', 'email': 'employee@example.com'} ])
def test_existing_username_not_auto_linked_and_explicit_proof_binding_preserves_roles(oidc_context, identity, hints):
    from tests.identity_seed import seed_legacy_user
    from tests.test_identity_management import INITIAL
    service, admin, _, state = oidc_context
    identity_service, _ = identity
    activate(oidc_context)
    target = seed_legacy_user(identity_service._engine.url.render_as_string(hide_password=False), 'employee@example.com', 'Employee', INITIAL, ['analyst'])
    state['patch'] = hints
    with pytest.raises(IdentityError, match='oidc_link_required'):
        employee_login(oidc_context)
    flow, challenge = start_test(oidc_context)
    proof = service.complete_test(challenge, flow['browser_binding'], 'code', admin.token)
    service.bind_identity(admin.actor, target, proof['proof_id'], expected_revision=0)
    employee = employee_login(oidc_context)
    assert employee.actor.user_id == target
    assert employee.actor.roles == frozenset({'analyst'})


def test_candidate_callback_is_allowlisted_immutable_and_bound_to_start_origin(oidc_context, identity):
    service, admin, _, state = oidc_context
    configured = OidcService(identity[0]._engine, encryption_key=KEY, allowed_hosts={'tenant.example'},
        callback_url='http://127.0.0.1:18118/api/auth/oidc/callback',
        callback_origins={'http://127.0.0.1:18118', 'https://portal.example'}, provider=service._provider)
    candidate = configured.save_candidate(admin.actor, issuer='https://tenant.example', client_id='test-client',
        client_secret='secret', callback_url='https://portal.example/api/auth/oidc/callback')
    with pytest.raises(IdentityError, match='oidc_callback_origin_mismatch'):
        configured.start_test(admin.token, candidate, origin='http://127.0.0.1:18118')
    for callback in ('https://evil.example/api/auth/oidc/callback', 'https://portal.example/other',
                     'https://portal.example/api/auth/oidc/callback?x=1'):
        with pytest.raises(IdentityError, match='oidc_callback_not_allowed'):
            configured.save_candidate(admin.actor, issuer='https://tenant.example', client_id='test-client',
                client_secret='secret', callback_url=callback)
    reopened = OidcService(identity[0]._engine, encryption_key=KEY, allowed_hosts={'tenant.example'},
        callback_url='http://127.0.0.1:18118/api/auth/oidc/callback',
        callback_origins={'https://portal.example'}, provider=service._provider)
    flow = reopened.start_test(admin.token, candidate, origin='https://portal.example')
    query = parse_qs(urlsplit(flow['authorization_url']).query)
    assert query['redirect_uri'] == ['https://portal.example/api/auth/oidc/callback']
    state['nonce'] = query['nonce'][0]
    proof = reopened.complete_test(query['state'][0], flow['browser_binding'], 'code', admin.token)
    token_request = [r for r in state['requests'] if r.url.path == '/token'][-1]
    assert parse_qs(token_request.content.decode())['redirect_uri'] == query['redirect_uri']
    reopened.activate(admin.actor, candidate, proof['proof_id'], expected_revision=0)
    with pytest.raises(IdentityError, match='oidc_callback_origin_mismatch'):
        reopened.start_login(origin='http://127.0.0.1:18118')


def test_test_proof_expiry_and_admin_revocation_during_exchange(oidc_context, identity):
    from datetime import timedelta
    from tests.test_identity_management import INITIAL
    service, admin, candidate, state = oidc_context
    identities, _ = identity
    proof = activate(oidc_context)
    state['now'] += timedelta(minutes=16)
    with pytest.raises(IdentityError, match='oidc_test_required'):
        service.activate(admin.actor, candidate, proof['proof_id'], expected_revision=1)
    identities.provision_user(admin.actor, 'backup', 'Backup', INITIAL, ['system_admin'])
    session = identities.login('backup', INITIAL)
    backup = identities.change_password(session.token, INITIAL, CHANGED)
    flow, challenge = start_test(oidc_context)
    state['on_exchange'] = lambda: identities.set_roles(backup.actor, admin.actor.user_id, ['field_engineer'])
    with pytest.raises(IdentityError, match='permission_denied'):
        service.complete_test(challenge, flow['browser_binding'], 'code', admin.token)
    identities.set_roles(backup.actor, admin.actor.user_id, ['system_admin'])
    assert service.configuration(admin.actor)['proofs'] == []


def test_changed_active_config_rejects_inflight_login(oidc_context, identity):
    service, admin, candidate, state = oidc_context
    proof = activate(oidc_context)
    count = identity[0].list_users(admin.actor)['total']
    state['on_exchange'] = lambda: service.activate(admin.actor, candidate, proof['proof_id'], expected_revision=1)
    with pytest.raises(IdentityError, match='stale_oidc_configuration'):
        employee_login(oidc_context)
    assert identity[0].list_users(admin.actor)['total'] == count


def test_concurrent_activations_and_employee_logins_are_serialized(oidc_context, identity):
    from concurrent.futures import ThreadPoolExecutor
    service, admin, candidate, state = oidc_context
    flow, challenge = start_test(oidc_context)
    proof = service.complete_test(challenge, flow['browser_binding'], 'code', admin.token)
    def enable(_):
        try:
            service.activate(admin.actor, candidate, proof['proof_id'], expected_revision=0)
            return 'success'
        except IdentityError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(enable, range(2))) == ['stale_oidc_configuration', 'success']
    state['nonce_from_code'] = True
    flows = [service.start_login() for _ in range(2)]
    def login(flow):
        query = parse_qs(urlsplit(flow['authorization_url']).query)
        return service.complete_login(query['state'][0], flow['browser_binding'], query['nonce'][0])
    with ThreadPoolExecutor(max_workers=2) as pool:
        sessions = list(pool.map(login, flows))
    assert sessions[0].actor.user_id == sessions[1].actor.user_id
    assert identity[0].list_users(admin.actor)['total'] == 2


def test_concurrent_identity_binding_cannot_reassign_external_subject(oidc_context, identity, database_url):
    from concurrent.futures import ThreadPoolExecutor
    from tests.identity_seed import seed_legacy_user
    from tests.test_identity_management import INITIAL
    service, admin, _, _ = oidc_context
    proof = activate(oidc_context)
    targets = [seed_legacy_user(database_url, f'member-{i}', 'Member', INITIAL, ['analyst']) for i in range(2)]
    def bind(target):
        try:
            service.bind_identity(admin.actor, target, proof['proof_id'], expected_revision=0)
            return 'success'
        except IdentityError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(bind, targets)) == ['oidc_identity_already_bound', 'success']
    account = employee_login(oidc_context)
    assert account.actor.user_id in targets
    assert account.actor.roles == frozenset({'analyst'})


def test_wrong_decryption_key_disables_oidc_not_local_login(oidc_context, identity):
    from cryptography.fernet import Fernet
    service, admin, candidate, _ = oidc_context
    activate(oidc_context)
    reopened = OidcService(identity[0]._engine, encryption_key=Fernet.generate_key().decode(),
        allowed_hosts={'tenant.example'}, callback_url='http://127.0.0.1:18118/api/auth/oidc/callback', provider=service._provider)
    assert reopened.availability() == {'enabled': False}
    with pytest.raises(IdentityError, match='oidc_key_unavailable'):
        reopened.start_test(admin.token, candidate)
    assert identity[0].login('admin', CHANGED).actor.user_id == admin.actor.user_id


@pytest.mark.parametrize('action', ['OIDC_TEST', 'OIDC_ACTIVATE', 'OIDC_LOGIN'])
def test_database_audit_failure_cannot_leave_partial_oidc_success(oidc_context, identity, action):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError
    service, admin, candidate, _ = oidc_context
    proof = activate(oidc_context)
    identities, _ = identity
    before = identities.list_users(admin.actor)['total']
    proofs = service.configuration(admin.actor)['proofs']
    flow, challenge = start_test(oidc_context)
    # Explicit PostgreSQL fault injection at the persistence boundary. Assertions
    # observe the public interfaces, not private table shapes.
    with identities._engine.begin() as c:
        c.execute(text("""CREATE FUNCTION test_oidc_audit_failure() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN IF NEW.action_code = TG_ARGV[0] AND NEW.result='SUCCESS' THEN
            RAISE EXCEPTION 'isolated audit unavailable'; END IF; RETURN NEW; END $$"""))
        c.execute(text(f"CREATE TRIGGER test_oidc_audit BEFORE INSERT ON audit_logs FOR EACH ROW EXECUTE FUNCTION test_oidc_audit_failure('{action}')"))
    try:
        with pytest.raises(DBAPIError, match='isolated audit unavailable'):
            if action == 'OIDC_TEST':
                service.complete_test(challenge, flow['browser_binding'], 'code', admin.token)
            elif action == 'OIDC_ACTIVATE':
                service.activate(admin.actor, candidate, proof['proof_id'], expected_revision=1)
            else:
                employee_login(oidc_context)
    finally:
        with identities._engine.begin() as c:
            c.execute(text('DROP TRIGGER test_oidc_audit ON audit_logs; DROP FUNCTION test_oidc_audit_failure()'))
    view = service.configuration(admin.actor)
    assert view['revision'] == 1
    assert view['proofs'] == proofs
    assert identities.list_users(admin.actor)['total'] == before


@pytest.mark.parametrize('database_url', ['0028_oidc'], indirect=True)
def test_pre_callback_candidate_is_retained_but_requires_explicit_recreation(database_url):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text
    from uuid import uuid4
    from cryptography.fernet import Fernet
    from tests.test_identity_management import INITIAL
    engine = create_engine(database_url)
    identity = IdentityService(engine)
    identity.bootstrap_admin('migration-admin', 'Admin', INITIAL)
    session = identity.login('migration-admin', INITIAL)
    admin = identity.change_password(session.token, INITIAL, CHANGED)
    candidate = uuid4()
    with engine.begin() as c:
        c.execute(text('''INSERT INTO oidc_config_versions(id,issuer,client_id,secret_cipher,created_by,created_at)
            VALUES (:id,'https://tenant.example','old-client',:secret,:admin,now())'''),
            {'id': candidate, 'secret': Fernet(KEY.encode()).encrypt(b'old-secret').decode(), 'admin': admin.actor.user_id})
        c.execute(text('UPDATE oidc_active SET config_id=:id,revision=1'), {'id': candidate})
    command.upgrade(Config('alembic.ini'), 'head')
    oidc = OidcService(engine, encryption_key=KEY, allowed_hosts={'tenant.example'}, callback_url='https://portal.example/api/auth/oidc/callback')
    assert oidc.configuration(admin.actor)['candidates'][0]['id'] == candidate
    assert oidc.configuration(admin.actor)['candidates'][0]['callback_url'] is None
    assert oidc.availability() == {'enabled': False}
    with pytest.raises(IdentityError, match='oidc_candidate_callback_required'):
        oidc.start_test(admin.token, candidate)
    assert identity.login('migration-admin', CHANGED).actor.user_id == admin.actor.user_id
    engine.dispose()
