from datetime import datetime, timezone
from uuid import UUID

import pytest
from sqlalchemy import create_engine, text

from dga.assets.public import AssetDirectory
from dga.shared.auth.public import ActorContext


CUSTOMER_ID = UUID("10000000-0000-0000-0000-000000000001")
SITE_ID = UUID("20000000-0000-0000-0000-000000000001")
WHOLE_UNIT_ID = UUID("30000000-0000-0000-0000-000000000001")
OLD_TRANSFORMER_ID = UUID("40000000-0000-0000-0000-000000000001")
CURRENT_TRANSFORMER_ID = UUID("40000000-0000-0000-0000-000000000002")
SECOND_CUSTOMER_ID = UUID("10000000-0000-0000-0000-000000000002")
SECOND_SITE_ID = UUID("20000000-0000-0000-0000-000000000002")
SECOND_UNIT_ID = UUID("30000000-0000-0000-0000-000000000002")
THIRD_UNIT_ID = UUID("30000000-0000-0000-0000-000000000003")
DUPLICATE_TRANSFORMER_A_ID = UUID("40000000-0000-0000-0000-000000000003")
DUPLICATE_TRANSFORMER_B_ID = UUID("40000000-0000-0000-0000-000000000004")


def asset_reader() -> ActorContext:
    return ActorContext(
        user_id=UUID("00000000-0000-0000-0000-000000000004"),
        username="asset-reader",
        display_name="Asset Reader",
        roles=frozenset({"lab_admin"}),
        permissions=frozenset({"assets.read"}),
        must_change_password=False,
    )


@pytest.fixture
def official_assets(database_url):
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE asset_installations, formal_assets, sites, customers CASCADE"
            )
        )
        connection.execute(
            text("INSERT INTO customers(id,customer_name) VALUES (:id,:name)"),
            {"id": CUSTOMER_ID, "name": "Prairie Solar LLC"},
        )
        connection.execute(
            text("INSERT INTO customers(id,customer_name) VALUES (:id,:name)"),
            {"id": SECOND_CUSTOMER_ID, "name": "Desert Storage Inc"},
        )
        connection.execute(
            text(
                """INSERT INTO sites(id,customer_id,site_name,location_text)
                VALUES (:id,:customer,:name,:location)"""
            ),
            {
                "id": SITE_ID,
                "customer": CUSTOMER_ID,
                "name": "Prairie Sun",
                "location": "Texas, USA",
            },
        )
        connection.execute(
            text(
                """INSERT INTO sites(id,customer_id,site_name,location_text)
                VALUES (:id,:customer,:name,:location)"""
            ),
            {
                "id": SECOND_SITE_ID,
                "customer": SECOND_CUSTOMER_ID,
                "name": "Desert Star",
                "location": "Arizona, USA",
            },
        )
        connection.execute(
            text(
                """INSERT INTO formal_assets
                (id,system_asset_number,asset_type,serial_number,model,material_number,lifecycle_status)
                VALUES
                (:unit_id,'SYS-PV-001','WHOLE_UNIT','INV-UNIT-7788','SG4400UD','MAT-UNIT-44','IN_SERVICE'),
                (:old_id,'SYS-TX-001','TRANSFORMER','TX-OLD-1001','TX-4400','MAT-TX-40','RETIRED'),
                (:current_id,'SYS-TX-002','TRANSFORMER','TX-CURRENT-2002','TX-4400','MAT-TX-41','IN_SERVICE'),
                (:unit_2,'SYS-ESS-002','WHOLE_UNIT','PCS-UNIT-2002','SC5000UD','MAT-UNIT-50','IN_SERVICE'),
                (:unit_3,'SYS-PV-003','WHOLE_UNIT','INV-UNIT-3003','SG4400UD','MAT-UNIT-44','IN_SERVICE'),
                (:duplicate_a,'SYS-TX-D01','TRANSFORMER','TX-DUP-9009','TX-4400-A','MAT-TX-D1','IN_SERVICE'),
                (:duplicate_b,'SYS-TX-D02','TRANSFORMER','TX-DUP-9009','TX-5000-B','MAT-TX-D2','IN_SERVICE')"""
            ),
            {
                "unit_id": WHOLE_UNIT_ID,
                "old_id": OLD_TRANSFORMER_ID,
                "current_id": CURRENT_TRANSFORMER_ID,
                "unit_2": SECOND_UNIT_ID,
                "unit_3": THIRD_UNIT_ID,
                "duplicate_a": DUPLICATE_TRANSFORMER_A_ID,
                "duplicate_b": DUPLICATE_TRANSFORMER_B_ID,
            },
        )
        connection.execute(
            text(
                """INSERT INTO asset_installations
                (id,asset_id,parent_asset_id,site_id,valid_from,valid_to)
                VALUES
                ('50000000-0000-0000-0000-000000000001',:unit,NULL,:site,'2020-01-01T00:00:00Z',NULL),
                ('50000000-0000-0000-0000-000000000002',:old,:unit,NULL,'2020-01-01T00:00:00Z','2024-01-01T00:00:00Z'),
                ('50000000-0000-0000-0000-000000000003',:current,:unit,NULL,'2024-01-01T00:00:00Z',NULL),
                ('50000000-0000-0000-0000-000000000004',:unit_2,NULL,:site_2,'2021-01-01T00:00:00Z',NULL),
                ('50000000-0000-0000-0000-000000000005',:unit_3,NULL,:site,'2022-01-01T00:00:00Z',NULL),
                ('50000000-0000-0000-0000-000000000006',:duplicate_a,:unit_3,NULL,'2022-01-01T00:00:00Z',NULL),
                ('50000000-0000-0000-0000-000000000007',:duplicate_b,:unit_2,NULL,'2021-01-01T00:00:00Z',NULL)"""
            ),
            {
                "unit": WHOLE_UNIT_ID,
                "old": OLD_TRANSFORMER_ID,
                "current": CURRENT_TRANSFORMER_ID,
                "site": SITE_ID,
                "unit_2": SECOND_UNIT_ID,
                "unit_3": THIRD_UNIT_ID,
                "site_2": SECOND_SITE_ID,
                "duplicate_a": DUPLICATE_TRANSFORMER_A_ID,
                "duplicate_b": DUPLICATE_TRANSFORMER_B_ID,
            },
        )
    try:
        yield engine
    finally:
        engine.dispose()


def test_whole_unit_serial_expands_to_transformer_installed_at_sample_time(
    official_assets,
):
    directory = AssetDirectory(official_assets)

    matches = directory.search(
        asset_reader(),
        "inv-unit-7788",
        effective_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
    )

    assert len(matches) == 1
    match = matches[0]
    assert match.asset.serial_number == "INV-UNIT-7788"
    assert match.match_reason == "EXACT_SERIAL"
    assert match.customer_name == "Prairie Solar LLC"
    assert match.site_name == "Prairie Sun"
    assert [asset.serial_number for asset in match.linkable_transformers] == [
        "TX-CURRENT-2002"
    ]


def test_partial_duplicate_serials_return_fields_needed_for_disambiguation(
    official_assets,
):
    directory = AssetDirectory(official_assets)

    matches = directory.search(
        asset_reader(),
        "dup-9009",
        effective_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
    )

    assert {
        (
            match.asset.system_asset_number,
            match.customer_name,
            match.site_name,
            match.asset.model,
            match.asset.lifecycle_status,
            match.match_reason,
        )
        for match in matches
    } == {
        (
            "SYS-TX-D01",
            "Prairie Solar LLC",
            "Prairie Sun",
            "TX-4400-A",
            "IN_SERVICE",
            "SERIAL_CONTAINS",
        ),
        (
            "SYS-TX-D02",
            "Desert Storage Inc",
            "Desert Star",
            "TX-5000-B",
            "IN_SERVICE",
            "SERIAL_CONTAINS",
        ),
    }


def test_sampling_context_uses_the_installation_valid_at_the_historical_time(
    official_assets,
):
    directory = AssetDirectory(official_assets)

    context = directory.resolve_sampling_context(
        asset_reader(),
        OLD_TRANSFORMER_ID,
        sampled_at=datetime(2023, 5, 12, 14, 30, tzinfo=timezone.utc),
    )

    assert context.customer_name == "Prairie Solar LLC"
    assert context.site_name == "Prairie Sun"
    assert context.site_location == "Texas, USA"
    assert [asset.serial_number for asset in context.equipment_path] == [
        "INV-UNIT-7788",
        "TX-OLD-1001",
    ]
    assert context.asset.id == OLD_TRANSFORMER_ID
