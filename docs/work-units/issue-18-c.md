# Issue #18 C — regression and operational handoff

Gate: implementation/code review/re-review passed for bounded C changes. Branch codex/issue-18-identity-oidc; base520e8c0. Artifact: docs/work-units/issue-18-c.md.

Added first external account provisioning audit in the same identity/session transaction. Red test first failed on missing OIDC_PROVISION, then minimal implementation passed. Added real PostgreSQL concurrency, proof expiry, network-time authority/config changes, audit rollback, wrong key/local recovery, historical candidate migration, ESS capacity isolation and append-only history tests. No new feature beyond approved slices.

Updated README, scoped ADR-0007 and docs/identity-operations.md: six-role permissions, legacy migration impact, operator recovery, immutable candidate/callback setup, secret backup/rotation limitations and real IT evidence checklist. Four optional OIDC deployment variables reach API only. Original uncommitted documents were not overwritten.

Validation/review evidence: docs/reviews/code-review-20261002-033948.md. 369 backend tests, 9 key browser tests and TypeScript/Vite build passed. Actual application/proxy callback log probes passed. Normal API entry restored on18118; protocol fixture is not active. Real Okta remains unverified.

Residual risks classified in C review: aggregate owns combined-path review and password-rotation expiry finding; existing#18/user+IT owns true Okta acceptance; #20 owns production-specific edge proxy and deployment validation. No claim of final closeout or complete Issue18.

Next entry after local accepted C checkpoint: aggregate deepreview -> fix -> re-review -> accepted deepreview commit -> stop before push under explicit user restriction. Never use Closes#18 while real acceptance remains incomplete.
