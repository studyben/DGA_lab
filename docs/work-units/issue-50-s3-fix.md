# Issue50 S3 fix — findings1/2

Status: **IMPLEMENTATION COMPLETE**, ready for independent re-review. This is the accepted S3 fix gate, not aggregate review/PR/closeout. No commit or gate advancement.

## Authority and exact scope

Checkout `C:/Users/weila/.codex/worktrees/issue-50-material-import/DGA Lab`, branch `codex/issue-50-device-material-import`; accepted S2 base and unchanged HEAD `6eb7d5e540d288730287ace60cb93679d596a7f6`.

Read full `docs/reviews/code-review-20261029-173510.md` and current read-only G: controller. Controller accepted findings1/2 as current S3; subsequent Unicode-bound and received-known409 checks are explicitly accepted finite F2 correctness follow-ons, not new scope/contracts. Existing confirmed goals/TDD public seams apply.

This fix changes only `frontend/src/features/assets/AssetImportPage.tsx`, `V2ImportPanel.tsx`, targeted `frontend/tests/device-material-import.spec.ts`, this artifact and the S3 evidence record. `siteImportIntent.ts` remains unchanged. All other S3 files/review artifacts and unrelated workspaces/data are preserved. No backend production/migration/framework/provider/dependency/CI/#60 platform changes.

## Finding disposition

| Finding | Reviewed state → fix state | Actual proof |
| --- | --- | --- |
|1: initial metadata headers/body may hang forever, leaving no retry | 未修复 → **已修复** | Genuine two-case browser RED; complete read now bounded15s, same-batch actual-mode retry succeeds, cancelled/late request cannot replace new page;3-case GREEN and key/full browser regressions. |
|2: pending revision loses exact input across reload,404 leaves a digest-only dead end | 未修复 → **已修复** | Unforwarded real revision abort RED; exact bounded request saved before dispatch/readback, visible restored values/reason/revision, same-key byte-identical replay after real operation404, successful resolution clears it.401/403/503/network retention, quota failure, old SITES and follow-ons below all pass. |

Both are implemented as fixed; independent re-review is still controller-owned. Neither is marked evidence-invalid or deferred to#60.

## Implementation and invariants

### Finding1

`AssetImportPage` initial metadata effect owns an AbortController,15s deadline and active flag covering both fetch headers and `response.json()` consumption. Timeout produces an explicit batch-read error and retry control. Retry starts a fresh bounded attempt for the same selected batch, clears the old failure/loading state, cancels the previous attempt and still takes actual version/mode from server metadata. Cleanup cancels and guards late success/error/history updates. No URL guess bypasses metadata, including misleading SITES URLs for actual ASSETS batches or old v1 links.

The browser network fixture is a local ephemeral HTTP streaming server serving metadata obtained through the real authorized batch API. It independently holds headers or sends headers/one JSON byte and holds the body. Tests observe actual timeout/cancellation/retry/navigation, not React state or a mocked timeout clock.

### Finding2

New pending revisions retain `revision_request:{expected_revision,changes,reason}` beside key/kind/digest/batch/mode/version in the existing actor/mode session namespace. This is the exact one-row request prepared for dispatch, including values and row reason. The scalar guard permits only one known sheet/row, declared columns plus reason, finite scalar values, reason<=1000 and values<=2000 Unicode codepoints. No arbitrary request replay or additional platform is introduced. Size is bounded by those existing editor fields/counts/character limits.

The request is stored and read back before its first network dispatch. Storage failure blocks dispatch, reports that nothing was sent and leaves desired editor inputs intact. On an unresolved response, the original key and request survive reload/relogin. Recovery queries the original actor-scoped operation first. Operation404 remains unconfirmed and never authorizes deletion/rebasing/new keys: the saved exact fields, reason and old expected revision become visible for copy or same-key replay. The replay is not reconstructed from the current preview. Byte-identical POST assertions include the original idempotency key. A durable completed result clears the pending record; auth/network/server/malformed/ambiguous errors retain it.

Old SITES namespace and pre-mode signatures remain compatible. A payloadless old record can recover an existing durable operation. If operation404 and the old input never existed in browser storage, the UI explicitly states that automatic restoration is impossible and retains the key; it does not fabricate input or assume rollback. Different new input remains blocked by that unknown old intent. This historical limitation is intentionally disclosed and does not affect the new exact-input guarantee.

Choosing a recovered batch clears the prior displayed batch while reading, avoiding publication controls on stale displayed data. Existing committed-PUBLISH loss and old REFRESHED recovery still use the stored operation outcome, never the newer live batch state.

### Accepted Unicode follow-on

The first guard used JS `.length`, which counts UTF16 units; backend Python limits count Unicode codepoints. Actual public API acceptance of2000 non-BMP emoji followed by editing another field reproduced a guard-blocked RED: the note remained visible but no request was sent. Two guard counts now use `Array.from(...).length`, preserving the same2000/1000 backend bounds without ASCII restriction, normalization or truncation. The test preserves the entire2000-codepoint note through unknown response, reload,404, exact replay and server readback.

### Accepted received-known409 follow-on

Retaining every revision4xx would deadlock a rejected new intent. Two actual second-manager races reproduced this directly: another revision advances validation revision, or another manager publishes the batch while its editor is open. The real revision endpoints return respectively `409 import_stale_validation` and `409 import_already_published` before writing changes/operation completion. In `V2Imports.revise`, existing same-key operation lookup precedes these guards; therefore these exact received domain rejections are known no-write outcomes, unlike an operation-lookup404.

The client releases only the received revision409 with one of those two exact codes, and preserves the original desired field values/reason in the editor. Stale rejection requires explicit reread/current-revision review before a new key is submitted. Already-published rejection keeps inputs for copying, prevents further revision submission to that published batch and allows a new independent upload after user selection. The original published data is unchanged. No arbitrary409, operation conflict, lookup404,401/403,5xx or network failure is treated as rollback. The arbitrary409 negative control still recovers/retries the same exact key/payload.

These two negative acknowledgments are a deliberate distinction from unknown outcomes, not a cancellation or guessed-success mechanism.

## Runtime restoration and safety

Verified the absolute owned cluster `.cache/issue50-tests/pgdata`, absent18550 listener/old PG PID124184 and `pg_ctl status` no server before restoration. Existing API95704/frontend126964 paths/listeners were verified. Initial explicit18550 restoration used existing data and replayed interrupted WAL as PID123648; no5432 startup or retained port was used in this fix.

Found that `Start-Process -Wait` waits the descendant process tree, leaving the bootstrap exec attached to the long-lived server. Corrected only the owned startup helper: verified owned PID/path, graceful fast stop, hidden Start-Process with `-o "-p 18550 -h 127.0.0.1"`, and waited only for the pg_ctl process via `WaitForExit(60000)`. Final PG PID99080 remained available after that helper returned and throughout validation. This is a plausible explanation for earlier lifetime loss, not a proven historical cause. Logs: `.cache/issue50-tests/s3-fix-pg-start.stdout/stderr.log`, `s3-fix-pg-detached.stdout/stderr.log`, existing postgres.log.

API18570/PID95704 and built frontend18170/PID126964 were not restarted during this fix. Thus the memory FileStore process survived restoration. Read-only Python/PG binaries were reused; no old venv install, Docker Desktop restart or retained18448/18464/18465/18148/18164/18165 access.

After all18 key linked tests completed, the full suite required restoring the first-login/workbench fixture baseline. Ran existing guarded `tests.seed_browser` only against own `postgresql+psycopg://dga_browser@db:18550/dga_browser`, with `PGHOSTADDR=127.0.0.1`; no reseed occurred inside a linked chain. The action is recorded in `.cache/issue50-browser/s3-fix-full-baseline.log`. API/memory FileStore were not restarted. This is fake browser data, not acceptance or real storage evidence.

## Exact commands/results

All commands explicitly use this checkout. Browser prefix:

```powershell
$r='C:/Users/weila/.codex/worktrees/issue-50-material-import/DGA Lab'
Set-Location "$r/frontend"
$env:BASE_URL='http://127.0.0.1:18170'
$env:BROWSER_CHANNEL='chrome'
& 'C:/Program Files/nodejs/node.exe' node_modules/@playwright/test/cli.js test <selection> --output '../.cache/issue50-browser/<results>'
```

Combined output is retained via Tee-Object and exit code preserved. C2 is `npm.cmd run build` using this checkout's dependencies. No React implementation assertions/private business table success assertions.

| Selection / log in `.cache/issue50-browser/` | Actual result |
| --- | --- |
| device spec `--grep 'metadata .*挂起有界'`, `s3-fix-f1-red.log` |2 genuine RED failures: no bounded error at20s for pending headers/body. |
| device spec `--grep metadata`, `s3-fix-f1-green.log` |3 passed/32.9s, after `s3-fix-f1-build.log` build pass. |
| device spec `--grep '原修订.*未提交'`, `s3-fix-f2-red.log` | Aborted revision genuinely loses exact restored input. The503 case initially had a relogin-readiness test failure; not claimed as separate product RED. |
| Same2 cases, `s3-fix-f2-green-b.log` |2 passed/3.5s after awaiting actual authenticated UI. Earlier green attempt1pass/1login-readiness failure retained honestly. |
| `--grep 'metadata|原修订.*未提交|存储失败|旧SITES'`, `s3-fix-targeted-final.log` |10 passed/40.1s; C2 `s3-fix-c2-final.log` passed. Earlier coverage6pass/1strict locator ambiguity corrected to select the actual legacy notice; no product claim based on that fixture failure. |
| key C4: site-import/device-material-import/zz-asset-import specs `--trace on`, `s3-fix-c4-key.log` |18 passed/58.4s. Includes committed publication response abort, immutable REFRESHED recovery, modes, SITES/legacy, and fixes. |
| full C4, `s3-fix-c4-full.log` |**67 passed,1 existing OIDC fixture skip (1.5m as reported)**. This run precedes the following finite bound/known-rejection changes. |
| `--grep 合法2000码点`, `s3-fix-unicode-red.log` |1 genuine RED: legal server-accepted note blocked by UTF16 guard. |
| F2 affected cases including Unicode, `s3-fix-f2-unicode-final.log` |8 passed/9.6s; `s3-fix-c2-unicode-final.log` build passed. |
| `--grep 明确拒绝过期修订`, `s3-fix-stale-red.log` |1 genuine RED: actual stale409 then explicit reread/newreview remains blocked by old digest. |
| stale+arbitrary409, `s3-fix-stale-green.log` |2 passed/3.1s; `s3-fix-c2-stale.log` build passed. |
| `--grep 另一经理发布后`, `s3-fix-published-red.log` |1 genuine RED: actual already-published409 prevents a new independent upload (POST count0). |
| latest affected F2: `--grep '原修订.*未提交|存储失败|旧SITES|合法2000码点|明确拒绝过期修订|另一经理发布后'`, `s3-fix-f2-definitive-final.log` |**11 passed/11.9s**. Latest C2 `s3-fix-c2-published-final.log` **tsc/Vite pass**, bundle `index-GnxZOMSV.js`. |

The final11 cover abort/503/401/403/arbitrary409 exact retries, storage failure/no POST, old payloadless SITES missing/committed operations, Unicode, actual stale and published-terminal races. Only affected checks were repeated after finite follow-ons, as directed. No claim that the earlier full68-test run included the4 later cases or ran against the final V2 hash.

Traces/screenshots are retained under the corresponding `fix-*-results` paths; passing18 key-flow traces under `fix-c4-key-results`. The streaming metadata fixture is local to the test process and closes after each case.

## Fingerprints and before/after coverage

SHA256 final:

| File | Hash |
| --- | --- |
| AssetImportPage.tsx | `3208A8A8B61CAD530E06774F4B672A43F590798C1388C7E9538CF43846476EE7` |
| V2ImportPanel.tsx | `852A67672C86C26D4F4CB648441391E8C39C688EE38250F5AC625D425AE8B319` |
| device-material-import.spec.ts | `4AF5CCA4B06428289EA7B067E3780AAC0E513F6FABBC0341947F4C40F25A3A2A` |
| unchanged siteImportIntent.ts | `2EADE3A0AF500775B604399D985FB410B1A795F5AD0B119CE5ED7FF59A61DBA6` |
| unchanged backend test_device_material_import.py | `471C579C8251D01D624297F105B84265F8E96D9424F090307CA2E689C4E7A897` |

Core-fix key/full browser runs used V2 hash `6C9928C498041304471045BF37A2A1B24B32CE2289AE306EDE5B0E90DB305B9F` and device test hash `377E0C3DAF5C067DC408432ED1516B783147D56C14BBABB6FE8A031D705DAC7B`. Unicode-only intermediate V2 hash was `181712EA7D54AFFAB4AFC99864ED632B94EF662568C16C95A975737AAC716C31`. Final build/11 affected checks use the final fingerprints above. AssetImportPage/F1 code is unchanged across those later F2 follow-ons.

No backend production/migration/capacity test changed. Prior S3 C1 **242 passed**, C3 **582 passed/40 configured storage skips**, and actual2000-row/all100pages/all2000sources/all500material/equipment proof remain prior completed evidence; they were not rerun or represented as post-fix runs. Controller explicitly directed affected frontend validation only.

## Residuals and completion

- Both current findings are **已修复**, with the Unicode and two definitive409 regressions corrected in the same F2 path. No current fix is deferred to#60.
- Payloadless old SITES records cannot restore bytes never saved; durable operation recovery works, unknown404 remains explicit/key-preserving. This is an acknowledged historical-data limitation, not a fabricated success or partial new guarantee.
- Configured MinIO/Azurite40 contracts and the existing OIDC stub/browser fixture remain later exact reviewed-head CI/controller obligations. No real Azure/Okta acceptance is claimed.
- Cancellation/leases/orphans/reconciliation remain existing#60, wider combined retained-history load#61, real corporate integration#18/deployment. No new backend/platform is introduced.
- Earlier owned-PG termination cause remains unproven; process-only bootstrap wait correction and stable current listeners are recorded factually. Retained environments were untouched.

Final diff formatting and allowed scope verified; HEAD remains6eb7d5e. No commit/push/PR/comment/merge/controller write/review/gate advance. Fix implementation explicitly complete; stop for independent re-review.
