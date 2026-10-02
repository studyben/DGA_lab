# Issue #18 B2 — employee sessions and explicit activation

Gate: implementation / code review / fix / re-review passed. Artifact: docs/work-units/issue-18-b2.md. Base 7cd4c97; local branch codex/issue-18-identity-oidc.

Implemented stable issuer/sub accounts, first-login field_engineer only, ignored provider role claims, unchanged local roles/status on subsequent login, eight-hour absolute sessions, no refresh, explicit recent-proof binding of existing accounts, candidate TEST/activate/LOGIN HTTP, independent /login/local and administrator-only /settings/sso. Missing IT configuration leaves local login usable. External-only accounts have no local change-password UI/credential.

ADR-0007 review correction: callback address is editable within deployment origin allowlist and frozen in each candidate (0029). Both authorization and redemption consume that exact value; start Origin must match. Old unbound candidates retained but rejected until explicitly recreated/retested. No migration of any prior acceptance database. OIDC callback prefix logs only query-free status/timing; raw upstream error channel suppressed and Uvicorn query filtered.

Review: docs/reviews/code-review-20261002-031441.md. Both findings accepted, fixed, independently re-reviewed. Tests first demonstrated missing activation/UI, then the preferred_username/email collision edge and missing immutable callback. No threshold/provider compatibility guessed.

Validation: OIDC/API34 passed after corrections; full backend358 passed before callback correction; latest frontend TypeScript/Vite build passed; two Playwright tests passed including candidate save/test/activate, failed test retains active, external least-privilege and local recovery. Docker browser uses explicit test-only transport mapping internal origin to registered loopback, not real-domain/Okta acceptance. Provider fixture signs actual JWTs through production validation; never an environment bypass in deployment app.

Residual classification: C covers full post-fix regression, logs under upstream failure, concurrency/fault-injection/persistence and migration/documentation checks. Existing #18 (user+IT) owns real assigned-user/disabled/unassigned employee, actual registered-domain callbacks, operational secret custody and recovery acceptance. No PR/push/merge/Issue close. Original worktree and acceptance data remain untouched.

Next entry after accepted local checkpoint: C implementation/regression and operational handoff.
