from datetime import datetime, timezone
from uuid import UUID
from dataclasses import replace
import pytest
from sqlalchemy import text

from dga.assets.public import AssetDirectory, AssetQueryError
from dga.shared.auth.public import IdentityError
from tests.test_asset_dashboard import dashboard_assets
from tests.test_asset_search import official_assets, asset_reader


UNIT = UUID('30000000-0000-0000-0000-000000000001')


def test_current_equipment_details_offer_recursive_navigation(dashboard_assets):
    directory = AssetDirectory(dashboard_assets, clock=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))
    detail = directory.equipment_detail(asset_reader(), UNIT)
    assert detail['equipment']['serial_number'] == 'INV-UNIT-7788'
    assert detail['equipment']['machine_type'] == 'INVERTER_UNIT'
    assert detail['health_status'] == 'UNASSESSED'
    assert [child['serial_number'] for child in detail['children']] == ['TX-CURRENT-2002']
    child = directory.equipment_detail(asset_reader(), detail['children'][0]['id'])
    assert [node['id'] for node in child['path']] == [UNIT, detail['children'][0]['id']]
    assert child['children'] == []
    assert child['site']['site_name'] == 'Prairie Sun'


def test_optional_type_fields_and_access_errors(dashboard_assets):
    directory = AssetDirectory(dashboard_assets)
    detail = directory.equipment_detail(asset_reader(), UNIT)
    assert detail['equipment']['display_name'] == 'SYS-PV-001'
    assert detail['equipment']['commissioning_date'] is None
    with dashboard_assets.begin() as connection:
        connection.execute(text("""UPDATE formal_assets SET equipment_name='储能电池柜',
            tag_number='BAT-01', machine_type='BATTERY_CABINET', battery_manufacturer='示例电芯厂',
            commissioning_date='2025-01-02' WHERE id=:id"""), {'id': UNIT})
    equipment = directory.equipment_detail(asset_reader(), UNIT)['equipment']
    assert equipment['display_name'] == 'BAT-01'
    assert equipment['battery_manufacturer'] == '示例电芯厂'
    assert str(equipment['commissioning_date']) == '2025-01-02'
    with pytest.raises(IdentityError):
        directory.equipment_detail(replace(asset_reader(), permissions=frozenset()), UNIT)
    with pytest.raises(AssetQueryError, match='asset_not_found'):
        directory.equipment_detail(asset_reader(), UUID(int=0))


def test_device_tree_rejects_cycles(dashboard_assets):
    directory = AssetDirectory(dashboard_assets)
    child_id = directory.equipment_detail(asset_reader(), UNIT)['children'][0]['id']
    with dashboard_assets.begin() as connection:
        connection.execute(text('UPDATE asset_installations SET site_id=NULL,parent_asset_id=:child WHERE asset_id=:unit'), {'child': child_id, 'unit': UNIT})
    with pytest.raises(AssetQueryError, match='asset_context_unavailable'):
        directory.equipment_detail(asset_reader(), UNIT)


def test_site_equipment_can_be_filtered_by_displayed_name(dashboard_assets):
    with dashboard_assets.begin() as connection:
        connection.execute(text("UPDATE formal_assets SET tag_number='INV-01' WHERE id=:id"), {'id': UNIT})
    directory = AssetDirectory(dashboard_assets)
    result = directory.site_detail(asset_reader(), UUID('20000000-0000-0000-0000-000000000001'), name='INV-01', sort='display_name')
    assert result['equipment_count'] == 1
    assert result['equipment'][0]['display_name'] == 'INV-01'


def test_device_tree_rejects_overlapping_effective_parents(dashboard_assets):
    with dashboard_assets.begin() as connection:
        connection.execute(text("""INSERT INTO asset_installations(id,asset_id,site_id,valid_from,valid_to)
            VALUES ('66000000-0000-0000-0000-000000000001',:id,
            '20000000-0000-0000-0000-000000000002','2025-01-01','2027-01-01')"""), {'id': UNIT})
    directory = AssetDirectory(dashboard_assets, clock=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))
    with pytest.raises(AssetQueryError, match='asset_context_unavailable'):
        directory.equipment_detail(asset_reader(), UNIT)
