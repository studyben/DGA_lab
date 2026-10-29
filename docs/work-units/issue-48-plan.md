# Issue #48 implementation plan

Date: 2026-10-29. Gate: plan. Goal confirmed by the user; parent #47 and issue #48 are the accepted scope. Base: 68e4d278e3e2a6b3e976036e3581b3ff2a7a773a. Branch: codex/issue-48-site-export. No push, PR, merge, external comments or subsequent tickets.

## Goal / motivation / success

Provide one-click XLSX containing every currently readable physical site, once per site, independent of pagination, filters and product line. Preserve UUID identity, nulls, official capacities and text safety. Public permission is assets.read. Provide complete generation before success, UI feedback and auditable scope/count. No customer/site/device maintenance or import-write work.

Goal artifact: docs/work-units/issue-48-goal-confirmation.md. User confirmed the exact scope on 2026-10-29. Previously supplied AGENTS.md instructions have been revoked by the user; their old enforcement is not assumed. Explicit user/issue/spec constraints still apply.

## Evidence and design judgment

- AssetImports.template currently limits reference sites to500 and expands product-line joins; not a complete export.
- AssetDirectory already owns official site reads; use its public seam, with a private asset-owned XLSX builder.
- assets.http has /sites/{site_id}; register literal /sites/export before it.
- DashboardPage is the shared site table; AssetImportPage contains the existing template download. Reuse a small button component, not a generic export framework.
- Current AuditTrail supports append-only events but no metadata; scope/count require a narrowly additive details object, not a separate export business table or full audit UI.
- PostgreSQL roles currently have global assets.read, not row-level tenants. Export all sites under that existing policy; do not invent filtering/security rules from UI filters.
- Missing source notes have no write source on main. Export an empty source_note column; #49/#50 own subsequent provenance writing and #61 its integration.

## Contracts and exact behavior

1. AssetDirectory.export_sites(actor) requires assets.read before querying or creating files. It returns SiteExportFile: readable/seekable BinaryIO, filename, generated_at, site_count and export_id. Caller owns closing; HTTP adapter consumes and closes. Workbook formatting/SQL remains asset-owned, not in transport/frontend.
2. Private builder performs a single site query ordered by site_name,id under REPEATABLE READ, left-joining PV and ESS capacities independently; includes sites without any configured line. Server-side iteration/partitions avoid a full list. It never joins equipment or drops sites for no device. One physical site is one row.
3. Workbook schema site-reference-v1, Sites sheet columns (stable order): site_id, site_name, customer_id, customer_name, location_text, product_lines, pv_power_mw, ess_power_mw, ess_energy_mwh, commissioning_date, grid_status, operation_status, source_note. Units are explicit in keys and Instructions; product_lines is PV, ESS, PV;ESS or empty. Existing controlled status codes retained with Chinese legend. Date is ISO YYYY-MM-DD text. All identifiers/text cells explicitly string typed. Decimal capacity values use exact decimal text so Excel's15 significant-digit limit cannot silently round a16,6 value. None remains a blank cell; no grid_year.
4. Instructions sheet contains schema version, generation timestamp (aware UTC), all-readable-sites scope, actual count and all column Chinese meanings/unit/empty-value semantics. There are no data rows disguised as instructions. No provenance is guessed.
5. Generate with write-only openpyxl and a SpooledTemporaryFile capped at1MiB memory, spilling to OS temp; complete workbook/ZIP before return and rewind. Close file/workbook on every error. The private XLSX adapter explicitly closes each opened write-only worksheet writer and removes its temporary XML on failure; Workbook.close alone is insufficient. Keep this third-party cleanup narrowly contained and test filesystem leftovers; do not export writer internals. Generator errors map through an asset-owned failure to AssetQueryError('site_export_unavailable',503), not SQL/text/data leakage. No response is started on generation/audit failure. No arbitrary500-row limit; XLSX worksheet row hard limit returns an explicit unavailable error rather than truncated success (millions-of-sites future scale is a documented limit, not current business cap).
6. Add migration0025_site_export_audit with nullable/default-empty JSONB details on audit_logs, preserving append-only trigger and old events. AuditTrail.append gets optional details; IdentityService.audit_events exposes details under existing audit.read. No other auth behavior changes. Asset-owned scope/count/schema/timestamp/export-id details are generated server-side. One SITE_EXPORT_PREPARED SUCCESS event after complete XLSX creation means generated for download; it never proves browser-local save. File is not returned if audit commit fails. No failure claim or partial file is returned after unknown COMMIT.
7. GET /api/assets/sites/export (sync def in FastAPI threadpool) calls the public method, with no dashboard filter/pagination arguments. Response is XLSX StreamingResponse, Content-Disposition attachment with fixed ASCII-safe timestamp filename, Cache-Control:no-store and X-Content-Type-Options:nosniff. Chunk reader closes in finally and background cleanup also closes idempotently (including disconnect/pre-consumption paths). Static route wins over UUID detail route. Authentication uses current request actor dependency; no import permission or role grant added.
8. Shared SiteExportButton issues credentialed GET to the fixed endpoint (no current query string), disables while busy, shows scope explanation and accessible status/alert. Success creates a blob URL and temporary download anchor; message says file was generated/download offered, not saved locally. Delayed revoke with unmount cleanup avoids leaked blob URLs. Abort on unmount/60s timeout; distinguish401/403/503/network/timeouts. No secrets, response internals or raw SQL displayed. Add only at site list and import toolbar.

## Files / ownership

S1: backend/dga/assets/public.py; new backend/dga/assets/site_export.py; backend/dga/shared/auth/public.py (optional generic audit metadata only); new backend/migrations/versions/0025_site_export_audit.py; new backend/tests/test_site_export.py; existing auth regression if strictly necessary.
S2: backend/dga/assets/http.py; backend/tests/test_site_export.py for HTTP/error/file lifecycle behavior.
S3: new frontend/src/features/assets/SiteExportButton.tsx; DashboardPage.tsx; AssetImportPage.tsx; minimal asset CSS only if necessary; new frontend/tests/site-export.spec.ts; README.md export usage; no modification of unrelated pages or roles.
Artifacts: only docs/work-units/issue-48-* and timestamped docs/reviews/* for this unit. Test runtime/cache stays ignored. Do not copy unrelated dirty domain docs or source trees from the original checkout.

## State and failure ownership

No new business state machine. Per request: authorized -> query consistent site snapshot -> render complete workbook -> commit export audit -> provide file -> close; render/query/audit failure -> close ->503, no attachment. HTTP transmission/browser-local save is a separate transport outcome, not a business success guarantee. Each requested snapshot is a new read/export operation; double-click guarded in UI, retries do not create business entities. No idempotency infrastructure needed for read-only site data plus additive export audit.

## Implementation slices (one at a time)

### S1: public site export and minimal audit

Objective: actual XLSX through AssetDirectory with stable identity, coherent capacities, all sites and safe text, plus scope/count audit. Prerequisite: accepted plan. Allowed changes exactly S1 files above. Use TDD cycles: basic multi-line/null/zero-device workbook; permission/empty/>500/text/precision; snapshot concurrency and audit/failure. Each cycle red at public seam before minimal green. Test fixture may arrange DB data directly, but assertions observe export, existing public queries and IdentityService.audit_events. Do not add HTTP/UI or subsequent tickets. Success: application tests and affected auth/architecture pass; code review artifact, classified risks and accepted slice commit.

### S2: authenticated HTTP download

Objective: public route returns generated file with safe headers, route precedence,403/401/503 and reliable close. Prerequisite:S1 accepted. Allowed files S2 only plus focused S1 fixes if review requires. Red HTTP contract first; implement transport delegation; add failure/cleanup tests at system boundary, no private-builder assertions. Do not add async jobs or generic download APIs. Success: app+HTTP tests, legacy asset routes/auth pass; code review artifact and accepted slice commit.

### S3: two UI entry points / browser / docs

Objective: visible button on both surfaces, full-scope explanation, busy/error feedback and a real downloaded workbook. Prerequisite:S2 accepted. Allowed files S3 only plus focused fixes. First run failing browser behavior with missing button, then implement button and hosts, verify real API download under filtered ESS table still exports all; endpoint failures may be injected at browser network boundary. Test read-only field engineer works on site list, admin sees import entry. Build TypeScript and run affected browser regressions. README describes read permission, all-site scope, existing UUID, empty source note and offered-not-saved audit. Success: browser/build/application checks and code review artifact, accepted slice commit.

## Validation commands and isolation

- Preferred backend: docker compose -p dga-issue48-test -f compose.yaml --profile test run --build --rm api-test pytest -q tests/test_site_export.py tests/test_asset_dashboard.py tests/test_auth.py tests/test_architecture.py ; no commands operate the existing application project/volumes.
- Docker daemon unavailable during preflight. Non-destructive fallback: official PostgreSQL17 binary ZIP in ignored .cache/issue-48-postgres, own cluster/data,127.0.0.1 port18448, user/database dga_test, no system installation/service. Existing root .venv Python3.12 dependencies are reusable read-only. Set TEST_DATABASE_URL with host test-db (existing fixture guard retained), PGHOSTADDR=127.0.0.1 and chosen port; verify effective database before migrations. This is real PostgreSQL, not SQLite/mocked DB. Original fixtures/guard not weakened.
- Fallback backend from backend/: existing Python -m pytest -q tests/test_site_export.py; then affected tests and full pytest -q after slices justify integration. Migrations always on this isolated cluster. Use standard test fixtures; runtime scripts remain ignored or documented in artifact only.
- Browser: install locked frontend dependencies in this worktree; npm run build. Create a separate dga_browser role/database in the isolated cluster, URL host=db,port18448,user=dga_browser,database=dga_browser and PGHOSTADDR=127.0.0.1, preserving seed_browser guard. Run its migrations/seed only there, never dga_test. Use own API process on that browser DB and Vite port18148 with local ignored proxy config targeting own API18449, BASE_URL=http://127.0.0.1:18148, tests/site-export.spec.ts plus asset-dashboard.spec.ts. Do not execute seed_import_browser with its hard-coded5432 guard or weaken it; existing asset import regression uses backend application tests. Prefer existing Playwright browser; if missing use installed Chrome or obtain matching free test browser. No production/acceptance seed changes.
- Asset XLSX assertions: literal known columns/rows and string data types, exact high precision decimals, duplicate-name distinct IDs,601+ sites, null capacity, source_note empty, no grid_year, metadata/count; no tautological recalculation from implementation constants.
- Isolation failure or unavailable runtime is a real validation blocker; do not claim pass, change service credentials or reset data to evade it. Continue independent implementation/review only where a valid red-green loop exists.

## Documentation / review / commits

Goal passes by user's explicit confirmation. Next planreview must attack scope, audit compatibility, file lifecycle, Excel limits, permission model, inconsistent snapshots and test isolation. Address accepted findings and re-review before protected local plan commit. Slices require deepreview artifacts and local accepted commits, then aggregate deepreview/fix/re-review and accepted deepreview commit. Generate review filenames with actual host clock timestamp. No subagents required for this bounded scope; do not delegate without an applicable explicit need.

Each artifact records scope/files, validation evidence, finding dispositions/status, docs and classified residual risks. Final local report states changes, tests, reviews, remaining risks, local hashes and exact next gate. Stop at ready-to-open-draft-PR because user prohibits push; do not fabricate PR review, draft-PR-pass or final-closeout pass.

## Risks / destinations / no overdesign

- source_note is blank on current main: assigned to later work units#49/#50 and#61 integration; no speculative schema.
- Existing assets.read is globally readable: same policy preserved; future row-level permissions must remain in asset owner, not inferred from filters.
- Excel row maximum and browser-memory limits: current issue tests>500 and bounded server writing; extreme millions-of-sites pagination/export redesign assigned to future separately authorized work, not guessed here; never silently truncate.
- Audit JSON metadata and failure atomicity: fixed in current slice S1; regression through existing audit public query, no new audit UI or export platform.
- Windows Docker unavailable: tracked by this work unit; isolated real PostgreSQL fallback is necessary validation infrastructure, no appdata mutation.
- Temporary file cleanup and transport failure: fixed in S1/S2. Client saved-to-disk cannot be proven; explicit product wording and audit semantics avoid false claims.
- No blocking open questions. No Redis, object-storage changes, AI agents, extra role management, background export framework or main workspace cleanup.

