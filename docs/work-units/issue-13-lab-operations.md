# Issue #13 — 实验室运营视图

## Confirmed goal and isolation

User confirmed a branch and isolated worktree from latest main, preserving existing changes and port 18093 acceptance data. Branch `codex/issue-13-lab-operations`, base `62f26a4a9b597a7a9182f12e3f7f5711897d75fd`.

Scope: four laboratory home metrics using America/Chicago business dates, filtered/sorted/paginated sample ledger, audited pending-identity association without rebuilding sample/barcode, controlled container state changes, and navigation to the existing barcode workbench. Tests at laboratory public interfaces with real isolated PostgreSQL plus key browser acceptance. No later Issues, push or merge authorized for this work unit.

## Current gate: preflight dependency blocker

Issue #13 explicitly says Blocked by #7. Live GitHub and source inspection found the dependency is not integrated into main:

- PR #26 (Issue #6) merged into main on 2026-09-10 at 17:54:04 UTC.
- PR #27 (Issue #7) subsequently merged into `codex/issue-6-test-entry`, not main, on 2026-09-10 at 23:15:46 UTC.
- PR #28 (Issue #8) also merged into `codex/issue-6-test-entry`, not main, on 2026-09-11 at 06:00:04 UTC.
- GitHub Issues #7 and #8 remain open.
- Current main's laboratory public interface includes reception, barcode retrieval and test entry, but no finalization/withdrawal/report-result selection command. The OPEN/FINALIZED enum and editing guard are not an implemented finalization workflow.
- Current main migration tree has 0005 then 0009; finalization/report migrations and report implementation are absent. This is consistent with PR target history, not merely a stale issue label.

Sources: https://github.com/studyben/DGA_lab/issues/13, https://github.com/studyben/DGA_lab/pull/26, https://github.com/studyben/DGA_lab/pull/27, https://github.com/studyben/DGA_lab/pull/28; current main backend/dga/laboratory/public.py, workbench.py and backend/migrations/versions.

## Decision and next entry

Do not silently recreate #7 inside #13 or treat the status enum as a completed dependency. Integrating the already-written #7/#8 branch into latest main is a distinct work unit, with conflict resolution, migration-chain review and full regression required. Request user authorization for that prerequisite integration before finalizing #13's implementation plan. No application code, migration, existing data or external issue was changed during this preflight. The new worktree contains only this local blocker record.

Residual risk owner: prerequisite integration work unit, pending user direction. Once the dependency is integrated and verified, update the #13 baseline and continue plan -> plan review -> test-driven slices -> code review. No plan/implementation/review pass is claimed yet.

## Resolved dependency and accepted implementation plan

User authorized local integration, completed and reviewed at f612076 with149 backend/19 browser tests. #13 is now stacked locally on that checkpoint; original main62f26a4 unchanged. The historical blocker above is resolved locally, not on GitHub. User confirmed goal, isolated branch and public laboratory+real PostgreSQL/browser test seams. Current gate: plan review.

### Public contracts and meanings

Add laboratory-owned `LaboratoryOperations(engine, registry, asset_directory, audit, clock=...)`, exported through laboratory.public. Methods: `dashboard(actor)`, `ledger(actor, **filters)`, `sample_operations(actor, barcode)`, `confirm_identity(actor, barcode, formal_asset_id, expected_revision, reason)`, `change_container(actor, barcode, container_id, target, expected_revision, reason)`. Read requires laboratory.read, mutations laboratory.write and transport Origin/CSRF. HTTP is a thin laboratory adapter, no SQL in frontend/composition.

Dashboard exactly four numeric metrics plus as_of/business_date/timezone metadata and recent-sample links. `detecting_samples`: OPEN oil samples with at least one ACTIVE test, including identity-pending samples with ongoing work. `tests_created_today`: all test records created during local Chicago calendar day, including later removed records; updates and measured_at do not affect count. `samples_created_today`: created_at, not received_at; `samples_created_total`: all retained oil samples. Chicago midnight-to-next-midnight converted independently to UTC (23/25-hour DST days), half-open ranges. Count all four in one consistent database snapshot. Return explanations so UI does not imply received time is creation time.

Ledger derives display state without creating a second mutable sample state: IDENTITY_PENDING first; then FINALIZED with current READY matching finalization_token -> REPORTED; FINALIZED otherwise -> COMPLETED; OPEN with ACTIVE tests -> DETECTING; otherwise RECEIVED. No cancel operation exists in current code; don't invent cancellation in #13. Filters barcode, sample_number, site, equipment serial (including sampled snapshot path serials), display state, test type (ACTIVE only), date range with date_field created_at(default)/received_at/sampled_at. Case-insensitive substring matching, AND-combined; date end includes entire chosen Chicago day; reject end<start and invalid sorts/enums. Sort whitelist created_at/received_at/sampled_at/sample_number/site_name plus id tie-break; asc/desc; pages1..100000, size1..100 default20. One REPEATABLE READ snapshot for count+rows. Frontend keeps filters/sort/page in URL, supports reset/column visibility/results/empty/error, links back to original ledger from barcode workbench.

Sample operations returns existing sample dataclass, its operations_revision, container statuses/revisions/allowed_targets, and append-only operation history. No dynamic recomputation of saved asset snapshots. Identity confirmation only IDENTITY_PENDING and OPEN. Take graph advisory110011 then sample FOR UPDATE, compare revision, resolve formal transformer via asset public sampling context at current locked sampled_at; save snapshot and derived site/serial atomically with actor/time/reason/before/after history + shared audit. Preserve sample id, barcode, containers, existing tests and original raw identity in event before_value. Reject wrong type/missing historical context, stale revision, already-associated or finalized. Existing update_sample increments operations_revision so editing basic facts during asset search cannot confirm stale context. No correction/rebinding of already-associated assets in this ticket.

Containers are physical state independent of scientific finalization, and may change after finalization without altering report snapshots. All existing/new containers default RECEIVED, revision0. Transitions: RECEIVED -> IN_USE/RETAINED/BROKEN/DISPOSED; IN_USE -> RETAINED/EXHAUSTED/BROKEN/DISPOSED; RETAINED -> IN_USE/EXHAUSTED/BROKEN/DISPOSED; EXHAUSTED/BROKEN -> DISPOSED; DISPOSED terminal. Same-state and stale revisions conflict; server returns allowed targets, frontend does not maintain a second graph. Mandatory trimmed reason1..500, server timestamp, history and shared audit in same transaction. Container must belong to supplied barcode. No hard delete/reopen/backdating/storage-inventory/automatic test-count-driven state change.

### Schema and slices

S1 operational read views: new operations.py query DTOs and SQL/public export; HTTP dashboard+ledger; frontend laboratory OperationsPages with dashboard+ledger. No schema required. Public tests first for empty/Chicago date boundaries and combinations, then UI. Build/typecheck and slice review/commit. Do not implement identity/container commands early.

S2 identity+container lifecycle: additive0015_lab_operations after0014, operations_revision on oil_samples; status/revision on sample_containers; laboratory_operation_events (sample/container association, action, reason, actor, occurred_at, before/after JSON), append-only trigger using existing forbid_audit_mutation. Migration rollback refuses retained events (no data deletion). Existing rows default received with no invented past event. Index sample events and created_at on samples/tests for daily queries. operations methods+DTOs, registry/workbench composition only as required. Public tests for pending->associated with existing tests, audit/raw evidence, stale after basics, concurrent confirmation, wrong asset/permission, full allowed/illegal container transitions, finalization-independent physical disposal. Review/commit.

S3 UI identity queue+container controls and acceptance: identity page shares filtered ledger; select barcode, show raw/context, reuse OfficialAssetSelector (sampling time from server), reason, explicit confirmation; preserve inputs on conflict and explicit reload. Containers shown in workbench via same operations pane with allowed target select/reason/history; reports/finalize flows untouched. HTTP request DTOs forbid extras, enforce strict revisions/UUID and no-store. Browsers cover home/ledger/identity/continue test/container, readonly denied. Full backend/browser/build, parallel Standards/Spec review and aggregate deepreview; commits local only.

### Validation and risk

Separate projects dga-issue13 and dga-issue13-browser (port18097,tmpfs); no fixtures/migrations on18093. Tests mock only external clock/store; fixture SQL for arrangement, public reads for outcomes. Include DST spring/fall, measured_at vs created_at, removed tests, pagination ties, stale identity snapshots and finalization race. No formal ASTM/thresholds/PDF branding. Domain docs are read from authoritative original workspace; do not overwrite dirty versions. README documents counts, states and dependency baseline. Remaining production deployment concerns stay #20. No push/PR/remote merge or later Issue.

### S1 implementation / review pass
Implemented public dashboard/ledger queries, laboratory HTTP adapter and operational home/ledger UI, barcode continuation and restricted return link. TDD observed missing-interface/route failures then green; boundary review reproduced and fixed maximum-date overflow. Evidence: docs/reviews/code-review-20260912-224212.md,5 backend tests,1 browser flow, frontend build/typecheck. Docs decision: semantics here, final README in S3. Current gate/next entry: S2 implementation; identity/container commands and aggregate validation remain approved work, not completed.
