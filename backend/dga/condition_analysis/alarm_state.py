"""Analysis policy for one physical alarm episode. Persistence stays in AlarmCenter."""
from datetime import datetime
from .alarm_inputs import worst
from .rules import encode


def sampled(sources):
    return max(datetime.fromisoformat(s['measurement']['sampled_at']) for s in sources)


def can_recover(alarm, sources):
    baseline = alarm['latest_abnormal']
    if not sources or sampled(sources) <= sampled(baseline):
        return False
    methods = {(s['measurement']['method_version_id'],s['measurement']['unit']) for s in baseline}
    return len(methods)==1 and all(s['status']=='NORMAL' and
        (s['measurement']['method_version_id'],s['measurement']['unit']) in methods for s in sources)


def observation(alarm, sources):
    if not sources:
        reason='no_finalized_results'
    elif sampled(sources)<=sampled(alarm['latest_abnormal']):
        reason='not_later_sample'
    elif any(s['reason'] for s in sources):
        reason=next(s['reason'] for s in sources if s['reason'])
    elif not can_recover(alarm,sources):
        reason='still_abnormal' if any(s['status']!='NORMAL' for s in sources) else 'different_method_or_unit'
    else:
        reason='later_normal'
    return dict(reason=reason,sources=sources)


def inherit_baseline(target, other):
    sources=target['latest_abnormal']+other['latest_abnormal']
    latest=sampled(sources)
    sources={encode(s):s for s in sources if sampled([s])==latest}
    target['latest_abnormal']=[sources[k] for k in sorted(sources)]
    target['severity']=worst(target['latest_abnormal'])['status']


def recovery_valid(alarm, groups):
    sources=alarm['recovery']['sources']
    key=(alarm['asset_id'],alarm['test_type'],alarm['analyte'],sampled(sources))
    return {encode(s['measurement']) for s in sources}==groups.get(key,set())
