"""Laboratory-owned operational queries and controlled physical sample commands."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Literal
from enum import StrEnum
from uuid import UUID, uuid4
from dataclasses import asdict
import json

from sqlalchemy import text
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from dga.shared.auth.public import require_permission
from .errors import LaboratoryError

BUSINESS_ZONE = ZoneInfo('America/Chicago')


class ContainerStatus(StrEnum):
    RECEIVED = 'RECEIVED'
    IN_USE = 'IN_USE'
    RETAINED = 'RETAINED'
    EXHAUSTED = 'EXHAUSTED'
    BROKEN = 'BROKEN'
    DISPOSED = 'DISPOSED'


CONTAINER_TRANSITIONS = {
    ContainerStatus.RECEIVED: ('IN_USE','RETAINED','BROKEN','DISPOSED'),
    ContainerStatus.IN_USE: ('RETAINED','EXHAUSTED','BROKEN','DISPOSED'),
    ContainerStatus.RETAINED: ('IN_USE','EXHAUSTED','BROKEN','DISPOSED'),
    ContainerStatus.EXHAUSTED: ('DISPOSED',),
    ContainerStatus.BROKEN: ('DISPOSED',),
    ContainerStatus.DISPOSED: (),
}


class OperationAction(StrEnum):
    ASSOCIATED = 'SAMPLE_ASSET_ASSOCIATED'
    CONTAINER_CHANGED = 'SAMPLE_CONTAINER_CHANGED'


class OperationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    expected_revision: int = Field(strict=True,ge=0,le=2147483647)
    reason: str = Field(min_length=1,max_length=500)


class ConfirmIdentityInput(OperationInput):
    formal_asset_id: UUID


class ChangeContainerInput(OperationInput):
    target: ContainerStatus


def validate_command(model, **values):
    try:
        return model(**values)
    except ValidationError as error:
        raise LaboratoryError('invalid_sample_operation') from error


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

    @staticmethod
    def _sample(c, barcode, *, lock=False):
        normalized = barcode.strip().upper()
        if not 1 <= len(normalized) <= 40:
            raise LaboratoryError('invalid_barcode')
        row = c.execute(text('SELECT * FROM oil_samples WHERE barcode_value=:barcode' + (' FOR UPDATE' if lock else '')),
                        {'barcode':normalized}).mappings().first()
        if row is None:
            raise LaboratoryError('sample_not_found',404)
        return row

    def sample_operations(self, actor, barcode):
        require_permission(actor,'laboratory.read')
        # Decode laboratory-owned DTOs in the same snapshot as revisions and event history.
        from .public import OilSample, SampleContainer, SampleIdentityStatus, _decode_snapshot
        with self._engine.connect().execution_options(isolation_level='REPEATABLE READ') as c:
            row = self._sample(c,barcode)
            containers = [dict(r) for r in c.execute(text('SELECT id,container_number,ordinal,status,revision FROM sample_containers WHERE oil_sample_id=:id ORDER BY ordinal'),{'id':row['id']}).mappings()]
            history = [dict(r) for r in c.execute(text('SELECT id,container_id,action_code,reason,actor_id,occurred_at,before_value,after_value FROM laboratory_operation_events WHERE oil_sample_id=:id ORDER BY occurred_at,id'),{'id':row['id']}).mappings()]
            sample = OilSample(
                **{key:row[key] for key in ('id','sample_number','barcode_value','sampled_at','received_at','site_name','equipment_serial','notes','formal_asset_id','created_at')},
                identity_status=SampleIdentityStatus(row['identity_status']),asset_snapshot=_decode_snapshot(row['asset_snapshot']),
                containers=tuple(SampleContainer(r['id'],r['container_number'],r['ordinal']) for r in containers),
            )
        for container in containers:
            container['allowed_targets'] = list(CONTAINER_TRANSITIONS[container['status']])
        return dict(sample=sample,operations_revision=row['operations_revision'],testing_status=row['testing_status'],containers=containers,history=history)

    def _event(self,c,actor,sample_id,action,reason,before,after,now,container_id=None):
        c.execute(text('''INSERT INTO laboratory_operation_events
            (id,oil_sample_id,container_id,action_code,reason,actor_id,occurred_at,before_value,after_value)
            VALUES (:id,:sample,:container,:action,:reason,:actor,:now,CAST(:before AS jsonb),CAST(:after AS jsonb))'''),
            dict(id=uuid4(),sample=sample_id,container=container_id,action=action.value,reason=reason,actor=actor.user_id,now=now,
                 before=json.dumps(before,default=str),after=json.dumps(after,default=str)))
        self._audit.append(c,actor,action,entity_id=sample_id)

    def confirm_identity(self,actor,barcode,formal_asset_id,*,expected_revision,reason):
        require_permission(actor,'laboratory.write')
        command = validate_command(ConfirmIdentityInput,formal_asset_id=formal_asset_id,expected_revision=expected_revision,reason=reason)
        from dga.assets.public import AssetType
        from .public import _snapshot
        with self._engine.begin() as c:
            # Match asset lifecycle lock ordering, then serialize against finalize/basic edits.
            c.execute(text('SELECT pg_advisory_xact_lock(110011)'))
            row = self._sample(c,barcode,lock=True)
            if row['operations_revision'] != command.expected_revision:
                raise LaboratoryError('stale_sample',409)
            if row['identity_status'] != 'IDENTITY_PENDING' or row['testing_status'] != 'OPEN':
                raise LaboratoryError('identity_confirmation_not_allowed',409)
            context = self._assets.resolve_sampling_context(actor,command.formal_asset_id,sampled_at=row['sampled_at'],connection=c)
            if context.asset.asset_type != AssetType.TRANSFORMER:
                raise LaboratoryError('sample_requires_transformer')
            snapshot = asdict(_snapshot(context))
            now = self._clock()
            before = {key:row[key] for key in ('identity_status','site_name','equipment_serial','sampled_at','received_at','formal_asset_id','asset_snapshot','operations_revision')}
            after = dict(identity_status='ASSOCIATED',site_name=context.site_name,equipment_serial=context.asset.serial_number,
                         sampled_at=row['sampled_at'],received_at=row['received_at'],formal_asset_id=command.formal_asset_id,asset_snapshot=snapshot,operations_revision=command.expected_revision+1)
            c.execute(text('''UPDATE oil_samples SET identity_status='ASSOCIATED',formal_asset_id=:asset,
                asset_snapshot=CAST(:snapshot AS jsonb),site_name=:site,equipment_serial=:serial,
                operations_revision=operations_revision+1,updated_by=:actor,updated_at=:now WHERE id=:id'''),
                dict(id=row['id'],asset=command.formal_asset_id,snapshot=json.dumps(snapshot,default=str),site=context.site_name,
                     serial=context.asset.serial_number,actor=actor.user_id,now=now))
            self._event(c,actor,row['id'],OperationAction.ASSOCIATED,command.reason,before,after,now)
        return self.sample_operations(actor,barcode)

    def change_container(self,actor,barcode,container_id,target,*,expected_revision,reason):
        require_permission(actor,'laboratory.write')
        if not isinstance(container_id, UUID):
            raise LaboratoryError('invalid_container_id')
        command = validate_command(ChangeContainerInput,target=target,expected_revision=expected_revision,reason=reason)
        with self._engine.begin() as c:
            sample = self._sample(c,barcode,lock=True)
            row = c.execute(text('SELECT id,status,revision FROM sample_containers WHERE id=:id AND oil_sample_id=:sample FOR UPDATE'),
                            dict(id=container_id,sample=sample['id'])).mappings().first()
            if row is None:
                raise LaboratoryError('container_not_found',404)
            if row['revision'] != command.expected_revision:
                raise LaboratoryError('stale_container',409)
            if command.target not in CONTAINER_TRANSITIONS[row['status']]:
                raise LaboratoryError('invalid_container_transition',409)
            c.execute(text('UPDATE sample_containers SET status=:status,revision=revision+1 WHERE id=:id'),dict(id=container_id,status=command.target.value))
            self._event(c,actor,sample['id'],OperationAction.CONTAINER_CHANGED,command.reason,
                        dict(status=row['status'],revision=row['revision']),dict(status=command.target.value,revision=row['revision']+1),self._clock(),container_id)
        return self.sample_operations(actor,barcode)

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
