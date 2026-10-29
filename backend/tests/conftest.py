import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url
from sqlalchemy import create_engine, text


@pytest.fixture(scope='session')
def current_database_url():
    value = os.environ['TEST_DATABASE_URL']
    url = make_url(value)
    if (url.host, url.database, url.username) != ('test-db', 'dga_test', 'dga_test'):
        raise RuntimeError('Tests require the isolated Compose test-db database')
    os.environ['DATABASE_URL'] = value
    command.upgrade(Config('alembic.ini'), 'head')
    return value


@pytest.fixture
def database_url(current_database_url, request, monkeypatch):
    """Historical migration cases get their own schema at the requested revision.

    No stamping, skipped migrations, or downgrade of shared acceptance data.
    """
    revision = getattr(request, 'param', None)
    if revision is None:
        monkeypatch.setenv('DATABASE_URL', current_database_url)
        yield current_database_url
        return
    schema = 'historical_' + uuid4().hex
    engine = create_engine(current_database_url)
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA {schema}'))
    isolated = make_url(current_database_url).update_query_dict(
        {'options': f'-csearch_path={schema}'}).render_as_string(hide_password=False)
    monkeypatch.setenv('DATABASE_URL', isolated)
    try:
        command.upgrade(Config('alembic.ini'), revision)
        yield isolated
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        engine.dispose()
