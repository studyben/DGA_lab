# PR #28 required-check fix

## Failure

GitHub Actions started the browser environment with `docker compose -f compose.browser.yaml up --build -d --wait frontend`. The new report worker was a sibling service rather than a transitive dependency of `frontend`, so the environment omitted it. The real report acceptance correctly failed after 30 seconds waiting for the queued report to become ready; the other 12 scenarios passed.

## Fix

The browser-only `frontend` service now declares `report-worker` with `condition: service_started`. Selecting the existing CI target therefore brings up the complete production-like report path: PostgreSQL migration/fixture, MinIO initialization, API, report worker and frontend.

This does not couple production frontend code to the worker and does not change runtime business behavior. It only makes the declared browser acceptance environment complete under its documented/CI entry point.

## TDD evidence

- Red: remote required check, 12 passed / 1 failed; report stayed non-ready for the full 30-second wait.
- Green: the exact CI startup target (`up --build -d --wait frontend`) brought up `report-worker`; all 13 browser scenarios then passed in 9.0 seconds.
