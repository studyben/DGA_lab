# Issue #17 local acceptance handoff

## Status

Implementation S1/S2/S3 and aggregate deepreview accepted locally. Current gate / next entry point: **ready-to-open-draft-PR**. User prohibits push/merge; no remote PR, issue comment or next Issue started. This is not final-closeout pass.

- Worktree: G:/Sungrow Develop/DGA Lab/.worktrees/issue-17-alarm-lifecycle.
- Branch: codex/issue-17-alarm-lifecycle.
- Base: 15c36e61a87ea4c370b18a26bd76f82e275cfe37.
- Accepted plan/S1/S2/S3: 53cb7b3 / 967e866 / 7c10c1f / c99f99c. Aggregate checkpoint is the commit containing this document.
- Review: docs/reviews/code-review-20260918-024121.md. No unresolved material finding.

## Delivered

Current/history alarm filtering, physical-device deduplication, acknowledgment with actor/time/note, evidence-based recovery, withdrawal correction and immutable timeline. Rule retirement never means normal; replacement does not clear the removed transformer's alarm. Current ancestor counts follow installation; sampling source remains historical. Asset/laboratory/analysis public ownership boundaries retained.

Dashboard entry count uses the explicitly labeled product-line/site/customer scope, not all dashboard location/status filters. Alarm confirmation is separate from current health: confirming awareness never forces health normal.

## Validation

Final backend271 and browser37 passed; alarm-focused26 passed; TypeScript/Vite passed. Migration upgrades exercised on empty isolated PostgreSQL, through 0024. Two pre-existing dependency deprecation warnings. Production load/rollback certification remains deployment work; remote CI not run.

## Local acceptance

- Isolated preview: http://127.0.0.1:18117/assets/analysis/alarms?asset_id=30000000-0000-0000-0000-000000000015
- Fixture accounts: browser-admin (admin), field-user (field engineer), operations-reader (read-only).
- Fixture password for these accounts: `Browser changed passphrase 84!`. These are local browser-test credentials, not production accounts.
- This environment contains synthetic method/rule/result fixtures only; never reuse their thresholds scientifically. Its tmpfs database is disposable when containers are removed. Existing 18108/18097 environments and original acceptance data were not migrated/reset by this task.

Suggested checks:

1. Open alarm center; inspect current/history lists and filters. Count and list must describe the same filter scope.
2. Open an alarm and distinguish retained abnormal severity, current state, current location and original sampling location.
3. Inspect source barcode, selected result/method/unit and operation history; accessible report/workbench links follow role permissions.
4. For an unacknowledged fixture, enter a note and confirm. Severity is retained; acknowledgment records actor/time/note. Current fixture may already be acknowledged after automated validation; historical confirmation is still inspectable.
5. Inspect the resolved fixture and its later comparable normal source. Automated PostgreSQL tests additionally cover qualifiers, rule retirement, withdrawn finalization, same-time evidence, duplicate serials and actual replacement without requiring destructive manual mutations.
6. Log in as operations-reader: view evidence/report but no confirmation action or write-only workbench link.

## Preservation / follow-up

Original main has its pre-existing CONTEXT.md and PROJECT_PLAN.md modifications and untracked directories unchanged. Generated screenshots/traces under this worktree outputs/ remain untracked. No branch reset, original data deletion, push or merge performed. Publication requires a new explicit user instruction; do not begin a subsequent Issue.
