"""Immutable finalized facts through the public workbench/report seams."""
from dga.laboratory.public import LaboratoryConfiguration, LaboratoryReports, FinalizationReportPolicy
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
@pytest.mark.parametrize('operation', ['finalize', 'no_request', 'withdraw', 'retry'])
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
    if operation in ('finalize', 'no_request'):
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
        if operation in ('finalize', 'no_request'):
            bench.finalize(analyst, sample.barcode_value, report_policy=(FinalizationReportPolicy.NO_REQUEST
                           if operation == 'no_request' else FinalizationReportPolicy.QUEUE_CURRENT))
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



def test_explicit_no_request_finalizes_without_a_report_task(workbench_context):
    from dga.laboratory.public import FinalizationReportPolicy
    engine, _, actor, sample = workbench_context
    files = RecordingObjectStore()
    bench = make_workbench(engine, files)
    method = next(m for m in bench.load(actor, sample.barcode_value).methods if m.test_type.value == 'MOISTURE')
    record = bench.add_test(actor, sample.barcode_value, _moisture(method.id))
    bench.finalize(actor, sample.barcode_value, report_policy=FinalizationReportPolicy.NO_REQUEST)
    view = bench.get_current_finalization(actor, sample.barcode_value)
    assert view.state == 'AVAILABLE' and view.adopted_test_ids == (record.id,)
    reports = LaboratoryReports(engine, AuditTrail(), files)
    assert reports.get_report_by_barcode(actor, sample.barcode_value).unavailable_reason == 'report_not_requested'
    assert reports.claim_next_report('no-request', lease_seconds=30) is None
    with pytest.raises(LaboratoryError, match='report_retry_not_allowed') as error:
        reports.retry_report(actor, sample.barcode_value)
    assert error.value.status == 409
    with pytest.raises(LaboratoryError, match='report_unavailable') as error:
        reports.read_report_file(actor, sample.barcode_value)
    assert error.value.status == 409


def test_no_request_effective_facts_feed_all_three_analysis_facades(workbench_context):
    from dga.laboratory.public import FinalizationReportPolicy
    from tests.test_transformer_trends import configured_method, query
    from tests.test_device_health import health
    from tests.test_alarm_center import center
    from tests.test_health_rules import rules, command
    engine, _, actor, sample = workbench_context
    files = RecordingObjectStore()
    bench = make_workbench(engine, files)
    method = configured_method(engine, actor)
    rule = rules(engine).create(actor, command(method))
    rules(engine).activate(actor, rule['id'], 0, 'No-request public evidence')
    record = bench.add_test(actor, sample.barcode_value, _moisture(method['id'], value='20'))
    bench.finalize(actor, sample.barcode_value, report_policy=FinalizationReportPolicy.NO_REQUEST)
    points = LaboratoryTrendSource(engine).finalized_measurements(actor, sample.formal_asset_id)
    assert len(points) == 1 and points[0].test_id == record.id
    assert query(engine, actor, sample.formal_asset_id)['latest']['test_id'] == record.id
    assert health(engine).query(actor, sample.formal_asset_id)['status'] == 'WARNING'
    alarm = center(engine).query(actor)['items'][0]
    assert alarm['trigger']['measurement']['test_id'] == str(record.id)
    assert alarm['trigger_currently_finalized'] is True


@pytest.mark.parametrize('damage', ['missing', 'invalid'])
@pytest.mark.parametrize('database_url', ['0032_device_material_import'], indirect=True)
def test_qualified_bad_fact_blocks_all_consumers_beside_valid_current_data(database_url, damage):
    import copy, json
    from uuid import UUID
    from sqlalchemy import create_engine
    from alembic import command
    from alembic.config import Config
    from tests.finalization_legacy import load_case
    from tests.test_transformer_trends import query
    from tests.test_device_health import health
    from tests.test_alarm_center import center
    engine = create_engine(database_url)
    files = RecordingObjectStore()
    valid, actor = load_case(engine, 'parent_repeated_quality_ready', files)
    bad, actor = load_case(engine, 'old71_placeholder_ready', files)
    with engine.begin() as c:
        if damage == 'missing':
            c.execute(text('DELETE FROM laboratory_reports WHERE oil_sample_id=:id'), {'id': UUID(bad['sample_id'])})
        else:
            payload = copy.deepcopy(bad['report_snapshot'])
            payload['sample']['asset_snapshot']['formal_asset_id'] = []
            c.execute(text('UPDATE laboratory_reports SET report_snapshot=CAST(:payload AS jsonb) WHERE oil_sample_id=:id'),
                      {'payload': json.dumps(payload), 'id': UUID(bad['sample_id'])})
    command.upgrade(Config('alembic.ini'), 'head')
    asset = UUID('44000000-0000-0000-0000-000000000001')
    assert make_workbench(engine, files).get_current_finalization(actor, valid['barcode']).state == 'AVAILABLE'
    for read in (lambda: query(engine, actor, asset), lambda: health(engine).query(actor, asset), lambda: center(engine).query(actor)):
        with pytest.raises(LaboratoryError, match='trend_snapshot_unavailable') as error:
            read()
        assert error.value.status == 503
    reason = 'missing_finalization_facts' if damage == 'missing' else 'invalid_finalization_facts'
    assert make_workbench(engine, files).get_current_finalization(actor, bad['barcode']).unavailable_reason == reason
    status = LaboratoryReports(engine, AuditTrail(), files).get_report_by_barcode(actor, bad['barcode'])
    assert status.unavailable_reason == 'finalization_facts_unavailable' if damage == 'missing' else status.state.value == 'READY'
    engine.dispose()


def test_no_request_refinalization_has_no_current_request_and_blocks_late_worker(workbench_context):
    from dga.laboratory.public import FinalizationReportPolicy
    engine, _, actor, sample = workbench_context
    files = RecordingObjectStore()
    bench = make_workbench(engine, files)
    method = next(m for m in bench.load(actor, sample.barcode_value).methods if m.test_type.value == 'MOISTURE')
    bench.add_test(actor, sample.barcode_value, _moisture(method.id))
    bench.finalize(actor, sample.barcode_value)
    reports = LaboratoryReports(engine, AuditTrail(), files)
    old = reports.claim_next_report('old-generation', lease_seconds=30)
    before = LaboratoryTrendSource(engine).finalized_measurements(actor, sample.formal_asset_id)
    bench.withdraw_finalization(actor, sample.barcode_value, 'No-request correction')
    assert LaboratoryTrendSource(engine).finalized_measurements(actor, sample.formal_asset_id) == ()
    bench.finalize(actor, sample.barcode_value, report_policy=FinalizationReportPolicy.NO_REQUEST)
    assert reports.get_report_by_barcode(actor, sample.barcode_value).unavailable_reason == 'report_not_requested'
    current = LaboratoryTrendSource(engine).finalized_measurements(actor, sample.formal_asset_id)
    assert current[0].finalization_token != before[0].finalization_token
    assert current[0].test_id == before[0].test_id and reports.claim_next_report('no-new-task', lease_seconds=30) is None
    with pytest.raises(StaleReportClaim):
        reports.complete_report(old, object_key='obsolete.pdf', content_sha256='a'*64, byte_size=1, generated_at=old.started_at)
    bench.withdraw_finalization(actor, sample.barcode_value, 'Ordinary correction')
    bench.finalize(actor, sample.barcode_value)
    assert reports.get_report_by_barcode(actor, sample.barcode_value).state.value == 'QUEUED'


def test_ordinary_http_rejects_report_policy_and_still_autoqueues(workbench_context, database_url):
    from fastapi.testclient import TestClient
    from dga.main import create_app
    from dga.shared.config import Settings
    engine, identity, actor, sample = workbench_context
    files = RecordingObjectStore()
    bench = make_workbench(engine, files)
    method = next(m for m in bench.load(actor, sample.barcode_value).methods if m.test_type.value == 'MOISTURE')
    bench.add_test(actor, sample.barcode_value, _moisture(method.id))
    session = identity.login('workbench-admin', CHANGED_PASSWORD)
    with TestClient(create_app(Settings(database_url=database_url, cookie_secure=False), file_store=files)) as client:
        client.cookies.set('dga_session', session.token)
        headers = {'Origin': 'http://127.0.0.1:8080', 'X-CSRF-Token': session.csrf_token}
        path = f'/api/laboratory/samples/{sample.barcode_value}/finalization'
        blocked = client.post(path, headers=headers, json={'report_policy': 'NO_REQUEST'})
        assert blocked.status_code == 422
        assert bench.get_current_finalization(actor, sample.barcode_value).state == 'NOT_FINALIZED'
        assert client.post(path, headers=headers, json={}).status_code == 200
        assert LaboratoryReports(engine, AuditTrail(), files).get_report_by_barcode(actor, sample.barcode_value).state.value == 'QUEUED'


def test_no_request_keeps_identity_inventory_and_warning_guards(workbench_context):
    from dga.laboratory.public import SampleRegistry, ReceiveSample, SampleIdentityStatus
    from dga.assets.public import AssetDirectory
    engine, _, actor, sample = workbench_context
    files = RecordingObjectStore()
    bench = make_workbench(engine, files)
    with pytest.raises(LaboratoryError, match='invalid_report_policy'):
        bench.finalize(actor, sample.barcode_value, report_policy='SKIP_ALL')
    with pytest.raises(LaboratoryError, match='no_active_tests'):
        bench.finalize(actor, sample.barcode_value, report_policy=FinalizationReportPolicy.NO_REQUEST)
    pending = SampleRegistry(engine, AssetDirectory(engine), AuditTrail()).receive(actor, ReceiveSample(
        sampled_at=sample.sampled_at, received_at=sample.received_at, site_name='Unknown', equipment_serial='Unconfirmed',
        notes=None, container_count=1, identity_status=SampleIdentityStatus.IDENTITY_PENDING))
    with pytest.raises(LaboratoryError, match='sample_identity_not_confirmed'):
        bench.finalize(actor, pending.barcode_value, report_policy=FinalizationReportPolicy.NO_REQUEST)
    method = LaboratoryConfiguration(engine).create_method(actor, method_input(qa_checks=[dict(code='CHECK', label='Explicit QC')]))
    first = bench.add_test(actor, sample.barcode_value, _moisture(method['id'], value='8.50'))
    bench.add_test(actor, sample.barcode_value, _moisture(method['id'], value='9'))
    with pytest.raises(LaboratoryError, match='report_result_selection_required'):
        bench.finalize(actor, sample.barcode_value, report_policy=FinalizationReportPolicy.NO_REQUEST)
    bench.select_report_result(actor, sample.barcode_value, first.id)
    with pytest.raises(LaboratoryError, match='warnings_not_acknowledged'):
        bench.finalize(actor, sample.barcode_value, report_policy=FinalizationReportPolicy.NO_REQUEST)
    warnings = bench.load(actor, sample.barcode_value).finalization_assessment.warning_codes
    bench.finalize(actor, sample.barcode_value, warnings, report_policy=FinalizationReportPolicy.NO_REQUEST)
    assert bench.get_current_finalization(actor, sample.barcode_value).acknowledged_warning_codes == tuple(sorted(warnings))
    with pytest.raises(LaboratoryError, match='sample_already_finalized'):
        bench.finalize(actor, sample.barcode_value, warnings, report_policy=FinalizationReportPolicy.NO_REQUEST)


@pytest.mark.parametrize('fault', ['event', 'audit'])
def test_no_request_late_write_failure_rolls_back_whole_finalization(workbench_context, fault):
    engine, _, actor, sample = workbench_context
    files = RecordingObjectStore()
    bench = make_workbench(engine, files)
    method = next(m for m in bench.load(actor, sample.barcode_value).methods if m.test_type.value == 'MOISTURE')
    record = bench.add_test(actor, sample.barcode_value, _moisture(method.id))
    def fail_late(connection, cursor, statement, parameters, context, executemany):
        target = 'laboratory_finalization_events' if fault == 'event' else 'audit_logs'
        if statement.lstrip().startswith('INSERT INTO ' + target):
            if fault == 'event' or parameters.get('action') == 'LAB_TESTING_FINALIZATION_ATTEMPT':
                raise psycopg.OperationalError('isolated no-request late fault')
    event.listen(engine, 'before_cursor_execute', fail_late)
    try:
        with pytest.raises(psycopg.OperationalError, match='isolated no-request'):
            bench.finalize(actor, sample.barcode_value, report_policy=FinalizationReportPolicy.NO_REQUEST)
    finally:
        event.remove(engine, 'before_cursor_execute', fail_late)
    loaded = bench.load(actor, sample.barcode_value)
    assert loaded.testing_status.value == 'OPEN' and loaded.finalization_history == ()
    assert not loaded.tests[0].selected_for_report and loaded.tests[0].id == record.id
    assert bench.get_current_finalization(actor, sample.barcode_value).state == 'NOT_FINALIZED'
    assert LaboratoryTrendSource(engine).finalized_measurements(actor, sample.formal_asset_id) == ()
    assert LaboratoryReports(engine, AuditTrail(), files).claim_next_report('rollback', lease_seconds=30) is None
    bench.finalize(actor, sample.barcode_value, report_policy=FinalizationReportPolicy.NO_REQUEST)
    assert bench.get_current_finalization(actor, sample.barcode_value).state == 'AVAILABLE'


@pytest.mark.parametrize('delivery', ['queued', 'generating', 'failed', 'missing_file', 'deleted_request'])
def test_delivery_state_or_absence_never_erases_valid_facts(workbench_context, delivery):
    from dga.laboratory.report_worker import ReportWorker
    engine, _, actor, sample = workbench_context
    files = RecordingObjectStore()
    bench = make_workbench(engine, files)
    method = next(m for m in bench.load(actor, sample.barcode_value).methods if m.test_type.value == 'MOISTURE')
    bench.add_test(actor, sample.barcode_value, _moisture(method.id))
    bench.finalize(actor, sample.barcode_value)
    reports = LaboratoryReports(engine, AuditTrail(), files)
    before = LaboratoryTrendSource(engine).finalized_measurements(actor, sample.formal_asset_id)
    if delivery in ('generating', 'failed'):
        claim = reports.claim_next_report('delivery', lease_seconds=30)
        if delivery == 'failed': reports.fail_report(claim, 'isolated_failure')
    elif delivery == 'missing_file':
        assert ReportWorker(reports, files).process_one('delivery-file')
        files.objects.clear()
        from dga.shared.files import ObjectStorageError
        with pytest.raises(ObjectStorageError): reports.read_report_file(actor, sample.barcode_value)
    elif delivery == 'deleted_request':
        with engine.begin() as c:
            c.execute(text('DELETE FROM laboratory_reports WHERE oil_sample_id=:id'), {'id': sample.id})
        assert reports.get_report_by_barcode(actor, sample.barcode_value).unavailable_reason == 'report_not_requested'
    assert LaboratoryTrendSource(engine).finalized_measurements(actor, sample.formal_asset_id) == before


def test_unsupported_date_metadata_is_unavailable_without_inventing_instant_semantics(workbench_context):
    import json
    engine, _, actor, sample = workbench_context
    files = RecordingObjectStore()
    bench = make_workbench(engine, files)
    method = next(m for m in bench.load(actor, sample.barcode_value).methods if m.test_type.value == 'MOISTURE')
    bench.add_test(actor, sample.barcode_value, _moisture(method.id))
    def corrupt_metadata(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith('INSERT INTO laboratory_finalization_facts'):
            payload = json.loads(parameters['payload'])
            payload['read_metadata']['sampled_at_precision'] = 'DATE'
            parameters = parameters | {'payload': json.dumps(payload)}
        return statement, parameters
    event.listen(engine, 'before_cursor_execute', corrupt_metadata, retval=True)
    try:
        bench.finalize(actor, sample.barcode_value, report_policy=FinalizationReportPolicy.NO_REQUEST)
    finally:
        event.remove(engine, 'before_cursor_execute', corrupt_metadata)
    assert bench.get_current_finalization(actor, sample.barcode_value).unavailable_reason == 'invalid_finalization_facts'
    with pytest.raises(LaboratoryError, match='trend_snapshot_unavailable'):
        LaboratoryTrendSource(engine).finalized_measurements(actor, sample.formal_asset_id)


def test_concurrent_policy_finalization_has_one_current_token(workbench_context):
    from concurrent.futures import ThreadPoolExecutor
    engine, _, actor, sample = workbench_context
    bench = make_workbench(engine, RecordingObjectStore())
    method = next(m for m in bench.load(actor, sample.barcode_value).methods if m.test_type.value == 'MOISTURE')
    bench.add_test(actor, sample.barcode_value, _moisture(method.id))
    def finalize(policy):
        try:
            bench.finalize(actor, sample.barcode_value, report_policy=policy)
            return 'FINALIZED'
        except LaboratoryError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(finalize, (FinalizationReportPolicy.QUEUE_CURRENT, FinalizationReportPolicy.NO_REQUEST)))
    assert sorted(outcomes) == ['FINALIZED', 'sample_already_finalized']
    view = bench.get_current_finalization(actor, sample.barcode_value)
    points = LaboratoryTrendSource(engine).finalized_measurements(actor, sample.formal_asset_id)
    assert len(points) == 1 and points[0].finalization_token == view.token


def test_report_completion_serializes_with_withdrawal_and_cannot_resurrect_current_facts(workbench_context):
    from concurrent.futures import ThreadPoolExecutor, TimeoutError
    from threading import Event
    engine, _, actor, sample = workbench_context
    files = RecordingObjectStore()
    bench = make_workbench(engine, files)
    method = next(m for m in bench.load(actor, sample.barcode_value).methods if m.test_type.value == 'MOISTURE')
    bench.add_test(actor, sample.barcode_value, _moisture(method.id))
    bench.finalize(actor, sample.barcode_value)
    reports = LaboratoryReports(engine, AuditTrail(), files)
    claim = reports.claim_next_report('completion-race', lease_seconds=30)
    locked, release = Event(), Event()
    def pause_complete(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith("UPDATE laboratory_reports SET state='READY'"):
            locked.set()
            assert release.wait(5)
    event.listen(engine, 'before_cursor_execute', pause_complete)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            complete = pool.submit(reports.complete_report, claim, object_key='race.pdf', content_sha256='a'*64,
                                   byte_size=1, generated_at=claim.started_at)
            assert locked.wait(5)
            withdraw = pool.submit(bench.withdraw_finalization, actor, sample.barcode_value, 'Concurrent correction')
            try:
                with pytest.raises(TimeoutError): withdraw.result(timeout=.2)
            finally:
                release.set()
            complete.result(timeout=5)
            withdraw.result(timeout=5)
    finally:
        release.set()
        event.remove(engine, 'before_cursor_execute', pause_complete)
    assert bench.get_current_finalization(actor, sample.barcode_value).state == 'NOT_FINALIZED'
    assert LaboratoryTrendSource(engine).finalized_measurements(actor, sample.formal_asset_id) == ()
    with pytest.raises(LaboratoryError, match='report_unavailable'):
        reports.read_report_file(actor, sample.barcode_value)
    with pytest.raises(StaleReportClaim):
        reports.complete_report(claim, object_key='late.pdf', content_sha256='b'*64, byte_size=1, generated_at=claim.started_at)
