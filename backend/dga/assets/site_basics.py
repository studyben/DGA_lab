"""Narrow asset-owned site maintenance; never changes customer or installation identity."""
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError, field_validator, model_validator
from sqlalchemy import text

from dga.shared.auth.public import AuditTrail, require_permission


class SiteBasicsInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: StrictInt = Field(ge=0)
    site_name: str = Field(min_length=1, max_length=200)
    location_text: str | None = Field(default=None, max_length=300)
    grid_status: Literal['NOT_STARTED', 'IN_PROGRESS', 'COMPLETED'] | None = None
    operation_status: Literal['NOT_OPERATIONAL', 'PARTIAL', 'OPERATIONAL', 'DECOMMISSIONED'] | None = None
    commissioning_date: date | None = None
    product_line: Literal['PV', 'ESS']
    power_mw: Decimal | None = Field(default=None, ge=0, max_digits=16, decimal_places=6, allow_inf_nan=False)
    energy_mwh: Decimal | None = Field(default=None, ge=0, max_digits=16, decimal_places=6, allow_inf_nan=False)

    @field_validator('site_name')
    @classmethod
    def nonempty_name(cls, value):
        if not value.strip():
            raise ValueError('site_name_required')
        return value.strip()

    @model_validator(mode='after')
    def capacity_line(self):
        if self.product_line == 'PV' and self.energy_mwh is not None:
            raise ValueError('pv_energy_not_allowed')
        return self


class SiteAction(StrEnum):
    UPDATE = 'SITE_BASICS_UPDATE'


class SiteBasics:
    def __init__(self, engine, *, clock=None):
        self._engine = engine
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._audit = AuditTrail(clock=self._clock)

    def update(self, actor, site_id, **values):
        from .public import AssetQueryError
        require_permission(actor, 'assets.site.edit')
        try:
            body = SiteBasicsInput(**values)
        except ValidationError as error:
            raise AssetQueryError('invalid_site_basics') from error
        with self._engine.begin() as c:
            # Same asset lock held by laboratory snapshot reads; no cross-module table access.
            c.execute(text('SELECT pg_advisory_xact_lock(110011)'))
            row = c.execute(text('SELECT * FROM sites WHERE id=:id FOR UPDATE'), {'id': site_id}).mappings().first()
            if row is None:
                raise AssetQueryError('site_not_found', 404)
            if row['revision'] != body.expected_revision:
                raise AssetQueryError('stale_site', 409)
            line = c.execute(text('SELECT * FROM site_product_lines WHERE site_id=:id AND product_line=:line'),
                {'id': site_id, 'line': body.product_line}).mappings().first()
            if line is None:
                raise AssetQueryError('site_product_line_not_found', 409)
            shared = ('site_name', 'location_text', 'grid_status', 'operation_status', 'commissioning_date')
            before = {key: row[key] for key in shared} | {key: line[key] for key in ('product_line', 'power_mw', 'energy_mwh')}
            after = body.model_dump(exclude={'expected_revision'})
            c.execute(text('''UPDATE sites SET site_name=:site_name,location_text=:location_text,
                grid_status=:grid_status,operation_status=:operation_status,commissioning_date=:commissioning_date,
                revision=revision+1 WHERE id=:id'''), after | {'id': site_id})
            c.execute(text('''UPDATE site_product_lines SET power_mw=:power_mw,energy_mwh=:energy_mwh
                WHERE site_id=:id AND product_line=:product_line'''), after | {'id': site_id})
            c.execute(text('''INSERT INTO site_basic_events(id,site_id,actor_id,occurred_at,before_value,after_value)
                VALUES (:event,:id,:actor,:at,CAST(:before AS jsonb),CAST(:after AS jsonb))'''),
                {'event': uuid4(), 'id': site_id, 'actor': actor.user_id, 'at': self._clock(),
                 'before': json.dumps(before, default=str), 'after': json.dumps(after, default=str)})
            self._audit.append(c, actor, SiteAction.UPDATE, entity_id=site_id)
            return {'revision': row['revision'] + 1}

    def history(self, actor, site_id):
        require_permission(actor, 'audit.read')
        with self._engine.connect() as c:
            return [dict(r) for r in c.execute(text('''SELECT id,actor_id,occurred_at,before_value,after_value
                FROM site_basic_events WHERE site_id=:id ORDER BY occurred_at,id'''), {'id': site_id}).mappings()]
