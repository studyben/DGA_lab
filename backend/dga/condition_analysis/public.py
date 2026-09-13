"""Public application interface for physical transformer trends."""
from dataclasses import asdict
import json
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, model_validator
from dga.assets.public import TransformerReader
from dga.laboratory.public import FinalizedResultReader
from .statistics import calculate, metric
from dga.shared.contracts import ModuleDescriptor
from dga.shared.auth.public import ActorContext, require_permission
from .rules import HealthRules, HealthRuleInput, HealthError

MODULE = ModuleDescriptor(code='condition_analysis', label='状态分析')


def access_context(actor: ActorContext) -> dict:
    require_permission(actor, 'analysis.read')
    return {'module': MODULE.code, 'actor_id': str(actor.user_id)}


class TrendQuery(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    test_type: Literal['DGA', 'MOISTURE', 'BREAKDOWN_VOLTAGE'] = 'DGA'
    analyte: str = 'H2'
    group_id: str | None = Field(default=None, max_length=240)
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode='after')
    def coherent(self):
        fields = {'DGA': ('H2', 'CH4', 'C2H2', 'C2H4', 'C2H6', 'CO', 'CO2'),
                  'MOISTURE': ('MOISTURE',), 'BREAKDOWN_VOLTAGE': ('BREAKDOWN_VOLTAGE',)}
        if self.analyte not in fields[self.test_type]:
            raise ValueError('invalid_analyte')
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError('invalid_date_range')
        if self.end_date == date.max:
            raise ValueError('invalid_end_date')
        return self

    def instants(self):
        zone = ZoneInfo('America/Chicago')
        start = datetime.combine(self.start_date, time(), zone).astimezone(timezone.utc) if self.start_date else None
        end = datetime.combine(self.end_date + timedelta(days=1), time(), zone).astimezone(timezone.utc) if self.end_date else None
        return start, end


class TransformerTrends:
    def __init__(self, assets: TransformerReader, laboratory: FinalizedResultReader):
        self._assets = assets
        self._laboratory = laboratory

    def query(self, actor: ActorContext, asset_id: UUID, query: TrendQuery) -> dict:
        require_permission(actor, 'analysis.read')
        asset = self._assets.transformer_identity(actor, asset_id)
        start, end = query.instants()
        points = [asdict(p) for p in self._laboratory.finalized_measurements(actor, asset_id, start, end)
                  if p.test_type == query.test_type and p.analyte == query.analyte]
        points.sort(key=lambda p: (p['sampled_at'], p['sample_id'], p['test_id']))
        groups = {}
        latest_group_id = None
        for point in points:
            point['group_id'] = json.dumps([str(point['method_version_id']), point['unit']], ensure_ascii=False)
            if point['method_configured'] and point['unit']:
                latest_group_id = point['group_id']
                groups[point['group_id']] = {key: point[key] for key in ('method_version_id', 'method_name', 'version_label', 'unit')}
                groups[point['group_id']]['id'] = point['group_id']
        selected_id = query.group_id if query.group_id is not None else latest_group_id
        selected = groups.get(selected_id)
        for point in points:
            reasons = []
            if not point['method_configured']:
                reasons.append('placeholder_method')
            if not point['unit']:
                reasons.append('missing_unit')
            if selected:
                if point['method_version_id'] != selected['method_version_id']:
                    reasons.append('different_method')
                if point['unit'] != selected['unit']:
                    reasons.append('different_unit')
            else:
                reasons.append('no_comparable_group')
            if point['qualifier'] != 'EQ':
                reasons.append('qualified_result')
            point['exclusion_reasons'] = reasons
            for key in ('delta', 'annualized_change', 'moving_mean'):
                point[key] = metric(reason='excluded_result')
        observed = [p for p in points if selected and p['group_id'] == selected_id]
        numeric = [p for p in points if not p['exclusion_reasons']]
        statistics = calculate(numeric)
        return {'asset': asset, 'points': points, 'groups': list(groups.values()), 'selected_group': selected,
                'latest': observed[-1] if observed else None, 'latest_numeric': numeric[-1] if numeric else None,
                'latest_time_tied': len(observed) > 1 and observed[-1]['sampled_at'] == observed[-2]['sampled_at'],
                'numeric_count': len(numeric), 'statistics': statistics}


def http_router(trends, actor_dependency):
    from .http import http_router as router
    return router(trends, actor_dependency)
