"""Fixture for pre-OIDC local employee accounts, never production provisioning."""
from uuid import uuid4
from argon2 import PasswordHasher
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def seed_legacy_user(database_url, username, display_name, password, roles):
    url = make_url(database_url)
    if (url.host, url.database, url.username) not in {
        ('test-db', 'dga_test', 'dga_test'), ('db', 'dga_browser', 'dga_browser'),
    }:
        raise RuntimeError('Legacy fixtures require an isolated test database')
    engine = create_engine(database_url)
    user_id = uuid4()
    try:
        with engine.begin() as c:
            c.execute(text('''INSERT INTO users(id,username,display_name,password_hash)
                VALUES (:id,:name,:display,:password)'''),
                {'id': user_id, 'name': username, 'display': display_name, 'password': PasswordHasher().hash(password)})
            for role in roles:
                c.execute(text('INSERT INTO user_roles(user_id,role_id) SELECT :id,id FROM roles WHERE role_code=:role'),
                          {'id': user_id, 'role': role})
        return user_id
    finally:
        engine.dispose()
