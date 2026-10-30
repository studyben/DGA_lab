# Issue #52 finite CI browser fix

COMPLETE — 2026-10-30 15:14 UTC. Base HEAD `bd8fd0d591819aeb20d2f95ae8aa256cfa616ef2`, branch `codex/issue-52-lab-import-staging`. Only production/test delta: `frontend/src/features/assets/V2ImportPanel.tsx` and `frontend/tests/site-import.spec.ts`; this document is the sole fix artifact. No commit/push/CI rerun performed.

## Symptom and feedback loop

Root-provided final feedback: GitHub PR/push jobs both succeeded (834 backend,97 browser+1 existing optional OIDC skip). GHE run313695636 passed834 backend but ended96 browser pass/1 failure/1 existing skip. Its sole failure was old site-import flow clicking “发布客户与现场”: initially unstable, then disabled until30s timeout. Evidence: `.cache/issue52-final-ci-sungrow-bd8fd0d.log` lines2255–2300. Expected SQL fault-injection errors were not treated as its cause; all #52 browser cases passed. No network/resource explanation was inferred from different hosts.

Used diagnosing-bugs. Existing retained lab-browser namespace lacked this suite's account/candidate fixtures, so its setup failures were not counted as this bug's RED. Created separate owned nativePG18553/dga_browser, migrated current head and initialized browser fixtures before acceptance. The actual old publicHTTP/UI path ran through production dist on18173/API18573 and the actual asset validation worker. No existing database/port was reset or reseeded.

Tight unattended loop, from `frontend` with `DIAG_USERNAME=<REDACTED>`, `DIAG_PASSWORD=<REDACTED>`:

```text
npx playwright test -c ../.cache/issue52-ci-browser/probe.config.ts
```

The probe follows upload→same-name warning→row review→real revision POST. It delays only delivery of the real follow-up validated GET until after the existing test/user checks warnings; no JSON, IDs, server outcome or permissions are fabricated. `.cache/issue52-ci-browser/probe-red.log`:1 failed5.6s; narrowed instrumented loop:1 failed5.4s (`probe-instrumented-red.log`). Actual observations:

```text
POST: VALIDATED,revision2,error_count0,warning_count2
GET : VALIDATED,revision2,error_count0,warning_count2; same warning IDs
while GET held: checked2/2,publishDisabled=false (stable across browser paint)
after GET delivered: checked0/2,publishDisabled=true
```

Three ranked hypotheses were sent to root/user before further probing: (1) stale local seen-revision marker clears newly checked acknowledgments when the same-version GET arrives; (2) backend changes warning identity despite same revision/count; (3) checkbox/layout action alone loses confirmation. One-variable comparison releases the exact GET before checking instead:1 passed4.1s (`probe-read-first-green.log`). POST/GET warning IDs identical and held checkbox state stable falsify2/3. Persistent regression additionally compares exact revision, summary, issues and reviewed rows between POST/GET. This establishes a user interaction defect, not merely missing test waiting.

## Cause and minimum change

V2ImportPanel's mutation path immediately rendered its authoritative returned batch, but only GET loading updated `seen.current`. After revision2 was already visible and its current warnings were legitimately checked, a subsequent identical GET still compared against revision1 and called `setAck([])`. Hence the original click could first see enabled/unstable and then remain disabled.

The mutation path now synchronizes `seen.current` to the authoritative result immediately after `choose` and before rendering it. `choose` still clears confirmations on mutation; GET still clears them for a genuinely different revision. Publication validation, IDs, permissions, warning requirements, backend schema/storage/dependencies and30-minute CI budget are unchanged. No force click, timeout increase, skip or automatic warning acknowledgment was introduced.

The original site flow now controls this late real GET, checks its full relevant payload is identical, confirms warnings, delivers the GET and asserts confirmations remain checked before normal publication. A separate real new-revision test changes NEW to REFERENCE, retains a differing supplied name, verifies the new SITES `reference_difference` warning ID and requires all warnings unchecked/publication disabled. Its initial assertion mistakenly expected the ASSETS-only `site_name_difference`; corrected to the actual public SITES contract, not counted as product RED.

## RED→GREEN and affected validation

All browser commands used the owned18173 production bundle and Chrome, ordinary-HTTP crypto fallback preserved; credentials remain environment/fixture-only, not in captured signal output.

- Persistent `BASE_URL=http://127.0.0.1:18173 BROWSER_CHANNEL=chrome npx playwright test tests/site-import.spec.ts --workers=1`: before production fix, original flow failed unchecked-after-GET in5.7s (`persistent-red.log`); after fix, entire file **3 passed7.2s**, exit0 (`persistent-green.log`), including original publication/history/download, unknown upload response and true new revision/new warning reset.
- Original minimized loop, unchanged late-GET order, after production fix: **1 passed4.1s** (5.2s overall), checked2/2 retained/publish enabled (`original-loop-green.log`). This reruns the original feedback signal rather than replacing it with a waiting-only test.
- `npx playwright test tests/device-material-import.spec.ts --workers=1`: **25 passed1.7m**, exit0 (`shared-v2-neighbor-green.log`). Covers shared V2 publication, REFRESHED outcome, metadata suspension/abort, exact revision recovery, stale/publication conflicts, Unicode/storage boundaries and SITES editor. Not a repeat of834 backend or472 old neighbors.
- `npm run build`: tsc+Vite PASS,72modules,496.04kB JS,121ms (`build-green.log`). `git diff --check`:PASS. No `[DEBUG` or `console.log` remains in either changed production/test file; throwaway probes/logs are isolated under `.cache/issue52-ci-browser`, not committed.

Bootstrap details are separate from bug verdicts: a relative Tee path failed before runtime startup, and the optional existing material seeder refused its hardcoded5432 boundary at18553. An optional material-fixture probe was denied `SHOW data_directory` as the unprivileged app role before any INSERT. None was called bug RED or silently converted to PASS; the actual isolated site fixture then passed public login/candidate setup and all28 affected browser tests without material fixture modification.

## Ownership / residual

New retained diagnostic resources only: PG17 PID103572, port18553, datadir this worktree `.cache/issue52-ci-browser/pgdata`; API18573 PID78804; production front18173 PID144676; asset worker actualPID149540,parent27428,launcher142084. Startup commands/modules/listeners verified. Local original files stay under `.cache/issue52-ci-browser/files`; SQL namespace verified as dga_browser/dga_browser/public on18553. Old18552/18572/18172 and other workers/resources were preserved; no prune/global restart or data cleanup.

Root's untracked `issue-52-closeout-comment.md` and `issue-52-final-closeout.md` are untouched/un-staged. No other source, backend, workflow, migration or business policy changed. Residual owner: original PR reviewer checks only this finite delta, root accepts/commits and runs new exact-head CI; the old GHE failure is historical evidence, not claimed repaired remotely yet. No genuine blocker. Implementation source is frozen; no further checks or source edits are planned.
