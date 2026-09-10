"""HTTP adapter for the laboratory reception interface."""

from datetime import datetime
from typing import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from .public import ReceiveSample, SampleIdentityStatus, SampleRegistry


class ReceptionInput(BaseModel):
    sampled_at: datetime
    received_at: datetime
    site_name: str = Field(min_length=1, max_length=200)
    equipment_serial: str = Field(min_length=1, max_length=160)
    notes: str | None = Field(default=None, max_length=2000)
    container_count: int = Field(ge=1, le=20)
    identity_status: SampleIdentityStatus
    formal_asset_id: UUID | None = None


def laboratory_router(
    registry: SampleRegistry,
    actor_dependency: Callable,
    mutation_actor_dependency: Callable,
):
    router = APIRouter(prefix='/api/laboratory')

    @router.post('/samples', status_code=201)
    def receive(payload: ReceptionInput, actor=Depends(mutation_actor_dependency)):
        return registry.receive(actor, ReceiveSample(**payload.model_dump()))

    @router.get('/samples/by-barcode/{barcode_value}')
    def find_by_barcode(barcode_value: str, actor=Depends(actor_dependency)):
        return registry.find_by_barcode(actor, barcode_value)

    @router.post('/samples/{barcode_value}/label-prints', status_code=204)
    def record_label_print(
        barcode_value: str,
        actor=Depends(mutation_actor_dependency),
    ):
        registry.record_label_print(actor, barcode_value)
        return Response(status_code=204)

    return router
