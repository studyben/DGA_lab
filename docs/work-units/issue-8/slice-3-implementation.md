# Slice 3 implementation — report center and browser acceptance

## Gate and scope

- Work unit: Issue #8
- Slice: 3
- Objective: expose current report states by barcode and prove the finalized-report lifecycle through the browser against real infrastructure.

## Changed files

- Added `ReportPage` at `/lab/reports` with normalized/URL-encoded barcode lookup, bounded polling, current-state messaging, permission-gated retry, inline PDF preview and attachment download.
- Wired the page into the existing laboratory workspace without adding another workspace switcher.
- Extended the isolated browser Compose stack with ephemeral MinIO, bucket initialization and the real database-polling report worker.
- Added a second isolated sample fixture and one public-HTTP browser flow that records DGA data, finalizes, waits for a real PDF, downloads it, withdraws, and re-finalizes.
- Updated developer documentation for the completed page, browser infrastructure and migration.

## TDD evidence

- Red: the new Playwright scenario timed out waiting for the absent `油样条码` control on `/lab/reports`.
- Green: the focused scenario passed in 3.1 seconds against real PostgreSQL, API, MinIO and report worker.
- Regression: all 13 browser scenarios passed from a freshly created isolated Compose environment.
- The frontend production image build ran TypeScript checking and Vite compilation successfully.

## Review

- Deep review: `docs/reviews/code-review-20260911-004200.md`.
- Result: pass with no material findings.

## Residual risks

- The current PDF is intentionally a simple Chinese placeholder; formal brand details remain outside Issue #8.
- External delivery, e-signature and report history/version UI remain outside scope.
- Production object lifecycle and recovery operations remain assigned to Issue #20.

## Completion status

Complete pending accepted-slice commit.
