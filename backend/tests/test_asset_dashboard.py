from datetime import datetime, timezone
from dataclasses import replace
from uuid import uuid4
from decimal import Decimal
import pytest
from sqlalchemy import text

from dga.assets.public import AssetDirectory, AssetQueryError
from dga.shared.auth.public import IdentityError
from tests.test_asset_search import official_assets, asset_reader, SITE_ID


@pytest.fixture
def dashboard_assets(official_assets):
    with official_assets.begin() as c:
        c.execute(text("""
            INSERT INTO site_product_lines VALUES
            ('20000000-0000-0000-0000-000000000001','PV',100,NULL),
            ('20000000-0000-0000-0000-000000000001','ESS',20,80),
            ('20000000-0000-0000-0000-000000000002','ESS',NULL,NULL);
            UPDATE sites SET grid_year=2020,grid_status='COMPLETED',
                operation_status='OPERATIONAL',commissioning_date='2020-06-01';
            UPDATE formal_assets SET product_line='PV',machine_type='INVERTER_UNIT',power_mw=4.4
                WHERE system_asset_number IN ('SYS-PV-001','SYS-PV-003');
            UPDATE formal_assets SET product_line='ESS',machine_type='ESS_SYSTEM',power_mw=5,energy_mwh=20
                WHERE system_asset_number='SYS-ESS-002';
            UPDATE formal_assets SET machine_type='TRANSFORMER' WHERE asset_type='TRANSFORMER';
        """))
    return official_assets


def test_line_metrics_use_all_filtered_sites_before_pagination(dashboard_assets):
    directory = AssetDirectory(dashboard_assets)
    pv = directory.dashboard(asset_reader(), product_line='PV', page_size=1)
    assert pv['site_count'] == 1
    assert pv['sites'][0]['power_mw'] == Decimal('100')
    inverter = next(t for t in pv['machine_totals'] if t['machine_type'] == 'INVERTER_UNIT')
    assert inverter['count'] == 2
    assert inverter['power_mw'] == Decimal('8.8')
    ess = directory.dashboard(asset_reader(), product_line='ESS', page_size=1)
    assert ess['site_count'] == 2
    assert ess['customer_count'] == 2
    assert len(ess['sites']) == 1
    assert ess['machine_totals'][0]['machine_type'] == 'ESS_SYSTEM'
    assert ess['machine_totals'][0]['energy_mwh'] == Decimal('20')
    filtered = directory.dashboard(asset_reader(), product_line='ESS', customer='Prairie', location='texas')
    assert filtered['site_count'] == filtered['customer_count'] == 1
    assert filtered['machine_totals'] == []
    assert filtered['sites'][0]['energy_mwh'] == Decimal('80')


def test_dashboard_keeps_unknown_legacy_classification_out_of_product_totals(official_assets):
    directory = AssetDirectory(official_assets, clock=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))
    result = directory.dashboard(asset_reader(), product_line='PV')
    assert result['site_count'] == 0
    assert result['customer_count'] == 0
    assert result['sites'] == []
    assert result['machine_totals'] == []


def test_site_details_show_official_fields_and_only_direct_current_equipment(dashboard_assets):
    directory = AssetDirectory(dashboard_assets)
    result = directory.site_detail(asset_reader(), SITE_ID, product_line='PV', page_size=1, direction='desc')
    assert result['site']['grid_year'] == 2020
    assert result['site']['operation_status'] == 'OPERATIONAL'
    assert str(result['site']['commissioning_date']) == '2020-06-01'
    assert result['equipment_count'] == 2
    assert len(result['equipment']) == 1
    assert result['equipment'][0]['serial_number'] == 'INV-UNIT-3003'
    filtered = directory.site_detail(asset_reader(), SITE_ID, product_line='PV', serial='7788', model='SG4400')
    assert filtered['equipment_count'] == 1
    assert filtered['equipment'][0]['system_asset_number'] == 'SYS-PV-001'
    assert directory.site_detail(asset_reader(), SITE_ID, product_line='ESS')['equipment_count'] == 0


def test_unknown_capacity_and_literal_filters_and_stable_pages(dashboard_assets):
    d = AssetDirectory(dashboard_assets)
    result = d.dashboard(asset_reader(), product_line='ESS', sort='power_mw', direction='desc', page_size=1, page=2)
    assert result['sites'][0]['site_name'] == 'Desert Star'
    assert result['sites'][0]['power_mw'] is None
    assert result['sites'][0]['energy_mwh'] is None
    assert d.dashboard(asset_reader(), site='%')['site_count'] == 0
    assert d.dashboard(asset_reader(), location='Texas', grid_year=2020, grid_status='COMPLETED', operation_status='OPERATIONAL')['site_count'] == 1
    assert d.dashboard(asset_reader(), grid_status='IN_PROGRESS')['site_count'] == 0
    with pytest.raises(AssetQueryError, match='site_not_found'):
        d.site_detail(asset_reader(), uuid4())


def test_active_installations_and_inactive_ancestors_control_machine_totals(dashboard_assets):
    d = AssetDirectory(dashboard_assets, clock=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))
    transformers = next(t for t in d.dashboard(asset_reader())['machine_totals'] if t['machine_type'] == 'TRANSFORMER')
    assert transformers['count'] == 2
    assert transformers['power_mw'] is None
    assert transformers['missing_power_count'] == 2
    with dashboard_assets.begin() as c:
        c.execute(text("UPDATE formal_assets SET lifecycle_status='RETIRED' WHERE system_asset_number='SYS-PV-003'"))
        c.execute(text("UPDATE asset_installations SET valid_to='2026-01-01' WHERE asset_id='30000000-0000-0000-0000-000000000001'"))
    assert d.dashboard(asset_reader())['machine_totals'] == []
    # Retired direct assets remain visible with their actual lifecycle status.
    assert d.site_detail(asset_reader(), SITE_ID)['equipment_count'] == 1


@pytest.mark.parametrize('filters', [dict(product_line='BAD'),dict(page=0),dict(page_size=101),dict(sort='id; DROP TABLE sites'),dict(grid_year=1800),dict(grid_status='MAINTENANCE')])
def test_invalid_dashboard_queries_are_rejected(dashboard_assets, filters):
    with pytest.raises(AssetQueryError, match='invalid_dashboard_query'):
        AssetDirectory(dashboard_assets).dashboard(asset_reader(), **filters)


def test_asset_permissions_apply_to_both_queries(dashboard_assets):
    actor = replace(asset_reader(), permissions=frozenset())
    d = AssetDirectory(dashboard_assets)
    with pytest.raises(IdentityError):
        d.dashboard(actor)
    with pytest.raises(IdentityError):
        d.site_detail(actor, SITE_ID)
    with pytest.raises(AssetQueryError, match='invalid_equipment_query'):
        d.site_detail(asset_reader(), SITE_ID, sort='bad')
