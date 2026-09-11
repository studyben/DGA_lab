# Issue #9 — PV/ESS dashboard and site details

Base: dc45a26 (origin/main); branch: codex/issue-9-asset-dashboard.
User authorized implementation and an isolated branch. The requested implement skill exists on disk and governs this work; use TDD and two-axis code-review.

## Scope and evidence

Issue #9 asks for line switching, filter-dependent site/customer/machine totals, configurable sortable paginated site and first-level equipment lists, and site details. Issue #4 is complete. AssetDirectory already owns official identity and effective installations; frontend asset routes are placeholders. Existing sites have only customer/name/location. Root workspace domain/design documents were consulted read-only (they are untracked and absent from this checkout).

Add asset-owned dashboard/site queries behind the public application boundary. Keep laboratory and condition-analysis interfaces unchanged. No editing, import, service records, maps, recursive equipment-detail pages, thresholds, or health calculations.

## Decisions and slices

1. Migration 0009 after current main's 0005: optional site grid year, separate grid commissioning/operation status and commissioning date; site_product_lines stores PV/ESS membership and official project MW/MWh (mixed sites supported; null means unknown). Optional asset product line, machine classification and nominal MW/MWh support grouped equipment totals. Do not backfill guessed classifications or capacities. Existing asset identity/type remains unchanged; machine classification is a display classification, not a replacement for asset_type.
2. Public AssetDirectory.dashboard and site_detail accept validated filters, sort and bounded pagination. Read one repeatable-read snapshot; dashboard aggregates all matching sites before pagination, distinct customers, and current installed non-retired/non-merged assets grouped by machine classification. Separate type totals are never added together. Recursive membership uses cycle guard and excludes inactive ancestor trees. Details list only current direct site children, filtered by line. Null quantities and incomplete sums stay explicit. SQL uses bound inputs and allowlisted sort columns.
3. React dashboard at /assets and /assets/sites; detail /assets/sites/:id. PV/ESS controls, filter form, metrics, sortable headings, pagination, column controls, clear/reset, loading/error/empty states. Navigation preserves list query and column selection. Site detail displays confirmed fields and first-level device list. No links to unimplemented recursive detail pages.

## Tests and completion

Pre-agreed seams: public asset application interfaces with real isolated PostgreSQL; key Playwright user flows. No internal schema assertions or component tests. RED/GREEN cycles cover line isolation, mixed/unknown capacities, filtered aggregates before paging, current/ended/future installations, permissions, invalid queries, details and list interactions. Run targeted tests per slice, frontend TypeScript build, full suites once after implementation; then code-review against dc45a26 and fix findings. Commit only this work. External publication/merge is not included in this Issue #9 authorization.

## Risks and ownership

Asset write/catalog/recursive editing belongs to later tickets (#10 onward). Existing unclassified data requires authorized master-data enrichment; do not silently assume PV. Main does not yet contain Issue #7/#8; a later merge may require a migration merge/rebase, owned by the integrator. Live dashboards reflect current installations, never historical sample snapshots. Date fields are calendar dates; installation comparisons use an aware UTC instant.
