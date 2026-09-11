# Slice 1 implementation — finalization to current report status

## Gate and scope

- Work unit: Issue #8
- Slice: 1
- Objective: make open samples report-unavailable, atomically queue an immutable current report snapshot on finalization, expose current status through the laboratory seam, and invalidate it on withdrawal.

## Changed files

- Added migration `0007_laboratory_reports.py` with finalization token, current report row, state/file consistency checks, and worker queue index.
- Added `dga/laboratory/reports.py` with current status DTO/service, snapshot v1 serialization, queue upsert, and invalidation.
- Updated laboratory workbench/public/HTTP/runtime composition to require the report lifecycle and expose status through the public seam.
- Added real-PostgreSQL report lifecycle/HTTP tests and connected existing workbench tests to the real lifecycle.

## Decisions

- Pre-0007 finalized development rows with no finalization token are explicitly `UNAVAILABLE/refinalization_required`; the greenfield migration does not fabricate historical snapshots.
- Retry generation and object delivery remain Slice 2.
- A withdrawal stores an inaccessible internal `FAILED/finalization_withdrawn` row so workers cannot claim it and the next finalization can reuse the same row identity.

## TDD evidence

- Red: initial focused run failed import because the report interface did not exist.
- Intermediate red: transaction/status tests exposed missing token placement and persisted PostgreSQL numeric scale expectations.
- Green: `docker compose --profile test run --build --rm api-test pytest -q tests/test_laboratory_reports.py tests/test_laboratory_workbench.py tests/test_architecture.py` — 40 passed.

## Residual risks

- Worker leases, rendering, object storage, retry, file integrity, and download locking are covered by approved Slice 2.
- UI polling/preview/browser acceptance are covered by approved Slice 3.
- Formal report content remains outside Issue #8.

## Completion status

Complete pending code review/re-review and accepted-slice commit.
