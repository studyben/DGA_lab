"""Strict source temporal evidence for staging, independent of business clock."""
import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_DATE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')
_INSTANT = re.compile(r'([0-9]{4}-[0-9]{2}-[0-9]{2})T([0-9]{2}:[0-9]{2}:[0-9]{2})(\.[0-9]{1,6})?(Z|[+-][0-9]{2}:[0-9]{2})?')


def decode_time(raw, *, cell_type='TEXT', row_zone=None, batch_zone=None,
                batch_zone_confirmed=False, required=True):
    zone_name = row_zone if row_zone not in (None, '') else (
        batch_zone if batch_zone_confirmed is True and batch_zone not in (None, '') else None)
    result=dict(raw=raw, precision='UNRESOLVED', business_date=None, local_time=None,
                source_timezone=zone_name, explicit_offset=None, utc_instant=None, issue_codes=[])
    if raw is None or raw == '':
        result.update(precision='MISSING', issue_codes=['date_required'] if required else [])
        return result
    if cell_type != 'TEXT' or not isinstance(raw, str):
        result['issue_codes']=['timestamp_requires_text']
        return result
    if len(raw)>80:
        result['issue_codes']=['timestamp_invalid']
        return result
    zone = None
    if zone_name is not None:
        try:
            if not isinstance(zone_name,str) or len(zone_name)>100:
                raise ValueError()
            zone=ZoneInfo(zone_name)
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            result['issue_codes']=['timezone_invalid']
    if _DATE.fullmatch(raw):
        try:
            day=date.fromisoformat(raw)
        except ValueError:
            result['issue_codes']=['timestamp_invalid']
        else:
            result.update(precision='DATE', business_date=day.isoformat())
        return result
    match=_INSTANT.fullmatch(raw)
    if match is None:
        result['issue_codes']=['timestamp_invalid']
        return result
    day,clock,fraction,offset=match.groups()
    try:
        local=datetime.fromisoformat(day+'T'+clock+(fraction or ''))
    except ValueError:
        result['issue_codes']=['timestamp_invalid']
        return result
    result.update(business_date=day, local_time=local.isoformat(), explicit_offset=offset)
    if result['issue_codes']:
        return result
    fixed = None
    if offset is not None:
        if offset=='Z':
            fixed=timezone.utc
        else:
            hours,minutes=int(offset[1:3]),int(offset[4:6])
            if hours>14 or minutes>59 or (hours==14 and minutes!=0):
                result['issue_codes']=['timestamp_invalid']
                return result
            fixed=timezone((1 if offset[0]=='+' else -1)*timedelta(hours=hours,minutes=minutes))
    try:
        if fixed is not None:
            instant=local.replace(tzinfo=fixed).astimezone(timezone.utc)
            if zone is not None:
                back=instant.astimezone(zone)
                if back.replace(tzinfo=None)!=local or back.utcoffset()!=fixed.utcoffset(None):
                    result['issue_codes']=['offset_timezone_conflict']
                    return result
        elif zone is None:
            result['issue_codes']=['timezone_required']
            return result
        else:
            candidates={}
            for fold in (0,1):
                aware=local.replace(tzinfo=zone,fold=fold)
                instant=aware.astimezone(timezone.utc)
                back=instant.astimezone(zone)
                if back.replace(tzinfo=None)==local and back.utcoffset()==aware.utcoffset():
                    candidates[instant]=aware
            if not candidates:
                result['issue_codes']=['nonexistent_local_time']
                return result
            if len(candidates)>1:
                result['issue_codes']=['ambiguous_local_time']
                return result
            instant=next(iter(candidates))
    except (OverflowError, ValueError):
        result['issue_codes']=['timestamp_invalid']
        return result
    result.update(precision='INSTANT', utc_instant=instant.isoformat().replace('+00:00','Z'))
    return result
