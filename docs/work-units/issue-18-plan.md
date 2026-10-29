# Issue #18 implementation plan

Gate: plan. Goal confirmed by user 2026-10-02; baseline a1c5603251773ad9483ad569663ab491f11bfd8b, branch codex/issue-18-identity-oidc. Scope: one expanded Issue #18; no publication, merge, closure or #19 work. Original checkout and running acceptance databases are outside mutation scope.

## Goal, motivation, success

Deliver internal account management with composable business roles, separately recoverable local administrators, OIDC employee login and candidate/test/activate configuration. Existing shared identity remains owner of authentication/authorization, not the three business modules. Success: permissions enforced at public interfaces, last local administrator survives concurrent commands, disabled sessions fail immediately, immutable external identity and maximum eight-hour OIDC sessions, configuration failures preserve active settings. Real Okta acceptance remains separately required, never inferred from protocol mocks.

Sources: Issue #18; goal-confirmation artifact; original checkout CONTEXT.md, PROJECT_PLAN.md section six and ADR-0007. Latest user OIDC-only choice supersedes ADR's pending protocol wording. Import only relevant decisions into branch docs, not unrelated dirty domain changes. Do not restore the removed grid-year UI just because older source docs still mention it.

## Evidence and scope

IdentityService already owns Argon2 credentials, opaque sessions, audit and authorization refresh. set_roles/set_status currently lack target policy and final administrator protection; audit lacks before/after. users.password_hash is non-null; no OIDC identity/config storage. No user management HTTP/UI exists. AssetDirectory site reads have no basic-edit command. Migration head is 0024_alarm_observation.

Non-goals: SAML, directory synchronization, external users, bulk employee actions, arbitrary permission editor, customer reassignment, new master-data CRUD, work orders, export implementation, new infrastructure/paid services, speculative domain refactoring. Current changes are minimal capabilities required by #18 rather than replacement auth or generic IAM platform.

## Approved capability matrix

Codes remain stable: system_admin, lab_admin (label 实验室经理), analyst, field_engineer, asset_manager, management. Roles compose by union. management_readonly is nonassignable legacy compatibility, with its existing read permissions unchanged.

| Capability | Roles |
| --- | --- |
| assets.read, laboratory.read, analysis.read | All six |
| assets.write, assets.history.correct | system_admin, lab_admin |
| assets.site.edit | system_admin, lab_admin, asset_manager, management |
| laboratory.write, laboratory.finalize | system_admin, lab_admin, analyst |
| laboratory.configure, analysis.write, audit.read | system_admin, lab_admin |
| analysis.acknowledge | system_admin, lab_admin, analyst, field_engineer |
| identity.manage | system_admin |
| identity.ordinary.manage | lab_admin |
| identity.am.manage | management |
| OIDC configuration and DISABLED restoration | system_admin only |

Actual existing permission codes are inventoried before migration; do not create duplicate synonymous codes. Management has no asset-wide write or alarm acknowledgement. Ordinary target: no system_admin/lab_admin, not local recovery admin. Lab manager can edit ordinary profile/ordinary roles, disable or unlock, not restore DISABLED. Management can only add/remove AM on ordinary target. Non-system-admin cannot change own roles. Identity target checks use current DB actor and target under serialized transaction, not a caller-supplied stale ActorContext. UI gets explicit available actions, not inferred rank.

## Contracts, persistence and security

### Accounts and migration

Keep UUID/username/history and existing password hashes. Add local-credential classification (legacy or recovery; external users have no password), monotonic user revision, and append-only identity audit details (before/after safe profile, role and status values only). No hard deletion endpoint. Existing system_admin with password is recovery-capable; last ACTIVE such user cannot lose admin role, be locked or disabled. Temporary brute-force cooldown does not change ACTIVE state; local trusted recovery command clears cooldown and resets password, forces change, revokes sessions and audits actor as local operator. OIDC-only administrators do not count toward protection.

Migration 0025 adds identity metadata and confirmed role grants, preserving existing assignments; management_readonly stays unassignable and is never mapped. A read-only CLI role-impact command works before upgrade and lists each username/UUID, old/new effective grants and added/removed permissions; deploying existing databases requires operator review of that report and explicit application. No acceptance database is upgraded by this task. Role-name changes do not change stable role IDs. Downgrade cannot drop new identity history or OIDC-only users silently; fail explicitly if data would be lost, document backup/forward recovery.

IdentityService remains public facade: list_users(actor, query/status/role/page), user_detail(actor,id), role_catalog(actor), update_profile(actor,id,display_name,expected_revision), change_roles(actor,id,add,remove,expected_revision), set_status(actor,id,status,expected_revision optional for legacy CLI), provision local recovery admin, trusted recover_local_admin. Existing set_roles remains compatibility command applying same policy/recovery invariants. Validate roles before mutation, preserve unrelated roles in delta command; empty role set rejected. Read models never expose hashes, sessions or OIDC secrets. Current account revisions prevent stale UI overwrite. All management commands acquire advisory lock 30003 before user locks, serializing actor/target checks and last-admin count. New local credential creation is recovery-admin only; test fixtures for old ordinary local accounts explicitly seed legacy setup, not a production bypass.

HTTP: /api/auth/users list/detail/profile/roles/status, /api/auth/roles. Reads use session; all writes origin+CSRF; extra payload keys forbidden. Consistent 403 permission_denied, 404 user_not_found, 409 stale_user/last_local_admin, 422 invalid_roles/invalid_status. Failed authorized attempts audit safe action/result without secret input. Successful mutation and audit share transaction. Cross-module ActorContext still contains effective permissions only. Existing requests refresh roles through IdentityService.session; no private identity table access in business modules.

### Site basics

Asset-owned SiteBasics command exported through assets.public; update name/location/grid and operation status/commissioning date/existing product-line MW,MWh, with expected revision. No customer_id, installation or asset keys accepted; cannot add/remove product line through this command. Nonnegative finite capacities, ESS energy permitted, PV energy prohibited. Same site row lock protects shared basics and capacities; optimistic revision rejects stale writes. Audit before/after in asset-owned event, no historical oil-sample snapshot rewrite. GET site detail adds revision. PUT /api/assets/sites/{id}/basics uses assets.site.edit. Existing main site detail gets compact edit form for allowed actors, conflict/errors preserve entered values.

### OIDC

Add auth/oidc.py owning orchestration and auth/oidc_provider.py owning HTTP/OIDC library adapter; callable dependencies clock and provider transport are external seams. Use maintained Authlib for Authorization Code + PKCE S256 and signed ID token validation, cryptography Fernet for secrets; do not hand-roll signatures. Public composition in main; no business table access. Official references: https://docs.authlib.org/en/stable/oauth2/client/http/index.html and https://developer.okta.com/docs/concepts/auth-servers/ . Org issuer is sufficient for OIDC; do not assume paid custom authorization server or /oauth2/default.

Schema migration 0026: external_identities unique(issuer,subject)→user UUID; encrypted immutable oidc_config_versions; one active-config pointer; expiring one-use flow rows with hashed state/browser binding, encrypted verifier, nonce, config ID, purpose LOGIN or TEST, initiating admin/session hash for TEST, issued/expiry; test evidence bound to exact config and initiating admin. Settings adds secret encryption key and exact deployment allowlist of Okta hosts. HTTPS issuer/endpoints only, exact allowed hostname, no redirects to other hosts; callback fixed /api/auth/oidc/callback with origin from deployed allowlist (HTTP loopback only local). Endpoint allowlist prevents credential exfiltration/SSRF. Missing key/host setup disables OIDC features, never local recovery login. Secret never in API readback, audit, URL or error logs.

Start creates flow (10-minute expiry), state, nonce, verifier and browser-binding HttpOnly SameSite=Lax cookie; authorization request openid/profile/email, prompt=login, max_age=0, PKCE S256. Callback validates browser binding and atomically consumes state before token exchange, prevents replay on failures as well. Exact issuer/audience, authorized party for multiple audiences, nonce, exp/iat/auth_time, signature algorithm allowlist RS256 and JWKS kid required. Provider timeout yields safe error, no token logged; access/ID tokens discarded after validation, no refresh token requested/stored. Verify token through library plus claim constraints. Protocol transport tests exercise real token validation with locally signed test keys, not a fake that bypasses validation. No direct arbitrary return URL: redirect fixed /assets or /settings/sso.

Successful LOGIN checks active configuration unchanged after network round trip, serializes external identity lookup/create and user status. Stable issuer/sub owns identity; roles claims ignored. First identity receives field_engineer and random internal username, display name bounded. A pre-existing matching email/username conflict is refused for explicit administrative association, never auto-linked. Provide systemadmin-only explicit binding to an existing account using verified login proof with target revision and unique issuer/sub; do not relink an already bound identity. No provider-driven changes to roles/status. New app session expiry exactly verified-login time +8h, not settings.session_hours or subsequent activity; locally disabled/locked account rejected. External accounts cannot use change-password endpoint. Local account login remains separate and independently functional.

TEST callback revalidates initiating administrator session/authority, does not create a business user or replace local admin session. Proof binds candidate config ID plus initiator and successful validated external identity. Save candidate never alters active pointer; test failure retains active. Activate rechecks actor, candidate ID, matching successful proof (15-minute validity), same admin, and expected active revision in one transaction. Concurrent edit/test/activate cannot activate changed candidate. Real external HTTP is the production adapter; test adapter available only through in-process injection, never HTTP flag/environment bypass. Mock proof never exists in a deployed app. Settings UI labels local test evidence vs real acceptance honestly.

## Ordered small slices (one at a time)

B2 review correction (ADR-0007 alignment, no goal expansion): registered callback_url belongs to each immutable candidate, editable in Settings within deployment callback-origin allowlist and fixed /api/auth/oidc/callback path. Deployment default only prefills new candidates. Start rejects a different browser Origin before redirect (host-only binding cookie); pre-B2 candidates without stored callback require explicit recreation/retest, never silent fallback. Sequential migration0029 preserves their records. This supersedes the earlier service-global callback description above. Nginx OIDC prefix retains query-free status/timing logs and suppresses raw-request error logs, including noncanonical callback paths. Review artifact code-review-20261002-031441.md.

Each slice: red public-interface test → minimal implementation → repeat, then deepreview/fix/re-review artifact and protected local commit. No bulk imagined tests. Tests query observable public outcomes, not internal schema except migration fixtures.

### A0 — last local administrator safety

Files: shared/auth/public.py, CLI, tests/test_identity_management.py, relevant old test_auth expectation. Prerequisite accepted plan. Only prevent set_roles/set_status from removing last ACTIVE password-backed system_admin; existing users are all local at this baseline. Lock 30003 before actor/target reads, count active role and credential holders under that lock. Add trusted recover_local_admin(username,new_password): existing password-backed system_admin only, no creation/promotion/reactivation of DISABLED accounts, clear transient/manual login lock, force password change, invalidate sessions, audit LOCAL_ADMIN_RECOVERY with no password. CLI interactive recover-admin, no password argument. Tests: last admin disable/demotion/lock rejected; another admin allows normal changes; competing changes retain one; recovery works without old password and invalidates existing session. No role grants/migration/OIDC/UI. A1 refines credential eligibility when external accounts become possible. Completion: targeted real PostgreSQL auth tests pass and code review accepted; residual broader policy owned by A1.

### A1 — account policy and migration

Files: shared/auth/public.py, private identity policy helper if needed, CLI, migration0025, tests/test_identity_management.py and auth legacy fixture/expectations. First tracer: last local administrator cannot be disabled or demoted; subsequent concurrent two-admin race, trusted recovery, ordinary manager target limits, management AM delta, stale role actor, revocation, safe audit. Add account read interface only as needed for assertions. Existing compatibility commands get same checks. Implement role-impact CLI and six-role grant changes with explicit legacy fixtures. No UI/OIDC or site edits. Complete when public-interface and existing auth tests pass, invariants and audit verified. Stop on unapproved legacy mapping, not missing real Okta credentials.

### A2 — web user management

Files: auth HTTP, main wiring, frontend features/identity, Auth/main/nav, browser identity tests. Dependencies A1. Search/filter/detail/catalog/profile/role deltas/status action controls, CSRF and extra-field rejection. No local ordinary password screen. Independent local recovery admin creation available to sysadmin; password transient/redacted. Empty/error/403/409 states visible; AM management UI preserves other roles. Browser acceptance administrator edits roles→existing session permissions change; management cannot mutate privileged target; lab manager cannot restore disabled. Backend tests verify forged requests. No OIDC configuration yet.

### A3 — narrow site-basic permission

Files: assets/public exported SiteBasics, private site_basics.py, assets/http.py, migration0026-site if OIDC then0027, DashboardPage and asset UI, site permission tests. Dependencies A1. Exact command above; no cross-module reads. Test AM edits basics but cannot move/replace/import/reassign customer; field cannot edit; stale revision loses no data; laboratory sample snapshots unchanged. Browser edit success/conflict/denial. Adjust migration numbers sequentially to one head. Existing asset tests remain intact.

### B1 — OIDC configuration custody and flows

Files: shared/auth/oidc*, config, requirements.in/lock, sequential migration, identity public integration, tests/test_oidc.py. Dependencies A1. First tracer candidate save reads redacted with local login unaffected; encrypted durable custody, authorization, flow one-use binding, protocol adapter validation. No user-facing enable bypass. Test negative state, nonce, issuer/aud/azp, expired/invalidsignature, redirect, timeout, replay and concurrent callback. Authlib version/hash lock with minimal transitive dependencies, no unrelated dependency upgrades. No real provider calls without IT setup.

### B2 — OIDC session lifecycle and activation

Same auth files plus HTTP/main, auth UI and settings page. Dependencies B1,A2. First tracer verified external login returns same user on repeat with roles unchanged; then local disabled refusal, identity conflicts, expired session, no sliding, test-login→explicitactivate, same admin, stale config rejection and old-config survival. HTTP login entry/callback fixed redirects and errors; separate local recovery entry. Browser local flow and controlled-provider journey, test/activate failures. Public DB persistence tests reopen service to verify. No assertion of real Okta success.

### C — regression and operational handoff

Files: targeted docs/work-units, reviews, scoped ADR/update, runbook, test evidence and necessary regression fixes only. Dependencies A/B. Full PostgreSQL suite, module-import guards, frontend typecheck/build and key browser acceptance. Migration fresh + previous baseline fixtures forward; no destructive existing-data downgrade test. Role-impact report, recovery commands, secret installation/backup/rotation, IT setup checklist and real evidence template. Aggregate deepreview, fix/re-review. Stop before push. #18 remains open until IT supplies assigned test employee, test app issuer/client secret/registered callback and actual real acceptance covers unassignment/disable/relogin/max session, candidate activation and local fallback. No automatic #19.

## Validation commands and gates

Dedicated Docker project dga-issue18-test, explicit unused subnet, test-db tmpfs; no production/acceptance DSN. `docker compose -p dga-issue18-test -f compose.yaml -f <isolated-network-overlay> --profile test run --build --rm api-test pytest -q tests/test_identity_management.py` (target changes per cycle), then full api-test. Browser project distinct port and seeded data, never dga-issue17-browser. `npm ci`, `npm run build`, declared package test command for browser. Existing Docker image pull failure is diagnostic blocker, not permission to bypass checks or replace storage. Preserve test failure output as evidence.

Review artifacts under docs/reviews with actual system timestamps; findings accepted/rejected-with-reason/deferred-with-owner/needs-more-evidence, re-review statuses and classified risks. Accepted plan/slices local commits only; before each inspect branch/status and stage exact files. No pushes by Gateflow default (user prohibition wins).

## Risks / documentation / completion report

- IT real configuration and test identity missing: tracked by existing #18, owner user+IT; does not block A/B isolated work, blocks real acceptance/closure.
- Actual current account role migration impact: read-only report and operator approval before any existing-data deployment, tracked #18. Original acceptance untouched.
- Browser accessibility/layout and new matrix old test assumptions: covered by A2/A3/C, not deferred to next issue.
- Protocol/security and concurrency: covered B1/B2 + aggregate review, not claimed from happy-path mocks.
- Migration rollback: preserve identity history, use backups/forward fix; no destructive default downgrade.
- Existing unrelated dirty doc contradictions: preserve original; relevant changed identity decisions get branch documentation only.

Completion report must state actual gates/commits, tests run and counts, findings/status, unchanged acceptance environment, no push/merge, missing real Okta evidence, exact next entry point. Do not say full Issue completed or prepare closing keyword while real acceptance pending.
