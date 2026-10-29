# Issue #50 / BI-03 — S1 implementation

## Status and reviewed target

Gate: implementation S1 only. Status: implementation complete; final after-fix validation passed (168 tests and C2 build). No independent review/commit/gate advancement is claimed.

Checkout: `C:/Users/weila/.codex/worktrees/issue-50-material-import/DGA Lab`.
Branch: `codex/issue-50-device-material-import`.
Base and unchanged Git HEAD: `a9d250248cd02b683a969a495150bad1a8a5def7` (accepted goal/plan/independent plan review); changes are uncommitted working-tree changes above that base. Source prerequisite remains merged main `d60dc7633b0294d5b8630e6b18284f0f788c995e`.

Read accepted `docs/work-units/issue-50-plan.md`, `docs/reviews/plan-review-20261029-151813.md` and current read-only G: controller. Used `C:/Users/weila/.codex/skills/tdd/SKILL.md`, tests.md and mocking.md, with already-confirmed public AssetImports/AssetDirectory/lifecycle and HTTP security seams; no repeated seam/goal interview. Each behavior increment had a real public-facade/HTTP RED before implementation. No private business-table shape success test or React internal test was added.

## What is implemented

- Exact input/persisted `(1,ASSETS)/(2,SITES)/(2,ASSETS)` dispatch. New default template is marked v2 ASSETS; omitted upload version remains legacy; explicit v1 download remains unchanged in content/assertions. Unsupported persisted modes cannot fall into the SITES writer.
- Private coordinator/parser renamed to V2Imports/v2_import_workbook; SITES validation accepts a caller snapshot while its old policy stays intact. v2 parser supports the four fixed schemas, required headers, allowed empty optional sheets, independent 500-row bounds, retained failures, and existing archive protections.
- Asset-owned new material/equipment validator: explicit MATERIAL:number/NEW:key and UUID/NEW:key references, no last-row choice for ambiguous keys, material conflicts/controlled types, no equipment customer/site attribute writes, actionable raw-value issues, distinct stable issue IDs and `summary.by_kind` counts.
- Unordered recursive initial equipment trees: missing/duplicate/self/cyclic parent, legal100/illegal101-node depth, product-line/time/status/position rules, SITE-only ancestry, repair-center rows and inherited-site consistency. Correct-ID/name disagreement is a specific warning; source notes remain independent of identity and preserve whitespace/newlines.
- Existing and same-batch duplicate serial candidates include formal IDs/system numbers/model/material/type, customer/site/location and ancestor lifecycle context. Candidate changes invalidate the warning evidence; no automatic binding/merge/skip occurs. ASSETS duplicate-file history is complete and paged20 at a time, with published results prioritized and actual mode/version preserved.
- Current import authorization for staging reads/mutations; actor-scoped persistent upload/revision results and additive operation_result responses. Concurrent same revision intent applies once; later live changes do not overwrite an earlier stored result. Lost durable COMMIT response recovers exact source and result using original key.
- Worker takes asset110011 before batch claim, uses REPEATABLE READ, commits preview/revision together, rolls technical faults back to a retained FAILED result and retries serialization/deadlock contention. Restored parsed rows can be revised/revalidated; successful validation clears obsolete failure_code.
- Transport supports Assets/Materials revisions, 2000 changes/max20 values, duplicate_page and the new default template filename. Existing CSRF/MIME/auth/no-store/generic error behavior remains; ASSETS audit actions are ASSET_IMPORT_SUBMIT/REVISE/SOURCE_DOWNLOAD. SITES action values remain unchanged.

Temporary publication guard is mandatory and still active: v2 ASSETS publish returns409 `{code:'import_mode_not_publishable'}` after current authorization and BEFORE any business writer. No v2 ASSETS material/equipment/customer/site publication capability, source schema expansion or migration0032 exists yet. Existing v1 and SITES publication paths remain and pass regressions.

## Changed-file ownership

- `backend/dga/assets/imports.py`, `import_http.py`: version/mode facade, worker, current staging reads, HTTP schemas/defaults/paging.
- Renamed `backend/dga/assets/site_imports.py` -> `v2_imports.py`: retained workflow mode dispatch, durable revision responses, duplicate history, audit, guard.
- Renamed `backend/dga/assets/site_import_workbook.py` -> `v2_import_workbook.py`: fixed v2 sheets/headers/safe parsing and usable ASSETS instructions.
- `backend/dga/assets/site_import_validation.py`: renamed parser import and optional snapshot only.
- New `backend/dga/assets/asset_import_validation_v2.py`: asset-owned material/equipment preview policy.
- New `backend/tests/test_device_material_import.py` and `test_device_material_import_http.py`: public behavior and transport/security proof.
- `backend/tests/test_asset_import.py`, `test_site_import.py`: only explicit version1 template selection; original Materials/reference/no-Format/business assertions retained.
- This slice evidence `docs/work-units/issue-50-s1.md`.

No lifecycle/public/query semantic change, import_validation helper extraction, UI source, business docs, dependency manifest/lockfile, provider, CI, controller or migration change. No original G:/#49/#48 workspace/data mutation. Test/runtime artifacts are ignored and not commit candidates.

## Dedicated native runtime and exact commands

Docker Desktop was not started/restarted. Existing binaries/runtime were used READ ONLY:

- PostgreSQL17.6 bin: `C:/Users/weila/.codex/worktrees/issue-48-site-export/DGA Lab/.cache/issue-48-postgres/pgsql/bin`.
- Python: `C:/Users/weila/.codex/worktrees/issue-48-dual-main-sync/DGA Lab/.cache/test-venv/Scripts/python.exe`.

New resources belong only to this checkout:

- Cluster `.cache/issue50-tests/pgdata`, init log `.cache/issue50-tests/initdb.log`, server log `.cache/issue50-tests/postgres.log`.
- Bound only127.0.0.1:18550; verified free before bootstrap. Observed server PID99412, matching postmaster.pid and listener. Preserve cluster for subsequent authorized slices.
- Bootstrap initdb `-D <this cluster> -U issue50_admin -A trust --encoding=UTF8 --locale=C`; hidden pg_ctl start with this data dir/log and `-o "-p 18550 -h 127.0.0.1"`. CREATE ROLE dga_test LOGIN CREATEDB; CREATE DATABASE dga_test OWNER dga_test. This local test role is isolated; no retained DB URL/port was used.
- Python env: TEST_DATABASE_URL=`postgresql+psycopg://dga_test@test-db:18550/dga_test`, PGHOSTADDR=`127.0.0.1`, PYTHONPATH=`<this checkout>/backend`, PYTHONUTF8=1; final runs also PYTHONDONTWRITEBYTECODE=1. Conftest validates logical test-db/dga_test/dga_test and runs real migrations through existing0031. Historical regression cases use their own schemas, not stamps/shared downgrade.
- Fresh `frontend/node_modules`, npm cache `.cache/issue50-tests/npm-cache`, Node24.11.1. No mutable dependencies of retained workspaces were reused.

Exact final backend invocation from this checkout/backend:

```powershell
$env:TEST_DATABASE_URL='postgresql+psycopg://dga_test@test-db:18550/dga_test'
$env:PGHOSTADDR='127.0.0.1'
$env:PYTHONUTF8='1'
$env:PYTHONPATH='C:/Users/weila/.codex/worktrees/issue-50-material-import/DGA Lab/backend'
$env:PYTHONDONTWRITEBYTECODE='1'
& 'C:/Users/weila/.codex/worktrees/issue-48-dual-main-sync/DGA Lab/.cache/test-venv/Scripts/python.exe' -m pytest -q -p no:cacheprovider tests/test_device_material_import.py tests/test_device_material_import_http.py tests/test_site_import.py tests/test_site_import_http.py tests/test_asset_import.py tests/test_asset_lifecycle.py tests/test_equipment_details.py tests/test_architecture.py --tb=short
```

Exact C2 from this checkout/frontend:

```powershell
& 'C:/Program Files/nodejs/npm.cmd' ci --cache 'C:/Users/weila/.codex/worktrees/issue-50-material-import/DGA Lab/.cache/issue50-tests/npm-cache' --no-audit --no-fund
& 'C:/Program Files/nodejs/npm.cmd' run build
```

C2 passed:28 packages installed only in this checkout; TypeScript noEmit and Vite8.2.2 production build passed. Logs `.cache/issue50-tests/s1-npm-ci.log`, `s1-frontend-build.log`. No global npm update was performed.

## Red/green evidence

All logs below are under this checkout `.cache/issue50-tests/`. Targeted commands used the same Python/env above with the specific test file/`-k` expression recorded in the commands/tool history; logs contain actual failure and pass counts.

| Increment | Genuine RED | GREEN |
| --- | --- | --- |
|01 default template + retained root | s1-red-01.log:1fail, missing Format sheet | s1-green-01.log:1pass |
|02 mixed same-batch refs | red-02:1fail, missing material rows (5 vs7) | green-02:2pass |
|03 material decisions/forbidden fields | red-03:8fail, absent conflicts or generic header error | green-03:10pass |
|04 scalar/time/site-ID | red-04:14fail/5pass | green-04-corrected:19pass; the first post-implementation check exposed a new test's expected-field lookup error for a line change, corrected to the actual submitted site_id without weakening business assertions |
|05 tree/positions/depth | red-05:9fail/4pass | green-05:13pass |
|06 serial/file candidates | red-06:2fail | green-06:2pass |
|07 revision/recovery/current auth/worker | red-07:4fail/1pass | green-07:5pass |
|08 HTTP | red-08:2fail (old default and Assets revision rejected) | green-08:2pass |
|09 schema/issues/counts | red-09:3fail/3pass | green-09:6pass |
|10 instructions/audit | red-10:1fail (ASSETS references absent from instructions) | green-10:1pass |
|11 strict dispatch/ambiguous refs/context | red-11:2fail/6pass (last-row choice, ancestor change left warning ID unchanged) | green-11:9pass including strengthened current actor-key ownership proof |
|12 technical-failure recovery | s1-red-12-recovery.log:1fail, successful recovery retained validation_unavailable | final cumulative run below proves cleared failure_code and original retention |

An initial s1-red-12.log was a passing diagnostic before the extra recovery assertion was actually inserted; it is not counted as a RED. The checked insertion then produced the genuine s1-red-12-recovery.log failure. The first UTF-8 editing attempt also failed on Windows' default cp1252 after file renames; explicit UTF-8 completed it before any GREEN claim.

Cumulative earlier results: s1-focused-regression-01.log160passed; s1-focused-regression-final.log168passed,3warnings,69.79s before the final one-line stale-failure-code fix. Current final result/log: 168 passed,3 expected warnings,68.50s (after the stale-failure-code fix) in `s1-focused-regression-final-recovery.log`. Warnings are existing Starlette/httpx and anyio deprecations plus the intentional duplicate-ZIP fixture warning, not hidden failures.

Public proof includes: zero new ASSETS business entities; old IDs/history/source bytes intact; valid referenced and recursive preview; material/site conflicts; no silent serial merge; current warning facts; same-intent/raw-revision/lost-COMMIT recovery; actor-key isolation/current grants/CSRF; technical failure plus repair; real legacy/SITES migration regressions; architecture direction. No new0032 or S2 transaction writer has been executed or inferred tested.

## Docs decision and classified residuals

Business README/CONTEXT/PROJECT_PLAN/UI documentation is unchanged by explicit S1 dispatch. Template instructions are part of this slice's actual public file contract; only this implementation artifact records delivery evidence.

| Residual / uncovered | Classification / owner |
| --- | --- |
| v2 ASSETS formal publication,0032 typed provenance/source queries, publication warning/file/catalog refresh and atomic late-failure/concurrent publish tests | Covered by later approved S2; #50 owner. Temporary409 guard remains until reviewed S2. |
| Operator UI/mode-aware links/browser recovery and exact2000-target publication capacity | Covered by later approved S3; #50 owner. C2 build is not a completed browser flow claim. |
| Full MinIO/Azurite/FileStore integration suite | Covered by later approved S2/shared-source validation and exact-head CI; controller. Native local seam uses controllable Files adapter, no Azure acceptance claim. |
| Full0013/0030/0031-to0032 upgrade/guarded downgrade proof | Covered by later approved S2; #50 owner. Existing0030->0031 regression passed here;0032 does not exist yet. |
| Long-lived orphan/cancel/lease/reconciliation | Existing#60, asset import owner; basic S1 original retention and same-intent safety are implemented, not deferred. |
| Combined asset/lab/analysis load | Existing#61, later acceptance owner; own legal maximum publication stays S3. |
| Real Azure/Okta deployment | Existing deployment/#18 acceptance owners; native tests do not establish it. |
| Independent review/checkpoint/aggregate review/draft PR/CI | Controller's next gates; none performed or advanced by this implementation agent. |

No unresolved scope/contract blocker. Retained environments18148/18165/18164 and native retained database ports18448/18464/18465 were never targeted. No commit/push/PR/comment/merge or controller write. Next controller entry is independent S1 code review against the uncommitted working tree above a9d2502, then its required fix/re-review/checkpoint, not S2 implementation by this agent.

## Accepted-review fix follow-up

The independent review found three accepted S1 defects. They are now fixed with genuine public RED/GREEN and final184passed/3warnings/76.63s; see `docs/work-units/issue-50-s1-fix.md` and `.cache/issue50-tests/s1-fix-focused-regression.log`. This is the latest current-tree result; the168-pass record above is historical pre-review evidence. Independent re-review remains pending; no checkpoint or gate advancement by this agent. C2 was not repeated because frontend/dependencies are unchanged.
