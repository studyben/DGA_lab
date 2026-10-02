"""Account-policy acceptance at the public identity interface, real PostgreSQL."""
import pytest
from sqlalchemy import create_engine, text

from dga.shared.auth.public import IdentityError, IdentityService

INITIAL = 'Initial isolated password 18!'
CHANGED = 'Changed isolated password 18!'


@pytest.fixture
def identity(database_url):
    engine = create_engine(database_url)
    with engine.begin() as c:
        c.execute(text('TRUNCATE users CASCADE'))
    service = IdentityService(engine)
    service.bootstrap_admin('admin', 'Administrator', INITIAL)
    login = service.login('admin', INITIAL)
    admin = service.change_password(login.token, INITIAL, CHANGED)
    yield service, admin
    engine.dispose()


def test_last_local_administrator_cannot_be_disabled(identity):
    service, admin = identity
    with pytest.raises(IdentityError, match='last_local_admin'):
        service.set_status(admin.actor, admin.actor.user_id, 'DISABLED')
    assert service.session(admin.token).actor.roles == frozenset({'system_admin'})


def test_last_local_administrator_cannot_be_demoted(identity):
    service, admin = identity
    with pytest.raises(IdentityError, match='last_local_admin'):
        service.set_roles(admin.actor, admin.actor.user_id, ['field_engineer'])
    assert 'system_admin' in service.session(admin.token).actor.roles


def test_operator_recovers_local_admin_without_old_password_and_revokes_session(identity):
    service, admin = identity
    replacement = 'Recovered isolated password 18!'
    service.recover_local_admin(' ADMIN ', replacement)
    with pytest.raises(IdentityError, match='session_expired'):
        service.session(admin.token)
    recovered = service.login('admin', replacement)
    assert recovered.actor.user_id == admin.actor.user_id
    assert recovered.actor.must_change_password
    changed = service.change_password(recovered.token, replacement, CHANGED)
    events = service.audit_events(changed.actor)
    assert any(e['action_code'] == 'LOCAL_ADMIN_RECOVERY' and e['actor_user_id'] is None
               and e['entity_id'] == admin.actor.user_id for e in events)
    assert replacement not in str(events)


def test_recovery_command_is_available_without_password_argument():
    import subprocess
    import sys
    result = subprocess.run([sys.executable, '-m', 'dga.shared.auth.cli', 'recover-admin', '--help'],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0
    assert '--username' in result.stdout
    assert '--password' not in result.stdout


@pytest.mark.parametrize('operation', ['LOCKED', 'DISABLED', 'DEMOTE'])
def test_competing_admin_changes_leave_one_usable_recovery_account(identity, operation):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    service, admin = identity
    service.provision_user(admin.actor, 'second', 'Second administrator', INITIAL, ['system_admin'])
    first = service.login('second', INITIAL)
    second = service.change_password(first.token, INITIAL, CHANGED)
    barrier = Barrier(2)

    def remove(session):
        barrier.wait(timeout=5)
        try:
            if operation == 'DEMOTE':
                service.set_roles(session.actor, session.actor.user_id, ['field_engineer'])
            else:
                service.set_status(session.actor, session.actor.user_id, operation)
            return 'removed'
        except IdentityError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(remove, [admin, second]))
    assert sorted(outcomes) == ['last_local_admin', 'removed']
    survivors = []
    for username in ['admin', 'second']:
        try:
            session = service.login(username, CHANGED)
            if 'system_admin' in session.actor.roles:
                survivors.append(username)
        except IdentityError:
            pass
    assert len(survivors) == 1


def test_recovery_clears_login_cooldown(identity):
    service, _ = identity
    for _ in range(5):
        with pytest.raises(IdentityError):
            service.login('admin', 'incorrect')
    with pytest.raises(IdentityError):
        service.login('admin', CHANGED)
    service.recover_local_admin('admin', INITIAL)
    assert service.login('admin', INITIAL).actor.must_change_password


def test_recovery_never_promotes_members_or_restores_disabled_account(identity):
    service, admin = identity
    member = service.provision_user(admin.actor, 'member', 'Member', INITIAL, ['field_engineer'])
    second = service.provision_user(admin.actor, 'second', 'Second', INITIAL, ['system_admin'])
    service.set_status(admin.actor, second, 'DISABLED')
    for username in ['member', 'second', 'unknown']:
        with pytest.raises(IdentityError, match='local_recovery_unavailable'):
            service.recover_local_admin(username, CHANGED)
    assert service.login('member', INITIAL).actor.user_id == member
    with pytest.raises(IdentityError):
        service.login('second', INITIAL)
