# Issue #50 / BI-03 — S1 accepted-findings fix

## Scope and result

Gate: S1 fix only, after controller accepted findings1/2/3 from `docs/reviews/code-review-20261029-155906.md`. All three are implemented and tested; independent re-review remains required. No review acceptance, checkpoint commit or gate advancement is claimed.

Checkout `C:/Users/weila/.codex/worktrees/issue-50-material-import/DGA Lab`, branch `codex/issue-50-device-material-import`, unchanged base/HEAD `a9d250248cd02b683a969a495150bad1a8a5def7`. Read the complete review and current G: controller read-only. Preserved the existing uncommitted S1 implementation/review artifacts. Followed TDD at the already-approved AssetImports public facade with real isolated PostgreSQL; no repeated business decision or permission request.

Final focused regression: **184 passed,3 expected warnings,76.63s**, `.cache/issue50-tests/s1-fix-focused-regression.log`. This supersedes the earlier168-pass S1 execution record for the current working tree. Warnings remain the existing Starlette/httpx/anyio deprecations and deliberate duplicate-ZIP fixture warning.

## Findings and final fix states

| Accepted review finding | Before | After | Implementation and observable proof |
| --- | --- | --- | --- |
|1 unresolved same-batch site dereference / lost actionable rows | 未修复 | 已修复 | Site-reference owner returns no resolved reference for absent/ambiguous/unresolved BATCH rows; identity calculation checks uniqueness and explicit NEW/REFERENCE decision, with no fabricated fallback. Children with unresolved root sites receive inherited_site_conflict. Implicit child, same missing NEW key, and child explicit existing UUID remain VALIDATED with row errors; progressive revisions save normally, preserve originals and eventually clear errors. |
|2 casefold inputs vs SQL lower loses Unicode existing candidates | 未修复 | 已修复 | One asset-owned serial_key casefold policy is used at actual catalog lookup, batch grouping and comparison. On PostgreSQL17, compact ID/serial rows stream in500-row batches through that policy; only matched identities load full detail/context. Exact Straße, STRAßE, STRASSE and strasse find the existing formal asset and explicit duplicate warning. ASCII and same-batch Unicode behavior remain, with no binding/merge/skip or ASCII restriction. |
|3 worker consumes unknown persisted pair as technical FAILED | 未修复 | 已修复 | Strict pair guard is before the technical-failure catch/savepoint path. Unknown mode/version raises AssetQueryError unsupported_import_format503 and rolls back the claim unchanged. After restoring only metadata, original STAGED state/revision/rows/issues/summary/failure remain and the same batch validates normally. Genuine technical FAILED/recovery and actual PostgreSQL40001/40P01 rollback/retry are preserved. |

These are implementation fix states, not an assertion that the independent re-review has passed. No accepted finding is deferred or partially fixed; no new blocking contract was needed.

## Changes made during this fix gate

- `backend/dga/assets/asset_import_validation_v2.py`: resolved-site ownership/identity and child error propagation; unified Unicode serial lookup/group/compare. The original declared site reference remains in reviewed/raw values even when no resolved identity is returned.
- `backend/dga/assets/imports.py`: move the supported persisted-pair check immediately after claim and before the broad technical handler; remove the now-redundant inner legacy-pair check.
- `backend/tests/test_device_material_import.py`:16 public-facade regression cases for the accepted findings and preserved retry semantics. SQL is fixture setup or a database-boundary fault; success is observed through public previews/revisions/source downloads/candidates/state, not private table layout.
- `docs/work-units/issue-50-s1-fix.md` and an appended current-result pointer in `issue-50-s1.md`.

No HTTP adapter/test needed alteration: transport behavior was already established and the accepted defects are on its shared facade path. The complete regression includes the actual HTTP tests. No other production file changed during this fix gate. SHA-256 of import_http.py, v2_imports.py, v2_import_workbook.py and site_import_validation.py still matches the reviewed fingerprints. No migration, formal ASSETS writer, UI, provider, dependency or controller change; the409 import_mode_not_publishable guard remains active.

## Red/green execution

Same retained **new #50 test namespace only**: cluster `.cache/issue50-tests/pgdata`,127.0.0.1:18550, logical URL test-db/dga_test/dga_test, PGHOSTADDR=127.0.0.1. No runtime restart/bootstrap, Docker Desktop action or retained workspace/database write. Existing PostgreSQL/Python binaries reused read-only, as recorded in `issue-50-s1.md`.

From the active checkout/backend, each command used:

```powershell
$env:TEST_DATABASE_URL='postgresql+psycopg://dga_test@test-db:18550/dga_test'
$env:PGHOSTADDR='127.0.0.1'
$env:PYTHONUTF8='1'
$env:PYTHONPATH='C:/Users/weila/.codex/worktrees/issue-50-material-import/DGA Lab/backend'
$env:PYTHONDONTWRITEBYTECODE='1'
```

Executable for all rows below:
`C:/Users/weila/.codex/worktrees/issue-48-dual-main-sync/DGA Lab/.cache/test-venv/Scripts/python.exe`.
All logs are under this checkout `.cache/issue50-tests/`.

| Step | Exact pytest arguments after `-m pytest` | Actual result / log |
| --- | --- | --- |
|F1 RED | `-q -p no:cacheprovider tests/test_device_material_import.py -k 'unresolved_root_site or progressive_site_revision' --tb=short` |4failed; implicit child lacks actionable inherited error, explicit cases become FAILED, progressive revision raises AttributeError. `s1-fix-f1-red.log`. |
|F1 GREEN | `-q -p no:cacheprovider tests/test_device_material_import.py -k 'unresolved_root_site or progressive_site_revision or initial_tree or existing_and_batch_references' --tb=short` |14passed/54deselected. `s1-fix-f1-green.log`. |
|F2 RED | `-q -p no:cacheprovider tests/test_device_material_import.py -k 'unicode_and_ascii_serials or same_batch_unicode' --tb=short` |4Unicode failures/3passes. `s1-fix-f2-red.log`. |
|F2 GREEN | `-q -p no:cacheprovider tests/test_device_material_import.py -k 'unicode_and_ascii_serials or same_batch_unicode or duplicate_serial_candidates or ancestor_lifecycle' --tb=short` |9passed/66deselected. `s1-fix-f2-green.log`. |
|F3 RED | `-q -p no:cacheprovider tests/test_device_material_import.py -k 'worker_rejects_unknown or worker_database_contention' --tb=short` |3unknown-pair failures/2existing contention passes. `s1-fix-f3-red.log`. |
|F3 GREEN | `-q -p no:cacheprovider tests/test_device_material_import.py -k 'worker_rejects_unknown or worker_database_contention or validation_database_failure or unsupported_persisted_mode' --tb=short` |7passed/73deselected. `s1-fix-f3-green.log`. |

F3 metadata fixtures cover `(2,UNSUPPORTED)`, `(3,ASSETS)` and `(1,SITES)`. Restoration SQL changes only format_version/mode, not state/revision/preview/failure, so it cannot conceal a consumed batch. Actual server-side RAISE SQLSTATE40001/40P01 is injected at the SQL execution boundary; the claim remains STAGED/revision0 and a normal subsequent worker pass succeeds. The prior genuine missing-table technical-failure/recovery case still passes.

Exact cumulative command:

```powershell
& 'C:/Users/weila/.codex/worktrees/issue-48-dual-main-sync/DGA Lab/.cache/test-venv/Scripts/python.exe' -m pytest -q -p no:cacheprovider tests/test_device_material_import.py tests/test_device_material_import_http.py tests/test_site_import.py tests/test_site_import_http.py tests/test_asset_import.py tests/test_asset_lifecycle.py tests/test_equipment_details.py tests/test_architecture.py --tb=short
```

Result184passed/3warnings/76.63s. Includes old v1/SITES/real historical migration, lifecycle/equipment, HTTP security and architecture checks. `git diff --check` passes. C2 was not repeated: no frontend/dependency change or build concern; the original S1 production build remains its prior evidence, not a new browser claim.

## Decisions and classified residual risks

- Unicode policy remains Python casefold, which already owned same-batch matching; actual catalog lookup now follows it. No NFC/transliteration or additional identity equivalence was added. The lookup streams compact catalog rows rather than using a PostgreSQL lower prefilter that can omit legal values; detailed context is loaded only for actual matches. Empty serial sets skip that scan.
- Broader catalog lookup cost is linear in existing identities. Memory is streamed500 at a time plus actual matched identities/candidates. This tradeoff preserves complete correctness on PostgreSQL17 without a forbidden schema/index migration. Own legal capacity remains S3 proof; broader catalog/load optimization is tracked by existing#61, not used to waive the legal maximum.
- S2 still owns ASSETS whole-batch publication/0032 typed sources/current publish-time files/catalog/warnings/late rollback and publication recovery. No part is claimed delivered here.
- S3 still owns operator UI/browser chains and actual2000-target publication capacity. Default-template/legacy UI intermediate sequencing remains as accepted by the reviewer/controller.
- Full MinIO/Azurite/provider suite and exact-head CI remain later shared-source/S2/controller evidence; no cloud acceptance claim.
- Orphans/cancellation/leases/reconciliation stay existing#60; combined asset/lab/analysis load existing#61; real Okta/Azure acceptance existing#18/deployment owners. All three current S1 findings are fixed here, not assigned to those later owners.
- Independent re-review, checkpoint and later gates remain controller-owned. Source fingerprints/working-tree inventory are available for that handoff.

Fix execution explicitly complete. No commit/push/PR/comment/merge or gate advancement. No new blocking question; next entry is independent re-review of these three fixes on the uncommitted S1 tree above a9d2502.
