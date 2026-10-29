# Issue #18 — goal confirmation (confirmed)

## Gate / scope

- User confirmed all four recommendations on 2026-10-02. Current gate / next entry: plan.
- Branch: codex/issue-18-identity-oidc. Latest fetched main baseline: a1c5603251773ad9483ad569663ab491f11bfd8b.
- Isolated managed worktree: C:/Users/weila/.codex/worktrees/issue-18-identity-oidc/DGA Lab.
- Original workspace G:/Sungrow Develop/DGA Lab remains dirty and untouched. Existing acceptance databases/containers are not used for migrations or test seeding.
- Issue: https://github.com/studyben/DGA_lab/issues/18, updated single-ticket identity/roles/OIDC scope. No additional Okta ticket.
- Source decisions: original workspace CONTEXT.md, PROJECT_PLAN.md section six, ADR-0004 and ADR-0007; newer user decision chooses OIDC only. Original uncommitted domain files are read as requirements, not bulk copied over main. ADR-0007's pending protocol wording is stale relative to this decision.

## Goal and first-principles judgment

Provide internal user management, composable six-role business authorization, stable OIDC identities, independently recoverable local administrators, and tested candidate-to-active OIDC configuration. Authentication transport must not become the owner of business roles; three business modules retain their public application interfaces.

Success means unauthorized requests cannot bypass UI restrictions, role deltas preserve unrelated grants, local disablement revokes sessions, concurrency cannot remove the last local recovery administrator, and real Okta acceptance verifies assigned-user login and eight-hour absolute session constraints. Missing IT setup permits isolated implementation/testing, not a claim of real acceptance or closing the Issue.

## Direct code evidence

- backend/dga/shared/auth/public.py: IdentityService._assign_roles deletes and recreates the entire role set; set_roles and set_status have one broad identity.manage guard and no last-local-admin invariant. Existing sessions rebuild actor permissions and status changes delete sessions, reusable foundations rather than a new auth stack.
- backend/migrations/versions/0002_identity.py: users require password_hash; six old seeded roles include management_readonly and broad asset_manager assets.write. External identity/local credential distinction and safe migration must be designed, not inferred from display labels.
- backend/migrations/versions/0023_alarm_acknowledgement.py grants AM acknowledgement as well as system_admin, lab_admin, analyst and field_engineer; proposed new single-role matrix differs.
- backend/dga/assets/http.py exposes site-detail reads, but no site-basics mutation. Delivering AM/management site editing requires a narrowly owned asset command/UI, not broad assets.write.
- No OIDC callback/configuration management exists in the shared auth HTTP boundary. Existing CLI bootstrap/provision/status/role operations must obey new safety invariants too.

## Non-goals

No SAML, dual-protocol fallback, external customers, self-registration, arbitrary permission editor, company-wide directory sync, audit export implementation, service work orders, new cloud resources or unsolicited employee contact. No unrelated repairs to historical domain-document differences. No push, PR creation, merge, subsequent Issue or premature Issue closure.

## Confirmed decisions

1. System admin, lab manager, analyst and field engineer can acknowledge alarms; AM/management alone cannot. Lab configuration and health-rule authoring/approval limited to system admin and lab manager; analyst can use configured methods, not administer policy. Security audit reading limited to system admin and lab manager; no audit-export UI in this Issue.
2. Ordinary target means no system_admin or lab_manager role. Lab manager may edit ordinary profiles, assign ordinary roles, disable and unlock them; not restore disabled accounts or touch privileged/local-recovery accounts. Management may only add/remove AM for ordinary targets, with no account-state/profile changes. A manager cannot assign management to self to obtain new capabilities; recommend prohibiting self role mutations except system-admin operations subject to recovery protection. Multi-role actors use explicit authorized capabilities, not assumed rank.
3. Keep old management_readonly as a nonassignable compatibility role until an explicitly approved per-account mapping is executed; do not auto-convert to management or field engineer. Preserve existing credentials/IDs/data; no mutation of acceptance DB. Produce dry-run migration impact for all existing role grants, not only the retired role. New local credentials are administrator recovery only; old ordinary local credentials remain during controlled transition and are not deleted silently. No email-only auto-link of OIDC identities.
4. Include minimum site-basic editing to fulfill #18 authorization acceptance, with independent permission, optimistic concurrency and audit. Exclude customer reassignment, general master-data CRUD and asset lifecycle redesign.

## Validation / residual risks / docs decision

- Preflight, current Issue and actual main code read; managed worktree created clean, branch at verified main. No implementation, migration, account mutation or tests run in this gate.
- Application policy and legacy transition boundaries above are confirmed; no remaining goal-confirmation blocker.
- Covered by later slices within this work unit after goal approval: identity storage, migration, permission delta commands, site-basic seam, OIDC protocol security and configuration lifecycle.
- External IT owner: test/production registration isolation, issuer/client credentials, registered callback URLs and authorized test identities. Never store secrets in Issues/review artifacts. Real verification may remain blocked independently of local completion.
- User publication restriction overrides Gateflow automatic publication: stop before push; no final-closeout pass while real acceptance or publication gates remain incomplete.
- Artifact: docs/work-units/issue-18-goal-confirmation.md. Preserve source docs; approved decisions will be captured in scoped branch artifacts in the plan gate, without importing unrelated dirty changes.
