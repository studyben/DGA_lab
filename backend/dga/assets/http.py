"""HTTP adapter for the official asset application interface."""
from datetime import datetime
from typing import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from .public import AssetDirectory


def assets_router(directory: AssetDirectory, actor_dependency: Callable):
    router = APIRouter(prefix='/api/assets')

    @router.get('/search')
    def search(
        q: str = Query(min_length=1, max_length=160),
        effective_at: datetime | None = None,
        actor=Depends(actor_dependency),
    ):
        return directory.search(actor, q, effective_at=effective_at)

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
