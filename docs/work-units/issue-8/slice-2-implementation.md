# Slice 2 implementation — report worker, PDF, storage and download

## Gate and scope

- Work unit: Issue #8
- Slice: 2
- Objective: turn queued snapshots into concurrency-safe current PDFs, expose failure/retry, and securely preview/download verified bytes.

## Changed files

- Extended `LaboratoryReports` with leased claims, stale-token protection, completion/failure/retry, shared-lock file reads, checksum/size verification, and audit.
- Added the snapshot-only Chinese ReportLab renderer and database polling worker.
- Extended `FileStore`/S3 adapter with signed byte reads.
- Added inline/attachment API routes and runtime object-store injection.
- Added production Compose worker, ReportLab hash-pinned dependency, README contracts, and focused PostgreSQL/worker/PDF/S3/HTTP tests.

## TDD evidence

- Red: focused collection failed because worker, renderer and stale-claim contract did not exist.
- Green before review: 50 focused lifecycle/workbench/architecture tests passed.
- Review finding CR-201 exposed long-text clipping; width-based wrapping test/fix was added.
- Green after fix: 18 focused report/PDF/storage tests and 74 complete backend tests passed.

## PDF QA

- The PDF skill operation marker was recorded once before the first PDF authoring command.
- Normal report: A4, one page, 10,548 bytes; required Chinese text extracted successfully; PNG inspection found readable headings, fields and values.
- Long mixed Chinese/ASCII report after fix: PNG inspection found wrapped values within the right boundary and no bottom clipping.
- Temporary PDFs, text and page images were removed after inspection.

## Review

- Initial deep review: `docs/reviews/code-review-20260911-002632.md`, one accepted medium finding.
- Fix record: `docs/work-units/issue-8/slice-2-fix.md`.
- Re-review: `docs/reviews/code-review-20260911-002958.md`, finding fixed, pass.

## Residual risks

- Browser page/true Compose flow is covered by Slice 3.
- Object orphan cleanup after a database outage is assigned to Issue #20.
- Formal branding/ASTM/threshold details remain outside scope.

## Completion status

Complete pending accepted-slice commit.
