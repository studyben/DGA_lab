"""Laboratory-owned projection of current immutable finalized measurements."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Protocol, Literal
from uuid import UUID

from sqlalchemy import Engine, text

from dga.shared.auth.public import ActorContext, require_permission
from .errors import LaboratoryError
from .finalization_facts import FinalizationFacts


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
    finalization_token: UUID | None = None
    sampling_context: dict | None = None
    result_origin: Literal['LOCAL_LAB', 'EXTERNAL_LAB'] | None = None
    sampled_at_precision: Literal['INSTANT'] | None = None
    measured_at_precision: Literal['INSTANT'] | None = None
    sampling_context_verification: Literal['VERIFIED', 'PHYSICAL_IDENTITY_ONLY'] | None = None


def finalized_measurement_evidence(point: FinalizedMeasurement) -> dict:
    evidence = asdict(point)
    for key in ('result_origin', 'sampled_at_precision', 'measured_at_precision', 'sampling_context_verification'):
        if evidence[key] is None:
            del evidence[key]
    return evidence


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
            rows = connection.execute(text('''SELECT s.id AS candidate_sample_id,f.* FROM oil_samples s
                LEFT JOIN laboratory_finalization_facts f ON f.oil_sample_id=s.id
                    AND f.finalization_token=s.testing_finalization_token
                WHERE COALESCE(f.physical_asset_id,s.formal_asset_id)=ANY(CAST(:assets AS uuid[])) AND s.identity_status='ASSOCIATED'
                    AND s.testing_status='FINALIZED' AND s.testing_finalization_token IS NOT NULL
                    AND (CAST(:start AS timestamptz) IS NULL OR COALESCE(f.sampled_at,s.sampled_at)>=:start)
                    AND (CAST(:end AS timestamptz) IS NULL OR COALESCE(f.sampled_at,s.sampled_at)<:end)
                ORDER BY COALESCE(f.sampled_at,s.sampled_at),s.id'''), {'assets': list(asset_ids), 'start': start, 'end': end}).mappings().all()
        points = []
        try:
            for row in rows:
                if row['oil_sample_id'] is None:
                    raise LaboratoryError('finalization_facts_unavailable', 503)
                decoded = FinalizationFacts.decode(row)
                snapshot = decoded.measurement_snapshot()
                metadata = decoded.snapshot['read_metadata'] if decoded.schema_version == 2 else {}
                sample = snapshot.sample
                for result in snapshot.selected_results:
                    method = result.method
                    for field in method.fields:
                        code = field.code
                        reading = result.result[code.lower() if result.test_type == 'DGA' else 'result']
                        points.append(FinalizedMeasurement(
                            row['candidate_sample_id'], result.test_id, sample.barcode, sample.sampled_at.astimezone(timezone.utc),
                            result.measured_at.astimezone(timezone.utc), result.test_type, code, method.method_version_id,
                            method.display_name, method.version_label, field.unit_code, method.configuration is not None,
                            reading.qualifier, reading.value, sample.site_name, sample.equipment_serial,
                            result.instrument_name, tuple(snapshot.acknowledged_warning_codes),row['physical_asset_id'],
                            row['finalization_token'], sample.asset_snapshot, **metadata))
        except (LaboratoryError, KeyError, ValueError, TypeError, ArithmeticError) as error:
            raise LaboratoryError('trend_snapshot_unavailable', 503) from error
        return tuple(points)
