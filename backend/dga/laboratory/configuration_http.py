"""Strict authenticated configuration adapter; laboratory service owns behavior."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import Field

from .configuration import (ConfigInput, TypeCode, TypeSettingsInput, MethodVersionInput,
    InstrumentInput, CalibrationInput, PackageInput)


class ActivationInput(ConfigInput):
    is_active: bool = Field(strict=True)


class InstrumentStatusInput(ConfigInput):
    status: Literal['ACTIVE', 'OUT_OF_SERVICE', 'RETIRED']
    expected_status: Literal['ACTIVE', 'OUT_OF_SERVICE', 'RETIRED']


class PackageApplicationInput(ConfigInput):
    package_id: UUID
    expected_package_id: UUID | None = None


def configuration_router(service, actor_dependency, mutation_actor_dependency):
    def no_store(response: Response):
        response.headers['Cache-Control'] = 'no-store'

    router = APIRouter(prefix='/api/laboratory', dependencies=[Depends(no_store)])

    @router.get('/configuration')
    def catalog(response: Response, actor=Depends(actor_dependency)):
        response.headers['Cache-Control'] = 'no-store'
        return service.catalog(actor)

    @router.post('/configuration/methods', status_code=201)
    def create_method(payload: MethodVersionInput, actor=Depends(mutation_actor_dependency)):
        return service.create_method(actor, payload)

    @router.put('/configuration/methods/{identifier}/activation', status_code=204)
    def activate_method(identifier: UUID, payload: ActivationInput, actor=Depends(mutation_actor_dependency)):
        service.set_method_active(actor, identifier, payload.is_active)

    @router.put('/configuration/types/{code}', status_code=204)
    def update_type(code: TypeCode, payload: TypeSettingsInput, actor=Depends(mutation_actor_dependency)):
        service.set_type(actor, code, payload)

    @router.post('/configuration/instruments', status_code=201)
    def create_instrument(payload: InstrumentInput, actor=Depends(mutation_actor_dependency)):
        return service.create_instrument(actor, payload)

    @router.put('/configuration/instruments/{identifier}/status', status_code=204)
    def update_instrument(identifier: UUID, payload: InstrumentStatusInput, actor=Depends(mutation_actor_dependency)):
        service.set_instrument_status(actor, identifier, payload.status, payload.expected_status)

    @router.post('/configuration/instruments/{identifier}/calibrations', status_code=201)
    def add_calibration(identifier: UUID, payload: CalibrationInput, actor=Depends(mutation_actor_dependency)):
        return service.add_calibration(actor, identifier, payload)

    @router.post('/configuration/packages', status_code=201)
    def create_package(payload: PackageInput, actor=Depends(mutation_actor_dependency)):
        return service.create_package(actor, payload)

    @router.put('/samples/{barcode}/package')
    def apply_package(barcode: str, payload: PackageApplicationInput, actor=Depends(mutation_actor_dependency)):
        return service.apply_package(actor, barcode, payload.package_id, payload.expected_package_id)

    return router
