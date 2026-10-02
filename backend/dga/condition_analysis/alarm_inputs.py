"""Observation reads complete before alarm storage connection is borrowed."""
import json
from uuid import UUID
from sqlalchemy import text
from .rules import encode, HealthError
from .health import assess, SEVERITY, latest_groups


def observe(engine, assets, laboratory, actor, now):
    contexts = assets.alarm_assets(actor, now)
    points = tuple(p for p in laboratory.finalized_measurements_for_assets(actor, tuple(UUID(a['id']) for a in contexts)) if p.sampled_at <= now)
    with engine.connect() as c:
        rules = tuple(dict(r) for r in c.execute(text("SELECT * FROM health_rule_versions WHERE state='ACTIVE' AND effective_from<=:at AND (effective_to IS NULL OR :at<effective_to) ORDER BY id"), {'at': now}).mappings())
    return contexts, points, rules


def stable_observation(engine, assets, laboratory, actor, now):
    for _ in range(3):
        before = observe(engine, assets, laboratory, actor, now)
        after = observe(engine, assets, laboratory, actor, now)
        if before == after:
            return after
    raise HealthError('health_inputs_changed', 409)


def assessments(points, rules):
    return {tuple(map(str, key)): json.loads(encode([assess(p.asset_id, p, rules) for p in group]))
            for key, group in latest_groups(points).items()}


def worst(sources):
    return max(sources, key=lambda s: SEVERITY[s['status']])
