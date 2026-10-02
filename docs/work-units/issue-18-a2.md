# Issue #18 A2 — user management interface

Gate: implementation/deepreview/fix/re-review passed; next entry A3 implementation. Base3834b5a.

## Outcome

Added /settings/users and shared-auth HTTP list/detail/catalog/profile/role-delta/status/recovery-admin routes. Backend emits available target actions and enforces current authorization, origin/CSRF, strict payloads and optimistic conflicts. UI supports filters, paging, explicit errors, role composition and protected-account controls; no ordinary employee password creation.

Successful writes are acknowledged independently of read refresh. Sole role may be replaced atomically; empty final set and last local administrator remain protected. Navigation appears for authorized managers in both workspaces. Current-role matrix updates field-user read-only laboratory browser expectation.

## Tests / review

- TDD HTTP missing routes red then green; real PostgreSQL identity/auth/HTTP50passed.
- Browser absent page red then implemented; identity3passed including immediate existing-session permissions, management/lab-manager limits, single-role replacement and post-commit GET503. Auth2passed separately; TypeScript/productionbuild passed.
- Review/fixes: docs/reviews/code-review-20261002-020607.md, two accepted findings 已修复, bounded read-only re-review no blockers.
- Tests run only in dga-issue18-test and new dga-issue18-browser (18118, disposable fixtures). Original18117/18120 data untouched.

## Residual risks / documentation

All remaining site editing, OIDC security/provider configuration and aggregate regression belong approved A3/B/C. Missing real IT evidence tracked by #18; issue remains open. No GitHub writes, push or merge. Work-unit/review artifacts record this slice; operational docs completed in C.
