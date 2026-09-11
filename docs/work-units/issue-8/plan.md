# Issue #8 implementation plan

## Outcome

Deliver one current Chinese PDF report for each finalized oil-sample barcode. Finalization queues report generation from an immutable snapshot; the report can then be found by barcode, previewed, and downloaded. Open samples cannot expose a report. Withdrawing finalization invalidates the current report, and re-finalization replaces it without exposing report versions.

## Confirmed boundaries

- Keep report behavior behind the laboratory module's public application interface.
- Reuse authentication, RBAC, audit, PostgreSQL, and S3-compatible storage already established by earlier work units.
- Do not introduce formal branding, signatures, external delivery, report-number/version-history concepts, formal ASTM method identifiers, formal thresholds, or guessed units.
- Do not build a generic job platform or message broker. A database-backed laboratory report worker is sufficient for this work unit.
- Do not implement later tickets.

## State model and invariants

### Sample/report relationship

- `laboratory_reports.oil_sample_id` is unique: the row represents the current report only.
- Migration 0007 adds nullable `oil_samples.testing_finalization_token UUID`. New finalizations set it; withdrawals clear it. Existing development rows that were finalized before 0007 retain `NULL`, and report lookup returns `UNAVAILABLE` with reason `refinalization_required`; withdrawing and finalizing again is the explicit recovery. This greenfield migration does not synthesize a report snapshot from mutable historical rows.
- A report is available only while its sample is `FINALIZED` and `laboratory_reports.finalization_token` equals the sample's non-null `testing_finalization_token`.
- The finalization, generation, and claim tokens are internal concurrency controls, never user-visible versions. Retry preserves the finalization token and immutable snapshot but replaces the generation token.
- The report snapshot is written in the same PostgreSQL transaction that changes the sample from `OPEN` to `FINALIZED`.
- The snapshot contains the barcode, sample basics, received-time asset snapshot, selected test results, acknowledged warning codes, finalization time, and requesting actor. The worker renders only this snapshot.
- Finalization creates or replaces the current row as `QUEUED`, clears prior file metadata/errors, and assigns a new generation token.
- Withdrawal changes the sample to `OPEN`, invalidates the report generation in the same transaction, clears accessible file metadata, and makes all report read/download operations return unavailable.
- Re-finalization reuses the same database row, writes a fresh snapshot/generation token, and queues a replacement.

### Database schema

Migration `0007_laboratory_reports` creates one laboratory-owned table:

- `id UUID PRIMARY KEY`
- `oil_sample_id UUID NOT NULL UNIQUE REFERENCES oil_samples(id) ON DELETE CASCADE`
- `finalization_token UUID NOT NULL`
- `generation_token UUID NOT NULL`
- `snapshot_schema_version SMALLINT NOT NULL DEFAULT 1 CHECK (= 1)`
- `report_snapshot JSONB NOT NULL`
- `state VARCHAR(16) NOT NULL CHECK (IN ('QUEUED','GENERATING','READY','FAILED'))`
- `claim_token UUID NULL`, `lease_expires_at TIMESTAMPTZ NULL`
- `object_key TEXT NULL`, `content_sha256 CHAR(64) NULL`, `byte_size BIGINT NULL CHECK (byte_size >= 0)`
- `error_code VARCHAR(80) NULL`
- `requested_by UUID NOT NULL REFERENCES users(id)`, `requested_at TIMESTAMPTZ NOT NULL`
- `started_at TIMESTAMPTZ NULL`, `generated_at TIMESTAMPTZ NULL`, `updated_at TIMESTAMPTZ NOT NULL`

Add an index on `(state, lease_expires_at, requested_at)`. A database check requires all three file metadata fields and `generated_at` in `READY`, and forbids them in other states. Application tests additionally enforce claim/lease/error field combinations because those transition-oriented invariants are clearer in the laboratory service than a large SQL check.

Snapshot schema v1 is a JSON object with these stable keys:

- `schema_version: 1`
- `sample`: `barcode`, `sampled_at`, `received_at`, `site_name`, `equipment_serial`, `notes`, `identity_status`, and the complete received-time `asset_snapshot`
- `selected_results`: ordered items containing `test_id`, `test_type`, `method` (`method_version_id`, `method_code`, `display_name`, configured field labels/units), `measured_at`, `instrument_name`, `notes`, and typed result fields with `qualifier` and decimal `value`
- `acknowledged_warning_codes`: sorted strings
- `finalization`: `token`, `finalized_at`, `finalized_by_user_id`, and `finalized_by_display_name`

UUIDs are strings, aware timestamps are UTC ISO-8601 strings, Decimal values are exact decimal strings, and absent values are JSON null. Raw attachments, credentials, session facts, and later-mutated user/profile data are excluded.

### Report states

- `QUEUED`: awaiting a worker claim.
- `GENERATING`: claimed by a worker with a claim token and lease expiry.
- `READY`: object upload and metadata commit completed for the current generation and claim.
- `FAILED`: current generation failed with a stable error code safe for display.
- Withdrawal does not need a user-facing report state; the sample state is authoritative and the stored row is inaccessible until re-finalized.

### Worker safety

- Workers claim `QUEUED` rows with `FOR UPDATE SKIP LOCKED` and may reclaim an expired `GENERATING` lease.
- Each claim gets a new claim token. The object key includes both generation and claim tokens, so stale workers cannot overwrite a newer object.
- Completion/failure updates compare the current generation and claim tokens. A stale result cannot become current.
- The worker uploads before committing `READY`. Failed/stale completions make a best-effort delete of the just-uploaded object.
- A database outage after upload may leave an unreachable orphan object. This is an operations/storage-lifecycle concern assigned to the deployment/operations work in Issue #20; it is never exposed by the application.
- A user-triggered retry is allowed only for a `FAILED` report whose sample remains `FINALIZED` with the same finalization token; it retains the snapshot, assigns a new generation token, and returns to `QUEUED`.

### Download safety

- Preview/download goes through the application and requires `laboratory.read`.
- The application begins a transaction, locks the sample then current report row in that order with a shared row lock, revalidates state/tokens, reads and checksums the object while holding those locks, writes the audit row, then commits and returns the already-read bytes as `application/pdf` with private/no-store and `nosniff` headers. Withdrawal uses the same sample-then-report lock order with exclusive locks, so after withdrawal commits no new download can obtain old bytes.
- Download filenames are generated from a sanitized barcode; object keys and arbitrary user text are never copied into response headers.

## Public application contract

Add `backend/dga/laboratory/reports.py` with a laboratory-owned `LaboratoryReports` application service. `backend/dga/laboratory/public.py` re-exports only operator-facing report DTOs/service methods; worker claim types remain private to the laboratory package. Call paths are HTTP router -> `LaboratoryReports` -> PostgreSQL/file port, and worker CLI -> private worker methods -> renderer/file port/PostgreSQL.

- `get_report_by_barcode(actor, barcode)` returns `UNAVAILABLE`, `QUEUED`, `GENERATING`, `READY`, or `FAILED` plus safe current metadata.
- `retry_report(actor, barcode)` requires `laboratory.finalize` and returns the newly queued current report.
- `read_report_file(actor, barcode)` requires `laboratory.read`, verifies availability and checksum, records the audit entry, and returns bytes plus safe filename/metadata.
- `claim_next_report(worker_id, lease_seconds)`, `complete_report(claim, stored_file)`, and `fail_report(claim, error_code)` are worker-facing methods kept inside the laboratory package, not exposed as HTTP endpoints.

`LaboratoryWorkbench` receives an explicit laboratory report lifecycle port. Production composition supplies the real service; tests that do not exercise reporting supply an explicit no-op implementation. There is no optional production fallback that can silently skip queuing.

## HTTP and UI contract

- `GET /api/laboratory/reports/by-barcode/{barcode}` returns the current safe state and metadata.
- `POST /api/laboratory/reports/by-barcode/{barcode}/retry` retries a failed current generation.
- `GET /api/laboratory/reports/by-barcode/{barcode}/file?disposition=inline|attachment` returns the current PDF only when ready.
- Stable errors are `sample_not_found` (404), `report_unavailable` (409 with safe reason), `report_not_ready` (409), `report_failed` (409 with safe error code), `report_retry_not_allowed` (409), and `report_integrity_failure` (503). Storage exception text/object keys are never returned.
- `/lab/reports` provides barcode input/search, unavailable/queued/generating/failed/ready states, polling while work is pending, inline PDF preview when ready, download, and retry when failed.
- The page follows the existing unified portal and laboratory navigation; no additional top-level switcher is added.

## PDF contract

The MVP renderer creates a concise Chinese PDF containing:

- a restrained SUNGROW/阳光电源 placeholder header;
- barcode and sample basics;
- received-time site/customer/equipment snapshot;
- selected DGA, moisture, and breakdown-voltage results present in the snapshot;
- qualifiers and the already configured `unit_code` where available, with no invented method numbers, limits, conclusions, or thresholds;
- finalization time and actual generation time.

The renderer uses an available CJK-capable font and deterministic layout. A real generated PDF is checked for extractable required text and rendered to PNG for visual inspection following the PDF skill workflow.

## Implementation slices

### Slice 1 — Finalization to current report status

Deliver an open-barcode unavailable response, transactional finalization queueing, immutable snapshot, current status lookup, and withdrawal invalidation.

Allowed modules/files: `backend/migrations/versions/0007_laboratory_reports.py`; `backend/dga/laboratory/{workbench,reports,public,http,errors}.py`; `backend/dga/main.py`; and directly corresponding backend tests. Shared files, PDF dependencies, worker/Compose, and frontend files are not allowed in this slice.

Exact call/data flow: `LaboratoryWorkbench.finalize()` locks the sample, validates/selects results, creates a UUID finalization token, updates the sample, calls an explicit `ReportLifecycle.queue_current(connection, ...)` before transaction commit, and records existing events/audit. `queue_current` queries the just-selected records through laboratory-owned SQL, serializes snapshot v1, and upserts the unique current row. `withdraw_finalization()` locks sample then calls `ReportLifecycle.invalidate_current(connection, ...)` before commit. `GET` calls `LaboratoryReports.get_report_by_barcode` and never reads report tables in HTTP.

Tests first:

- Real PostgreSQL: open unavailable; finalize creates/replaces one queued snapshot; failed finalization queues nothing; withdrawal invalidates; re-finalization refreshes the same current row.
- HTTP: lookup states and permission enforcement.
- Architecture: no direct laboratory-internal imports from other domain modules.

Validation command: `docker compose --profile test run --build --rm api-test pytest -q tests/test_laboratory_reports.py tests/test_laboratory_workbench.py tests/test_architecture.py`. Expected: new state/transaction/migration assertions and all existing finalization/architecture assertions pass.

Stop condition: status lookup, queueing, snapshot, migration compatibility, and invalidation tests pass; no file generation/download/UI work is present.

### Slice 2 — Worker, PDF, object storage, retry, and file access

Deliver queued-to-ready generation, failure/retry, guarded preview/download, and concurrency-safe worker behavior.

Allowed modules/files: `backend/dga/laboratory/{reports,report_pdf,report_worker,http,public,errors}.py`; `backend/dga/shared/files.py`; `backend/dga/main.py`; backend dependency manifests/Dockerfile only if needed for the renderer; `compose.yaml`; README runtime/API additions; and directly corresponding backend tests. Frontend/browser files are not allowed.

Exact call/data flow: worker CLI builds the same `LaboratoryReports`, polls `claim_next_report`, renders bytes from the claim snapshot, writes the claim-specific object key, and calls token-checked complete/fail. HTTP lookup/retry/file routes call public operator methods only. `FileStore.get(object_key) -> bytes` is added to the shared port, unavailable adapter, S3 adapter, and test doubles. Renderer input is snapshot v1 plus worker claim time; it never queries the database.

Tests first:

- Real PostgreSQL: claim, expired-lease reclaim, completion, failure, retry, stale completion rejection, and withdrawal during generation.
- Verifiable file store: upload/read/delete/checksum.
- Renderer: real PDF with required text and no invented fields.
- HTTP: preview/download headers, permissions, checksum mismatch, audit.
- Worker: stable failed state and safe retry to ready.

Validation commands:

- `docker compose --profile test run --build --rm api-test pytest -q tests/test_laboratory_reports.py tests/test_report_worker.py tests/test_report_pdf.py tests/test_files.py`
- `docker compose config --quiet`

Expected: concurrency/retry/download/PDF assertions pass and production Compose contains a healthy-configured report-worker dependent on migration/database and object-store availability.

Stop condition: public API can move a finalized report from queued through ready/failed/retry and securely return verified PDF bytes; no report-page UI is present.

### Slice 3 — Barcode report page and browser acceptance

Deliver `/lab/reports` barcode search, pending polling, failure/retry, inline preview/download, and no version UI.

Allowed modules/files: `frontend/src/features/laboratory/**`, `frontend/src/main.tsx`, directly related shared frontend API/types/styles when reuse is necessary, `frontend/tests/**`, `compose.browser.yaml`, browser seed support, and README UI/testing additions. Backend production behavior may only receive test-fixture corrections discovered by the true end-to-end flow; any broader backend change reopens Slice 2 review.

Exact call/data flow: the report page URL-encodes a trimmed barcode and calls the report GET endpoint; it polls only queued/generating responses with bounded backoff and stops on navigation/unmount; ready embeds the inline file URL and offers the attachment URL; failed offers retry only when the session capability includes `laboratory.finalize`. Browser seeding creates user/assets/sample/test inputs but never inserts a report row or object; the browser uses the real finalization endpoint and report worker.

Browser acceptance with real API and PostgreSQL:

1. Open barcode shows unavailable.
2. Finalized prepared sample advances through asynchronous generation to preview/download.
3. Withdrawal removes access.
4. Re-finalization regenerates the current report without exposing history.

Validation commands:

- `docker compose -f compose.browser.yaml up --build -d --wait frontend`
- `docker compose -f compose.browser.yaml --profile test run --build --no-deps --rm browser-test`
- `docker compose -f compose.browser.yaml --profile test down`
- `npm --prefix frontend run build`

Expected: new flows and existing portal/asset/reception/workbench flows pass; built UI has no report version/history affordance.

Stop condition: all four real-stack browser scenarios pass at the configured desktop viewport and existing UI regressions are green.

## Verification matrix

- Backend unit/architecture suite and real-PostgreSQL integration suite.
- Migration upgrade/downgrade checks.
- Frontend typecheck/build and behavior tests.
- Critical Playwright flows plus existing portal/laboratory regression flows.
- Production/browser Compose configuration validation.
- PDF text inspection and rendered-page PNG visual inspection.
- RBAC, audit, stale-worker rejection, checksum verification, safe headers, and absence of version UI/API.

Final aggregate commands are the unfiltered backend Compose test command, production Compose config validation, frontend build, and the complete browser commands above. Any skipped command must be classified as a blocking validation failure or a named residual risk before review can pass.

## Why this is not overdesigned

The design adds one current-row table, one laboratory service, one renderer, and one polling worker because durability, process-failure recovery, S3 storage, and asynchronous status are explicit acceptance requirements. Tokens and a lease solve concrete withdrawal/retry/crash races. It deliberately omits a generic queue, event bus, history table, report template framework, signed public URLs, formal rules engine, and cross-module read model.

## Gate and commit sequence

1. Adversarially review, fix, re-review, accept, and commit this plan.
2. Implement each slice test-first; deep-review, fix, re-review, and commit it before the next slice.
3. Run aggregate verification and aggregate deep review; fix and re-run.
4. Push `codex/issue-8-barcode-report`, create a draft PR based on `codex/issue-6-test-entry`, complete PR review/fixes, mark ready, and merge after every gate passes.

## Residual risks owned elsewhere

- Formal PDF brand/signature/customer delivery requires later product confirmation.
- Formal ASTM identifiers, precision/detection limits, thresholds, and conclusions remain unconfigured; the PDF reflects only stored method metadata.
- Unreachable S3 orphan cleanup after a database outage belongs to deployment/operations hardening in Issue #20.
