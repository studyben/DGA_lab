from fastapi.testclient import TestClient

from dga.main import create_app
from dga.shared.config import Settings


def test_portal_can_discover_all_three_domain_modules(database_url):
    with TestClient(create_app(Settings(database_url=database_url))) as client:
        response = client.get('/api/modules')
    assert response.status_code == 200
    assert response.json() == [
        {'code': 'assets', 'label': '资产管理'},
        {'code': 'laboratory', 'label': 'DGA 实验室'},
        {'code': 'condition_analysis', 'label': '状态分析'},
    ]
