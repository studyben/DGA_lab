# Issue #51 — goal confirmation (already human-confirmed)

Gate: goal confirmation evidence carried into PLAN; no new approval request.
Date: 2026-10-29. Branch: codex/issue-51-finalization-facts.
Verified parent/base: fcea999e313db51461cd9aefda66d70e6e34ed3b.
Checkout: C:/Users/weila/.codex/worktrees/issue-51-finalization-facts/DGA Lab.

## Authorization and actual dependency

The human confirmed #50/#51/#52 goals together and authorized the batch's gated work; the controller's explicit #51 PLAN dispatch carries that confirmation. Do not ask the human again. Read the authoritative control record at G:/Sungrow Develop/DGA Lab/docs/work-units/phaseflow-50-52-control.md, frozen issue-47/51.json and outputs/specs/bulk-data-import.md. This document records the existing decision; it does not grant implementation authority.

The controller verified live #51 OPEN with native blocked_by=[]; #50 is an engineering stack base, not an invented issue blocker. Parent PR #65 remains draft/unmerged. This branch was verified clean at exact fcea999e before these two docs. Parent final CI is controller-owned; during this PLAN turn the controller recorded exact fcea999e GitHub PR40975486166/push40975478587 and Sungrow312301681 COMPLETED/SUCCESS (622 backend with storage;77 browser passed/1 intentional OIDC skip). Parent CI is now resolved, but accepted-plan commit/implementation still require independent planreview and explicit controller gate dispatch. Parent changes require baseline refresh before acceptance. This dispatch ends after the two docs and explicit handoff to independent planreview.

## Goal, motivation and success signals

Current ordinary finalization locks a sample and creates a current token in the same transaction as queueing a PDF request. Its only immutable result snapshot lives on the report row. Analysis ignores PDF READY/file state but still joins that row. A no-request policy would currently remove the only effective fact source. This compatibility work is justified before a future external-data writer exists.

The confirmed outcome is immutable laboratory-owned finalization facts, independent of PDF delivery, with a controlled public application policy that can finalize without a report request. Ordinary workbench/HTTP finalization must retain default autoqueue and full rollback when queueing fails. New facts capture the entire active-test inventory, selected/adopted results, exact method configuration, confirmed warnings and actor/time/token atomically with the sample lock/event/audit.

Success is observable through Workbench/Reports and the laboratory result protocols, then TransformerTrends, DeviceHealth and AlarmCenter on real isolated PostgreSQL: valid facts stay effective with no task, queued/failed task or missing file; qualified values/method-unit groups/physical identities remain distinct. Withdrawal removes current results/report availability immediately at its committed transition; a new finalization uses a new token, and stale claims cannot resurrect an old report. Lawful old v1 results and intact old PDF bytes remain readable without blanket refinalization; unverifiable/corrupt cases are explicit and never reconstructed from today's mutable data.

## Scope and non-goals

- Laboratory owns frozen facts, token qualification and report snapshots; analysis consumes laboratory.public only. Assets remains the identity/history owner; shared identity/audit/files remain their owners.
- Preserve the integrated #18 analyst laboratory.finalize grant. Earlier parent prose saying analysts cannot finalize is obsolete current-state evidence; policy alignment belongs to #53.
- Add optional read metadata for origin/instant precision/context verification without inventing values for old rows or changing old observation hashes when metadata is absent.
- Report page explains valid finalized/no-request state without blank output or advice to withdraw merely to request a PDF. Ordinary finalize/report/download browser regression remains.
- No formal external imports, source-PDF upload, DATE-only formal writes, import page, full manual summary workflow, alternative task/storage framework, guessed ASTM method/compatibility/threshold, credential/cloud/Okta provisioning or cross-module writes.
- No rewriting old PDF bytes/barcodes/snapshots/IDs, no rereading today's assets/methods/tests to invent a legacy complete inventory, no destructive recovery of retained data.

## Direct code evidence at exact base

- backend/dga/laboratory/workbench.py:454–533: configuration/sample locks, warning/selection rules, token, unconditional queue, event and audit in one transaction; :547–584 reasoned withdrawal.
- backend/dga/laboratory/reports.py:353–469: current request also constructs v1 frozen snapshot; :118–165 retry preserves it; :167–246 and :327–341 token/generation/claim guards; :275–325 saved-byte validation.
- backend/dga/laboratory/trends.py:128–154: current matching report token join, no READY/file predicate; malformed selected facts raise trend_snapshot_unavailable 503.
- backend/dga/condition_analysis/public.py:61–102; health.py:63–110; alarms.py:69–143: all consume laboratory.public protocols, with physical identity and stable measurements central to statistics/evidence/recovery.
- backend/migrations/versions/0032_device_material_import.py:4–20: actual current single head, assets-only provenance extension. Existing merge nodes 0014 and 0030 remain.
- backend/tests/test_device_material_import_migrations.py:22–136: new #50 dynamic-head historical upgrade/downgrade paths arrange OPEN samples, not old finalized fact/PDF coverage.
- backend/tests/test_laboratory_reports.py:202–223: NULL-token synthetic legacy metadata is explicitly unavailable; it is not reconstruction evidence. test_transformer_trends.py:272–294 distinguishes retained typed corruption from an empty result set.
- backend/migrations/versions/0025_identity_roles.py:25–28 and shared/auth/policy.py:10: analysts retain finalize; shared/auth/public.py:244–257 already exposes the current-authorization transaction guard.
- Read-only git comparison confirms laboratory/analysis/auth/migrations and named historical/laboratory tests unchanged from evidence baseline 6eb7d5e to fcea999e. The G: evidence map remains read-only evidence, not a plan-pass artifact.

## First-principles judgment and restrained design

A small immutable fact module behind Workbench/Reports/result interfaces removes real duplicated ownership. One additive table plus a v1 compatibility decoder and a v2 complete producer is sufficient. The current token remains the sole currentness pointer; no second publication state machine, import-specific analysis engine, event bus, historical report UI or generic workflow platform is needed. Reports continue to own request/lease/delivery metadata.

The plan chooses two coherent slices: first establish safe immutable storage/legacy compatibility while ordinary reporting remains; then expose no-request effective results across all consumers and the page. Their split follows persistence/compatibility risk and the user-observable capability, rather than separating frontend/backend or individual tables. See issue-51-plan.md for exact contracts and tests.

## Open questions and stop state

No blocking product/architecture question remains for this plan. Exact legacy corpus and implementation/runtime outcomes are future validation work with explicit capture/provenance rules in the plan, not facts claimed already verified. #50 final exact-head CI was resolved by the controller during this gate; it does not itself authorize implementation.

Current artifacts: this goal evidence and docs/work-units/issue-51-plan.md only.
Validation in this gate: read-only source/domain/baseline inspection; no tests, migrations, runtime or service changes.
Next entry: independent planreview; accepted-plan commit/implementation remain controller-owned pending independent planreview; the parent CI condition is recorded resolved.


