# Issue #51 S2 implementation evidence

2026-10-29. Workspace R=C:/Users/weila/.codex/worktrees/issue-51-finalization-facts/DGA Lab, branch codex/issue-51-finalization-facts. Accepted S1/base/HEAD4f6ff0721b5e49811f15c21cb884859120db1c26 remains unchanged. S2 changes are uncommitted. This records implementation, not independent review or controller acceptance. No commit/push/PR/comment/next gate.

## Scope and delivered contracts

- Public FinalizationReportPolicy has QUEUE_CURRENT default and explicit NO_REQUEST. Both use the same current identity authorization, configuration/sample lock order, identity, QC, active inventory, selection, warning, immutable capture, event and audit transaction. Only the report callback is conditional. Invalid policy422. Ordinary HTTP FinalizationInput forbids extra fields, so report_policy cannot create an HTTP bypass. Actual analyst laboratory.finalize grant remains unchanged.
- LaboratoryTrendSource selects ASSOCIATED/FINALIZED/nonempty-current-token candidates and LEFT JOINs current immutable facts. Missing qualified facts cannot disappear through an equality join. Frozen physical/time headers select scope; the sample header is only a missing-fact discovery fallback. Entire candidate validation precedes returned points; missing/corrupt facts yield trend_snapshot_unavailable503, with no partial successful result. Legitimate old NULL-token rows remain excluded before fact validation. No report table/state/file, current method or current test fallback remains.
- The existing laboratory facts owner supplies typed adopted measurements from its validated versioned evidence. No second legacy decoder in trends, private analysis SQL, reverse import, new repository/task/storage framework or scientific/date algorithm is introduced.
- Four appended optional FinalizedMeasurement metadata slots default None: result_origin, sampled_at_precision, measured_at_precision, sampling_context_verification. All current/legacy writers remain unknown. The public finalized_measurement_evidence serializer preserves the original21 fields and omits only these four when None; explicit values participate in evidence/signatures. TransformerTrends, DeviceHealth and AlarmCenter use it at each measurement serialization/fingerprint/current-set/group-set seam. Existing grouping/qualifiers/health aggregation/recovery algorithms are unchanged.
- Matching current report status and READY byte reads retain their independent behavior even if typed facts are invalid. Without a matching request, valid current facts mean report_not_requested, including after withdrawal→NO_REQUEST with an obsolete request row. Unavailable facts are explicit; mismatched old row with missing current fact retains report_not_current. Missing retry remains409; no first-request endpoint/button.
- Report page labels report_not_requested as 未请求 and says 检测已整体定稿，尚未请求系统报告；有效检测结果不依赖 PDF 生成。 It has no retry/download/blank iframe/withdraw advice in that state. Invalid facts use 当前定稿资料无法核实，请联系实验室核对。 Ordinary report controls remain.
- README/CONTEXT/PROJECT_PLAN/ADR0010 narrowly describe the delivered contracts and existing residual owners. No0033 change, provider/role grant/threshold/ASTM/date/formal-import/original-PDF/manual-summary expansion.

Controller approved two necessary test-path extensions: seed_browser.py's two-line isolated fixture hook before logout, and the existing migration tests' pre0033 measurement expectations. Production main/compose/CI/old migration/captured positive JSON/PDFs are unchanged.

## Old→new observation evidence captured before reader/consumer change

.cache/issue51-tests/capture_s2_observations.py ran against the accepted S1 ordinary producer and the then-unchanged reader/three consumers. A new own dga_test schema s2_baseline_f7cc52e891a44c96a9111b2e51ab336a was actually migrated and populated via public facades. It produced a configured abnormal point, an OPEN alarm, public acknowledgement, then a later compatible normal point and RESOLVED alarm, plus a persisted health evaluation and trends. The baseline records source commit4f6ff072 and actual SHA256 for the four reader/consumer files. This attests those producer/reader boundaries, not a claim that every S2 test/doc file was unchanged at capture time. The first NO_REQUEST test existed already; policy production changes followed capture. S1 ordinary delivery was the producer used, not a fabricated historical application.

Capture .cache/issue51-tests/s2-observation-capture.log; JSON .cache/issue51-tests/s2-observation-baseline.json. Captured bytes SHA25690175dc8d2c15198209cc08d907f51ebeb421605f940fbf5c2f720fea7bc73a9. Retained evaluation529cb502-133a-4fcd-82ed-adcc00889483; resolved alarm291ea9fe-d469-42f8-805c-933a3361ab86. New code recheck log s2-observation-recheck.log proves identical trends, complete persisted health evidence/fingerprint/evaluation ID with only one evaluation, identical alarm generation/fingerprint/ack/recovery/events and unchanged baseline file bytes. This schema remains for review; normal test fixtures operate other schemas and did not reset it.

Additional repeatable tests compare upgraded old-producer points against the original attested public_measurements, not expectations calculated from the new reader. Synthetic nonNone metadata wraps real PG-backed public points: stable metadata deduplicates health evidence/alarms, changed source metadata changes evaluation IDs/alarm observations, old evaluation evidence remains readable. DATE corruption at the owner storage fault seam is explicitly unavailable; no formal DATE write feature is added.

## Actual TDD and bounded test corrections

Pre-agreed success seams are public Workbench/Reports/laboratory result protocols and three analysis facades with real PG. Historical/raw SQL is arrangement or actual storage fault only. No private layout/React-internal assertion is success.

| Log under .cache/issue51-tests | Actual outcome and meaning |
| --- | --- |
| s2-no-request-red.log |1 failed1.72s, public enum absent (initial tracer); corrected the test's LaboratoryError attribute to the actual .status contract before GREEN |
| s2-no-request-green.log |1 passed1.58s: no task, valid inventory, missing request/retry/file409 |
| s2-reader-red.log |1 failed1.82s: valid NO_REQUEST produced no point through old report join |
| s2-reader-green.log |1 passed1.67s: same point feeds Trends/Health/Alarm public facades |
| s2-contracts-red.log |4 failed/1 passed4.22s: missing/no-current report classification and absent public evidence helper were real gaps; HTTP403 was missing Origin in test setup, not a behavior RED |
| s2-contracts-green.log |1 failed/4 passed4.44s despite its filename: instrument fixture was incorrectly assumed None; fixed test to explicitly supply None for the preservation assertion |
| s2-focused-01.log |10 failed/136 passed71.37s:7 old tests called current reader on0032 (facts table absent);3 new fixture typos used wrong enum/event table/worker method. No production schema fallback added |
| s2-arrangements-green.log |2 failed/15 passed10.49s despite filename: QA test default exceeded configured precision; missing file raised the correct ObjectStorageError, not LaboratoryError. Corrected arrangements/expectations |
| s2-c1-public.log |163 passed,2 inherited warnings79.93s, exit0, final S2 backend source |

The pre0033 migration tests now use actual captured fcea/71 public_measurements as their BEFORE expectation. They still arrange real0032, migrate actual head, compare public IDs/instants/values/method/units with captured output, retain PDF SHA/byte/status assertions and populated downgrade guard. Positive fixture business payload/PDF bytes and0033 are unchanged. The three report-copy corruption tests now prove a damaged delivery copy cannot rewrite effective immutable points; distinct real-migration missing/corrupt fact tests still require all three analysis queries503 beside valid current data.

C1 command from R/backend, read-only existing issue-48-dual-main-sync Python runtime:

    python -m pytest -q -rs -p no:cacheprovider tests/test_finalization_facts.py tests/test_finalization_facts_migrations.py tests/test_laboratory_reports.py tests/test_transformer_trends.py tests/test_device_health.py tests/test_alarm_center.py tests/test_laboratory_sample_operations.py tests/test_architecture.py

Environment: TEST_DATABASE_URL=postgresql+psycopg://dga_test@test-db:18551/dga_test; DATABASE_URL=same; PGHOSTADDR=127.0.0.1; PYTHONPATH=R/backend; PYTHONUTF8=1; PYTHONDONTWRITEBYTECODE=1. No same-DB parallel pytest. Added rollback tests inject actual late event/audit errors after fact capture; public view/selection/history/point/job all roll back. Current revoke/disable covers NO_REQUEST too. Real concurrent mixed-policy finalize has one success/409; completion holds sample lock against withdrawal, then cannot resurrect withdrawn results. Existing download share lock, expired lease/stale completion/failure and ordinary queue-failure tests remain.

Delivery independence covers QUEUED, GENERATING, FAILED, missing stored file, deleted request, damaged request snapshot, withdrawal/new NO_REQUEST token/obsolete request and later ordinary queue. Legal0006→0007 NULL-token/current coexistence still exercises all3 public consumers, separately from nonnull missing/bad facts503. Existing physical replacement/duplicate serial/method-unit/qualifier/tie/recovery/retirement tests were retained.

## Isolated native browser arrangement and retained resources

Owned PG17 PID45160 is127.0.0.1:18551, datadir R/.cache/issue51-tests/pgdata; executable is existing read-only issue-48-site-export bundled postgres. No PG restart or old/#50 resource operation. API18571/frontend18171 only; frontend PID87192 keeps the existing own ignored Vite preview config. Original own51 public business sample/report rows and LocalFiles remain. Four preexisting own LocalFiles files were enumerated before browser switch and individually SHA-checked unchanged afterwards (s2-preserved-localfiles-before.json). Seven committed legacy PDFs/cases/manifest remain unchanged and verified by loader.

Two fresh schemas in own dga_browser/dga_browser DB, no reseed/reset of retained schemas:
- key issue51_s2_key_20261029;
- full issue51_s2_full_20261029.

For each, prepare_schema.py verifies real database/user/port, creates a new namespace, performs actual0033/head migration, then from the SAME URL asserts current_schema/search_path equals only that new schema and every targeted table resolves there before existing destructive fixture setup. Logs s2-key-seed.log and s2-full-seed.log show guards and fixed old barcodes1/2 OPEN plus new no-request barcode DGA-20260901-000003 FINALIZED. Existing seed_browser adds a two-line call to the new guarded public Python helper, so ordinary production compose CI obtains the same new fixture without a custom API or HTTP bypass. The helper uses a separately named physical transformer SYS-TX-NOREQUEST-051 and TEST method; no files/provider are needed. Existing original catalog/material fixture is copied into each new schema exactly; no retained schema is touched.

Native-only configuration issue: main.create_app supplies connect_args.options for statement_timeout, overriding URL options search_path. First browser probe logged in to retained own public and GET history returned0; it did not mutate samples/tests/reports. Login itself adds auth session/login audit, so it is not labeled zero DB writes. This is fixture failure, not product RED. Controller approved setting only this own role IN DATABASE dga_browser default search_path to the verified key/full namespace without public fallback; production main/connect_args/other roles/other DBs are untouched. App-style connections and subsequent public no-request reads confirmed actual scope. Original observed current_schema was public; original SHOW search_path string was not separately captured and is not falsely attested. Current explicit role config and recovery information are in s2-role-search-path.json. Future restoration is an own-fixture decision; no automatic reset was performed.

Each API/worker was checked by PID/executable/full command/datadir/port before finite switch; hidden Start-Process, no global process kill. Key API first69672 then126844 after the scope correction; key worker launcher124316/actual152776. Full API launcher87204/actual20792; report worker launcher37384/actual42244; import worker launcher114844/actual82280. API and report worker share existing LocalFiles under R/.cache/browser-files; import worker is the unchanged production validation worker. Full URLs contain options=-csearch_path%3Dissue51_s2_full_20261029 as well as the necessary role default. Processes/schemas/files are left available for review. No#50 18550/18570/18170, original18148/18164/18165 or retained#48/#49 environment mutation.

For native Windows only, existing browser tests contain Linux /app/test-results screenshot paths. A disposable copy under frontend/.cache/issue51-s2-native/tests changes ONLY those screenshot paths and prior issue50 screenshot-output paths to own R/.cache/issue51-browser/native-screenshots. All assertions/fixtures/behavior and single-worker1920x1080 Chrome settings are preserved. native-test-copy-manifest.json records original/copy hashes and exact substitutions; every copy is checked equal to source after those output-only replacements. New spec uses testInfo.outputPath directly. Committed existing browser tests/config were not modified. CI runs originals under normal compose paths.

## Browser RED/GREEN, C2 and final verification

- s2-ui-red.log first failed on history0 due native scope issue above; not product RED.
- s2-ui-red-02.log on correct key schema:1 failed because 未请求 badge absent, actual UI RED against old built frontend.
- First UI edit command used wrong relative path from frontend and failed before edit; its s2-c2-build.log built the unchanged old bundle. It is not latest-source C2 evidence.
- Corrected UI edit, s2-c2-build-02.log: tsc --noEmit + Vite PASS, bundle index-D7hOPHFr.js. No dependency/lock/CI change.
- s2-key-browser.log:6 passed/1 failed12.3s across fixed plan key selection. New case's status locator also matched the portal connection status, a test arrangement ambiguity. Limited it by the exact report status text; no production change for this correction.
- s2-no-request-green.log: final new original-source spec1 passed2.2s; report truthfulness/no iframe/actions and existing real trend point7.25 passed. Existing six key cases had already passed ordinary queue→READY→PDF→withdraw→refinalize and analysis chains, so they were not gratuitously rerun on the used baseline.

Commands from R/frontend, BASE_URL=http://127.0.0.1:18171/BROWSER_CHANNEL=chrome:

    npm.cmd run build
    node node_modules/@playwright/test/cli.js test --config .cache/issue51-s2-native/playwright.config.ts laboratory-reports.spec.ts laboratory-workbench.spec.ts finalization-facts.spec.ts transformer-trends.spec.ts alarm-center.spec.ts --output ../.cache/issue51-browser/s2-key
    node node_modules/@playwright/test/cli.js test tests/finalization-facts.spec.ts --output ../.cache/issue51-browser/s2-no-request-green
    node node_modules/@playwright/test/cli.js test --config .cache/issue51-s2-native/playwright.config.ts --output ../.cache/issue51-browser/s2-full

Screenshots were visually inspected: .cache/issue51-browser/s2-no-request-green/finalization-facts-公开无请求定稿显示未请求，现有趋势仍读取有效结果/no-request-report-1920.png (1920x1080) and no-request-trend-1920.png (1920x2277 full page at1920x1080 viewport). Legible state/inputs/results, no overlap/blank iframe; the trend has exactly one valid7.25 TEST-UNIT point. No scientific/branding/PDF page-layout acceptance is inferred from these screenshots.

Final whole backend C3 from R/backend:

    python -m pytest -q -rs -p no:cacheprovider

s2-c3-full-backend.log:644 passed,40 skipped,6 warnings483.84s (8:03), exit0. This one final whole run includes all final S2 backend behavior/tests, the accepted S1 finite malformed-ID fix, real historical/#50 merge/head paths and actual current-source consumer switch. No later backend production/test change occurred. Exactly26 report-storage/10 storage-contract/4 storage-workflow provider cases remain skipped because native MinIO/Azurite are not configured; no global Docker was started and nothing was weakened. Warnings are inherited Starlette/anyio/Authlib deprecations and intentional duplicate-ZIP fixtures. Native concurrent browser plus backend timing is evidence, not a claim about configured CI duration.

s2-full-browser.log:78 passed,1 intentional OIDC_PROTOCOL_FIXTURE skip,2.9m, exit0, all79 cases (78 existing plus1 new no-request case) on the new full schema. It includes ordinary report/workbench,3 analysis UI surfaces, safe return/read-failure retry, full#49/#50 import/existing assertions and no-request page/point. No assertion/count was weakened or skipped for the new fixture. It used the output-only native copy described above; the source/copy manifest was checked after the final new-spec locator correction. The existing optional OIDC overlay is not enabled by ordinary compose CI, so this does not close#18 acceptance.

The plan's requested key CLI selects files alphabetically: alarms/new no-request precede ordinary report/workbench in the actual combined key run; the full run likewise uses existing deterministic Playwright order. We did not claim ordinary-first execution or reorder/reset a retained baseline to disguise that chronology. Ordinary and no-request samples have independent identities, and both actual linked chains pass. Fresh schema setup seeds all fixtures before either chain, as the CI migrate hook also does.

After full browser, an actual public HTTP READY download of DGA-20260802-000002 was saved as s2-ordinary-current.pdf, proof s2-ordinary-download-proof.json:10967 bytes, application/pdf, SHA25608ca97770af3253f2b24bf75e8fa351c15e1d40df7cc34e26e428401049b2afd. This is the current ordinary newly generated file, not the attested historical PDF. S1's seven immutable old PDFs have separate captured hashes. No PDF visual branding/layout acceptance is inferred. The old→new persisted-observation script was rechecked after both full suites to confirm no accidental cross-schema reset: s2-observation-final-recheck.log PASS with the same90175dc8... baseline bytes/identical persisted evidence.

## Final hashes and scope verification

.cache/issue51-tests/s2-final-source-hashes.json records raw SHA256 of all nine touched production Python files, fixture hooks/new helpers/new browser spec/ReportPage, unchanged0033/captured cases/manifest. These are Windows checkout byte hashes; they are not Git blob IDs or portable business-corpus hashes. Final production hashes:

| File | SHA256 |
| --- | --- |
| laboratory/workbench.py |b6490c011f2da15a51a00d29723b0a0841594abc2d8a5577b9689b409b26bd72 |
| laboratory/finalization_facts.py |e0f07b8f9f75610bd23c13f8bfcbd9005e93f8a59169e33927d216f098835594 |
| laboratory/trends.py |c317bf512bf192c3e62ec098e82dd4a92233aaf09bb7c913e93fe72f82a580ac |
| laboratory/reports.py |7f045b8b8874af4417a46b6addc63047285692d813ff51047ebb058ef291f69a |
| laboratory/public.py |55db4de95ff9fa6d7183f9fe676a6f459a51484d8a1785cfe35c19422e36f5c1 |
| laboratory/http.py |a3e27d1b7e2cabd200145059d80358a56f35c904926564f2932b9f0bc6fb8266 |
| condition_analysis/public.py |7b9e7c702af4d6e1db3ba3ee854369ac2c8c99633db2b902b7d693f81cce09c2 |
| condition_analysis/health.py |cb30e6581f50b2dcb04eeb7fe2d586229d3f98f09e42f7512ff9be45f416a778 |
| condition_analysis/alarms.py |75e805a4055638571ab7ecf2db5c23e0449bcafcc034391e810aa8c77bfec09c |
| frontend ReportPage.tsx |77d9737dfdabb7fe222cc5258bec53167d5136718c57d0306d3c0bfe4ebe8017 |

Unchanged0033 raw SHA73097c4e51869b3b011e027e55a5b9fea4cbbb717263510b06a89395619845d9; unchanged cases.json capture bytes334c432b27d907f6ce9ead2ef202df08c0311be31e0d82ec7a13912b9c1d4a00; unchanged manifest46df938dbfa04ef7b74012cba8fd7148deaf213e2e403b5b0ae6814d2c23bb4a. Existing portable LF corpus digest and all seven PDF bytes remain checked by its loader, not compared to platform-converted raw text.

Read-only branch/status and diff checks confirm HEAD4f6ff072 unchanged. git diff --check for current tracked S2 changes is clean; this is not a claim that every inherited staged/PDF byte has clean whitespace. Controller already classified intrinsic PDF spaces/7 inherited EOF blank warnings benign; immutable PDFs were not normalized for formatting. No stage/commit/cached mutation. Scoped diff has no migration/CI/compose/shared-auth/main production/provider changes. S1 evidence/reviews/accepted-plan files and G controller are untouched. New evidence/test helpers/spec are untracked pending controller acceptance.

A complete final file/hash/run fingerprint, including tests and scoped docs, is stored in s2-final-fingerprint.json. Only documentation/fingerprint collection followed the final full tests; no further behavioral/source/test correction required a redundant full rerun.

## Residual ownership and handoff

| Item | Owner / boundary |
| --- | --- |
| Independent S2 deepreview/fix/re-review and accepted slice checkpoint | Controller next; not self-declared here |
| Aggregate fcea..current review, draft PR/PR review/exact-head CI/closeout | Controller subsequent gates; none executed by this slice |
| Native configured-storage40 / exact-head dual-host CI / any observed20min timeout | Current unit/controller; no skipped checks or speculative timeout edit |
| Real Azure and corporate Okta/optional OIDC overlay | Existing deployment/#18; LocalFiles/native baseline not acceptance |
| Formal external/date/original-PDF/manual first-summary/policy alignment | Existing approved#53+; no partial implementation here |
| Broad orphan/lease/cancellation/uncertain COMMIT platform | Existing#60, current transactional/lease guards retained |
| Combined-chain/load/context-depth discrepancy | Existing#61/#53, no unproved regression deferral |
| Captured legacy facts/PDF provenance | Existing S1 attestation retained; no business payload rewrites |

S2 implementation COMPLETE. No blocking human product/architecture question. Stop for independent S2 deepreview and controller adjudication; no review-pass, commit, S3/aggregate review or next gate was started.
