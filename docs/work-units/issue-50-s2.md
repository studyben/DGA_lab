# Issue50 S2 — atomic publication, provenance and recovery

Status: S2 implementation COMPLETE, ready for independent review. No review/gate advancement or commit is performed by this slice agent.

## Authority, base and scope

- Checkout: `C:/Users/weila/.codex/worktrees/issue-50-material-import/DGA Lab`; branch `codex/issue-50-device-material-import`.
- Reviewed/implemented on accepted S1 HEAD `94441c86e6c1626f83597bacb0b69468b0387cb0`, unchanged throughout this slice. Prerequisite main base `d60dc7633b0294d5b8630e6b18284f0f788c995e` and accepted plan commit `a9d250248cd02b683a969a495150bad1a8a5def7`.
- Dispatch: S2 only after accepted S1 re-review. Read controller (read only), frozen bulk-data-import design, issue47/50 snapshots, accepted plan sections3–4/6/S2/8–10 and TDD guidance. Confirmed user decisions were reused; no new interview or contract substitution.
- This slice removes the S1 `import_mode_not_publishable` guard with the full transaction/file/current-authority/catalog/warning/operation guarantees. No UI/S3, laboratory/analysis writer, provider/dependency redesign, old migration edits or original workspace/data changes.

## Changed files and ownership

| File | Change |
| --- | --- |
| `backend/migrations/versions/0032_device_material_import.py` | Additive source typed-target/check/FK/confirmation extension; protected downgrade. |
| `backend/dga/assets/import_persistence_v2.py` | Asset-owned connection-bound customer/site/material/equipment/installation/source writer and stable full target mapping. |
| `backend/dga/assets/v2_imports.py` | Current-authorized whole publication, original/candidate/catalog revalidation, exact ASSETS warning IDs, immutable operation outcomes and ASSET audit. SITES writer delegates without changing its decisions. |
| `backend/dga/assets/public.py` | Exact text material detail and paged ASSET/MATERIAL formal provenance beside existing SITE/CUSTOMER readers. |
| `backend/dga/assets/http.py` | Three formal read routes, no-store and safe SQL-error transport mapping. |
| `backend/dga/assets/import_http.py` | Accepted warning-list transport limit12000; no legacy blanket acknowledgment shortcut for ASSETS. |
| `backend/tests/test_device_material_import.py` | Public S2 behavior/fault/concurrency/recovery/history tests. Only obsolete S1 publish409 assertions removed; all staging/no-business assertions preserved. |
| `backend/tests/test_device_material_import_http.py` | S1 guard expectation becomes successful publication; formal read vs private-import/session/no-store/security coverage. |
| `backend/tests/test_device_material_import_migrations.py` | Real0013/0030/0031 upgrade fixtures and guarded0032 downgrade, using disposable historical schemas. |
| `README.md` | Backend contract, schema and unknown-outcome/forward-recovery notes; explicit following-slice UI boundary. |
| `docs/work-units/issue-50-s2.md` | This implementation evidence. |

No change to source parser/validator semantics, public lifecycle commands, laboratory/analysis boundaries, provider settings, dependency locks or controller. No commit/push/PR/comment/merge, acceptance migration/reseed or gate transition.

## Runtime namespace and commands

Reused the dedicated S1 native PostgreSQL17 cluster only: `127.0.0.1:18550`, data `<checkout>/.cache/issue50-tests/pgdata`, server log `.cache/issue50-tests/postgres.log`; role/database `dga_test/dga_test`, logical host `test-db`. Retained environments18148/18165/18164 and ports18448/18464/18465 were never targets. Docker Desktop was not started/restarted.

Read-only binaries:

- Python: `C:/Users/weila/.codex/worktrees/issue-48-dual-main-sync/DGA Lab/.cache/test-venv/Scripts/python.exe`.
- PostgreSQL: `C:/Users/weila/.codex/worktrees/issue-48-site-export/DGA Lab/.cache/issue-48-postgres/pgsql/bin`.

Every test command ran serially from this checkout's `backend`, with:

```powershell
$r='C:/Users/weila/.codex/worktrees/issue-50-material-import/DGA Lab'
Set-Location "$r/backend"
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:TEST_DATABASE_URL='postgresql+psycopg://dga_test@test-db:18550/dga_test'
$env:PGHOSTADDR='127.0.0.1'
$env:PYTHONPATH="$r/backend"
$python='C:/Users/weila/.codex/worktrees/issue-48-dual-main-sync/DGA Lab/.cache/test-venv/Scripts/python.exe'
```

Invoke `& $python -m pytest -q -p no:cacheprovider <selection>` and pipe combined output to the corresponding `.cache/issue50-tests/<log>` with `Tee-Object`, preserving `$LASTEXITCODE`. C3 additionally uses `-rs`. All logs are retained under this ignored, slice-owned cache. No old venv/node_modules/runtime was modified.

## Actual RED → GREEN and incremental evidence

| Selection after common pytest command | Log | Actual result |
| --- | --- | --- |
| `tests/test_device_material_import.py -k atomic_mixed_batch` at94441c8 | `s2-red-01.log` | Genuine behavioral RED: mixed new customer/site/material plus unordered root/child/grandchild/repair/existing references raises S1 `import_mode_not_publishable`409;1 failed. |
| Same mixed public test after writer/migration | `s2-green-01.log` |1 passed/1.63s; complete formal tree/material/provenance/targets and immutable original. |
| `tests/test_device_material_import_http.py -k formal_material` before formal routes | `s2-red-02.log` | Genuine route RED:404 instead of authenticated401;1 failed. |
| Full `tests/test_device_material_import_http.py` after routes | `s2-green-02.log` |3 passed/3.16s. |
| Device test `-k 'duplicate_serial_and_file or refreshed_intent'` | `s2-validation-03.log` |2 passed/1.95s; exact confirmations, explicit distinct physical IDs, immutable REFRESHED. |
| Device test `-k 'late_publication or source_integrity or lost_publication'` | `s2-validation-04.log` |10 passed/5.62s; six late transaction faults, three original-store faults, actual committed/lost response. |
| Device test `-k 'publication_refreshes or concurrent_upload or competing_new_material'` | `s2-validation-05.log` |11 passed/6.38s; eight catalog/candidate changes plus same/different intent and competing-material concurrency. |
| Device test `-k 'rechecks_current or concurrent_revoke or finalized_laboratory'` | `s2-validation-06b.log` |4 passed/3.90s; stale grants, disabled actor, identity-lock race and immutable sample/report. |
| `tests/test_device_material_import_migrations.py` initial group | `s2-migrations-07.log` |8 passed/7.56s. |
| Migration+device `-k 'historical or 0031 or 0032 or zero_equipment or paged_targets or identical_revision or finalized_laboratory'` | `s2-validation-08b.log` |13 passed/10.49s; final9 migration cases, zero-equipment site/material, all21 typed targets, concurrent identical revise and frozen history. |

Intermediate `s2-validation-06.log` (2failed/2passed) and `s2-validation-08.log` (2failed/11passed) are retained honestly as test-construction corrections, not missing-feature RED: operation results are actor-scoped/direct objects; the asset query is `equipment_detail`; material-only files lack the accepted required Sites-or-Assets business row; ESS site detail requires `product_line=ESS`. Corrected tests use those existing contracts, with no product widening or production workaround.

C1 exact selection:

```powershell
& $python -m pytest -q -p no:cacheprovider tests/test_device_material_import.py tests/test_device_material_import_http.py tests/test_device_material_import_migrations.py tests/test_asset_import.py tests/test_site_import.py tests/test_site_import_http.py tests/test_asset_lifecycle.py tests/test_equipment_details.py tests/test_architecture.py
```

Result: **225 passed,3 warnings,107.23s**, `s2-c1-focused.log`. Warnings are existing Starlette/httpx/anyio deprecations and the deliberately malformed duplicate-ZIP fixture warning, not assertion failures.

C3 exact command: `& $python -m pytest -q -rs -p no:cacheprovider`. Result: **565 passed,40 skipped,5 warnings,245.04s**, `s2-c3-full-backend.log`. The40 skips are exactly26 report-storage,10 storage-contract and4 storage-workflow cases requiring configured MinIO/Azurite (`tests/storage_fixtures.py:29`). Native PostgreSQL/memory-FileStore behavior passed; configured unchanged-provider contract execution remains the later controller/CI obligation. Warnings are existing Starlette/anyio/Authlib deprecations and the intentionally duplicate-ZIP fixture.

After C1/C3, final evidence inspection found the corrupt-original case only exercised changed size. A test-only fourth parameter adds same-length byte corruption, proving SHA rejection independently of size. Final command `& $python -m pytest -q -p no:cacheprovider tests/test_device_material_import.py -k source_integrity` passed **4 tests/2.98s** (`s2-integrity-final.log`). No production code changed after C1/C3. Counts above are the actual broad runs before that one added parameter, not inflated combined results.

Frontend C2 is unnecessary here: no frontend/build changes; S1 C2 remains accepted evidence, S3 owns the new operator flow.

## Public behavior and transaction proof

`backend/dga/assets/v2_imports.py:160` (`V2Imports.publish`) owns one `engine.begin()` context; lock ordering is in `v2_imports.py:40` and the unchanged current-auth owner `backend/dga/shared/auth/public.py:244`. Its `lock` first calls current `IdentityService.authorize_current` (shared identity30003), then takes asset110011; the coordinator locks the batch, then `asset_materials,customers,sites,site_product_lines` in that fixed order. Public identity revocation uses the exclusive identity lock and demonstrably waits while a publication pauses at the FileStore read; publication commits under the still-current grant, then revocation completes. A post-commit response read can correctly see the later denial; the successful durable intent remains recoverable after restoring the actor's grant. Another admin cannot retrieve that actor's operation.

Before first publication `_content` reads the real configured FileStore interface and checks actual size/SHA. The full current preview compares both normalized rows/issues and the catalog/candidate/duplicate fingerprint. Relevant changes persist a new revision and REFRESHED outcome with empty targets; no masters/equipment/sources are created. A prior REFRESHED key retains that exact result after a later key publishes, even when the returned live batch is now PUBLISHED. Missing/extra warning IDs, old blanket bool, stale revisions and conflicting same-key payloads cannot authorize a write.

`backend/dga/assets/import_persistence_v2.py:11` (`create_batch(c,...)`) receives that same connection and never opens/commits a transaction or calls separately committing lifecycle mutations. It allocates customer/site/equipment UUIDs, inserts NEW masters only, creates all equipment before parent relations, writes resolved material/site/parent identities and original/reviewed evidence, and retains row/global warning IDs in source provenance. Material targets use their exact number in `target_key`; UUID target_ids exclude materials. Stable source order maps every row, including REFERENCE records, beyond the20-row preview page. Existing references gain per-batch provenance without modifying original master attributes/notes/history.

Graph validation, batch PUBLISHED state, final ASSET_IMPORT_PUBLISH audit and the operation insertion are in the caller transaction. Fault injection is at SQLAlchemy's database transport boundary after masters/second equipment/second relation/second source/final audit/final operation; all public master counts/catalog/material lookups/batch state/operation lookup remain baseline and original bytes survive. Removing each fault permits the same key to succeed once. A wrapper that actually commits before raising proves unknown-COMMIT recovery through public operation/target/source/original reads, not a pre-commit exception simulation.

Mixed publication covers same-batch/new and existing sites/materials, REFERENCE provenance, dual-line declared site capacity, recursive unordered tree, inherited site and standalone repair transformer. Within-batch duplicate serials remain21 distinct physical UUID/system numbers after all current warnings are reviewed. Concurrent same/different publication keys produce the same full mapping once; two proposed material numbers competing concurrently yield one PUBLISHED and one REFRESHED/conflicting preview with no upsert or partial masters. Concurrent identical revise creates one revision.

Formal material/detail/source readers require assets.read, preserve slash-containing text identities, use paged sources and expose batch mode/version/reason/original/reviewed/confirmation evidence. Private batch/raw original access still requires assets.import. New HTTP routes use no-store and safe SQL-error shapes; existing write session/Origin/CSRF/strict-body behavior remains covered by the focused legacy/SITES/HTTP regressions.

## Migration and original integrity

`backend/migrations/versions/0032_device_material_import.py:10` upgrades and `:24` guards downgrade.0032 follows0031; no historical migration is edited. Only provenance extends: nullable UUID target_id, VARCHAR(120) material target_key FK, exclusive kind/target CHECK, confirmed_warning_ids JSONB array/default[] and material-source index. Existing rows receive empty confirmation lists; no invented approvals or material UUID conversion.

Real migrations run from0013_asset_import,0030_merge_export_identity and0031_site_import in conftest-owned `historical_<uuid>` schemas. Pre-upgrade fixtures use actual historical SQL for users/master assets/installations/materials/sample snapshot/container and v1 STAGED/VALIDATED/PUBLISHED batches plus retained original bytes. After real upgrade head, public readers retain IDs/system numbers/results/source bytes/snapshot/container; old drafts continue v1 validation/publication; fresh ASSETS publishes.0031 additionally performs actual SITES review/publication before upgrade and resumes a pending SITES batch afterward. Safe0032→0031→0032 preserves SITES sources/revision/original;0031's own retained-v2 guard remains enforced.

Any retained ASSETS-v2 STAGED/VALIDATED/FAILED/PUBLISHED batch prevents0032 downgrade; published material remains queryable and source bytes/batch results unchanged after refusal. Empty disposable schema downgrade/re-upgrade passes. No shared head/acceptance schema is stamped or downgraded. Existing finalized laboratory sample/workbench/asset snapshot/lifecycle/report metadata/readable bytes compare equal before/after ASSETS publication through public readers; no lab/analysis code changed.

## Residual classification and completion

| Item | Classification / owner |
| --- | --- |
| S3 UI/editor/candidate/warning/recovery UX, key browser workflows and exact legal maximum2000-row end-to-end publication | Accepted following-slice scope; S3 agent/controller. S2 proves complete21-row mapping, not maximum-capacity acceptance. |
| Full-catalog Unicode candidate scan and graph validation at large retained history/concurrency | Existing broader load risk#61 plus S3 legal-capacity proof; no correctness exception or ASCII restriction introduced. |
| Upload orphan cleanup/cancellation/leases | Existing#60; unknown commit intentionally retains original evidence. |
| Configured MinIO/Azurite storage contracts / exact reviewed head CI | Local environment availability limitation; controller/CI must run configured unchanged-provider contract suite. No emulator or real Azure acceptance is fabricated. |
| Real Azure production service and real Okta corporate integration | Existing external/provider and#18 owners; native/memory/isolated protocol tests are not that acceptance. |

No unresolved product/contract blocker. Final scope verification: only the11 files listed above differ/add from94441c8; `git diff --check` succeeds (only the existing Git LF→CRLF advisory for the HTTP test file). HEAD remains `94441c86e6c1626f83597bacb0b69468b0387cb0`. S2 is complete with the explicit local emulator limitation; the agent stops for independent review without review/commit/gate advancement. No new broad run is needed after the final test-only integrity parameter: its affected group is green and production files match the C1/C3 runs.
