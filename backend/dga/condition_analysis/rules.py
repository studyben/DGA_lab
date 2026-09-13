"""Analysis-owned rule version lifecycle; values are explicitly supplied by operators."""
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
import json
from typing import Literal, Protocol
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, model_validator
from sqlalchemy import text
from dga.shared.auth.public import require_permission, AuditTrail
from dga.assets.public import TransformerReader


class HealthError(Exception):
    def __init__(self, code, status=422):
        self.code, self.status = code, status
        super().__init__(code)


class RuleMethodReader(Protocol):
    def health_methods(self, actor) -> tuple[dict, ...]: ...


class HealthRuleInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, frozen=True)
    name: str = Field(min_length=1, max_length=160)
    test_type: Literal['DGA', 'MOISTURE', 'BREAKDOWN_VOLTAGE']
    analyte: str = Field(min_length=1, max_length=30)
    method_version_id: UUID
    unit: str = Field(min_length=1, max_length=40)
    asset_id: UUID | None = None
    priority: int = Field(ge=0, le=1000, strict=True)
    effective_from: AwareDatetime
    effective_to: AwareDatetime | None = None
    operator: Literal['GT', 'GE', 'LT', 'LE']
    threshold: Decimal = Field(ge=0, max_digits=18, decimal_places=6, allow_inf_nan=False)
    severity: Literal['ATTENTION', 'WARNING', 'CRITICAL']

    @model_validator(mode='after')
    def valid_period(self):
        if self.effective_to and self.effective_to <= self.effective_from:
            raise ValueError('invalid_effective_period')
        return self


class _Action(StrEnum):
    CHANGE = 'HEALTH_RULE_CHANGED'


def lock_rules(c):
    c.execute(text('SELECT pg_advisory_xact_lock(160016)'))


def encode(value):
    return json.dumps(value, default=str, sort_keys=True)


def validate_revision(value):
    if type(value) is not int or value < 0:
        raise HealthError('invalid_rule_revision')


class HealthRules:
    def __init__(self, engine, methods: RuleMethodReader, assets: TransformerReader, *, clock=None):
        self._engine, self._methods, self._assets = engine, methods, assets
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._audit = AuditTrail(clock=self._clock)

    def methods(self, actor):
        require_permission(actor, 'analysis.read')
        return self._methods.health_methods(actor)

    def _validate(self, actor, command):
        command = HealthRuleInput.model_validate(command)
        method = next((m for m in self.methods(actor) if m['id'] == command.method_version_id), None)
        if not method or not method['configured'] or method['test_type'] != command.test_type:
            raise HealthError('rule_method_not_configured')
        if not any(f['code'] == command.analyte and f['unit_code'] == command.unit for f in method['fields']):
            raise HealthError('rule_method_unit_mismatch')
        if command.asset_id:
            self._assets.transformer_identity(actor, command.asset_id)
        return command

    def _get(self, c, identifier):
        row = c.execute(text('SELECT * FROM health_rule_versions WHERE id=:id'), {'id': identifier}).mappings().first()
        if row is None:
            raise HealthError('rule_not_found', 404)
        return dict(row)

    def _event(self, c, actor, action, before, after, reason):
        c.execute(text('''INSERT INTO health_rule_events
            (id,rule_id,actor_id,action,reason,occurred_at,before_value,after_value)
            VALUES (:id,:rule,:actor,:action,:reason,:at,CAST(:before AS jsonb),CAST(:after AS jsonb))'''),
            dict(id=uuid4(), rule=after['id'], actor=actor.user_id, action=action, reason=reason,
                 at=self._clock(), before=encode(before), after=encode(after)))
        self._audit.append(c, actor, _Action.CHANGE, entity_id=after['id'])

    def create(self, actor, command: HealthRuleInput):
        require_permission(actor, 'analysis.write')
        command = self._validate(actor, command)
        with self._engine.begin() as c:
            lock_rules(c)
            fields = command.model_dump()
            identifier = uuid4()
            c.execute(text('INSERT INTO health_rule_versions (' + ','.join(fields) + ',id,created_by,created_at) VALUES ('
                + ','.join(':'+key for key in fields) + ',:id,:actor,:now)'),
                fields | dict(id=identifier, actor=actor.user_id, now=self._clock()))
            result = self._get(c, identifier)
            self._event(c, actor, 'CREATED', None, result, 'Created draft')
            return result

    def get(self, actor, identifier):
        require_permission(actor, 'analysis.read')
        with self._engine.connect() as c:
            return self._get(c, identifier)

    def update(self, actor, identifier, command, expected_revision):
        require_permission(actor, 'analysis.write')
        validate_revision(expected_revision)
        command = self._validate(actor, command)
        with self._engine.begin() as c:
            lock_rules(c)
            before = self._get(c, identifier)
            if before['state'] != 'DRAFT':
                raise HealthError('rule_not_draft', 409)
            if before['revision'] != expected_revision:
                raise HealthError('rule_revision_conflict', 409)
            fields = command.model_dump()
            c.execute(text('UPDATE health_rule_versions SET ' + ','.join(key+'=:'+key for key in fields)
                + ',revision=revision+1 WHERE id=:id'), fields | {'id': identifier})
            after = self._get(c, identifier)
            self._event(c, actor, 'UPDATED', before, after, 'Updated draft')
            return after

    def copy(self, actor, identifier):
        require_permission(actor, 'analysis.write')
        source = self.get(actor, identifier)
        return self.create(actor, HealthRuleInput(**{k: source[k] for k in HealthRuleInput.model_fields}))

    def activate(self, actor, identifier, expected_revision, reason):
        return self._transition(actor, identifier, expected_revision, reason, 'ACTIVE')

    def retire(self, actor, identifier, expected_revision, reason):
        return self._transition(actor, identifier, expected_revision, reason, 'RETIRED')

    def _transition(self, actor, identifier, expected_revision, reason, target):
        require_permission(actor, 'analysis.write')
        validate_revision(expected_revision)
        if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 1000:
            raise HealthError('rule_reason_required')
        with self._engine.begin() as c:
            lock_rules(c)
            before = self._get(c, identifier)
            if before['revision'] != expected_revision:
                raise HealthError('rule_revision_conflict', 409)
            if before['state'] != ('DRAFT' if target == 'ACTIVE' else 'ACTIVE'):
                raise HealthError('invalid_rule_transition', 409)
            if target == 'ACTIVE':
                self._validate(actor, HealthRuleInput(**{k: before[k] for k in HealthRuleInput.model_fields}))
                conflict = c.execute(text('''SELECT id FROM health_rule_versions
                    WHERE state='ACTIVE' AND priority=:priority AND test_type=:test_type
                    AND analyte=:analyte AND method_version_id=:method_version_id AND unit=:unit
                    AND (asset_id IS NULL OR CAST(:asset_id AS uuid) IS NULL OR asset_id=:asset_id)
                    AND tstzrange(effective_from,effective_to,'[)') &&
                        tstzrange(:effective_from,:effective_to,'[)') LIMIT 1'''), before).first()
                if conflict:
                    raise HealthError('rule_scope_conflict', 409)
                c.execute(text("UPDATE health_rule_versions SET state='ACTIVE',revision=revision+1,approved_by=:actor,approved_at=:at WHERE id=:id"),
                          dict(actor=actor.user_id, at=self._clock(), id=identifier))
            else:
                c.execute(text("UPDATE health_rule_versions SET state='RETIRED',revision=revision+1 WHERE id=:id"),
                          dict(id=identifier))
            after = self._get(c, identifier)
            self._event(c, actor, 'ACTIVATED' if target == 'ACTIVE' else 'RETIRED', before, after, reason.strip())
            return after

    def list(self, actor):
        require_permission(actor, 'analysis.read')
        with self._engine.connect() as c:
            return [dict(r) for r in c.execute(text('SELECT * FROM health_rule_versions ORDER BY created_at DESC,id')).mappings()]

    def history(self, actor, identifier):
        require_permission(actor, 'analysis.read')
        with self._engine.connect() as c:
            self._get(c, identifier)
            return [dict(r) for r in c.execute(text("SELECT * FROM health_rule_events WHERE rule_id=:id ORDER BY (after_value->>'revision')::integer,id"), {'id': identifier}).mappings()]
