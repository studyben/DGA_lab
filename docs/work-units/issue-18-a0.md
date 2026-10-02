# Issue #18 A0 implementation

Gate: implementation and code review complete; next entry accepted slice commit → implementation A1. Plan: issue-18-plan.md; review: ../reviews/code-review-20261002-011518.md.

Changes: protect last ACTIVE local administrator through both existing mutation commands; trusted interactive recover-admin with forced password change and revoked sessions. No migration, grant change or web changes. Exact scope: backend/dga/shared/auth/{public,cli}.py, backend/tests/{test_auth,test_identity_management}.py.

TDD: separate failing disable, demotion, recovery and CLI tests observed before minimal implementation. Parallel status/role races and negative recovery regression run on dedicated test-db. Final 22 passed (4.90s), no failure; two dependency deprecation warnings unchanged. Original acceptance data untouched.

Docs: recovery usage `docker compose exec -it api python -m dga.shared.auth.cli recover-admin --username <existing-local-admin>`; prompted password only, no command-line secret. This does not restore business-DISABLED accounts or promote ordinary users. Deployment not performed.

Residual risks: A1 owns full permission migration/classification/audit detail; A2 UI; B1/B2 OIDC; C full regression; real Okta acceptance tracked #18/user+IT. No push/merge/closure. Findings: none in A0 review.
