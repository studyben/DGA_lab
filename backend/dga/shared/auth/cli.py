"""Interactive, trusted operator entry; no default accounts or password arguments."""
import argparse
import json
import getpass
import sys
from uuid import UUID

from sqlalchemy import create_engine

from dga.shared.config import Settings
from .public import IdentityError, IdentityService


def new_password():
    password = getpass.getpass('Initial password (15-128 characters): ')
    if password != getpass.getpass('Confirm initial password: '):
        raise IdentityError('passwords_do_not_match', 422)
    return password


def main():
    parser = argparse.ArgumentParser(description='DGA trusted account operator; passwords are prompted, never command-line arguments.')
    actions = parser.add_subparsers(dest='action', required=True)
    actions.add_parser('role-impact', help='Read-only pre-migration role permission impact; no account changes')
    recover = actions.add_parser('recover-admin', help='Trusted server operator: recover an existing local administrator')
    recover.add_argument('--username', required=True)
    bootstrap = actions.add_parser('bootstrap', help='Create the first administrator; refuses if any account exists')
    create = actions.add_parser('create-user', help='Provision a local recovery administrator only')
    for command in (bootstrap, create):
        command.add_argument('--username', required=True)
        command.add_argument('--display-name', required=True)
    create.add_argument('--role', action='append', required=True)
    create.add_argument('--admin', required=True)
    status = actions.add_parser('set-status')
    status.add_argument('--status', choices=['ACTIVE', 'LOCKED', 'DISABLED'], required=True)
    roles = actions.add_parser('set-roles')
    roles.add_argument('--role', action='append', required=True)
    for command in (status, roles):
        command.add_argument('--admin', required=True)
        command.add_argument('--user-id', type=UUID, required=True)
    args = parser.parse_args()
    if args.action != 'role-impact' and not sys.stdin.isatty():
        parser.error('An interactive terminal is required; use docker compose exec -it api ...')
    settings = Settings()
    engine = create_engine(settings.database_url.get_secret_value())
    service = IdentityService(engine, session_hours=settings.session_hours)
    session = None
    try:
        if args.action == 'role-impact':
            print(json.dumps(service.role_migration_impact(), ensure_ascii=False, indent=2))
            return
        if args.action == 'recover-admin':
            service.recover_local_admin(args.username, new_password())
            print('Local administrator recovered; previous sessions revoked. Sign in and change the initial password.')
            return
        if args.action == 'bootstrap':
            user_id = service.bootstrap_admin(args.username, args.display_name, new_password())
            print(f'Administrator created: {user_id}. Sign in through the portal to change the initial password.')
            return
        session = service.login(args.admin, getpass.getpass('Administrator password: '))
        if session.actor.must_change_password:
            raise IdentityError('change_administrator_password_in_portal_first', 403)
        if args.action == 'create-user':
            user_id = service.provision_user(session.actor, args.username, args.display_name, new_password(), args.role)
            print(f'User created: {user_id}. First login requires a password change.')
        elif args.action == 'set-status':
            service.set_status(session.actor, args.user_id, args.status)
            print('Account status updated.')
        elif args.action == 'set-roles':
            service.set_roles(session.actor, args.user_id, args.role)
            print('Roles updated.')
    except IdentityError as error:
        print(f'Operation refused: {error.code}', file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        if session:
            service.logout(session.token)
        engine.dispose()


if __name__ == '__main__':
    main()
