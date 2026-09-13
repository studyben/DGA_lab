"""Transport for laboratory operations; business meanings stay in operations."""
from fastapi import APIRouter, Depends, Query, Response
from .operations import LedgerQuery


def operations_router(operations, actor_dependency, mutation_actor):
    def no_store(response: Response):
        response.headers['Cache-Control'] = 'no-store'
    router = APIRouter(prefix='/api/laboratory', dependencies=[Depends(no_store)])

    @router.get('/dashboard')
    def dashboard(actor=Depends(actor_dependency)):
        return operations.dashboard(actor)

    @router.get('/ledger')
    def ledger(query: LedgerQuery = Query(), actor=Depends(actor_dependency)):
        return operations.ledger(actor, **query.model_dump())

    return router
