# Issue #49 S2 implementation

Goal/plan confirmed; S1 accepted d5b5226. Extend transport for explicit2/SITES and Idempotency-Key, strict revisions and warning-ID publication, paged preview/history, private verified source download, result query. AssetDirectory owned provenance routes for site/customer; normal field reader sees metadata but not private source. Public v1 command/response compatibility on real0013 repaired without changing the original integration test.

Frontend preserves v1 entry and adds explicit v2 mode: template/file, status, paged issues/rows, candidate current facts vs proposed values, per-row edit/reason, per-warning confirmation, transaction publication, zero-device detail/capacity, original source and paged revisions. Unknown request result uses persisted intent key/digest and server operation lookup; file body not persisted in browser. Unsaved editor blocks publication. Metadata labels owner is feature presentation, source trace remains asset-owned.

Validation: local backend437 passed/40 storage-only skipped; added protected migration-downgrade test1passed; HTTP2passed; TS/Vite buildpass; 17 relevant browserpass plus final2corepass after presentation adjustment. Firstred evidence, failures and fixes recorded S2 code-review artifact. No original acceptance database or worktree mutation; only new18465test cluster/dga_browser and18165API18466.

Docs: glossary zero-device site/capacity/source semantics, PROJECT_PLAN current v1/v2 boundary and additive permission, bilingualREADME workflow/limits/recovery/access/upgrade. No new ADR or guessedscientific values.

Residual risks classified: real cloud/Okta #18 and existing storageCI; complex cancellation#60; complete feature/load#61; lab permission drift#53. No blocker. Completion S2pass; next aggregate deepreview after accepted slicecommit.
