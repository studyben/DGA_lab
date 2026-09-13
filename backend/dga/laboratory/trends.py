"""Laboratory-owned projection of current finalized report measurements."""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Protocol, Literal
from uuid import UUID

from sqlalchemy import Engine, text
from pydantic import BaseModel, AwareDatetime, Field, model_validator

from dga.shared.auth.public import ActorContext, require_permission
from .errors import LaboratoryError
from .configuration import TYPE_FIELDS, TypeCode, MethodVersionInput


class _Reading(BaseModel):
    qualifier: Literal['EQ', 'ND', 'LT', 'GT']
    value: Decimal | None = Field(ge=0, max_digits=18, decimal_places=6, allow_inf_nan=False)

    @model_validator(mode='after')
    def pairing(self):
        if (self.qualifier == 'ND') != (self.value is None):
            raise ValueError('invalid qualified measurement')
        return self


class _Field(BaseModel):
    code: str
    unit_code: str | None = Field(min_length=1, max_length=40)


class _Method(BaseModel):
    method_version_id: UUID
    display_name: str
    version_label: str
    fields: list[_Field]
    configuration: MethodVersionInput | None = None


class _Selected(BaseModel):
    test_id: UUID
    test_type: TypeCode
    method: _Method
    measured_at: AwareDatetime
    instrument_name: str | None = None
    result: dict[str, _Reading]

    @model_validator(mode='after')
    def typed_fields(self):
        codes = [f.code for f in self.method.fields]
        expected = TYPE_FIELDS[self.test_type]
        keys = {c.lower() for c in expected} if self.test_type == 'DGA' else {'result'}
        if len(codes) != len(expected) or set(codes) != set(expected) or set(self.result) != keys:
            raise ValueError('invalid typed result fields')
        return self


class _Sample(BaseModel):
    barcode: str
    sampled_at: AwareDatetime
    site_name: str
    equipment_serial: str


class _Snapshot(BaseModel):
    schema_version: Literal[1]
    sample: _Sample
    selected_results: list[_Selected] = Field(min_length=1, max_length=3)
    acknowledged_warning_codes: list[str]

    @model_validator(mode='after')
    def unique_types(self):
        if len({r.test_type for r in self.selected_results}) != len(self.selected_results):
            raise ValueError('duplicate selected type')
        return self


@dataclass(frozen=True)
class FinalizedMeasurement:
    sample_id: UUID
    test_id: UUID
    barcode: str
    sampled_at: datetime
    measured_at: datetime
    test_type: str
    analyte: str
    method_version_id: UUID
    method_name: str
    version_label: str
    unit: str | None
    method_configured: bool
    qualifier: str
    value: Decimal | None
    site_name: str
    equipment_serial: str
    instrument_name: str | None
    warnings: tuple[str, ...]
    asset_id: UUID | None = None


class FinalizedResultReader(Protocol):
    def finalized_measurements(self, actor: ActorContext, asset_id: UUID,
                               start: datetime | None, end: datetime | None) -> tuple[FinalizedMeasurement, ...]: ...


class HealthResultReader(Protocol):
    def finalized_measurements_for_assets(self, actor: ActorContext, asset_ids: tuple[UUID, ...],
        start: datetime | None = None, end: datetime | None = None) -> tuple[FinalizedMeasurement, ...]: ...


class LaboratoryTrendSource:
    def __init__(self, engine: Engine):
        self._engine = engine

    def finalized_measurements(self, actor: ActorContext, asset_id: UUID,
                               start: datetime | None = None, end: datetime | None = None) -> tuple[FinalizedMeasurement, ...]:
        return self.finalized_measurements_for_assets(actor,(asset_id,),start,end)

    def finalized_measurements_for_assets(self, actor: ActorContext, asset_ids: tuple[UUID, ...],
                               start: datetime | None = None, end: datetime | None = None) -> tuple[FinalizedMeasurement, ...]:
        require_permission(actor, 'analysis.read')
        if not asset_ids:
            return ()
        with self._engine.connect() as connection:
            rows = connection.execute(text('''SELECT s.id,s.formal_asset_id,r.report_snapshot FROM oil_samples s
                JOIN laboratory_reports r ON r.oil_sample_id=s.id
                    AND r.finalization_token=s.testing_finalization_token
                WHERE s.formal_asset_id=ANY(CAST(:assets AS uuid[])) AND s.identity_status='ASSOCIATED'
                    AND s.testing_status='FINALIZED'
                    AND (CAST(:start AS timestamptz) IS NULL OR s.sampled_at>=:start)
                    AND (CAST(:end AS timestamptz) IS NULL OR s.sampled_at<:end)
                ORDER BY s.sampled_at,s.id'''), {'assets': list(asset_ids), 'start': start, 'end': end}).mappings().all()
        points = []
        try:
            for row in rows:
                snapshot = _Snapshot.model_validate(row['report_snapshot'])
                sample = snapshot.sample
                for result in snapshot.selected_results:
                    method = result.method
                    for field in method.fields:
                        code = field.code
                        reading = result.result[code.lower() if result.test_type == 'DGA' else 'result']
                        points.append(FinalizedMeasurement(
                            row['id'], result.test_id, sample.barcode, sample.sampled_at.astimezone(timezone.utc),
                            result.measured_at.astimezone(timezone.utc), result.test_type, code, method.method_version_id,
                            method.display_name, method.version_label, field.unit_code, method.configuration is not None,
                            reading.qualifier, reading.value, sample.site_name, sample.equipment_serial,
                            result.instrument_name, tuple(snapshot.acknowledged_warning_codes),row['formal_asset_id']))
        except (KeyError, ValueError, TypeError, ArithmeticError) as error:
            raise LaboratoryError('trend_snapshot_unavailable', 503) from error
        return tuple(points)
