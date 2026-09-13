# Issue #15 implementation plan

Gate: plan; goal confirmed by user. Base feab0f2, branch codex/issue-15-transformer-trends. No push, merge, external comments or subsequent tickets.

## Goal and evidence

Give engineers a trustworthy trend for one physical transformer, using only finalized selected report results; preserve sampling context across moves/replacements. Success: equipment -> filtered trend -> source/return context, correct descriptive statistics and visible exclusions.

Assets currently own AssetDirectory and installations. LaboratoryReports already saves immutable report_snapshot during finalization, including selected_results, fields, configuration, sample context and quality warnings. condition_analysis/public.py currently only checks access. No new database table/migration, background job, storage or chart dependency is necessary. Root uncommitted CONTEXT and ADR 0002–0005 constrain domain ownership; preserve those files. Record this task's decisions here rather than copying unrelated docs.

## Contracts and implementation decisions

- Assets public seam: add narrow frozen TransformerIdentity (UUID, system asset number, serial, model) and TransformerReader protocol, implemented by AssetDirectory.transformer_identity(actor,id). Require analysis.read; validate actual asset_type=TRANSFORMER, not machine_type or current installation. Return 404/422 stable AssetQueryError. This permits historical offsite/retired transformers and analysis-only viewers without granting asset mutations.
- Laboratory public seam: add frozen FinalizedMeasurement and FinalizedResultReader protocol, implemented by LaboratoryTrendSource.finalized_measurements(actor,asset_id,start,end). Require analysis.read. Owner reads current-token report snapshots joined to ASSOCIATED, FINALIZED, non-cancelled samples by exact formal_asset_id (never ancestry/serial). Snapshot parsing remains inside laboratory. Typed projection includes test/sample UUID, barcode, sampled/measured times, type/analyte, method ID/name/version, unit, placeholder flag, qualifier/value, site/equipment serial, instrument, warnings. Expose no raw notes, storage keys or actor identities. Snapshot schema validation failure returns explicit error, not guessed data. Query is a single read snapshot, independent of PDF generation readiness. Withdrawn finalization disappears on next read.
- Analysis public seam: TransformerTrends(TransformerReader,FinalizedResultReader).query(actor,asset_id,TrendQuery). No SQL or concrete engine in analysis. TrendQuery validates type/analyte combinations, optional inclusive Chicago start/end dates, optional method_version_id. Convert dates to half-open UTC instants; reject reversed dates and upper overflow.
- Group by exact method-version ID AND unit after type/analyte filters. Missing units and built-in placeholder methods visible/excluded. Same version with inconsistent units not pooled. Default choose newest eligible group; user may select another; requested unavailable group is explicit empty, never silently replaced. Return groups, selected group, points and statistics. Group identifier encodes method UUID and unit so unit collisions cannot mix. No cross-version compatibility inference; blank ASTM reference alone does not exclude managed methods.
- Each point has reasons (placeholder_method, missing_unit, different_method, different_unit, qualified_result), value/qualifier, source context, moving mean/adjacent delta/annualized change if eligible. Latest observation = newest point IN SELECTED GROUP, qualifiers included; latest_numeric separately. Tie order sampled_at,sample_id,test_id. No aggregation of repeat samples. min/max/mean only EQ; delta between consecutive EQ; annualized absolute delta / UTC elapsed days *365.25; no zero-time rate. Three EQ trailing mean. OLS against elapsed UTC days, >=2 distinct instants, slope *365.25. Decimal arithmetic; serialize explicit null plus reason for insufficiency, not zero. Same-time points retained; latest timestamp tie is disclosed.
- GET /api/condition-analysis/transformers/{asset_id}/trends accepts query filters, authenticated analysis.read. Stable 422 invalid query; 404 nonexistent; 503 source unavailable (not empty). Cache-Control no-store. Main composition creates adapters and injects; HTTP remains analysis-owned.
- UI owns display only: /assets/analysis/trends?asset_id=...&return_to=...; permission-gated link on transformer detail. Without asset selection explain to open a transformer from assets. Filters type/analyte/date/group kept in URL; reset group on type/analyte/date change. Chart uses actual sampling-time x positions, distinct special marks for qualifiers, no fabricated ND ordinate; result table traces sample/test/method/instrument/warnings. Never connect incompatible/qualified points as numeric observations. Table paging affects display only, not statistics; all calculations server-side. Loading, failed read/retry, no finalized data and no comparable data states explicit. Same-origin asset detail return URL allowlist; no javascript/protocol-relative return URL. Source report/workbench links shown only with laboratory.read. Small muted explanatory text, 1920x1080 and narrower desktop safe layout.

## Slices and TDD seam

User approved public analysis query + real PostgreSQL seam, minimal browser tests. Test setup via public lab configuration/receive/add/select/finalize APIs and asset import/lifecycle APIs; reuse existing isolated identity/customer/site fixtures only, no private-table assertions. Object storage fake only at external system boundary. Red one behavioral test, implement minimum green, repeat.

### S1 — finalized transformer trend query and HTTP

Allowed: backend/dga/{assets/public.py,laboratory/public.py,laboratory/trends.py,condition_analysis/*,main.py}, backend/tests/test_transformer_trends.py and task artifacts. Prerequisite accepted plan. Build owner projections, query, calculations, HTTP composition iteratively. Tests: no open samples; only selected repeat; physical UUID/replacement isolation; all types; method/unit exclusion and deactivation stability; ND/LT/GT; zero/single/same-time; Chicago DST/end date; withdrawal/refinalization; permissions/errors. Hand worked numerical fixtures, not copied formula assertions. Run isolated dga-issue15-test Compose test-db and api-test; existing containers untouched. Review S1 and commit after pass. No frontend in S1.

### S2 — equipment-to-trend browser slice

Allowed: frontend/src/features/condition-analysis/*, EquipmentDetailPage.tsx, main.tsx, frontend/tests/transformer-trends.spec.ts; backend/tests/seed_trends_browser.py if needed; compose.trends-browser.yaml for isolated seeding only, task artifacts. Prerequisite S1 pass. Implement chart/filter/table/source/return. Build frontend; browser test against separate dga-issue15-browser project and unused port, never seed existing acceptance DB. Browser must cover actual HTTP/data, not route mocks: equipment navigation, group/analyte changes, exclusions, chart and safe return. Add screenshots/geometry at desktop widths; test API errors/loading with deterministic browser network boundary if needed. Review/commit S2, then full regression and aggregate deepreview.

## Accepted plan review corrections

P1: TrendQuery uses optional group_id (maximum 240 characters), a JSON-encoded [method UUID, exact unit] pair, not method_version_id. Clients receive group IDs from the response, never parse them. No selected-key match yields explicit unavailable-group state, not fallback to another group.

P2: Eligibility uses ASSOCIATED + FINALIZED + matching non-null current report token only. There is no sample cancellation field in the current schema; do not invent one. Snapshot managed method configuration presence is the authoritative configured-method fact; absent configuration remains unconfigured, irrespective of ASTM text. Snapshot decoding failures return 503 explicitly; missing optional instrument/quality evidence is legitimate historical data, not a reason to infer compatibility.

## Validation and completion

S2 review correction: add laboratory/ReportPage.tsx to allowed files solely to consume barcode deep-link query and load the existing report read endpoint. Review found the existing page ignored query parameters; no report generation/state/permission changes. Browser source-link regression must fail before this edit and pass after.

Commands: docker compose -p dga-issue15-test --profile test run --rm --build api-test pytest -q -p no:cacheprovider [target]; full suite same without target. alembic heads expected 0018_lab_packages (no new migration). Browser isolated Compose with frontend build and Playwright. Run git diff --check, architecture tests, full backend regression, frontend TypeScript/Vite build and critical browser suite. Never run fixture TRUNCATE against acceptance data.

Report: changes, gate state, commands/counts, review findings and disposition, artifact paths, preserved data, next entry ready-to-open-draft-PR (stop before push per user).

## Risks and destinations

- Scientific equivalence/cross-version mapping and formal thresholds: excluded by explicit user decision; future separately authorized work, not guessed here.
- Historical snapshots without managed configuration: placeholder/unit rules above; no rewriting historical data.
- Runtime/data volumes: small laboratory read-on-demand; no caching because withdrawal must be reflected. Avoid per-point SQL. Fail explicitly on oversized range if needed, never truncate arithmetic silently.
- Main/domain doc divergence: root files preserved; task decisions local plan only. No unrelated cleanup.
- Regression/browser coverage: S1/S2 must close testing gaps before aggregate review. No unclassified residual risks accepted.
