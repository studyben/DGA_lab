# Issue #52 S1 finite fix

Status: COMPLETE — implementation/verification for accepted findings01/02/03 is complete; await original independent reviewer re-review. This is not a review PASS or gate advancement.

## Authority and bounded scope

Root accepted all three P2 findings in docs/reviews/code-review-20261029-232050.md. Current worktree C:/Users/weila/.codex/worktrees/issue-52-lab-import-staging/DGA Lab, branch codex/issue-52-lab-import-staging, unchanged HEAD14a958a16aaf597c908bfb4283605d2e0ff96ef9. Original S1 source manifest e9dd8ae05e02a35928fe26f30536b44970a8d0a009d10176966c5e605a41d79c is the pre-fix reference. Review was read fully; no accepted-plan/goal/schema/permission change.

Frontend child explicitly confirmed idle before nonoverlapping delegation: it owned only ImportPage.tsx/importApi.ts/importTypes.ts and the existing laboratory browser spec. Principal owned imports.py/import_http.py, public facade/HTTP tests and docs; principal verified complete integrated behavior. Both stopped source writes after handoff. No S2/parser/worker/asset lookup/row editor, new migration, source CRUD, generic cancel/discard platform, commit/push/PR/comment or self-review artifact.

## 01 — Fixed: one synchronous submission owner before the first await

Before: upload awaited File.arrayBuffer before busy/intent ownership, allowing a double click to make two UUIDs/POSTs and overwrite the actor-private recovery slot.

After: ImportPage.owned claims a synchronous ref token before invoking any async work. Create, upload, revise, retry, recovery query and explicit correction use that common owner. Upload owns the token before fileMetadata, and run checks that token before persistence/network/response handling. A separate retained-intent ref prevents a different key from overwriting an unresolved slot. finally releases the owner on success and failure; a stale callback cannot clear another request's retained intent. Unknown results retain the original key/payload; no backend different-key deduplication was added.

Real browser RED: fix-frontend-red-01.log,1 failed; delayed500ms File.arrayBuffer +20ms double click produced2 files rather than1. GREEN: fix-frontend-green-01.log,1 passed6.7s; exactly1 POST/file/revision1, then a distinct explicit next upload succeeds, proving lock release. Existing lost-RECEIVE case now also delays arrayBuffer/double-clicks and proves only the original key is queried/recovered. Wrong-original retry/storage/preflight error cases exercise failure release without losing the retained intent.

## 02 — Fixed: committed owner-backed input rejection, then explicit correction

Chosen approach is a durable REJECTED operation, not a transport-only “no write happened” guess.

The public laboratory owner adds LaboratoryImports.reject_input(actor,idempotency_key,action,request,batch_id?). It independently verifies the same strict CreateImport/ReviseImport model actually rejects that parsed JSON. Valid commands cannot use it as cancellation. It stores only a versioned rejection envelope: rejection_contract=1, canonical raw-input SHA256 and the REVISE route batch UUID context. Canonical raw JSON uses the existing sorted-key/separator/UTF-8 digest before model normalization; normal create/revise still use their existing normalized strict model digest. The distinct envelope namespace cannot collide with a normal accepted command. This also avoids putting invalid/NUL-bearing fields into PostgreSQL JSONB or shared audit.

Transaction order stays current identity guard -> actor/key lock -> REJECTED op + safe audit, with no business batch/source/file mutation. Existing different action/payload/current operation returns409, never overwrites; exact invalid retry returns the same frozen rejection without duplicate audit. After the transaction has known committed, a still-current private operation read returns the rejection. Only then can HTTP emit:

~~~json
{"code":"invalid_import_input","disposition":"DURABLE_REJECTED","operation":{"state":"REJECTED","action":"CREATE","batch_id":null,"result":{"code":"invalid_import_input","status":422,"details":null},"error_code":null}}
~~~

REVISE uses the same shape/action REVISE. Invalid JSON/missing transport inputs/no validated rejection has no proof. Audit failure, rollback, durable-but-lost COMMIT response and readback failure cannot emit proof; technical failures remain503 import_write_unknown. Both committed/uncommitted outcomes can be resolved by the original actor's private operation query/exact retry. Shared audit refers to the internal operation ID, never the private key/raw rejected request.

Frontend parses the full status422/code/disposition/op/action/result/null-fields contract, then matches it to the submitted action. It retains the exact intent and exposes only an explicit correction control; the user must click before editing and later creating a new key. Reload queries the durable original rejection first. Generic422, malformed/spoofed proof,404,503,401/403 and lost responses retain exact key/input; there is no automatic forget/new key, no arbitrary discard/cancel.

Real browser RED: fix-frontend-red-02.log,1 failed for actual server-only america/chicago rejection. GREEN: fix-frontend-green-02.log,1 passed3.7s: server rejects, durable rejection survives reload, user explicitly enables correction, America/Chicago succeeds using a different explicit key. No timezone-specific casing patch was added. fix-frontend-unproven.log1 passed3.8s covers ordinary422, real operation404,503 with a spoofed proof and malformed422 proof, retaining identical key/payload and no correction control.

Backend RED: fix02-red-http-proof.log1 failed due missing disposition. GREEN: fix02-03-green-contract.log1 passed4.36s. Persistent public tests cover exact rejected retry, corrected same-key409, existing completed key409/no overwrite, invalid REVISE with no revision, invalid NUL safely digested, malformed JSON422 without proof. Public real-PG fault tests cover rejection audit rollback and both COMMIT outcomes, no duplicate audit and action/payload conflicts. Public production router fault test fix02-http-unknown-commit.log1 passed5.92s proves both outcomes return503 with no disposition before an exact retry obtains authoritative422.

Old strict-HTTP regressions were updated to respect the now-durable binding: after an intentional invalid request, they assert REJECTED and use a distinct explicit intent for a corrected payload. They do not silently reuse a rejected key.

## 03 — Fixed: one owner applies the same Unicode comparison on both sides

Before: Python casefold(q) produced strasse.csv while SQL lower(filename) kept straße.csv, omitting the exact filename.

After: list_batches passes the original q and applies PostgreSQL lower to both query and retained filename/batch UUID. Filenames remain byte-for-byte metadata values; no schema/index/data rewrite, character-specific replacement, truncated candidate list or all-data client filtering. This is SQL lower semantics, not full Unicode casefold equivalence: Straße.csv and STRASSE.csv remain distinct filenames. Source-laboratory candidate casefold behavior is separate and unchanged.

Real public PostgreSQL RED: fix03-red-unicode.log1 failed, search returned1 rather than21 (the SS-only false match). GREEN: fix03-green-unicode.log1 passed5.94s. A fresh isolated historical schema supplies21 Straße.csv batches plus SS/Chinese/mixed-ASCII filenames. Exact/mixed-ASCII-case searches yield all21 across20+1 pages with consistent total/distinct IDs, SS finds only its own batch, Chinese and UUID-uppercase searches succeed, and original filename remains unchanged. No private-table assertion substitutes for public search outcomes.

## Verification, commands and precise overlap

All logs are .cache/issue52-tests. Existing runtime namespace and ports remain owned; test schemas are created/dropped by the isolated test harness, not by changing acceptance data.

| Run | Exact outcome | Scope |
| --- | --- | --- |
| fix-backend-focused.log |29 passed,2 warnings,40.34s | Existing/new S1 public recovery/currentauth/receipt/manifest, HTTP,0033 preservation/0034 migration, architecture; includes the3 new backend cases present at that point |
| fix02-http-unknown-commit.log |1 passed,3 deselected,2 warnings,5.92s | Additional public HTTP router real-PG commit-outcome test |
| fix02-final-guard-recheck.log |2 passed,15 deselected,2 warnings,7.59s | Added explicit cross-action/no-duplicate-audit assertions plus current-authority test, overlapping the29 |
| fix-auth-neighbors.log |10 passed,5 deselected,2 warnings,18.79s | Existing shared auth CSRF/origin, role matrix and status/session revocation neighbors |
| fix-frontend-final.log |13 passed23.0s | Prior10 expanded S1 browser cases plus3 finite-fix cases, actual Chrome production bundle/API |
| fix-frontend-build.log | tsc --noEmit + Vite successful479ms | Current production bundle,72 modules |

The29 plus the extra HTTP test cover23 unique S1 facade/HTTP/migration cases and7 architecture cases; the guard recheck overlaps and is not added. The13 browser cases include the old10, not an additional13 beyond them. Historical pre-fix19/21/43/472/10 results remain historical evidence, not rebranded as new fixes or summed with these runs. No provider adapter/schema/normal FileStore path changed, so the old43 configured storage neighbors and472 broad suite were not blindly rerun; controller owns exact final-head complete configured dual CI.

Native commands (same owned runner/PG18552/PYTHONPATH/UTF8/noBytecode as original S1 artifact):

~~~powershell
& .\.cache\issue52-tests\run-tests.ps1 -Log fix-backend-focused tests/test_laboratory_imports.py tests/test_laboratory_import_http.py tests/test_laboratory_import_migrations.py tests/test_architecture.py
& .\.cache\issue52-tests\run-tests.ps1 -Log fix02-http-unknown-commit tests/test_laboratory_import_http.py -k never_emits_rejection_proof
& .\.cache\issue52-tests\run-tests.ps1 -Log fix02-final-guard-recheck tests/test_laboratory_imports.py -k 'rejected_input_proof or current_authority'
& .\.cache\issue52-tests\run-tests.ps1 -Log fix-auth-neighbors tests/test_auth.py -k 'csrf_origin_validation or roles_enforced_at_public_module_and_http_seams or account_status_and_role_changes'
~~~

Browser from frontend uses BASE_URL=http://127.0.0.1:18172, BROWSER_CHANNEL=chrome and LAB_IMPORT_BROWSER_USERNAME/PASSWORD for the existing owned reception-admin fixture; npm exec playwright test tests/laboratory-import.spec.ts. Server data/files were not re-bootstrapped/reset. Before the only reload, API listener PID/command/module/port were checked; final API PID96448/helper68076 at18572, PG PID124948/datadir unchanged at18552, production server PID150436 at18172. Existing native/provider/oldUAT resources remain; no prune/global restart/network removal/other process stop. Screenshot frontend/test-results/laboratory-import-reopened.png was regenerated by the production run.

## Contract/docs and residual ownership

docs/laboratory-imports.md now specifies committed-rejection proof/explicit correction, one submitted intent, and SQL lower history semantics. Original issue-52-s1.md remains historical with an appended pointer to this fix and final manifest; accepted goal/plan/fix/reviews and all schema/migration/roles remain unchanged.

Findings01/02/03: implemented and verified as above; no accepted finding is deferred. Backend remains authoritative for IANA/scientific inputs; edition differences now have a correction path rather than an unresolved actor lock. S2/S3 retain their accepted parser/worker/current-result/row-review obligations; #53 retains formal publication/PDF/role-policy scope; existing#60 retains abandoned-object lifecycle. No fix delegates current submission integrity/recovery to those later slices.

Genuine blocking questions: none. No implementation tests remain running at final handoff. STOP after EXPLICIT COMPLETE; await original independent reviewer re-review and controller adjudication, with no commit/push or S2.

## Final source fingerprints and consistency

Final values appended after the last guard test and frontend ownership handoff. Pre-fix source record remains .cache/issue52-tests/source-fingerprints.json; final record is fix-source-fingerprints.json. Only the finite-fix files differ from the pre-fix S1 manifest.



Aggregate final source manifest SHA256: `5bacff195be7d51528439b5adaa439a04c9505b18f23d54b1720e7e91bd075e8`. Canonicalization matches the original S1 artifact: UTF-8 lines of relative path + one space + lowercase raw-file SHA256 + LF, in the table order. All21 original source/test paths remain; exactly8 changed in this finite fix (two production backend, two backend test, three production frontend, one browser spec).

| Path | Final SHA256 |
| --- | --- |
| backend/dga/laboratory/import_contracts.py | 4a588f29b2664c41a4df67daaafe07d70312e86001c33cea67d3dfbec47c7b70 |
| backend/dga/laboratory/import_files.py | d6c7406637eede1f5f4e2dab5c9e6841fc24da5144e1cc7129ca10e5011ea9e3 |
| backend/dga/laboratory/import_http.py | ce9617898ed72ad060e3b3bbafa8603d1e88917c93feaddc76c92831e639063d |
| backend/dga/laboratory/import_tables.py | 0e462b165aad0c42b24d2ca436a625d2b4256e775a496b9d4443fd1f025df45f |
| backend/dga/laboratory/imports.py | a11fada5d4e6317bb4dcd49394ec73831430b19b83675d786ef1455a81dd7478 |
| backend/dga/laboratory/public.py | ce48aac25c772426fba44502780032d9d9458501d7a950fe0ff3ef40bc1822fc |
| backend/dga/main.py | 0cfddd22f4669714a765a03d64a3ae1cd3119ee2078d15e265ca8425a264d79a |
| backend/migrations/versions/0034_lab_import_staging.py | 37f4afbcd859fdd3d650527a2d75b27fe8d08196742ca244aa46924f477e5d54 |
| backend/tests/laboratory_import_browser_app.py | b4c2badc6b5b194e04dd0db3053bb36224bc4644606c61e50eb15fd0a6ddfb73 |
| backend/tests/test_laboratory_import_http.py | d8074577089d402f7a20eaa895bbd2a06a457fb3bdb0a75ac25bd581183c824b |
| backend/tests/test_laboratory_import_migrations.py | 84e48e7a4e580be9577f37302fcc72a14cfaaedc8b0369f378c1eae0078940ab |
| backend/tests/test_laboratory_import_storage.py | 49af201c39a773f06d8f9118d37bdd35fa1c1cda1b97f4d52b5c06df2f581eb4 |
| backend/tests/test_laboratory_imports.py | 70def023ca4452e594d99fc54cc09767610ada4b3062eb129d29fcd386ddf9f4 |
| frontend/src/features/laboratory/importApi.ts | 2b26a6367ff70294ab996b1057c37537a1c4933c27174412f339cdd5ea8dd23e |
| frontend/src/features/laboratory/importIntent.ts | ded27371150b1a3d65b1edd4bbf631d6f2c1d67cf8e2a70209a9950164907656 |
| frontend/src/features/laboratory/ImportPage.tsx | 7fe578c2d88b8a2b078f9da4481a7f663ba3836eb7de1184263666badbc1a9ca |
| frontend/src/features/laboratory/imports.css | a21b6ba0723b1db580a2561053efb762b1f48d348d12162be735209ebc61d38f |
| frontend/src/features/laboratory/importTypes.ts | 7221f191f5dde8514428f5cf9019a26759bfc37c199716ddf748f7fe6a8c37ca |
| frontend/src/features/laboratory/pages.ts | 3121325971cf6be842e06949706a4e043a1cc9a473754f67d83d34404efcdf65 |
| frontend/src/main.tsx | 3bcf30e4d1d142c504ae4063905b9e32d00ec1f089b0374836184d3790424621 |
| frontend/tests/laboratory-import.spec.ts | bf515158a27b6a3bdd1711f8bff85cbb0c7037805bb2850758b19bc5d0b74e1b |

Protected0034 migration hash remains `37f4afbcd859fdd3d650527a2d75b27fe8d08196742ca244aa46924f477e5d54`; unchanged independent review hash `8cc749e3c3a65f47a07966d6f2f6a8b7657b4b60f2435b3cd467d53b3822a657`. Screenshot final SHA256 `65571cc180606bf665839f7acb9548ca7105d52bebeda89ab83deb51180f79d4`. Production index SHA256 `65b341d8ab8b40c57db8ae62f5f06f10f58d053efc1ae241d357c7064ca52361`; JavaScript index-AmRhqdx9.js SHA256 `782048cafbf2f40fdd2c9670a8341dc6eadf103d9584d59f401931cab7709f5c`. Machine-readable local records: fix-source-fingerprints.json, fix-artifact-hashes.json, fix-runtime-ports.json under .cache/issue52-tests.

Final read-only checks: git diff --check passes with normal LF/CRLF notices only; source hashes rechecked against this final manifest; migration/import_contracts.py/raw schema/current role policy/plan/goal/controller unchanged by this fix; the HTTP rejection proof is the explicit bounded contract refinement above. No source/test changes outside the eight named files, plus the allowed product docs/original evidence pointer/new fix artifact. No tests or child work remain running. Findings01/02/03 are all FIXED by the author; independent re-review is still required.
