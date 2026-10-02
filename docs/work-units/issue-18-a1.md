# Issue #18 A1 — account policy and migration

Gate: implementation → deepreview → fix → re-review passed. Next entry: A2 implementation.

## Outcome and scope

Identity public interface owns fresh-actor/target authorization, ordinary-account boundaries, AM-only deltas, optimistic revisions, account list/detail/catalog/profile, status changes, safe before/after audit, compatibility role commands and local recovery protection. Migrations0025/0026 apply confirmed six-role policy and identity metadata; legacy role/IDs/passwords retained. CLI role-impact is read-only and works before upgrade.

No OIDC, user-management UI, site-basic write, GitHub publication or existing acceptance migration in this slice. Changed files are shared/auth public/policy/CLI, migrations0025/26, identity/auth and historical migration fixture tests.

## Validation / fixes

- Public-interface TDD on isolated PostgreSQL dga-issue18-test: latest identity/auth 44 passed.
- Full backend 298 passed before final four new tests; no production checks bypassed. Existing two framework deprecation warnings.
- Review/fix/re-review: docs/reviews/code-review-20261002-013944.md, all five accepted findings 已修复; no blockers.
- Historical migration tests now explicitly start at historical schemas, preserving original retention assertions. Fixture helpers seed only allowlisted disposable test/browser databases; not a production provisioning bypass.
- git diff --check passed. Original workspace and acceptance data untouched.

## Residual risks / docs decision

- A2: HTTP/CSRF and frontend acceptance; A3: scoped site edit; B: OIDC security and real-provider behavior; C: full regression including direct audit-write fault injection. All covered by later approved slices.
- Existing-data deployment requires role-impact operator review (existing #18). Real Okta evidence requires user/IT configuration; isolated tests are not acceptance and Issue remains open.
- Scope documentation in work-unit/review artifacts; no unrelated domain doc changes. Local checkpoint only, no push/merge.
