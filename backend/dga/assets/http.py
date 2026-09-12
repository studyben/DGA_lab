"""HTTP adapter for the official asset application interface."""
from datetime import datetime
from typing import Callable, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from .public import AssetDirectory, AssetLifecycle, DashboardQuery, EquipmentQuery


class ChangeInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    effective_at: datetime
    expected_revision: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=1000)


class MoveInput(ChangeInput):
    destination: Literal['SITE', 'PARENT', 'REPAIR_CENTER']
    parent_asset_id: UUID | None = None
    site_id: UUID | None = None


class StatusInput(ChangeInput):
    status: Literal['IN_SERVICE', 'UNDER_REPAIR', 'SPARE', 'RETIRED']


class ReplacementInput(ChangeInput):
    replacement_id: UUID
    replacement_revision: int = Field(ge=0)


class CorrectionInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    installation_id: UUID
    valid_from: datetime
    valid_to: datetime | None = None
    parent_asset_id: UUID | None = None
    site_id: UUID | None = None
    repair_center: bool = False
    expected_revision: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=1000)


def assets_router(directory: AssetDirectory, actor_dependency: Callable, lifecycle: AssetLifecycle, mutation_actor: Callable):
    router = APIRouter(prefix='/api/assets')

    @router.get('/catalog')
    def catalog(query: str = Query(default='', max_length=200), repair_only: bool = False,
                page: int = Query(default=1, ge=1, le=100000), actor=Depends(actor_dependency)):
        return lifecycle.catalog(actor, query=query, repair_only=repair_only, page=page)

    @router.get('/equipment/{asset_id}/lifecycle')
    def history(asset_id: UUID, effective_at: datetime | None = None, actor=Depends(actor_dependency)):
        return lifecycle.history(actor, asset_id, effective_at=effective_at)

    @router.post('/equipment/{asset_id}/move')
    def move(asset_id: UUID, body: MoveInput, actor=Depends(mutation_actor)):
        return {'event_id': lifecycle.move(actor, asset_id, **body.model_dump())}

    @router.post('/equipment/{asset_id}/status')
    def status(asset_id: UUID, body: StatusInput, actor=Depends(mutation_actor)):
        return {'event_id': lifecycle.change_status(actor, asset_id, **body.model_dump())}

    @router.post('/equipment/{asset_id}/replace')
    def replace(asset_id: UUID, body: ReplacementInput, actor=Depends(mutation_actor)):
        return {'event_id': lifecycle.replace_transformer(actor, asset_id, **body.model_dump())}

    @router.post('/equipment/{asset_id}/correct')
    def correct(asset_id: UUID, body: CorrectionInput, actor=Depends(mutation_actor)):
        return {'event_id': lifecycle.correct_installation(actor, asset_id, **body.model_dump())}

    @router.get('/dashboard')
    def dashboard(query: DashboardQuery = Query(), actor=Depends(actor_dependency)):
        return directory.dashboard(actor, **query.model_dump())

    @router.get('/sites/{site_id}')
    def site_detail(site_id: UUID, query: EquipmentQuery = Query(), actor=Depends(actor_dependency)):
        return directory.site_detail(actor, site_id, **query.model_dump())

    @router.get('/search')
    def search(
        q: str = Query(min_length=1, max_length=160),
        effective_at: datetime | None = None,
        actor=Depends(actor_dependency),
    ):
        return directory.search(actor, q, effective_at=effective_at)

    @router.get('/equipment/{asset_id}')
    def equipment_detail(asset_id: UUID, actor=Depends(actor_dependency)):
        return directory.equipment_detail(actor, asset_id)

    @router.get('/{asset_id}/sampling-context')
    def sampling_context(
        asset_id: UUID,
        sampled_at: datetime,
        actor=Depends(actor_dependency),
    ):
        return directory.resolve_sampling_context(
            actor, asset_id, sampled_at=sampled_at
        )

    return router
