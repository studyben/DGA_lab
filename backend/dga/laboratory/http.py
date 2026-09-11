"""HTTP adapter for laboratory reception and typed test entry."""

import base64
from datetime import datetime
from decimal import Decimal
from typing import Callable, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from .public import (
    BreakdownVoltageResultInput,
    DgaResultInput,
    LaboratoryError,
    LaboratoryWorkbench,
    LaboratoryReports,
    MoistureResultInput,
    QualifiedMeasurement,
    RawAttachment,
    ReceiveSample,
    ResultQualifier,
    SampleIdentityStatus,
    SampleRegistry,
    TestSubmission,
    TestType,
    UpdateSampleBasics,
)


class ReceptionInput(BaseModel):
    sampled_at: datetime
    received_at: datetime
    site_name: str = Field(min_length=1, max_length=200)
    equipment_serial: str = Field(min_length=1, max_length=160)
    notes: str | None = Field(default=None, max_length=2000)
    container_count: int = Field(ge=1, le=20)
    identity_status: SampleIdentityStatus
    formal_asset_id: UUID | None = None


class MeasurementInput(BaseModel):
    qualifier: ResultQualifier
    value: Decimal | None = None


class DgaInput(BaseModel):
    kind: Literal['DGA']
    h2: MeasurementInput
    ch4: MeasurementInput
    c2h2: MeasurementInput
    c2h4: MeasurementInput
    c2h6: MeasurementInput
    co: MeasurementInput
    co2: MeasurementInput


class SingleValueInput(BaseModel):
    kind: Literal['MOISTURE', 'BREAKDOWN_VOLTAGE']
    result: MeasurementInput


class AttachmentInput(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=160)
    content_base64: str


class TestInput(BaseModel):
    test_type: TestType
    method_version_id: UUID
    measured_at: datetime
    instrument_name: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=2000)
    result: DgaInput | SingleValueInput
    attachment: AttachmentInput | None = None


class SampleBasicsInput(BaseModel):
    sampled_at: datetime
    received_at: datetime
    site_name: str = Field(min_length=1, max_length=200)
    equipment_serial: str = Field(min_length=1, max_length=160)
    notes: str | None = Field(default=None, max_length=2000)


class RemovalInput(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class ReportResultInput(BaseModel):
    test_id: UUID


class FinalizationInput(BaseModel):
    acknowledged_warning_codes: list[str] = Field(default_factory=list, max_length=100)


class WithdrawalInput(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


def _submission(payload: TestInput):
    def measurement(item):
        return QualifiedMeasurement(item.qualifier, item.value)

    if payload.result.kind != payload.test_type.value:
        raise LaboratoryError('result_type_mismatch')
    if isinstance(payload.result, DgaInput):
        result = DgaResultInput(**{
            code: measurement(getattr(payload.result, code))
            for code in ('h2', 'ch4', 'c2h2', 'c2h4', 'c2h6', 'co', 'co2')
        })
    elif payload.test_type == TestType.MOISTURE:
        result = MoistureResultInput(measurement(payload.result.result))
    else:
        result = BreakdownVoltageResultInput(measurement(payload.result.result))
    return TestSubmission(
        payload.test_type, payload.method_version_id, payload.measured_at,
        payload.instrument_name, payload.notes, result,
    )


def _attachment(payload: AttachmentInput | None):
    if not payload:
        return None
    try:
        content = base64.b64decode(payload.content_base64, validate=True)
    except ValueError as error:
        raise LaboratoryError('invalid_attachment') from error
    return RawAttachment(payload.filename, payload.content_type, content)


def laboratory_router(
    registry: SampleRegistry,
    workbench: LaboratoryWorkbench,
    reports: LaboratoryReports,
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

    @router.get('/workbench/{barcode_value}')
    def load_workbench(barcode_value: str, actor=Depends(actor_dependency)):
        return workbench.load(actor, barcode_value)

    @router.get('/reports/by-barcode/{barcode_value}')
    def report_status(barcode_value: str, actor=Depends(actor_dependency)):
        return reports.get_report_by_barcode(actor, barcode_value)

    @router.patch('/samples/{barcode_value}')
    def update_sample(barcode_value: str, payload: SampleBasicsInput, actor=Depends(mutation_actor_dependency)):
        return workbench.update_sample(actor, barcode_value, UpdateSampleBasics(**payload.model_dump()))

    @router.post('/samples/{barcode_value}/tests', status_code=201)
    def add_test(barcode_value: str, payload: TestInput, actor=Depends(mutation_actor_dependency)):
        return workbench.add_test(actor, barcode_value, _submission(payload), _attachment(payload.attachment))

    @router.put('/samples/{barcode_value}/tests/{test_id}')
    def update_test(barcode_value: str, test_id: UUID, payload: TestInput, actor=Depends(mutation_actor_dependency)):
        return workbench.update_test(actor, barcode_value, test_id, _submission(payload), _attachment(payload.attachment))

    @router.delete('/samples/{barcode_value}/tests/{test_id}', status_code=204)
    def remove_test(barcode_value: str, test_id: UUID, payload: RemovalInput, actor=Depends(mutation_actor_dependency)):
        workbench.remove_test(actor, barcode_value, test_id, payload.reason)
        return Response(status_code=204)

    @router.put('/samples/{barcode_value}/report-result')
    def select_report_result(
        barcode_value: str,
        payload: ReportResultInput,
        actor=Depends(mutation_actor_dependency),
    ):
        return workbench.select_report_result(actor, barcode_value, payload.test_id)

    @router.post('/samples/{barcode_value}/finalization')
    def finalize(
        barcode_value: str,
        payload: FinalizationInput,
        actor=Depends(mutation_actor_dependency),
    ):
        return workbench.finalize(
            actor,
            barcode_value,
            tuple(payload.acknowledged_warning_codes),
        )

    @router.post('/samples/{barcode_value}/finalization-withdrawals')
    def withdraw_finalization(
        barcode_value: str,
        payload: WithdrawalInput,
        actor=Depends(mutation_actor_dependency),
    ):
        return workbench.withdraw_finalization(actor, barcode_value, payload.reason)

    return router
