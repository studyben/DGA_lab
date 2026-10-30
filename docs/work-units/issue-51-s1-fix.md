# Issue #51 S1 finite fix — malformed frozen asset identity

2026-10-29. Controller accepted finding1 from docs/reviews/code-review-20261029-200426.md (FAIL1). This artifact records implementation evidence, not independent re-review or slice acceptance.

Workspace: C:/Users/weila/.codex/worktrees/issue-51-finalization-facts/DGA Lab. Branch codex/issue-51-finalization-facts, HEAD remains115ba812b6c85142e387ea5a24101ab3341de251. No commit, push, PR, external action or S2 work.

## Finding and bounded repair

A raw schema1 report retained by0032 and copied by0033 can contain sample.asset_snapshot.formal_asset_id as a JSON integer, array or object. UUID(value) then raised AttributeError outside the facts owner's defined error mapping. The public current-fact view crashed even though its intact matching READY PDF remained readable.

FinalizationFacts.decode now explicitly requires a string whenever that optional historical nested ID is present and nonnull. A non-string raises ValueError inside the existing LaboratoryError(finalization_facts_unavailable,503) conversion. Strings still use the existing UUID value parser and physical-ID comparison; invalid strings and valid-but-mismatched UUIDs remain invalid. There is no broad AttributeError/Exception catch, coercion, invented UUID, live identity fallback or history rewrite. Absent/null evidence keeps its previous compatibility behavior.

Production edit is confined to backend/dga/laboratory/finalization_facts.py. One parameterized public regression was added to existing backend/tests/test_finalization_facts_migrations.py. It arranges a deep copy of attested old71_placeholder_ready in each isolated historical0032 schema, changes only that negative fixture's nested ID, actually migrates to0033/head, and checks the public Workbench view plus public Reports bytes. Positive cases.json/PDF/manifest and migration are unchanged.

Cases: integer123, empty array, empty object, boolean true, float1.5 and empty string. Every case requires UNAVAILABLE / invalid_finalization_facts, original token/schema1, unknown inventory and no active/adopted IDs, with exact original READY bytes and the captured PDF SHA256. This adds six cases without broadening into general malformed-payload exploration.

## Actual RED → GREEN

Pre-agreed seams remain LaboratoryWorkbench.get_current_finalization and LaboratoryReports.read_report_file, backed by real PostgreSQL and actual historical migrations. No private decoder unit test or private-table success assertion was added.

Owned existing PG127.0.0.1:18551 (PID45160) was verified listening. Tests use guarded test-db/dga_test/dga_test with PGHOSTADDR127.0.0.1 and fresh per-test historical schemas; no cluster restart, browser reseed, existing data reset or process change.

From R/backend, R denotes the explicit workspace above. Python is the existing read-only issue-48-dual-main-sync/DGA Lab/.cache/test-venv/Scripts/python.exe. Environment:

    TEST_DATABASE_URL=postgresql+psycopg://dga_test@test-db:18551/dga_test
    DATABASE_URL=same
    PGHOSTADDR=127.0.0.1
    PYTHONPATH=R/backend
    PYTHONUTF8=1
    PYTHONDONTWRITEBYTECODE=1

RED, before production edit:

    python -m pytest -q -rs -p no:cacheprovider tests/test_finalization_facts_migrations.py -k malformed_legacy_asset_id

Result5 failed,1 passed,22 deselected,2 warnings in5.07s, exit1. Five non-string inputs leaked AttributeError; empty string already followed the controlled ValueError path. Log .cache/issue51-tests/s1-fix-asset-type-red.log.

GREEN, after the minimal production guard:

    python -m pytest -q -rs -p no:cacheprovider tests/test_finalization_facts.py tests/test_finalization_facts_migrations.py tests/test_architecture.py

Result48 passed,2 warnings in25.53s, exit0. Log .cache/issue51-tests/s1-fix-asset-type-green.log. This includes all six new cases, existing valid UUID mismatch/corrupt snapshot cases, valid old producer/parent corpus, NULL-token coexistence through three analysis public queries, rollback/current authorization/race behavior and architecture checks. Warnings are inherited Starlette/anyio deprecations.

No redundant179-case/full617/backend/browser repeat. Those earlier results belong to the pre-fix S1 source; the latest48-case run covers this final bounded decoder change. Exact accepted-head whole-suite/configured40storage CI remains controller-owned.

## Final bounded hashes and scope

SHA256:
- finalization_facts.py 2F09E6277D2FC2C46D2B508F0C0820AA8BA49FF528576D03CDEC545CA05B492C
- test_finalization_facts_migrations.py 7F2949987224BBBBEC43A736B721CEAFA974E0E035D5437133156F6A30A43057
- unchanged0033_lab_finalization_facts.py 73097C4E51869B3B011E027E55A5B9FEA4CBBB717263510B06A89395619845D9
- unchanged captured cases.json raw bytes334C432B27D907F6CE9EAD2EF202DF08C0311BE31E0D82EC7A13912B9C1D4A00
- unchanged manifest.json raw bytes46DF938DBFA04EF7B74012CBA8FD7148DEAF213E2E403B5B0AE6814D2C23BB4A

The corpus loader still verifies portable LF text attestation and all captured PDF raw hashes. Capture-byte provenance is not confused with normalized/current-checkout text hashes. This fix changes only the facts decoder, existing migration test file, this fix artifact and a time-evidence note in issue-51-s1.md. It does not change authorization, queue semantics, NULL-token qualification, source fixtures, migration/schema, analysis, UI, providers, runtime configuration or controller documents.

git diff --check is clean. Workbench/Reports/public/migration and prior S1 behavior hashes remain as recorded in issue-51-s1.md; only the two hashes above supersede their pre-fix values there.

## Handoff and residual ownership

Finding1 implementation fix COMPLETE. No human question or new product decision is needed. Independent re-review and controller acceptance are still required; no PASS is self-declared. Configured storage40, exact-head dual-host CI and any evidence-triggered CI budget adjustment remain controller-owned. S2/result-reader/NO_REQUEST and existing deployment/#18/#53+/#60/#61 residual owners remain unchanged. Stop here; no next gate or commit.
