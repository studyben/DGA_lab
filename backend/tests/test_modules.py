from fastapi.testclient import TestClient

from dga.main import create_app
from dga.shared.config import Settings
from dga.shared.auth.public import IdentityService
from sqlalchemy import create_engine, text


def test_portal_can_discover_all_three_domain_modules(database_url):
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text('TRUNCATE auth_sessions,user_roles,audit_logs,users CASCADE'))
    identity = IdentityService(engine)
    initial = 'Module registry initial passphrase!'
    identity.bootstrap_admin('registry', 'Registry admin', initial)
    session = identity.login('registry', initial)
    session = identity.change_password(session.token, initial, 'Module registry changed passphrase!')
    with TestClient(create_app(Settings(database_url=database_url, cookie_secure=False))) as client:
        client.cookies.set('dga_session', session.token)
        response = client.get('/api/modules')
    engine.dispose()
    assert response.status_code == 200
    assert response.json() == [
        {'code': 'assets', 'label': '资产管理'},
        {'code': 'laboratory', 'label': 'DGA 实验室'},
        {'code': 'condition_analysis', 'label': '状态分析'},
    ]
