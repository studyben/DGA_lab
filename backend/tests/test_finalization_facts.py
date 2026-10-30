"""Immutable finalized facts through the public workbench/report seams."""
from dga.laboratory.public import LaboratoryConfiguration, LaboratoryReports
from dga.shared.auth.public import AuditTrail
from tests.test_laboratory_configuration import method_input
from tests.test_laboratory_workbench import workbench_context, make_workbench, RecordingObjectStore, _moisture


def test_current_fact_freezes_complete_inventory_and_adopted_report(workbench_context):
    engine, _, actor, sample = workbench_context
    store = RecordingObjectStore()
    bench = make_workbench(engine, store)
    assert bench.get_current_finalization(actor, sample.barcode_value).state == 'NOT_FINALIZED'
    method = LaboratoryConfiguration(engine).create_method(actor, method_input(
        qa_checks=[dict(code='BLANK', label='Isolated evidence check')]))
    adopted = bench.add_test(actor, sample.barcode_value, _moisture(method['id'], value='8.50'))
    unselected = bench.add_test(actor, sample.barcode_value, _moisture(method['id'], value='9.50'))
    bench.select_report_result(actor, sample.barcode_value, adopted.id)
    warnings = bench.load(actor, sample.barcode_value).finalization_assessment.warning_codes
    assert warnings
    bench.finalize(actor, sample.barcode_value, warnings)
    view = bench.get_current_finalization(actor, sample.barcode_value)
    assert view.state == 'AVAILABLE' and view.schema_version == 2
    assert view.inventory_complete is True
    assert set(view.active_test_ids) == {adopted.id, unselected.id}
    assert view.adopted_test_ids == (adopted.id,)
    assert set(view.acknowledged_warning_codes) == set(warnings)
    claim = LaboratoryReports(engine, AuditTrail(), store).claim_next_report('fact-proof', lease_seconds=30)
    assert claim.finalization_token == view.token
    assert [r['test_id'] for r in claim.snapshot['selected_results']] == [str(adopted.id)]
    assert claim.snapshot['selected_results'][0]['result']['result']['value'] == '8.500000'
    assert claim.snapshot['acknowledged_warning_codes'] == sorted(warnings)



import pytest
import psycopg
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError
from dga.laboratory.public import LaboratoryError, LaboratoryTrendSource, StaleReportClaim
from dga.shared.auth.public import IdentityError
from tests.identity_seed import seed_legacy_user
from tests.test_laboratory_workbench import INITIAL_PASSWORD, CHANGED_PASSWORD


@pytest.mark.parametrize('fault', ['queue', 'last_audit', 'fact_database'])
def test_late_failure_rolls_back_facts_selection_request_and_event(workbench_context, fault):
    engine, _, actor, sample = workbench_context
    store = RecordingObjectStore()
    reports = LaboratoryReports(engine, AuditTrail(), store)
    class FailureAudit(AuditTrail):
        def append(self, connection, actor, action, **kwargs):
            if fault == 'last_audit' and action.value == 'LAB_TESTING_FINALIZATION_ATTEMPT':
                raise RuntimeError('isolated last audit failure')
            return super().append(connection, actor, action, **kwargs)
    class Queue:
        def queue_current(self, *args):
            reports.queue_current(*args)
            if fault == 'queue':
                raise RuntimeError('isolated queue failure after write')
        def invalidate_current(self, *args):
            return reports.invalidate_current(*args)
    bench = make_workbench(engine, store, report_lifecycle=Queue(), audit=FailureAudit())
    method = next(m for m in bench.load(actor, sample.barcode_value).methods if m.test_type.value == 'MOISTURE')
    record = bench.add_test(actor, sample.barcode_value, _moisture(method.id))
    def fail_fact(connection, cursor, statement, parameters, context, executemany):
        if fault == 'fact_database' and statement.lstrip().startswith('INSERT INTO laboratory_finalization_facts'):
            raise psycopg.OperationalError('isolated fact database failure')
    event.listen(engine, 'before_cursor_execute', fail_fact)
    try:
        with pytest.raises((RuntimeError, psycopg.OperationalError), match='isolated'):
            bench.finalize(actor, sample.barcode_value)
    finally:
        event.remove(engine, 'before_cursor_execute', fail_fact)
    loaded = bench.load(actor, sample.barcode_value)
    assert loaded.testing_status.value == 'OPEN'
    assert not loaded.tests[0].selected_for_report and loaded.tests[0].id == record.id
    assert loaded.finalization_history == ()
    assert bench.get_current_finalization(actor, sample.barcode_value).state == 'NOT_FINALIZED'
    assert reports.claim_next_report('after-rollback', lease_seconds=30) is None
    assert LaboratoryTrendSource(engine).finalized_measurements(actor, sample.formal_asset_id) == ()
    with pytest.raises(LaboratoryError, match='report_unavailable'):
        reports.read_report_file(actor, sample.barcode_value)


def test_withdrawal_retains_immutable_old_token_and_rejects_old_worker(workbench_context):
    engine, _, actor, sample = workbench_context
    store = RecordingObjectStore()
    bench = make_workbench(engine, store)
    method = next(m for m in bench.load(actor, sample.barcode_value).methods if m.test_type.value == 'MOISTURE')
    bench.add_test(actor, sample.barcode_value, _moisture(method.id))
    bench.finalize(actor, sample.barcode_value)
    first = bench.get_current_finalization(actor, sample.barcode_value)
    reports = LaboratoryReports(engine, AuditTrail(), store)
    claim = reports.claim_next_report('old-worker', lease_seconds=30)
    bench.withdraw_finalization(actor, sample.barcode_value, 'Isolated correction')
    assert bench.get_current_finalization(actor, sample.barcode_value).state == 'NOT_FINALIZED'
    assert LaboratoryTrendSource(engine).finalized_measurements(actor, sample.formal_asset_id) == ()
    bench.finalize(actor, sample.barcode_value)
    second = bench.get_current_finalization(actor, sample.barcode_value)
    assert second.token != first.token and second.adopted_test_ids == first.adopted_test_ids
    with pytest.raises(StaleReportClaim):
        reports.complete_report(claim, object_key='stale.pdf', content_sha256='a'*64, byte_size=1,
                                generated_at=claim.started_at)
    # Constraint fault at owner DB seam; public view remains the success assertion.
    for mutation in ('UPDATE laboratory_finalization_facts SET fact_snapshot=fact_snapshot',
                     'DELETE FROM laboratory_finalization_facts'):
        with pytest.raises(DBAPIError, match='facts are immutable'):
            with engine.begin() as c:
                c.execute(text(mutation+' WHERE oil_sample_id=:sample AND finalization_token=:token'),
                          {'sample': sample.id, 'token': first.token})
        assert bench.get_current_finalization(actor, sample.barcode_value) == second


@pytest.mark.parametrize('change', ['revoke', 'disable'])
@pytest.mark.parametrize('operation', ['finalize', 'withdraw', 'retry'])
def test_stale_actor_cannot_finalize_after_current_permission_changes(workbench_context, database_url, change, operation):
    engine, identity, admin, sample = workbench_context
    member = seed_legacy_user(database_url, 'fact-analyst', 'Fact analyst', INITIAL_PASSWORD, ['analyst'])
    login = identity.login('fact-analyst', INITIAL_PASSWORD)
    analyst = identity.change_password(login.token, INITIAL_PASSWORD, CHANGED_PASSWORD).actor
    assert 'laboratory.finalize' in analyst.permissions  # Preserve integrated #18 grant.
    bench = make_workbench(engine, RecordingObjectStore())
    method = next(m for m in bench.load(admin, sample.barcode_value).methods if m.test_type.value == 'MOISTURE')
    bench.add_test(analyst, sample.barcode_value, _moisture(method.id))
    bench.finalize(analyst, sample.barcode_value)
    reports = LaboratoryReports(engine, AuditTrail(), RecordingObjectStore())
    if operation == 'finalize':
        bench.withdraw_finalization(admin, sample.barcode_value, 'Isolated current-auth check')
    elif operation == 'retry':
        claim = reports.claim_next_report('auth-retry', lease_seconds=30)
        reports.fail_report(claim, 'isolated_auth_retry')
    before = bench.get_current_finalization(admin, sample.barcode_value)
    if change == 'revoke':
        current = identity.user_detail(admin, member)
        identity.change_roles(admin, member, add=['field_engineer'], remove=['analyst'],
                              expected_revision=current['revision'])
    else:
        identity.set_status(admin, member, 'DISABLED')
    with pytest.raises(IdentityError, match='permission_denied'):
        if operation == 'finalize':
            bench.finalize(analyst, sample.barcode_value)
        elif operation == 'withdraw':
            bench.withdraw_finalization(analyst, sample.barcode_value, 'Stale authorization')
        else:
            reports.retry_report(analyst, sample.barcode_value)
    assert bench.get_current_finalization(admin, sample.barcode_value) == before


def test_report_copy_uses_already_captured_facts_not_live_tests(workbench_context):
    engine, _, actor, sample = workbench_context
    files = RecordingObjectStore()
    reports = LaboratoryReports(engine, AuditTrail(), files)
    class AdversarialQueue:
        def queue_current(self, connection, *args):
            connection.execute(text("UPDATE oil_samples SET notes='Changed after capture' WHERE id=:id"), {'id': sample.id})
            connection.execute(text("""UPDATE moisture_test_results SET result_value=99
                WHERE test_id IN (SELECT id FROM laboratory_tests WHERE oil_sample_id=:id)"""), {'id': sample.id})
            reports.queue_current(connection, *args)
        def invalidate_current(self, *args):
            return reports.invalidate_current(*args)
    bench = make_workbench(engine, files, report_lifecycle=AdversarialQueue())
    method = next(m for m in bench.load(actor, sample.barcode_value).methods if m.test_type.value == 'MOISTURE')
    bench.add_test(actor, sample.barcode_value, _moisture(method.id))
    bench.finalize(actor, sample.barcode_value)
    claim = reports.claim_next_report('frozen-projection', lease_seconds=30)
    assert claim.snapshot['sample']['notes'] == 'annual sample'
    assert claim.snapshot['selected_results'][0]['result']['result']['value'] == '8.500000'




def test_current_view_is_coherent_with_concurrent_withdrawal(workbench_context):
    from concurrent.futures import ThreadPoolExecutor, TimeoutError
    from threading import Event
    engine, _, actor, sample = workbench_context
    bench = make_workbench(engine, RecordingObjectStore())
    method = next(m for m in bench.load(actor, sample.barcode_value).methods if m.test_type.value == 'MOISTURE')
    bench.add_test(actor, sample.barcode_value, _moisture(method.id))
    bench.finalize(actor, sample.barcode_value)
    entered, release = Event(), Event()
    def pause_fact_read(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith('SELECT * FROM laboratory_finalization_facts'):
            entered.set()
            assert release.wait(5)
    event.listen(engine, 'before_cursor_execute', pause_fact_read)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            view = pool.submit(bench.get_current_finalization, actor, sample.barcode_value)
            assert entered.wait(2)
            withdrawal = pool.submit(bench.withdraw_finalization, actor, sample.barcode_value, 'Concurrent fact view')
            try:
                with pytest.raises(TimeoutError):
                    withdrawal.result(timeout=0.3)
            finally:
                release.set()
            assert view.result(timeout=3).state == 'AVAILABLE'
            assert withdrawal.result(timeout=3).testing_status.value == 'OPEN'
    finally:
        release.set()
        event.remove(engine, 'before_cursor_execute', pause_fact_read)
    assert bench.get_current_finalization(actor, sample.barcode_value).state == 'NOT_FINALIZED'

