from datetime import datetime, timezone
import pytest
from dga.condition_analysis.public import HealthRules, HealthRuleInput, HealthError
from dga.assets.public import AssetDirectory
from dga.laboratory.public import LaboratoryConfiguration
from tests.test_transformer_trends import configured_method
from tests.test_laboratory_workbench import workbench_context

NOW = datetime(2026, 9, 13, tzinfo=timezone.utc)


def rules(engine):
    return HealthRules(engine, LaboratoryConfiguration(engine), AssetDirectory(engine), clock=lambda: NOW)


def command(method, **changes):
    return HealthRuleInput(**(dict(name='Synthetic test policy', test_type='MOISTURE', analyte='MOISTURE',
        method_version_id=method['id'], unit='TEST-UNIT', effective_from='2026-01-01T00:00:00Z',
        priority=10, operator='GT', threshold='10', severity='WARNING') | changes))


def test_create_draft_is_retrievable_with_explicit_configuration(workbench_context):
    engine, _, actor, _ = workbench_context
    method = configured_method(engine, actor)
    saved = rules(engine).create(actor, command(method))
    assert saved['state'] == 'DRAFT'
    assert saved['revision'] == 0
    assert rules(engine).get(actor, saved['id'])['name'] == 'Synthetic test policy'
    assert rules(engine).history(actor, saved['id'])[0]['action'] == 'CREATED'


def test_approve_locks_content_retire_and_copy_preserve_evidence(workbench_context):
    engine, _, actor, _ = workbench_context
    method = configured_method(engine, actor)
    service = rules(engine)
    draft = service.create(actor, command(method))
    edited = service.update(actor, draft['id'], command(method, name='Reviewed'), 0)
    active = service.activate(actor, draft['id'], edited['revision'], 'Reviewed synthetic policy')
    assert active['approved_by'] == actor.user_id
    with pytest.raises(HealthError, match='rule_not_draft'):
        service.update(actor, draft['id'], command(method), active['revision'])
    copied = service.copy(actor, draft['id'])
    assert copied['state'] == 'DRAFT' and copied['id'] != draft['id']
    retired = service.retire(actor, draft['id'], active['revision'], 'Retire synthetic policy')
    assert retired['state'] == 'RETIRED'
    assert {e['action'] for e in service.history(actor, draft['id'])} == {'CREATED','UPDATED','ACTIVATED','RETIRED'}
    assert service.history(actor, draft['id'])[0]['after_value']['name'] == 'Synthetic test policy'


def test_concurrent_activation_rejects_same_priority_overlapping_scope(workbench_context):
    from concurrent.futures import ThreadPoolExecutor
    engine, _, actor, sample = workbench_context
    method = configured_method(engine, actor)
    service = rules(engine)
    drafts = [service.create(actor, command(method)), service.create(actor, command(method, asset_id=sample.formal_asset_id))]
    def activate(draft):
        try:
            service.activate(actor, draft['id'], 0, 'test approval')
            return 'ACTIVE'
        except HealthError as e:
            return e.code
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(activate, drafts)) == ['ACTIVE', 'rule_scope_conflict']


def test_revision_reason_and_method_validation(workbench_context):
    engine, _, actor, _ = workbench_context
    method = configured_method(engine, actor)
    service = rules(engine)
    draft = service.create(actor, command(method))
    with pytest.raises(HealthError, match='rule_revision_conflict'):
        service.update(actor, draft['id'], command(method), 9)
    with pytest.raises(HealthError, match='rule_reason_required'):
        service.activate(actor, draft['id'], 0, ' ')
    with pytest.raises(HealthError, match='rule_method_unit_mismatch'):
        service.create(actor, command(method, unit='other'))
    assert service.get(actor, draft['id'])['state'] == 'DRAFT'
    assert len(service.history(actor, draft['id'])) == 1


def test_adjacent_periods_and_different_priorities_can_activate(workbench_context):
    engine, _, actor, _ = workbench_context
    method = configured_method(engine, actor)
    service = rules(engine)
    for overrides in [dict(effective_to='2026-06-01T00:00:00Z'),
                      dict(effective_from='2026-06-01T00:00:00Z'), dict(priority=11)]:
        draft = service.create(actor, command(method, **overrides))
        assert service.activate(actor, draft['id'], 0, 'test')['state'] == 'ACTIVE'


@pytest.mark.parametrize('changes', [dict(priority=True), dict(threshold='NaN'),
    dict(threshold='-1'), dict(threshold='0.0000001'), dict(effective_from='2026-01-01'),
    dict(effective_to='2025-01-01T00:00:00Z')])
def test_invalid_rule_shape_is_rejected(changes):
    from pydantic import ValidationError
    from uuid import uuid4
    with pytest.raises(ValidationError):
        command({'id': uuid4()}, **changes)


def test_read_only_actor_cannot_change_rules(workbench_context):
    from dataclasses import replace
    from dga.shared.auth.public import IdentityError
    engine, _, actor, _ = workbench_context
    method = configured_method(engine, actor)
    reader = replace(actor, permissions=frozenset({'analysis.read'}))
    assert rules(engine).methods(reader)
    with pytest.raises(IdentityError):
        rules(engine).create(reader, command(method))


@pytest.mark.parametrize('revision', [True, False, -1, '0'])
def test_revision_must_be_nonnegative_integer(workbench_context, revision):
    engine, _, actor, _ = workbench_context
    method = configured_method(engine, actor)
    service = rules(engine)
    draft = service.create(actor, command(method))
    with pytest.raises(HealthError, match='invalid_rule_revision'):
        service.activate(actor, draft['id'], revision, 'test')


def test_placeholder_rejected_but_inactive_configured_method_allowed(workbench_context):
    engine, _, actor, _ = workbench_context
    service = rules(engine)
    placeholder = next(m for m in service.methods(actor) if m['test_type']=='MOISTURE' and not m['configured'])
    with pytest.raises(HealthError, match='rule_method_not_configured'):
        service.create(actor, command(placeholder))
    method = configured_method(engine, actor)
    LaboratoryConfiguration(engine).set_method_active(actor, method['id'], False)
    draft = service.create(actor, command(method))
    assert service.activate(actor, draft['id'], 0, 'historical method')['state']=='ACTIVE'
