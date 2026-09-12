from datetime import datetime, timezone
from dataclasses import replace
import pytest
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from dga.main import create_app
from dga.shared.config import Settings

from dga.assets.public import AssetLifecycle, AssetQueryError
from dga.shared.auth.public import IdentityError
from dga.shared.auth.public import IdentityService, AuditTrail
from sqlalchemy import text
from dga.assets.public import AssetDirectory
from dga.laboratory.public import SampleRegistry, ReceiveSample, SampleIdentityStatus
from tests.test_asset_search import official_assets, CURRENT_TRANSFORMER_ID, OLD_TRANSFORMER_ID, DUPLICATE_TRANSFORMER_B_ID, WHOLE_UNIT_ID as UNIT
from tests.test_sample_reception import reception_context, WHOLE_UNIT_ID, TRANSFORMER_ID, SITE_ID


def at(year, month=1, day=1):
    return datetime(year, month, day, tzinfo=timezone.utc)


def test_detaching_and_reinstalling_preserves_half_open_location_history(database_url):
    engine, _, actor = reception_context(database_url)
    lifecycle = AssetLifecycle(engine, clock=lambda: at(2026))
    initial = lifecycle.history(actor, TRANSFORMER_ID)
    lifecycle.move(actor, TRANSFORMER_ID, effective_at=at(2025),
                   destination='REPAIR_CENTER', reason='Remove for repair',
                   expected_revision=initial['revision'])
    detached = lifecycle.history(actor, TRANSFORMER_ID, effective_at=at(2025))
    assert detached['location']['kind'] == 'REPAIR_CENTER'
    assert detached['status'] == 'UNDER_REPAIR'
    assert lifecycle.history(actor, TRANSFORMER_ID, effective_at=at(2024, 12, 31))['location']['site_id'] == SITE_ID
    lifecycle.move(actor, TRANSFORMER_ID, effective_at=at(2025, 2),
                   destination='PARENT', parent_asset_id=WHOLE_UNIT_ID,
                   reason='Repair complete', expected_revision=detached['revision'])
    restored = lifecycle.history(actor, TRANSFORMER_ID)
    assert restored['location']['site_id'] == SITE_ID
    assert restored['status'] == 'IN_SERVICE'
    assert len(restored['events']) == 2
    engine.dispose()


def test_uninstalled_retired_asset_restores_to_spare_at_repair_center(official_assets):
    lifecycle, actor, _ = lifecycle_context(official_assets)
    lifecycle.change_status(actor, OLD_TRANSFORMER_ID, status='SPARE', effective_at=at(2025), reason='Authorized restoration', expected_revision=0)
    restored = lifecycle.history(actor, OLD_TRANSFORMER_ID)
    assert restored['location']['kind'] == 'REPAIR_CENTER'
    assert restored['status'] == 'SPARE'


def test_repair_center_sample_uses_formal_asset_without_fictitious_site(database_url):
    engine, _, actor = reception_context(database_url)
    lifecycle = AssetLifecycle(engine, clock=lambda: at(2026))
    lifecycle.move(actor, TRANSFORMER_ID, destination='REPAIR_CENTER', effective_at=at(2025), reason='Repair', expected_revision=0)
    directory = AssetDirectory(engine)
    matches = directory.search(actor, 'TX-CURRENT', effective_at=at(2025, 2))
    assert len(matches) == 1
    assert matches[0].location_kind == 'REPAIR_CENTER'
    assert matches[0].site_id is None
    registry = SampleRegistry(engine, directory, AuditTrail())
    sample = registry.receive(actor, ReceiveSample(sampled_at=at(2025, 2), received_at=at(2025, 2, 2),
        site_name='维修中心', equipment_serial='TX-CURRENT-2002', notes='', container_count=1,
        identity_status=SampleIdentityStatus.ASSOCIATED, formal_asset_id=TRANSFORMER_ID))
    assert sample.asset_snapshot.site_id is None
    assert sample.asset_snapshot.customer_id is None
    assert sample.asset_snapshot.location_kind == 'REPAIR_CENTER'
    lifecycle.move(actor, TRANSFORMER_ID, destination='PARENT', parent_asset_id=WHOLE_UNIT_ID,
        effective_at=at(2025, 3), reason='Reinstall', expected_revision=1)
    retrieved = registry.find_by_barcode(actor, sample.barcode_value)
    assert retrieved.asset_snapshot == sample.asset_snapshot
    engine.dispose()


def test_lifecycle_http_requires_csrf_and_returns_queryable_results(database_url):
    engine, _, _ = reception_context(database_url)
    with TestClient(create_app(Settings(database_url=database_url, cookie_secure=False, auth_allowed_origins='http://testserver'))) as client:
        login = client.post('/api/auth/login', headers={'Origin': 'http://testserver'}, json={'username': 'reception-admin', 'password': 'Changed reception passphrase 87!'})
        payload = {'effective_at': at(2025).isoformat(), 'reason': 'HTTP detach', 'expected_revision': 0, 'destination': 'REPAIR_CENTER'}
        assert client.post(f'/api/assets/equipment/{TRANSFORMER_ID}/move', json=payload).status_code == 403
        result = client.post(f'/api/assets/equipment/{TRANSFORMER_ID}/move', json=payload,
                            headers={'Origin': 'http://testserver', 'X-CSRF-Token': login.json()['csrf_token']})
        assert result.status_code == 200
        history = client.get(f'/api/assets/equipment/{TRANSFORMER_ID}/lifecycle').json()
        assert history['location']['kind'] == 'REPAIR_CENTER'
        assert client.get('/api/assets/catalog?repair_only=true').json()['total'] == 1
    engine.dispose()


def test_detached_equipment_remains_browsable_and_listed_at_repair_center(database_url):
    engine, _, actor = reception_context(database_url)
    lifecycle = AssetLifecycle(engine, clock=lambda: at(2026))
    lifecycle.move(actor, TRANSFORMER_ID, destination='REPAIR_CENTER', effective_at=at(2025), reason='Detach', expected_revision=0)
    detail = AssetDirectory(engine).equipment_detail(actor, TRANSFORMER_ID)
    assert detail['location']['kind'] == 'REPAIR_CENTER'
    assert detail['site'] is None
    assert [r['id'] for r in lifecycle.catalog(actor, repair_only=True, query='TX-CURRENT')['assets']] == [TRANSFORMER_ID]
    engine.dispose()


def test_competing_moves_allow_one_commit_and_reject_same_day_second_switch(database_url):
    engine, _, actor = reception_context(database_url)
    lifecycle = AssetLifecycle(engine, clock=lambda: at(2026))
    def detach():
        try:
            lifecycle.move(actor, TRANSFORMER_ID, destination='REPAIR_CENTER', effective_at=at(2025), reason='Concurrent detach', expected_revision=0)
            return 'ok'
        except AssetQueryError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(lambda _: detach(), range(2))) == ['ok', 'stale_asset_revision']
    with pytest.raises(AssetQueryError, match='one_move_per_day'):
        lifecycle.move(actor, TRANSFORMER_ID, destination='PARENT', parent_asset_id=WHOLE_UNIT_ID,
            effective_at=datetime(2025, 1, 1, 12, tzinfo=timezone.utc), reason='Same day reinstall', expected_revision=1)
    assert len(lifecycle.history(actor, TRANSFORMER_ID)['events']) == 1
    engine.dispose()


def lifecycle_context(engine):
    with engine.begin() as c:
        c.execute(text('TRUNCATE users,auth_sessions,user_roles,audit_logs CASCADE'))
    identity = IdentityService(engine)
    identity.bootstrap_admin('lifecycle', 'Lifecycle', 'Initial reception passphrase 43!')
    first = identity.login('lifecycle', 'Initial reception passphrase 43!')
    actor = identity.change_password(first.token, 'Initial reception passphrase 43!', 'Changed reception passphrase 87!').actor
    return AssetLifecycle(engine, clock=lambda: at(2026)), actor, identity


def test_replacement_is_atomic_and_keeps_samples_on_physical_transformer(official_assets):
    lifecycle, actor, identity = lifecycle_context(official_assets)
    registry = SampleRegistry(official_assets, AssetDirectory(official_assets), AuditTrail())
    sample = registry.receive(actor, ReceiveSample(sampled_at=at(2024, 6), received_at=at(2024, 6, 2),
        site_name='Prairie Sun', equipment_serial='TX-CURRENT-2002', container_count=1, notes='',
        identity_status=SampleIdentityStatus.ASSOCIATED, formal_asset_id=CURRENT_TRANSFORMER_ID))
    lifecycle.move(actor, DUPLICATE_TRANSFORMER_B_ID, destination='REPAIR_CENTER', effective_at=at(2024, 7),
                   reason='Prepare replacement', expected_revision=0)
    lifecycle.change_status(actor, DUPLICATE_TRANSFORMER_B_ID, status='SPARE', effective_at=at(2024, 8),
                            reason='Repair complete', expected_revision=1)
    # New asset has a later state change. The old detach must roll back when the
    # second half refuses this backdated replacement inside the transaction.
    with pytest.raises(AssetQueryError, match='use_history_correction'):
        lifecycle.replace_transformer(actor, CURRENT_TRANSFORMER_ID, replacement_id=DUPLICATE_TRANSFORMER_B_ID,
            effective_at=at(2024, 7, 15), reason='Invalid replacement date', expected_revision=0, replacement_revision=2)
    assert lifecycle.history(actor, CURRENT_TRANSFORMER_ID)['revision'] == 0
    assert lifecycle.history(actor, CURRENT_TRANSFORMER_ID)['location']['path'][-2]['id'] == UNIT
    with pytest.raises(AssetQueryError, match='stale_asset_revision'):
        lifecycle.replace_transformer(actor, CURRENT_TRANSFORMER_ID, replacement_id=DUPLICATE_TRANSFORMER_B_ID,
            effective_at=at(2025), reason='Replace', expected_revision=0, replacement_revision=0)
    assert lifecycle.history(actor, CURRENT_TRANSFORMER_ID)['revision'] == 0
    lifecycle.replace_transformer(actor, CURRENT_TRANSFORMER_ID, replacement_id=DUPLICATE_TRANSFORMER_B_ID,
        effective_at=at(2025), reason='Replace after failure', expected_revision=0, replacement_revision=2)
    old = lifecycle.history(actor, CURRENT_TRANSFORMER_ID)
    new = lifecycle.history(actor, DUPLICATE_TRANSFORMER_B_ID)
    assert old['status'] == 'UNDER_REPAIR'
    assert old['location']['kind'] == 'REPAIR_CENTER'
    assert new['location']['path'][-2]['id'] == UNIT
    assert new['status'] == 'IN_SERVICE'
    assert registry.find_by_barcode(actor, sample.barcode_value).asset_snapshot == sample.asset_snapshot
    assert registry.asset_test_history(actor, CURRENT_TRANSFORMER_ID)['total'] == 1
    assert registry.asset_test_history(actor, DUPLICATE_TRANSFORMER_B_ID)['total'] == 0
    assert 'TRANSFORMER_REPLACE' in [e['action_code'] for e in identity.audit_events(actor)]


def test_lifecycle_status_requires_location_and_reason_and_preserves_retired_tree(database_url):
    engine, _, actor = reception_context(database_url)
    lifecycle = AssetLifecycle(engine, clock=lambda: at(2026))
    with pytest.raises(AssetQueryError, match='status_requires_repair_center'):
        lifecycle.change_status(actor, TRANSFORMER_ID, status='SPARE', effective_at=at(2025), reason='Not detached', expected_revision=0)
    with pytest.raises(IdentityError):
        lifecycle.change_status(replace(actor, permissions=frozenset({'assets.read'})), WHOLE_UNIT_ID,
                                status='RETIRED', effective_at=at(2025), reason='Retire', expected_revision=0)
    lifecycle.change_status(actor, WHOLE_UNIT_ID, status='RETIRED', effective_at=at(2025), reason='Retire root', expected_revision=0)
    assert lifecycle.history(actor, TRANSFORMER_ID)['location']['site_id'] == SITE_ID
    assert lifecycle.history(actor, WHOLE_UNIT_ID)['status'] == 'RETIRED'
    with pytest.raises(AssetQueryError, match='disabled_asset_cannot_install'):
        lifecycle.move(actor, WHOLE_UNIT_ID, destination='SITE', site_id=SITE_ID, effective_at=at(2025, 2), reason='Move', expected_revision=1)
    lifecycle.change_status(actor, WHOLE_UNIT_ID, status='IN_SERVICE', effective_at=at(2025, 3), reason='Restore', expected_revision=1)
    assert lifecycle.history(actor, WHOLE_UNIT_ID)['status'] == 'IN_SERVICE'
    assert len(lifecycle.history(actor, WHOLE_UNIT_ID)['events']) == 2
    engine.dispose()


def test_correction_requires_permission_reason_and_rejects_overlap_or_cycle(database_url):
    engine, identity, actor = reception_context(database_url)
    lifecycle = AssetLifecycle(engine, clock=lambda: at(2026))
    lifecycle.move(actor, TRANSFORMER_ID, destination='REPAIR_CENTER', effective_at=at(2025), reason='Detach', expected_revision=0)
    history = lifecycle.history(actor, TRANSFORMER_ID)
    old = history['installations'][0]
    correction = dict(installation_id=old['id'], valid_from=at(2024), valid_to=at(2025, 2),
                      parent_asset_id=WHOLE_UNIT_ID, site_id=None, repair_center=False, reason='Date correction', expected_revision=1)
    with pytest.raises(IdentityError):
        lifecycle.correct_installation(replace(actor, permissions=frozenset({'assets.read', 'assets.write'})), TRANSFORMER_ID, **correction)
    with pytest.raises(AssetQueryError, match='conflicting_installation'):
        lifecycle.correct_installation(actor, TRANSFORMER_ID, **correction)
    assert lifecycle.history(actor, TRANSFORMER_ID)['revision'] == 1
    with pytest.raises(AssetQueryError, match='history_gap'):
        lifecycle.correct_installation(actor, TRANSFORMER_ID, **(correction | {'valid_to': at(2024, 12)}))
    repair = history['installations'][1]
    with pytest.raises(AssetQueryError, match='status_location_conflict'):
        lifecycle.correct_installation(actor, TRANSFORMER_ID, **(correction | {
            'installation_id': repair['id'], 'valid_from': at(2025), 'valid_to': None}))
    correction.update(valid_to=at(2025), valid_from=at(2023))
    with pytest.raises(AssetQueryError, match='reason_required'):
        lifecycle.correct_installation(actor, TRANSFORMER_ID, **(correction | {'reason': ' '}))
    lifecycle.correct_installation(actor, TRANSFORMER_ID, **correction)
    result = lifecycle.history(actor, TRANSFORMER_ID, effective_at=at(2023, 6))
    assert result['location']['site_id'] == SITE_ID
    event = next(e for e in result['events'] if e['action'] == 'ASSET_HISTORY_CORRECT')
    assert event['before_value'][str(TRANSFORMER_ID)]['installations'][0]['valid_from'].startswith('2024')
    assert event['after_value'][str(TRANSFORMER_ID)]['installations'][0]['valid_from'].startswith('2023')
    root = lifecycle.history(actor, WHOLE_UNIT_ID)['installations'][0]
    with pytest.raises(AssetQueryError, match='cyclic_installation'):
        lifecycle.correct_installation(actor, WHOLE_UNIT_ID, installation_id=root['id'], valid_from=at(2020), valid_to=None,
            parent_asset_id=TRANSFORMER_ID, site_id=None, repair_center=False, reason='Bad ancestry', expected_revision=0)
    assert 'ASSET_HISTORY_CORRECT' in [e['action_code'] for e in identity.audit_events(actor)]
    engine.dispose()
