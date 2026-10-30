"""Atomic active-row review and paged immutable revision entries; no raw replacement."""
import json
from sqlalchemy import text
from .imports import dumped,fail
from .import_tables import SAMPLE_COLUMNS,TEST_COLUMNS
from .import_validation import BOUNDS


def apply_rows(c,batch,changes):
    ids=[x.row_id for x in changes]
    rows=c.execute(text("""SELECT r.* FROM lab_import_rows r JOIN lab_import_files f ON f.id=r.file_id
        WHERE r.batch_id=:batch AND r.id=ANY(:ids) AND f.active AND f.state='RECEIVED'
        ORDER BY r.id FOR UPDATE OF r"""),dict(batch=batch['id'],ids=ids)).mappings().all()
    found={str(x['id']):x for x in rows}
    if len(found)!=len(ids): fail('import_row_not_found',404)
    before=[];after=[]
    bounds=dict(BOUNDS,source_lab_key=80,external_sample_id=160,external_test_id=160)
    for prefix in ('h2','ch4','c2h2','c2h4','c2h6','co','co2','result'): bounds[prefix+'_value']=128
    for change in sorted(changes,key=lambda x:str(x.row_id)):
        row=found[str(change.row_id)]
        allowed=SAMPLE_COLUMNS if row['sheet']=='油样信息' else TEST_COLUMNS
        if set(change.values)-set(allowed): fail('invalid_import_input')
        if any(isinstance(v,str) and len(v)>bounds.get(k,32767) for k,v in change.values.items()):
            fail('invalid_import_input')
        old={**row['raw_values'],**row['overrides']}
        changed={k:v for k,v in change.values.items() if dumped(old.get(k))!=dumped(v)}
        if not changed: continue
        overrides=dict(row['overrides'])
        for field,value in changed.items():
            if type(value) is type(row['raw_values'].get(field)) and value==row['raw_values'].get(field):
                overrides.pop(field,None)
            else: overrides[field]=value
        c.execute(text('UPDATE lab_import_rows SET overrides=CAST(:values AS jsonb) WHERE id=:id'),
            dict(id=row['id'],values=dumped(overrides)))
        locator=dict(row_id=str(row['id']),sheet=row['sheet'],row_number=row['row_number'])
        before.append(dict(**locator,values={k:old.get(k) for k in changed}))
        after.append(dict(**locator,values=changed))
    return before,after


def history(owner,actor,batch_id,*,page=1):
    if type(page) is not int or not 1<=page<=100000: fail('invalid_import_input')
    with owner.engine.begin() as c:
        owner._authorize(c,actor)
        owner._locked(c,batch_id)
        params=dict(id=owner._uuid(batch_id),offset=(page-1)*20)
        row=c.execute(text("""WITH events AS(
            SELECT r.*,u.display_name FROM lab_import_revisions r JOIN users u ON u.id=r.actor_id
            WHERE r.batch_id=:id),entries AS(
            SELECT e.id::text id,e.id event_id,e.revision,e.actor_id,e.display_name,e.occurred_at,e.reason,
                'BATCH'::text change_kind,NULL::text row_id,NULL::text sheet,NULL::int row_number,0::bigint ordinal,
                jsonb_array_length(COALESCE(e.after_value->'row_changes','[]'::jsonb)) row_change_count,
                e.before_value-'row_changes' before_value,e.after_value-'row_changes' after_value
            FROM events e
            UNION ALL
            SELECT e.id::text||':row:'||(a.value->>'row_id'),e.id,e.revision,e.actor_id,e.display_name,e.occurred_at,e.reason,
                'ROW',a.value->>'row_id',a.value->>'sheet',(a.value->>'row_number')::int,a.ordinality,
                jsonb_array_length(e.after_value->'row_changes'),
                e.before_value->'row_changes'->(a.ordinality::int-1)->'values',a.value->'values'
            FROM events e CROSS JOIN LATERAL jsonb_array_elements(COALESCE(e.after_value->'row_changes','[]'::jsonb))
                WITH ORDINALITY a(value,ordinality))
            SELECT (SELECT count(*) FROM entries) total,
                (SELECT jsonb_agg(to_jsonb(p)-'ordinal') FROM(SELECT * FROM entries
                 ORDER BY revision DESC,ordinal,id LIMIT 20 OFFSET :offset)p) items"""),params).mappings().one()
        return dict(items=row['items'] or [],total=row['total'],page=page,page_size=20)

