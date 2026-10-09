"""Database-backed worker for current laboratory PDF reports."""

import time
import logging
from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import create_engine

from dga.shared.auth.public import AuditTrail
from dga.shared.config import Settings
from dga.shared.files import ObjectStorageError, UnavailableFileStore
from dga.shared.file_store_factory import create_file_store

from .report_pdf import render_report_pdf
from .reports import LaboratoryReports, StaleReportClaim

logger = logging.getLogger(__name__)


class ReportWorker:
    def __init__(self, reports, object_store, renderer=render_report_pdf, *, clock=None):
        self._reports = reports
        self._objects = object_store
        self._renderer = renderer
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def process_one(self, worker_id: str, *, lease_seconds: int = 120) -> bool:
        claim = self._reports.claim_next_report(worker_id, lease_seconds=lease_seconds)
        if claim is None:
            return False
        generated_at = self._clock()
        object_key = (
            f'laboratory/reports/{claim.generation_token}/{claim.claim_token}.pdf'
        )
        uploaded = False
        try:
            content = self._renderer(claim.snapshot, generated_at)
            self._objects.put(
                object_key=object_key,
                content=content,
                content_type='application/pdf',
            )
            uploaded = True
            self._reports.complete_report(
                claim,
                object_key=object_key,
                content_sha256=sha256(content).hexdigest(),
                byte_size=len(content),
                generated_at=generated_at,
            )
        except StaleReportClaim:
            if uploaded:
                self._delete_best_effort(object_key)
        except (ObjectStorageError, OSError):
            if uploaded:
                logger.error('Report completion uncertain; retain and reconcile object: %s', object_key)
            self._reports.fail_report(claim, 'object_storage_unavailable')
        except Exception:
            if uploaded:
                # COMMIT may have succeeded even if its response was lost. Only
                # StaleReportClaim proves this file cannot be the current report.
                logger.error('Report completion uncertain; retain and reconcile object: %s', object_key)
            self._reports.fail_report(claim, 'report_generation_failed')
        return True

    def _delete_best_effort(self, object_key: str) -> None:
        try:
            self._objects.delete(object_key=object_key)
        except Exception:
            pass


def main() -> None:
    settings = Settings()
    store = create_file_store(settings)
    if isinstance(store, UnavailableFileStore):
        raise RuntimeError('object_storage_not_configured')
    engine = create_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_timeout=3,
    )
    reports = LaboratoryReports(engine, AuditTrail(), store)
    worker = ReportWorker(reports, store)
    worker_id = f'report-worker-{uuid4()}'
    try:
        while True:
            if not worker.process_one(worker_id):
                time.sleep(1)
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
