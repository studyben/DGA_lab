# Issue #10 — 浏览递归设备树与类型化设备详情

Source: https://github.com/studyben/DGA_lab/issues/10
Base: ab54ef6 (main, Issue #9 merged). Branch: codex/issue-10-equipment-details.

## Scope and accepted seams

- AssetDirectory public queries + real PostgreSQL: current effective path, direct children, typed properties, unknown asset and denied access. Repeated child queries support arbitrary hierarchy within the existing 20-level safety bound.
- SampleRegistry public asset_test_history + real PostgreSQL: read-only summary owned by laboratory. No asset-to-laboratory table access or imports.
- Browser acceptance: ESS system → battery / PCS unit → PCS body / MVT, fixed layouts, history → barcode workbench.
- Existing user-approved tests remain the boundary; no React implementation or database-schema assertion tests.

## Implementation decisions

- Keep existing identity classification and machine_type distinct. machine_type is the stable layout key (INVERTER_UNIT, INVERTER, ESS_SYSTEM, PCS_UNIT, PCS, BATTERY_CABINET, TRANSFORMER). MVT uses TRANSFORMER, not a separate guessed identity category.
- Add nullable equipment_name, tag_number, commissioning_date, battery_manufacturer. Display tag, then equipment name, then system asset number for legacy missing names. Do not guess unknown metadata.
- Register fixed frontend field sets with one shared shell. Battery manufacturer and MWh appear only on relevant layouts; no rated voltage, battery/rack counts, equipment manufacturer or manufacturing date.
- Health is explicitly UNASSESSED, not a calculation or a claim of normal operation. Real condition-analysis rules remain out of scope.
- Current navigation uses effective installations; ambiguous or cyclic paths fail safely. Laboratory history uses immutable sample snapshot ancestry at sampling time, not current installation or serial equality. Removed tests do not count. Includes samples awaiting testing with count zero.
- assets.read permits only laboratory's small asset-history projection: barcode, sample time, sampled transformer serial/ID, test types/count and testing status. Raw results, files, workbench and mutation permissions remain unchanged. Full workbench links appear only with laboratory.read.
- Migration adds optional fields only; no asset editing, imports or data backfill. Existing production records remain intact.

## Excluded

Services/repair/upgrade/rectification work orders; asset editing; real health thresholds or alarm acknowledgement; ASTM guesses; formal PDF or report generation changes; merging pending #7/#8 branches; production deployment.

## Sequence

1. Device query red/green; optional fields migration red/green.
2. Laboratory summary red/green, permissions and historical ancestry checks.
3. Browser acceptance red/green, layout registry, child links and barcode handoff.
4. Build, full public-interface and browser suites; standards/spec review and fixes; local commit.
