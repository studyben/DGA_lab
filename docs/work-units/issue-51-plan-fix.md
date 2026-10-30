# Issue #51 finite PLAN FIX — accepted finding 1

Gate: PLAN fix, explicitly COMPLETE for independent re-review.
Date: 2026-10-29.
Checkout: C:/Users/weila/.codex/worktrees/issue-51-finalization-facts/DGA Lab.
Branch/base: codex/issue-51-finalization-facts / fcea999e313db51461cd9aefda66d70e6e34ed3b.
Review: docs/reviews/plan-review-20261029-191956.md, FAIL with one material finding. Controller accepted finding1 and dispatched this finite document-only fix. No human reconfirmation required.

## Finding and decision

Finding1: NULL-token旧定稿记录将阻断整个设备乃至全局报警读取.
Disposition: accepted; writer status 已修复. Independent re-review remains required; this artifact does not claim plan-pass.

I read the entire review artifact and rechecked the migration/query source:0006 allowed legitimate FINALIZED records with finalizer/time before a token existed;0007 only adds nullable testing_finalization_token without backfill. Existing result token equality join excludes NULL. Treating that legacy noncandidate as corrupt current evidence would make unrelated qualified records depend on it, including AlarmCenter's all-assets batch.

The revised plan preserves that qualification contract:
- Require ASSOCIATED + FINALIZED + a nonnull current sample token before aggregate fact validation. Preserve a LEFT JOIN within that qualified set, so nonnull-token missing facts remain visible and fail503.
- Legal legacy NULL-token records produce no point and cannot block lawful current samples on the same transformer or unrelated assets/global alarms. No token/fact/source is generated or backfilled.
- Single-record diagnostics remain get_current_finalization UNAVAILABLE/missing_finalization_token and report refinalization_required.
- A qualified nonnull current token with missing/corrupt facts still raises trend_snapshot_unavailable503, with no partial success. No swallowing current typed corruption.
- Missing optional PDF request alone never fails independently valid current facts. Legacy report absence before migration can leave missing facts; it is distinct from NO_REQUEST with valid facts.

## Changes and consistency reconciliation

Modified only docs/work-units/issue-51-plan.md; added this fix artifact.
Goal document was checked and left unchanged: it already records the single-sample NULL-token unavailability/reconstruction limit and does not require aggregate503. Its SHA stayed identical. Review artifact was read-only and untouched.

Plan sections synchronized:
- §4 migration: legal tokenless legacy records remain unqualified/no fabricated backfill.
- §5 corpus/negatives: separate lawful NULL-token qualification fixture from corrupted nonnull-current negatives; missing-report-before-backfill versus missing-current-fact versus valid no-request clarified.
- §6 transition table: separate tokenless legacy exclusion/diagnosis from nonnull missing/unverifiable fact503.
- §7 source/error contract: explicit sample-token IS NOT NULL predicate before LEFT JOIN validation; single-record diagnosis versus aggregate scope.
- §9 S1/S2 acceptance: real historical migration coexistence and all3 public query assertions; standalone missing/bad nonnull fact503 preserved; page text no longer labels legal tokenless state as current corruption.
- §10 matrix, §11 command expectations and §12 residual owner: same distinction throughout.

Future implementation proof is concrete and NOT RUN in this gate: create legal FINALIZED/ASSOCIATED tokenless fixture at actual0006 with valid explicit finalizer/time, run real0007 then0032/0033 chain, retain NULL without synthesized facts, and coexist with lawful current sample on the same physical transformer plus another lawful current asset in global alarms. TransformerTrends, DeviceHealth and AlarmCenter must remain readable and omit the old sample; single-sample view/report diagnosis stays. Separately place a nonnull-token missing fact and corrupt fact beside lawful data, each still503/no partial result. This adds qualification proof without replacing attested valid-v1 snapshot/PDF corpus.

## Validation actually performed

- Read-only branch/rev/status preflight: feature branch and fcea999e; preexisting untracked plan/goal/review documents only.
- Full review artifact read; relevant0006/0007/current token-join and caller evidence inspected.
- Scoped string replacements required exactly one old occurrence each; all targeted changes applied once.
- Searched all plan NULL-token/missing-token/missing-fact/qualification/503 mentions and checked matrix/fixture/slice/command agreement.
- Explicit obsolete expectations absent: original NULL-token/missing/invalid503 sentence, combined fact/token state row, combined token/request/fact matrix row, old invalid-legacy wording and missing-current-token in the corrupt-current negative list.
- Read-only git diff --check and final status/scope; document trailing-whitespace check. These are document checks, not application tests.

Hashes:
- Plan before fix SHA256 88D313E51E28D50440CBBB9E8DCA6D63B1F573AB86E3B496A602FE7A5C34E18A.
- Plan after fix SHA256 9102A95C0504C6F486148E20CA26CC235CBE9F3926E0FA830C457C28AAE2348F.
- Unchanged goal SHA256 F314753EA28DB8878869291CEA9468DAF08977E363E85BFD265E00816EF7B206.
- Unchanged review SHA256 F53F136B6780DD7A4BF2F87C40BD913DAE760DD9D747FCDFAA55CB81B61C2DA7.

No source/test/schema/config/runtime/database/browser changes or execution; no migrations, commits, staging, push, external actions or controller writes. No claim of PG or browser pass.

## Residuals and next entry

- Legal NULL-token coexistence, qualified-current corruption, lawful producer capture, immutable inventory/old bytes, current authorization/races and observation fingerprint proof: current #51 S1/S2 implementation/validation obligations, unchanged owners and no deferral to#61.
- Exact parent remains controller-recorded green fcea999e; future parent changes require baseline refresh.
- Configured storage/CI timing, real Azure/Okta, later import/date/manual-summary scope and#60/#61 risks remain as classified in the plan; this finite fix changes none.
- No new product/architecture question. Finding1 is writer 已修复; independent re-review must adjudicate it before accepted-plan commit.

Explicit completion: finite PLAN FIX COMPLETE. Stop for independent re-review; do not implement or advance another gate.

