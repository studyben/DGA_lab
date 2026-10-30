# #52 finite plan fix — finding01 COMPLETE

Gate: FINITE PLAN FIX DOCS ONLY. Worktree C:/Users/weila/.codex/worktrees/issue-52-lab-import-staging/DGA Lab; branch codex/issue-52-lab-import-staging; HEAD896d7072cfd81c07ac732404d286e160e9ed3459 unchanged.

## Authority and reviewed target

Read the complete independent artifact docs/reviews/plan-review-20261029-220544.md (FAIL, sole material P2 finding01), then the affected plan/goal/baseline sections. Root explicitly accepted finding01 and selected the working-manifest-only readiness contract. No new product interview or other finding was introduced.

Review finding01: inactive historical PENDING/RETRYABLE receipt could be interpreted as a batch-global files_pending gate, while its original actor alone could recover its operation and might be revoked forever. B could hold a complete confirmed working manifest yet be forced to recreate the batch or wait for#60. This is a plan contract ambiguity, not a claim of an implemented production bug.

Status: **01 已修复（plan contract and required acceptance specification）；独立 re-review 待完成**. This report does not declare re-review pass or authorize implementation.

## Bounded correction

1. Validation readiness now depends only on explicitly selected active working input: required roles complete for XLSX/CSV_PAIR, state RECEIVED, confirmed actual size/SHA metadata and applicable limits. Unrelated inactive PENDING/RETRYABLE history never gates a complete manifest.
2. files_pending now applies to an explicit selection/activation request for a specified file that is not RECEIVED. Missing active roles use active_files_incomplete; validate does not scan all historical receipts for pending status.
3. A's original operation stays actor-private; reservation/object/recovery metadata and any written bytes remain preserved. B uses its own key and received replacement in the same batch, without cancellation/deletion, proxying A's operation or guessing source identity.
4. Late successful A receipt cannot replace B's occupied active role. It remains inactive, follows the existing successful-receipt revision increment, supersedes old job/current validation and leaves previous results stale. Old upload/validation tokens cannot back-write current results. If A stays revoked, final receipt success remains denied.
5. Worker queue/claim/process reads only the immutable selected active manifest; historical inactive files are not read, awaited or silently promoted. After a late receipt revision bump, fresh validation still uses B's selected IDs/hashes at the new revision.

No schema/table/column/migration/permission/new platform/cancel/publication change. Format1,18 sample columns,39 complete-test columns,8 staging tables,0034 proposal and3 vertical slices remain the original design. No asset/lab/analysis source changed.

## Synchronized plan locations

- Section10 HTTP validate/list_files/revise/error scope: selected-confirmed manifest and scoped files_pending; no global historical pending gate.
- Section11 orthogonal manifest/receipt states and receipt step3: preserve actor-private abandoned history, allow current B replacement and fence late inactive receipt by existing revision.
- Section12 worker input/currentness: only queued selected inputs; stale revision/token results cannot become current; existing same-revision QUEUED/RUNNING/FAILED versus old parsed output consistency remains explicitly required.
- Section13 UI and S1/S2/S3: unresolved history is separate informational status, not a disabled validation button. B own-intent replacement/reopen is possible without old-key access/cancel/delete.
- T1: S1 receipt/currentauth/private history and B replacement only, no early worker implementation.
- T6: S2 real-PG queue/process/preview with complete B input despite A history, late receipt/validation races and fresh validation, plus formal non-effects.
- T10/S3: bounded two-writer replacement/reopen browser smoke, retaining original history and intent authority.
- Added the numbered Finding01 public PostgreSQL scenario after the validation matrix, separating S1 receipt-only assertions from S2 worker behavior.
- Residual section: basic same-batch replacement is current#52 obligation, not deferred to#60; general orphan cleanup/cancel remains#60. Same-revision/current-read consistency remains the original review residual required in S2/S3, not a manufactured second finding.

## Required implementation acceptance, not executed in this gate

A reserves through public receive_file and controlled FileStore blocks/stores or loses response after durable reservation; lease expires and/or A is revoked through the public identity service. B's own public receive/revision selects complete confirmed originals in the same batch. Public list/files/original/operation queries prove B can continue and cannot query/replay A's operation, while A reservation and any object remain.

S2 then proves B validate/process_next/preview succeeds despite inactive A PENDING/RETRYABLE, for both XLSX and CSV_PAIR. Releasing A while revoked denies final success; authorized original-intent recovery with a fresh upload token may complete late but remains inactive, increments revision and supersedes any racing validation. New validation still reads only B inputs. Old tokens cannot promote old data. Formal samples/tests/containers/assets/facts/report tasks and business analysis observations remain unchanged, allowing existing read-side evaluation behavior.

These cases are specified for real isolated PostgreSQL and public application seams with controlled file/clock boundaries; no private-table insertion or internal-parser-call test is substituted. No such test/database/worker/browser was run in this plan-fix gate.

## Controller-provided CI status and historical evidence

Root now reports verified latest896 GitHubPR40992909646/push40992903963 plus Sungrow312591896 ALLSUCCESS. Both hosts ran684 backend and78 browser passes/1 existing optionalOIDC skip; all40 configured provider cases executed. Enterprise full job21m02 completed under the accepted30-minute budget. Thus the original07720-minute failure is closed by actual new-head full-run evidence, not by relabelling the cancelled old run.

This Agent did not run or independently query CI. Parent CI guard is released per root; finite plan-fix re-review and accepted-plan checkpoint are still mandatory before source/test edits/runtime. Prior077 preflight and pointer-refresh pending-CI paragraphs remain explicitly historical in goal/baseline documents, with a later current-state addendum. Original review artifact retains its original FAIL/pending-CI statement and is read-only.

## Scope and consistency verification

Changed only:
- docs/work-units/issue-52-plan.md
- docs/work-units/issue-52-goal-confirmation.md (necessary historical/current CI and finite-fix summary)
- docs/work-units/issue-52-plan-baseline-refresh.md (historical hash/CI timing versus later fix/current CI)
- this docs/work-units/issue-52-plan-fix.md

The G: evidence artifact and root control were not edited in this gate. Original planreview artifact was not edited. No other checkout or user data touched.

Read-only consistency searches confirm:
- old unscoped phrase 'no PENDING receipt' removed from current plan;
- each files_pending contract use is either scoped to explicit non-RECEIVED selection or explicitly denies a batch-global gate;
- active input / inactive historical receipts / own-actor key / late receipt / revision / worker snapshot / S1-vs-S2 sequencing appears consistently across exact contracts, UI, slices and T1/T6/T10;
- unchanged unique18/39 header counts and3 S1/S2/S3 headings;
- current parent896 and currentCI evidence are distinguished from the original077/pending-CI writing times.

No application tests, builds, installs, database/service/worker/browser/runtime actions, source/test/config edits, commit/push/PR/comment/branch/FF operations. Tracked git diff remains empty; status contains only the known untracked review and assigned planning artifacts.

Remaining blockers/questions: none for this finite fix. Stop for root's complete artifact read and independent finding01 re-review; no implementation self-start.


## Final finite-scope size/encoding check

Controller noted an early47KB observation; it was an in-flight initial-plan read, not an established completed baseline. This Agent's earlier completed baseline-refresh readback was82,045 bytes; current fixed plan is92,420 bytes/388 lines, an increase10,375 bytes (~12.6%). The increase is the manifest/error/receipt/worker/UI/slice/T1/T6/T10 synchronization, explicit A/B public-PG procedure and the authorized currentCI addendum. No pre-fix full-text backup was saved, so this artifact does not claim a complete before/after byte diff; targeted replacement commands asserted each expected old paragraph before writing.

Actual read-only checks:1 top-level heading,17 numbered sections,3 S1/S2/S3 headings,1 Finding01 scenario heading; exact duplicate paragraphs longer than120 characters=0; U+FFFD replacement characters=0; literal escaped-Unicode patterns=0. Header tuples remain unique18/39 and the old unscoped 'no PENDING receipt' phrase has0 matches in the current plan. No duplicate full-document insertion, escaping expansion or encoding rewrite was found. No design reduction/rewrite was made because of the size observation.

Postfix tracked diff remains empty and HEAD896 unchanged; untracked status is exactly the original read-only review plus goal/plan/baseline-refresh/fix documents. These are document inspections, not tests of the future implementation.

