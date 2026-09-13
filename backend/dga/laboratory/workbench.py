"""Typed laboratory result workflow behind the public laboratory seam."""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from pathlib import PurePath
from typing import TYPE_CHECKING, Callable, Protocol
from uuid import UUID, uuid4

from sqlalchemy import Engine, text

from dga.shared.auth.public import ActorContext, AuditTrail, require_permission
from dga.shared.files import FileStore

from .errors import LaboratoryError

if TYPE_CHECKING:
    from .public import OilSample, SampleRegistry


class TestType(StrEnum):
    DGA = 'DGA'
    MOISTURE = 'MOISTURE'
    BREAKDOWN_VOLTAGE = 'BREAKDOWN_VOLTAGE'


class ResultQualifier(StrEnum):
    EQ = 'EQ'
    ND = 'ND'
    LT = 'LT'
    GT = 'GT'


class TestingStatus(StrEnum):
    OPEN = 'OPEN'
    FINALIZED = 'FINALIZED'


class FinalizationEventType(StrEnum):
    FINALIZED = 'FINALIZED'
    WITHDRAWN = 'WITHDRAWN'


class _AuditAction(StrEnum):
    SAMPLE_BASICS_UPDATED = 'SAMPLE_BASICS_UPDATED'
    LAB_TEST_CREATED = 'LAB_TEST_CREATED'
    LAB_TEST_UPDATED = 'LAB_TEST_UPDATED'
    LAB_TEST_REMOVED = 'LAB_TEST_REMOVED'
    REPORT_RESULT_SELECTED = 'REPORT_RESULT_SELECTED'
    REPORT_RESULT_CLEARED = 'REPORT_RESULT_CLEARED'
    LAB_TESTING_FINALIZATION_ATTEMPT = 'LAB_TESTING_FINALIZATION_ATTEMPT'
    LAB_TESTING_FINALIZATION_WITHDRAWN = 'LAB_TESTING_FINALIZATION_WITHDRAWN'


@dataclass(frozen=True)
class QualifiedMeasurement:
    qualifier: ResultQualifier
    value: Decimal | None


@dataclass(frozen=True)
class DgaResultInput:
    h2: QualifiedMeasurement
    ch4: QualifiedMeasurement
    c2h2: QualifiedMeasurement
    c2h4: QualifiedMeasurement
    c2h6: QualifiedMeasurement
    co: QualifiedMeasurement
    co2: QualifiedMeasurement


@dataclass(frozen=True)
class MoistureResultInput:
    result: QualifiedMeasurement


@dataclass(frozen=True)
class BreakdownVoltageResultInput:
    result: QualifiedMeasurement


TypedResult = DgaResultInput | MoistureResultInput | BreakdownVoltageResultInput


@dataclass(frozen=True)
class TestSubmission:
    test_type: TestType
    method_version_id: UUID
    measured_at: datetime
    instrument_name: str | None
    notes: str | None
    result: TypedResult


@dataclass(frozen=True)
class RawAttachment:
    filename: str
    content_type: str
    content: bytes


@dataclass(frozen=True)
class MethodField:
    code: str
    display_name: str
    unit_code: str | None
    display_decimal_places: int | None
    detection_limit: Decimal | None


@dataclass(frozen=True)
class MethodConfiguration:
    id: UUID
    test_type: TestType
    display_name: str
    standard_reference: str | None
    version_label: str
    is_active: bool
    fields: tuple[MethodField, ...]


@dataclass(frozen=True)
class StoredAttachment:
    id: UUID
    filename: str
    content_type: str
    byte_size: int


@dataclass(frozen=True)
class TestRecord:
    id: UUID
    test_type: TestType
    method: MethodConfiguration
    measured_at: datetime
    instrument_name: str | None
    analyst_user_id: UUID
    notes: str | None
    result: TypedResult
    attachments: tuple[StoredAttachment, ...]
    selected_for_report: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class FinalizationAssessment:
    ready: bool
    blocking_codes: tuple[str, ...]
    missing_test_types: tuple[TestType, ...]
    warning_codes: tuple[str, ...]


@dataclass(frozen=True)
class FinalizationEvent:
    id: UUID
    event_type: FinalizationEventType
    actor_user_id: UUID
    occurred_at: datetime
    reason: str | None


class FinalizationWarningSource(Protocol):
    def __call__(self, tests: tuple[TestRecord, ...]) -> tuple[str, ...]: ...


class ReportLifecycle(Protocol):
    def queue_current(
        self, connection, actor, sample_id, finalization_token, finalized_at,
        acknowledged_warning_codes,
    ) -> None: ...

    def invalidate_current(self, connection, sample_id, now) -> None: ...


@dataclass(frozen=True)
class WorkbenchSample:
    sample: 'OilSample'
    testing_status: TestingStatus
    testing_finalized_by: UUID | None
    testing_finalized_at: datetime | None
    methods: tuple[MethodConfiguration, ...]
    tests: tuple[TestRecord, ...]
    finalization_assessment: FinalizationAssessment
    finalization_history: tuple[FinalizationEvent, ...]


@dataclass(frozen=True)
class UpdateSampleBasics:
    sampled_at: datetime
    received_at: datetime
    site_name: str
    equipment_serial: str
    notes: str | None


def _measurement(value, qualifier) -> QualifiedMeasurement:
    return QualifiedMeasurement(ResultQualifier(qualifier), value)


class LaboratoryWorkbench:
    """Load one barcode and manage its editable, typed test records."""

    def __init__(
        self,
        engine: Engine,
        sample_registry: 'SampleRegistry',
        audit_trail: AuditTrail,
        object_store: FileStore,
        report_lifecycle: ReportLifecycle,
        *,
        clock: Callable[[], datetime] | None = None,
        warning_source: FinalizationWarningSource | None = None,
    ):
        self._engine = engine
        self._audit = audit_trail
        self._objects = object_store
        self._reports = report_lifecycle
        self._samples = sample_registry
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._warning_source = warning_source or (lambda _tests: ())

    def load(self, actor: ActorContext, barcode_value: str) -> WorkbenchSample:
        require_permission(actor, 'laboratory.read')
        barcode = self._barcode(barcode_value)
        with self._engine.connect() as connection:
            sample_row = connection.execute(
                text("""SELECT id,testing_status,identity_status,testing_finalized_by,
                testing_finalized_at FROM oil_samples WHERE barcode_value=:barcode"""),
                {'barcode': barcode},
            ).mappings().first()
            if not sample_row:
                raise LaboratoryError('sample_not_found', 404)
            methods = self._methods(connection, sample_row['id'])
            tests = tuple(
                self._record(connection, row, methods)
                for row in connection.execute(
                    text("""SELECT * FROM laboratory_tests
                    WHERE oil_sample_id=:sample AND record_status='ACTIVE'
                    ORDER BY created_at,id"""),
                    {'sample': sample_row['id']},
                ).mappings()
            )
            assessment = self._assessment(sample_row['identity_status'], tests)
            history = self._events(connection, sample_row['id'])
        return WorkbenchSample(
            sample=self._samples.find_by_barcode(actor, barcode),
            testing_status=TestingStatus(sample_row['testing_status']),
            testing_finalized_by=sample_row['testing_finalized_by'],
            testing_finalized_at=sample_row['testing_finalized_at'],
            methods=methods,
            tests=tests,
            finalization_assessment=assessment,
            finalization_history=history,
        )

    def add_test(
        self,
        actor: ActorContext,
        barcode_value: str,
        submission: TestSubmission,
        attachment: RawAttachment | None = None,
    ) -> TestRecord:
        require_permission(actor, 'laboratory.write')
        self._validate_submission(submission)
        test_id, now = uuid4(), self._clock()
        object_key = None
        try:
            with self._engine.begin() as connection:
                sample_id = self._editable_sample(connection, self._barcode(barcode_value))
                method = self._method(connection, submission.method_version_id, submission.test_type)
                self._validate_configured_precision(submission, method)
                self._insert_header(connection, test_id, sample_id, actor, submission, now)
                self._replace_result(connection, test_id, submission)
                if attachment:
                    object_key = self._store_attachment(connection, actor, test_id, attachment, now)
                self._audit.append(connection, actor, _AuditAction.LAB_TEST_CREATED, entity_id=test_id)
        except Exception:
            if object_key:
                try:
                    self._objects.delete(object_key=object_key)
                except Exception:
                    pass
            raise
        return self._find_test(actor, barcode_value, test_id)

    def update_test(
        self,
        actor: ActorContext,
        barcode_value: str,
        test_id: UUID,
        submission: TestSubmission,
        attachment: RawAttachment | None = None,
    ) -> TestRecord:
        require_permission(actor, 'laboratory.write')
        self._validate_submission(submission)
        object_key = None
        try:
            with self._engine.begin() as connection:
                sample_id = self._editable_sample(connection, self._barcode(barcode_value))
                existing = connection.execute(
                    text("""SELECT test_type,method_version_id,selected_for_report FROM laboratory_tests
                    WHERE id=:id AND oil_sample_id=:sample AND record_status='ACTIVE' FOR UPDATE"""),
                    {'id': test_id, 'sample': sample_id},
                ).mappings().first()
                if not existing:
                    raise LaboratoryError('test_not_found', 404)
                method = self._method(
                    connection,
                    submission.method_version_id,
                    submission.test_type,
                    allow_inactive=submission.method_version_id == existing['method_version_id'],
                )
                self._validate_configured_precision(submission, method)
                old_table = self._result_table(TestType(existing['test_type']))
                connection.execute(text(f'DELETE FROM {old_table} WHERE test_id=:id'), {'id': test_id})
                now = self._clock()
                connection.execute(
                    text("""UPDATE laboratory_tests SET test_type=:type,method_version_id=:method,
                    measured_at=:measured,instrument_name=:instrument,analyst_user_id=:analyst,
                    notes=:notes,
                    selected_for_report=:selected,
                    updated_by=:actor,updated_at=:now WHERE id=:id"""),
                    {'id': test_id, 'type': submission.test_type.value,
                     'method': submission.method_version_id, 'measured': submission.measured_at,
                     'instrument': self._optional_text(submission.instrument_name, 160, 'invalid_instrument'),
                     'analyst': actor.user_id,
                     'notes': self._optional_text(submission.notes, 2000, 'invalid_notes'),
                     'selected': existing['selected_for_report']
                        if existing['test_type'] == submission.test_type.value else False,
                     'actor': actor.user_id, 'now': now},
                )
                self._replace_result(connection, test_id, submission)
                if attachment:
                    object_key = self._store_attachment(connection, actor, test_id, attachment, now)
                self._audit.append(connection, actor, _AuditAction.LAB_TEST_UPDATED, entity_id=test_id)
                if (
                    existing['selected_for_report']
                    and existing['test_type'] != submission.test_type.value
                ):
                    self._audit.append(
                        connection,
                        actor,
                        _AuditAction.REPORT_RESULT_CLEARED,
                        entity_id=test_id,
                    )
        except Exception:
            if object_key:
                try:
                    self._objects.delete(object_key=object_key)
                except Exception:
                    pass
            raise
        return self._find_test(actor, barcode_value, test_id)

    def remove_test(
        self,
        actor: ActorContext,
        barcode_value: str,
        test_id: UUID,
        reason: str,
    ) -> None:
        require_permission(actor, 'laboratory.write')
        reason = reason.strip()
        if not 1 <= len(reason) <= 500:
            raise LaboratoryError('removal_reason_required')
        with self._engine.begin() as connection:
            sample_id = self._editable_sample(connection, self._barcode(barcode_value))
            existing = connection.execute(
                text("""SELECT selected_for_report FROM laboratory_tests
                WHERE id=:id AND oil_sample_id=:sample AND record_status='ACTIVE' FOR UPDATE"""),
                {'id': test_id, 'sample': sample_id},
            ).mappings().first()
            if not existing:
                raise LaboratoryError('test_not_found', 404)
            changed = connection.execute(
                text("""UPDATE laboratory_tests SET record_status='REMOVED',removal_reason=:reason,
                selected_for_report=FALSE,
                updated_by=:actor,updated_at=:now
                WHERE id=:id AND oil_sample_id=:sample AND record_status='ACTIVE'"""),
                {'id': test_id, 'sample': sample_id, 'reason': reason,
                 'actor': actor.user_id, 'now': self._clock()},
            )
            if changed.rowcount != 1:
                raise LaboratoryError('test_not_found', 404)
            self._audit.append(connection, actor, _AuditAction.LAB_TEST_REMOVED, entity_id=test_id)
            if existing['selected_for_report']:
                self._audit.append(
                    connection,
                    actor,
                    _AuditAction.REPORT_RESULT_CLEARED,
                    entity_id=test_id,
                )

    def select_report_result(
        self,
        actor: ActorContext,
        barcode_value: str,
        test_id: UUID,
    ) -> WorkbenchSample:
        require_permission(actor, 'laboratory.write')
        barcode = self._barcode(barcode_value)
        with self._engine.begin() as connection:
            sample_id = self._editable_sample(connection, barcode)
            selected = connection.execute(
                text("""SELECT test_type,selected_for_report FROM laboratory_tests
                WHERE id=:id AND oil_sample_id=:sample AND record_status='ACTIVE'"""),
                {'id': test_id, 'sample': sample_id},
            ).mappings().first()
            if not selected:
                raise LaboratoryError('test_not_found', 404)
            if not selected['selected_for_report']:
                connection.execute(
                    text("""UPDATE laboratory_tests SET selected_for_report=FALSE,
                    updated_by=:actor,updated_at=:now
                    WHERE oil_sample_id=:sample AND test_type=:type
                        AND record_status='ACTIVE' AND selected_for_report"""),
                    {'sample': sample_id, 'type': selected['test_type'],
                     'actor': actor.user_id, 'now': self._clock()},
                )
                connection.execute(
                    text("""UPDATE laboratory_tests SET selected_for_report=TRUE,
                    updated_by=:actor,updated_at=:now WHERE id=:id"""),
                    {'id': test_id, 'actor': actor.user_id, 'now': self._clock()},
                )
                self._audit.append(
                    connection,
                    actor,
                    _AuditAction.REPORT_RESULT_SELECTED,
                    entity_id=test_id,
                )
        return self.load(actor, barcode)

    def finalize(
        self,
        actor: ActorContext,
        barcode_value: str,
        acknowledged_warning_codes: tuple[str, ...] = (),
    ) -> WorkbenchSample:
        require_permission(actor, 'laboratory.finalize')
        barcode = self._barcode(barcode_value)
        sample_id = None
        try:
            with self._engine.begin() as connection:
                sample = self._locked_sample(connection, barcode)
                sample_id = sample['id']
                if sample['testing_status'] == TestingStatus.FINALIZED.value:
                    raise LaboratoryError('sample_already_finalized', 409)
                methods = self._methods(connection, sample_id)
                tests = tuple(
                    self._record(connection, row, methods)
                    for row in connection.execute(
                        text("""SELECT * FROM laboratory_tests
                        WHERE oil_sample_id=:sample AND record_status='ACTIVE'
                        ORDER BY created_at,id"""),
                        {'sample': sample_id},
                    ).mappings()
                )
                assessment = self._assessment(sample['identity_status'], tests)
                self._raise_blocker(assessment)
                acknowledged = set(acknowledged_warning_codes)
                missing_warnings = [
                    code for code in assessment.warning_codes if code not in acknowledged
                ]
                if missing_warnings:
                    raise LaboratoryError(
                        'warnings_not_acknowledged',
                        details={'warning_codes': missing_warnings},
                    )
                now = self._clock()
                finalization_token = uuid4()
                by_type: dict[TestType, list[TestRecord]] = {}
                for record in tests:
                    by_type.setdefault(record.test_type, []).append(record)
                for records in by_type.values():
                    if len(records) == 1 and not records[0].selected_for_report:
                        connection.execute(
                            text("""UPDATE laboratory_tests SET selected_for_report=TRUE,
                            updated_by=:actor,updated_at=:now WHERE id=:id"""),
                            {'id': records[0].id, 'actor': actor.user_id, 'now': now},
                        )
                        self._audit.append(
                            connection,
                            actor,
                            _AuditAction.REPORT_RESULT_SELECTED,
                            entity_id=records[0].id,
                        )
                connection.execute(
                    text("""UPDATE oil_samples SET testing_status='FINALIZED',
                    testing_finalized_by=:actor,testing_finalized_at=:now,
                    testing_finalization_token=:token,
                    updated_by=:actor,updated_at=:now WHERE id=:id"""),
                    {'id': sample_id, 'actor': actor.user_id, 'now': now,
                     'token': finalization_token},
                )
                self._reports.queue_current(
                    connection,
                    actor,
                    sample_id,
                    finalization_token,
                    now,
                    tuple(code for code in assessment.warning_codes if code in acknowledged),
                )
                self._insert_event(
                    connection, sample_id, actor, FinalizationEventType.FINALIZED, now
                )
                self._audit.append(
                    connection,
                    actor,
                    _AuditAction.LAB_TESTING_FINALIZATION_ATTEMPT,
                    entity_id=sample_id,
                )
        except LaboratoryError:
            if sample_id is not None:
                with self._engine.begin() as connection:
                    self._audit.append(
                        connection,
                        actor,
                        _AuditAction.LAB_TESTING_FINALIZATION_ATTEMPT,
                        entity_id=sample_id,
                        result='FAILURE',
                    )
            raise
        return self.load(actor, barcode)

    def withdraw_finalization(
        self,
        actor: ActorContext,
        barcode_value: str,
        reason: str,
    ) -> WorkbenchSample:
        require_permission(actor, 'laboratory.finalize')
        reason = reason.strip()
        if not 1 <= len(reason) <= 500:
            raise LaboratoryError('withdrawal_reason_required')
        barcode = self._barcode(barcode_value)
        with self._engine.begin() as connection:
            sample = self._locked_sample(connection, barcode)
            if sample['testing_status'] != TestingStatus.FINALIZED.value:
                raise LaboratoryError('sample_not_finalized', 409)
            now = self._clock()
            connection.execute(
                text("""UPDATE oil_samples SET testing_status='OPEN',
                testing_finalized_by=NULL,testing_finalized_at=NULL,
                testing_finalization_token=NULL,
                updated_by=:actor,updated_at=:now WHERE id=:id"""),
                {'id': sample['id'], 'actor': actor.user_id, 'now': now},
            )
            self._reports.invalidate_current(connection, sample['id'], now)
            self._insert_event(
                connection,
                sample['id'],
                actor,
                FinalizationEventType.WITHDRAWN,
                now,
                reason,
            )
            self._audit.append(
                connection,
                actor,
                _AuditAction.LAB_TESTING_FINALIZATION_WITHDRAWN,
                entity_id=sample['id'],
            )
        return self.load(actor, barcode)

    def update_sample(
        self,
        actor: ActorContext,
        barcode_value: str,
        command: UpdateSampleBasics,
    ) -> WorkbenchSample:
        require_permission(actor, 'laboratory.write')
        if command.sampled_at.tzinfo is None or command.received_at.tzinfo is None:
            raise LaboratoryError('timestamp_requires_timezone')
        if command.received_at < command.sampled_at:
            raise LaboratoryError('received_before_sampled')
        site = command.site_name.strip()
        serial = command.equipment_serial.strip()
        notes = self._optional_text(command.notes, 2000, 'invalid_notes')
        if not 1 <= len(site) <= 200:
            raise LaboratoryError('invalid_site_name')
        if not 1 <= len(serial) <= 160:
            raise LaboratoryError('invalid_equipment_serial')
        barcode = self._barcode(barcode_value)
        with self._engine.begin() as connection:
            sample_id = self._editable_sample(connection, barcode)
            row = connection.execute(
                text('SELECT identity_status,site_name,equipment_serial FROM oil_samples WHERE id=:id'),
                {'id': sample_id},
            ).mappings().one()
            if row['identity_status'] == 'ASSOCIATED' and (
                site != row['site_name'] or serial != row['equipment_serial']
            ):
                raise LaboratoryError('associated_identity_is_fixed', 409)
            connection.execute(
                text("""UPDATE oil_samples SET sampled_at=:sampled,received_at=:received,
                site_name=:site,equipment_serial=:serial,notes=:notes,updated_by=:actor,updated_at=:now,
                operations_revision=operations_revision+1
                WHERE id=:id"""),
                {'id': sample_id, 'sampled': command.sampled_at, 'received': command.received_at,
                 'site': site, 'serial': serial, 'notes': notes,
                 'actor': actor.user_id, 'now': self._clock()},
            )
            self._audit.append(connection, actor, _AuditAction.SAMPLE_BASICS_UPDATED, entity_id=sample_id)
        return self.load(actor, barcode)

    def _find_test(self, actor, barcode, test_id):
        loaded = self.load(actor, barcode)
        return next((item for item in loaded.tests if item.id == test_id), None) or self._missing_test()

    @staticmethod
    def _missing_test():
        raise LaboratoryError('test_not_found', 404)

    def _store_attachment(self, connection, actor, test_id, attachment, now):
        filename = PurePath(attachment.filename).name.strip()
        if not filename or len(filename) > 255 or not attachment.content or len(attachment.content) > 25_000_000:
            raise LaboratoryError('invalid_attachment')
        content_type = attachment.content_type.strip() or 'application/octet-stream'
        if len(content_type) > 160:
            raise LaboratoryError('invalid_attachment')
        stored_id = uuid4()
        object_key = f'laboratory/{test_id}/{stored_id}/{filename}'
        self._objects.put(object_key=object_key, content=attachment.content, content_type=content_type)
        try:
            connection.execute(
                text("""INSERT INTO stored_objects
                (id,object_key,original_filename,content_type,byte_size,sha256_hex,created_by,created_at)
                VALUES (:id,:key,:filename,:content_type,:size,:digest,:actor,:now)"""),
                {'id': stored_id, 'key': object_key, 'filename': filename, 'content_type': content_type,
                 'size': len(attachment.content), 'digest': sha256(attachment.content).hexdigest(),
                 'actor': actor.user_id, 'now': now},
            )
            connection.execute(
                text('INSERT INTO laboratory_test_attachments(test_id,stored_object_id) VALUES (:test,:stored)'),
                {'test': test_id, 'stored': stored_id},
            )
        except Exception:
            try:
                self._objects.delete(object_key=object_key)
            except Exception:
                pass
            raise
        return object_key

    def _insert_header(self, connection, test_id, sample_id, actor, submission, now):
        connection.execute(
            text("""INSERT INTO laboratory_tests
            (id,oil_sample_id,test_type,method_version_id,measured_at,instrument_name,
             analyst_user_id,notes,created_by,created_at,updated_by,updated_at)
            VALUES (:id,:sample,:type,:method,:measured,:instrument,:analyst,:notes,
                    :actor,:now,:actor,:now)"""),
            {'id': test_id, 'sample': sample_id, 'type': submission.test_type.value,
             'method': submission.method_version_id, 'measured': submission.measured_at,
             'instrument': self._optional_text(submission.instrument_name, 160, 'invalid_instrument'),
             'analyst': actor.user_id, 'notes': self._optional_text(submission.notes, 2000, 'invalid_notes'),
             'actor': actor.user_id, 'now': now},
        )

    def _replace_result(self, connection, test_id, submission):
        if submission.test_type == TestType.DGA:
            values = submission.result
            assert isinstance(values, DgaResultInput)
            params = {'test': test_id}
            columns = []
            for code in ('h2', 'ch4', 'c2h2', 'c2h4', 'c2h6', 'co', 'co2'):
                measurement = getattr(values, code)
                params[f'{code}_value'] = measurement.value
                params[f'{code}_qualifier'] = measurement.qualifier.value
                columns.extend((f'{code}_value', f'{code}_qualifier'))
            names = ','.join(('test_id', *columns))
            binds = ','.join((':test', *(f':{column}' for column in columns)))
            connection.execute(text(f'INSERT INTO dga_test_results ({names}) VALUES ({binds})'), params)
        else:
            expected = MoistureResultInput if submission.test_type == TestType.MOISTURE else BreakdownVoltageResultInput
            assert isinstance(submission.result, expected)
            table = 'moisture_test_results' if submission.test_type == TestType.MOISTURE else 'breakdown_voltage_test_results'
            connection.execute(
                text(f'INSERT INTO {table}(test_id,result_value,result_qualifier) VALUES (:test,:value,:qualifier)'),
                {'test': test_id, 'value': submission.result.result.value,
                 'qualifier': submission.result.result.qualifier.value},
            )

    @staticmethod
    def _result_table(test_type):
        return {
            TestType.DGA: 'dga_test_results',
            TestType.MOISTURE: 'moisture_test_results',
            TestType.BREAKDOWN_VOLTAGE: 'breakdown_voltage_test_results',
        }[test_type]

    def _methods(self, connection, sample_id):
        rows = connection.execute(
            text("""SELECT * FROM test_method_versions m
            WHERE m.is_active OR EXISTS (
                SELECT 1 FROM laboratory_tests t
                WHERE t.oil_sample_id=:sample AND t.method_version_id=m.id
            ) ORDER BY test_type,display_name,id"""),
            {'sample': sample_id},
        ).mappings().all()
        return tuple(self._method_from_row(connection, row) for row in rows)

    def _method(self, connection, method_id, test_type, *, allow_inactive=False):
        row = connection.execute(
            text('SELECT * FROM test_method_versions WHERE id=:id'), {'id': method_id}
        ).mappings().first()
        if not row or row['test_type'] != test_type.value or (not row['is_active'] and not allow_inactive):
            raise LaboratoryError('invalid_method')
        return self._method_from_row(connection, row)

    @staticmethod
    def _method_from_row(connection, row):
        fields = tuple(
            MethodField(field['field_code'], field['display_name'], field['unit_code'],
                        field['display_decimal_places'], field['detection_limit'])
            for field in connection.execute(
                text('SELECT * FROM test_method_fields WHERE method_version_id=:id ORDER BY sort_order,field_code'),
                {'id': row['id']},
            ).mappings()
        )
        return MethodConfiguration(row['id'], TestType(row['test_type']), row['display_name'],
                                   row['standard_reference'], row['version_label'], row['is_active'], fields)

    def _record(self, connection, row, methods):
        method = next(item for item in methods if item.id == row['method_version_id'])
        if row['test_type'] == TestType.DGA.value:
            result_row = connection.execute(
                text('SELECT * FROM dga_test_results WHERE test_id=:id'), {'id': row['id']}
            ).mappings().one()
            result = DgaResultInput(**{
                code: _measurement(result_row[f'{code}_value'], result_row[f'{code}_qualifier'])
                for code in ('h2', 'ch4', 'c2h2', 'c2h4', 'c2h6', 'co', 'co2')
            })
        else:
            table = 'moisture_test_results' if row['test_type'] == TestType.MOISTURE.value else 'breakdown_voltage_test_results'
            value_row = connection.execute(text(f'SELECT * FROM {table} WHERE test_id=:id'), {'id': row['id']}).mappings().one()
            cls = MoistureResultInput if row['test_type'] == TestType.MOISTURE.value else BreakdownVoltageResultInput
            result = cls(_measurement(value_row['result_value'], value_row['result_qualifier']))
        attachments = tuple(
            StoredAttachment(item['id'], item['original_filename'], item['content_type'], item['byte_size'])
            for item in connection.execute(
                text("""SELECT o.id,o.original_filename,o.content_type,o.byte_size
                FROM stored_objects o JOIN laboratory_test_attachments a ON a.stored_object_id=o.id
                WHERE a.test_id=:test ORDER BY o.created_at,o.id"""), {'test': row['id']}
            ).mappings()
        )
        return TestRecord(row['id'], TestType(row['test_type']), method, row['measured_at'],
                          row['instrument_name'], row['analyst_user_id'], row['notes'], result,
                          attachments, row['selected_for_report'], row['created_at'], row['updated_at'])

    def _assessment(self, identity_status, tests):
        blocking = []
        missing_types = []
        if identity_status != 'ASSOCIATED':
            blocking.append('sample_identity_not_confirmed')
        if not tests:
            blocking.append('no_active_tests')
        by_type: dict[TestType, list[TestRecord]] = {}
        for record in tests:
            by_type.setdefault(record.test_type, []).append(record)
        for test_type, records in by_type.items():
            if len(records) > 1 and not any(record.selected_for_report for record in records):
                missing_types.append(test_type)
        if missing_types:
            blocking.append('report_result_selection_required')
        warnings = tuple(dict.fromkeys(self._warning_source(tests)))
        return FinalizationAssessment(
            ready=not blocking,
            blocking_codes=tuple(blocking),
            missing_test_types=tuple(missing_types),
            warning_codes=warnings,
        )

    @staticmethod
    def _raise_blocker(assessment):
        if 'sample_identity_not_confirmed' in assessment.blocking_codes:
            raise LaboratoryError('sample_identity_not_confirmed')
        if 'no_active_tests' in assessment.blocking_codes:
            raise LaboratoryError('no_active_tests')
        if assessment.missing_test_types:
            raise LaboratoryError(
                'report_result_selection_required',
                details={
                    'test_types': [item.value for item in assessment.missing_test_types]
                },
            )

    @staticmethod
    def _locked_sample(connection, barcode):
        row = connection.execute(
            text("""SELECT id,identity_status,testing_status FROM oil_samples
            WHERE barcode_value=:barcode FOR UPDATE"""),
            {'barcode': barcode},
        ).mappings().first()
        if not row:
            raise LaboratoryError('sample_not_found', 404)
        return row

    @staticmethod
    def _insert_event(connection, sample_id, actor, event_type, occurred_at, reason=None):
        connection.execute(
            text("""INSERT INTO laboratory_finalization_events
            (id,oil_sample_id,event_type,actor_user_id,occurred_at,reason)
            VALUES (:id,:sample,:type,:actor,:time,:reason)"""),
            {'id': uuid4(), 'sample': sample_id, 'type': event_type.value,
             'actor': actor.user_id, 'time': occurred_at, 'reason': reason},
        )

    @staticmethod
    def _events(connection, sample_id):
        return tuple(
            FinalizationEvent(
                row['id'], FinalizationEventType(row['event_type']), row['actor_user_id'],
                row['occurred_at'], row['reason'],
            )
            for row in connection.execute(
                text("""SELECT id,event_type,actor_user_id,occurred_at,reason
                FROM laboratory_finalization_events WHERE oil_sample_id=:sample
                ORDER BY occurred_at,id"""),
                {'sample': sample_id},
            ).mappings()
        )

    @staticmethod
    def _editable_sample(connection, barcode):
        row = connection.execute(
            text('SELECT id,testing_status FROM oil_samples WHERE barcode_value=:barcode FOR UPDATE'),
            {'barcode': barcode},
        ).mappings().first()
        if not row:
            raise LaboratoryError('sample_not_found', 404)
        if row['testing_status'] != TestingStatus.OPEN.value:
            raise LaboratoryError('sample_finalized', 409)
        return row['id']

    @staticmethod
    def _validate_submission(submission):
        if submission.measured_at.tzinfo is None:
            raise LaboratoryError('timestamp_requires_timezone')
        expected = {
            TestType.DGA: DgaResultInput,
            TestType.MOISTURE: MoistureResultInput,
            TestType.BREAKDOWN_VOLTAGE: BreakdownVoltageResultInput,
        }[submission.test_type]
        if not isinstance(submission.result, expected):
            raise LaboratoryError('result_type_mismatch')
        measurements = submission.result.__dict__.values()
        for measurement in measurements:
            if measurement.qualifier == ResultQualifier.ND and measurement.value is not None:
                raise LaboratoryError('nd_must_not_have_value')
            if measurement.qualifier != ResultQualifier.ND and measurement.value is None:
                raise LaboratoryError('qualifier_requires_value')
            if measurement.value is not None and measurement.value < 0:
                raise LaboratoryError('negative_result')
            if measurement.value is not None and measurement.value.as_tuple().exponent < -6:
                raise LaboratoryError('result_precision_exceeded')

    @staticmethod
    def _validate_configured_precision(submission, method):
        if submission.test_type == TestType.DGA:
            measurements = {
                code.upper(): getattr(submission.result, code)
                for code in ('h2', 'ch4', 'c2h2', 'c2h4', 'c2h6', 'co', 'co2')
            }
        else:
            measurements = {method.fields[0].code: submission.result.result}
        for field in method.fields:
            value = measurements[field.code].value
            if (value is not None and field.display_decimal_places is not None
                    and value.as_tuple().exponent < -field.display_decimal_places):
                raise LaboratoryError('configured_precision_exceeded')

    @staticmethod
    def _barcode(value):
        barcode = value.strip().upper()
        if not 1 <= len(barcode) <= 40:
            raise LaboratoryError('invalid_barcode')
        return barcode

    @staticmethod
    def _optional_text(value, maximum, code):
        if value is None:
            return None
        value = value.strip()
        if len(value) > maximum:
            raise LaboratoryError(code)
        return value or None
