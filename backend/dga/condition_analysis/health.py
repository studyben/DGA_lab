"""Read-through health evaluation over owner-provided facts."""
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from operator import gt, ge, lt, le
from uuid import uuid4
from sqlalchemy import text
from dga.shared.auth.public import require_permission
from dga.assets.public import HealthAssetReader
from dga.laboratory.public import HealthResultReader
from .rules import HealthRules, HealthError, lock_rules, encode

SEVERITY = {'UNASSESSED': 0, 'NORMAL': 1, 'ATTENTION': 2, 'WARNING': 3, 'CRITICAL': 4}
COMPARE = {'GT': gt, 'GE': ge, 'LT': lt, 'LE': le}


def aggregate(sources):
    return dict(status=max((s['status'] for s in sources), key=SEVERITY.get, default='UNASSESSED'),
                incomplete=any(s['status']=='UNASSESSED' for s in sources) or not sources)


def assess(asset_id, measurement, policies):
    result = dict(asset_id=str(asset_id), status='UNASSESSED', reason=None,
                  measurement=asdict(measurement), rule=None)
    if not measurement.method_configured:
        result['reason'] = 'method_not_configured'
    elif not measurement.unit:
        result['reason'] = 'missing_unit'
    elif measurement.qualifier != 'EQ':
        result['reason'] = 'qualified_result'
    else:
        applicable = [r for r in policies if r['test_type']==measurement.test_type
            and r['analyte']==measurement.analyte and r['method_version_id']==measurement.method_version_id
            and r['unit']==measurement.unit and (r['asset_id'] is None or r['asset_id']==asset_id)]
        if not applicable:
            result['reason'] = 'no_applicable_rule'
        else:
            rule = max(applicable, key=lambda r:r['priority'])
            result['rule'] = rule
            result['status'] = rule['severity'] if COMPARE[rule['operator']](measurement.value,rule['threshold']) else 'NORMAL'
    return result


class DeviceHealth:
    def __init__(self, engine, assets: HealthAssetReader, laboratory: HealthResultReader,
                 rules: HealthRules, *, clock=None):
        self._engine, self._assets, self._laboratory, self._rules = engine, assets, laboratory, rules
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _source(self,actor,asset_id,now):
        tree=self._assets.health_assets(actor,asset_id,now)
        ids=tuple(a.id for a in tree if a.asset_type=='TRANSFORMER')
        points=tuple(p for p in self._laboratory.finalized_measurements_for_assets(actor,ids) if p.sampled_at<=now)
        return tree,points

    def _stable_source(self,actor,asset_id,now):
        for _ in range(3):
            before=self._source(actor,asset_id,now)
            after=self._source(actor,asset_id,now)
            if before==after:
                return after
        raise HealthError('health_inputs_changed',409)

    def query(self, actor, asset_id):
        require_permission(actor, 'analysis.read')
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise HealthError('timezone_required')
        with self._engine.begin() as c:
            lock_rules(c)
            policies = [dict(r) for r in c.execute(text("""SELECT * FROM health_rule_versions
                WHERE state='ACTIVE' AND effective_from<=:now AND (effective_to IS NULL OR :now<effective_to)
                ORDER BY id"""), {'now':now}).mappings()]
            tree,points=self._stable_source(actor,asset_id,now)
            ids = tuple(a.id for a in tree if a.asset_type=='TRANSFORMER')
            latest = {}
            for point in points:
                key = (point.asset_id,point.test_type,point.analyte)
                if key not in latest or point.sampled_at>latest[key][0].sampled_at:
                    latest[key]=[point]
                elif point.sampled_at==latest[key][0].sampled_at:
                    latest[key].append(point)
            sources = [assess(p.asset_id,p,policies) | {'latest_time_tied':len(group)>1}
                       for group in latest.values() for p in group]
            observed = {p.asset_id for p in points}
            sources += [dict(asset_id=str(identifier),status='UNASSESSED',reason='no_finalized_results',measurement=None,rule=None)
                        for identifier in ids if identifier not in observed]
            payload = dict(subject_id=str(asset_id),sources=sources,assets=[asdict(a) for a in tree],
                own=aggregate([s for s in sources if s['asset_id']==str(asset_id)]),
                descendants=aggregate([s for s in sources if s['asset_id']!=str(asset_id)]),**aggregate(sources))
            payload = json.loads(encode(payload))
            fingerprint = sha256(encode(payload).encode()).hexdigest()
            identifier=uuid4()
            payload.update(evaluated_at=now.isoformat(),evaluation_id=str(identifier))
            c.execute(text('''INSERT INTO health_evaluations(id,subject_id,fingerprint,evaluated_at,evidence)
                VALUES(:id,:subject,:fingerprint,:now,CAST(:evidence AS jsonb))
                ON CONFLICT(subject_id,fingerprint) DO NOTHING'''), dict(id=identifier,subject=asset_id,
                fingerprint=fingerprint,now=now,evidence=encode(payload)))
            retained = c.execute(text('SELECT evidence FROM health_evaluations WHERE subject_id=:subject AND fingerprint=:fingerprint'),
                                 dict(subject=asset_id,fingerprint=fingerprint)).scalar_one()
            return retained | {'checked_at':now.isoformat()}

    def evaluation(self, actor, asset_id, evaluation_id):
        require_permission(actor, 'analysis.read')
        with self._engine.connect() as c:
            evidence = c.execute(text('SELECT evidence FROM health_evaluations WHERE id=:id AND subject_id=:subject'),
                                 dict(id=evaluation_id,subject=asset_id)).scalar_one_or_none()
            if evidence is None:
                raise HealthError('health_evaluation_not_found',404)
            return evidence
