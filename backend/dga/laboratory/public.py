"""Public application interface for oil sample reception and barcode lookup."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Callable
from uuid import UUID, uuid4

from sqlalchemy import Engine, text
from pydantic import ValidationError
from .asset_history import AssetHistoryQuery

from dga.assets.public import AssetDirectory, AssetType, SamplingAssetContext
from dga.shared.auth.public import (
    ActorContext,
    AuditTrail,
    require_permission,
)
from dga.shared.contracts import ModuleDescriptor

from .errors import LaboratoryError

MODULE = ModuleDescriptor(code='laboratory', label='DGA 实验室')


def access_context(actor: ActorContext) -> dict:
    require_permission(actor, 'laboratory.read')
    return {'module': MODULE.code, 'actor_id': str(actor.user_id)}


class SampleIdentityStatus(StrEnum):
    ASSOCIATED = 'ASSOCIATED'
    IDENTITY_PENDING = 'IDENTITY_PENDING'


class _AuditAction(StrEnum):
    SAMPLE_RECEIVED = 'SAMPLE_RECEIVED'
    SAMPLE_ASSET_ASSOCIATED = 'SAMPLE_ASSET_ASSOCIATED'
    BARCODE_LABEL_PRINTED = 'BARCODE_LABEL_PRINTED'


@dataclass(frozen=True)
class ReceiveSample:
    sampled_at: datetime
    received_at: datetime
    site_name: str
    equipment_serial: str
    notes: str | None
    container_count: int
    identity_status: SampleIdentityStatus
    formal_asset_id: UUID | None = None


@dataclass(frozen=True)
class AssetSnapshotNode:
    id: UUID
    system_asset_number: str
    asset_type: str
    serial_number: str
    model: str | None
    material_number: str | None
    lifecycle_status: str


@dataclass(frozen=True)
class SampleAssetSnapshot:
    formal_asset_id: UUID
    customer_id: UUID | None
    customer_name: str
    site_id: UUID | None
    site_name: str
    site_location: str | None
    equipment_path: tuple[AssetSnapshotNode, ...]
    location_kind: str = 'SITE'


@dataclass(frozen=True)
class SampleContainer:
    id: UUID
    container_number: str
    ordinal: int


@dataclass(frozen=True)
class OilSample:
    id: UUID
    sample_number: str
    barcode_value: str
    identity_status: SampleIdentityStatus
    sampled_at: datetime
    received_at: datetime
    site_name: str
    equipment_serial: str
    notes: str | None
    formal_asset_id: UUID | None
    asset_snapshot: SampleAssetSnapshot | None
    containers: tuple[SampleContainer, ...]
    created_at: datetime


def _snapshot(context: SamplingAssetContext) -> SampleAssetSnapshot:
    return SampleAssetSnapshot(
        formal_asset_id=context.asset.id,
        customer_id=context.customer_id,
        customer_name=context.customer_name,
        site_id=context.site_id,
        site_name=context.site_name,
        site_location=context.site_location,
        location_kind=context.location_kind,
        equipment_path=tuple(
            AssetSnapshotNode(
                id=asset.id,
                system_asset_number=asset.system_asset_number,
                asset_type=asset.asset_type.value,
                serial_number=asset.serial_number,
                model=asset.model,
                material_number=asset.material_number,
                lifecycle_status=asset.lifecycle_status.value,
            )
            for asset in context.equipment_path
        ),
    )


def _decode_snapshot(value: dict | None) -> SampleAssetSnapshot | None:
    if value is None:
        return None
    return SampleAssetSnapshot(
        formal_asset_id=UUID(value['formal_asset_id']),
        customer_id=UUID(value['customer_id']) if value['customer_id'] else None,
        customer_name=value['customer_name'],
        site_id=UUID(value['site_id']) if value['site_id'] else None,
        site_name=value['site_name'],
        site_location=value['site_location'],
        location_kind=value.get('location_kind', 'SITE'),
        equipment_path=tuple(
            AssetSnapshotNode(
                id=UUID(node['id']),
                system_asset_number=node['system_asset_number'],
                asset_type=node['asset_type'],
                serial_number=node['serial_number'],
                model=node['model'],
                material_number=node['material_number'],
                lifecycle_status=node['lifecycle_status'],
            )
            for node in value['equipment_path']
        ),
    )


class SampleRegistry:
    """Register oil samples and retrieve their stable identity by shared barcode."""

    def __init__(
        self,
        engine: Engine,
        asset_directory: AssetDirectory,
        audit_trail: AuditTrail,
        *,
        clock: Callable[[], datetime] | None = None,
    ):
        self._engine = engine
        self._assets = asset_directory
        self._audit = audit_trail
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def asset_test_history(self, actor: ActorContext, asset_id: UUID, **filters) -> dict:
        """Asset readers may see summaries, not the laboratory workbench or raw files."""
        require_permission(actor, 'assets.read')
        from .asset_history import asset_test_history
        try:
            query = AssetHistoryQuery(**filters)
        except ValidationError as error:
            raise LaboratoryError('invalid_asset_history_query') from error
        return asset_test_history(self._engine, asset_id, query)

    def receive(self, actor: ActorContext, command: ReceiveSample) -> OilSample:
        require_permission(actor, 'laboratory.write')
        self._validate(command)
        snapshot = None
        if command.identity_status == SampleIdentityStatus.ASSOCIATED:
            context = self._assets.resolve_sampling_context(
                actor, command.formal_asset_id, sampled_at=command.sampled_at
            )
            if context.asset.asset_type != AssetType.TRANSFORMER:
                raise LaboratoryError('sample_requires_transformer')
            snapshot = _snapshot(context)

        site_name = snapshot.site_name if snapshot else command.site_name.strip()
        equipment_serial = (
            snapshot.equipment_path[-1].serial_number
            if snapshot
            else command.equipment_serial.strip()
        )

        sample_id = uuid4()
        created_at = self._clock()
        with self._engine.begin() as connection:
            sequence = connection.execute(
                text("SELECT nextval('oil_sample_number_seq')")
            ).scalar_one()
            sample_number = f"DGA-{command.received_at:%Y%m%d}-{sequence:06d}"
            connection.execute(
                text(
                    """INSERT INTO oil_samples
                    (id,sample_number,barcode_value,identity_status,sampled_at,received_at,
                     site_name,equipment_serial,notes,formal_asset_id,asset_snapshot,created_by,created_at)
                    VALUES
                    (:id,:number,:barcode,:status,:sampled,:received,:site,:serial,:notes,
                     :asset,CAST(:snapshot AS jsonb),:actor,:created)"""
                ),
                {
                    'id': sample_id,
                    'number': sample_number,
                    'barcode': sample_number,
                    'status': command.identity_status.value,
                    'sampled': command.sampled_at,
                    'received': command.received_at,
                    'site': site_name,
                    'serial': equipment_serial,
                    'notes': command.notes.strip() if command.notes else None,
                    'asset': command.formal_asset_id,
                    'snapshot': json.dumps(asdict(snapshot), default=str) if snapshot else None,
                    'actor': actor.user_id,
                    'created': created_at,
                },
            )
            for ordinal in range(1, command.container_count + 1):
                connection.execute(
                    text(
                        """INSERT INTO sample_containers
                        (id,oil_sample_id,container_number,ordinal)
                        VALUES (:id,:sample,:number,:ordinal)"""
                    ),
                    {
                        'id': uuid4(),
                        'sample': sample_id,
                        'number': f'{sample_number}-C{ordinal:02d}',
                        'ordinal': ordinal,
                    },
                )
            self._audit.append(
                connection,
                actor,
                _AuditAction.SAMPLE_RECEIVED,
                entity_id=sample_id,
            )
            if snapshot:
                self._audit.append(
                    connection,
                    actor,
                    _AuditAction.SAMPLE_ASSET_ASSOCIATED,
                    entity_id=sample_id,
                )
        return self.find_by_barcode(actor, sample_number)

    def find_by_barcode(self, actor: ActorContext, barcode_value: str) -> OilSample:
        require_permission(actor, 'laboratory.read')
        barcode = barcode_value.strip().upper()
        if not 1 <= len(barcode) <= 40:
            raise LaboratoryError('invalid_barcode')
        with self._engine.connect() as connection:
            row = connection.execute(
                text("SELECT * FROM oil_samples WHERE barcode_value=:barcode"),
                {'barcode': barcode},
            ).mappings().first()
            if not row:
                raise LaboratoryError('sample_not_found', 404)
            containers = tuple(
                SampleContainer(
                    id=container['id'],
                    container_number=container['container_number'],
                    ordinal=container['ordinal'],
                )
                for container in connection.execute(
                    text(
                        """SELECT id,container_number,ordinal FROM sample_containers
                        WHERE oil_sample_id=:sample ORDER BY ordinal"""
                    ),
                    {'sample': row['id']},
                ).mappings()
            )
            return OilSample(
                id=row['id'],
                sample_number=row['sample_number'],
                barcode_value=row['barcode_value'],
                identity_status=SampleIdentityStatus(row['identity_status']),
                sampled_at=row['sampled_at'],
                received_at=row['received_at'],
                site_name=row['site_name'],
                equipment_serial=row['equipment_serial'],
                notes=row['notes'],
                formal_asset_id=row['formal_asset_id'],
                asset_snapshot=_decode_snapshot(row['asset_snapshot']),
                containers=containers,
                created_at=row['created_at'],
            )

    def record_label_print(self, actor: ActorContext, barcode_value: str) -> None:
        require_permission(actor, 'laboratory.write')
        sample = self.find_by_barcode(actor, barcode_value)
        with self._engine.begin() as connection:
            self._audit.append(
                connection,
                actor,
                _AuditAction.BARCODE_LABEL_PRINTED,
                entity_id=sample.id,
            )

    @staticmethod
    def _validate(command: ReceiveSample) -> None:
        if command.sampled_at.tzinfo is None or command.received_at.tzinfo is None:
            raise LaboratoryError('timestamp_requires_timezone')
        if command.received_at < command.sampled_at:
            raise LaboratoryError('received_before_sampled')
        if not 1 <= len(command.site_name.strip()) <= 200:
            raise LaboratoryError('invalid_site_name')
        if not 1 <= len(command.equipment_serial.strip()) <= 160:
            raise LaboratoryError('invalid_equipment_serial')
        if command.notes and len(command.notes.strip()) > 2000:
            raise LaboratoryError('invalid_notes')
        if not 1 <= command.container_count <= 20:
            raise LaboratoryError('invalid_container_count')
        if command.identity_status == SampleIdentityStatus.ASSOCIATED:
            if command.formal_asset_id is None:
                raise LaboratoryError('formal_asset_required')
        elif command.formal_asset_id is not None:
            raise LaboratoryError('pending_identity_has_asset')


def http_router(registry: SampleRegistry, workbench, reports, actor_dependency: Callable, mutation_actor_dependency: Callable):
    """Compose the laboratory-owned HTTP adapter."""
    from .http import laboratory_router

    return laboratory_router(registry, workbench, reports, actor_dependency, mutation_actor_dependency)


# Result-entry contracts are re-exported here so callers cross one laboratory seam.
from .workbench import (  # noqa: E402
    BreakdownVoltageResultInput,
    DgaResultInput,
    FinalizationAssessment,
    FinalizationEvent,
    FinalizationEventType,
    FinalizationWarningSource,
    LaboratoryWorkbench,
    MethodConfiguration,
    MethodField,
    MoistureResultInput,
    QualifiedMeasurement,
    RawAttachment,
    ResultQualifier,
    StoredAttachment,
    TestRecord,
    TestSubmission,
    TestType,
    TestingStatus,
    UpdateSampleBasics,
    WorkbenchSample,
)

from .reports import (  # noqa: E402
    LaboratoryReports,
    ReportFile,
    ReportState,
    ReportStatus,
    StaleReportClaim,
)

from .operations import LaboratoryOperations  # noqa: E402
from .operations_http import operations_router  # noqa: E402
