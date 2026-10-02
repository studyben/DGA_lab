# Issue #18 B1 — OIDC custody and protocol

Gate: implementation / review / fix / re-review passed. Artifact: docs/work-units/issue-18-b1.md.

Changes: encrypted immutable candidates, redacted configuration read, browser/session-bound ten-minute single-use TEST flows, fifteen-minute same-admin proof, safe audit, bounded HTTPS allowlisted endpoints without redirects, Authorization Code + PKCE S256 through maintained library, signed RS256 ID-token checks. Local login unaffected by missing/invalid encryption key. No activation or employee login exposed yet.

TDD evidence and finding: docs/reviews/code-review-20261002-024231.md. 26 OIDC public/protocol tests passed; preceding combined identity run55 passed. Network clock review finding fixed and independently re-reviewed. Generated hash lock only adds three necessary packages.

Original checkout and acceptance data untouched. No real Okta calls, no new credentials/paid services, no pushes. Migration0028 applied only to isolated test database. Docs decision: operational configuration and real-acceptance checklist consolidated in C.

Residuals classified in review: B2 owns employee login/activation/binding/HTTP/UI; C owns remaining fault injections and regression; #18 with user+IT owns actual provider acceptance. Issue remains open.

Current gate after local checkpoint / next entry point: B2 implementation.
