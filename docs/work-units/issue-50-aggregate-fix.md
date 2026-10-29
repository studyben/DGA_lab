# Issue #50 aggregate fix — Unicode editor limits

Status: **IMPLEMENTATION COMPLETE — independent aggregate re-review pending**. Recorded 2026-10-29T18:37:19-05:00. No gate advancement is claimed.

## Baseline and scope

- Checkout: `C:/Users/weila/.codex/worktrees/issue-50-material-import/DGA Lab`.
- Branch: `codex/issue-50-device-material-import`.
- Exact accepted S3 HEAD / fix base: `2f7c76d73c8d3696cb6a485c0a6da2b63243a643`; HEAD remains unchanged. Starting tracked tree was clean; only the new aggregate review artifact was untracked.
- Accepted authority: `docs/reviews/code-review-20261029-182723.md`, finding1 (P2); read-only original G: Phaseflow controller. Existing Issue47/50 goals and browser/public-API seam are already confirmed. Applied tdd skill and its testing/mocking guidance; no new goal interview or contract decision.
- This fix changes only `frontend/src/features/assets/V2ImportPanel.tsx`, `frontend/tests/device-material-import.spec.ts`, and this evidence file. Existing reviewer-owned `docs/reviews/code-review-20261029-182723.md` is preserved. No CSS change was necessary.
- No backend production/test, migration, source storage, provider, dependency, framework, role, CI, domain-document or #51/#52 change. No sampling-context20 versus lifecycle100 change. No commit/push/PR/comment/merge/controller write/review/next-gate action.

## Finding disposition

| Finding | State | Actual evidence / resolution |
| --- | --- | --- |
| 1: actual shared V2 editor native maxlength silently truncates legal non-BMP notes/reasons | **已修复** | Two independent actual-keyboard REDs on accepted HEAD; legal2000-codepoint note and1000-codepoint reason now compose intact, POST successfully and read back through public preview/history. Over-limit note/reason and generic text inputs remain exact, show explicit counts/errors and cannot dispatch. Shared SITES correction-to-boundary/save and existing exact Unicode recovery pass. |

The original source-note textarea used native `maxLength={2000}`, revision-reason textarea `maxLength={1000}`, and generic text input `maxLength={2000}`. HTML counts UTF16 units before React receives the input. The existing persistent payload guard and backend use Unicode codepoints; that guard alone cannot recover characters prevented by the control.

Removed these native caps from the actual controls. The form now computes codepoint lengths using `Array.from` without truncation, normalization, character substitution or ASCII restrictions. The source-note/generic scalar ceiling remains the existing2000-codepoint editor/payload ceiling; reason remains1000. This does not claim every other business field accepts2000 characters: existing smaller server field rules remain authoritative and unchanged.

Excess input stays in the same controlled field. Adjacent `role=alert` text identifies the field, maximum and current character count, and explicitly says input is preserved and must be shortened. `aria-invalid` / `aria-describedby` connect the control to its error. Save is disabled while any editor bound is exceeded; the actual revision dispatch also checks the same validation before locking, persisting an intent or sending a request. Shortening the input clears the error and enables normal submission. Existing required reason/trim behavior is retained.

`isRevisionRequest`, actor/mode durable storage, key/digest generation, exact saved request replay, operation404 retention and narrow known409 handling were not changed. Saved valid original requests can still recover independently of another currently edited draft. No speculative cancellation/recovery abstraction was introduced.

## Runtime: verified existing owned resources only

Before tests, verified listeners and full command lines:

| Resource | Address / PID | Ownership |
| --- | --- | --- |
| PostgreSQL17 |127.0.0.1:18550 /99080 | `.../issue-50-material-import/DGA Lab/.cache/issue50-tests/pgdata`, explicit18550 command; binaries reused read-only from old issue48 export tree |
| Native API |127.0.0.1:18570 /95704 | uvicorn `native_app:app --app-dir` this checkout's `.cache/issue50-browser` |
| Production frontend preview |127.0.0.1:18170 /126964 | current-tree Vite preview and `.cache/issue50-browser/vite.config.mjs` |

`GET http://127.0.0.1:18570/api/health` returned200, `{"status":"ok","database":"ok"}`. Frontend returned200 and actual API-arranged browser flows succeeded. Initial readiness request mistakenly used `/health`, yielding404; corrected immediately to the existing `/api/health` path. This was a probe-path mistake, not an API/runtime failure. Listeners/PIDs were unchanged at final check.

No restart, reset, reseed, process stop, new runtime installation, cluster recovery, file-store replacement or infrastructure mutation was needed. Browser tests use only existing own `dga_browser` fake resources on18550, preserving linked chains. Memory FileStore/fixture workers remain the existing native test seam, not real Azure/MinIO acceptance. Retained18148/18164/18165 and ports18448/18464/18465 were never targeted. No global Docker action.

## Genuine red → green loops

All logs/traces are under this checkout's ignored `.cache/issue50-browser/`.

1. Added two independent real-editor keyboard tests. They clear the actual control, call Playwright `pressSequentially` with2000🙂 in the source note or1000🧪 in the reason, then require the complete value. Neither supplies the long boundary via `fill`, public API setup or React internals. Against accepted production bundle both failed at `toHaveValue`, before any revision submission: `aggregate-red-input.log`, **2failed** (6.9s /6.5s individual). The actual controls clipped the values. Failure contexts/traces: `aggregate-red-input-results/`.
2. Removed only the note/reason native caps. `aggregate-boundary-build.log` passed; the same two real typing tests then submitted successful200 revision responses and verified exact note through public batch read and exact reason through public revision history: `aggregate-green-boundary.log`, **2passed5.6s**.
3. Added finite one-beyond tests:2001-codepoint note,1001-codepoint reason and representative2001-codepoint generic equipment-name input. `aggregate-red-excess.log`, **3failed** (7.6s /7.0s /7.0s individual). Notes/reasons were retained after step2 but lacked explicit validation; generic input was still clipped by its native cap. No backend or runtime failure caused these REDs. Traces: `aggregate-red-excess-results/`.
4. Added explicit codepoint-aware form validation and removed the remaining generic native cap. `aggregate-excess-build.log` passed; `aggregate-green-excess.log`, **5passed12.3s** (both legal cases plus three excess cases). Excess cases assert exact retained input, visible field/count error, invalid accessibility state, disabled save, zero revision POSTs and unchanged public validation revision.
5. Added one shared SITES neighbor. Actual keyboard inputs2001🙂 /1001🧪 remain visible/blocked; Backspace corrects them to2000 /1000; save becomes available; exactly one successful revision occurs and public preview/history retain both full legal values. This is shared-editor coverage, not a new SITES business contract.

## Exact executed verification commands

PowerShell, always explicit checkout workdir. Current-tree Node dependencies were reused; no install or lockfile change. Common browser setup:

```powershell
$env:BASE_URL='http://127.0.0.1:18170'
$env:BROWSER_CHANNEL='chrome'
Set-Location 'C:/Users/weila/.codex/worktrees/issue-50-material-import/DGA Lab/frontend'
```

Commands below used `2>&1 | Tee-Object <log>` and preserved `$LASTEXITCODE`. First two/three failing tests intentionally returned1; all GREEN/build commands returned0.

```powershell
& 'C:/Program Files/nodejs/node.exe' node_modules/@playwright/test/cli.js test tests/device-material-import.spec.ts --grep '实际输入合法非BMP' --output ../.cache/issue50-browser/aggregate-red-input-results
# aggregate-red-input.log: 2failed

& 'C:/Program Files/nodejs/npm.cmd' run build
# aggregate-boundary-build.log: tsc/Vite pass
& 'C:/Program Files/nodejs/node.exe' node_modules/@playwright/test/cli.js test tests/device-material-import.spec.ts --grep '实际输入合法非BMP' --output ../.cache/issue50-browser/aggregate-green-boundary-results
# aggregate-green-boundary.log: 2passed5.6s

& 'C:/Program Files/nodejs/node.exe' node_modules/@playwright/test/cli.js test tests/device-material-import.spec.ts --grep '超过码点边界' --output ../.cache/issue50-browser/aggregate-red-excess-results
# aggregate-red-excess.log: 3failed

& 'C:/Program Files/nodejs/npm.cmd' run build
# aggregate-excess-build.log: tsc/Vite pass
& 'C:/Program Files/nodejs/node.exe' node_modules/@playwright/test/cli.js test tests/device-material-import.spec.ts --grep '超过码点边界|实际输入合法非BMP' --output ../.cache/issue50-browser/aggregate-green-excess-results
# aggregate-green-excess.log: 5passed12.3s

& 'C:/Program Files/nodejs/npm.cmd' run build
# LATEST C2 aggregate-c2-final.log: tsc/Vite pass; index-Dmb31Asw.js
& 'C:/Program Files/nodejs/node.exe' node_modules/@playwright/test/cli.js test tests/device-material-import.spec.ts --grep '实际输入|共享SITES编辑器|合法2000码点|默认设备物料|零设备现场到设备物料|真实发布提交后响应丢失|原修订.*未提交|服务器明确拒绝|另一管理者发布' --trace on --output ../.cache/issue50-browser/aggregate-affected-final-results
# LATEST affected browser aggregate-affected-final.log: 16passed31.9s

& 'C:/Program Files/nodejs/node.exe' node_modules/@playwright/test/cli.js test tests/device-material-import.spec.ts --grep '重复已发布文件|旧REFRESHED|另一经理发布后' --trace on --output ../.cache/issue50-browser/aggregate-key-state-results
# LATEST key state browser aggregate-key-state.log: 3passed4.4s
```

The first final grep used a nonmatching phrase `另一管理者发布`; the actual existing test title uses `另一经理发布后`. The explicit second selection includes that test plus repeat-file and immutable REFRESHED neighbors; all three passed. No pass is claimed for an unselected test. Final affected evidence is19 cases across two sequential runs, not a new whole-browser suite.

Both final trace directories retain traces for passed tests. Existing linked-chain detail/source screenshots are refreshed by the normal chain test, but the direct boundary proof is the actual control/network/public-read assertions and traces. `git --work-tree=<exact checkout> diff --check` passed. Final changed source/test hashes below were stable across the final build and both final test runs.

## Final source fingerprints and evidence limits

SHA256:

| File | Hash |
| --- | --- |
| `frontend/src/features/assets/V2ImportPanel.tsx` | `D5DB03B9317BCD682A0AF499B841EBA2707E42E326CCCDEA8243238BE92AF42D` |
| `frontend/tests/device-material-import.spec.ts` | `7145DAB293FDD4975A89B4EF20C21B5884C29CF1FFA4A91EBBC0340F54F96ED6` |
| unchanged `frontend/src/features/assets/siteImportIntent.ts` | `2EADE3A0AF500775B604399D985FB410B1A795F5AD0B119CE5ED7FF59A61DBA6` |

Latest exact-source evidence: C2 pass,16 affected browser pass31.9s,3 key-state browser pass4.4s. Six new tests exercise the finite accepted input/correction counterexamples; existing business assertions were retained.

No full backend or2000-target capacity rerun: backend is unchanged and controller explicitly retained that meaningful prior evidence. Earlier582pass/40configuredstorage skips, real2000-target publication proof and67pass/1skip full browser are historical evidence in the earlier S3/fix artifacts, not newly executed or whole-current-head claims. The latest changes do not claim fresh whole-head browser/CI acceptance.

## Residual ownership and handoff

| Item | Classification / owner / destination |
| --- | --- |
| Aggregate finding1 | 已修复 by finite current#50 UI change; independent fresh aggregate re-review and controller adjudication remain required. No current implementation blocker. |
|40 configured MinIO/Azurite tests | Exact reviewed-head configured storage CI/controller obligation remains open. Memory fixtures/native browser do not substitute for those contracts. |
| Existing OIDC fixture skip | Inherited#18 explicit protocol-overlay owner; ordinary CI also skips without that overlay/fixture flag. No bypass, CI change or real Okta acceptance claim. |
| Real Azure/Okta/deployment | Existing provider/deployment owners; no new credentials/provider change. |
| Existing sampling-context20 versus lifecycle100 | Pre-existing#61 cross-module /#53 laboratory formal-import ownership; unchanged and not falsely closed. |
| Wider retained history/concurrent module load | Existing#61/controller integration acceptance. Legal2000 publication proof remains valid for unchanged backend. |
| Orphans/cancellation/leases/reconciliation and old payloadless records | Existing#60 owner; current exact new-intent recovery remains protected and tested. No fabricated old input. |
| Historical own-PG lifetime cause | Prior plausible process-tree-wait observation remains unproven historically. No process/runtime change in this fix. |
| Commit/push/draftPR/PR review/exact-head GitHub+Sungrow checks/closeout | Parent Phaseflow controller's later gates only. This artifact does not advance them. |

Implementation explicitly complete. Stop for fresh independent aggregate re-review; do not implement another gate or expand the matrix without a new dispatch or actual defect.
