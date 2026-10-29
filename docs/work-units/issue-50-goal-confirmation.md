# Issue #50 goal confirmation

- Gate: goal confirmation evidence, already confirmed by the human through the #50–#52 controller. This artifact records that authorization; it does not request it again or advance a gate.
- Work unit: [#50 / BI-03](https://github.com/studyben/DGA_lab/issues/50), parent [#47](https://github.com/studyben/DGA_lab/issues/47).
- Reviewed checkout: `C:/Users/weila/.codex/worktrees/issue-50-material-import/DGA Lab`.
- Branch: `codex/issue-50-device-material-import`; clean before planning. HEAD/base: `d60dc7633b0294d5b8630e6b18284f0f788c995e` (merged PR #64 / completed #49).
- Authority: read-only `G:/Sungrow Develop/DGA Lab/docs/work-units/phaseflow-50-52-control.md`, frozen `G:/Sungrow Develop/DGA Lab/outputs/specs/bulk-data-import.md`, and full issue snapshots `G:/Sungrow Develop/DGA Lab/outputs/phaseflow-50-52/issue-{47,50}.json`.

## Goal, motivation and success

Finish the initial asset-import workflow: a v2 ASSETS workbook explicitly supplies or references customers, sites and materials, and supplies a recursive new-equipment tree. Devices reference site UUID/name only. Preview exposes actionable differences and source evidence; a currently authorized operator explicitly confirms conflicts/warnings before the entire approved batch becomes business data in one PostgreSQL transaction. Published IDs, the original file and reviewed provenance remain recoverable after retries or an uncertain response.

Success means existing/same-batch sites and materials both work; product-line/location/status/time/tree rules hold; repeated serials create distinct equipment only after explicit review; existing records and sample snapshots remain unchanged; failures create no partial business data; exact capacity (500 per business sheet, 2000 total) works; v1 and #49 SITES batches still work. The primary test seam is AssetImports plus AssetDirectory on isolated real PostgreSQL, with only essential visible browser flows.

## Direct code evidence and judgment

- `backend/dga/assets/imports.py:35,94,123,146`: only `(2,SITES)` is accepted; persisted v2 operations are all dispatched to SiteImports. The v1 equipment writer already accepts the caller connection (`:183`) and must keep its legacy behavior.
- `backend/dga/assets/site_imports.py:32,46,103,134,160`: current authorization, retained files, persistent operations, revisions and atomic customer/site creation already exist. Extend this asset-owned workflow, split its connection-bound writer, and dispatch by persisted mode.
- `backend/dga/assets/site_import_workbook.py:41` and `site_import_validation.py:21`: v2 safely parses bounded customer/site rows and returns explicit references/candidates. ASSETS needs additional allowed sheets and field rules, rather than interpreting the old reference sheets as commands.
- `backend/dga/assets/import_validation.py:43` and `lifecycle.py:42,76,176`: existing equipment type, status, time, recursive path and graph rules establish the behavior to preserve/reuse. A new import must not invoke separately committing lifecycle commands in a loop.
- `backend/dga/assets/public.py:147,245`: source queries cover SITE/CUSTOMER only; equipment detail has no import-source view. Material identity is the existing text material_number (`0013_asset_import.py`), while provenance target_id currently accepts UUID only (`0031_site_import.py`). An additive, typed source mapping is necessary.
- `frontend/src/features/assets/AssetImportPage.tsx:30` and `SiteImportPanel.tsx:25`: two current paths are legacy equipment and v2 SITES; v2 recovery/revision UI can be extended rather than recreated.

The work unit is justified: #49 solved independent site creation but cannot yet consume the equipment/material workflow approved in #47/#50. A small asset-owned extension is sufficient; no cross-module ImportService, new provider, message system, compatibility engine, or generic schema framework is needed.

## Scope and exclusions

Implement v2 ASSETS upload/template/validation/revision/publish/recovery and material/equipment provenance, reuse customer/site behavior, preserve legacy v1 and SITES. Use additive migration `0032_device_material_import` after `0031_site_import`.

Existing material/asset update or merge, site-customer reassignment, equipment-row site writes, installation under arbitrary existing parents, warehouse/transit positions, repair tickets, model compatibility guesses, laboratory/analysis changes, cancellation/reconciliation platform work, and #51/#52 implementation remain outside this unit. Follow-up recovery/cancellation complexity remains #60; combined-chain acceptance remains #61, without deferring #50's own atomicity, authorization or exact legal capacity.

Only this checkout's plan/goal files are written by this gate. Original G:, #49/#48 trees and retained environments 18148/18165/18164 are untouched. No source edit, migration/test execution, commit, push, PR, external comment or controller modification occurs during planning.

## Domain alignment and questions

Read current CONTEXT.md/PROJECT_PLAN.md and tracked ADR-0007; the checkout contains only ADR-0007. Also read the accepted original ADR-0001/0002/0004/0008/0009 as references. Frozen #47 and accepted #50 supersede PROJECT_PLAN's obsolete exclusion of v2 equipment/material import. Do not copy unrelated original domain files into the branch. The implementation updates only #50's relevant terminology and delivery notes; laboratory/finalization wording belongs to #51/#52.

No blocking scope question remains. Exact engineering choices, compatibility dispatch and tests are fixed in `docs/work-units/issue-50-plan.md` and are proposals for the separate plan-review gate. Completion status: goal evidence recorded; plan ready for review, not accepted or implemented.
