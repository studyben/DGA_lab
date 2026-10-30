"""Current laboratory report lifecycle behind the laboratory application seam."""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from hashlib import sha256
from pathlib import PurePath
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Engine, text
from sqlalchemy.engine import Connection

from dga.shared.auth.public import ActorContext, AuditTrail, IdentityService, require_permission
from dga.shared.files import FileStore, ObjectStorageError

from .errors import LaboratoryError
from .finalization_facts import FinalizationFacts


class ReportState(StrEnum):
    UNAVAILABLE = 'UNAVAILABLE'
    QUEUED = 'QUEUED'
    GENERATING = 'GENERATING'
    READY = 'READY'
    FAILED = 'FAILED'


class _AuditAction(StrEnum):
    REPORT_GENERATION_RETRIED = 'REPORT_GENERATION_RETRIED'
    LAB_REPORT_DOWNLOADED = 'LAB_REPORT_DOWNLOADED'


class StaleReportClaim(Exception):
    pass


@dataclass(frozen=True)
class ReportStatus:
    barcode: str
    state: ReportState
    unavailable_reason: str | None = None
    error_code: str | None = None
    requested_at: datetime | None = None
    generated_at: datetime | None = None


@dataclass(frozen=True)
class ReportClaim:
    report_id: UUID
    oil_sample_id: UUID
    finalization_token: UUID
    generation_token: UUID
    claim_token: UUID
    snapshot: dict[str, Any]
    started_at: datetime


@dataclass(frozen=True)
class ReportFile:
    content: bytes
    filename: str
    generated_at: datetime


class LaboratoryReports:
    """Own current report delivery requests and copies of frozen laboratory facts."""

    def __init__(
        self,
        engine: Engine,
        audit_trail: AuditTrail,
        object_store: FileStore,
        *,
        clock=None,
    ):
        self._engine = engine
        self._audit = audit_trail
        self._objects = object_store
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get_report_by_barcode(
        self, actor: ActorContext, barcode_value: str
    ) -> ReportStatus:
        require_permission(actor, 'laboratory.read')
        barcode = self._barcode(barcode_value)
        with self._engine.connect() as connection:
            row = connection.execute(
                text(
                    """SELECT s.testing_status,s.testing_finalization_token,
                    r.finalization_token,r.state,r.error_code,r.requested_at,r.generated_at
                    FROM oil_samples s
                    LEFT JOIN laboratory_reports r ON r.oil_sample_id=s.id
                    WHERE s.barcode_value=:barcode"""
                ),
                {'barcode': barcode},
            ).mappings().first()
        if not row:
            raise LaboratoryError('sample_not_found', 404)
        if row['testing_status'] != 'FINALIZED':
            return ReportStatus(barcode, ReportState.UNAVAILABLE, 'sample_not_finalized')
        if row['testing_finalization_token'] is None:
            return ReportStatus(barcode, ReportState.UNAVAILABLE, 'refinalization_required')
        if row['state'] is None:
            return ReportStatus(barcode, ReportState.UNAVAILABLE, 'report_not_requested')
        if row['finalization_token'] != row['testing_finalization_token']:
            return ReportStatus(barcode, ReportState.UNAVAILABLE, 'report_not_current')
        return ReportStatus(
            barcode=barcode,
            state=ReportState(row['state']),
            error_code=row['error_code'],
            requested_at=row['requested_at'],
            generated_at=row['generated_at'],
        )

    def retry_report(self, actor: ActorContext, barcode_value: str) -> ReportStatus:
        require_permission(actor, 'laboratory.finalize')
        barcode = self._barcode(barcode_value)
        now = self._clock()
        with self._engine.begin() as connection:
            actor = IdentityService(self._engine).authorize_current(connection, actor, 'laboratory.finalize')
            sample = connection.execute(
                text(
                    """SELECT id,testing_status,testing_finalization_token
                    FROM oil_samples WHERE barcode_value=:barcode FOR UPDATE"""
                ),
                {'barcode': barcode},
            ).mappings().first()
            if not sample:
                raise LaboratoryError('sample_not_found', 404)
            report = connection.execute(
                text('SELECT * FROM laboratory_reports WHERE oil_sample_id=:sample FOR UPDATE'),
                {'sample': sample['id']},
            ).mappings().first()
            if (
                sample['testing_status'] != 'FINALIZED'
                or sample['testing_finalization_token'] is None
                or not report
                or report['finalization_token'] != sample['testing_finalization_token']
                or report['state'] != ReportState.FAILED.value
                or report['error_code'] == 'finalization_withdrawn'
            ):
                raise LaboratoryError('report_retry_not_allowed', 409)
            connection.execute(
                text(
                    """UPDATE laboratory_reports SET state='QUEUED',generation_token=:generation,
                    claim_token=NULL,lease_expires_at=NULL,object_key=NULL,content_sha256=NULL,
                    byte_size=NULL,error_code=NULL,started_at=NULL,generated_at=NULL,
                    requested_by=:actor,requested_at=:now,updated_at=:now WHERE id=:id"""
                ),
                {
                    'id': report['id'],
                    'generation': uuid4(),
                    'actor': actor.user_id,
                    'now': now,
                },
            )
            self._audit.append(
                connection,
                actor,
                _AuditAction.REPORT_GENERATION_RETRIED,
                entity_id=report['id'],
            )
        return self.get_report_by_barcode(actor, barcode)

    def claim_next_report(self, worker_id: str, *, lease_seconds: int) -> ReportClaim | None:
        if not worker_id.strip() or not 1 <= lease_seconds <= 3600:
            raise ValueError('invalid_worker_claim')
        now = self._clock()
        lease_expires = now + timedelta(seconds=lease_seconds)
        claim_token = uuid4()
        with self._engine.begin() as connection:
            row = connection.execute(
                text(
                    """SELECT r.* FROM laboratory_reports r
                    JOIN oil_samples s ON s.id=r.oil_sample_id
                    WHERE s.testing_status='FINALIZED'
                      AND s.testing_finalization_token=r.finalization_token
                      AND (r.state='QUEUED'
                           OR (r.state='GENERATING' AND r.lease_expires_at < :now))
                    ORDER BY r.requested_at,r.id
                    FOR UPDATE OF r SKIP LOCKED LIMIT 1"""
                ),
                {'now': now},
            ).mappings().first()
            if not row:
                return None
            connection.execute(
                text(
                    """UPDATE laboratory_reports SET state='GENERATING',claim_token=:claim,
                    lease_expires_at=:lease,error_code=NULL,started_at=:now,updated_at=:now
                    WHERE id=:id"""
                ),
                {'id': row['id'], 'claim': claim_token, 'lease': lease_expires, 'now': now},
            )
        return ReportClaim(
            report_id=row['id'],
            oil_sample_id=row['oil_sample_id'],
            finalization_token=row['finalization_token'],
            generation_token=row['generation_token'],
            claim_token=claim_token,
            snapshot=row['report_snapshot'],
            started_at=now,
        )

    def complete_report(
        self,
        claim: ReportClaim,
        *,
        object_key: str,
        content_sha256: str,
        byte_size: int,
        generated_at: datetime,
    ) -> None:
        if (
            not object_key
            or len(content_sha256) != 64
            or byte_size < 0
            or generated_at.tzinfo is None
        ):
            raise ValueError('invalid_report_file_metadata')
        with self._engine.begin() as connection:
            self._lock_current_sample(connection, claim)
            changed = connection.execute(
                text(
                    """UPDATE laboratory_reports SET state='READY',object_key=:key,
                    content_sha256=:digest,byte_size=:size,generated_at=:generated,
                    claim_token=NULL,lease_expires_at=NULL,error_code=NULL,updated_at=:generated
                    WHERE id=:id AND finalization_token=:finalization
                      AND generation_token=:generation AND claim_token=:claim
                      AND state='GENERATING'"""
                ),
                {
                    'id': claim.report_id,
                    'finalization': claim.finalization_token,
                    'generation': claim.generation_token,
                    'claim': claim.claim_token,
                    'key': object_key,
                    'digest': content_sha256,
                    'size': byte_size,
                    'generated': generated_at,
                },
            )
            if changed.rowcount != 1:
                raise StaleReportClaim('stale_report_claim')

    def fail_report(self, claim: ReportClaim, error_code: str) -> None:
        if not 1 <= len(error_code) <= 80:
            raise ValueError('invalid_report_error')
        now = self._clock()
        with self._engine.begin() as connection:
            try:
                self._lock_current_sample(connection, claim)
            except StaleReportClaim:
                return
            connection.execute(
                text(
                    """UPDATE laboratory_reports SET state='FAILED',claim_token=NULL,
                    lease_expires_at=NULL,error_code=:error,updated_at=:now
                    WHERE id=:id AND finalization_token=:finalization
                      AND generation_token=:generation AND claim_token=:claim
                      AND state='GENERATING'"""
                ),
                {
                    'id': claim.report_id,
                    'finalization': claim.finalization_token,
                    'generation': claim.generation_token,
                    'claim': claim.claim_token,
                    'error': error_code,
                    'now': now,
                },
            )

    def read_report_file(
        self, actor: ActorContext, barcode_value: str
    ) -> ReportFile:
        require_permission(actor, 'laboratory.read')
        barcode = self._barcode(barcode_value)
        with self._engine.begin() as connection:
            sample = connection.execute(
                text(
                    """SELECT id,testing_status,testing_finalization_token FROM oil_samples
                    WHERE barcode_value=:barcode FOR SHARE"""
                ),
                {'barcode': barcode},
            ).mappings().first()
            if not sample:
                raise LaboratoryError('sample_not_found', 404)
            if sample['testing_status'] != 'FINALIZED' or sample['testing_finalization_token'] is None:
                raise LaboratoryError('report_unavailable', 409)
            report = connection.execute(
                text('SELECT * FROM laboratory_reports WHERE oil_sample_id=:sample FOR SHARE'),
                {'sample': sample['id']},
            ).mappings().first()
            if not report or report['finalization_token'] != sample['testing_finalization_token']:
                raise LaboratoryError('report_unavailable', 409)
            if report['state'] == ReportState.FAILED.value:
                raise LaboratoryError(
                    'report_failed', 409, details={'error_code': report['error_code']}
                )
            if report['state'] != ReportState.READY.value:
                raise LaboratoryError('report_not_ready', 409)
            try:
                content = self._objects.get(object_key=report['object_key'])
            except ObjectStorageError:
                raise
            except Exception as error:
                raise ObjectStorageError('object_storage_unavailable') from error
            if (
                len(content) != report['byte_size']
                or sha256(content).hexdigest() != report['content_sha256']
            ):
                raise LaboratoryError('report_integrity_failure', 503)
            self._audit.append(
                connection,
                actor,
                _AuditAction.LAB_REPORT_DOWNLOADED,
                entity_id=report['id'],
            )
            return ReportFile(
                content=content,
                filename=self._filename(barcode),
                generated_at=report['generated_at'],
            )

    @staticmethod
    def _lock_current_sample(connection: Connection, claim: ReportClaim) -> None:
        sample = connection.execute(
            text(
                """SELECT testing_status,testing_finalization_token FROM oil_samples
                WHERE id=:sample FOR SHARE"""
            ),
            {'sample': claim.oil_sample_id},
        ).mappings().first()
        if (
            not sample
            or sample['testing_status'] != 'FINALIZED'
            or sample['testing_finalization_token'] != claim.finalization_token
        ):
            raise StaleReportClaim('stale_report_claim')

    @staticmethod
    def _filename(barcode: str) -> str:
        safe = ''.join(
            character
            if character.isascii() and (character.isalnum() or character in '._-')
            else '_'
            for character in PurePath(barcode).name
        )
        return f'{safe or "report"}.pdf'

    def queue_current(
        self,
        connection: Connection,
        actor: ActorContext,
        sample_id: UUID,
        finalization_token: UUID,
        finalized_at: datetime,
        acknowledged_warning_codes: tuple[str, ...],
    ) -> None:
        snapshot = FinalizationFacts().load_current(connection, sample_id, finalization_token).to_report_snapshot()
        if (datetime.fromisoformat(snapshot['finalization']['finalized_at']) != finalized_at
                or tuple(snapshot['acknowledged_warning_codes']) != tuple(sorted(set(acknowledged_warning_codes)))):
            raise LaboratoryError('finalization_facts_unavailable', 503)
        connection.execute(
            text(
                """INSERT INTO laboratory_reports
                (id,oil_sample_id,finalization_token,generation_token,
                 snapshot_schema_version,report_snapshot,state,requested_by,
                 requested_at,updated_at)
                VALUES (:id,:sample,:finalization,:generation,1,CAST(:snapshot AS jsonb),
                        'QUEUED',:actor,:now,:now)
                ON CONFLICT (oil_sample_id) DO UPDATE SET
                    finalization_token=EXCLUDED.finalization_token,
                    generation_token=EXCLUDED.generation_token,
                    snapshot_schema_version=1,
                    report_snapshot=EXCLUDED.report_snapshot,
                    state='QUEUED',claim_token=NULL,lease_expires_at=NULL,
                    object_key=NULL,content_sha256=NULL,byte_size=NULL,error_code=NULL,
                    requested_by=EXCLUDED.requested_by,requested_at=EXCLUDED.requested_at,
                    started_at=NULL,generated_at=NULL,updated_at=EXCLUDED.updated_at"""
            ),
            {
                'id': uuid4(),
                'sample': sample_id,
                'finalization': finalization_token,
                'generation': uuid4(),
                'snapshot': json.dumps(snapshot, ensure_ascii=False),
                'actor': actor.user_id,
                'now': finalized_at,
            },
        )

    @staticmethod
    def invalidate_current(connection: Connection, sample_id: UUID, now: datetime) -> None:
        connection.execute(
            text(
                """UPDATE laboratory_reports SET state='FAILED',
                generation_token=:generation,claim_token=NULL,lease_expires_at=NULL,
                object_key=NULL,content_sha256=NULL,byte_size=NULL,generated_at=NULL,
                error_code='finalization_withdrawn',updated_at=:now
                WHERE oil_sample_id=:sample"""
            ),
            {'sample': sample_id, 'generation': uuid4(), 'now': now},
        )

    @staticmethod
    def _barcode(value: str) -> str:
        barcode = value.strip().upper()
        if not 1 <= len(barcode) <= 40:
            raise LaboratoryError('invalid_barcode')
        return barcode
