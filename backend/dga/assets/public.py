"""Public application interface for official asset identity and history."""
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Callable
from uuid import UUID

from sqlalchemy import Engine, text
from pydantic import ValidationError

from .dashboard import DashboardQuery, EquipmentQuery

from dga.shared.auth.public import ActorContext, require_permission
from dga.shared.contracts import ModuleDescriptor

MODULE = ModuleDescriptor(code='assets', label='资产管理')


def access_context(actor: ActorContext) -> dict:
    require_permission(actor, 'assets.read')
    return {'module': MODULE.code, 'actor_id': str(actor.user_id)}


class AssetQueryError(Exception):
    """Stable error raised when an asset query cannot be answered safely."""

    def __init__(self, code: str, status: int = 422):
        self.code = code
        self.status = status
        super().__init__(code)


class AssetType(StrEnum):
    WHOLE_UNIT = 'WHOLE_UNIT'
    TRANSFORMER = 'TRANSFORMER'


class LifecycleStatus(StrEnum):
    COMMISSIONING = 'COMMISSIONING'
    IN_SERVICE = 'IN_SERVICE'
    OUT_OF_SERVICE = 'OUT_OF_SERVICE'
    RETIRED = 'RETIRED'
    MERGED = 'MERGED'


class MatchReason(StrEnum):
    EXACT_SERIAL = 'EXACT_SERIAL'
    SERIAL_PREFIX = 'SERIAL_PREFIX'
    SERIAL_CONTAINS = 'SERIAL_CONTAINS'


@dataclass(frozen=True)
class FormalAsset:
    id: UUID
    system_asset_number: str
    asset_type: AssetType
    serial_number: str
    model: str | None
    material_number: str | None
    lifecycle_status: LifecycleStatus


@dataclass(frozen=True)
class SamplingAssetContext:
    asset: FormalAsset
    customer_id: UUID
    customer_name: str
    site_id: UUID
    site_name: str
    site_location: str | None
    equipment_path: tuple[FormalAsset, ...]


@dataclass(frozen=True)
class AssetSearchMatch(SamplingAssetContext):
    match_reason: MatchReason
    linkable_transformers: tuple[FormalAsset, ...]


def _asset(row) -> FormalAsset:
    return FormalAsset(
        id=row['id'],
        system_asset_number=row['system_asset_number'],
        asset_type=AssetType(row['asset_type']),
        serial_number=row['serial_number'],
        model=row['model'],
        material_number=row['material_number'],
        lifecycle_status=LifecycleStatus(row['lifecycle_status']),
    )


class AssetDirectory:
    """Read-only official asset queries used by the portal and laboratory module."""

    def __init__(
        self,
        engine: Engine,
        *,
        clock: Callable[[], datetime] | None = None,
    ):
        self._engine = engine
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def dashboard(self, actor: ActorContext, **filters) -> dict:
        require_permission(actor, 'assets.read')
        from .dashboard import dashboard
        try:
            query = DashboardQuery(**filters)
        except ValidationError as error:
            raise AssetQueryError('invalid_dashboard_query') from error
        return dashboard(self._engine, query, self._clock())

    def site_detail(self, actor: ActorContext, site_id: UUID, **filters) -> dict:
        require_permission(actor, 'assets.read')
        from .dashboard import site_detail
        try:
            query = EquipmentQuery(**filters)
        except ValidationError as error:
            raise AssetQueryError('invalid_equipment_query') from error
        result = site_detail(self._engine, site_id, query, self._clock())
        if result is None:
            raise AssetQueryError('site_not_found', 404)
        return result

    def search(
        self,
        actor: ActorContext,
        serial_query: str,
        *,
        effective_at: datetime | None = None,
        limit: int = 20,
    ) -> tuple[AssetSearchMatch, ...]:
        require_permission(actor, 'assets.read')
        query = serial_query.strip()
        if not query or len(query) > 160 or not 1 <= limit <= 50:
            raise AssetQueryError('invalid_asset_search')
        at = effective_at or self._clock()
        if at.tzinfo is None:
            raise AssetQueryError('effective_at_requires_timezone')

        with self._engine.connect() as connection:
            matches = []
            normalized_query = query.lower()
            escaped_query = normalized_query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            offset = 0
            batch_size = max(50, limit)
            while len(matches) < limit:
                rows = connection.execute(
                    text(
                        """SELECT * FROM formal_assets
                        WHERE lower(serial_number) LIKE :contains ESCAPE '\\'
                        ORDER BY
                            CASE
                                WHEN lower(serial_number) = :exact THEN 0
                                WHEN lower(serial_number) LIKE :prefix ESCAPE '\\' THEN 1
                                ELSE 2
                            END,
                            serial_number,system_asset_number
                        LIMIT :batch_size OFFSET :offset"""
                    ),
                    {
                        'exact': normalized_query,
                        'prefix': escaped_query + '%',
                        'contains': '%' + escaped_query + '%',
                        'batch_size': batch_size,
                        'offset': offset,
                    },
                ).mappings().all()
                if not rows:
                    break
                offset += len(rows)
                for row in rows:
                    try:
                        context = self._context(connection, row['id'], at)
                    except AssetQueryError:
                        # An asset without an effective path is not linkable to a sample.
                        continue
                    normalized_serial = row['serial_number'].lower()
                    reason = (
                        MatchReason.EXACT_SERIAL
                        if normalized_serial == normalized_query
                        else MatchReason.SERIAL_PREFIX
                        if normalized_serial.startswith(normalized_query)
                        else MatchReason.SERIAL_CONTAINS
                    )
                    children = ()
                    if row['asset_type'] == AssetType.WHOLE_UNIT:
                        children = tuple(
                            _asset(child)
                            for child in connection.execute(
                                text(
                                    """SELECT child.* FROM formal_assets child
                                    JOIN asset_installations installation
                                      ON installation.asset_id=child.id
                                    WHERE installation.parent_asset_id=:parent
                                      AND child.asset_type='TRANSFORMER'
                                      AND installation.valid_from<=:at
                                      AND (installation.valid_to IS NULL OR installation.valid_to>:at)
                                    ORDER BY child.serial_number,child.system_asset_number"""
                                ),
                                {'parent': row['id'], 'at': at},
                            ).mappings()
                        )
                    matches.append(
                        AssetSearchMatch(
                            asset=context.asset,
                            customer_id=context.customer_id,
                            customer_name=context.customer_name,
                            site_id=context.site_id,
                            site_name=context.site_name,
                            site_location=context.site_location,
                            equipment_path=context.equipment_path,
                            match_reason=reason,
                            linkable_transformers=children,
                        )
                    )
                    if len(matches) == limit:
                        break
            return tuple(matches)

    def resolve_sampling_context(
        self,
        actor: ActorContext,
        asset_id: UUID,
        *,
        sampled_at: datetime,
    ) -> SamplingAssetContext:
        """Resolve the site and complete equipment path at the sampling instant."""
        require_permission(actor, 'assets.read')
        if sampled_at.tzinfo is None:
            raise AssetQueryError('sampled_at_requires_timezone')
        with self._engine.connect() as connection:
            return self._context(connection, asset_id, sampled_at)

    def _context(self, connection, asset_id: UUID, at: datetime) -> SamplingAssetContext:
        row = connection.execute(
            text('SELECT * FROM formal_assets WHERE id=:id'), {'id': asset_id}
        ).mappings().first()
        if not row:
            raise AssetQueryError('asset_not_found', 404)

        selected = _asset(row)
        path = [selected]
        visited = {selected.id}
        current = selected
        for _ in range(20):
            installations = connection.execute(
                text(
                    """SELECT parent_asset_id,site_id FROM asset_installations
                    WHERE asset_id=:asset
                      AND valid_from<=:at
                      AND (valid_to IS NULL OR valid_to>:at)
                    ORDER BY valid_from DESC LIMIT 2"""
                ),
                {'asset': current.id, 'at': at},
            ).mappings().all()
            if len(installations) != 1:
                raise AssetQueryError('asset_context_unavailable', 409)
            installation = installations[0]
            if installation['site_id']:
                location = connection.execute(
                    text(
                        """SELECT s.id,s.site_name,s.location_text,
                                  c.id AS customer_id,c.customer_name
                        FROM sites s JOIN customers c ON c.id=s.customer_id
                        WHERE s.id=:site"""
                    ),
                    {'site': installation['site_id']},
                ).mappings().first()
                if not location:
                    raise AssetQueryError('asset_context_unavailable', 409)
                return SamplingAssetContext(
                    asset=selected,
                    customer_id=location['customer_id'],
                    customer_name=location['customer_name'],
                    site_id=location['id'],
                    site_name=location['site_name'],
                    site_location=location['location_text'],
                    equipment_path=tuple(reversed(path)),
                )
            parent = connection.execute(
                text('SELECT * FROM formal_assets WHERE id=:id'),
                {'id': installation['parent_asset_id']},
            ).mappings().first()
            if not parent or parent['id'] in visited:
                raise AssetQueryError('asset_context_unavailable', 409)
            current = _asset(parent)
            visited.add(current.id)
            path.append(current)
        raise AssetQueryError('asset_context_unavailable', 409)


def http_router(directory: AssetDirectory, actor_dependency: Callable):
    """Compose the asset-owned HTTP adapter without exposing internal imports."""
    from .http import assets_router

    return assets_router(directory, actor_dependency)
