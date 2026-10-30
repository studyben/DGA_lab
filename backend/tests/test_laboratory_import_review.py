"""Atomic one-row review and frozen-retry behavior through the public staging facade."""
from uuid import uuid4
import pytest
from dga.laboratory.public import LaboratoryError
from tests.laboratory_import_fixtures import setup,receive,queued


def test_review_retains_raw_overrides_and_parsed_note_without_creating_retests(database_url):
    engine,_,actor,imports,_,batch,sample,test,_=setup(database_url)
    receive(imports,actor,batch,[sample],[test]);queued(imports,actor,batch);imports.process_next('before-review')
    first=imports.samples(actor,batch['id'])['items'][0]
    test_before=imports.sample(actor,batch['id'],first['id'])['tests']['items'][0]
    key=str(uuid4());note='😀'*2000
    values=dict(expected_revision=imports.get(actor,batch['id'])['revision'],reason='Reviewed source evidence',
        changes=[dict(row_id=first['id'],values=dict(source_note=note,notes='separate ordinary note'))])
    revised=imports.revise(actor,batch['id'],idempotency_key=key,**values)
    stale=imports.samples(actor,batch['id'])['items'][0]
    assert stale['stale'] and stale['raw_values']['source_note']==sample['source_note']
    assert stale['reviewed_values']['source_note']==note
    assert stale['parsed_values']['source_note']==sample['source_note']
    assert imports.revise(actor,batch['id'],idempotency_key=key,**values)['operation']==revised['operation']
    queued(imports,actor,batch);imports.process_next('after-review')
    current=imports.samples(actor,batch['id'])['items'][0]
    assert current['id']==first['id'] and current['parsed_values']['source_note']==note
    assert current['parsed_values']['notes']=='separate ordinary note'
    assert imports.sample(actor,batch['id'],first['id'])['tests']['items'][0]['id']==test_before['id']
    assert imports.get(actor,batch['id'])['summary']['test_count']==1
    history=imports.revision_history(actor,batch['id'])
    row_entry=next(x for x in history['items'] if x['change_kind']=='ROW')
    assert row_entry['row_id']==first['id'] and row_entry['before_value']['source_note']==sample['source_note']
    assert row_entry['after_value']['source_note']==note and row_entry['event_id']
    assert not any('row_changes' in x['before_value'] or 'row_changes' in x['after_value'] for x in history['items'])
    engine.dispose()


@pytest.mark.parametrize('change',[
    dict(unknown='value'),dict(result_value=1),dict(result_value=1.5),dict(notes=['not scalar']),
    dict(source_note='😀'*2001),dict(external_sample_id='x'*161),dict(result_value='1'*129)])
def test_row_review_rejects_unknown_non_scalar_and_out_of_bound_values_atomically(database_url,change):
    engine,_,actor,imports,_,batch,sample,test,_=setup(database_url)
    receive(imports,actor,batch,[sample],[test]);queued(imports,actor,batch);imports.process_next('review-bounds')
    row=imports.samples(actor,batch['id'])['items'][0]
    revision=imports.get(actor,batch['id'])['revision']
    with pytest.raises(LaboratoryError,match='invalid_import_input'):
        imports.revise(actor,batch['id'],idempotency_key=str(uuid4()),expected_revision=revision,
            reason='Explicit correction',changes=[dict(row_id=row['id'],values=change)])
    assert imports.get(actor,batch['id'])['revision']==revision
    assert imports.samples(actor,batch['id'])['items'][0]['overrides']=={}
    engine.dispose()


def test_row_review_private_intent_concurrency_stale_and_explicit_replacement(database_url):
    from concurrent.futures import ThreadPoolExecutor
    engine,identity,actor,imports,_,batch,sample,test,_=setup(database_url)
    receive(imports,actor,batch,[sample],[test]);queued(imports,actor,batch);imports.process_next('review-concurrent')
    row=imports.samples(actor,batch['id'])['items'][0];revision=imports.get(actor,batch['id'])['revision']
    values=dict(expected_revision=revision,reason='Confirmed original note',changes=[dict(row_id=row['id'],values=dict(notes='review A'))])
    key=str(uuid4())
    with ThreadPoolExecutor(3) as pool:
        results=list(pool.map(lambda _:imports.revise(actor,batch['id'],idempotency_key=key,**values),range(3)))
    assert {r['operation']['result']['applied_revision'] for r in results}=={revision+1}
    assert len([e for e in identity.audit_events(actor) if e['action_code']=='LAB_IMPORT_REVISED'])==1
    with pytest.raises(LaboratoryError,match='import_operation_conflict'):
        imports.revise(actor,batch['id'],idempotency_key=key,**(values|dict(reason='different payload')))
    rejected=str(uuid4())
    with pytest.raises(LaboratoryError,match='import_stale_revision'):
        imports.revise(actor,batch['id'],idempotency_key=rejected,**values)
    assert imports.operation(actor,rejected)['state']=='REJECTED'
    with pytest.raises(LaboratoryError,match='import_stale_revision'):
        imports.revise(actor,batch['id'],idempotency_key=rejected,**values)
    fresh=values|dict(expected_revision=revision+1,changes=[dict(row_id=row['id'],values=dict(notes='review B'))])
    imports.revise(actor,batch['id'],idempotency_key=str(uuid4()),**fresh)
    assert imports.samples(actor,batch['id'])['items'][0]['reviewed_values']['notes']=='review B'
    engine.dispose()


@pytest.mark.parametrize('fault',['audit','rollback','committed'])
def test_row_review_commit_boundary_preserves_exact_operation_and_atomic_history(database_url,fault):
    from contextlib import contextmanager
    from dga.laboratory.public import LaboratoryImports
    from dga.shared.auth.public import AuditTrail
    engine,_,actor,original,files,batch,sample,test,_=setup(database_url)
    receive(original,actor,batch,[sample],[test]);queued(original,actor,batch);original.process_next('before-boundary')
    row=original.samples(actor,batch['id'])['items'][0];revision=original.get(actor,batch['id'])['revision']
    class Boundary:
        pending=False
        def __getattr__(self,name):return getattr(engine,name)
        @contextmanager
        def begin(self):
            armed=False
            with engine.begin() as c:
                yield c
                armed=self.pending;self.pending=False
                if armed and fault=='rollback':raise ConnectionError('Uncommitted revision')
            if armed and fault=='committed':raise ConnectionError('Unknown committed revision')
    boundary=Boundary()
    class FaultAudit(AuditTrail):
        armed=True
        def append(self,c,actor,action,**values):
            if str(action)=='LAB_IMPORT_REVISED' and self.armed:
                self.armed=False
                if fault=='audit':raise ConnectionError('Audit failed')
                boundary.pending=True
            super().append(c,actor,action,**values)
    imports=LaboratoryImports(boundary,files,audit=FaultAudit())
    key=str(uuid4());values=dict(expected_revision=revision,reason='Boundary review',changes=[dict(row_id=row['id'],values=dict(source_note='reviewed source'))])
    with pytest.raises(ConnectionError):imports.revise(actor,batch['id'],idempotency_key=key,**values)
    current=original.get(actor,batch['id'])
    assert current['revision']==revision+(fault=='committed')
    assert original.samples(actor,batch['id'])['items'][0]['reviewed_values']['source_note']==('reviewed source' if fault=='committed' else sample['source_note'])
    imports.revise(actor,batch['id'],idempotency_key=key,**values)
    assert original.get(actor,batch['id'])['revision']==revision+1
    assert len([x for x in original.revision_history(actor,batch['id'])['items'] if x['change_kind']=='ROW'])==1
    engine.dispose()


def test_row_review_supersedes_running_claim_and_history_pages_every_changed_row(database_url):
    engine,_,actor,imports,_,batch,sample,test,_=setup(database_url)
    samples=[sample|dict(external_sample_id=f'{n:05}') for n in range(21)]
    receive(imports,actor,batch,samples,[test|dict(external_sample_id='00000')]);queued(imports,actor,batch);imports.process_next('history-baseline')
    rows=imports.samples(actor,batch['id'])['items']+imports.samples(actor,batch['id'],page=2)['items']
    queued(imports,actor,batch);claim=imports.claim_validation('old-review-snapshot')
    revision=imports.get(actor,batch['id'])['revision']
    imports.revise(actor,batch['id'],idempotency_key=str(uuid4()),expected_revision=revision,reason='Review every source note',
        changes=[dict(row_id=r['id'],values=dict(source_note='review '+r['external_sample_id'])) for r in rows])
    with pytest.raises(LaboratoryError,match='stale_validation_claim'):imports.complete_validation(claim,dict(rows=[],summary={},file_issues=[],context={}))
    history=imports.revision_history(actor,batch['id'])
    entries=history['items']+imports.revision_history(actor,batch['id'],page=2)['items']
    assert {x['row_id'] for x in entries if x['change_kind']=='ROW'}=={r['id'] for r in rows}
    assert len([x for x in entries if x['change_kind']=='ROW'])==21
    assert history['total']>=22 and all('row_changes' not in x['after_value'] for x in entries)
    queued(imports,actor,batch);imports.process_next('reviewed-current')
    assert imports.get(actor,batch['id'])['validation_current']
    assert imports.samples(actor,batch['id'],page=2)['items'][0]['parsed_values']['source_note'].startswith('review ')
    engine.dispose()



def test_row_review_rejects_inactive_or_missing_rows_and_mixed_file_selection(database_url):
    engine,_,actor,imports,_,batch,sample,test,_=setup(database_url)
    originals=receive(imports,actor,batch,[sample],[test]);queued(imports,actor,batch);imports.process_next('active-review')
    row=imports.samples(actor,batch['id'])['items'][0];revision=imports.get(actor,batch['id'])['revision']
    for changes,active in [([dict(row_id=str(uuid4()),values=dict(notes='missing'))],None),
        ([dict(row_id=row['id'],values=dict(notes='one')),dict(row_id=row['id'],values=dict(notes='two'))],None),
        ([dict(row_id=row['id'],values=dict(notes='mixed'))],dict(SAMPLES=originals[0]['file']['id']))]:
        with pytest.raises(LaboratoryError):
            imports.revise(actor,batch['id'],idempotency_key=str(uuid4()),expected_revision=revision,
                reason='Invalid review target',changes=changes,active_files=active)
    new=receive(imports,actor,batch,[sample|dict(source_note='Replacement original')],[test])
    current=imports.get(actor,batch['id'])['revision']
    imports.revise(actor,batch['id'],idempotency_key=str(uuid4()),expected_revision=current,
        reason='Explicit source replacement',active_files=dict(SAMPLES=new[0]['file']['id']))
    with pytest.raises(LaboratoryError,match='import_row_not_found'):
        imports.revise(actor,batch['id'],idempotency_key=str(uuid4()),expected_revision=current+1,
            reason='Old inactive row must remain immutable',changes=[dict(row_id=row['id'],values=dict(notes='old'))])
    assert imports.original(actor,batch['id'],originals[0]['file']['id'])['content']
    engine.dispose()
