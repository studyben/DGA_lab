"""Laboratory-owned version configuration. Formal scientific values are user supplied."""
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from dga.shared.auth.public import AuditTrail, require_permission
from .errors import LaboratoryError


TYPE_FIELDS = {
    'DGA': ('H2', 'CH4', 'C2H2', 'C2H4', 'C2H6', 'CO', 'CO2'),
    'MOISTURE': ('MOISTURE',), 'BREAKDOWN_VOLTAGE': ('BREAKDOWN_VOLTAGE',),
}
TypeCode = Literal['DGA', 'MOISTURE', 'BREAKDOWN_VOLTAGE']
Qualifier = Literal['EQ', 'ND', 'LT', 'GT']


class _Action(StrEnum):
    METHOD_CREATED = 'LAB_METHOD_CREATED'
    METHOD_ACTIVATION = 'LAB_METHOD_ACTIVATION_CHANGED'
    INSTRUMENT_CREATED = 'LAB_INSTRUMENT_CREATED'
    INSTRUMENT_STATUS = 'LAB_INSTRUMENT_STATUS_CHANGED'
    CALIBRATION_ADDED = 'LAB_CALIBRATION_ADDED'
    TYPE_UPDATED = 'LAB_TYPE_UPDATED'
    PACKAGE_CREATED = 'LAB_PACKAGE_CREATED'
    PACKAGE_APPLIED = 'LAB_PACKAGE_APPLIED'


class ConfigInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, frozen=True)


class FieldConfiguration(ConfigInput):
    code: str
    display_name: str = Field(min_length=1, max_length=80)
    unit_code: str | None = Field(default=None, min_length=1, max_length=40)
    display_decimal_places: int | None = Field(default=None, ge=0, le=6, strict=True)
    detection_limit: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=6, allow_inf_nan=False)
    quantitation_limit: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=6, allow_inf_nan=False)
    minimum: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=6, allow_inf_nan=False)
    maximum: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=6, allow_inf_nan=False)
    allowed_qualifiers: tuple[Qualifier, ...] = ('EQ', 'ND', 'LT', 'GT')

    @model_validator(mode='after')
    def coherent(self):
        if not self.allowed_qualifiers or len(set(self.allowed_qualifiers)) != len(self.allowed_qualifiers):
            raise ValueError('invalid_qualifiers')
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError('invalid_range')
        if self.detection_limit is not None and self.quantitation_limit is not None and self.quantitation_limit < self.detection_limit:
            raise ValueError('invalid_limits')
        return self


class QaCheck(ConfigInput):
    code: str = Field(pattern=r'^[A-Z][A-Z0-9_]{0,29}$')
    label: str = Field(min_length=1, max_length=100)
    instructions: str = Field(default='', max_length=500)


class QaExecution(ConfigInput):
    code: str = Field(pattern=r'^[A-Z][A-Z0-9_]{0,29}$')
    status: Literal['PASS', 'FAIL', 'NOT_RUN']
    note: str = Field(default='', max_length=500)


class MethodVersionInput(ConfigInput):
    test_type: TypeCode
    display_name: str = Field(min_length=1, max_length=160)
    version_label: str = Field(min_length=1, max_length=80)
    standard_reference: str | None = Field(default=None, min_length=1, max_length=160)
    fields: tuple[FieldConfiguration, ...]
    qa_checks: tuple[QaCheck, ...] = Field(default=(), max_length=20)

    @model_validator(mode='after')
    def coherent(self):
        if tuple(f.code for f in self.fields) != TYPE_FIELDS[self.test_type]:
            raise ValueError('incorrect_typed_fields')
        if len({q.code for q in self.qa_checks}) != len(self.qa_checks):
            raise ValueError('duplicate_qa_code')
        return self


class InstrumentInput(ConfigInput):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=150)
    model: str | None = Field(default=None, max_length=150)
    serial_number: str | None = Field(default=None, max_length=150)


class CalibrationInput(ConfigInput):
    calibrated_on: date
    expires_on: date | None = None
    outcome: Literal['VALID', 'FAILED', 'UNKNOWN']
    provider: str | None = Field(default=None, max_length=150)
    certificate: str | None = Field(default=None, max_length=100)

    @model_validator(mode='after')
    def coherent(self):
        if self.expires_on is not None and self.expires_on < self.calibrated_on:
            raise ValueError('invalid_calibration_period')
        return self


class TypeSettingsInput(ConfigInput):
    display_name: str = Field(min_length=1, max_length=100)
    is_active: bool = Field(strict=True)


class PackageItem(ConfigInput):
    test_type: TypeCode
    method_version_id: UUID
    required: bool = Field(default=True, strict=True)


class PackageInput(ConfigInput):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    items: tuple[PackageItem, ...] = Field(min_length=1, max_length=3)

    @model_validator(mode='after')
    def coherent(self):
        if len({i.test_type for i in self.items}) != len(self.items):
            raise ValueError('duplicate_package_type')
        return self


def instrument_evidence(connection, instrument_id, measured_at, *, existing_id=None):
    if instrument_id is None:
        return {'instrument': None, 'calibration': {'status': 'NOT_LINKED'}}
    instrument = connection.execute(text('SELECT * FROM laboratory_instruments WHERE id=:id'),
                                    {'id': instrument_id}).mappings().first()
    if not instrument or (instrument['status'] != 'ACTIVE' and instrument_id != existing_id):
        raise LaboratoryError('instrument_not_available')
    day = measured_at.astimezone(ZoneInfo('America/Chicago')).date()
    calibration = connection.execute(text('''SELECT * FROM laboratory_calibrations
        WHERE instrument_id=:id AND calibrated_on<=:day ORDER BY calibrated_on DESC LIMIT 1'''),
        dict(id=instrument_id, day=day)).mappings().first()
    status = 'UNKNOWN'
    details = {}
    if calibration:
        status = calibration['outcome']
        if status == 'VALID':
            status = ('UNKNOWN' if calibration['expires_on'] is None else
                      'EXPIRED' if day > calibration['expires_on'] else 'VALID')
        details = {key: str(calibration[key]) if calibration[key] is not None else None
                   for key in ('id', 'calibrated_on', 'expires_on', 'provider', 'certificate')}
    return {'instrument': {'id': str(instrument['id']), 'code': instrument['code'],
                'name': instrument['name'], 'status': instrument['status']},
            'calibration': {**details, 'status': status, 'measurement_date': day.isoformat(),
                            'timezone': 'America/Chicago'}}


def lock_configuration(connection):
    """Laboratory lock order: configuration, then sample. No cross-module lock."""
    connection.execute(text('SELECT pg_advisory_xact_lock(140014)'))


class LaboratoryConfiguration:
    def __init__(self, engine):
        self._engine = engine
        self._audit = AuditTrail()

    def health_methods(self, actor):
        """Narrow analysis catalog; exposes no instrument or package maintenance data."""
        require_permission(actor, 'analysis.read')
        with self._engine.connect() as c:
            rows = c.execute(text('''SELECT id,test_type,display_name,version_label,is_active,configuration
                FROM test_method_versions ORDER BY test_type,version_label''')).mappings().all()
            fields = c.execute(text('SELECT method_version_id,field_code,unit_code FROM test_method_fields ORDER BY sort_order')).mappings().all()
            return tuple(dict(id=r['id'], test_type=r['test_type'], name=r['display_name'],
                version_label=r['version_label'], is_active=r['is_active'], configured=r['configuration'] is not None,
                fields=[dict(code=f['field_code'], unit_code=f['unit_code']) for f in fields if f['method_version_id'] == r['id']]) for r in rows)

    def catalog(self, actor):
        require_permission(actor, 'laboratory.read')
        with self._engine.connect().execution_options(isolation_level='REPEATABLE READ') as c:
            return {
                'types': [dict(r) for r in c.execute(text('SELECT code,display_name,is_active FROM laboratory_type_settings ORDER BY code')).mappings()],
                'methods': [dict(r) for r in c.execute(text('SELECT id,test_type,display_name,version_label,standard_reference,is_active,configuration FROM test_method_versions ORDER BY test_type,version_label')).mappings()],
                'instruments': [dict(r) for r in c.execute(text('SELECT id,code,name,model,serial_number,status FROM laboratory_instruments ORDER BY code')).mappings()],
                'calibrations': [dict(r) for r in c.execute(text('SELECT id,instrument_id,calibrated_on,expires_on,outcome,provider,certificate FROM laboratory_calibrations ORDER BY calibrated_on DESC,id')).mappings()],
                'packages': [dict(r) for r in c.execute(text('SELECT id,code,name,items FROM laboratory_packages ORDER BY code')).mappings()],
            }

    def create_method(self, actor, command: MethodVersionInput):
        require_permission(actor, 'laboratory.configure')
        command = MethodVersionInput.model_validate(command)
        identifier = uuid4()
        try:
            with self._engine.begin() as c:
                lock_configuration(c)
                c.execute(text('''INSERT INTO test_method_versions
                    (id,test_type,display_name,standard_reference,version_label,is_active,configuration,created_by,created_at)
                    VALUES (:id,:type,:name,:standard,:version,TRUE,CAST(:config AS jsonb),:actor,:now)'''),
                    dict(id=identifier, type=command.test_type, name=command.display_name,
                         standard=command.standard_reference, version=command.version_label,
                         config=command.model_dump_json(), actor=actor.user_id, now=datetime.now(timezone.utc)))
                for index, f in enumerate(command.fields):
                    c.execute(text('''INSERT INTO test_method_fields
                        (method_version_id,field_code,display_name,unit_code,display_decimal_places,detection_limit,sort_order)
                        VALUES (:id,:code,:name,:unit,:places,:limit,:sort)'''),
                        dict(id=identifier, code=f.code, name=f.display_name, unit=f.unit_code,
                             places=f.display_decimal_places, limit=f.detection_limit, sort=index))
                self._audit.append(c, actor, _Action.METHOD_CREATED, entity_id=identifier)
        except IntegrityError as exc:
            raise LaboratoryError('configuration_duplicate', 409) from exc
        return next(m for m in self.catalog(actor)['methods'] if m['id'] == identifier)

    def set_method_active(self, actor, method_id: UUID, active: bool):
        require_permission(actor, 'laboratory.configure')
        if type(active) is not bool:
            raise LaboratoryError('invalid_active_flag')
        with self._engine.begin() as c:
            lock_configuration(c)
            if c.execute(text('UPDATE test_method_versions SET is_active=:active WHERE id=:id'),
                         dict(id=method_id, active=active)).rowcount != 1:
                raise LaboratoryError('method_not_found', 404)
            self._audit.append(c, actor, _Action.METHOD_ACTIVATION, entity_id=method_id)

    def set_type(self, actor, code: TypeCode, command: TypeSettingsInput):
        require_permission(actor, 'laboratory.configure')
        command = TypeSettingsInput.model_validate(command)
        if code not in TYPE_FIELDS:
            raise LaboratoryError('unsupported_test_type')
        with self._engine.begin() as c:
            lock_configuration(c)
            c.execute(text('UPDATE laboratory_type_settings SET display_name=:name,is_active=:active WHERE code=:code'),
                      dict(code=code, name=command.display_name, active=command.is_active))
            self._audit.append(c, actor, _Action.TYPE_UPDATED, entity_id=UUID('14000000-0000-0000-0000-000000000001'))

    def create_instrument(self, actor, command: InstrumentInput):
        require_permission(actor, 'laboratory.configure')
        command = InstrumentInput.model_validate(command)
        identifier = uuid4()
        try:
            with self._engine.begin() as c:
                lock_configuration(c)
                c.execute(text('''INSERT INTO laboratory_instruments(id,code,name,model,serial_number,created_by)
                    VALUES (:id,:code,:name,:model,:serial_number,:actor)'''),
                    dict(id=identifier, actor=actor.user_id, **command.model_dump()))
                self._audit.append(c, actor, _Action.INSTRUMENT_CREATED, entity_id=identifier)
        except IntegrityError as exc:
            raise LaboratoryError('configuration_duplicate', 409) from exc
        return next(i for i in self.catalog(actor)['instruments'] if i['id'] == identifier)

    def set_instrument_status(self, actor, instrument_id, status, expected_status):
        require_permission(actor, 'laboratory.configure')
        if status not in ('ACTIVE', 'OUT_OF_SERVICE', 'RETIRED'):
            raise LaboratoryError('invalid_instrument_status')
        with self._engine.begin() as c:
            lock_configuration(c)
            if c.execute(text('UPDATE laboratory_instruments SET status=:status WHERE id=:id AND status=:expected'),
                         dict(id=instrument_id, status=status, expected=expected_status)).rowcount != 1:
                raise LaboratoryError('instrument_status_conflict', 409)
            self._audit.append(c, actor, _Action.INSTRUMENT_STATUS, entity_id=instrument_id)

    def add_calibration(self, actor, instrument_id, command: CalibrationInput):
        require_permission(actor, 'laboratory.configure')
        command = CalibrationInput.model_validate(command)
        identifier = uuid4()
        try:
            with self._engine.begin() as c:
                lock_configuration(c)
                if not c.execute(text('SELECT id FROM laboratory_instruments WHERE id=:id'), {'id': instrument_id}).first():
                    raise LaboratoryError('instrument_not_found', 404)
                c.execute(text('''INSERT INTO laboratory_calibrations
                    (id,instrument_id,calibrated_on,expires_on,outcome,provider,certificate,created_by)
                    VALUES (:id,:instrument,:calibrated_on,:expires_on,:outcome,:provider,:certificate,:actor)'''),
                    dict(id=identifier, instrument=instrument_id, actor=actor.user_id, **command.model_dump()))
                self._audit.append(c, actor, _Action.CALIBRATION_ADDED, entity_id=identifier)
        except IntegrityError as exc:
            raise LaboratoryError('configuration_duplicate', 409) from exc
        return next(i for i in self.catalog(actor)['calibrations'] if i['id'] == identifier)

    @staticmethod
    def _validate_package_methods(c, items):
        for item in items:
            if not c.execute(text('''SELECT m.id FROM test_method_versions m
                JOIN laboratory_type_settings t ON t.code=m.test_type
                WHERE m.id=:id AND m.test_type=:type AND m.is_active AND t.is_active'''),
                dict(id=item.method_version_id, type=item.test_type)).first():
                raise LaboratoryError('package_method_unavailable')

    def create_package(self, actor, command: PackageInput):
        require_permission(actor, 'laboratory.configure')
        command = PackageInput.model_validate(command)
        identifier = uuid4()
        try:
            with self._engine.begin() as c:
                lock_configuration(c)
                self._validate_package_methods(c, command.items)
                c.execute(text('''INSERT INTO laboratory_packages(id,code,name,items,created_by)
                    VALUES (:id,:code,:name,CAST(:items AS jsonb),:actor)'''),
                    dict(id=identifier, code=command.code, name=command.name,
                         items=json.dumps([i.model_dump(mode='json') for i in command.items]), actor=actor.user_id))
                self._audit.append(c, actor, _Action.PACKAGE_CREATED, entity_id=identifier)
        except IntegrityError as exc:
            raise LaboratoryError('configuration_duplicate', 409) from exc
        return next(p for p in self.catalog(actor)['packages'] if p['id'] == identifier)

    def apply_package(self, actor, barcode, package_id, expected_package_id=None):
        require_permission(actor, 'laboratory.write')
        with self._engine.begin() as c:
            lock_configuration(c)
            sample = c.execute(text('SELECT id,testing_status,package_snapshot FROM oil_samples WHERE barcode_value=:barcode FOR UPDATE'),
                               {'barcode': barcode.strip().upper()}).mappings().first()
            if not sample:
                raise LaboratoryError('sample_not_found', 404)
            if sample['testing_status'] != 'OPEN':
                raise LaboratoryError('sample_finalized', 409)
            previous_id = (sample['package_snapshot'] or {}).get('id')
            if previous_id != (str(expected_package_id) if expected_package_id else None):
                raise LaboratoryError('package_plan_conflict', 409)
            package = c.execute(text('SELECT * FROM laboratory_packages WHERE id=:id'), {'id': package_id}).mappings().first()
            if not package:
                raise LaboratoryError('package_not_found', 404)
            self._validate_package_methods(c, [PackageItem.model_validate(i) for i in package['items']])
            snapshot = dict(id=str(package['id']), code=package['code'], name=package['name'], items=package['items'])
            c.execute(text('UPDATE oil_samples SET package_snapshot=CAST(:snapshot AS jsonb) WHERE id=:id'),
                      dict(id=sample['id'], snapshot=json.dumps(snapshot)))
            c.execute(text('''INSERT INTO laboratory_operation_events
                (id,oil_sample_id,action_code,reason,actor_id,occurred_at,before_value,after_value)
                VALUES (:id,:sample,'PACKAGE_APPLIED','应用检测包',:actor,:now,CAST(:before AS jsonb),CAST(:after AS jsonb))'''),
                dict(id=uuid4(), sample=sample['id'], actor=actor.user_id, now=datetime.now(timezone.utc),
                     before=json.dumps(sample['package_snapshot'] or {}), after=json.dumps(snapshot)))
            self._audit.append(c, actor, _Action.PACKAGE_APPLIED, entity_id=sample['id'])
        return snapshot
