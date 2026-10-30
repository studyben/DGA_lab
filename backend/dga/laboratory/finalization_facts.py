"""Laboratory-owned immutable finalization capture and versioned evidence decoding."""
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text
from sqlalchemy.engine import Connection

from .configuration import MethodVersionInput, TYPE_FIELDS
from .errors import LaboratoryError


@dataclass(frozen=True)
class FinalizationFactsView:
    state: str
    unavailable_reason: str | None = None
    token: UUID | None = None
    schema_version: int | None = None
    inventory_complete: bool | None = None
    active_test_ids: tuple[UUID, ...] | None = None
    adopted_test_ids: tuple[UUID, ...] | None = None
    acknowledged_warning_codes: tuple[str, ...] | None = None


class _Reading(BaseModel):
    qualifier: Literal['EQ', 'ND', 'LT', 'GT']
    value: Decimal | None = Field(ge=0, max_digits=18, decimal_places=6, allow_inf_nan=False)

    @model_validator(mode='after')
    def pairing(self):
        if (self.qualifier == 'ND') != (self.value is None):
            raise ValueError('invalid qualified value')
        return self


class _Field(BaseModel):
    code: str
    unit_code: str | None = Field(min_length=1, max_length=40)


class _Method(BaseModel):
    method_version_id: UUID
    display_name: str
    version_label: str
    fields: tuple[_Field, ...]
    configuration: MethodVersionInput | None = None


class _Test(BaseModel):
    test_id: UUID
    test_type: Literal['DGA', 'MOISTURE', 'BREAKDOWN_VOLTAGE']
    method: _Method
    measured_at: AwareDatetime
    instrument_name: str | None = None
    quality_snapshot: dict | None = None
    notes: str | None = None
    result: dict[str, _Reading]

    @model_validator(mode='after')
    def typed(self):
        expected = TYPE_FIELDS[self.test_type]
        codes = [f.code for f in self.method.fields]
        keys = {c.lower() for c in expected} if self.test_type == 'DGA' else {'result'}
        if len(codes) != len(expected) or set(codes) != set(expected) or set(self.result) != keys:
            raise ValueError('invalid typed result fields')
        if self.method.configuration is not None and self.method.configuration.test_type != self.test_type:
            raise ValueError('method type mismatch')
        if self.method.configuration is not None and (
                tuple((f.code, f.unit_code) for f in self.method.fields) !=
                tuple((f.code, f.unit_code) for f in self.method.configuration.fields)):
            raise ValueError('frozen method fields disagree with configuration')
        return self


class _Sample(BaseModel):
    barcode: str = Field(min_length=1)
    sampled_at: AwareDatetime
    received_at: AwareDatetime
    site_name: str
    equipment_serial: str
    identity_status: Literal['ASSOCIATED']
    asset_snapshot: dict | None = None
    notes: str | None = None


class _Finalization(BaseModel):
    token: UUID
    finalized_at: AwareDatetime
    finalized_by_user_id: UUID
    finalized_by_display_name: str = Field(min_length=1)


class _Legacy(BaseModel):
    schema_version: Literal[1]
    sample: _Sample
    selected_results: tuple[_Test, ...] = Field(min_length=1, max_length=3)
    acknowledged_warning_codes: tuple[str, ...]
    finalization: _Finalization

    @model_validator(mode='after')
    def selections(self):
        if len({r.test_type for r in self.selected_results}) != len(self.selected_results):
            raise ValueError('duplicate selected type')
        if len({r.test_id for r in self.selected_results}) != len(self.selected_results):
            raise ValueError('duplicate selected id')
        return self


class _Attachment(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    id: UUID
    filename: str
    content_type: str
    byte_size: int = Field(ge=0)


class _Active(_Test):
    model_config = ConfigDict(extra='forbid', frozen=True)
    analyst_user_id: UUID
    instrument_id: UUID | None
    selected_for_report: bool
    created_at: AwareDatetime
    updated_at: AwareDatetime
    attachments: tuple[_Attachment, ...]


class _NativeSample(_Sample):
    model_config = ConfigDict(extra='forbid', frozen=True)
    oil_sample_id: UUID
    formal_asset_id: UUID
    package_snapshot: dict | None


class _Metadata(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    result_origin: Literal['LOCAL_LAB', 'EXTERNAL_LAB'] | None = None
    sampled_at_precision: Literal['INSTANT'] | None = None
    measured_at_precision: Literal['INSTANT'] | None = None
    sampling_context_verification: Literal['VERIFIED', 'PHYSICAL_IDENTITY_ONLY'] | None = None


class _Native(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    schema_version: Literal[2]
    sample: _NativeSample
    active_tests: tuple[_Active, ...] = Field(min_length=1)
    adopted_test_ids: tuple[UUID, ...] = Field(min_length=1, max_length=3)
    acknowledged_warning_codes: tuple[str, ...]
    finalization: _Finalization
    read_metadata: _Metadata

    @model_validator(mode='after')
    def inventory(self):
        ids = [r.test_id for r in self.active_tests]
        adopted = set(self.adopted_test_ids)
        selected = [r for r in self.active_tests if r.selected_for_report]
        if len(set(ids)) != len(ids) or len(adopted) != len(self.adopted_test_ids):
            raise ValueError('duplicate fact id')
        if adopted != {r.test_id for r in selected}:
            raise ValueError('adopted inventory mismatch')
        if len({r.test_type for r in selected}) != len(selected):
            raise ValueError('duplicate adopted type')
        if {r.test_type for r in selected} != {r.test_type for r in self.active_tests}:
            raise ValueError('missing adopted type')
        warnings = {w['code'] for r in self.active_tests for w in (r.quality_snapshot or {}).get('warnings', [])}
        if not warnings.issubset(self.acknowledged_warning_codes):
            raise ValueError('warnings not acknowledged')
        if tuple(sorted(set(self.acknowledged_warning_codes))) != self.acknowledged_warning_codes:
            raise ValueError('invalid acknowledgement set')
        return self


@dataclass(frozen=True)
class DecodedFinalization:
    """An immutable serialized value; each projection gets its own JSON value."""
    schema_version: int
    serialized: str

    @property
    def snapshot(self):
        return json.loads(self.serialized)

    def view(self):
        data = self.snapshot
        native = self.schema_version == 2
        adopted = data['adopted_test_ids'] if native else [r['test_id'] for r in data['selected_results']]
        return FinalizationFactsView(
            'AVAILABLE', token=UUID(data['finalization']['token']), schema_version=self.schema_version,
            inventory_complete=native,
            active_test_ids=tuple(UUID(r['test_id']) for r in data['active_tests']) if native else None,
            adopted_test_ids=tuple(UUID(identifier) for identifier in adopted),
            acknowledged_warning_codes=tuple(data['acknowledged_warning_codes']),
        )

    def to_report_snapshot(self):
        data = self.snapshot
        if self.schema_version == 1:
            return data
        tests = {r['test_id']: r for r in data['active_tests']}
        result_keys = ('test_id', 'test_type', 'method', 'measured_at', 'instrument_name', 'quality_snapshot', 'notes', 'result')
        sample_keys = ('barcode', 'sampled_at', 'received_at', 'site_name', 'equipment_serial', 'notes', 'identity_status', 'asset_snapshot')
        return dict(schema_version=1, sample={key: data['sample'][key] for key in sample_keys},
                    selected_results=[{key: tests[i][key] for key in result_keys} for i in data['adopted_test_ids']],
                    quality_evidence=[r['quality_snapshot'] for r in data['active_tests'] if r['quality_snapshot'] is not None],
                    acknowledged_warning_codes=data['acknowledged_warning_codes'], finalization=data['finalization'])


class FinalizationFacts:
    def capture_current(self, connection, actor, sample_id, token, now, warning_codes):
        sample = connection.execute(text('SELECT * FROM oil_samples WHERE id=:id'), {'id': sample_id}).mappings().one()
        rows = connection.execute(text("""SELECT t.*,m.display_name AS method_display_name,
            m.standard_reference,m.version_label FROM laboratory_tests t
            JOIN test_method_versions m ON m.id=t.method_version_id
            WHERE t.oil_sample_id=:id AND t.record_status='ACTIVE' ORDER BY t.created_at,t.id"""),
            {'id': sample_id}).mappings().all()
        active = []
        for row in rows:
            item = self._selected_result(connection, row)
            item.update(analyst_user_id=str(row['analyst_user_id']),
                        instrument_id=str(row['instrument_id']) if row['instrument_id'] else None,
                        selected_for_report=row['selected_for_report'], created_at=self._json_value(row['created_at']),
                        updated_at=self._json_value(row['updated_at']))
            attachments = connection.execute(text("""SELECT o.id,o.original_filename AS filename,o.content_type,o.byte_size
                FROM laboratory_test_attachments a JOIN stored_objects o ON o.id=a.stored_object_id
                WHERE a.test_id=:test ORDER BY o.created_at,o.id"""), {'test': row['id']}).mappings().all()
            item['attachments'] = [self._json_value(dict(a)) for a in attachments]
            active.append(item)
        adopted = sorted((r for r in active if r['selected_for_report']),
                         key=lambda r: (r['test_type'], r['created_at'], r['test_id']))
        payload = dict(schema_version=2, sample=dict(
            oil_sample_id=str(sample_id), formal_asset_id=str(sample['formal_asset_id']),
            barcode=sample['barcode_value'], sampled_at=self._json_value(sample['sampled_at']),
            received_at=self._json_value(sample['received_at']), site_name=sample['site_name'],
            equipment_serial=sample['equipment_serial'], notes=sample['notes'], identity_status=sample['identity_status'],
            asset_snapshot=sample['asset_snapshot'], package_snapshot=sample['package_snapshot']),
            active_tests=active, adopted_test_ids=[r['test_id'] for r in adopted],
            acknowledged_warning_codes=sorted(set(warning_codes)),
            finalization=dict(token=str(token), finalized_at=now.isoformat(),
                              finalized_by_user_id=str(actor.user_id), finalized_by_display_name=actor.display_name),
            read_metadata=dict(result_origin=None, sampled_at_precision=None, measured_at_precision=None,
                               sampling_context_verification=None))
        header = dict(oil_sample_id=sample_id, finalization_token=token, snapshot_schema_version=2,
                      physical_asset_id=sample['formal_asset_id'], sampled_at=sample['sampled_at'], fact_snapshot=payload)
        decoded = self.decode(header)
        connection.execute(text("""INSERT INTO laboratory_finalization_facts
            (oil_sample_id,finalization_token,snapshot_schema_version,physical_asset_id,sampled_at,fact_snapshot)
            VALUES (:sample,:token,2,:asset,:sampled,CAST(:payload AS jsonb))"""),
            dict(sample=sample_id, token=token, asset=sample['formal_asset_id'], sampled=sample['sampled_at'],
                 payload=decoded.serialized))
        return decoded

    @staticmethod
    def decode(row):
        try:
            payload = row['fact_snapshot']
            version = row['snapshot_schema_version']
            model = _Legacy.model_validate(payload) if version == 1 else _Native.model_validate(payload) if version == 2 else None
            if model is None or model.finalization.token != row['finalization_token']:
                raise ValueError('invalid fact version/token')
            if model.sample.sampled_at != row['sampled_at'] or row['physical_asset_id'] is None:
                raise ValueError('invalid frozen sampling identity')
            asset = model.sample.asset_snapshot
            if asset and asset.get('formal_asset_id') is not None:
                asset_id = asset['formal_asset_id']
                if not isinstance(asset_id, str):
                    raise ValueError('invalid asset snapshot identity type')
                if UUID(asset_id) != row['physical_asset_id']:
                    raise ValueError('asset snapshot mismatch')
            if version == 2 and (model.sample.oil_sample_id != row['oil_sample_id'] or model.sample.formal_asset_id != row['physical_asset_id']):
                raise ValueError('native identity mismatch')
            return DecodedFinalization(version, json.dumps(payload, ensure_ascii=False, allow_nan=False))
        except (KeyError, ValueError, TypeError, ArithmeticError) as error:
            raise LaboratoryError('finalization_facts_unavailable', 503) from error

    @staticmethod
    def _row(connection, sample_id, token):
        return connection.execute(text("""SELECT * FROM laboratory_finalization_facts
            WHERE oil_sample_id=:sample AND finalization_token=:token"""),
            {'sample': sample_id, 'token': token}).mappings().first()

    def load_current(self, connection, sample_id, token):
        row = self._row(connection, sample_id, token)
        if row is None:
            raise LaboratoryError('finalization_facts_unavailable', 503)
        return self.decode(row)

    def current_view(self, connection, sample):
        if sample['testing_status'] != 'FINALIZED':
            return FinalizationFactsView('NOT_FINALIZED')
        token = sample['testing_finalization_token']
        if token is None:
            return FinalizationFactsView('UNAVAILABLE', 'missing_finalization_token')
        row = self._row(connection, sample['id'], token)
        if row is None:
            return FinalizationFactsView('UNAVAILABLE', 'missing_finalization_facts', token=token)
        try:
            return self.decode(row).view()
        except LaboratoryError:
            return FinalizationFactsView('UNAVAILABLE', 'invalid_finalization_facts', token=token,
                                         schema_version=row['snapshot_schema_version'])


    def _selected_result(self, connection: Connection, row) -> dict[str, Any]:
        fields = [
            {
                'code': field['field_code'],
                'display_name': field['display_name'],
                'unit_code': field['unit_code'],
            }
            for field in connection.execute(
                text(
                    """SELECT field_code,display_name,unit_code FROM test_method_fields
                    WHERE method_version_id=:method ORDER BY sort_order,field_code"""
                ),
                {'method': row['method_version_id']},
            ).mappings()
        ]
        configuration = connection.execute(text('SELECT configuration FROM test_method_versions WHERE id=:id'),
                                           {'id': row['method_version_id']}).scalar_one()
        if configuration is not None:
            fields = [f.model_dump(mode='json') for f in MethodVersionInput.model_validate(configuration).fields]
        if row['test_type'] == 'DGA':
            values = connection.execute(
                text('SELECT * FROM dga_test_results WHERE test_id=:test'),
                {'test': row['id']},
            ).mappings().one()
            result = {
                code: {
                    'qualifier': values[f'{code}_qualifier'],
                    'value': self._json_value(values[f'{code}_value']),
                }
                for code in ('h2', 'ch4', 'c2h2', 'c2h4', 'c2h6', 'co', 'co2')
            }
        else:
            table = (
                'moisture_test_results'
                if row['test_type'] == 'MOISTURE'
                else 'breakdown_voltage_test_results'
            )
            value = connection.execute(
                text(f'SELECT result_value,result_qualifier FROM {table} WHERE test_id=:test'),
                {'test': row['id']},
            ).mappings().one()
            result = {
                'result': {
                    'qualifier': value['result_qualifier'],
                    'value': self._json_value(value['result_value']),
                }
            }
        return {
            'test_id': str(row['id']),
            'test_type': row['test_type'],
            'method': {
                'method_version_id': str(row['method_version_id']),
                'method_code': row['standard_reference'],
                'display_name': row['method_display_name'],
                'version_label': row['version_label'],
                'fields': fields,
                'configuration': configuration,
            },
            'measured_at': self._json_value(row['measured_at']),
            'instrument_name': row['instrument_name'],
            'quality_snapshot': row['quality_snapshot'],
            'notes': row['notes'],
            'result': result,
        }

    @classmethod
    def _json_value(cls, value):
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Decimal):
            return format(value, 'f')
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, dict):
            return {key: cls._json_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._json_value(item) for item in value]
        return value


