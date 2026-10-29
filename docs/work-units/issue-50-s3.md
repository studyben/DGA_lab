# Issue50 S3 — operator flow, legal capacity and acceptance mapping

Status: S3 implementation and accepted findings1/2 fixes COMPLETE; ready for independent re-review. See `issue-50-s3-fix.md` for latest source fingerprints and post-review evidence. No review/commit/gate advance by this agent.

## Authority and scope

Active checkout `C:/Users/weila/.codex/worktrees/issue-50-material-import/DGA Lab`, branch `codex/issue-50-device-material-import`; accepted S2 base/unchanged HEAD `6eb7d5e540d288730287ace60cb93679d596a7f6`. Prerequisite main d60dc763 and accepted plan/S1/S2 checkpoints retain controller ownership. Read accepted plan section5/frontend allowlist/S3/commands/docs, frozen issue47/50/design, controller read only, S2 review `code-review-20261029-165109.md`, glossary and TDD/domain-modeling guidance. Previously confirmed goals/seams reused, no re-interview or new contract.

Changes are confined to:

- Frontend asset feature: `AssetImportPage.tsx`, rename `SiteImportPanel.tsx`→`V2ImportPanel.tsx`, `siteImportPresentation.ts`, `siteImportIntent.ts`, `ImportSourcesPanel.tsx`, `EquipmentDetailPage.tsx`, local `siteImport.css`.
- Browser: new `frontend/tests/device-material-import.spec.ts`, synthetic `fixtures/device-material-import.xlsx`; existing `zz-asset-import.spec.ts` selects explicit legacy mode. Existing SITES assertions unchanged.
- Backend tests: `test_device_material_import.py` capacity/bounds/text-identity cases; synthetic `make_device_material_import_fixture.py` generator.
- Docs: bilingual `README.md`, `CONTEXT.md`, `PROJECT_PLAN.md`, this slice artifact/acceptance map.

No backend production/migration/provider/dependency/CI/framework/laboratory/analysis source changed. No other workspace/data edits, controller edits, commit/push/PR/comment/merge/review or gate advancement.

## Owned runtime and restoration

Own existing PostgreSQL17 cluster only: `.cache/issue50-tests/pgdata`, logical test URL `postgresql+psycopg://dga_test@test-db:18550/dga_test`, `PGHOSTADDR=127.0.0.1`; role/database dga_test/dga_test. Before starting, resolved the exact absolute owned path, confirmed no18550 listener or old PID99412, and `pg_ctl status` reported no server. The stale PID file was not manually removed/reseeded. Native startup replayed WAL after the interrupted shutdown. Initial invocation omitted its prior `-o` override and temporarily bound this owned cluster onlocalhost5432; verified exact owned process112372/path, waited for recovery, then hidden `pg_ctl -m fast -w restart -o "-p 18550 -h 127.0.0.1"`. It became ready on18550 as PID124184. Logs `s3-pg-start.stdout/stderr.log`, `s3-pg-restart.stdout/stderr.log`, `postgres.log` record this correction. Cause of previous termination remains unknown; restored behavior is verified, not inferred.

Read-only binaries reused: PostgreSQL under issue-48-site-export `.cache/issue-48-postgres/pgsql/bin`; Python under issue-48-dual-main-sync `.cache/test-venv/Scripts/python.exe`; installed Node/Chrome. No installation or mutation in old runtimes. Docker Desktop was never started. Retained18148/18164/18165 and18448/18464/18465 were never targeted.

First restored-cluster test: transaction/refresh/lost-response/source/current-grant/concurrency/unknown-worker/historical migration selection, `s3-s2-risk-rerun.log`: **39 passed,82 deselected,23.19s**. This closes the S2 review's unavailable local rerun risk for those public seams.

Fresh browser resources in this own cluster: new LOGIN role/database `dga_browser/dga_browser`, URL `postgresql+psycopg://dga_browser@db:18550/dga_browser`. Verified neither existed first. API18570 and frontend18170 were free. Runtime scripts/logs only `.cache/issue50-browser/`. Native app calls existing `create_app(...,file_store=Files())` test injection and shares that memory FileStore with in-process real import/report workers; this is isolated fixture evidence, not a new production provider or real storage acceptance. API final PID95704 (launcher12092); production frontend PID126964; original dev frontend92084 was verified/stopped before production preview. API original26468/launcher8012 was verified/stopped only for the environment correction described below. All helpers start hidden.

Browser setup applied real migrations and existing guarded `tests.seed_browser` only to this fake browser database. The import overlay's single MAT-TX-41 catalog fixture was inserted equivalently with ON CONFLICT DO NOTHING because its standalone seed hardcodes5432. No source guard was weakened. Each linked site→equipment chain retained its data continuously. Only after completed key chains was the own fake baseline reset for the full suite, with controller authorization; a second reset followed the demonstrated native Origin mismatch. Native memory FileStore contents are ephemeral across the API restart, so only the final fresh run is the current browser dataset. This does not claim long-lived object retention or real Azure/Okta behavior.

## Operator behavior

Default `/assets/import` is v2ASSETS; `?mode=SITES` retains v2SITES; `?format_version=1` selects legacy. Batch-only or misleading mode links first read persisted metadata; actual version/mode determines panel/history/source links. Explicit legacy template/upload remains version1, including existing legacy browser assertions.

The renamed panel handles all four sheet types with full-batch NEW/REFERENCE counts,20-row paging, current/original values, source notes, scalar issues and resolved inherited site context. Equipment controls expose site UUID/name only, never site attributes/customer writes. Material decisions/number/model/type can be corrected explicitly; candidate selection still requires saving a reason. Existing equipment candidates link their full details; same-batch candidates retain sheet/key identity. UUID/name warnings identify the adopted UUID; repeated serial warnings explicitly confirm another physical device. Opening a candidate does not check a warning.

Corrections submit only declared editable sheet columns (derived model/type/material details are read-only context). Revalidation/refresh clears confirmations across pages. Disabled publication explains blocking errors, unfinished review, waiting validation or missing confirmations. Errors focus/scroll actionable issues; editing scrolls to its form and retains inputs while unresolved. Notes/raw values wrap within local scroll containers, without global framework/layout changes.1920×1080 evidence was visually inspected: source text, metadata and links remain readable without overlap.

Pending intent key/kind/digest/mode/version/batch is saved before network dispatch, actor/mode-scoped; ASSETS uses a separate namespace from retained SITES. New signatures include mode/version; retained SITES signatures remain retryable.401/403/5xx/network/timeout preserve pending intent. Upload uses actual XMLHttpRequest byte progress; validation/publication are separate states. Recovery queries the durable operation and uses its outcome. An old REFRESHED result remains REFRESHED even when the live batch later becomes PUBLISHED. Published rows retain typed equipment/material links, with formal source panels and exact text material queries. assets.read sees provenance; private batch/original links require assets.import.

## Actual RED/GREEN, commands and evidence

All commands use this checkout explicitly. Common native backend environment:

```powershell
$r='C:/Users/weila/.codex/worktrees/issue-50-material-import/DGA Lab'
Set-Location "$r/backend"
$env:PYTHONUTF8='1'; $env:PYTHONDONTWRITEBYTECODE='1'
$env:TEST_DATABASE_URL='postgresql+psycopg://dga_test@test-db:18550/dga_test'
$env:PGHOSTADDR='127.0.0.1'; $env:PYTHONPATH="$r/backend"
$python='C:/Users/weila/.codex/worktrees/issue-48-dual-main-sync/DGA Lab/.cache/test-venv/Scripts/python.exe'
```

Browser commands run from `$r/frontend`, `BASE_URL=http://127.0.0.1:18170`, `BROWSER_CHANNEL=chrome`, installed `C:/Program Files/nodejs/node.exe node_modules/@playwright/test/cli.js test ...`; own ignored Vite config proxies API18570. C2 is `npm.cmd run build`. Output uses Tee-Object and preserves process exit codes.

| Command selection | Actual evidence |
| --- | --- |
| Browser device spec `--grep 默认` at unchanged6eb7d5e UI | `s3-browser-red-01.log`: genuine RED, expected v2设备物料 template link absent from old legacy default. Trace under `red-results/`. |
| Same selection after first mode-aware panel increment | `s3-browser-green-01.log`:1 passed/1.5s. |
| Linked zero-equipment→equipment→provenance chain | `s3-browser-green-02.log` exposed edit422 from derived context fields; sending declared columns fixes it. `green-02b.log`:1 passed/7.4s. The earlier `red-02.log` crossed dev hot reload and is not claimed as a clean baseline RED. |
| `--grep '响应丢失|重复已发布'` | `s3-browser-recovery-03b.log`:2 passed/3.7s. Earlier03 corrected a test readiness wait and explicit select accessible name; retained honestly. Real publish commits before HTTP response abort. |
| `--grep 旧REFRESHED` | `s3-browser-refreshed-04.log`:1 passed/2.9s; later public publish does not relabel the pending old intent. |
| Backend device test `-k 'exact_500 or 501_in_each'`, `-s` | `s3-capacity-01.log`:5 passed/36.08s. Existing S2 writer already supports approved capacity; no artificial RED or product mutation fabricated. |
| Backend `-k unsafe_assets` | `s3-unsafe-02.log`:10 passed/5.48s. |
| C2 `npm.cmd run build` | `s3-c2-build.log`: tsc --noEmit and Vite production build pass. |
| C4 key: site-import, device-material-import, zz-asset-import specs, `--trace on` | `s3-c4-key.log`:8 passed/16.8s on production build; traces retained for every key flow. |
| C4 full browser suite | First run `s3-c4-full.log`:56 passed/1skip/1failure because unchanged workbench test uses Compose Origin frontend:8080 and native harness initially allowed only18170. No product test/source changed. Added that existing Compose origin to native AUTH_ALLOWED_ORIGINS, restarted only owned API/reset only own fake baseline. Final `s3-c4-full-final.log`: **57 passed,1 existing OIDC fixture skip,52.1s**. |

The one skipped browser protocol fixture requires the existing dedicated OIDC stub/configuration, not supplied by this native fallback; no real corporate Okta acceptance is inferred. Full native backend and configured storage coverage are separately recorded below. C1 uses the exact nine-file selection in the accepted plan; C3 is the complete backend suite, not a filtered substitute.

Screenshots: `.cache/issue50-browser/device-material-detail.png`, `device-source-1920.png`, `device-recovered-publish.png`; original key traces under `c4-key-results/`, final full failures/artifacts under `c4-full-final-results/`. New workbook generator is `python -m tests.make_device_material_import_fixture`, run with this checkout/backend PYTHONPATH; data is explicitly synthetic.

## Final C1/C3 and scope result

C1 exact command after the common environment:

```powershell
& $python -m pytest -q -p no:cacheprovider tests/test_device_material_import.py tests/test_device_material_import_http.py tests/test_device_material_import_migrations.py tests/test_asset_import.py tests/test_site_import.py tests/test_site_import_http.py tests/test_asset_lifecycle.py tests/test_equipment_details.py tests/test_architecture.py
```

Result: **242 passed,4 warnings,140.25s**, `.cache/issue50-tests/s3-c1-focused-final.log`. This includes the final reserved-prefix existing-material reference test.

C3 exact command: `& $python -m pytest -q -rs -p no:cacheprovider`. Result: **582 passed,40 skipped,6 warnings,285.29s**, `.cache/issue50-tests/s3-c3-full-backend-final.log`. The40 skips are exactly26 report-storage,10 storage-contract and4 storage-workflow cases requiring configured MinIO/Azurite (`tests/storage_fixtures.py:29`); they remain an explicit later CI obligation. Warnings are existing Starlette/anyio/Authlib deprecations and deliberate duplicate-ZIP fixture warnings. No failure or additional product fix remains.

`git diff --check` passes; final status contains only the approved S3 paths listed above, including the old/new panel rename and synthetic workbook. HEAD remains `6eb7d5e540d288730287ace60cb93679d596a7f6`. Production frontend files match the successful C2 and final C4 runs. No backend production source or migration changed during S3; no tests were run concurrently against the same test database. Runtime listeners remain owned PostgreSQL18550/PID124184, API18570/PID95704 and built frontend18170/PID126964 for reviewer inspection.

Direct implementation/test entry points: `frontend/src/features/assets/V2ImportPanel.tsx:29` (mode-aware workflow), `:63` (operation recovery), `:71` (persist-before-request mutation/progress); `siteImportIntent.ts:21` (metadata-aware route); `ImportSourcesPanel.tsx:9` and `EquipmentDetailPage.tsx:38` (formal provenance/material detail). Capacity/bounds/text-identity public tests start at `backend/tests/test_device_material_import.py:1102`, `:1148`, `:1163`, `:1206`. Browser chains are in `frontend/tests/device-material-import.spec.ts`.

## Exact legal capacity and safety proof

`test_exact_500_of_each_kind_publishes_and_recovers_all_2000_targets` writes exactly500 NEW customers,500 NEW sites,500 NEW materials and500 equipment roots in one workbook. Every row carries exactly2000 source-note characters; all identities remain legal text. Material numbers begin `NEW:capacity/` and contain slashes. Workbook123920 bytes; actual publication **1.883s**, complete public-interface proof **29.792s** on this local runtime. This is observed evidence, not an SLA.

The test actually publishes, reads all100 preview pages, checks500 typed targets per kind/1500 UUID targets plus500 exact material text keys, all2000 per-row provenance records, all500 material details and all500 equipment details/resolved sites/system numbers. Public dashboard sees501 customers/sites including known baseline1, asset catalog502 including baseline2. Original workbook bytes and same-key operation/retry mappings remain exact; no extra publication appears. A separate named test verifies existing `MATERIAL:NEW:.../...` references and material detail/source preserve the complete reserved-prefix/slash identity without altering that material.

501 rows in each individual sheet yields retained FAILED/actionable issues, publication409 and unchanged public baseline. Unsafe byte/expanded/member/cell/sparse/formula/macro/external/duplicate-member/malformed variants reject safely, preserve retained source bytes where upload is accepted, and create no business facts. Oversized transport bytes413 create no batch. No truncation, stage-only substitution or deferral of the legal maximum to#61.

## Issue50 criterion mapping

| Frozen#50 criterion | Proof / owning slice |
| --- | --- |
| v2 four sheets; explicit NEW/REFERENCE master decisions, existing/same-batch sites/materials | S1 public validation tests; S2 mixed publication; S3 four-table UI/key chain. |
| Equipment only references site UUID/name; no site attribute/customer reassignment | S1 forbidden-column/reference/ID-name tests; S3 editor browser assertion and adopted-UUID confirmation. |
| Material model/type conflicts block, exact text identity, no overwrite/merge | S1 conflict cases; S2 competing-material transaction; S3 reserved-prefix/material detail and explicit reference. |
| Recursive same-batch tree; cycle/missing/position/status/time/depth/repair rules; duplicate serial candidates | S1 public graph/scalar/depth/repair cases; S2 unordered mixed tree/real publication; S3 existing-detail links and explicit different-physical browser review. |
| Entire masters/assets/installations/sources/audit/operation commit or rollback with current grants/revalidation | S2 six late faults/current grant/concurrency/immutableREFRESHED/lostCOMMIT; restored S3 risk rerun39 passed. No S3 backend writer change. |
| Per-row notes/original/reviewed/reason/provenance; originals immutable, existing attributes/history preserved | S1 revision/raw tests; S2 public source/frozen sample/report/history tests; S3 detail/source/original return browser chain and exact2000 source proof. |
| Published-first repeat-file results, reviewed distinct physical device, scoped recovery/permissions/CSRF | S1 duplicate paging/current-auth/HTTP; S2 exact warnings/atomic duplicate keys; S3 real committed-response abort/reload/recovery and repeated-file browser cases. |
|500 of each kind; unsafe limits; legacy v1/SITES/old sample identities and migrations remain valid | S3 actual2000 publish/all pages/details/sources and501/bounds; C4 explicit legacy+SITES; S2 real0013/0030/0031 upgrades/guarded0032 downgrade; final C1/C3. |

Docs decision: extend existing glossary's来源备注 to material/equipment and add物料 as exact text master identity; preserve immutable physical identity/inherited site terminology. No new architecture decision/ADR/provider ownership needed. README has matched concise Chinese-before-English operator/migration/recovery/limit guidance; PROJECT_PLAN records implemented#50 increment without claiming PR/merge/closeout.

## Residual owners and handoff

- Configured MinIO/Azurite contracts remain later exact reviewed-head CI/controller obligation; native/memory evidence is not real cloud acceptance.
- Real corporate Okta/Azure/deployment acceptance retain#18/deployment owners. Native full browser's one existing OIDC-stub skip is explicit.
- Cancellation/leases/orphans/reconciliation remain#60; basic authorization/original retention/atomicity/intent recovery are implemented here.
- Broader retained-history/concurrent combined asset/lab/analysis load remains#61. Exact legal2000 capacity is closed by this unit, not deferred.
- Unknown prior owned-PG termination cause is an environment observation;39 risk tests and final suites on restored cluster are the actual validation. No retained environment was used as fallback.
- No scope/contract blocker or new finding requiring an unauthorized backend change. Controller owns independent review, accepted commit, exact-head CI, PR and later user-authorized closeout.

S3 is explicitly complete with the local emulator/OIDC limitations above, and stops for independent review. No commit/push/PR/comment/merge/controller write or gate advancement was performed. No product/contract blocker remains; later review/CI/closeout remain controller-owned.


## Accepted S3 review findings and fix evidence

Independent review `docs/reviews/code-review-20261029-173510.md` found two current UI recovery defects after the normal-path/capacity results above: unbounded initial metadata read and lost exact pending revision input. Controller accepted both; implementation maps both to **已修复** in `docs/work-units/issue-50-s3-fix.md`, including legal Unicode-bound preservation and safe distinctions for received known stale/already-published409 versus unknown outcomes.

Post-review core fix evidence: metadata3pass, exact recovery/storage/legacy targeted10pass, C2 pass, key C4 **18passed58.4s**, full C4 **67passed/1existingOIDCfixture skip (1.5m)**. That full run precedes the finite Unicode/known409 follow-ons. Latest source build passes C2 and latest affected F2 **11passed11.9s**; only affected tests repeated per controller direction. The fix artifact records exact commands/logs, all intermediate RED/failures, final fingerprints, scope and runtime corrections. Do not interpret the prior242/582/57 runs as tests of the new code or inflate the full-run count with later targeted cases.

Backend production/migration/capacity files are unchanged by this fix; original exact2000-row proof and backend suites remain valid prior evidence without rerun. Final owned runtime is PostgreSQL18550/PID99080, API18570/PID95704 and built frontend18170/PID126964. API/memory FileStore were not restarted during the fix. One own-fake baseline reset occurred only after complete key chains for the required full browser suite, never during linked stages or against retained data. No commit/PR/gate advancement; independent re-review is the next controller entry.
