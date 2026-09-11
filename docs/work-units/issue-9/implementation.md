# Issue #9 implementation result

## Subsequent user review — 2026-09-11

User requested removing the three static workspace-explanation cards and the redundant grid-year field. Removed the cards throughout the portal and removed grid year from site table columns, detail attributes and filter controls. Commissioning date and the two distinct site statuses remain. This supersedes the original Issue #9 frontend grid-year requirement. Existing database/API grid-year compatibility is retained; no stored data is deleted.

Status: implemented, locally tested and reviewed. Branch codex/issue-9-asset-dashboard, base dc45a26 (main). No GitHub publication or merge performed for this issue.

## Delivered

- /assets and /assets/sites: PV/ESS selector, matching site/customer counts, separately grouped machine counts and known nominal capacity sums, filterable/sortable/paginated site list, configurable columns.
- /assets/sites/:id: official site fields, separate grid and operation states, commissioning date, selected product line capacities, direct current equipment list with filters/sort/page/columns. Return link preserves source query and column choices.
- AssetDirectory.dashboard and AssetDirectory.site_detail are the public application seams. GET /api/assets/dashboard and GET /api/assets/sites/{site_id} require assets.read. Repeatable-read queries keep per-response aggregates and lists consistent. Database schema remains asset-owned.
- Migration 0009 adds nullable official site data, PV/ESS membership per site, optional asset dashboard classifications and capacity fields. Mixed sites have one membership per product line. Project capacities are not derived from machine counts. Nulls remain unknown; partial machine capacity sums are identified as known portions. Installation history and sample snapshots are untouched.
- Browser fixture supplies clearly isolated PV/ESS example data. The preview stack accepts its configured port for login, defaults unchanged.

## Validation evidence

TDD: first unknown-classification query failed because dashboard was absent, then passed. Filtered aggregate/pagination test failed on missing query parameters, then passed. Site detail test failed on missing method, then passed. Browser flow failed because dashboard region was absent, then passed after UI implementation.

Commands from this worktree:

```
docker compose -p dga-issue9-test --profile test run --build --rm api-test
# 51 passed; 2 existing dependency deprecation warnings
docker compose -p dga-browser-issue9 -f compose.browser.yaml --profile test run --build --rm browser-test
# DGA_BROWSER_PORT=18089; 14 passed, viewport 1920x1080
```

After review corrections, targeted dashboard backend tests: 12 passed; dashboard browser tests: 2 passed; production tsc/Vite build passed. Visual inspection identified and corrected narrow-window table wrapping using minimum cell widths and horizontal scroll. Local browser login at 18089 verified. Review details: docs/reviews/issue-9-code-review.md.

## Remaining scope and ownership

No production backfill invents product lines, machine classifications, capacities, or site statuses. Existing data without membership will not appear in product-line lists until an authorized asset data import/enrichment supplies it; later asset import/catalog work owns that path. The display classification is separate from existing asset identity/type; recursive model/typed details remain Issue #10. Material catalogue and controlled write workflows are not added here. No health/threshold calculations, services, maps, or changes to laboratory/analysis behavior.

Migration is based on main's current 0005 head. Issue #7/#8 are in a separate stack, not in this base. Whoever integrates that stack and this branch must reconcile the migration graph before deployment; do not run an unresolved multiple-head upgrade. No production services or database were modified.

Next step: publish this branch and a draft PR against main when authorized. GitHub Issue #9 remains open.
