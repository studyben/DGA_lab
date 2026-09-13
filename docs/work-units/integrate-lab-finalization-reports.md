# Integrate completed laboratory #7/#8 into current main

## Goal confirmation and gate

User explicitly authorized this prerequisite integration in an independent branch, preserving #9–#12 and existing workspace/acceptance data, then continuing #13. Local integration/commits are allowed; no remote push, PR merge, issue changes or deployment. Base main `62f26a4`; source `origin/codex/issue-6-test-entry` at `b16c0e4` containing PR #27/#28. Plan accepted8ed06ec. Slice review/fix/re-review passed; next gate aggregate deepreview after local integration commit.

Main lacks the finalization/report migrations and public commands; source retains them but predates asset lifecycle/import work. This is integration of existing intent, not reimplementation. Successful outcome: both capabilities coexist behind the existing laboratory public seam, all original suites and added integration regression pass, and migration upgrade preserves populated current-main records.

## Code-generation-ready plan

One cohesive integration slice: local no-commit merge of b16c0e4, resolve each overlapping file using both histories and their issue plans. Retain main's asset history, import router/FileStore injection, equipment/dashboard navigation and pinned object images; add existing laboratory finalization/report routes, worker and page. Combine FileStore methods and audit capabilities, regenerate dependency lock without removing existing packages. Preserve all tests from both sides. Do not alter root dirty docs or any acceptance stack.

Allowed: incoming #7/#8 files and overlapping application composition, laboratory/asset-history compatibility, shared FileStore/auth capabilities, dependency lock, browser/CI compose wiring, focused integration tests and review/work-unit documentation. No new laboratory workflow design, asset changes or #13 in this slice.

Migration: do NOT rewrite main's already-applied 0009→0005 history or source 0006→0005/0007→0006. Add empty merge revision 0014 with parents 0013_asset_import and 0007_laboratory_reports. Fresh DB and existing main DB reach one head; adding a missing laboratory branch from 0005 is safe because existing asset migrations do not own those tables/columns. Verify public sample/asset readback before and after upgrade using a dedicated isolated database. Never downgrade/seed user data. Any old FINALIZED rows without finalizer must be detected and rejected, not invented.

Integration regression: create main-era asset/sample via public seams with real isolated PostgreSQL, upgrade missing branch, verify identities/snapshot/containers survive; exercise test creation→selection→finalization→report generation/download→withdrawal and ensure asset/import public capabilities remain available. Existing backend and complete browser suites provide previous contract coverage. Include repair-center nullable site/customer snapshots in PDF path if source assumes non-null. Time and storage test doubles only at external seams.

Environment: new Compose projects dga-lab-integration (test-db only) and dga-lab-integration-browser (disposable tmpfs, unused local port 18096); never touch 18093 or original workspace. Build source images; use source bind for incremental backend runs. Browser startup includes BOTH report-worker and import-worker plus object-store and isolated fixture seed; update CI similarly if needed.

Review: planreview then accepted plan commit; merge/resolve; run typecheck and focused/full backend/browser tests; deepreview against fixed main base, including conflict/adversarial/semantic-owner passes; accepted local integration commit and aggregate review artifact/checkpoint. No remote PR gates (explicit user pause). Then continue #13 on a separate local branch based on accepted integration while preserving its blocker note. No automatic main mutation.

## Risks and ownership

- Divergent migration heads: fixed in this integration via additive merge revision and populated upgrade test.
- Shared UI/composition/dependency conflicts: fixed here, retain both intents, no ours/theirs whole-file preference.
- Report snapshot after asset lifecycle enhancements: fixed here if integration incompatibility confirmed.
- Production deployment, backups and source retention: existing #20; not performed.
- Formal ASTM, thresholds and PDF branding: remain out of scope per original #7/#8.

## Reporting

Record source/base hashes, per-conflict decisions, tests/results, fixed findings and remaining risks. Do not claim GitHub issues closed or main integrated until separately authorized remote publication. Integration is a local prerequisite for #13.

## Slice evidence

Review docs/reviews/code-review-20260912-222426.md records all seven conflict decisions and one accepted report-worker data-loss finding. Actual COMMIT-acknowledgement failure reproduced, fixed and independently re-reviewed.149 backend tests passed with2 existing deprecation warnings;19 browser tests passed; TypeScript/Vite production build and diff check passed. Fresh migration and populated0013 upgrade covered without touching real data. Uncertain report object cleanup is deliberately retained/logged for #20 reconciliation, not deleted. One isolated browser stack18096 holds disposable data. Original18093 unchanged.

## Local completion / next entry

Accepted integration slice f14bae1. Aggregate review docs/reviews/code-review-20260912-222620.md passed, no open accepted findings. Current next gate: ready-to-open-draft-PR, explicitly paused before push by user. This is local acceptance only, not full remote Gateflow closeout. Continue user-authorized #13 from the accepted local integration checkpoint, with its own plan, tests, review and commits. Source issues remain open until a separately authorized PR reaches main.
