"""Authenticated alarm adapters; no lifecycle decisions here."""
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError
from .alarm_query import AlarmQuery
from .health_http import wire
from .rules import HealthError


class AcknowledgeInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_revision: int=Field(ge=0,strict=True)
    note: str=Field(min_length=1,max_length=1000)


def alarm_router(alarms,actor_dependency,mutation_actor_dependency):
    def no_store(response: Response):
        response.headers['Cache-Control']='no-store'
    def available():
        try:
            yield
        except SQLAlchemyError as error:
            raise HealthError('alarm_source_unavailable',503) from error
    router=APIRouter(prefix='/api/condition-analysis/alarms',dependencies=[Depends(no_store),Depends(available)])

    @router.get('')
    def listing(query: Annotated[AlarmQuery,Query()],actor=Depends(actor_dependency)):
        return wire(alarms.query(actor,query))

    @router.get('/{identifier}')
    def detail(identifier: UUID,actor=Depends(actor_dependency)):
        return wire(alarms.detail(actor,identifier))

    @router.post('/{identifier}/acknowledgement')
    def acknowledge(identifier: UUID,payload: AcknowledgeInput,actor=Depends(mutation_actor_dependency)):
        return wire(alarms.acknowledge(actor,identifier,payload.expected_revision,payload.note))

    return router
