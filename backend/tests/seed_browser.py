"""Destructive fixture setup exclusively for the isolated browser-test database."""
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from dga.shared.config import Settings
from dga.shared.auth.public import IdentityService


def main():
    value = Settings().database_url.get_secret_value()
    url = make_url(value)
    if (url.host, url.database, url.username) != ('db', 'dga_browser', 'dga_browser'):
        raise RuntimeError('Browser fixtures require the dedicated dga_browser database')
    engine = create_engine(value)
    try:
        with engine.begin() as connection:
            connection.execute(text('TRUNCATE auth_sessions,user_roles,audit_logs,users CASCADE'))
        service = IdentityService(engine)
        initial = 'Browser initial passphrase 42!'
        changed = 'Browser changed passphrase 84!'
        service.bootstrap_admin('browser-admin', '测试管理员', initial)
        login = service.login('browser-admin', initial)
        admin = service.change_password(login.token, initial, changed)
        service.provision_user(admin.actor, 'first-login', '首次登录测试', initial, ['lab_admin'])
        service.provision_user(admin.actor, 'field-user', '现场工程师', initial, ['field_engineer'])
        field = service.login('field-user', initial)
        service.change_password(field.token, initial, changed)
        service.logout(admin.token)
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
