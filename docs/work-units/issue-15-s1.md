# Issue #15 S1 — finalized trend query

Gate: implementation -> code review -> fix -> re-review passed. Base feab0f2. Artifact: docs/work-units/issue-15-s1.md.

Changed: assets/public.py (TransformerReader/identity, additive equipment asset_type), laboratory/public.py/trends.py (typed finalized projection), condition_analysis/public.py/statistics.py/http.py (read-only query, statistics, transport), main.py composition and test_transformer_trends.py.

Red/green evidence: first import failure -> finalized-selected test pass; missing groups -> grouping pass; missing statistics -> irregular-time/equal-time pass; ignored date/type -> Chicago/DST/query validation pass; missing HTTP route -> authenticated transport pass; default A/B/A group regression -> latest_group_id fix pass; corrupted EQ/null, unknown qualifier and empty fields failed -> typed snapshot owner validation pass; equipment asset_type absent -> additive public fact pass. No thresholds, method equivalence or data migrations introduced.

Validation: dedicated Compose project dga-issue15-test uses tmpfs test-db (guarded host/user/database); full backend run 212 passed (37.18s), then additive equipment fact verified by 34 targeted trend/equipment/architecture tests. Existing FastAPI/Starlette deprecation warnings only. No acceptance database touched. All behavioral assertions use public contracts; corrupt snapshot injection is deliberate storage-failure arrangement, not private-table success assertion.

Review: docs/reviews/code-review-20260913-115754.md. Accepted P2 snapshot semantic validation fixed and independently re-reviewed. Controller also walked query -> owner reads -> grouping -> calculate -> HTTP error chain. No writes/caches, explicit unavailable states, exact physical UUID, blank ASTM permitted managed configuration. Equipment type exposure is additive source fact, not classification inferred by UI.

Residual risks: browser and final HTTP UI are covered by approved S2; aggregate final regression will rerun latest tree. Scientific cross-version compatibility remains excluded by confirmed user decision. No unclassified risks. Docs decision: scoped contracts and accepted criteria in issue-15-plan.md, root domain/user edits untouched.

Current / next gate: accepted slice commit S1, then implementation S2. No external publication authorized.
