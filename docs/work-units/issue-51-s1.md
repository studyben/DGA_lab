# Issue #51 S1 implementation evidence

Gate: accepted-plan S1 implementation — COMPLETE, awaiting independent S1 deepreview.
Date: 2026-10-29.
Checkout R: C:/Users/weila/.codex/worktrees/issue-51-finalization-facts/DGA Lab.
Branch: codex/issue-51-finalization-facts.
HEAD remains115ba812b6c85142e387ea5a24101ab3341de251 (accepted5-doc plan checkpoint); production parentfcea999e313db51461cd9aefda66d70e6e34ed3b. No commit/stage/push/PR/comment performed.

## Delivered scope and ownership

S1 adds immutable per-token laboratory facts and safe v1 migration while preserving ordinary autoqueued reports. It does NOT implement S2 NO_REQUEST, new trend-reader source, analysis DTO/serializer changes, report-page changes, external imports or date-only writes.

Changed production:
- backend/migrations/versions/0033_lab_finalization_facts.py: additive0032 successor; per-sample/token facts, v1 raw copy/current-token-only backfill, new v2 identity consistency, immutable UPDATE/DELETE trigger, populated downgrade refusal/empty downgrade support. Existing migration files/merge nodes untouched.
- backend/dga/laboratory/finalization_facts.py: one private owner for v2 full-active capture, strict typed v1/v2/envelope/method-unit consistency, explicit legacy unknown inventory, immutable serialized decoded values and old-schema1 PDF projection. Attachment metadata only; no attachment bytes/keys in facts.
- workbench.py: current public get_current_finalization view; identity-before-config/sample lock guard for finalize/withdraw; fact INSERT before ordinary queue; safe audit details; share-locked sample read through current-fact lookup prevents withdrawal racing a stale AVAILABLE response.
- reports.py: queue copies saved facts and checks warning/time agreement; snapshot assembly removed here. Retry current-authorizes and keeps existing saved delivery snapshot/generation semantics. Worker/file/current claim behavior and renderer unchanged.
- public.py exports only the new typed view, not the private fact implementation.

No production changes in assets, condition_analysis, trends.py, HTTP/UI, shared auth, report renderer/worker/provider, CI or prior migrations. Existing analyst laboratory.finalize grant remains and is tested through a real analyst/current authorization changes.

Tests/helpers:
- capture_finalization_legacy.py and fixtures/finalization_legacy/v1/{cases,manifest,pdfs}: mandatory real unchanged-producer capture.
- finalization_legacy.py: guarded owner-storage fixture arrangement preserving IDs/data, portable text attestation and exact PDF-byte checks.
- test_finalization_facts.py:13 cases for public inventory/frozen projection/DB-task-audit rollback/current authorization/immutable historical token/stale worker/current-view race.
- test_finalization_facts_migrations.py:22 cases for actual old/current v1 producers, malformed raw snapshots with independently intact READY bytes, guarded downgrade and lawful0006 tokenless coexistence through3 public analysis facades.
- Existing historical workbench test changes only legitimate old arrangement; assertions for0006 downgrade→OPEN, same test ID/unselected public readback retained.

Docs: narrow CONTEXT glossary, PROJECT_PLAN/README S1 status and ADR0010. Original G: files/controller/accepted plan/reviews unchanged.

## FIRST hard checkpoint: actual parent/old-v1 corpus before source edits

A new own PostgreSQL17 cluster was initialized only at R/.cache/issue51-tests/pgdata, loopback18551. Verified actual SQL current_user=dga_test, current_database=dga_test, inet_server_port=18551; postmaster PID45160/data path/port match. No old/#50 cluster was used. PG binaries were read-only reused from issue48-site-export; Python from issue48-dual-main-sync.

The helper was added/run BEFORE any laboratory production/migration diff. It refused producer/migration drift against fcea999e, read exact old71d8a9e23a4e2428937f604b8ef8e24c4fe272de Reports blob12f2801b61df73b3d6e28003993a98653b2b0db7, and called actual public parent Workbench/Reports/TrendSource/ReportWorker on real0032 PG.

Run (R/backend, own test env below):
    python -m tests.capture_finalization_legacy --expected-parent fcea999e313db51461cd9aefda66d70e6e34ed3b --output tests/fixtures/finalization_legacy/v1

Log: .cache/issue51-tests/capture-v1.log. Successful9 observed cases /7 stored PDFs: DGA, repeated adopted MOISTURE with acknowledged unselected QA evidence, mixed types/ND/LT/GT, real historical71 producer omission of configuration/quality_evidence, failed/queued report, withdrawal and different-token refinalization. The manifest records fcea caller and separate report producer71 provenance; it does NOT claim running the entire71 application. No positive report snapshot was hand edited. Pre-refinalization/withdrawn snapshots are marked historical observations, not falsely current facts.

The very first helper invocation used an incorrect backend/backend relative output path and failed before creating a file or running producer logic. Corrected to backend-relative tests path; the successful capture above preceded production edits. This setup mistake is not a RED/GREEN claim or historical data evidence.

### Hash definitions and portability correction

The original console/manifest cases_sha256 initially hashed UTF8 LF-normalized text, while Windows Path.write_text produced CRLF bytes. Root independently detected the distinction; only hash names/manifest definition/helper were corrected. Original cases.json/PDF bytes were NOT rewritten.
- cases_text_sha256 (UTF8 text after universal-newline LF normalization): fecba7efa983220d2409dfe48c84f35e144c53c28470266e843611b104127261.
- captured_cases_file_sha256 (original Windows capture bytes, provenance only):334c432b27d907f6ce9ead2ef202df08c0311be31e0d82ec7a13912b9c1d4a00.
- Actual current cases.json byte SHA remains the latter value. Linux Git checkout may use LF; loader checks portable normalized text hash, NOT equality to the original Windows raw-byte hash.
- All7 PDFs are checked by their exact raw SHA/size. A fixture-local .gitattributes declares pdfs/*.pdf -text; read-only git check-attr confirmed text:unset. No root/global attribute change or PDF rewrite.
- Current manifest byte SHA:46df938dbfa04ef7b74012cba8fd7148deaf213e2e403b5b0ae6814d2c23bb4a.

## Actual TDD and corrective loops

| Log under .cache/issue51-tests | Actual observation |
| --- | --- |
| s1-fact-view-red.log |1 failed: public get_current_finalization absent (AttributeError), before new production implementation. |
| s1-fact-view-green-01.log | Collection failed on moved helper's missing Connection type import; corrected imports, not counted as a behavioral RED. |
| s1-fact-view-green-02.log |1 passed1.67s, full-active/adopted/warning/current-token/ordinary report projection public proof. |
| s1-historical-arrangement-red.log | Real inherited0024 test failed because new writer attempted absent0033 table. |
| s1-historical-arrangement-green.log | First replacement exposed actual retained quality from fcea caller. Did NOT clear that saved quality to force downgrade. |
| s1-historical-arrangement-green-02.log |1 passed2.02s after lawful real0007 arrangement→upgrade0024→original laboratory branch downgrade/OPEN/readback. |
| s1-fact-failures-01.log |8 passed4.90s, late queue/audit/DB failures, old worker, immutable retained token, initial stale-actor/frozen-copy cases. |
| s1-legacy-corpus-02.log |21 passed13.73s, producer/current v1 states, old PDF bytes, malformed candidates, empty/populated guards and real tokenless coexistence. |
| s1-config-consistency-red.log |1 failed: a named corrupted unit differed from saved configuration but was accepted. |
| s1-config-consistency-green.log |30 passed18.24s after minimal same-snapshot unit/configuration validation. |
| s1-view-withdraw-race-red.log |1 failed: withdrawal completed while current-view read paused after sample read, proving potential stale AVAILABLE. |
| s1-view-withdraw-race-green.log |1 passed1.90s after holding sample FOR SHARE through immutable lookup; withdrawal waits, then later view NOT_FINALIZED. |

Failure tests inject actual task/audit/database boundaries and assert public sample/view/claim/bytes/result behavior. Supporting owner SQL only arranges historical/corrupt states and probes immutable DB constraint; no table-column-layout success assertions.

Current authorization tests expanded revoke/disable across finalize/withdraw/retry (6 combinations); real analyst first successfully finalizes with unchanged grant, then stale DTO cannot mutate after public role/status change.

## Real historical arrangements and compatibility

The old0024 downgrade regression cannot call the new fact writer on an old schema. Attested71 report data was replayed at actual0007, when no quality_snapshot column existed, then real upgrade0024 ran before the original downgrade exercise. This naturally yields a genuine pre-quality record; it does not delete captured business JSON or clear a real saved quality snapshot. No production schema detection/fallback added.

The tokenless regression starts at actual0006 with legal FINALIZED/ASSOCIATED metadata, executes0007 (token remains NULL), then0032/0033. A lawful current v1 sample on the same transformer and a new lawful current warning on another transformer coexist. Public Trends/Health/global AlarmCenter return the current outcomes; old sample produces no point; single view missing_finalization_token/report refinalization_required remain. No token/fact/history/source created for the old record.

V1 tests preserve unknown active inventory, IDs/tokens/instants/methods/results and exact READY PDF bytes; queued/failed facts remain available. Corruption classes cover JSON null/array/schema, token/physical/time envelope, missing envelope/fields, null EQ/unknown qualifier/configuration/duplicates and inconsistent configured units. Corrupt migrated facts return an unavailable view without deleting intact current READY bytes. S2 remains responsible for switching aggregate result reading to this fact decoder and nonnull missing/bad-fact503 behavior; current S1 trend source is deliberately unchanged.

All #50 dynamic-head upgrades/downgrades, older identity/site/quality guards and integrated role policy pass in C1/C3. No migration renumbering/stamping/production downgrade or retained acceptance data migration.

## Runtime and exact commands

Read-only runtime dependencies:
- Python: C:/Users/weila/.codex/worktrees/issue-48-dual-main-sync/DGA Lab/.cache/test-venv/Scripts/python.exe.
- PG17 bin: C:/Users/weila/.codex/worktrees/issue-48-site-export/DGA Lab/.cache/issue-48-postgres/pgsql/bin.
- Node: C:/Program Files/nodejs/node.exe.

New PG initdb own path/role issue51_admin, hidden pg_ctl start with explicit -p18551 -h127.0.0.1, waited only pg_ctl.WaitForExit(60000), not descendant-tree -Wait. No restoration/reseed/copy of old data. Own role/database dga_test/dga_test. Test environment:
    TEST_DATABASE_URL=postgresql+psycopg://dga_test@test-db:18551/dga_test
    DATABASE_URL=same
    PGHOSTADDR=127.0.0.1
    PYTHONPATH=R/backend
    PYTHONUTF8=1
    PYTHONDONTWRITEBYTECODE=1

### C1 required public/historical regression

R/backend:
    python -m pytest -q -rs -p no:cacheprovider tests/test_finalization_facts.py tests/test_finalization_facts_migrations.py tests/test_laboratory_workbench.py tests/test_laboratory_reports.py tests/test_laboratory_configuration.py tests/test_laboratory_integration.py tests/test_device_material_import_migrations.py tests/test_site_import.py tests/test_dual_main_upgrade.py tests/test_identity_management.py tests/test_architecture.py

Result179 passed,3 warnings,90.41s. Log .cache/issue51-tests/s1-c1-public-regression.log.
This run precedes the later current-view share-lock race fix/additional test; its affected test passed afterwards, and final C3 below includes all final production changes. Don't label the earlier C1 as a final-source full run.

### C2 and ordinary browser

npm ci --cache ../.cache/npm installed existing lockfile into new checkout only; no package/lock changes or unsolicited upgrade/audit fix.
npm run build: PASS, .cache/issue51-browser/s1-c2-build.log; bundle index-Dmb31Asw.js (frontend source unchanged).

Separate new dga_browser DB on own18551; migrate head and existing guarded tests.seed_browser used once before linked ordinary scenarios. Existing tests.site_import_browser_app + LocalFiles and separate real ReportWorker share only R/.cache/browser-files; no provider/config change/real Azure claim. API18571 actualPID127128 (launcher87324), worker71396, frontend18171 PID87192. PG18551 PID45160. Exact path/PID/listener identities verified; old/#50 18550/18570/18170 and18148/18164/18165/18448/18464/18465 untouched.

R/frontend:
    BASE_URL=http://127.0.0.1:18171 BROWSER_CHANNEL=chrome
    node node_modules/@playwright/test/cli.js test tests/laboratory-reports.spec.ts tests/laboratory-workbench.spec.ts --output ../.cache/issue51-browser/s1-key

Result2 passed5.9s; .cache/issue51-browser/s1-ordinary-browser.log.
Real report chain: not-finalized status, current autoqueue→READY, preview controls/download%PDF, withdrawal removes link/file, refinalization generates current report. Real workbench scan/add/edit/delete/adopt/finalize/read-only/withdraw chain retained. No fake upload/no-request UI or new browser tests introduced in S1.

1920x1080 visual evidence:
- .cache/issue51-browser/s1-report-1920.png (full page1920x1500): READY status/download/preview controls legible, no overlap; native headless PDF iframe was dark, so this screenshot does not establish PDF page-layout/branding acceptance. Bytes/download/old SHA were separately verified.
- .cache/issue51-browser/s1-workbench-1920.png (loaded read-only sample, full page1920x2154): fields/status/read-only controls visible without overlap.
The initial screenshot helper used a wrong button label and captured only lookup; corrected to the verified '加载油样', waited actual已定稿, and overwrote only own screenshot. Browser test pass was unaffected.

Browser2 ran before the late getter-only share-lock fix; ordinary HTTP never calls that new application-only view, and its exercised mutation/report paths did not change thereafter. Final C3 covers the latest getter code. No unjustified second broad browser/seed/reset run.

### C3 final whole backend

R/backend:
    python -m pytest -q -rs -p no:cacheprovider

Result617 passed,40 skipped,6 warnings in318.73s (5:18), exit0.
Log .cache/issue51-tests/s1-c3-full-backend.log.
All final production and test behavior, including the view/withdraw race, were present. Afterwards only docs, fixture PDF -text metadata and removal of one introduced empty EOF line in the existing historical test changed; no behavioral production/test change or repeat justified.

The40 skips are exactly26 report-storage,10 storage-contract and4 storage-workflow cases requiring configured MinIO/Azurite. Native real-PG + fixture LocalFiles/memory does not establish those contracts or real Azure. Existing warnings: Starlette/anyio/Authlib deprecations and intentional duplicate-ZIP fixtures. No CI tests skipped/disabled by this work.

## Final source hashes and scope

SHA256:
- workbench.py F5103B6644FBC856B085E9DA5F6CC7F69C511F639D3DFA07183D5C23C8BC0C68
- reports.py BD3826D69FF86655ADFE53BE4AFD1D2FB9779CF91FE2E83A79B69D4842D9B426
- public.py B31BADBC089163C18C75A2820A3B031612BDEC111D1275803E22ECF3613D3399
- finalization_facts.py 9AD20187713C32BA98DE4A9546A219485B1050A909617BDDD3BC75C5CC3F7C4E
- 0033_lab_finalization_facts.py 73097C4E51869B3B011E027E55A5B9FEA4CBBB717263510B06A89395619845D9
- test_finalization_facts.py 751259023187E539F48EC246B164A7C8618F6DC7BD0FEEEBCEAE73FC2F67EEB2
- test_finalization_facts_migrations.py 9E51423E00E13A62793285A52015257052CDBFD6019199A33DD9E5ED39CD06DC

git diff --check clean after removing only the new test EOF blank. Source scope check has no diff under condition_analysis, trends.py, frontend, shared/auth or prior0032. No accepted plan/review/controller/G: mutation. No source commit, push or next gate executed.

## Residual risks and handoff

| Item | Classification / owner |
| --- | --- |
| S1 implementation code/legacy/fault/race result acceptance | Current independent S1 deepreview/root checkpoint; this is implementation evidence, not review-pass |
| NO_REQUEST / independent result reader / optional metadata fingerprints / report page | Later approved S2, deliberately absent; no partial completion claim |
| Configured40 storage cases/exact-head dual-host CI | Current #51/controller CI obligation; native skips cannot close it |
| Near20min existing CI timeout | Current controller evidence-triggered reviewed budget fix only if needed; no speculative CI edit |
| Real Azure/Okta and optional corporate/protocol acceptance | Existing deployment/#18, no credentials/provider change |
| Formal import/DATE/original PDFs/manual first summary / policy alignment | Existing approved#53+ owners |
| Broad orphan/lease/cancellation reconciliation | Existing#60; current atomicity/stale guards preserved now |
| Combined chain/load/inherited context-depth20 vs graph100 | Existing#61/#53, unchanged |
| Captured fixture validity on future checkout | Portable LF text attestation, explicit capture-byte provenance and exact PDF bytes; immutable business JSON/PDFs retained |

No blocking question remains for S1. Explicit S1 implementation COMPLETE. Stop for independent deepreview/fix/re-review and controller accepted slice checkpoint; no S2 implementation or other gate started.

## Subsequent finite S1 fix evidence

After the original implementation evidence above, independent review code-review-20261029-200426.md found one malformed nested asset-ID classification defect. The controller accepted it. The bounded repair and actual RED5failed/1passed → GREEN48passed25.53s are recorded in [issue-51-s1-fix.md](issue-51-s1-fix.md). That artifact supersedes only the earlier finalization_facts.py and test_finalization_facts_migrations.py hashes. The earlier C1179/backend617/browser2 results remain dated pre-fix evidence; they are not claimed as reruns on the finite-fix source. The latest48-case public facts/migrations/architecture run covers the final guard. Positive captured JSON/PDF/manifest and0033 remain unchanged. Finite fix COMPLETE; stop for independent re-review, with exact-head full/configured-storage CI still controller-owned. No S2, commit or push.
