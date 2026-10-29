# Issue #50 / BI-03 — material and equipment import plan

## Gate, authority and outcome

Status: PLAN ready for separate plan review, not accepted or implemented. Goal already human-confirmed through the batch controller; see `docs/work-units/issue-50-goal-confirmation.md`. This dispatch writes only these two planning artifacts and stops. No source/runtime edit, migration/test execution, commit, push, PR, external comment or gate advancement.

Reviewed checkout: `C:/Users/weila/.codex/worktrees/issue-50-material-import/DGA Lab`; branch `codex/issue-50-device-material-import`; clean base `d60dc7633b0294d5b8630e6b18284f0f788c995e` (merged PR64 / completed#49). Every later command must use this explicit directory. The C: checkout needs approved escalation for writes. Original G:, #49/#48 worktrees and retained environments18148/18165/18164 are outside this unit's ownership.

Read-only authority: `G:/Sungrow Develop/DGA Lab/outputs/specs/bulk-data-import.md` D2–D4/D8–D9/D11–D14, T2-1/2/3/5/14/16/20/21/22 and asset T3; complete `outputs/phaseflow-50-52/issue-{47,50}.json`; controller `docs/work-units/phaseflow-50-52-control.md` (never edit); checkout CONTEXT.md/PROJECT_PLAN.md/tracked ADR0007; original accepted ADR0001/0002/0004/0008/0009. Only ADR0007 exists in this clean checkout; do not copy unrelated original dirty documents.

The outcome is one marked v2 ASSETS workbook explicitly supplying/referencing customers, sites and materials and supplying a recursive NEW-equipment tree. Equipment references site UUID/name only. After explicit preview review, current-authorized whole-batch publication commits masters/equipment/relationships/sources/audit/operation result once. Retries recover the same targets and originals. Success includes existing/same-batch references, actionable conflicts, distinct physical equipment despite repeated serials, public tree/provenance queries, exact500-per-sheet/2000-total capacity and unchanged v1/SITES/history.

Exclude existing asset/material update/merge, site-customer reassignment, equipment-row site attribute writes, arbitrary existing-parent installation, warehouse/transit/service tickets, guessed compatibility, laboratory/analysis changes and#51/#52 code. Complex cancellation/leases/orphan reconciliation remain#60; combined-chain acceptance remains#61, without deferring this unit's own atomicity/current authorization/capacity.

## Direct code evidence and design judgment

| Reviewed source | Actual implementation and decision |
| --- | --- |
| `backend/dga/assets/imports.py:35,79,94,123,146` | Only `(2,SITES)` admitted; persisted v2 dispatch ignores mode. Add mode dispatch; retain v1 branch. |
| `site_imports.py:29,32,46,103,134,160,201,210` | Current-auth/intent/revision/original/revalidation/customer-site transactions exist. Extend this asset-owned coordinator and extract its connection-bound row writer before composing equipment. |
| `site_import_workbook.py:8,41`; `site_import_validation.py:15,21` | Bounded marked v2 parser and master-data decisions/candidates exist. Preserve SITES schema/meaning, add mode-specific fields. |
| `import_validation.py:10,43`; `lifecycle.py:42,56,76,176` | Existing machine/status/time/recursive path/graph rules apply; legacy roots require customer_id. Reuse rules without separately committing lifecycle commands. |
| `backend/migrations/versions/0013_asset_import.py`; `0031_site_import.py` | material_number is existing text identity; source target_id is UUID-only. Add a typed material source target, not another material ID. |
| `public.py:147,245`; `http.py:111` | Only SITE/CUSTOMER source queries/routes exist; equipment details lack provenance. Extend AssetDirectory. |
| `backend/dga/shared/auth/public.py:244` | authorize_current holds shared identity30003/account protection through commit. Acquire before asset110011. |
| `frontend/src/features/assets/AssetImportPage.tsx:30,68`; `SiteImportPanel.tsx:25,50,76`; `ImportSourcesPanel.tsx:6` | Every v2 link assumes SITES. Reuse retained UI with actual mode/version routing. |
| `backend/tests/conftest.py:11,24`; `test_site_import.py:166,187,254,320` | Real isolated PostgreSQL, historical-schema fixtures, FileStore and lost-COMMIT precedents exist; public behavior is the seam. |

Assets owns this missing behavior. Keep AssetImports as the public interface and the existing FileStore/worker/provider configuration. Rename private v2 coordinator/parser to match expanded ownership; keep site validation specialized; add one equipment/material validator and one transaction-bound writer. No shared ImportService, generic schema registry, repository hierarchy, new queue/provider or compatibility framework is justified.

## 1. Workbook and version contract

### Dispatch

Supported pairs exactly `(1,ASSETS)`, `(2,SITES)`, `(2,ASSETS)`. Non-integer versions including bool, unknown versions/modes or `(1,SITES)` ->422 invalid_import_format. Unsupported persisted pair ->503 unsupported_import_format, never fallback. Persisted metadata, not caller mode, determines get/revise/publish/worker semantics.

Omitted upload version/unmarked legacy workbook remains v1 ASSETS: old2MiB/32-column/500-row rules, result shape, boolean warning acknowledgment, reference-only Sites/Materials. Format cannot cause legacy references to become writes. Default NEW template becomes v2 ASSETS in AssetImports.template and HTTP; explicit `format_version=1&mode=ASSETS` remains available and all legacy call sites/tests select it. Existing explicit v2 SITES requests/batches remain compatible.

v2 Format consists exactly of `version,mode` then numeric2 and exact SITES/ASSETS, no other nonempty cells/rows; request and marker must match. Templates contain blank business sheets plus Instructions, not automatically populated NEW commands. SITES requires at least one Sites row, optional Customers; Materials/Assets absent or without business rows retain#49 behavior. ASSETS accepts optional four sheets but must contain an Assets or Sites business row; customer-only/material-only/header-only/instructions-only invalid. ASSETS with valid Sites and zero equipment is valid.

### Fixed ordered generated headers

| Sheet | Headers |
| --- | --- |
| Customers | `record_key,decision,customer_id,customer_name,source_note,reason` |
| Sites | `record_key,decision,site_id,site_name,customer_ref,location_text,product_lines,pv_power_mw,ess_power_mw,ess_energy_mwh,commissioning_date,grid_status,operation_status,source_note,reason` |
| Materials | `record_key,decision,material_number,model,asset_type,source_note,reason` |
| Assets | `record_key,decision,serial_number,material_ref,product_line,machine_type,status,location_kind,effective_at,parent_record_key,site_id,site_name,power_mw,energy_mwh,equipment_name,tag_number,commissioning_date,battery_manufacturer,source_note,reason` |

Reordered headers and omitted optional headers are allowed; reject duplicate/unknown/empty nontrailing headers and populated unheaded cells. Customers/Sites keep#49 header acceptance (record_key header, business-required values validated). Materials required headers: record_key/decision/material_number/model/asset_type/reason. Assets required headers: record_key/decision/serial_number/material_ref/product_line/machine_type/status/location_kind/effective_at/reason; conditional SITE values still required. Missing values are actionable cell issues.

Assets rejects customer_id/customer_ref/location_text/product_lines/site capacities/site statuses/commissioning_year/update/asset_id/parent_asset_id/model/material_number write fields. Its site-related columns are only site_id/site_name. power_mw/energy_mwh/commissioning_date on Assets are equipment properties. Notes never supply inferred attributes.

### Scalars and decisions

- IDs are text, trimmed for resolution while original cells remain immutable; UUIDs complete/canonical. record_key1–120, sheet-local unique and case-sensitive. Numeric serial/reference cells reject rather than guess leading zeros. material number/model1–120; serial1–160; names1–200; equipment_name<=200; tag<=160; battery_manufacturer<=200; machine_type<=40. Reject wrong scalar types/nonfinite/control characters except CR/LF/TAB in ordinary text. source_note nullable, verbatim text<=2000; reason trimmed nonblank1–1000 on every NEW/REFERENCE row including equipment.
- Customers/Sites/Materials: NEW or REFERENCE only. NEW customer/site leaves formal ID blank. Materials NEW still supplies its proposed number. Assets: NEW only; no REFERENCE/UPDATE/MERGE/SKIP. A duplicate cannot silently change this decision.
- Materials asset_type only WHOLE_UNIT/TRANSFORMER. Reuse import_validation.KINDS: PV INVERTER_UNIT/INVERTER/TRANSFORMER; ESS ESS_SYSTEM/PCS_UNIT/PCS/BATTERY_CABINET/TRANSFORMER. TRANSFORMER machine iff TRANSFORMER material, others WHOLE_UNIT. No model/parent compatibility guess.
- Capacities nullable finite nonnegative Decimal `<10000000000`, <=6 fractional places, bool invalid; PV equipment energy_mwh empty. Unknown is null, not0. Sites retain current#49 product-line/capacity/status rules and nullable fields.
- commissioning_date ISO calendar date; native Excel midnight becomes that date; nonmidnight is not truncated. effective_at is ISO text with explicit offset, normalized UTC, <=current validation clock; no naive/date-only inference.

### Resource/file boundary

v2 exactly500 nonempty rows per sheet,2000 total. Instructions/Format do not consume rows. Enforce10MiB actual bytes/50MiB uncompressed/200 unique archive members/150000 cells and expanded sparse rectangle, plus each sheet's field whitelist, before unsafe materialization. Reuse#49 macro/formula/external/encryption/malformed/duplicate/traversing member and sparse-coordinate protections. HTTP/public/worker use same bounds;501 gives sheet/row, no truncation. Byte-size rejection413 precedes FileStore. Safely received malformed/row-overlimit workbooks are retained FAILED with visible issues and durable upload outcome. The file is never silently discarded to make a retry seem clean.

## 2. Resolution, conflicts and initial tree

### Typed references and dependency order

Preview returns discriminated JSON references, represented by TypedDicts beside the v2 validator:

- site `{kind:'EXISTING',site_id:UUID-text}` or `{kind:'BATCH',record_key:text}`;
- material `{kind:'EXISTING',material_number:text}` or `{kind:'BATCH',record_key:text}`.

Assets.site_id uses full existing UUID or `NEW:<Sites.record_key>`. material_ref uses `MATERIAL:<exact existing material_number>` or `NEW:<Materials.record_key>`; explicit MATERIAL prefix preserves existing numbers that themselves start NEW:. Strip outer cell whitespace only. Sites.customer_ref keeps UUID or NEW:<Customers.key>. A BATCH key resolves through that row's explicit NEW/REFERENCE decision, including an existing target when the row is REFERENCE. No fabricated identity. Reject missing/duplicated/wrong-sheet keys.

Build all sheet indices first, then customers -> sites, materials -> equipment scalars -> parent graph -> inherited context. File order is irrelevant. Store raw reference in reviewed_values and typed/resolved references separately. Published targets are real formal identities.

### Master conflicts

Retain#49 customer/site explicit decisions, same-name candidates, no site-customer reassignment, no overwrite of attributes/lines/capacities/notes. A same-name distinct entity requires NEW+reason+current warning confirmation. REFERENCE verifies actual customer ownership; ignored supplied attributes remain source evidence.

Materials REFERENCE must exist and exactly match submitted model/type; mismatch ERROR material_conflict, never a warning override. NEW for an existing number ERROR material_exists_choose_reference even if facts match. Missing reference ERROR material_not_found. One Materials row per material_number; duplicates ERROR duplicate_material_number regardless of decision; many Assets may reference it. Absent material requires an explicit NEW Materials row; model text cannot create it. Sources append for NEW/REFERENCE without overwriting catalog/provenance; number remains formal identity.

### Site attribution and explicit ID confirmation

SITE root: site_id plus nonblank site_name; no parent; INVERTER_UNIT or ESS_SYSTEM and corresponding WHOLE_UNIT material; product_line already configured on resolved site. Unknown UUID/NEW key blocks with “first or simultaneously supply Sites”. Name-only returns candidates plus ERROR site_reference_required, no inferred binding/creation.

ID/name mismatch WARNING site_name_difference binds exactID/key, supplied+actual names and target facts. Operator corrects the name in revision or explicitly acknowledges “use this site number despite source name” with row reason. It cannot override unknown site or wrong product line. Save acknowledgment in sources/audit. No extra site-attribute/confirmation workbook column.

PARENT: same-batch parent key, inherits root site/line. Optional site_id must resolve to same inherited target or ERROR inherited_site_conflict. Optional name mismatch is confirmable only when an explicit correct inherited ID was supplied; name-only mismatch requires correction or adding that ID. Child installation never stores site_id.

REPAIR_CENTER: parent/site_id/site_name empty; SPARE/UNDER_REPAIR/RETIRED; any current controlled machine/material type. SITE/PARENT status IN_SERVICE. PARENT chains must terminate at SITE, not a repair root, consistent with lifecycle parent_not_at_site. Unknown/warehouse/transit position blocks.

### Recursive relationships

Each NEW asset gets UUID, unique AST-UUID system number and one open `[effective_at,infinity)` interval. Root site, child parent UUID, or repair_center=true are mutually exclusive. No valid_to/history input. Block duplicate keys/missing/self/existing-ID parent/cycle/>100-node path, product-line mismatch, child-before-parent effective time, disabled/repair ancestor and status/location disagreement. Parent type/child quantity is not a compatibility rule. Final composed transaction runs existing validate_graph. Keep v1 behavior separate; stronger inherited-position validation is v2-only.

### Duplicate equipment and file semantics

Case-insensitive serial duplicates within batch/existing directory produce WARNING duplicate_serial per affected new row. Candidate context includes UUID/system asset number, material/model/type/line, current lifecycle revision/status and customer/site/path or explicit repair/unknown location. Same-batch candidates show key/row. Controls offer “view existing” or “confirm different physical equipment”, never binding/merging existing asset. NEW+reason+current warning acknowledgment creates a distinct UUID; correct unintended rows/files instead. Notes alone never establish/skip/create identity.

Byte-identical upload retains a new draft/original but exposes existing batches/results first: actual mode/version/state/publication time and links. Paginate duplicate history so20 recent drafts cannot hide older published results. GET preview adds duplicate_page(default1), duplicate_total; a global duplicate_file warning binds the full ordered duplicate fingerprint, not only returned page. UI defaults to prior results; “review as another group of physical devices” opens draft, without server business writes. Publish requires explicit duplicate_file plus all row duplicate_serial warnings, NEW decisions/reasons. Hash is repeat/integrity evidence, not physical identity. Serial+same attributes never auto-skips a confirmed distinct entity.

ASSETS issue IDs:24-hex hash of code+sheet/row/key+relevant supplied/resolved/candidate facts, excluding translated message. Require exactly current warning-ID set (no old/unknown IDs or legacy boolean bypass). Retain existing SITES acknowledgment semantics. Any revision/catalog refresh clears browser confirmations; reasons and acknowledged IDs remain durable.

## 3. Modules, migration and transaction state

### Module/function ownership

- Rename private `site_imports.py` -> `v2_imports.py`, SiteImports -> V2Imports; `site_import_workbook.py` -> `v2_import_workbook.py`. Update direct imports only. AssetImports stays exported by assets.public; SITES actions/inputs/results remain compatible.
- v2_import_workbook: COLUMNS/mode-specific required headers, `template(mode='SITES')`, `parse(content,*,mode)`, existing shared safety/bounds. No directory writing.
- site_import_validation.validate(c,source) remains customer/site owner; update parser import and add optional private catalog-snapshot argument to validate ASSETS in one snapshot. Keep SITES wrapper unchanged.
- Add asset_import_validation_v2.py: `validate(c,source,now)->(rows,issues,counts,catalog_digest)`. Invoke customer/site validation for its subset; resolve material/equipment as above. Reuse KINDS/TEXT_LIMITS and lifecycle location/graph semantics. Legacy validate remains unchanged; no v1-through-v2 normalization.
- Add import_persistence_v2.py: `create_batch(c,actor,batch,rows,*,now,acknowledged_warning_ids)` accepts caller connection. Allocate customer/site/equipment UUIDs, resolve local keys, insert new customers/sites/lines/materials, all equipment, installations and sources; return targeted rows. It never opens/commits a transaction, handles HTTP, marks batch state or operation complete. Extract existing SITES row writes here; no SiteBasics.update/AssetLifecycle.move loop.
- V2Imports owns current auth/intents/batch/revision/FileStore checks/audit/completion; AssetDirectory owns readable formal sources/details. No asset->lab/analysis dependency or shared domain policy.

### Additive0032 migration

File `backend/migrations/versions/0032_device_material_import.py`; revision0032_device_material_import, down_revision0031_site_import; one head. Do not edit older migrations.

Only extend asset_import_sources:

1. target_id UUID becomes nullable; add target_key VARCHAR(120) nullable FK asset_materials(material_number).
2. Replace existing kind check with named kind/target constraint: CUSTOMER/SITE/ASSET require nonnull target_id and null target_key; MATERIAL requires null target_id and nonnull target_key. No material UUID or business-ID/attribute rewrite.
3. Add confirmed_warning_ids JSONB NOT NULL DEFAULT[] with array-type check. Existing rows get empty list, not invented approvals.
4. Add(kind,target_key) index; preserve UUID target index and unique(batch_id,sheet,row_number). Existing batch/revision/operation tables suffice; no new task/intent tables.

No source_note shadow column on material/equipment: per-import source relations are authoritative and displayed on formal detail. Sources retain original/reviewed values, row/note/reason/actor/time/revision and relevant row warning confirmations plus global duplicate-file confirmation. Derived references without a corresponding master-data workbook row do not fabricate an extra master source row; the equipment source records the actual resolved reference.

Downgrade0032->0031 refuses if ANY v2 ASSETS batch exists in any state, ASSET/MATERIAL source exists, or target_key has data; message explains forward recovery. Only evidence-free new mode permits removing new columns/index and restoring old target/kind constraints. SITES provenance survives this downgrade;0031's own guard still refuses dropping retained v2 evidence. Never remove formal material/assets or rewrite old sample/report snapshots.

### Lock/call order

One engine.begin for each v2 mutation:

1. IdentityService.authorize_current(c,actor,'assets.import'): shared identity30003/account guard FIRST, hold through commit; returned current actor is audit actor.
2. Exclusive asset advisory110011; read actor+UUID intent. Canonical digest includes action, batch/mode/version or upload filename+SHA, revision, changes/reason, sorted unique warning IDs. Same key/different content/action409 import_operation_conflict; same intent returns stored operation result even when a later action changed live batch.
3. Batch FOR UPDATE; already PUBLISHED returns original full mapping, never inserts again. A successful replay is not rejected for an old revision. A different key may observe PUBLISHED and the same IDs.
4. Publication locks reference tables in fixed order `asset_materials,customers,sites,site_product_lines` SHARE ROW EXCLUSIVE. This protects catalog/provisioning writers not using110011; lifecycle/asset graph writers already use110011. No domain lock precedes identity and no exclusive identity lock is requested while holding domain locks.
5. Check original existence/actual length/SHA; revalidate all working rows with stable graph/catalog. Fingerprint includes customer/site/line facts, material number/model/type, matching serial candidate IDs/current lifecycle/context revisions and all duplicate-file results. New relevant candidate/catalog fact invalidates preview even if normalized source strings are equal.
6. Compare persisted digest, rows and complete issues. If changed, save preview/increment validation_revision, persist operation REFRESHED(new revision, no targets), commit and return; ZERO business/source writes. Operator reviews with a new key. Old key must keep returning REFRESHED after later publication.
7. If unchanged require VALIDATED, submitted current revision, no ERROR and current warning confirmations. create_batch on same connection; final validate_graph; mark PUBLISHED/targeted rows/actor/time; append ASSET_IMPORT_PUBLISH with per-kind counts/mapping/confirmations; insert operation success last; single COMMIT.

Publication row writers cannot open nested independent commits or call per-record public mutations. Source creation, audit or operation-insert failure rolls back masters/equipment/relations/batch success together. Do not mark operation succeeded in a finally block.

Worker only validates; never publishes. Take110011 BEFORE `FOR UPDATE SKIP LOCKED` pending-batch claim so it cannot hold batch while waiting behind revise/publish's domain lock. Use a caller connection with REPEATABLE READ for validate_next so all catalog/candidate reads share one snapshot; acquire110011 before claim. Serialization/deadlock errors roll back and are retryable on the next worker pass, not permanently classified as bad-file FAILED. Claim+preview/revision commit together. Worker preview does not authorize future business writes. Unexpected validation failure uses savepoint, retains original and records FAILED/failure_code rather than endless STAGED retry; malformed business rows produce normal VALIDATED issues. Both v2 modes use safe claim order; v1 observable validation behavior remains unchanged.

Upload puts immutable object per batch before successful receipt. FileStore failure ->no successful operation/batch. Definite DB rollback may leave orphan evidence for#60; uncertain COMMIT must NEVER delete its object. Publish unavailable/missing/corrupt original ->VALIDATED/no business result/503; restored original permits same-intent retry. No distributed file/DB transaction or provider/configuration change.

### State/revision/outcome contract

Keep states STAGED->VALIDATED->PUBLISHED; parse/technical validation failure ->FAILED. VALIDATED plus ERROR is “needs attention”; warnings “requires confirmation”; otherwise ready. Worker/revise/refresh increases validation_revision. Revise recoverable existing rows in STAGED/VALIDATED, never PUBLISHED; FAILED without parsed rows requires reupload. Existing sheet/row fields only, no row insertion/deletion/reordering. Up to2000 unique row changes, one nonblank event reason; row reason plus revision event reason preserved.

Actor-scoped operation GET returns exact durable result. Keep outcome/batch_id/revision/target_ids; ASSETS adds typed `targets:[{sheet,row,record_key,kind,target_id?,target_key?,system_asset_number?,decision}]` in stable source order. UUID target_ids retains UUID-list semantics; MATERIAL target_key=number. Typed targets cover full2000-row mapping, not only displayed20 rows. UPLOAD STAGED/FAILED, REVISE REVISED, PUBLISH REFRESHED(no targets) or PUBLISHED(full targets). Include stored result as additive operation_result on v2 mutate batch responses; live preview may be newer but cannot relabel that operation. Same-key replay returns original outcome. Missing operation404 after timeout is “unconfirmed”, not proof of rollback; retain intent/input, read/query and retry exactly same key/content.

## 4. Public/HTTP contracts and errors

| Interface | Concrete change |
| --- | --- |
| AssetImports.template / GET `/api/assets/imports/template` | Default version2/modeASSETS; explicit1ASSETS/2SITES remain. Authenticated XLSX/no-store, mode/version filename. |
| submit / POST imports | Existing streamed XLSX body and filename/version/mode query; upload defaults1ASSETS; v2 UUID Idempotency-Key required.201 is retained STAGED/FAILED, never business publication. |
| get / GET imports/{id} |20-row business paging, actual mode/version, per-kind counts, original_values/values/typed references/resolved context/candidates/IDs/issues; duplicate_page(default1)/duplicate_total/paged duplicate_batches. Internal source arrays/object keys/catalog digest hidden. |
| list_batches / GET imports |20-row search/paging retained; actual mode/version/per-kind counts and correct links. |
| revise / POST {id}/revisions | Sheet literal Customers/Sites/Materials/Assets; extra forbid; values max20keys; changes1–2000 unique rows; expected_revision strict int>=0; reason1–1000; UUID key. Application repeats per-sheet whitelist/scalar checks. Invalid row/sheet/patch/mode422. |
| publish / POST {id}/publish | validation_revision strict int>=1, UUID key, unique24-hex acknowledged_warning_ids max12000. Existing legacy boolean v1-only; unknown top-level fields reject.200 REFRESHED explicitly carries new revision/no business success; operation_result durable. |
| operation / GET operations/{key} | Current import authorization; actor-scoped404 for another actor; exact persistent outcome/mappings. |
| source/revisions | Existing authenticated original byte download and20-row revision history support both modes; raw/reviewed evidence, safe filename/MIME/no-store and source-download audit. |
| AssetDirectory.import_sources(actor,kind,target,page=1) | Add ASSET(UUID) and MATERIAL(exact material_number) alongside CUSTOMER/SITE;20-row sources include confirmations and batch mode/version. Bad kind/ID422; missing/unreadable target404. |
| AssetDirectory.material_detail(actor,material_number) | Read-only `{material_number,model,asset_type}`; no update route. |
| Asset HTTP | GET `/api/assets/equipment/{asset_id}/sources`; GET `/api/assets/materials/detail?material_number=...`; GET `/api/assets/materials/sources?material_number=...&page=1`. Material query identity preserves slashes/special characters; static routes before dynamic routes. |

Staging/list/revise/publish/operation/originals require CURRENT assets.import; current permission on template reads as well. Formal source/material/equipment reads require assets.read. They expose provenance text, not private original bytes or storage keys; importing permission is not implied by read permission.

Failure body remains `{code:string}` with no-store; request validation uses existing invalid_input422. Row issues `{id,code,severity,sheet,row,field,message,original_value,suggestion}`, with readable candidate/resolved facts; row0=file. New stable codes: invalid_material_ref/material_not_found/material_conflict/material_exists_choose_reference/duplicate_material_number/site_not_found/batch_reference_not_found/site_reference_required/site_product_line_missing/site_name_difference/inherited_site_conflict/duplicate_serial/duplicate_file/missing_parent/cyclic_installation/parent_not_at_site/invalid_effective_at/status_location_conflict. Preserve#49 stored codes; no historical issue rewrite.

401 session;403 permission/CSRF;404 absent batch/operation/target;409 import_not_validated/import_stale_validation/import_has_errors/import_warnings_unacknowledged/import_operation_conflict/import_already_published;413 byte/capacity transport rejection;415 MIME;422 structure;503 safe storage/SQL failure. Safely retained workbook content/row-limit violations remain FAILED issues (not a lost upload). SQL ->generic import_*_unavailable; FileStore ->object_storage_unavailable. Never SQL/payload/credential/opaque object-key leakage. HTTP owns transport/CSRF/schema/status only; business validation stays in facade. Upload/revise/publish/source-download use AuditTrail; request security retains existing denied/CSRF audit behavior.

## 5. Frontend behavior

`/assets/import` becomes v2ASSETS; `?mode=SITES` v2SITES; `?format_version=1` legacy. Persisted batch metadata wins over URL guesses; old batch-only links load and route to their actual version/mode. Legacy upload/publication behavior stays, with explicit1ASSETS template/upload URLs and corrected history links.

Rename SiteImportPanel.tsx ->V2ImportPanel.tsx; parameterize mode ASSETS/SITES, extend existing tables/edit/recovery rather than a parallel wizard. Keep siteImportIntent CSPRNG/hash helpers. New intent signature includes mode/version; ASSETS pending namespace separate from retained `dga-site-import-pending:<actor>`. Persist key/kind/digest/mode/batch before network call. Recover server operation before creating another;401/403/5xx/network loss retains pending state. REFRESHED completes that intent and clears acknowledgments; PUBLISHED uses saved typed targets. Live PUBLISHED cannot masquerade as outcome of an earlier REFRESHED intent.

Show four sheet kinds/per-kind NEW/REFERENCE counts,20-row server paging, notes/raw/current values/cell problems. Existing customer/site controls remain. Material editor explicitly NEW/REFERENCE with number/model/type differences; equipment editor cannot add site fields/customer. Site candidate choice fills UUID/name only; inherited parent context displayed. Equipment candidates are readable existing-detail links plus explicit distinct-physical confirmation. ID/name checkbox states the UUID adopted. Save revision+reason revalidates whole batch and clears confirmations across pages.

Repeated file prominently shows prior published results first with paged/mode-aware links. Opening new-physical review doesn't auto-approve warning. Published materials show exact number/detail/source, assets link equipment. ImportSourcesPanel adds equipment/material variants, batch mode/version links; EquipmentDetailPage includes own and material sources/details. assets.read sees source text; original/batch link only assets.import.

States: loading/empty/STAGED/background processing/ERROR blocked/warning confirmation/ready/saving/publishing/technical retry/unknown-outcome recovery/published. Separate actual upload progress from validation (XHR upload progress acceptable; no simulated percent). Focus/scroll to problem region and offending sheet/row; retain edit while unresolved. Long notes wrap, visible disabled-publish rationale, no overlap at1920x1080. Tests assert user-visible navigation/download/feedback, never React internals, component snapshots or CSS structure.

## 6. Implementation file ownership

Paths relative to this checkout. This is future slice ownership, not source-edit permission for this plan gate.

| Owner | Files |
| --- | --- |
| Assets public interface | backend/dga/assets/imports.py, public.py, http.py, import_http.py. |
| Retained v2/parser | Rename site_imports.py->v2_imports.py, site_import_workbook.py->v2_import_workbook.py; site_import_validation.py; new asset_import_validation_v2.py and import_persistence_v2.py. |
| Existing rules | import_workbook.py/import_validation.py/lifecycle.py read/reuse. No broad rewrite; only evidence-backed minimal helper/constant extraction in import_validation if necessary, with exact v1 regression and explicit review. Lifecycle commands unchanged. |
| Schema | backend/migrations/versions/0032_device_material_import.py only. |
| Backend tests | New backend/tests/test_device_material_import.py, test_device_material_import_http.py, test_device_material_import_migrations.py; focused existing test_asset_import.py/test_site_import.py adjustments for explicit legacy template/compatibility. Reuse conftest historical/FileStore seams. |
| Frontend | AssetImportPage.tsx, rename SiteImportPanel.tsx->V2ImportPanel.tsx, siteImportPresentation.ts, siteImportIntent.ts only for mode intent helper if needed, ImportSourcesPanel.tsx, EquipmentDetailPage.tsx, siteImport.css/assetImport.css as needed. No global state/UI framework. |
| Browser evidence | New frontend/tests/device-material-import.spec.ts, fixtures/device-material-import.xlsx; backend/tests/make_device_material_import_fixture.py; zz-asset-import.spec.ts explicit legacy view; site-import.spec.ts only mode-aware expectations if required. Fake fixture/public commands; no acceptance seed change. |
| Docs | README.md/CONTEXT.md/PROJECT_PLAN.md and per-slice/review artifacts under docs/work-units/docs/reviews by later dispatch. Controller/original ADRs/provider settings/lockfile/CI unmodified unless a separately reviewed failure proves necessity. |

## 7. Vertical implementation slices

Three slices chosen by behavioral risk. Each receives an implementation/review/fix/accepted-slice checkpoint; only controller dispatch proceeds. Overlapping allowlist files do not authorize cleanup. Tests below cross AssetImports/AssetDirectory or HTTP with real PostgreSQL; private helper/table-shape tests and React implementation tests are excluded.

### S1 — Complete v2 ASSETS staging and reviewed preview

Objective/outcome: new format downloadable, safely retained/validated/revised, formal data unchanged. Prerequisite: accepted plan. Allowed: parser/coordinator renames, imports/import_http/site_import_validation/new asset_import_validation_v2, new behavior/HTTP tests, explicit legacy-template regression adjustments. No schema/writer/formal-detail/UI work yet.

Implement sections1–2 mode/schema/type/ref/graph/candidate rules and submit/template/get/worker/revise/duplicate paging. Immutable source_rows and revised working_rows remain separate. Current authorization/intents/revision/original retention ship with first staging write. Expose operation_result for upload/revision. Preserve SITES and old source queries. Until S2, ASSETS publish409 import_mode_not_publishable BEFORE any business write; never fall through to SITES. S2 removes this temporary guard before feature delivery.

Red first: public v2ASSETS template/submit fails unsupported format at reviewed base. Add expected facade failures/issues before implementation, then green complete preview/revision/recovery. Assert formal-query baseline unchanged and original download bytes equal; public revision history shows old/new/reason. Meaningful cases:

- Format/request mismatch, default2 vs explicit1 template; empty optional sheets, valid Sites with0devices, material-only invalid; numeric serial/ref; duplicate/unknown headers and forbidden equipment customer/site write fields.
- Existing/same-batch/missing sites/materials; wrong-sheet/duplicate key; material NEW-existing/REFERENCE conflict/duplicate number; root line mismatch; UUID/name warning and specific acknowledgment meaning in preview.
- PARENT inherited/mismatching site, repair-center legal row and repair-root child conflict; missing/self/cyclic/duplicate parent; legal100-node/invalid101-node path; child-before-parent, future/naive time, status/location/type/capacity errors.
- Retained malformed source, source-note-only revisions don't determine identity; same-intent upload/revise returns original result; current grants checked, source/private batch boundaries intact.

Commands: C1 with device behavior+HTTP/site/legacy/architecture tests (omit not-yet-created migration test); C2. Expected new preview has actionable field issues/candidates, revision and durable operation result, no formal publication; existing suites still pass. S1 report records base/head/changed files/red+green/temporary guard and S2/S3 risks. Stop on a required new contract/ownership ambiguity instead of expanding scope.

### S2 — Whole-batch atomic publication and formal provenance

Objective/outcome: masters/equipment/relationships/sources publish once and recover exact typed targets. Prerequisite: accepted S1. Allowed:0032/import_persistence_v2/v2coordinator/validator/facade/HTTP, public/http, three new backend test files, focused regressions, README schema/recovery notes. No frontend/provider/library redesign.

Red first: mixed new customer/site/material plus unordered root/child/grandchild batch fails S1 guard; implement writer/migration/lock/state contracts and remove guard. Test through formal queries that all correct paths/materials/sources appear together. Current-auth/FileStore/revision/catalog/idempotency/audit/provenance/source read permissions ship with first formal write. Replayed PUBLISHED cannot append entities/sources/audit again; REFRESHED remains a durable distinct outcome.

Required red/green scenarios (faults are at FileStore/DB transport/COMMIT seams; success checks public data/download/audit):

1. Mixed existing and same-batch sites/materials; dual-line site; REFERENCE rows and standalone repair-center transformer. Correct site/path/model/material/history; no independent child site. Existing master attributes/notes/source entries unchanged. Material/equipment sources show original/reviewed row/note/batch/reason. assets.read reads formal provenance but cannot read import batch/originals.
2. Existing and within-batch repeated serials show context; missing specific acknowledgment blocks; explicit distinct physical entity creates different UUID/system numbers. Reupload published bytes prioritizes old results and cannot publish until duplicate-file+serial confirmations. More than20 later drafts cannot hide earlier published result from paged duplicate history/full fingerprint.
3. Change live site name/line/revision, material model/type, new matching serial candidate, same-name master candidate or duplicate result after preview: publish REFRESHED/new revision/no business writes. Old key remains REFRESHED after later new key publishes. Stale revision/new payload409; obsolete/extra warnings or v1 blanket bool cannot approve ASSETS.
4. Concurrent identical upload/revise/publish intent ->one batch/change/full target mapping; same key/different content409; actor scopes isolated. Concurrent different publish keys on one batch return same IDs. Two draft publishes competing on same NEW material number ->one success and second refreshed/conflicting preview; never upsert/partial masters. Concurrent new same-name/site/customer/serial candidate causes review; explicit legal different entities remain possible.
5. Inject failure after master creation, during equipment/installation/source writes, final audit and final operation insert. Batch stays VALIDATED, public customer/site/material/equipment observations remain baseline, no operation success, original bytes retained. Remove injection and same-key retry succeeds once. SQLAlchemy connection events may target failure stage; do not assert business success by private INSERT counts/table layout.
6. Lost durable COMMIT response for upload/revision/publication using existing engine.begin wrapper pattern: normal engine reads operation, exact original and mappings survive; same key retry recovers them; never deletes object. Distinguish definite rollback. Missing/corrupt/unavailable FileStore original blocks all business publication; restored bytes allow retry.
7. Revoke grant/disable account after staging: cached actor cannot publish. Concurrent public identity revoke and publish linearize on identity30003, no deadlock; winner determines current authorization through commit. Bounded futures prove completion. Preserve current-auth legacy regression. HTTP-only security matrix covers CSRF/session/roles/unknown fields/no-store/error mappings.
8. Existing assets/installations/lifecycle and an existing sample's frozen asset snapshot/readable report facts equal before/after via respective public readers. Architecture checks reject reverse/private imports. No lab/analysis writer touched.
9. Real0013/0030/0031 upgrade and guarded downgrade tests in section8.

Commands: C1 with all new files plus legacy/site/lifecycle/equipment/architecture suites; C3 full backend/real storage contracts before accepting shared transaction/source changes. Expected exactly whole publish or no business write, stable persisted outcomes after failures, readable sources and no regressions. Report migration/lock order/public observations for each failure. Stop if true existing-data invariants or writer lock protection cannot be preserved without a new architecture/scope decision.

### S3 — Operator flow, exact legal capacity and upgrade closeout

Objective/outcome: usable production UI, key browser chain, completed unit acceptance/doc evidence. Prerequisite: accepted S2. Allowed frontend/browser/generator/fixture/docs files above and backend capacity test additions; source fixes only for demonstrated approved behavior with recorded review, no contract invention.

Red first: browser default import expects v2ASSETS template/upload and equipment editor with only site references; old UI is legacy. Implement section5. Extend existing site-creation chain: download sites export/create zero-device site via SITES -> equipment file references that same formal site -> one deliberate UUID/name conflict -> correction or explicit-ID confirmation -> publish -> equipment detail path/source/material sources -> return correct batch/original byte download. Same-batch-new-site combinations stay primarily facade tests, avoiding redundant browser matrices.

One browser response-loss scenario lets a real publish commit but aborts its HTTP response, reloads/reopens and queries persisted intent: exactly one ID set/no duplicate publish. Include repeat-file prior results and distinct-physical review, plus existing SITES/explicit legacy regressions. Use real API setup and HTTP response loss only, never internal component state. Assert visible long-note wrap/actionable error focus/disabled rationale/progress/return navigation and1920x1080 screenshots/traces.

Exact legal maximum: one workbook with500 NEW customers+500 NEW sites+500 NEW materials+500 NEW equipment roots,2000-character notes/text identifiers, normal Instructions within10MiB/50MiB/200members/150000cells. Publish, page all100 preview pages, assert full typed results500 of every kind, directory sees500 new customer/site/equipment and material_detail reads all500 proposed numbers. Sources and retry IDs match; staging alone is not capacity proof. Parameterize501 of each sheet plus byte/expanded/sparse/formula/macro/external/malformed/duplicate-member bounds; visible failure/no partial business publication. Include material number starting NEW: and containing slash for faithful reference/query.100-node tree already covered separately;500 rows does not imply500-node depth. Record observed duration/recovery, no invented performance target or deferral of this capacity to#61.

Commands C1 targeted boundary/HTTP, C2, C3, C4. Existing passing checks repeated only after relevant change/new failure evidence; final whole suites once. Update docs, remove temporary guards, map each#50 criterion to actual proof/classified residual owner. Report completion to controller for aggregate deepreview/draft PR gates; this slice itself grants no commit/PR/merge/comment authority.

## 8. Historical upgrade and preservation proof

Use parametrized database_url historical-schema fixture, no stamp and no downgrade of shared head/acceptance DB.0013_asset_import: construct minimal historical users/roles/master assets/installations/materials and v1 STAGED/VALIDATED/PUBLISHED source/batch fixtures using schema at0013; DO NOT call current reception_context before upgrade (it needs later lab tables).0030_merge_export_identity: equivalent v1 plus available old sample/history fixtures.0031_site_import: additionally stage/publish/revise SITES through AssetImports. FileStore holds original exact bytes.

Run real alembic upgrade head in each isolated schema. Current public imports/directory/identity/lab readers show original IDs/system numbers/source bytes/results/history/snapshots intact; v1 references never create masters, valid old drafts continue v1 validate/publish; SITES resumes/reads; fresh ASSETS publish works. Historical fixture SQL is setup, not the business success seam; no exact private column layout assertion.

Evidence-free0032 can downgrade0031/reupgrade. Any ASSETS draft/source/result refuses downgrade and remains readable after failure. SITES-only provenance survives allowed0032->0031;0031 guard still refuses losing retained site imports. Migration cases serial in their own schemas; refused downgrade leaves usable connection/schema.0032 adds no permission and never rewrites business history.

## 9. Commands and evidence requirements

These are FUTURE implementation commands/expected assertions, not tests claimed run by this plan agent. Always explicit #50 checkout; if shell startup changes cwd, use absolute Compose file paths plus --project-directory. Separate project names protect retained data; no simultaneous suites against one test-db.

```powershell
Set-Location -LiteralPath 'C:/Users/weila/.codex/worktrees/issue-50-material-import/DGA Lab'
```

C1 focused red/green, choose active-slice explicit tests (S1 omits absent migrations file):

```powershell
docker compose -p dga-issue50-tests -f compose.yaml --profile test run --build --rm api-test pytest -q -p no:cacheprovider tests/test_device_material_import.py tests/test_device_material_import_http.py tests/test_device_material_import_migrations.py tests/test_asset_import.py tests/test_site_import.py tests/test_site_import_http.py tests/test_asset_lifecycle.py tests/test_equipment_details.py tests/test_architecture.py
```

Conftest requires test-db/dga_test/dga_test and real migrations. Red means missing business behavior, not unavailable runtime/network or guessed schema. Record failed assertion then green public result.

C2 frontend production type/build:

```powershell
docker compose -p dga-issue50-tests -f compose.yaml build frontend
```

Expected TypeScript/Vite production build passes; alternatively npm --prefix frontend run build only with this checkout's dependencies.

C3 full backend + existing FileStore/MinIO/Azurite contracts:

```powershell
docker compose -p dga-issue50-tests -f compose.yaml -f compose.storage-test.yaml --profile test run --build --rm api-test
```

Expected complete behavior/architecture/migration/storage suites pass with provider configuration unchanged. Emulator results are not real Azure/Okta acceptance.

C4 key production browser flows in fresh isolated project:

```powershell
$env:DGA_BROWSER_PORT='18170'
docker compose -p dga-issue50-browser -f compose.browser.yaml -f compose.import-browser.yaml up --build -d --wait frontend import-worker
docker compose -p dga-issue50-browser -f compose.browser.yaml -f compose.import-browser.yaml --profile test run --build --no-deps --rm browser-test npm run test:e2e -- tests/site-import.spec.ts tests/device-material-import.spec.ts tests/zz-asset-import.spec.ts
```

Check18170 free; if occupied use another unused port, never18148/18165/18164. New fake workbook generator runs in this isolated backend runtime before browser image build. Do not reseed between linked site/device stages. After key flows, run full browser suite once on this same isolated project. If build/runtime external availability fails, retain logs/report unavailable; do not use acceptance data as replacement.

C5 scope proof:

```powershell
git -C 'C:/Users/weila/.codex/worktrees/issue-50-material-import/DGA Lab' diff --check
git -C 'C:/Users/weila/.codex/worktrees/issue-50-material-import/DGA Lab' status --short --branch
```

Controller handles protected scoped commits and exact-head CI at later gates. No reset/clean/user-workspace mutation.

## 10. Documentation, risks and completion format

CONTEXT source-note definition includes materials/equipment/explicit references; preserve immutable physical identity/inherited site terms. PROJECT_PLAN replaces pending#50 note only after implementation and states v1/v2 scope. README documents defaults/legacy template, MATERIAL:/NEW: syntax, limits, specific confirmations, original/operation recovery, source permissions and0032/forward recovery. No lab/finalization rewrite, speculative ADR or copied dirty domain docs. This implements confirmed#47/ADR0001/0004 and changes no module/provider ownership. A genuinely new architecture decision found by review is a stop condition before implementation.

| Residual/uncovered area | Classification / owner |
| --- | --- |
| Wrong mode dispatch/material identity/source schema | Fixed in current unit S1/S2, #50 implementation owner. |
| Partial commits/stale grants/catalog/warnings/lost response/duplicate publication | Fixed in current unit S2 failure/concurrency proof, #50 owner. |
| Exact2000-row behavior and unsafe limits | Covered by later approved S3, #50 owner; not deferred to#61. |
| Long-lived orphans/cancellation/lease takeover/reconciliation | Tracked existing#60, asset import owner; basic current-write safety remains here. |
| Combined asset/lab/analysis chain and broader operational load | Tracked existing#61, later acceptance owner. |
| Lab import/finalization/time precision | Assigned later#51/#52/native children, controller; not needed for#50 acceptance. |
| Real Azure/Okta environment | Existing deployment/identity acceptance owners (#18/deployment work); local emulators cannot close it. |
| Prerequisite/main/new exact-head CI | Controller-owned, record exact hashes/results rather than infer. |
| External closeout issue comments | Requiring explicit user decision at batch closeout; prepare concrete comments later, no send from this dispatch. |

No blocking scope question remains. Explicit engineering choices for review: MATERIAL: prefix preserves arbitrary existing material identity; source target_key avoids fictitious UUID; default template v2 but omitted upload legacy; repeated-file draft prioritizes existing results and requires new-physical confirmation. Business goals already confirmed, no repeat interview.

Each slice report: unit/gate/base+head, allowed/changed files, actual public behavior/results, red/green command evidence, schema/docs decision, review finding/fix status, classified residuals/owners, temporary guards and next controller entry. Final delivery maps#50 criteria to actual proof and later-authorized draft PR linkage, distinguishing draft-PR-pass from final-closeout-pending. Current plan report: only two planning files authored; no source/runtime implementation, tests or gate advancement.


### Named acceptance tests for implementation

Use these names as concrete entry points (parameterize variants listed in the slices); they describe public behavior, not helper calls:

- S1/test_device_material_import.py: test_v2_assets_template_and_staging_preserve_original_without_business_writes; test_explicit_existing_and_batch_references_resolve_independent_of_row_order; test_material_conflicts_and_forbidden_site_writes_are_actionable; test_initial_tree_position_status_and_time_failures_block; test_site_id_name_difference_requires_explicit_id_review; test_revise_preserves_source_and_invalidates_current_preview; test_100_node_initial_path_is_valid_and_101_is_blocked.
- S1/test_device_material_import_http.py: test_v2_assets_http_upload_revision_and_recovery_require_current_permission_and_csrf; test_default_v2_template_and_explicit_v1_upload_remain_distinct.
- S2/test_device_material_import.py: test_atomic_mixed_batch_is_queryable_with_material_and_equipment_provenance; test_duplicate_serial_requires_current_new_physical_confirmation; test_reuploaded_published_file_prioritizes_results_and_requires_review; test_catalog_and_candidate_change_refreshes_without_business_writes; test_refreshed_intent_keeps_its_outcome_after_later_publication; test_concurrent_same_intent_and_distinct_publish_keys_share_targets; test_competing_new_material_batches_never_upsert_or_partially_publish; test_late_publication_failure_rolls_back_all_business_and_success_state; test_lost_commit_response_recovers_exact_original_and_targets; test_missing_or_corrupted_original_cannot_publish; test_current_grant_change_linearizes_before_asset_publication; test_import_preserves_existing_asset_and_sample_history.
- S2/test_device_material_import_http.py: test_formal_sources_are_readable_without_authorizing_private_original; test_errors_and_unknown_write_fields_keep_safe_http_shapes.
- S2/test_device_material_import_migrations.py: test_real_legacy_upgrade_preserves_originals_and_old_batch_semantics (0013/0030/0031); test_0032_downgrade_is_guarded_and_site_sources_survive.
- S3/test_device_material_import.py: test_exact_500_of_each_kind_publishes_and_recovers_all_2000_targets; test_501_in_each_sheet_and_unsafe_expansion_never_truncate; test_material_reference_and_detail_preserve_reserved_prefix_and_slash.
- S3/device-material-import.spec.ts: existing-zero-device-site -> ID/name review -> equipment publication -> formal sources -> correct batch/original; completed-publish response loss -> reload -> durable operation recovery; repeated file -> prior result -> explicit different-physical review. Keep the browser list to these business chains.

Source locations and line numbers above refer to reviewed base, not new file line positions. Exact outcomes and state/error assertions are the normative test expectations in sections1–8; the names are not a substitute for those assertions.
