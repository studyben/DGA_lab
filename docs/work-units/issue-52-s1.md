# Issue #52 S1 implementation evidence

Status: COMPLETE — S1 implementation and the scoped verification below are complete. Await controller independent S1 deepreview; this document does not itself advance a gate.

## Scope and baseline

- Worktree: C:/Users/weila/.codex/worktrees/issue-52-lab-import-staging/DGA Lab.
- Branch: codex/issue-52-lab-import-staging; HEAD remains accepted-plan commit 14a958a16aaf597c908bfb4283605d2e0ff96ef9. Parent product baseline896d7072cfd81c07ac732404d286e160e9ed3459, with0033. Root supplied the accepted dual-host parent CI evidence; this agent did not rerun that historical CI.
- Gate: accepted plan §14 S1 only, using tdd; no commit/push/PR/comment/review, no S2 self-start. Frontend was delegated with explicit root authorization and nonoverlapping ownership; author retains responsibility for this complete slice.
- Instructions read: original G: AGENTS.md, docs/agents/domain.md, CONTEXT, ADR0007/0010 and original ADR0009, frozen design/issue snapshots, goal/accepted plan/fix and both plan reviews. tdd and domain-modeling skills applied. No existing ADR, role policy or root controller edits.

## Implemented vertical behavior

LaboratoryImports is exported through laboratory.public and wired into the actual app. Its S1 constructor takes engine/FileStore and existing IdentityService/AuditTrail/clock only. Root accepted adding S2's actual public asset/configuration ports later within the unpublished unit; S1 invents no placeholder port and performs no lookup.

0034_lab_import_staging (23-character revision, one chain after0033_lab_finalization_facts) adds exactly eight laboratory-owned staging/source tables, owner indexes/FKs, immutable source/file/raw-row/history guards and protected downgrade. It changes no formal tables. Future staging rows/jobs have storage schema but no parser, worker, enqueue or fake processing implementation.

S1 includes:

- Format1 blank/synthetic templates: exact18 sample/39 complete-test columns; Chinese XLSX business sheets; CSV_PAIR download ZIP with two UTF-8 CSVs/instructions. Output only; no asset/method/unit guessing.
- Explicit NEW/REFERENCE source identities allocated only in confirmed transactions, complete-set candidate digest checks under source-name locks, no same-name merge/CRUD.
- Purpose/source-timezone metadata, R0 creation, optimistic metadata/binding/active-file revisions, frozen per-intent results, paged batch/original/revision history with actual active manifest/count summaries.
- Actor-private durable intent/reservation/receipt/token/60s-lease state machine. FileStore.put runs after known reservation COMMIT and outside its transaction. Final receipt requires current authorization/token/lease, atomically writes RECEIVED/op result/R++/audit; lost COMMIT does not delete objects or falsely report success.
- Current laboratory.write for every staging read/write; mutation Origin/CSRF; private authenticated original download with length/SHA verification, safe Unicode disposition and private,no-store/nosniff.
- /lab/imports actual production page: create, source decisions, byte-progress vs waiting-for-receipt distinction, exact-intent restoration, original reselection/hash verification, explicit inactive RECEIVED selection, history/reopen/download. No validation/finalization/publication control or development-stage badge on this page.
- Narrow README/PROJECT_PLAN/CONTEXT and docs/laboratory-imports.md documentation. Source_note and ordinary notes remain distinct in the versioned template contract; actual row ingestion is S2.

## Finding01 receipt-only proof

test_abandoned_private_receipt_can_be_replaced_in_same_batch_by_another_current_writer uses public receive_file with a FileStore boundary crash after storing A bytes. It observes durable inactive PENDING, confirms explicit selection returns scoped files_pending, revokes A through public identity, verifies B cannot query A key, and lets B's own intent provide the current same-batch RECEIVED file. A bytes/metadata survive; restored A exact-key retry after lease expiry completes inactive and R++ without replacing B. The old upload token is separately fenced under a concurrent reclaimed receipt. There is no queue/process assertion in S1; CSV_PAIR complete two-role receipts are additionally exercised through public migration/non-effect and browser cases. Validation readiness in S2 must continue to read only the selected RECEIVED manifest, never unrelated history.

## TDD sequence and focused results

Logs below are in .cache/issue52-tests. Counts overlap; do not sum incremental runs as unique cases.

| Behavior | Genuine RED | Result after minimal implementation |
| --- | --- | --- |
| Public first creation | red-create.log: ImportError,1 failed | green-create.log:1 passed1.59s |
| Explicit stable source identity | red-sources.log: missing source_labs,1 failed/1 passed | green-sources.log:2 passed2.06s |
| Confirmed immutable original | red-receipt.log: missing receive_file | green-receipt.log:3 passed2.61s |
| Abandoned A / B working receipt | red-manifest-review.log: missing revise | green-manifest-review.log:4 passed3.75s |
| Versioned complete templates | red-template.log: missing template | green-template.log:5 passed4.37s |
| Shared audit private-key leak | red-audit.log: key visible in failure audit | green-commit-audit.log:7 passed5.95s; audit uses internal operation ID |
| History filters/pagination | red-history.log: DAILY filter returned21 rather than1 | green-history-concurrent.log:9 passed7.03s |
| Real HTTP route | red-http.log:404 rather than401 | green-http.log:10 passed7.99s |
| Strict HTTP reserved extra names | red-http-strict.log: duplicate idempotency_key TypeError | green-http-strict.log:2 passed2.61s |
| HTTP metadata revision | red-http-revision.log: incorrect strict model422 | green-http-revision.log:2 passed3.22s |
| Source-bound audit snapshot | migration-non-effects.log: UUID audit serialization failure | green-migration-non-effects.log:16 passed13.14s |
| Paged manifest summary | red-history-summary.log: missing manifest_state | green-s1-configured.log includes final behavior |

Additional public real-PG cases cover both committed/uncommitted lost CREATE, reservation and final receipt COMMIT responses; no provider write before known reservation; retained objects/no duplicate receipt; parallel exact CREATE/RECEIVE; changed content409; storage put/get/hash failure; revoked stale actor on all read/write seams; analyst finalize grant retained; file size/MIME/path/control limits; stale upload token fencing; late audit failure rollback/recovery. FileStore/clock/database-COMMIT faults use only injected external boundaries, with real database transactions and public outcomes.

Final new S1 configured suite: **21 passed,2 warnings,13.87s** in green-s1-configured.log. These are15 facade +2HTTP +2migration +2configured-provider cases; no provider skips in this run. After adding exact10MiB/Unicode255 filename and oversized32MiB JSON boundary assertions (test-only), final-native-s1.log reports **19 passed,2 warnings,29.00s** for the same facade/HTTP/migration cases without the two provider variants. These runs overlap; do not add19 to21.

Reproducible configured command (own ephemeral project, no host ports):

~~~powershell
docker compose -p dga-issue52-s1 -f compose.yaml -f compose.storage-test.yaml -f .cache/issue52-tests/provider-network.yaml --profile test run --build --rm api-test pytest -q -p no:cacheprovider tests/test_laboratory_imports.py tests/test_laboratory_import_http.py tests/test_laboratory_import_migrations.py tests/test_laboratory_import_storage.py
~~~

The network-only local overlay is:

~~~yaml
networks:
  default:
    ipam:
      config:
        - subnet: 10.241.52.0/24
~~~

Native initial configured-provider attempt correctly reported2 skipped (provider-local-scope.log); this was not counted as pass. Daemon read-only preflight succeeded. Default new-network allocation then failed because predefined pools were exhausted (provider-configured.log). Read existing Docker CIDRs and host routes (docker-subnets.log), selected unused10.241.52.0/24 for only the fresh project, and reran actual MinIO/Azurite successfully:2 passed3.03s in provider-configured-owned-subnet.log, then included in the final21. No prune, existing network removal, Docker restart, WSL/global shutdown or old container/data mutation.

Existing configured storage contract/workflow/report neighbors: **43 passed,2 warnings,25.38s**, storage-neighbors-configured.log. Command uses the same own project/overlays with run --rm api-test pytest -q -p no:cacheprovider tests/test_storage_contract.py tests/test_storage_workflows.py tests/test_report_storage.py. An initial unsupported run --no-build option started no test; rerun used the supported default reuse of the already-built image.

## Formal non-effects and migration preservation

test_0034_preserves_0033_facts_pdf_and_all_formal_public_queries arranges attested old READY producer data only in a historical schema, upgrades through actual0033, captures public results, upgrades0034, creates source/batch, receives both CSV roles and revises metadata through LaboratoryImports. It then compares unchanged:

- Public oil sample and its containers, laboratory dashboard metrics, complete asset test history and workbench tests.
- Current finalization facts/token and original READY PDF bytes/hash/report status; claim_next_report remainsNone.
- Formal asset detail/dashboard and finalized measurements.
- Health status/source/business interpretation and alarm items.

Health/alarm reads legitimately write evaluation evidence. The test warms those queries and compares business meaning rather than claiming zero physical writes or comparing fresh evaluation IDs. It does not infer non-effects merely from a helper not being called. Empty0034 can downgrade/re-upgrade in its own historical schema; any retained source/batch evidence refuses downgrade and the original facts remain readable. No acceptance DB is downgraded or stamped.

## Runtime isolation and real browser evidence

Before starting, reserved ports18552/18572/18172 were checked free. All helpers started hidden. Read-only PG17 binaries came from issue-48-site-export/.cache/issue-48-postgres/pgsql/bin; read-only Python from issue-48-dual-main-sync/.cache/test-venv/Scripts/python.exe. No old venv installed into. Frontend npm ci used only this tree's frontend/node_modules and .cache/issue52-tests/npm-cache; lockfile/dependency versions unchanged.

Owned native PG datadir: .cache/issue52-tests/pgdata, loopback18552, postmasterPID124948. Actual test namespace queried dga_test/dga_test/18552/public with default search_path "$user",public. PostgreSQL admin independently verified the absolute owned datadir. Browser role remains unprivileged; a first attempt to read data_directory as that role failed before migration and was corrected by relying on the independent admin datadir proof, without granting privileges.

Separate whole browser DB/role dga_browser/dga_browser on the same owned PG, actual18552/public/default search_path verified before first bootstrap. This avoids create_app's known libpq options/search_path override. Bootstrap seeds only the owned isolated fixture; no #50/#51/oldUAT data is reused.

Current review resources (retained, not stopped):

| Resource | Address / ownership |
| --- | --- |
| Native PG | 127.0.0.1:18552; PID124948; exact owned datadir above |
| S1 API | 127.0.0.1:18572; PID63784; helper11876; tests.laboratory_import_browser_app:app |
| Production bundle server | 127.0.0.1:18172; runtimePID150436, launcher62396; .cache/issue52-tests/serve-bundle.py |
| Provider project | dga-issue52-s1 only; test-db/MinIO/Azurite tmpfs, no host ports, subnet10.241.52.0/24 |

API/bundle helpers and their stdout/stderr/provenance files are in .cache/issue52-tests. The browser fixture uses local hashed FileStore paths under .cache/issue52-browser-files; it is an honest local fixture, not hosted Azure/Okta acceptance. To stop later, first reverify PID/command/port/datadir; never stop a computed or unverified old resource. Own provider project can later be brought down by its exact project name/three overlays, without global cleanup.

Production build: tsc --noEmit + Vite successful, frontend-build.log. Browser command from frontend:

~~~powershell
$env:BASE_URL='http://127.0.0.1:18172'
$env:BROWSER_CHANNEL='chrome'
$env:LAB_IMPORT_BROWSER_USERNAME='reception-admin'
$env:LAB_IMPORT_BROWSER_PASSWORD='Changed reception passphrase 87!'
npm exec playwright test tests/laboratory-import.spec.ts
~~~

Final real Chrome production-bundle run: **10 passed21.5s**, browser-s1-final.log, against the final reloaded S1 API. It covers bytes/download/reopen, NEW/REFERENCE stable source, metadata revision/explicit inactive original switch, lost CREATE/RECEIVE response lookup, operation404 retaining exact key/payload, wrong original zero retransmission, storage failure zero POST, distinct upload state, both CSV roles, invalid explicit timezone zero POST followed by correction. Browser crypto.subtle/randomUUID are disabled in the spec to exercise ordinary-HTTP fallback.

Actual frontend RED evidence is retained: browser-first.log exposed the accessible-label mismatch; browser-s1-frontend.log exposed recovery digest property-order mismatch; browser-red-unknown404.log exposed original DAILY metadata not restored; browser-red-invalid-zone.log observed1POST for invalid metadata before preflight, then browser-green-invalid-zone.log proves0POST/editable input/correction. No claim of a missing-page RED after implementation had begun.

Screenshot inspected: frontend/test-results/laboratory-import-reopened.png,1920px production viewport/full page. It shows current selected original, separate historical files and revision/history sections with no validation/publish controls or prototype data. Image hash and source fingerprints follow after final consistency checks.

## Remaining verification and residual ownership

- Affected-native-neighbor run: **472 passed,4 warnings,792.43s**, affected-regressions.log, single run only. Includes architecture/auth/identity, asset/site/device-material import/search/history, laboratory configuration/operations/workbench/reports,0033facts/migrations, transformer trends/health/alarms. During that run the only additional production edit was the new LaboratoryImports history-summary query; final configured21/native19 and final browser10 cover that final source. Existing business modules did not change. Full684/configured exact-head CI is intentionally not repeatedly run in this slice; controller owns final #52 exact-head dual CI.
- S2 owns bounded parser/formula/ZIP/CSV/complete-row capacities, scientific method/unit/precision/time/DST issues, actual public asset/configuration ports, worker/validation state/readiness/current-results consistency and full preview pagination.
- S3 owns row review/source_note corrections and bounded two-writer browser validation/reopen proof. #53 owns formal publication/PDF-content workflow and later authorization alignment.
- Existing #60 owns abandoned-object lifecycle/reconciliation; S1 deliberately preserves recovery metadata/objects and provides no cancel/delete/other-actor proxy.
- Browser Intl and backend IANA editions may differ; backend remains authoritative, no inferred timezone. An anomalous prebinding server rejection retains exact intent conservatively; no automatic new key/discard was introduced.
- No scientific configuration was invented; missing scientific data becomes staged issues in S2 rather than blocking this authorized S1 delivery.
- Genuine blocking questions: none.

## Final consistency / completion

All assigned S1 verification completed; no tests remain running. git diff --check passes (normal LF/CRLF notices only). Scope inspection found no diff in .github workflows/compose, assets, condition_analysis, existing0033, reports/finalization or auth policy; public.py/main changes are necessary public wiring only. Root controller/accepted goal-plan/fix/reviews remain unchanged. No commit/push, review artifact or next-slice implementation was created. Genuine blocking questions: none. STOP: await root independent S1 deepreview; do not implement S2 or self-approve S1.



### Final source fingerprints

Raw working-file SHA256; paths relative to the explicit worktree. Listed manifest canonicalization is UTF-8 lines (path + one space + lowercase hash + LF), in the table order. Aggregate SHA256: `e9dd8ae05e02a35928fe26f30536b44970a8d0a009d10176966c5e605a41d79c`. Cached machine-readable record: .cache/issue52-tests/source-fingerprints.json. Source/test files below were frozen after final browser/frontend ownership handoff; final-native-s1 covers the final added limit assertions.

| Path | SHA256 |
| --- | --- |
| backend/dga/laboratory/import_contracts.py | 4a588f29b2664c41a4df67daaafe07d70312e86001c33cea67d3dfbec47c7b70 |
| backend/dga/laboratory/import_files.py | d6c7406637eede1f5f4e2dab5c9e6841fc24da5144e1cc7129ca10e5011ea9e3 |
| backend/dga/laboratory/import_http.py | afb175546a5002104eb3ff6aae92a84a990761ee706e1c98bcb55e20cb4e2be2 |
| backend/dga/laboratory/import_tables.py | 0e462b165aad0c42b24d2ca436a625d2b4256e775a496b9d4443fd1f025df45f |
| backend/dga/laboratory/imports.py | cec107dcc372d48078c009b26779d6d4d91ea322c04678d3181a4f724580858a |
| backend/dga/laboratory/public.py | ce48aac25c772426fba44502780032d9d9458501d7a950fe0ff3ef40bc1822fc |
| backend/dga/main.py | 0cfddd22f4669714a765a03d64a3ae1cd3119ee2078d15e265ca8425a264d79a |
| backend/migrations/versions/0034_lab_import_staging.py | 37f4afbcd859fdd3d650527a2d75b27fe8d08196742ca244aa46924f477e5d54 |
| backend/tests/laboratory_import_browser_app.py | b4c2badc6b5b194e04dd0db3053bb36224bc4644606c61e50eb15fd0a6ddfb73 |
| backend/tests/test_laboratory_import_http.py | c12e45cb9f7415149da5134074e7c62a99f03970d6687a35820c2d1d5a08614d |
| backend/tests/test_laboratory_import_migrations.py | 84e48e7a4e580be9577f37302fcc72a14cfaaedc8b0369f378c1eae0078940ab |
| backend/tests/test_laboratory_import_storage.py | 49af201c39a773f06d8f9118d37bdd35fa1c1cda1b97f4d52b5c06df2f581eb4 |
| backend/tests/test_laboratory_imports.py | bd890970f777805c399452bd683b2947ba9d0efdcdb79e941ded31cc56a49a54 |
| frontend/src/features/laboratory/importApi.ts | 0057f62732340625d492ada0ce2b5fce58c4a21097976cc6b952cf40b0f5d854 |
| frontend/src/features/laboratory/importIntent.ts | ded27371150b1a3d65b1edd4bbf631d6f2c1d67cf8e2a70209a9950164907656 |
| frontend/src/features/laboratory/ImportPage.tsx | cf658f610462e2c1cbf1c154246f9ba056a13f02420952c2bc501d7603515674 |
| frontend/src/features/laboratory/imports.css | a21b6ba0723b1db580a2561053efb762b1f48d348d12162be735209ebc61d38f |
| frontend/src/features/laboratory/importTypes.ts | 03ffd28100ad2d11e743b3b4e3f09668fe85e874c003aec641ae397b0813dc9d |
| frontend/src/features/laboratory/pages.ts | 3121325971cf6be842e06949706a4e043a1cc9a473754f67d83d34404efcdf65 |
| frontend/src/main.tsx | 3bcf30e4d1d142c504ae4063905b9e32d00ec1f089b0374836184d3790424621 |
| frontend/tests/laboratory-import.spec.ts | c58d3f898f819dee5af507154d774fbe875475dad7a7c276d3e08d2466cc727a |

Screenshot SHA256: `7c78777ef54fdb2908d90a93313eed6bef2ad3b6692bfca2f72facfa7c85a328`. Production dist/index.html SHA256: `28bdcbacb2f28ca8f17e34eccbb002873831d1b649c5f69dd94ac3f1791dfc67`; final JavaScript bundle SHA256: `0e4d80ab14f2ad0676d6ad60bfe8700fd7b06ba6e62e3dd15591e2d2434614b8`. Runtime/provenance records: final-runtime-ports.json, provider-owned-state.json, api-reload-provenance.log under .cache/issue52-tests.

### Native verification commands

Runner .cache/issue52-tests/run-tests.ps1 sets PGHOSTADDR=127.0.0.1; TEST_DATABASE_URL=postgresql+psycopg://dga_test@test-db:18552/dga_test; PYTHONPATH to this tree's backend; UTF8 and PYTHONDONTWRITEBYTECODE=1. It runs the read-only existing Python runtime from backend with pytest -q --disable-warnings -p no:cacheprovider and Tee-Object to its named log.

~~~powershell
& .\.cache\issue52-tests\run-tests.ps1 -Log final-native-s1 tests/test_laboratory_imports.py tests/test_laboratory_import_http.py tests/test_laboratory_import_migrations.py
& .\.cache\issue52-tests\run-tests.ps1 -Log affected-regressions tests/test_architecture.py tests/test_auth.py tests/test_identity_http.py tests/test_identity_management.py tests/test_asset_import.py tests/test_site_import.py tests/test_site_import_http.py tests/test_device_material_import.py tests/test_device_material_import_http.py tests/test_device_material_import_migrations.py tests/test_asset_search.py tests/test_asset_test_history.py tests/test_laboratory_configuration.py tests/test_laboratory_operations.py tests/test_laboratory_workbench.py tests/test_laboratory_reports.py tests/test_finalization_facts.py tests/test_finalization_facts_migrations.py tests/test_transformer_trends.py tests/test_device_health.py tests/test_alarm_center.py
~~~

## Post-review finite fix pointer

This original S1 artifact and manifest e9dd8ae05e02a35928fe26f30536b44970a8d0a009d10176966c5e605a41d79c describe the pre-review implementation. Independent code-review-20261029-232050.md returned FAIL with three accepted P2 findings. Their bounded fixes, new RED/GREEN evidence and final manifest5bacff195be7d51528439b5adaa439a04c9505b18f23d54b1720e7e91bd075e8 are in issue-52-s1-fix.md. That follow-up supersedes the old IANA/prebinding-rejection residual and old source fingerprints for the current implementation; this historical record is not rewritten or claimed as S1 acceptance. Await controller independent re-review.
