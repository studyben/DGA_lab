# Issue #7 — overall testing finalization, withdrawal, and report-result selection

## Baseline and boundary

Branch `codex/issue-7-finalization` starts from `origin/codex/issue-6-test-entry` at `d4528f1`. Issue #6 already owns barcode workbench loading, editable sample basics, typed DGA/moisture/breakdown-voltage records, attachment storage, and the `OPEN`/`FINALIZED` status enum. Issue #7 extends only the public laboratory application seam. Asset management remains the source of official asset identity; condition analysis and report/PDF generation remain consumers in later tickets.

The public implementation entry remains `dga.laboratory.public`. HTTP and React are adapters. Tests call public laboratory commands with the real PostgreSQL test database; they do not assert internal table layout except migration/constraint verification where the database invariant itself is the behavior under test.

## Domain behavior and contracts

### State machine

- `OPEN` (“检测中”): sample basics, active tests, and report-result selections are editable under their existing permissions.
- `OPEN -> FINALIZED`: requires `laboratory.finalize`, locks the sample row, validates the current database state, completes sole-result selections atomically, records finalizer/time and audit, then returns the refreshed workbench.
- `FINALIZED`: every scientific-record mutation command (sample basics, test creation/update/removal and attachment changes through those test commands), plus report selection, rejects with stable `sample_finalized` conflict behavior. Operational barcode label printing remains allowed because it does not alter the finalized report dataset. Repeated finalization rejects with `sample_already_finalized`; it is not silently idempotent.
- `FINALIZED -> OPEN`: requires `laboratory.finalize` and a trimmed 1–500 character reason, locks the sample row, records a durable laboratory finalization event and audit, clears current finalizer/time, and restores editability. Withdrawal of an open sample rejects with `sample_not_finalized`.

### Report-result selection

- Add `selected_for_report` to the public `TestRecord`; it is meaningful only for active tests.
- `select_report_result(actor, barcode, test_id)` requires `laboratory.write`, locks the owning sample before checking editability, verifies that the target is an active test belonging to that barcode, clears the former selection for that sample and test type, selects the target, and audits only a real change.
- At most one active test per `(oil_sample_id, test_type)` may be selected. PostgreSQL enforces this with a partial unique index; sample-row locking provides deterministic application behavior under concurrent selection/finalization.
- Updating a selected test without changing its test type preserves selection. Changing its type clears selection before applying the new type. Removing a selected test naturally removes it from the partial invariant and leaves that type unselected until another result is selected or a sole result is auto-selected at finalization.
- Finalization groups active tests by type. Zero active tests is `no_active_tests`. One active result is selected automatically. More than one requires exactly one current selection; otherwise raise `report_result_selection_required` with the public error detail `{ "test_types": ["DGA", ...] }`. No averaging or repetition grouping is introduced.

### Identity, validity, and warnings

- `IDENTITY_PENDING` blocks finalization with `sample_identity_not_confirmed`.
- An “active valid test” is a test already accepted by Issue #6 typed-result and method validation and still marked active. Issue #7 does not reimplement ASTM or QA/QC validity rules.
- A finalization assessment returned with the workbench exposes readiness, blocking codes/test types, and warning codes. A laboratory-owned `FinalizationWarningSource` callable is passed to `LaboratoryWorkbench`; it receives immutable candidate `TestRecord` values and returns stable warning-code strings. It is evaluated only after the sample row is locked. The production default returns no warnings, does not import condition analysis, and contains no formal rules. The finalize request accepts acknowledged warning codes so later warnings can require an explicit confirmation without changing finalization semantics. Missing acknowledgements for warning codes present in the locked assessment reject with `warnings_not_acknowledged`; extra acknowledgements are ignored as stale client input.

## Persistence, audit, and concurrency

Alembic `0006` will add:

- `laboratory_tests.selected_for_report BOOLEAN NOT NULL DEFAULT FALSE` and its partial unique index for active selected results;
- nullable `oil_samples.testing_finalized_by` and `testing_finalized_at`, with a check requiring both or neither;
- laboratory-owned `laboratory_finalization_events` containing sample, `FINALIZED`/`WITHDRAWN`, actor, timestamp, and nullable withdrawal reason. This keeps the required reason/history without widening the shared audit schema.

Application mutations already acquire `SELECT ... FOR UPDATE` on the sample through `_editable_sample`. Selection, finalization, and withdrawal will use the same row-lock order, so no test/result write can commit between final validation and state transition. Finalization records automatic selections, status, event, and audit in one transaction. Withdrawal records status, event, and audit in one transaction.

Failed finalization validation must survive the rolled-back command transaction. Extend the shared `AuditTrail` only with a generic explicit outcome (`SUCCESS` default, `FAILURE` allowed), retaining the same append-only storage and no laboratory semantics. The command catches only typed domain validation failures after a sample has been resolved, then opens a short separate transaction to append the neutral `LAB_TESTING_FINALIZATION_ATTEMPT` action with `result='FAILURE'` against the sample before re-raising. Permission denial, malformed barcode, and sample-not-found are not represented as business validation attempts and are not given a misleading sample audit event. Successful finalization records the same action with `SUCCESS`; withdrawal and selection keep distinct success action codes.

`LaboratoryError` gains an optional, JSON-safe details mapping while preserving the existing constructor/default response. The HTTP handler returns `{ "code": ... }` for current errors and adds `"details"` only when present. Issue #7 uses only the allowlisted `{ "test_types": [...] }` and `{ "warning_codes": [...] }` detail shapes; no exception strings or database values are serialized.

Migration upgrade must preserve all existing Issue #6 samples as `OPEN`, with no selection or finalizer. Downgrade removes only Issue #7 structures. Because no production data exists, no historical-finalized backfill is required.

## HTTP and UI adapter

Add laboratory-owned endpoints:

- `PUT /api/laboratory/samples/{barcode}/report-result` with `{ "test_id": UUID }`;
- `POST /api/laboratory/samples/{barcode}/finalization` with `{ "acknowledged_warning_codes": string[] }`;
- `POST /api/laboratory/samples/{barcode}/finalization-withdrawals` with `{ "reason": string }`.

The workbench response includes each result's selection state, finalizer/time, and current assessment. HTTP maps stable domain errors and their optional sanitized details through the laboratory error handler; server authorization remains authoritative.

In the React workbench:

- group/label records by test type while retaining the current cards;
- show a single-choice “设为报告结果” control when a type has multiple results, and a selected badge for the current result;
- show readiness blockers next to the overall “定稿” action and translate missing type codes to DGA/微水/击穿电压;
- on finalization, refresh from the server and render all basics, record actions, selection controls, and creation controls read-only;
- show “撤回定稿” only when `useAuth().can('laboratory.finalize')`; collect a mandatory reason, submit it, and restore editing after refresh;
- do not add report generation, report version text, formal QA warnings, or per-record finalization.

## TDD implementation slices

### S1 — persisted selection through the public laboratory seam

Start with failing PostgreSQL integration tests for selecting one of two same-type results, replacing a prior selection, cross-sample/removed-test rejection, selection permission, selected-type change/removal behavior, concurrent selections, and label-print recording remaining available after finalization. Implement migration `0006`, public record/assessment shape, and the smallest selection command. Run Alembic upgrade/downgrade/upgrade and focused backend tests. Deep-review this slice, fix all accepted findings, re-review, document evidence, and commit.

### S2 — atomic finalization and withdrawal

Start with failing public-interface tests for pending identity, no tests, sole-result auto-selection, multiple-result missing selection with typed error details, successful lock, all Issue #6 scientific-data mutation commands rejected after finalization, selection rejected after finalization, reason-required/permission-controlled withdrawal, edit-after-withdraw/re-finalize, durable events/audits with truthful SUCCESS/FAILURE results, and two concurrent finalizers. Inject a fake `FinalizationWarningSource` to prove locked evaluation and acknowledgement behavior without creating QA rules. Add a focused HTTP test for structured details. Implement finalization/withdrawal commands and HTTP endpoints. Deep-review, fix/re-review, document evidence, and commit.

### S3 — operator workbench acceptance and delivery evidence

Start with a failing Playwright scenario that creates/loads two DGA results, cannot finalize until one is selected, finalizes, observes read-only controls, withdraws with a reason, edits, and can finalize again. Add a focused unauthorized-user UI/API assertion. Implement the minimal workbench controls and styling; retain the confirmed 1K 16:9 desktop layout. Run frontend typecheck/build, full backend PostgreSQL suite, full Playwright suite, and migration cycle. Deep-review this slice, fix/re-review, document evidence, and commit.

## Review, completion, and publication gates

Before implementation, run adversarial plan review over state transitions, transaction ordering, audit durability, permissions, migration safety, public contracts, scope, and tests; repair accepted findings and commit the accepted plan. After every slice run `deepreview` against its fixed parent. After all slices run aggregate `deepreview` against `d4528f1` and repair/re-review until pass.

Ready-to-open-draft-PR requires the intended diff only, all accepted commits, passing focused/full tests, a clean worktree, and updated work-unit evidence. Because this is a stacked work unit, the draft PR base is `codex/issue-6-test-entry` until PR #26 merges; it must not be merged first. Publishing the branch/draft PR and posting the Issue #7 closeout comment require explicit user authorization. Do not merge, close Issue #7, or begin Issue #8/#13/#14.

## Residual risks and ownership

- Formal QA/QC warnings, ASTM thresholds, calibration, and configurable validation remain Issue #14; Issue #7 only preserves the confirmation contract.
- Report availability/PDF generation and the effect of withdrawal on stored report artifacts belong to the report ticket; Issue #7 exposes authoritative state and selection only.
- Condition-analysis consumption of finalized selected results belongs to its ticket and must use the laboratory public seam, not laboratory tables.
- Retarget/rebase of this stacked branch after PR #26 merges is publication hygiene, not Issue #7 behavior.
