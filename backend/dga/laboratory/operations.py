"""Laboratory-owned operational queries and controlled physical sample commands."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Literal

from sqlalchemy import text
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from dga.shared.auth.public import require_permission
from .errors import LaboratoryError

BUSINESS_ZONE = ZoneInfo('America/Chicago')


class LedgerQuery(BaseModel):
    model_config = ConfigDict(extra='forbid')
    barcode: str = Field(default='', max_length=160)
    sample_number: str = Field(default='', max_length=160)
    site: str = Field(default='', max_length=200)
    serial: str = Field(default='', max_length=160)
    state: Literal['IDENTITY_PENDING', 'RECEIVED', 'DETECTING', 'COMPLETED', 'REPORTED'] | None = None
    test_type: Literal['DGA', 'MOISTURE', 'BREAKDOWN_VOLTAGE'] | None = None
    start_date: date | None = None
    end_date: date | None = None
    date_field: Literal['created_at', 'received_at', 'sampled_at'] = 'created_at'
    sort: Literal['created_at', 'received_at', 'sampled_at', 'sample_number', 'site_name'] = 'created_at'
    direction: Literal['asc', 'desc'] = 'desc'
    page: int = Field(default=1, ge=1, le=100000)
    page_size: int = Field(default=20, ge=1, le=100)

    @model_validator(mode='after')
    def dates(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError('end_before_start')
        if self.end_date == date.max or self.start_date == date.max:
            raise ValueError('date_out_of_range')
        return self


SAMPLE_VIEW = """WITH samples AS (SELECT s.*,
    CASE WHEN identity_status='IDENTITY_PENDING' THEN 'IDENTITY_PENDING'
      WHEN testing_status='FINALIZED' THEN CASE WHEN EXISTS
        (SELECT 1 FROM laboratory_reports r WHERE r.oil_sample_id=s.id AND r.state='READY'
         AND r.finalization_token=s.testing_finalization_token) THEN 'REPORTED' ELSE 'COMPLETED' END
      WHEN EXISTS (SELECT 1 FROM laboratory_tests t WHERE t.oil_sample_id=s.id AND t.record_status='ACTIVE')
        THEN 'DETECTING' ELSE 'RECEIVED' END AS state
    FROM oil_samples s) """


def day_window(day):
    return (datetime.combine(day, time.min, BUSINESS_ZONE).astimezone(timezone.utc),
            datetime.combine(day + timedelta(days=1), time.min, BUSINESS_ZONE).astimezone(timezone.utc))


class LaboratoryOperations:
    def __init__(self, engine, registry, asset_directory, audit, *, clock=None):
        self._engine, self._registry, self._assets, self._audit = engine, registry, asset_directory, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def dashboard(self, actor):
        require_permission(actor, 'laboratory.read')
        now = self._clock()
        day = now.astimezone(BUSINESS_ZONE).date()
        start, end = day_window(day)
        with self._engine.connect().execution_options(isolation_level='REPEATABLE READ') as c:
            metrics = c.execute(text("""SELECT
                (SELECT count(*) FROM oil_samples s WHERE s.testing_status='OPEN' AND EXISTS
                    (SELECT 1 FROM laboratory_tests t WHERE t.oil_sample_id=s.id AND t.record_status='ACTIVE')) AS detecting_samples,
                (SELECT count(*) FROM laboratory_tests WHERE created_at>=:start AND created_at<:end) AS tests_created_today,
                count(*) FILTER (WHERE created_at>=:start AND created_at<:end) AS samples_created_today,
                count(*) AS samples_created_total FROM oil_samples"""), dict(start=start, end=end)).mappings().one()
            recent = c.execute(text(SAMPLE_VIEW + 'SELECT id,barcode_value,site_name,equipment_serial,state,created_at FROM samples ORDER BY created_at DESC,id DESC LIMIT 5')).mappings().all()
        return dict(metrics=dict(metrics), recent_samples=[dict(r) for r in recent], business_date=day.isoformat(), timezone=BUSINESS_ZONE.key, as_of=now)

    def ledger(self, actor, **filters):
        require_permission(actor, 'laboratory.read')
        try:
            query = LedgerQuery(**filters)
        except ValidationError as error:
            raise LaboratoryError('invalid_ledger_query') from error
        params = query.model_dump()
        params.update(start=day_window(query.start_date)[0] if query.start_date else None,
                      end=day_window(query.end_date)[1] if query.end_date else None,
                      offset=(query.page-1)*query.page_size)
        predicate = f""" FROM samples s WHERE
          strpos(lower(barcode_value),lower(:barcode))>0 AND strpos(lower(sample_number),lower(:sample_number))>0
          AND strpos(lower(site_name),lower(:site))>0
          AND (strpos(lower(equipment_serial),lower(:serial))>0 OR EXISTS
            (SELECT 1 FROM jsonb_array_elements(COALESCE(asset_snapshot->'equipment_path','[]'::jsonb)) node
             WHERE strpos(lower(node->>'serial_number'),lower(:serial))>0))
          AND (CAST(:state AS text) IS NULL OR state=:state)
          AND (CAST(:test_type AS text) IS NULL OR EXISTS (SELECT 1 FROM laboratory_tests t
            WHERE t.oil_sample_id=s.id AND t.record_status='ACTIVE' AND t.test_type=:test_type))
          AND (CAST(:start AS timestamptz) IS NULL OR {query.date_field}>=:start)
          AND (CAST(:end AS timestamptz) IS NULL OR {query.date_field}<:end)"""
        with self._engine.connect().execution_options(isolation_level='REPEATABLE READ') as c:
            total = c.execute(text(SAMPLE_VIEW + 'SELECT count(*)' + predicate), params).scalar_one()
            rows = c.execute(text(SAMPLE_VIEW + '''SELECT id,barcode_value,sample_number,site_name,
                equipment_serial,state,created_at,received_at,sampled_at,
                ARRAY(SELECT DISTINCT test_type FROM laboratory_tests t WHERE t.oil_sample_id=s.id
                  AND t.record_status='ACTIVE' ORDER BY test_type) AS test_types''' + predicate +
                f' ORDER BY {query.sort} {query.direction},id {query.direction} LIMIT :page_size OFFSET :offset'), params).mappings().all()
        return dict(samples=[dict(r) for r in rows], total=total, page=query.page, page_size=query.page_size, timezone=BUSINESS_ZONE.key)
