"""Validated alarm list contract; filters use current asset placement."""
from datetime import date, datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo
from pydantic import BaseModel, Field, model_validator


class AlarmQuery(BaseModel):
    scope: Literal['current','history','all']='current'
    product_line: Literal['PV','ESS'] | None=None
    site: str=Field(default='',max_length=160)
    customer: str=Field(default='',max_length=160)
    equipment: str=Field(default='',max_length=160)
    asset_id: UUID | None=None
    test_type: Literal['DGA','MOISTURE','BREAKDOWN_VOLTAGE'] | None=None
    analyte: Literal['H2','CH4','C2H2','C2H4','C2H6','CO','CO2','MOISTURE','BREAKDOWN_VOLTAGE'] | None=None
    severity: Literal['ATTENTION','WARNING','CRITICAL'] | None=None
    state: Literal['UNACKNOWLEDGED','ACKNOWLEDGED','RESOLVED'] | None=None
    from_date: date | None=None
    to_date: date | None=None
    page: int=Field(default=1,ge=1,le=1000000)
    page_size: int=Field(default=25,ge=1,le=100)

    @model_validator(mode='after')
    def dates(self):
        if self.from_date and self.to_date and self.from_date>self.to_date:
            raise ValueError('invalid date range')
        return self


def filtered(rows, contexts, query, now):
    matches=[]
    for alarm in rows:
        current=alarm['state']!='RESOLVED' and not alarm['superseded_by']
        if (query.scope=='current' and not current) or (query.scope=='history' and current):
            continue
        context=contexts.get(alarm['asset_id']) or {}
        if query.product_line and context.get('product_line')!=query.product_line:
            continue
        if query.asset_id and str(query.asset_id) not in [alarm['asset_id'],*context.get('ancestor_ids',[])]:
            continue
        if any(getattr(query,k) and alarm[k]!=getattr(query,k) for k in ('test_type','analyte','severity','state')):
            continue
        values={'site':context.get('site_name') or '', 'customer':context.get('customer_name') or '',
            'equipment':' '.join(context.get(k) or '' for k in ('serial_number','system_asset_number'))}
        if any(getattr(query,k).strip().casefold() not in value.casefold() for k,value in values.items()):
            continue
        day=datetime.fromisoformat(alarm['opened_at']).astimezone(ZoneInfo('America/Chicago')).date()
        if (query.from_date and day<query.from_date) or (query.to_date and day>query.to_date):
            continue
        matches.append(alarm|{'current_asset':context or None})
    matches.sort(key=lambda a:(a['opened_at'],a['id']),reverse=True)
    offset=(query.page-1)*query.page_size
    return dict(items=matches[offset:offset+query.page_size],total=len(matches),
        unresolved_count=sum(a['state']!='RESOLVED' and not a['superseded_by'] for a in matches),
        page=query.page,page_size=query.page_size,checked_at=now.isoformat())
