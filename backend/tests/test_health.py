from fastapi.testclient import TestClient

from dga.main import create_app
from dga.shared.config import Settings

from time import monotonic
from sqlalchemy.engine import make_url
from alembic import command
from alembic.config import Config


def test_migrated_postgresql_is_ready(database_url):
    with TestClient(create_app(Settings(database_url=database_url))) as client:
        response = client.get('/api/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok', 'database': 'ok'}


def test_unavailable_database_is_bounded_and_does_not_expose_credentials(database_url):
    unavailable = make_url(database_url).set(port=1).render_as_string(hide_password=False)
    started = monotonic()
    with TestClient(create_app(Settings(database_url=unavailable)), raise_server_exceptions=False) as client:
        response = client.get('/api/health')
    assert response.status_code == 503
    assert response.json() == {'status': 'unavailable', 'database': 'unavailable'}
    assert monotonic() - started < 10
    assert 'isolated-tests-only' not in response.text


def test_older_migration_is_unavailable_then_recovers_without_app_restart(database_url,monkeypatch):
    from sqlalchemy import create_engine, text
    from uuid import uuid4
    # Migrations must not depend on another test leaving business tables empty.
    # The fixture has already verified this is the isolated test-db database.
    probe_database='migration_probe_'+uuid4().hex
    engine=create_engine(database_url,isolation_level='AUTOCOMMIT')
    with engine.connect() as c:
        c.execute(text(f'CREATE DATABASE {probe_database}'))
    isolated=make_url(database_url).set(database=probe_database).render_as_string(hide_password=False)
    monkeypatch.setenv('DATABASE_URL',isolated)
    config = Config('alembic.ini')
    try:
        command.upgrade(config,'0013_asset_import')
        with TestClient(create_app(Settings(database_url=isolated))) as client:
            assert client.get('/api/health').status_code == 503
            command.upgrade(config, 'head')
            command.upgrade(config, 'head')
            assert client.get('/api/health').status_code == 200
    finally:
        with engine.connect() as c:
            c.execute(text(f'DROP DATABASE {probe_database}'))
        engine.dispose()
