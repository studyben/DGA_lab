# Issue #8 goal confirmation

## Status

Confirmed by the user on 2026-09-10. Push and merge are authorized after all Gateflow gates pass.

## Goal and motivation

Turn the finalized data set owned by the laboratory module into one current Chinese PDF report per oil-sample barcode. Generation must be durable and asynchronous so a request is not held open while rendering or writing to object storage. A report is available only while the matching sample finalization remains current.

## Recommended behavior

- A successful `OPEN -> FINALIZED` transition atomically creates or replaces the current report request and a frozen JSON snapshot of sample basics, the received-time asset snapshot, selected results, finalization time and acknowledged warning codes.
- Persist one current report row per oil sample. Its active generation state is `QUEUED`, `GENERATING`, `READY` or `FAILED`; internal generation tokens prevent a withdrawn or superseded worker attempt from publishing stale content. Users never see a version number or version list.
- A small database-backed report worker claims queued rows, renders a concise Chinese placeholder-branded PDF, writes it through the existing S3-compatible file port, and commits the object key, byte size, SHA-256 checksum and generation time. A failed attempt records a stable failure code and can be explicitly requeued by a user with `laboratory.finalize`.
- Report lookup by barcode requires `laboratory.read`. An open/unfinalized sample returns an explicit unavailable state; queued, generating and failed states are visible; a ready report provides inline preview and download endpoints.
- Download always revalidates the current sample finalization and report-generation token, reads through the application rather than exposing a permanent object URL, verifies the stored checksum, and appends a download audit event.
- Withdrawal invalidates access immediately and changes the generation token in the same database transaction. Re-finalization refreshes the same current report row with a new snapshot and queues generation again. Stale worker completion cannot make an old PDF current.

## Success signals

- Public laboratory report interfaces against a real migrated PostgreSQL database prove automatic queueing, frozen selected-result content, state transitions, failure/retry, concurrent worker safety, withdrawal invalidation, re-finalization replacement and guarded download.
- A verifiable file-store and task implementation are used at test seams; production Compose includes the minimal worker and S3-compatible storage path.
- Browser acceptance proves unfinalized lookup, asynchronous finalized generation, inline preview/download availability and withdrawal invalidation.
- A representative generated PDF is text-inspected and rendered to PNG for visual checks of Chinese glyphs, clipping, spacing and page structure.

## Direct code evidence

- `LaboratoryWorkbench.finalize` already locks the sample row, resolves sole selections and commits the authoritative `FINALIZED` timestamp; `withdraw_finalization` owns the reverse transition.
- `oil_samples.asset_snapshot` contains the customer, site and equipment path captured at sampling time, while `laboratory_tests.selected_for_report` identifies the report data set.
- `FileStore` and `S3CompatibleFileStore` already own object writes/deletes but have no read operation yet.
- `/lab/reports` exists only as a placeholder; no report interface, table, renderer, worker or Compose worker service exists.

## Scope boundary and non-goals

- Keep report generation inside the laboratory deep module and expose it only through `dga.laboratory.public`; do not add dependencies from assets or condition analysis into laboratory internals.
- Extend the shared file port only with the read operation needed for guarded preview/download. Build a report-specific database worker, not a general workflow platform or message broker.
- Do not add formal PDF brand details, electronic signatures, external customer delivery, report numbers, user-visible versions/history, formal ASTM method identifiers, invented units, thresholds, QA/QC rules or changes to later tickets.
- The current GitHub relationship still shows Issue #8 blocked by open Issue #7, but the selected code base contains merged PR #27 and therefore has the required implementation; this is not a code blocker.

## Blocking open questions

None. The choices above resolve the current issue without guessing the explicitly deferred scientific and brand details.
