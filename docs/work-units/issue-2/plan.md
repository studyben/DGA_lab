# Issue #2 implementation plan

## Goal and evidence

Deliver the five acceptance criteria in GitHub issue #2 under parent #1. The repository at base a1cc0ce has no production application, migrations or tests. The existing prototype is explicitly throwaway. Goal confirmed in conversation; see goal-confirmation.md for domain sources and ownership.

## Scope and design alignment

New `backend/`, `frontend/`, `compose.yaml`, `.gitignore`, `.dockerignore`, `README.md`, `.github/workflows/ci.yml`, and issue-specific artifacts only. Preserve pre-existing uncommitted docs and tools; never stage entire docs/.
One React/TypeScript application, FastAPI process and PostgreSQL. Top navigation has two workspaces. Assets, laboratory and condition_analysis remain separate backend packages and frontend feature directories. No business records, login, permissions, files, jobs, AWS provisioning, guessed thresholds or ASTM data.

## Contracts and implementation decisions

- Backend package `dga`, application composition in `dga/main.py`; `create_app(settings)` constructs runtime dependencies and owns cleanup. `dga/shared/config.py` validates PostgreSQL URL and America/Chicago timezone from environment. No production secret defaults.
- `GET /api/health`: 200 with `{status: "ok", database: "ok"}` only after successful SQL on real PostgreSQL; unavailable database returns 503 `{status: "unavailable", database: "unavailable"}` without credential/driver exception disclosure. Sync endpoint uses bounded PostgreSQL connection/statement timeouts, so sync I/O does not block the async event loop. Recovery requires no application restart. Connections close on all paths.
- SQLAlchemy + psycopg and Alembic migrations. Initial migration is an empty baseline with Alembic version tracking; no speculative domain tables. Application readiness includes migration revision compatibility, distinguishing reachable but unmigrated DB from ready state. The exact error response retains the same unavailable contract.
- Public in-process module entry files: `assets/public.py`, `laboratory/public.py`, `condition_analysis/public.py`. Initially expose immutable module descriptors for the portal registry; later business queries/commands extend the owning entry. No pretend CRUD contracts or NotImplemented endpoints.
- `GET /api/modules` composes the three public descriptors (stable code and Chinese label); no database or implementation objects in public exports. Frontend navigation is frontend-owned: backend descriptors describe domain modules, not React route/layout details.
- Dependency direction: condition_analysis may import assets.public and laboratory.public; laboratory may import assets.public; assets imports neither. Shared imports no business module. Composition root can wire public modules; no cross-module internal imports. An AST architecture check resolves relative/absolute imports and rejects bypasses; architecture policy verification is explicitly distinct from business tests.
- Frontend uses semantic navigation links and URL routes with browser history. Two top links, contextual side navigation and placeholder content clearly indicating a pending capability. No fabricated counts. Scheme A spacing, 1920x1080 desktop and max content width 1440px. Status analysis appears within asset navigation. Unknown routes show a recoverable not-found state; refreshing a valid deep link works.
- Frontend backend status fetch supports loading, success, unavailable/error and explicit retry, with cancellation on unmount. It does not present unavailable dependencies as healthy.
- Multi-stage images: frontend Node build to nginx static server and /api proxy; Python backend installs locked dependencies, runs as non-root. Compose database private on service network, only frontend localhost port 8080 published. Separate migration job must succeed before API becomes available. PostgreSQL named volume persists local application data.
- Integration-test profile has separate PostgreSQL service and ephemeral test storage, with distinct credentials and URL. Test startup runs the same migration files. Tests never migrate/reset a user-supplied application database: fixture accepts only the dedicated test service URL. No SQLite or mocked repository substitute.
- CI runs the same test and build commands with Docker Compose and publishes no deployment. No external issue changes or closeout comment until separately authorized, per Gateflow. Draft PR/push authorized through invoked workflow.

## Slices

### S1 — migrated API readiness

Allowed: backend config/app, dependency lock and Dockerfile, Alembic baseline, health integration tests, minimal compose database/API/migration/test wiring, local ignore files.
Prerequisite: accepted plan; Docker runtime for actual validation.
Red: test migrated real PostgreSQL yields health 200 before API implementation exists. Green: implement smallest runtime and baseline. Next red/green: unavailable database yields bounded 503 without secrets; reachable unmigrated DB unavailable; migrate and recover. Fixtures own test data lifecycle; production migration tested via Alembic invocation, no private-table business assertions.
Validation: `docker compose --profile test run --build --rm api-test` (initial health subset), Alembic upgrade repeated on isolated test database, teardown preserves application volume. Success: healthy/unhealthy/migration readiness contracts pass against PostgreSQL. Stop if engine or image acquisition cannot be made available.

### S2 — module-owned portal navigation

Allowed: backend business package public entries and module endpoint, architecture checker/test, frontend package/lock/config/source and browser smoke, frontend Docker/nginx; extend Compose for frontend/e2e.
Prerequisite: accepted S1.
Red/green: /api/modules registry test; architecture forbidden-import examples; browser top-level workspace switching and side navigation smoke before UI implementation. Public DTOs expose only module identity. API registry tests use real PostgreSQL-enabled app fixture. Frontend routes use same stable workspace state for header/side/main, handle back/forward and reload, no business state machine invented.
Validation: backend suite; `npm ci` and `npm run build` in frontend; `docker compose --profile test run --build --rm browser-test` tests rendered navigation, deep-link refresh, invalid path and status retry. Assertions on user-visible roles/text, not React hooks/classes.
Success: portal can be navigated by mouse/keyboard; forbidden import examples rejected, allowed public imports accepted; no accidental future capability implementation.

### S3 — repeatable developer delivery

Allowed: Compose refinements, CI, README, artifact updates, defects in S1/S2 revealed by delivery checks.
Prerequisite: accepted S2.
Validate one documented startup `docker compose up --build -d --wait`, clean isolated environment migrations, full test suite, type/build checks, application DB stop → health failure → restart → recovery; persistent local volume retained. Avoid destructive global Docker cleanup. Document ports, environment, architecture entry points, migration/test procedure, and development-only exposure until #3.
Success: all issue #2 criteria demonstrated with command outcomes recorded. This slice does not deploy Lightsail.

## Review, risks and completion

Every slice gets implementation and deepreview artifacts, accepted findings fixed/re-reviewed before protected local commit. Aggregate review then push/draft PR (Closes #2), actual PR metadata/diff review, accepted review commit/final push, closeout artifact. Never mark tests passed if unavailable. Closeout comment requires separate authorization; prepare exact text before asking at final gate.

Runtime availability/image downloads are current validation risks owned by this work unit. Authentication is tracked by #3; domain CRUD by #4 onward; cloud deployment/backups by #20. Existing documentation is local-only and not committed by this ticket; the PR must carry a self-contained architecture/startup guide and link the GitHub parent spec.

No overdesign: three public entry files, a single runtime, one migration baseline, two-workspace portal, one real integration test harness. No generic repositories, event bus, distributed transactions or business schema ahead of demand.

Final report: changed behavior, verified evidence, docs, finding dispositions, risks/owners, draft PR URL and issue-link status, current gate and next entry point. Execution order: #2→#3→#4→#5→#6→#7→#8, then #9–#19 in dependency order, #20 last.
