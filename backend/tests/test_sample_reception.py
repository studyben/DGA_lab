from datetime import datetime, timezone
from tests.laboratory_seed import restore_placeholder_methods
from tests.identity_seed import seed_legacy_user
from uuid import UUID

from sqlalchemy import create_engine, text
from fastapi.testclient import TestClient

from dga.assets.public import AssetDirectory
from dga.laboratory.public import (
    ReceiveSample,
    SampleIdentityStatus,
    SampleRegistry,
)
from dga.shared.auth.public import AuditTrail, IdentityService
from dga.main import create_app
from dga.shared.config import Settings


CUSTOMER_ID = UUID("11000000-0000-0000-0000-000000000001")
SITE_ID = UUID("22000000-0000-0000-0000-000000000001")
WHOLE_UNIT_ID = UUID("33000000-0000-0000-0000-000000000001")
TRANSFORMER_ID = UUID("44000000-0000-0000-0000-000000000001")
INITIAL_PASSWORD = "Initial reception passphrase 43!"
CHANGED_PASSWORD = "Changed reception passphrase 87!"


def reception_context(database_url):
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE asset_installations,formal_assets,sites,customers,"
                "auth_sessions,user_roles,audit_logs,users CASCADE"
            )
        )
        restore_placeholder_methods(connection)
        values = {
            "customer": CUSTOMER_ID,
            "site": SITE_ID,
            "unit": WHOLE_UNIT_ID,
            "transformer": TRANSFORMER_ID,
        }
        connection.execute(
            text("INSERT INTO customers(id,customer_name) VALUES (:customer,'Prairie Solar LLC')"),
            values,
        )
        connection.execute(
            text("INSERT INTO sites(id,customer_id,site_name,location_text) VALUES (:site,:customer,'Prairie Sun','Texas, USA')"),
            values,
        )
        connection.execute(
            text(
                """INSERT INTO formal_assets
                (id,system_asset_number,asset_type,serial_number,model,material_number,lifecycle_status)
                VALUES
                (:unit,'SYS-PV-001','WHOLE_UNIT','INV-UNIT-7788','SG4400UD','MAT-UNIT-44','IN_SERVICE'),
                (:transformer,'SYS-TX-002','TRANSFORMER','TX-CURRENT-2002','TX-4400','MAT-TX-41','IN_SERVICE')"""
            ),
            values,
        )
        connection.execute(
            text(
                """INSERT INTO asset_installations
                (id,asset_id,parent_asset_id,site_id,valid_from,valid_to)
                VALUES
                ('55000000-0000-0000-0000-000000000001',:unit,NULL,:site,'2020-01-01T00:00:00Z',NULL),
                ('55000000-0000-0000-0000-000000000002',:transformer,:unit,NULL,'2024-01-01T00:00:00Z',NULL)"""
            ),
            {
                "site": SITE_ID,
                "unit": WHOLE_UNIT_ID,
                "transformer": TRANSFORMER_ID,
            },
        )
    identity = IdentityService(engine)
    seed_legacy_user(database_url, "reception-admin", "Reception Admin", INITIAL_PASSWORD, ['system_admin'])
    first = identity.login("reception-admin", INITIAL_PASSWORD)
    session = identity.change_password(first.token, INITIAL_PASSWORD, CHANGED_PASSWORD)
    return engine, identity, session.actor


def test_receive_formally_associated_sample_preserves_snapshot_and_shared_barcode(database_url):
    engine, identity, actor = reception_context(database_url)
    registry = SampleRegistry(engine, AssetDirectory(engine), AuditTrail())
    sampled_at = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)

    sample = registry.receive(
        actor,
        ReceiveSample(
            sampled_at=sampled_at,
            received_at=datetime(2025, 6, 2, 9, 30, tzinfo=timezone.utc),
            site_name="Contradictory handwritten site",
            equipment_serial="CONTRADICTORY-SERIAL",
            notes="Routine annual sample",
            container_count=2,
            identity_status=SampleIdentityStatus.ASSOCIATED,
            formal_asset_id=TRANSFORMER_ID,
        ),
    )

    assert sample.identity_status == SampleIdentityStatus.ASSOCIATED
    assert sample.site_name == "Prairie Sun"
    assert sample.equipment_serial == "TX-CURRENT-2002"
    assert sample.sample_number.startswith("DGA-20250602-")
    assert sample.barcode_value == sample.sample_number
    assert [container.container_number for container in sample.containers] == [
        f"{sample.sample_number}-C01",
        f"{sample.sample_number}-C02",
    ]
    assert sample.asset_snapshot is not None
    assert sample.asset_snapshot.customer_name == "Prairie Solar LLC"
    assert sample.asset_snapshot.site_name == "Prairie Sun"
    assert [node.serial_number for node in sample.asset_snapshot.equipment_path] == [
        "INV-UNIT-7788",
        "TX-CURRENT-2002",
    ]

    with engine.begin() as connection:
        connection.execute(
            text("UPDATE customers SET customer_name='Renamed Customer' WHERE id=:id"),
            {"id": CUSTOMER_ID},
        )
        connection.execute(
            text("UPDATE sites SET site_name='Renamed Site' WHERE id=:id"),
            {"id": SITE_ID},
        )
    retrieved = registry.find_by_barcode(actor, sample.barcode_value)

    assert retrieved.asset_snapshot is not None
    assert retrieved.asset_snapshot.customer_name == "Prairie Solar LLC"
    assert retrieved.asset_snapshot.site_name == "Prairie Sun"
    assert len(retrieved.containers) == 2
    action_codes = [event["action_code"] for event in identity.audit_events(actor)]
    assert "SAMPLE_RECEIVED" in action_codes
    assert "SAMPLE_ASSET_ASSOCIATED" in action_codes
    engine.dispose()


def test_identity_pending_reception_barcode_lookup_and_print_are_audited(database_url):
    engine, identity, actor = reception_context(database_url)
    directory = AssetDirectory(engine)
    sampled_at = datetime(2025, 7, 10, 16, 0, tzinfo=timezone.utc)
    assert directory.search(actor, "UNKNOWN-TX", effective_at=sampled_at) == ()

    settings = Settings(
        database_url=database_url,
        cookie_secure=False,
        auth_allowed_origins="http://127.0.0.1:8080",
    )
    with TestClient(create_app(settings)) as client:
        login = client.post(
            "/api/auth/login",
            headers={"Origin": "http://127.0.0.1:8080"},
            json={
                "username": "reception-admin",
                "password": CHANGED_PASSWORD,
            },
        )
        csrf = login.json()["csrf_token"]
        payload = {
            "sampled_at": "2025-07-10T16:00:00Z",
            "received_at": "2025-07-11T09:00:00Z",
            "site_name": "Unconfirmed field site",
            "equipment_serial": "UNKNOWN-TX",
            "notes": "Nameplate photo requested",
            "container_count": 3,
            "identity_status": "IDENTITY_PENDING",
            "formal_asset_id": None,
        }
        assert client.post("/api/laboratory/samples", json=payload).status_code == 403
        created = client.post(
            "/api/laboratory/samples",
            headers={
                "Origin": "http://127.0.0.1:8080",
                "X-CSRF-Token": csrf,
            },
            json=payload,
        )
        assert created.status_code == 201
        body = created.json()
        assert body["identity_status"] == "IDENTITY_PENDING"
        assert body["asset_snapshot"] is None
        assert len(body["containers"]) == 3

        found = client.get(
            f'/api/laboratory/samples/by-barcode/{body["barcode_value"]}'
        )
        assert found.status_code == 200
        assert found.json()["equipment_serial"] == "UNKNOWN-TX"
        printed = client.post(
            f'/api/laboratory/samples/{body["barcode_value"]}/label-prints',
            headers={
                "Origin": "http://127.0.0.1:8080",
                "X-CSRF-Token": csrf,
            },
        )
        assert printed.status_code == 204

    assert directory.search(actor, "UNKNOWN-TX", effective_at=sampled_at) == ()
    action_codes = [event["action_code"] for event in identity.audit_events(actor)]
    assert "SAMPLE_RECEIVED" in action_codes
    assert "SAMPLE_ASSET_ASSOCIATED" not in action_codes
    assert "BARCODE_LABEL_PRINTED" in action_codes
    engine.dispose()
