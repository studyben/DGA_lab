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


def test_older_migration_is_unavailable_then_recovers_without_app_restart(database_url):
    config = Config('alembic.ini')
    with TestClient(create_app(Settings(database_url=database_url))) as client:
        # Exercise an outdated schema without destroying immutable business history.
        command.downgrade(config, '-1')
        try:
            assert client.get('/api/health').status_code == 503
        finally:
            command.upgrade(config, 'head')
        command.upgrade(config, 'head')
        assert client.get('/api/health').status_code == 200
