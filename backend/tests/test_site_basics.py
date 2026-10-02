from datetime import date
from decimal import Decimal

import pytest

from dga.assets.public import AssetDirectory, AssetQueryError, SiteBasics
from dga.shared.auth.public import IdentityService
from tests.identity_seed import seed_legacy_user
from tests.test_asset_import import import_context
from tests.test_sample_reception import SITE_ID, INITIAL_PASSWORD, CHANGED_PASSWORD


def values(**patch):
    return dict(site_name='Updated site', location_text='Houston', grid_status='COMPLETED',
        operation_status='OPERATIONAL', commissioning_date=date(2025, 1, 1), product_line='PV',
        power_mw=Decimal('125.500000'), energy_mwh=None, expected_revision=0) | patch


def test_am_edits_site_basics_with_revision_and_audit(database_url):
    engine, admin, _, _ = import_context(database_url)
    service = IdentityService(engine)
    seed_legacy_user(database_url, 'am', 'AM', INITIAL_PASSWORD, ['asset_manager'])
    login = service.login('am', INITIAL_PASSWORD)
    am = service.change_password(login.token, INITIAL_PASSWORD, CHANGED_PASSWORD).actor
    sites = SiteBasics(engine)
    sites.update(am, SITE_ID, **values())
    detail = AssetDirectory(engine).site_detail(am, SITE_ID)['site']
    assert detail['site_name'] == 'Updated site'
    assert detail['power_mw'] == Decimal('125.5')
    assert detail['revision'] == 1
    with pytest.raises(AssetQueryError, match='stale_site'):
        sites.update(am, SITE_ID, **values(site_name='Stale overwrite'))
    history = sites.history(admin, SITE_ID)
    assert len(history) == 1
    assert history[0]['before_value']['site_name'] == 'Prairie Sun'
    assert history[0]['after_value']['site_name'] == 'Updated site'
    engine.dispose()


@pytest.mark.parametrize('patch', [
    {'customer_id': str(SITE_ID)}, {'asset_id': str(SITE_ID)}, {'site_name': '  '},
    {'power_mw': '-1'}, {'power_mw': 'NaN'}, {'power_mw': 'Infinity'},
    {'power_mw': '0.0000001'}, {'power_mw': '10000000000'},
    {'energy_mwh': '0'}, {'expected_revision': True}, {'grid_status': 'INVALID'},
])
def test_invalid_changes_leave_site_and_history_intact(database_url, patch):
    engine, admin, _, _ = import_context(database_url)
    sites = SiteBasics(engine)
    with pytest.raises(AssetQueryError, match='invalid_site_basics'):
        sites.update(admin, SITE_ID, **values(**patch))
    assert AssetDirectory(engine).site_detail(admin, SITE_ID)['site']['site_name'] == 'Prairie Sun'
    assert sites.history(admin, SITE_ID) == []
    engine.dispose()


def test_field_cannot_edit_and_am_cannot_mutate_assets(database_url):
    from dga.assets.public import AssetLifecycle
    from dga.shared.auth.public import IdentityError
    from tests.test_sample_reception import TRANSFORMER_ID
    from datetime import datetime, timezone
    engine, _, imports, _ = import_context(database_url)
    identity = IdentityService(engine)
    for role in ('field_engineer', 'asset_manager'):
        seed_legacy_user(database_url, role, role, INITIAL_PASSWORD, [role])
        login = identity.login(role, INITIAL_PASSWORD)
        actor = identity.change_password(login.token, INITIAL_PASSWORD, CHANGED_PASSWORD).actor
        if role == 'field_engineer':
            with pytest.raises(IdentityError, match='permission_denied'):
                SiteBasics(engine).update(actor, SITE_ID, **values())
        else:
            with pytest.raises(IdentityError, match='permission_denied'):
                AssetLifecycle(engine).move(actor, TRANSFORMER_ID, destination='REPAIR_CENTER',
                    effective_at=datetime.now(timezone.utc), expected_revision=0, reason='Denied')
            with pytest.raises(IdentityError, match='permission_denied'):
                imports.submit(actor, filename='denied.xlsx', content=b'not evaluated')
    engine.dispose()


def test_edit_keeps_old_sample_snapshot_and_cannot_add_product_line(database_url):
    from datetime import datetime, timezone
    from dga.shared.auth.public import AuditTrail
    from dga.laboratory.public import SampleRegistry, ReceiveSample, SampleIdentityStatus
    from tests.test_sample_reception import TRANSFORMER_ID
    engine, admin, _, _ = import_context(database_url)
    registry = SampleRegistry(engine, AssetDirectory(engine), AuditTrail())
    sample = registry.receive(admin, ReceiveSample(sampled_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        received_at=datetime(2025, 6, 2, tzinfo=timezone.utc), site_name='ignored',
        equipment_serial='ignored', notes='', container_count=1,
        identity_status=SampleIdentityStatus.ASSOCIATED, formal_asset_id=TRANSFORMER_ID))
    sites = SiteBasics(engine)
    with pytest.raises(AssetQueryError, match='site_product_line_not_found'):
        sites.update(admin, SITE_ID, **values(product_line='ESS', energy_mwh='200'))
    sites.update(admin, SITE_ID, **values())
    assert registry.find_by_barcode(admin, sample.barcode_value).asset_snapshot.site_name == 'Prairie Sun'
    assert AssetDirectory(engine).site_detail(admin, SITE_ID)['site']['site_name'] == 'Updated site'
    engine.dispose()


def test_site_http_guards_and_revision(database_url):
    from fastapi.testclient import TestClient
    from dga.main import create_app
    from dga.shared.config import Settings
    engine, _, _, _ = import_context(database_url)
    with TestClient(create_app(Settings(database_url=database_url, cookie_secure=False,
            auth_allowed_origins='http://testserver'))) as client:
        login = client.post('/api/auth/login', headers={'Origin': 'http://testserver'},
            json={'username': 'reception-admin', 'password': CHANGED_PASSWORD}).json()
        headers = {'Origin': 'http://testserver', 'X-CSRF-Token': login['csrf_token']}
        body = values(power_mw='12.5', commissioning_date='2025-01-01')
        path = f'/api/assets/sites/{SITE_ID}/basics'
        assert client.put(path, json=body).status_code == 403
        assert client.put(path, json=body, headers={**headers, 'Origin': 'https://bad.example'}).status_code == 403
        assert client.put(path, json={**body, 'customer_id': str(SITE_ID)}, headers=headers).status_code == 422
        assert client.put(path, json=body, headers=headers).status_code == 200
        assert client.put(path, json=body, headers=headers).status_code == 409
        assert client.get(f'/api/assets/sites/{SITE_ID}').json()['site']['revision'] == 1
    engine.dispose()


def test_competing_product_lines_cannot_overwrite_shared_basics(database_url):
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy import text
    engine, admin, _, _ = import_context(database_url)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO site_product_lines(site_id,product_line) VALUES (:id,'ESS')"), {'id': SITE_ID})
    def change(line):
        try:
            SiteBasics(engine).update(admin, SITE_ID, **values(site_name=line, product_line=line))
            return line
        except AssetQueryError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(change, ['PV', 'ESS']))
    assert results.count('stale_site') == 1
    winner = next(result for result in results if result != 'stale_site')
    assert AssetDirectory(engine).site_detail(admin, SITE_ID)['site']['site_name'] == winner
    assert len(SiteBasics(engine).history(admin, SITE_ID)) == 1
    engine.dispose()


def test_site_audit_failure_rolls_back_entire_change(database_url, monkeypatch):
    from dga.shared.auth.public import AuditTrail
    engine, admin, _, _ = import_context(database_url)
    def unavailable(*args, **kwargs):
        raise RuntimeError('audit unavailable')
    monkeypatch.setattr(AuditTrail, 'append', unavailable)
    sites = SiteBasics(engine)
    with pytest.raises(RuntimeError, match='audit unavailable'):
        sites.update(admin, SITE_ID, **values())
    assert AssetDirectory(engine).site_detail(admin, SITE_ID)['site']['revision'] == 0
    assert sites.history(admin, SITE_ID) == []
    engine.dispose()
