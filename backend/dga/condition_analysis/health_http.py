"""Authenticated adapters; rule and evaluation decisions stay in analysis."""
from uuid import UUID
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field
from fastapi.encoders import jsonable_encoder
from decimal import Decimal
from sqlalchemy.exc import SQLAlchemyError
from .rules import HealthRuleInput, HealthError


def wire(value):
    return jsonable_encoder(value,custom_encoder={Decimal:str})


class RevisionInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_revision: int=Field(ge=0,strict=True)
    reason: str=Field(min_length=1,max_length=1000)


class UpdateInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_revision: int=Field(ge=0,strict=True)
    rule: HealthRuleInput


def health_router(rules,health,actor_dependency,mutation_actor_dependency):
    def no_store(response: Response):
        response.headers['Cache-Control']='no-store'
    def available():
        try:
            yield
        except SQLAlchemyError as error:
            raise HealthError('health_source_unavailable',503) from error
    router=APIRouter(prefix='/api/condition-analysis',dependencies=[Depends(no_store),Depends(available)])

    @router.get('/rules')
    def listing(actor=Depends(actor_dependency)):
        return wire(rules.list(actor))

    @router.get('/rule-methods')
    def methods(actor=Depends(actor_dependency)):
        return rules.methods(actor)

    @router.post('/rules',status_code=201)
    def create(payload: HealthRuleInput,actor=Depends(mutation_actor_dependency)):
        return wire(rules.create(actor,payload))

    @router.put('/rules/{identifier}')
    def update(identifier: UUID,payload: UpdateInput,actor=Depends(mutation_actor_dependency)):
        return wire(rules.update(actor,identifier,payload.rule,payload.expected_revision))

    @router.get('/rules/{identifier}/history')
    def history(identifier: UUID,actor=Depends(actor_dependency)):
        return rules.history(actor,identifier)

    @router.post('/rules/{identifier}/copy',status_code=201)
    def copy(identifier: UUID,actor=Depends(mutation_actor_dependency)):
        return wire(rules.copy(actor,identifier))

    @router.post('/rules/{identifier}/activate')
    def activate(identifier: UUID,payload: RevisionInput,actor=Depends(mutation_actor_dependency)):
        return wire(rules.activate(actor,identifier,payload.expected_revision,payload.reason))

    @router.post('/rules/{identifier}/retire')
    def retire(identifier: UUID,payload: RevisionInput,actor=Depends(mutation_actor_dependency)):
        return wire(rules.retire(actor,identifier,payload.expected_revision,payload.reason))

    @router.get('/health/{asset_id}')
    def current(asset_id: UUID,actor=Depends(actor_dependency)):
        return health.query(actor,asset_id)

    @router.get('/health/{asset_id}/evaluations/{evaluation_id}')
    def evidence(asset_id: UUID,evaluation_id: UUID,actor=Depends(actor_dependency)):
        return health.evaluation(actor,asset_id,evaluation_id)

    return router
