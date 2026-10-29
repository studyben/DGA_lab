# Issue #18 — local implementation handoff

Status: approved independent implementation and aggregate deepreview complete locally; **real Okta acceptance incomplete**. Not final-closeout pass. No GitHub push/PR/merge/comment/Issue close performed, and no later Issue started.

## Checkpoints

- Baseline latest fetched main: a1c5603251773ad9483ad569663ab491f11bfd8b.
- Branch: codex/issue-18-identity-oidc, isolated managed worktree.
- Accepted plan bc1e331; A0 de50dc9; A1 3834b5a; A2 7219ec3; A3 6adb760; B1 7cd4c97; B2 520e8c0; C c3a1211.
- Aggregate evidence: docs/reviews/code-review-20261002-034653.md. Final accepted deepreview commit contains this handoff and expiry fix; identify via local git log without embedding a self-referential commit hash.

## Delivered

Six-role current-policy enforcement; ordinary/protected target boundaries; user profile/role/status UI with optimistic concurrency; legacy impact report; last-local-admin guard and interactive recovery. Narrow site-basic editing remains asset-owned. OIDC-only signed protocol validation, stable issuer/subject identity, field-engineer first role, explicit verified existing-account binding, immutable encrypted candidates/callback, test-before-activate flow, eight-hour absolute sessions and independent local recovery login. Local credential rotation cannot extend original OIDC expiry.

## Verified

371 real-PostgreSQL backend tests;9 key Playwright flows; TypeScript/Vite build; single migration head0029 and historical forward upgrades; rollback/concurrency/revocation/secret-redaction tests. Protocol tests use isolated signed JWTs, **not real Okta**. Review finding accepted/fixed/re-reviewed; no remaining local blocker. Intermediate proxy502 failure and recovery evidence retained, not counted as passing run.

## Local acceptance environment

- URL: http://127.0.0.1:18118/login/local ; user administration /settings/users, OIDC configuration /settings/sso.
- Dedicated project dga-issue18-browser. Normal `dga.main:create_app --factory` restored; mocked OIDC entry disabled. Healthy proxied API; missing actual IT settings correctly leaves company login disabled.
- Only newly created automated fixture was reset for regression. Original dirty checkout and existing18117/18120 acceptance data were never migrated or reseeded. Do not reuse test Compose seed against those environments.
- Test accounts/credentials remain test-only fixture definitions; no real employee provisioning or external secret installed.

## Remaining gates / owners

Current gate / next entry: ready-to-open-draft-PR, **stop before push** per user. Later authorization is required to publish; PR review has not happened and remote CI has not been claimed. Real IT evidence checklist and migration/recovery operations are in docs/identity-operations.md. User+IT owns supplying registered test application and assigned employee and executing true acceptance. Use secure deployment channels for secrets, not chat/Issues. Keep#18 open; do not use closing keywords until its remaining acceptance is complete. #19 -> #20 chain unchanged and not started.
