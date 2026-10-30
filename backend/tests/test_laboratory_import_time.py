"""Strict staged temporal evidence; no source time is manufactured."""
def test_calendar_date_has_no_midnight_or_utc_and_missing_remains_missing():
    from dga.laboratory.import_time import decode_time
    date=decode_time('2026-10-29',row_zone='America/Chicago')
    assert date['precision']=='DATE' and date['business_date']=='2026-10-29'
    assert date['local_time'] is None and date['utc_instant'] is None
    assert date['raw']=='2026-10-29' and date['issue_codes']==[]
    missing=decode_time('')
    assert missing['precision']=='MISSING' and missing['issue_codes']==['date_required']
    assert missing['business_date'] is None and missing['utc_instant'] is None



def test_source_zone_gap_fold_and_explicit_offset_have_distinct_outcomes():
    from dga.laboratory.import_time import decode_time
    assert decode_time('2026-03-08T02:30:00',row_zone='America/Chicago')['issue_codes']==['nonexistent_local_time']
    fold=decode_time('2026-11-01T01:30:00',row_zone='America/Chicago')
    assert fold['precision']=='UNRESOLVED' and fold['issue_codes']==['ambiguous_local_time']
    early=decode_time('2026-11-01T01:30:00-05:00',row_zone='America/Chicago')
    late=decode_time('2026-11-01T01:30:00-06:00',row_zone='America/Chicago')
    assert early['utc_instant']=='2026-11-01T06:30:00Z'
    assert late['utc_instant']=='2026-11-01T07:30:00Z'
    assert early['precision']==late['precision']=='INSTANT'
    assert decode_time('2026-07-01T12:00:00-06:00',row_zone='America/Chicago')['issue_codes']==['offset_timezone_conflict']
    assert decode_time('2026-10-29T12:00:00',batch_zone='America/Chicago')['issue_codes']==['timezone_required']
    confirmed=decode_time('2026-10-29T12:00:00',batch_zone='America/Chicago',batch_zone_confirmed=True)
    assert confirmed['utc_instant']=='2026-10-29T17:00:00Z'
    offset=decode_time('2026-10-29T12:00:00+14:00')
    assert offset['utc_instant']=='2026-10-28T22:00:00Z' and offset['source_timezone'] is None



import pytest


@pytest.mark.parametrize('raw',[
    '2026-02-29','20261029','2026-W44-4','2026-302','2026-10-29 12:00:00',
    '2026-10-29T24:00:00Z','2026-10-29T12:00:60Z','2026-10-29T12:00Z',
    '2026-10-29T12:00:00.1234567Z','2026-10-29T12:00:00+14:01',
    '2026-10-29T12:00:00+15:00','2026-10-29T12:00:00+01:60',
    '0001-01-01T00:00:00+14:00','9999-12-31T23:59:59-14:00',
])
def test_non_contract_or_unrepresentable_timestamp_remains_unresolved(raw):
    from dga.laboratory.import_time import decode_time
    value=decode_time(raw)
    assert value['precision']=='UNRESOLVED'
    assert value['utc_instant'] is None and value['issue_codes']==['timestamp_invalid']


def test_temporal_cell_type_zone_precedence_and_fraction_are_explicit():
    from dga.laboratory.import_time import decode_time
    for raw,kind in [('45200','NUMBER'),('45200','DATE_NUMBER'),(True,'BOOLEAN')]:
        value=decode_time(raw,cell_type=kind)
        assert value['issue_codes']==['timestamp_requires_text'] and value['utc_instant'] is None
    bad=decode_time('2026-10-29T12:00:00',row_zone='Invalid/Zone',
        batch_zone='UTC',batch_zone_confirmed=True)
    assert bad['issue_codes']==['timezone_invalid']
    assert decode_time('',required=False)['issue_codes']==[]
    exact=decode_time('2026-10-29T12:00:00.000001Z')
    assert exact['utc_instant']=='2026-10-29T12:00:00.000001Z'
    assert exact['raw']=='2026-10-29T12:00:00.000001Z'
