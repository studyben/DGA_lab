import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url


@pytest.fixture(scope='session')
def database_url():
    value = os.environ['TEST_DATABASE_URL']
    url = make_url(value)
    if (url.host, url.database, url.username) != ('test-db', 'dga_test', 'dga_test'):
        raise RuntimeError('Tests require the isolated Compose test-db database')
    os.environ['DATABASE_URL'] = value
    command.upgrade(Config('alembic.ini'), 'head')
    return value
