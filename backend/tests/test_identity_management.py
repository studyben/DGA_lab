"""Account-policy acceptance at the public identity interface, real PostgreSQL."""
import pytest
from sqlalchemy import create_engine, text

from dga.shared.auth.public import IdentityError, IdentityService
from tests.identity_seed import seed_legacy_user

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


def test_recovery_invalidates_stale_management_commands(identity):
    service, admin = identity
    target = service.provision_user(admin.actor, 'second', 'Second', INITIAL, ['system_admin'])
    service.set_status(admin.actor, target, 'LOCKED')
    stale = service.user_detail(admin.actor, target)['revision']
    service.recover_local_admin('second', CHANGED)
    with pytest.raises(IdentityError, match='stale_user'):
        service.set_status(admin.actor, target, 'DISABLED', expected_revision=stale)
    assert service.login('second', CHANGED).actor.must_change_password


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


def test_recovery_never_promotes_members_or_restores_disabled_account(identity, database_url):
    service, admin = identity
    member = seed_legacy_user(database_url, 'member', 'Member', INITIAL, ['field_engineer'])
    second = service.provision_user(admin.actor, 'second', 'Second', INITIAL, ['system_admin'])
    service.set_status(admin.actor, second, 'DISABLED')
    for username in ['member', 'second', 'unknown']:
        with pytest.raises(IdentityError, match='local_recovery_unavailable'):
            service.recover_local_admin(username, CHANGED)
    assert service.login('member', INITIAL).actor.user_id == member
    with pytest.raises(IdentityError):
        service.login('second', INITIAL)


def test_am_only_has_site_basic_edit_not_asset_or_alarm_write(identity, database_url):
    service, admin = identity
    seed_legacy_user(database_url, 'am', 'AM', INITIAL, ['asset_manager'])
    member = service.login('am', INITIAL)
    actor = service.change_password(member.token, INITIAL, CHANGED).actor
    assert {'assets.read', 'laboratory.read', 'analysis.read', 'assets.site.edit'} <= actor.permissions
    assert not {'assets.write', 'analysis.acknowledge', 'laboratory.write'} & actor.permissions


def test_management_adds_and_removes_only_am_preserving_other_roles(identity, database_url):
    service, admin = identity
    seed_legacy_user(database_url, 'manager', 'Manager', INITIAL, ['management'])
    login = service.login('manager', INITIAL)
    manager = service.change_password(login.token, INITIAL, CHANGED).actor
    member = seed_legacy_user(database_url, 'member', 'Member', INITIAL, ['analyst', 'field_engineer'])
    before = service.user_detail(manager, member)
    service.change_roles(manager, member, add=['asset_manager'], remove=[], expected_revision=before['revision'])
    updated = service.user_detail(manager, member)
    assert updated['roles'] == ['analyst', 'asset_manager', 'field_engineer']
    service.change_roles(manager, member, add=[], remove=['asset_manager'], expected_revision=updated['revision'])
    assert service.user_detail(manager, member)['roles'] == ['analyst', 'field_engineer']
    with pytest.raises(IdentityError, match='permission_denied'):
        service.change_roles(manager, member, add=['system_admin'], remove=[], expected_revision=2)


def test_lab_manager_disables_ordinary_user_but_only_admin_restores(identity, database_url):
    service, admin = identity
    seed_legacy_user(database_url, 'lab', 'Lab manager', INITIAL, ['lab_admin'])
    login = service.login('lab', INITIAL)
    lab = service.change_password(login.token, INITIAL, CHANGED).actor
    member = seed_legacy_user(database_url, 'member', 'Member', INITIAL, ['analyst'])
    member_session = service.login('member', INITIAL)
    service.set_status(lab, member, 'DISABLED')
    with pytest.raises(IdentityError, match='session_expired'):
        service.session(member_session.token)
    with pytest.raises(IdentityError, match='permission_denied'):
        service.set_status(lab, member, 'ACTIVE')
    service.set_status(admin.actor, member, 'ACTIVE')
    assert service.login('member', INITIAL).actor.user_id == member
    with pytest.raises(IdentityError, match='permission_denied'):
        service.set_status(lab, admin.actor.user_id, 'DISABLED')


def test_profile_search_and_revision_do_not_expose_credentials(identity, database_url):
    service, admin = identity
    member = seed_legacy_user(database_url, 'member', 'Original', INITIAL, ['analyst'])
    before = service.user_detail(admin.actor, member)
    service.update_profile(admin.actor, member, 'Updated name', expected_revision=before['revision'])
    with pytest.raises(IdentityError, match='stale_user'):
        service.update_profile(admin.actor, member, 'Stale overwrite', expected_revision=before['revision'])
    result = service.list_users(admin.actor, query='updated', role='analyst', status='ACTIVE')
    assert result['total'] == 1
    assert result['items'][0]['display_name'] == 'Updated name'
    assert 'password' not in str(result)
    catalog = service.role_catalog(admin.actor)
    assert len([r for r in catalog if r['assignable']]) == 6
    assert not next(r for r in catalog if r['role_code'] == 'management_readonly')['assignable']


def test_new_local_password_accounts_are_recovery_admin_only(identity):
    service, admin = identity
    with pytest.raises(IdentityError, match='local_admin_required'):
        service.provision_user(admin.actor, 'ordinary', 'Ordinary', INITIAL, ['analyst'])
    user = service.provision_user(admin.actor, 'recovery', 'Recovery', INITIAL, ['system_admin'])
    assert service.user_detail(admin.actor, user)['credential_kind'] == 'RECOVERY'


@pytest.mark.parametrize('username,roles,error', [
    ('ordinary', ['analyst'], 'local_admin_required'),
    ('legacy', ['system_admin', 'management_readonly'], 'legacy_role_not_assignable'),
    ('admin', ['system_admin'], 'username_taken'),
])
def test_rejected_local_creation_is_audited_without_password(identity, username, roles, error):
    service, admin = identity
    with pytest.raises(IdentityError, match=error):
        service.provision_user(admin.actor, username, 'Rejected', INITIAL, roles)
    events = service.audit_events(admin.actor)
    assert any(e['action_code'] == 'USER_CREATE' and e['result'] == 'FAILURE' for e in events)
    assert INITIAL not in str(events)


def test_legacy_role_cannot_be_newly_assigned_through_compatibility_command(identity):
    service, admin = identity
    second = service.provision_user(admin.actor, 'second', 'Second', INITIAL, ['system_admin'])
    with pytest.raises(IdentityError, match='legacy_role_not_assignable'):
        service.set_roles(admin.actor, second, ['management_readonly'])


def test_management_attempts_and_successful_role_deltas_are_audited(identity, database_url):
    service, admin = identity
    seed_legacy_user(database_url, 'manager', 'Manager', INITIAL, ['management'])
    initial = service.login('manager', INITIAL)
    manager = service.change_password(initial.token, INITIAL, CHANGED).actor
    member = seed_legacy_user(database_url, 'member', 'Member', INITIAL, ['field_engineer'])
    service.change_roles(manager, member, add=['asset_manager'], remove=[], expected_revision=0)
    with pytest.raises(IdentityError, match='permission_denied'):
        service.change_roles(manager, member, add=['system_admin'], remove=[], expected_revision=1)
    events = [e for e in service.audit_events(admin.actor, limit=500)
              if e['action_code'] == 'ROLES_CHANGE' and e['entity_id'] == member]
    assert {e['result'] for e in events} == {'SUCCESS', 'FAILURE'}
    success = next(e for e in events if e['result'] == 'SUCCESS')
    assert success['before_value'] == {'roles': ['field_engineer']}
    assert success['after_value'] == {'roles': ['asset_manager', 'field_engineer']}


def test_operator_impact_report_retains_legacy_readonly_without_mapping(identity, database_url):
    service, admin = identity
    member = seed_legacy_user(database_url, 'legacy', 'Legacy reader', INITIAL, ['management_readonly'])
    report = service.role_migration_impact()
    row = next(r for r in report if r['user_id'] == str(member))
    assert row['roles'] == ['management_readonly']
    assert row['added_permissions'] == []
    assert row['removed_permissions'] == []
    assert row['requires_explicit_mapping'] is True
    assert service.user_detail(admin.actor, member)['roles'] == ['management_readonly']


def test_administrator_impact_matches_applied_policy(identity):
    service, admin = identity
    row = next(r for r in service.role_migration_impact() if r['user_id'] == str(admin.actor.user_id))
    assert row['added_permissions'] == []
    assert row['removed_permissions'] == []


def test_unknown_role_removal_is_rejected(identity, database_url):
    service, admin = identity
    member = seed_legacy_user(database_url, 'member', 'Member', INITIAL, ['field_engineer'])
    with pytest.raises(IdentityError, match='invalid_roles'):
        service.change_roles(admin.actor, member, add=[], remove=['typo'], expected_revision=0)
    assert service.user_detail(admin.actor, member)['revision'] == 0


def test_management_cannot_submit_non_am_delta_even_if_noop(identity, database_url):
    service, admin = identity
    seed_legacy_user(database_url, 'manager', 'Manager', INITIAL, ['management'])
    login = service.login('manager', INITIAL)
    manager = service.change_password(login.token, INITIAL, CHANGED).actor
    member = seed_legacy_user(database_url, 'member', 'Member', INITIAL, ['analyst'])
    with pytest.raises(IdentityError, match='permission_denied'):
        service.change_roles(manager, member, add=['analyst'], remove=[], expected_revision=0)


@pytest.mark.parametrize('database_url', ['0024_alarm_observation'], indirect=True)
def test_role_upgrade_matches_preview_and_preserves_accounts(database_url):
    from alembic import command
    from alembic.config import Config
    engine = create_engine(database_url)
    service = IdentityService(engine)
    before = {}
    for role in ['system_admin', 'lab_admin', 'analyst', 'field_engineer', 'asset_manager', 'management_readonly']:
        seed_legacy_user(database_url, role, role, INITIAL, [role])
        session = service.login(role, INITIAL)
        before[role] = service.change_password(session.token, INITIAL, CHANGED)
    impact = {row['username']: row for row in service.role_migration_impact()}
    command.upgrade(Config('alembic.ini'), 'head')
    for role, previous in before.items():
        actor = service.session(previous.token).actor
        assert actor.user_id == previous.actor.user_id
        assert actor.roles == previous.actor.roles
        assert sorted(actor.permissions - previous.actor.permissions) == impact[role]['added_permissions']
        assert sorted(previous.actor.permissions - actor.permissions) == impact[role]['removed_permissions']
        assert service.login(role, CHANGED).actor.user_id == previous.actor.user_id
    with pytest.raises(RuntimeError, match='Retained identity'):
        command.downgrade(Config('alembic.ini'), '0024_alarm_observation')
    assert service.session(before['system_admin'].token).actor.user_id == before['system_admin'].actor.user_id
    engine.dispose()


def test_role_commands_use_current_actor_not_stale_permissions(identity, database_url):
    service, admin = identity
    manager_id = seed_legacy_user(database_url, 'manager', 'Manager', INITIAL, ['lab_admin'])
    login = service.login('manager', INITIAL)
    manager = service.change_password(login.token, INITIAL, CHANGED).actor
    member = seed_legacy_user(database_url, 'member', 'Member', INITIAL, ['field_engineer'])
    service.set_roles(admin.actor, manager_id, ['field_engineer'])
    with pytest.raises(IdentityError, match='permission_denied'):
        service.change_roles(manager, member, add=['analyst'], remove=[], expected_revision=0)
    assert service.user_detail(admin.actor, member)['roles'] == ['field_engineer']


def test_competing_role_and_status_commands_reject_stale_revision(identity, database_url):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    service, admin = identity
    member = seed_legacy_user(database_url, 'member', 'Member', INITIAL, ['field_engineer'])
    barrier = Barrier(2)

    def change(kind):
        barrier.wait(timeout=5)
        try:
            if kind == 'roles':
                service.change_roles(admin.actor, member, add=['analyst'], remove=[], expected_revision=0)
            else:
                service.set_status(admin.actor, member, 'DISABLED', expected_revision=0)
            return 'success'
        except IdentityError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(change, ['roles', 'status'])) == ['stale_user', 'success']
    assert service.user_detail(admin.actor, member)['revision'] == 1


@pytest.mark.parametrize('role', ['management', 'lab_admin'])
def test_restricted_managers_cannot_change_own_roles_or_privileged_targets(identity, database_url, role):
    service, admin = identity
    own_id = seed_legacy_user(database_url, 'manager', 'Manager', INITIAL, [role])
    login = service.login('manager', INITIAL)
    manager = service.change_password(login.token, INITIAL, CHANGED).actor
    for target in [own_id, admin.actor.user_id]:
        revision = service.user_detail(manager, target)['revision']
        with pytest.raises(IdentityError, match='permission_denied'):
            service.change_roles(manager, target, add=['asset_manager'], remove=[], expected_revision=revision)


def test_lab_manager_can_unlock_but_management_cannot_edit_profiles_or_status(identity, database_url):
    service, admin = identity
    member = seed_legacy_user(database_url, 'member', 'Member', INITIAL, ['field_engineer'])
    service.set_status(admin.actor, member, 'LOCKED')
    for role in ['management', 'lab_admin']:
        seed_legacy_user(database_url, role, role, INITIAL, [role])
        login = service.login(role, INITIAL)
        actor = service.change_password(login.token, INITIAL, CHANGED).actor
        if role == 'management':
            with pytest.raises(IdentityError, match='permission_denied'):
                service.set_status(actor, member, 'ACTIVE')
            with pytest.raises(IdentityError, match='permission_denied'):
                service.update_profile(actor, member, 'Not allowed', expected_revision=1)
        else:
            service.set_status(actor, member, 'ACTIVE')
    assert service.login('member', INITIAL).actor.user_id == member
