# Issue #49 CI diagnosis

Gate: PR review / fix / re-review. Scope: the two site-import production browser failures on PR #64 head 8c711cd. No CI checks or assertions were bypassed.

## Tight feedback loop and minimization

Command (BASE_URL=http://127.0.0.1:18165, BROWSER_CHANNEL=msedge):

    npm --prefix frontend run test:e2e -- site-import.spec.ts --timeout=30000

The two existing scenarios use real application APIs and an independent PostgreSQL database. Removing crypto.subtle and crypto.randomUUID through Playwright's browser-capability initialization reproduced the exact CI symptoms: no preview table, and no recovered batch. Before the fix both failed; after the fix both passed, latest rerun 2 passed (7.1s). The normal flow reaches upload, revise, publish and provenance. The response-loss flow commits the actual upload, aborts delivery, reloads and resolves its original durable operation without another upload.

## Ranked hypotheses and evidence

1. Secure-context APIs are unavailable on ordinary HTTP: predicts no POST reaches the API, and removing those APIs locally reproduces both failures. Confirmed.
2. Navigation clears selection after a successful upload: predicts a POST and persisted operation before missing preview. Excluded for this failure; no POST reached the server.
3. CI object-storage failure prevents staging: predicts a server POST/storage exception. Excluded; the failure was before fetch, and CI's real storage contracts passed.

The ranked hypotheses were communicated before the capability probe. The reduced environment change is only browser secure-context capabilities; business and storage behavior were not mocked.

## Root cause / fix

SiteImportPanel awaited crypto.subtle.digest, then crypto.randomUUID, before sending mutations. Both are unavailable at CI's http://frontend origin; TypeError was misleadingly rendered as an unknown transport result. Use exact-pinned @noble/hashes 2.4.0 for SHA-256, and UUIDv4 from crypto.getRandomValues (available at this origin). Missing secure randomness fails explicitly. Preserve digest encoding, filename suffix, persistent operation key, current server-side integrity checks and publication rules.

## Cleanup, validation and remaining owners

Production build and both original browser scenarios pass with the regression capability boundary retained. No temporary debug logs, weak random fallback, insecure browser flags, CI skips, storage-provider changes or new credentials were added. PR fix re-review records the direct trace and dependency review. New exact-head full CI remains mandatory before closeout; complex cancellation/leases #60, combined/load validation #61 and real Okta #18 remain separately owned.
