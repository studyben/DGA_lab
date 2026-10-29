# Issue #18 A3 — narrow site-basic edit

Gate: implementation / code review / fix / re-review passed. Scope approved A3 only.

Asset-owned SiteBasics and PUT basics support revisioned site name/location/status/commissioning date and existing PV/ESS capacities. No customer reassignment, new product line, asset or installation mutation. Own append-only before/after history and audit share transaction. Site detail editor enforces capability visibility and preserves stale edits.

TDD: first missing public-class red → first AM update green; missing HTTP route red → HTTP guards green; browser missing edit button red → edit/conflict/denial green. Review-triggered draft loss regression red → independent edit snapshot green. Full backend 325 passed; tsc/vite build passed; targeted browser flow passed. All runs in dga-issue18-test / dga-issue18-browser (18118), not existing acceptance databases.

Changed scope: backend assets site_basics/public/http/dashboard; main composition; migration0027; tests/test_site_basics; frontend assets editor/dashboard/CSS and browser test.

Review artifact: docs/reviews/code-review-20261002-022543.md. One accepted finding fixed and re-reviewed; no blocking questions. Docs decision: this artifact plus review; final deployment/domain runbook consolidated in C.

Risks: explicit append-only/ESS migration assertions owned by approved C; OIDC owned B1/B2, real Okta evidence tracked by #18/user+IT. Original workspace and acceptance data unchanged; no publication.

Current gate after local checkpoint / next entry point: B1 implementation.
