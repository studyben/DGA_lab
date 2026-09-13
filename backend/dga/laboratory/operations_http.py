"""Transport for laboratory operations; business meanings stay in operations."""
from fastapi import APIRouter, Depends, Query, Response
from uuid import UUID
from .operations import LedgerQuery, ConfirmIdentityInput, ChangeContainerInput


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

    @router.get('/operations/{barcode}')
    def sample_operations(barcode: str, actor=Depends(actor_dependency)):
        return operations.sample_operations(actor,barcode)

    @router.post('/operations/{barcode}/identity')
    def confirm_identity(barcode: str, command: ConfirmIdentityInput, actor=Depends(mutation_actor)):
        return operations.confirm_identity(actor,barcode,**command.model_dump())

    @router.post('/operations/{barcode}/containers/{container_id}')
    def change_container(barcode: str, container_id: UUID, command: ChangeContainerInput, actor=Depends(mutation_actor)):
        return operations.change_container(actor,barcode,container_id,**command.model_dump())

    return router
