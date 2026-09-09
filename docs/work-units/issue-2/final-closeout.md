# Issue #2 final closeout

## Status and next entry point

Gate: final closeout PASS, recorded at 2026-09-08 22:08:55 -05:00. Implementation and draft-PR-pass have passed. The user explicitly authorized publishing the prepared comment and completing closeout while prohibiting merge and later issue implementation. Exact published body is closeout-comment.md; it was posted once and successfully read back through the GitHub API.

Work unit completed. Next entry point: await the user's decision on draft PR #21. No merge, approval, ready-for-review change or direct issue closing was performed; no subsequent issue was started. After user merge, the next development dependency is Issue #3. This closeout documentation checkpoint changes no runtime code or test expectations.

## What changed

- First production slice of the greenfield project: React/TypeScript portal with two workspaces and contextual navigation, explicit business placeholders, and backend connection/retry UI.
- FastAPI composition root, assets/laboratory/condition_analysis public entries, immutable module registry and import-direction constraints.
- PostgreSQL/Alembic baseline, migration-aware readiness, localhost-only Docker Compose, isolated real PostgreSQL test service, dependency locks and CI.
- No later-ticket business behavior, auth, files/jobs or cloud deployment implemented. Throwaway prototype remains unchanged on port 4173; the production foundation is available locally at http://127.0.0.1:8080.

## Verification

- 11 backend checks; 4 Linux production-build browser acceptance tests; TypeScript/Vite build.
- Fresh isolated Compose startup and actual DB failure (503) -> recovery (200), without API restart.
- Final-head GitHub Actions push run 34305583276: success.
- Final-head GitHub Actions PR run 34305585779: success, every startup/API/browser/log/cleanup step passed.
- First run 34305417103 logs explicitly confirmed 11 backend checks and 4 browser tests.
- git diff --check passed; remote/local head matched 8c11df87d4ee654c5541baca1557ee98f3d9e2cb after final push.
- Docker recheck returned Server 29.4.3, healthy API/DB/frontend and HTTP status/database ok. The Desktop runtime socket workaround retained backups; persistent data was not deleted. Recurrence after future host restarts is not ruled out.

## Reviews and documents

- Accepted plan eb58a15; S1 bff9b25; S2 85974f1; S3 88d177c; aggregate ec67372; PR review 8c11df8.
- S2-1 (/assets nginx directory collision): accepted, 已修复 and re-reviewed. No accepted finding remains unresolved.
- Aggregate artifact: docs/reviews/code-review-20260908-215903.md.
- PR artifact: docs/reviews/pr-21-review-20260908-220154.md.
- README covers startup, config, public module boundaries, migration, testing and ticket order. Issue-specific plans/slice/review/evidence files are durable. Pre-existing dirty CONTEXT/PROJECT_PLAN and untracked domain/product/tools remain user-owned and excluded from commits.
- This closeout summary, final state and exact comment body form a documentation-only closeout checkpoint after the accepted PR review commit. Review of this checkpoint checked the live comment URL/body, PR draft state, issue linkage, prior successful CI, scope and remaining owners; no new finding or runtime change.

## PR and issue linkage

- Draft PR: https://github.com/studyben/DGA_lab/pull/21.
- Issue: https://github.com/studyben/DGA_lab/issues/2; parent: #1.
- GitHub metadata verified PR is OPEN and draft, head codex/issue-2-foundation, base main, and closingIssuesReferences contains Issue #2. Body includes Closes #2; merge to default branch is expected to close the issue automatically.
- Issue closeout comment: https://github.com/studyben/DGA_lab/issues/2#issuecomment-5595166387. Published with explicit user authorization and read back successfully. Issue remains open; the PR has not been merged.

## Remaining risks and owners

- Auth/permissions/audit: #3. No internet exposure before the security/deployment work.
- Formal asset search -> sample intake -> test entry -> overall finalization -> barcode report: #4 -> #5 -> #6 -> #7 -> #8. Remaining business capabilities: #9–#19 according to blocking dependencies. Not claimed implemented or tested by this slice.
- Lightsail/TLS/backup/restore/restart policy: #20.
- Formal ASTM methods, thresholds and branded PDF details remain external product confirmations under their owning tickets; no guessed values introduced.
- Dependency maintenance: two nonblocking Python deprecation warnings and GitHub's checkout@v4 Node20-to-Node24 warning. Actual CI passed; maintenance belongs to a later dependency update work unit. These are not hidden failed tests.
- Host Docker recurrence: current environment recovery is verified; future Desktop/Windows socket failures require environment diagnosis, not destructive reset. Backup runtime directories remain recoverable.

## Final decision

PASS. Required comment and issue linkage are verified; no unresolved accepted finding or unclassified residual risk remains. Work unit completed through final closeout. Stop here as requested: keep the PR draft and do not begin later tickets.
