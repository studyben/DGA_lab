# Issue #51 — immutable finalization facts and optional PDF request plan

Gate: PLAN, pending independent planreview. No implementation/review pass is claimed.
Date: 2026-10-29.
Branch: codex/issue-51-finalization-facts.
Checkout R: C:/Users/weila/.codex/worktrees/issue-51-finalization-facts/DGA Lab.
Fixed parent/base: fcea999e313db51461cd9aefda66d70e6e34ed3b.
Future PR stack base: codex/issue-50-device-material-import; parent PR #65 draft/unmerged.
Native #51 blocked_by=[]; the stack is an engineering choice, not a fabricated issue dependency.

## 1. Authority, gate and source reconciliation

The human already confirmed #50/#51/#52 batch goals. issue-51-goal-confirmation.md records that existing confirmation, motivation, exclusions and actual source. Do not re-ask the goal. The controller explicitly permits only these two PLAN docs now. Independent planreview is next. Controller subsequently recorded exact fcea999e GitHub PR40975486166/push40975478587 and Sungrow312301681 COMPLETED/SUCCESS (622 backend cases with configured storage executed;77 browser passed/1 intentional OIDC skip). The parent-CI prerequisite is resolved; accepted-plan commit/implementation still require independent planreview and controller dispatch. If #50 changes, refresh against its new reviewed head before acceptance. No external issue/PR/comment/merge action is authorized here.

Sources read: G:/Sungrow Develop/DGA Lab/AGENTS.md and docs/agents/domain.md / issue-tracker.md; controller docs/work-units/phaseflow-50-52-control.md; frozen outputs/specs/bulk-data-import.md D10/D12/T1/T2-17/18/21/22 and issue-47/51.json; existing read-only issue-51-evidence.md; this checkout's CONTEXT.md, PROJECT_PLAN.md, ADR-0007 and current code; original G: accepted ADR-0002/0003/0004/0005/0009. Do not copy unrelated dirty G: docs. ADR-0009 supplements the ordinary report workflow; it does not revoke it.

Preflight executed read-only with explicit managed workdir/--work-tree: correct feature branch, clean status, HEAD fcea999e. git diff 6eb7d5e..fcea999e is empty for laboratory, analysis, shared/auth, migrations, conftest and named legacy/historical tests. Thus the earlier source map is current for those paths; its old #50 S3-in-flight status is historical, not this plan's gate state. Current source head is 0032_device_material_import; retain merge nodes 0014_merge_laboratory and 0030_merge_export_identity. No main/retained checkout/reset/reseed/old runtime mutation.

## 2. Outcome, scope and direct evidence

Effective laboratory results must exist because the sample has current valid immutable finalized facts, not because a PDF request exists. Ordinary finalization continues autoqueueing and must fail atomically if its queue/write/event/audit fails. An explicit privileged Python application policy can finalize with no PDF request; ordinary HTTP continues its existing behavior and rejects extra write fields. All three public analysis consumers retain current physical identity, exact method/unit groups, qualified-value exclusions, health aggregation and alarm dedup/recovery semantics.

Direct source:
- workbench.py:454–533 locks configuration and sample, validates all ACTIVE tests/warnings, selects sole results, updates token then unconditionally queues before event/audit. :547–584 clears token and invalidates report on reasoned withdrawal.
- reports.py:353–469 currently owns both request and snapshot; :118–165 retry already preserves a saved copy; :167–246/:327–341 guards current sample, generation and claim; :275–325 reads saved bytes under share locks and validates size/SHA.
- trends.py:16–75 validates only v1 selected facts; :128–154 joins current report token without a READY/file predicate, raising 503 for typed corruption. No independent fact source exists.
- condition_analysis/public.py:61–102, health.py:63–110, alarms.py:69–143 consume laboratory.public protocols. Their serialized measurement payloads participate in immutable evidence/currentness comparisons.
- operations.py:88–95 already distinguishes COMPLETED from current READY/REPORTED. It should remain that way.
- migration 0032 extends assets-only provenance. New #50 historical tests upgrade to dynamic head, with OPEN samples and asset snapshots; they are not valid old finalization/PDF migration evidence.
- 0025_identity_roles.py:25–28 and shared/auth/policy.py:10 grant analyst laboratory.finalize. Preserve that actual #18 policy; obsolete parent current-state prose is not authority to revoke it. Policy alignment remains #53.

Non-goals: formal external-data writes/import facade, original-PDF upload, DATE-only writes, import UI, full manual first-summary workflow, new storage/provider/queue, full report redesign/history UI, guessed ASTM methods/compatibility/thresholds, real Azure/Okta setup, old file/ID/barcode rewrite, live-table reconstruction of missing legacy facts. No current installation/path-depth redesign (#61/#53).

## 3. Module and interface decisions

Use one deep laboratory-private module backend/dga/laboratory/finalization_facts.py for immutable capture, v1/v2 validation, current-fact loading, summary and PDF projection. It hides SQL/version/provenance details from Workbench, Reports and consumers. It uses the caller's Connection and existing configuration/typed-result rules; no repository/protocol/port hierarchy is added for one adapter.

The seam remains laboratory.public:
1. Existing LaboratoryWorkbench.finalize(actor, barcode, acknowledged_warning_codes=(), *, report_policy=FinalizationReportPolicy.QUEUE_CURRENT) -> WorkbenchSample. Add enum QUEUE_CURRENT / NO_REQUEST in S2. Validate enum values; invalid policy -> LaboratoryError invalid_report_policy/422. Same identity/QC/selection/warning and current authorization rules apply to both. NO_REQUEST is explicit application code intent, not an ordinary HTTP field.
2. Add LaboratoryWorkbench.get_current_finalization(actor, barcode) -> FinalizationFactsView in S1. laboratory.read, normalized barcode, 404 for unknown sample. This is a real owner-provided current finalized-fact read model for audit/workbench callers and public inventory assertions, not raw JSON/table exposure. Existing load() shape and older-schema fixture calls stay unchanged; do not add hidden information_schema/table-existence fallbacks to production.
3. FinalizationFactsView is a frozen public dataclass: state NOT_FINALIZED | AVAILABLE | UNAVAILABLE; unavailable_reason optional; token UUID|None; schema_version int|None; inventory_complete bool|None; active_test_ids tuple[UUID,...]|None; adopted_test_ids tuple[UUID,...]|None; acknowledged_warning_codes tuple[str,...]|None. NOT_FINALIZED has no current token/facts; UNAVAILABLE retains only known token/version and explicit reason, with unknown lists None (never fake empty inventory). AVAILABLE v1 has inventory_complete=False and active_test_ids=None; AVAILABLE v2 has complete actual IDs. The view never includes storage keys or report delivery state.
4. Export enum/view and the existing result protocols from laboratory.public. Do not export the store/decoder implementation.
5. Preserve ReportLifecycle.queue_current(connection,actor,sample_id,token,finalized_at,warnings) and invalidate_current interfaces and Workbench constructor ordering. Existing failing-lifecycle adapters remain useful. queue_current now loads/copies the already stored immutable current fact instead of assembling from live tables.
6. LaboratoryReports status/retry/file/claim/complete method shapes and report DB states remain. No new public first-request HTTP command or first-request button in this work unit. Missing request retry remains 409. Later manual summary work will cross the same frozen-fact interface.
7. FinalizedResultReader/HealthResultReader signatures stay. Their production adapter switches to facts in S2; analysis never imports this private module or reads its table.

An internal immutable decoded value supports capture_current(connection, effective_actor, sample_id, token, now, warnings), load_current(connection, sample/token headers), summary(...), and to_report_snapshot(...). These are private implementation methods, not extra facades. reports._snapshot/_selected_result and their JSON conversion move into this module, with the existing scientific validators reused; delete the old live snapshot construction rather than layering a second builder. Report-specific generation/request/claim/file metadata remains in Reports.

## 4. Additive schema 0033 and immutable payload

Use backend/migrations/versions/0033_lab_finalization_facts.py:
- revision 0033_lab_finalization_facts (27 characters, within Alembic version_num VARCHAR32); down_revision 0032_device_material_import; no edit/renumber of existing nodes.
- laboratory_finalization_facts columns: oil_sample_id UUID NOT NULL REFERENCES oil_samples(id); finalization_token UUID NOT NULL; snapshot_schema_version SMALLINT NOT NULL CHECK IN (1,2); physical_asset_id UUID NULL; sampled_at TIMESTAMPTZ NOT NULL; fact_snapshot JSONB NOT NULL; legacy_report_id UUID NULL. Composite primary key (oil_sample_id,finalization_token), index (physical_asset_id,sampled_at,oil_sample_id). No FK/ownership from analysis/assets into facts; physical ID is frozen laboratory identity evidence, not a new asset write.
- Version 1 allows nullable physical ID and arbitrary retained JSONB content so a corrupt historic payload can be preserved and later fail explicitly. Do not reject the entire database migration because one old report has JSON null/array/unknown embedded schema/invalid typed values.
- Version 2 CHECK requires nonnull physical_asset_id, JSON object with schema_version=2 and matching embedded sample ID, physical asset ID and finalization token. Full inventory/method/qualifier rules are validated by the laboratory module before INSERT; do not duplicate the complete Pydantic model in SQL.
- A BEFORE UPDATE OR DELETE trigger rejects changes to facts with a stable immutability error. Native capture is INSERT-only; no upsert that overwrites a token. Currentness is exclusively oil_samples.testing_status + testing_finalization_token, not an extra fact-state/current flag.
- Migration backfill INSERT ... SELECT only existing FINALIZED samples with nonnull current token and a report row whose token equals it, independent of report state/file availability. Copy r.report_snapshot and its column version exactly as v1; keep r.id as legacy_report_id; copy the preexisting sample formal_asset_id/sampled_at as frozen lookup headers. Do not cast/repair arbitrary JSON, regenerate tokens, enumerate today's tests, infer source/precision, touch report rows/PDF metadata/bytes, or create facts for missing/mismatched reports. Existing report snapshot_schema_version column is constrained to 1; don't loosen or rewrite it.
- Backfill raw nonnull-current-token candidates even if their content is invalid; application validation must continue failing rather than silently omit a bad snapshot or invent a valid fact. Store provenance as legacy_report_id/version, not a fictional complete inventory. Legitimate pre0007 FINALIZED/ASSOCIATED rows whose token remains NULL are unqualified legacy records: do not generate a token/fact for them or include them in aggregate result candidates.
- Do not backfill obsolete withdrawn/mismatched requests using today's possibly edited sample metadata. Their existing inaccessible report rows/events remain untouched. Every migrated current fact remains retained when it is later withdrawn; all new tokens retain their own facts.
- Downgrade: first reject any nonempty facts table with 'Retained laboratory finalization facts require forward recovery'. When empty, drop trigger/function/index/table and return to 0032. Do not delete/transform populated facts to permit rollback. Production/retained acceptance rollback is forward recovery; isolated historic-schema tests can traverse an empty 0033.

New v2 fact JSON (internal schema, never a user report version):
- schema_version=2.
- sample: oil_sample_id, formal_asset_id plus exact existing report sample keys barcode/sampled_at/received_at/site_name/equipment_serial/notes/identity_status/asset_snapshot; package_snapshot copied as saved. Keep instant strings/decimals/UUIDs exact; no reinterpretation of source time.
- active_tests: every ACTIVE record ordered created_at,id, each containing the existing frozen selected-result shape (test_id,test_type,method with ID/code/name/version/full fields/configuration, measured_at,instrument_name,quality_snapshot,notes,typed result) plus analyst_user_id, instrument_id, selected_for_report, created_at/updated_at and attachment metadata from the existing laboratory attachment read path. Copy IDs/filename/content type/size only, never read attachment bytes/object keys into facts. No removed records.
- adopted_test_ids: deterministic test_type then created_at,id order; exactly one active test per present type after existing auto-selection, no duplicates and each ID exists in active_tests. selected_for_report flags and this list agree. Do not independently copy a second mutable selected-result list into v2.
- acknowledged_warning_codes: sorted unique exact confirmed current assessment codes, including warnings on unselected active tests. Preserve their saved quality evidence; do not recompute calibration/QA at report time.
- finalization: exact token, real finalized_at, effective internal actor UUID and display name.
- read_metadata: result_origin, sampled_at_precision, measured_at_precision, sampling_context_verification; all None from this work unit's producers. Definitions in section 8. Do not infer local/external provenance merely because an old sample is refinalized at the workbench.

Validator v2 is frozen/extra-forbid, requires ASSOCIATED + matching physical identity/token/header/sample time, aware instants, unique nonempty active IDs, valid three existing typed test families/qualified values/method fields, exact adopted subset/flags/one-per-type and complete warning acknowledgement. Existing configured-method/precision constraints remain. Return deterministic immutable decoded values; callers cannot mutate the retained JSON. No independent revalidation against changed current method/asset/test tables on read.

Report projection creates schema v1 with the same old sample fields, selected_results projected from the adopted frozen active tests, frozen quality_evidence/warnings/finalization. Exclude inventory/read_metadata bookkeeping from renderer shape. No report-table schema bump or renderer-v2 platform is needed; existing v1 queued/READY bytes/claims remain legal.


## 5. Lawful legacy v1 verification and corpus

Before changing production laboratory code or adding 0033, S1 captures legal v1 producer outputs at exact parent fcea999e. Implement only a test capture helper first: backend/tests/capture_finalization_legacy.py plus fixtures/finalization_legacy/v1/{manifest.json,cases.json,pdfs/...}. Run on the new own guarded 0032 test DB using parent public SampleRegistry, Workbench.finalize, Reports and ReportWorker. The helper refuses if git diff fcea999e -- backend/dga/laboratory backend/migrations is nonempty or expected producer blob IDs don't match git show fcea999e:path. Record source commit, producer path/blob IDs, capture command, fixture case operations/IDs/tokens, observed public measurements/report states, payload SHA-256 and PDF byte SHA/size. No credentials/auth-session/password hashes in fixtures. Capture before source change is a required provenance checkpoint; a later publisher cannot be relabeled a parent-v1 producer.

Capture real parent-producer cases: single DGA with seven qualified gas readings, sole and repeated MOISTURE with explicitly adopted result, mixed three types, configured and placeholder methods, EQ/ND/LT/GT, genuine saved QA warning acknowledged through parent finalize including an unselected active test, READY PDF, QUEUED and FAILED request, withdrawal then refinalization with different tokens. Use existing isolated TEST configuration factories/clock and real validators, no guessed ASTM or formal thresholds. Export exact sample/report JSON/header data and PDFs after observing public results. Versioned fixture loader prepares owner storage only at the matching historical schema, preserving exact captured IDs/relationships; arrangement SQL is allowed, success assertions remain public. Captured snapshots are not manually rewritten into positive fixtures.

Additional positive old-shape producer is identified now, not guessed: local commit 71d8a9e23a4e2428937f604b8ef8e24c4fe272de, reports.py blob 12f2801b61df73b3d6e28003993a98653b2b0db7. Read-only source shows schema1 snapshot with no method.configuration or quality_evidence. The capture helper also loads that exact trusted historical report module in a test-only dga.laboratory namespace from git-show bytes, verifies the blob hash, and supplies its LaboratoryReports as the existing ReportLifecycle adapter to the unchanged fcea999e Workbench on the own0032 DB. Observe the resulting snapshot through parent public LaboratoryTrendSource and report/PDF interfaces before exporting. Manifest explicitly records BOTH caller fcea999e and report producer71d8a9e; never claim the entire71d8 application ran. This produces attested older v1 payloads through an actual old producer rather than deleting fields by hand. Capture a placeholder method case and READY bytes this way; metadata remains unknown. No production loader/runtime compatibility framework is added. If source/helper cannot reproduce a lawful output, stop S1's capture checkpoint for evidence, not fabricate a positive fixture. Parent-v1 fcea cases remain separate.


v1 decoding:
- Reuse current selected-result typed parser semantics: schema1, aware sampled/measured instants, one to three unique selected types, exact expected fields, finite nonnegative qualified values and optional method.configuration=None. No lookup of today's method configuration or missing metadata.
- Additionally verify known v1 producer envelope before calling it valid immutable evidence: finalization token UUID equals stored current fact token; required finalization instant/actor/display name well formed; sample barcode/identity/received time has known producer shape; snapshot sampled_at equals frozen sampled_at header as an instant. If asset_snapshot has formal_asset_id it equals frozen physical header; None asset snapshot retains known physical row identity without invented history. Do not require nonexistent legacy complete inventory or compare with today's tests.
- Valid v1 summary exposes adopted IDs only, inventory_complete=False and unknown active_test_ids=None. Raw report snapshot stays JSON-content equivalent, with absent configuration still absent, not filled from current tables.
- Lawful old token/valid v1 returns same result values/IDs/instants/units/method grouping and PDF bytes without withdrawing/refinalizing.
- Distinguish unqualified legacy NULL token from qualified nonnull current-token evidence. A legitimate legacy NULL-token row produces no measurement and is excluded before aggregate fact validation; its single-sample view is UNAVAILABLE/missing_finalization_token and report is refinalization_required. For a nonnull current-token candidate, missing/invalid current facts, unsupported schema, malformed fields, duplicate selected IDs/types, embedded token/physical/time inconsistency or malformed known envelope remains explicit trend_snapshot_unavailable503, never empty/partial success. A previously typed-readable but unverifiable/mismatched envelope is deliberately rejected as unverifiable; do not fabricate evidence to preserve inconsistency.
- Derive qualified-current negative cases from an attested positive fixture by one named corruption; manifest records parent case plus alteration. Keep the sample current token nonnull for aggregate503 cases: JSON null/array, unsupported version, null EQ value, unknown qualifier, missing fields, malformed configured method, duplicate adopted test/type, embedded token mismatch, physical/time mismatch, missing finalization envelope, a legacy report missing before migration so no fact is backfilled, a current fact missing after migration, and row-token mismatch. Report-request absence with an independently valid fact is not a corruption case. Missing configuration alone remains legal v1 placeholder. NULL-token legacy qualification is a separate lawful fixture category, not a corrupt-current503 negative case; never combine those expected outcomes.
- Typed facts and saved-byte download are separate. Existing READY current report with intact metadata/file downloads original bytes even when typed fact decoder fails. No JSON regeneration changes bytes or hides a valid old READY file. Unknown/mismatched token still blocks file access.

Migration acceptance starts at actual0032 with captured valid/invalid nonnull-token candidates, upgrades once to0033/head, compares public readback/IDs/instants/old PDF SHA. OPEN samples or tokenless metadata do not replace valid v1 snapshot coverage. Separately arrange a legal FINALIZED/ASSOCIATED record at actual0006 (valid finalizer/time and explicit fixture identity), run real0007 then0032 migrations and confirm its token stays NULL, without inventing token/fact/source data. Co-locate a lawful current finalized sample on the same physical transformer plus an unrelated transformer with a lawful current alarm source; use version-specific owner fixture arrangement or public current producer only after its required schema exists. After0033/head, public TransformerTrends, DeviceHealth and global AlarmCenter must still consume the lawful current results, and the tokenless sample must produce no point. Its get_current_finalization remains UNAVAILABLE/missing_finalization_token; report remains refinalization_required. This mixed-record test is additional to, never a replacement for, nonnull missing/bad-fact503 tests. After migration mutate live asset labels/current methods and deliberately alter test storage at the owner arrangement seam; qualified facts/PDF projection remain frozen or explicit integrity error, never rebuild from live tables.

## 6. Transaction, authority, lock order and transitions

Use existing IdentityService.authorize_current on caller Connection for finalize, withdrawal and report retry. Keep initial require_permission fast failure, then use returned effective actor for mutation/finalization metadata/audit. Preserve grants. HTTP still resolves current session + Origin/CSRF; direct application DTO cannot retain revoked rights across transaction guard.

Lock order: identity shared advisory(30003) + ACTIVE user FOR SHARE -> configuration lock for finalize only -> sample FOR UPDATE -> selections/fact INSERT -> report row insert/update -> event/audit. Withdrawal/retry omit configuration and retain identity -> sample -> report. No nested engine checkout in fact module. Never acquire identity after a domain lock. Existing other scientific mutations retain config/sample serialization.

Finalize:
1. Validate policy (S1 ordinary QUEUE_CURRENT; S2 explicit enum), permission/barcode.
2. In engine.begin, current-authorize, configuration/sample locks; reject already FINALIZED/identity/package/selection/empty blockers with existing rules; confirm all current warnings.
3. Auto-select sole active tests/selection audit. Allocate new token/real instant; update finalized sample.
4. Capture every active test/method/evidence in same transaction after selection; validate/INSERT immutable v2 fact.
5. QUEUE_CURRENT calls unchanged lifecycle seam which reads saved fact and copies report projection. NO_REQUEST makes no queue call/new report row; no fake successful/failed job.
6. Insert FINALIZED event and existing finalization-attempt SUCCESS audit. Safe details contain token/report_policy/adopted+active IDs/confirmed codes, no secrets/storage keys.
7. Commit then existing load response. Already finalized stays409, including retry after unknown response; no second token/job. Public current state/view supports recovery instead of automatic refinalization.

Selection/fact INSERT/queue/event/success-audit/pre-commit DB failure rolls sample/token/selections/fact/report/event/success-audit back together. Preserve separate LaboratoryError failure-attempt behavior; do not claim all technical errors have failure audit or invent success after uncertain COMMIT. Runtime failures use existing safe handler. Inject before-commit DB and last-audit failures/queue failure; observe sample/view/claim/download/current results.

Withdrawal: current-authorize/validate reason/sample FOR UPDATE; OPEN+token NULL, report invalidation and WITHDRAWN event/audit atomically. Never update/delete facts. Missing report is valid no-op invalidation. Stored facts aren't current after token clear. Refinalization makes new token/fact; ordinary default queues; NO_REQUEST never revives old report. Committed withdrawal stops new results/reads. A concurrent in-flight download may complete under existing FOR SHARE serialization, then withdrawal commits and later reads block.

Reports:
- queue_current copies matching saved valid fact; unavailable -> finalization_facts_unavailable/503 aborts whole finalization. Passed warning/time/token must agree; never trigger live rebuild. Keep current upsert/generation reset, v1 snapshot column/current-row identity/no visible report versions.
- Retry keeps saved request snapshot exactly, new generation token/reset metadata under sample then report locks. No live asset/method/test query/rebuild and no missing first request creation.
- Worker claim/complete/fail preserves current sample/finalization/generation/claim matching, lease reclaim/SKIP LOCKED. Claimed v1 before0033 remains renderable. No fact query on completion/file read that would block intact old bytes.
- read_file keeps sample/report share locks through storage read, current token/READY, size/SHA checks. Adapter/config unchanged; delete stale upload only when proven stale. Uncertain COMMIT retains file for existing recovery owner#60.

| Sample/current facts | Current report | Public results | Report/file |
| --- | --- | --- | --- |
| OPEN/historic facts retained | stale | no effective facts | sample_not_finalized/no file |
| FINALIZED valid v2 NO_REQUEST | none/old-token row | effective | report_not_requested/no retry/file |
| FINALIZED valid v1/v2 | QUEUED/GENERATING/FAILED | effective | existing state/no nonREADY file |
| FINALIZED valid v1/v2 | READY intact | effective | original verified bytes |
| FINALIZED corrupt typed fact | READY intact | explicit503 | preserve READY/byte access |
| FINALIZED/ASSOCIATED legal legacy NULL token | no qualifying token/fact | excluded, no point; other current records and global alarms remain readable | view UNAVAILABLE/missing_finalization_token; report refinalization_required |
| FINALIZED/ASSOCIATED nonnull current token, missing/unverifiable fact | no qualifying fact | explicit503 for requested associated asset, no partial success | explicit unavailable/no invented token/fact/job |
| withdrawn/refinalized | old late claim | only new current facts or none | old completion rejected |

## 7. Current public reader and errors

S2 LaboratoryTrendSource reads sample currentness + immutable fact rows, with no report state/file/table join or fallback to reports/live tests/methods. Candidate qualification first requires ASSOCIATED, FINALIZED and s.testing_finalization_token IS NOT NULL. Keep this explicit sample predicate before validating the LEFT JOIN result; do not require the joined fact to exist in SQL, because that would silently drop a qualified nonnull-token missing fact. Within those nonnull-token candidates, LEFT JOIN on sample/current token keeps missing/corrupt facts observable. Requested physical/time filters use frozen fact headers where present; missing-fact candidate discovery alone uses old sample physical/time fields then returns explicit unavailable. Validate the whole qualified nonnull-token candidate set before returning points. NULL-token records never enter that set or its failure dependency.

Qualification: still ASSOCIATED/FINALIZED with a nonnull current token, matching fact token and valid frozen physical/header/typed snapshot. OPEN, identity-pending and NULL-token legacy records yield no effective point. Preserve the old equality-join NULL exclusion: a lawful0006->0007 tokenless record cannot block another valid sample on the same device or global AlarmCenter's batched read. Once a sample has a nonnull current token and belongs to the requested physical/time scope, missing/invalid matching facts -> existing trend_snapshot_unavailable503, never empty/partial success; this repair must not swallow genuine current corruption. start/end remain aware UTC; exact old instants normalized as today; no DATE ordering added.

Single-sample finalization view retains UNAVAILABLE/missing_finalization_token for a tokenless legacy record; this diagnostic is not aggregate source failure. Nonnull-token missing/invalid facts use missing_finalization_facts or invalid_finalization_facts in that view while qualified aggregate reads fail503. The view never repairs/mutates or generates a token. Unknown sample404, absent laboratory.read403; DB/service outage503.

Report status precedence:
1. Unknown404; OPEN sample_not_finalized; FINALIZED NULL token refinalization_required.
2. Matching current report -> existing state. Do not decode fact as condition for READY status/old byte access.
3. No matching report + valid facts -> report_not_requested, even if invalidated older-token row survives NO_REQUEST refinalization.
4. No matching report + unavailable facts -> finalization_facts_unavailable; retain report_not_current for mismatched old row with no current fact. Safe UNAVAILABLE200 read models; DB failure503.
5. Retry no matching FAILED request -> report_retry_not_allowed409. Ordinary HTTP extra report_policy422; no bypass route.

Keep safe errors free of SQL/blob keys/internal exception text. No new hardcoded role or policy remapping.

## 8. Optional metadata and observation compatibility

Append defaults None to FinalizedMeasurement without changing existing positional field order:
- result_origin: LOCAL_LAB | EXTERNAL_LAB | None.
- sampled_at_precision: INSTANT | None.
- measured_at_precision: INSTANT | None.
- sampling_context_verification: VERIFIED | PHYSICAL_IDENTITY_ONLY | None.

Read-extension slots aren't accepted new workbench write fields. v1 and all #51 v2 writers return None because current business records do not explicitly store these source/verification facts. Never infer VERIFIED from dict/path or classify old rows local/external. Preserve exact datetime values. DATE is unsupported here: fabricated DATE metadata/facts fail validation, formal writes still require aware instants. Later date work expands contract with its own semantics.

Add laboratory.public.finalized_measurement_evidence(point)->dict, owner-supplied stable DTO serialization: asdict plus omit exactly these four fields when None. Preserve all preexisting keys/None/UUID/Decimal/datetime semantics. Include nonNone metadata. Do not globally strip None or change shared encode.
- TransformerTrends returns compatible representation; same point/group/qualifier behavior.
- DeviceHealth.assess and AlarmCenter fingerprints/current measurement sets/group sets use same public serializer wherever points are serialized. With absent metadata, retained v1/current evidence/fingerprints remain byte-equivalent, preventing spurious duplicate health evaluations or recovery invalidation.
- NonNone metadata participates in equality/fingerprint/signature. Tests use public protocol adapter wrapping real PG-backed points with explicit synthetic INSTANT/source/verification fields, not formal external/DATE writes. Stable metadata deduplicates; changed metadata changes observation.
- Existing token/sampling_context remain exactly in signatures. No migration/rewrite of health/alarm evidence, no analysis import of private lab tables.


## 9. Minimal coherent slices and allowed files

Two slices are the minimum useful split. One combined pass entangles lawful legacy capture/storage/ordinary compatibility with new public policy/consumer/page changes in one difficult review. More slices by table/backend/frontend/test add gates without independently safe business/risk outcome. Each slice gets one implementation -> independent deepreview/fix/re-review -> controller accepted checkpoint. Do not start S2 before accepted S1.

### S1 — freeze facts safely while ordinary reporting remains

Outcome: new immutable facts/lawful old snapshots survive upgrade; ordinary finalize/report remains atomic; public current-fact view proves complete versus unknown inventory. Existing result source stays report-based until S2. NO_REQUEST isn't exposed yet, avoiding a half-working path.

Prerequisites: accepted plan + parent final CI green, exact base refresh, clean scoped branch, lawful capture before producer edits.
Allowed:
- backend/migrations/versions/0033_lab_finalization_facts.py.
- backend/dga/laboratory/finalization_facts.py (new), workbench.py, reports.py, public.py.
- backend/tests/capture_finalization_legacy.py; backend/tests/fixtures/finalization_legacy/v1/**; backend/tests/finalization_legacy.py loader.
- backend/tests/test_finalization_facts.py and test_finalization_facts_migrations.py (new); bounded test_laboratory_reports.py / test_laboratory_workbench.py / test_laboratory_integration.py updates for public assertions/lawful historical arrangement.
- README.md / CONTEXT.md / PROJECT_PLAN.md narrow increments; docs/adr/0010-finalization-facts-and-report-requests.md documenting incomplete v1 inventory, v2, immutable currentness/ordinary policy; docs/work-units/issue-51-s1.md. No G: writes.

Exact work: capture/provenance checkpoint; genuine missing-fact-view RED;0033/backfill/guard; private capture/validation; public view; ordinary finalize saves fact before queue; Reports projects frozen fact to v1; current authorization/lock order for touched commands; failure/race/old-byte coverage. Keep renderer/worker/provider/report state machine/result source unchanged.

Required assertions:
- All active IDs including unselected warning record, adopted subset/method/value preservation; repeat finalize409. Immutability rejects UPDATE/DELETE at owner DB fault seam and public view unchanged.
- Queue/DB insertion/last event or audit failure -> whole rollback: sample OPEN, no claimable success request/current facts/download/effective adopted result. Later ordinary finalize/claim/READY/file succeeds once.
- Current revoked/disabled actor or absent finalize permission cannot capture; actual analyst grant can; no grant migration.
- Attested0032->0033 nonnull-token legacy corpus same IDs/instants/values/PDF SHA, explicit unknown inventory; malformed classes explicit with byte-read separation. Additional real0006->0007->0032->0033 legal NULL-token fixture must remain unqualified and diagnostic-only, alongside lawful current records; all3 public analysis queries remain available.
- Populated0033 downgrade refuses loss; empty downgrade/re-upgrade succeeds; #50 dynamic-head paths and old branch histories retain intended assertions.
- Existing pinned0024 workbench downgrade test cannot invoke new writer pre0033: replace only its historical finalized arrangement with attested parent-v1 loader; retain0006 branch downgrade -> OPEN -> head public readback. No production schema-detection fallback. Other pinned0024 configuration/operations tests do not finalize and retain old guards.
- S1 ordinary finalize/report browser regression is included in its compatibility validation; S2 owns final new no-request page chain.

C1-S1/ordinary C4 commands below. Completion: artifact records provenance/blob/payload/PDF hashes, actual RED/GREEN, migration paths, fault/public evidence, scoped diff and residual owners. Stop at independent S1 review. No S2 enum/no-request/page/source switch in this pass.

### S2 — no-request effective results across consumers and truthful report state

Outcome: privileged public NO_REQUEST produces effective results with no task through all3 analysis facades; ordinary chain survives; no-request page and old observations remain compatible.

Prerequisite: accepted S1 checkpoint.
Allowed:
- workbench.py/public.py/finalization_facts.py bounded policy/metadata; trends.py; reports.py status classification; existing http.py only if required to preserve explicit extra-field rejection, not a skip endpoint.
- backend/dga/condition_analysis/public.py / health.py / alarms.py / alarm_inputs.py / alarm_state.py only as needed for consistent laboratory public serialization, not policy/recovery algorithm redesign/private lab SQL.
- frontend/src/features/laboratory/ReportPage.tsx and minimal existing report CSS state styling.
- backend/tests/test_finalization_facts.py / test_laboratory_reports.py / test_transformer_trends.py / test_device_health.py / test_alarm_center.py; test_report_storage.py only relevant frozen-byte/request regression; test_architecture.py only actual import constraints.
- backend/tests/seed_finalization_browser.py and finalization_browser_app.py (isolated helpers); frontend/tests/laboratory-reports.spec.ts / laboratory-workbench.spec.ts and new finalization-facts.spec.ts; scoped docs and docs/work-units/issue-51-s2.md.
- No migration rewrite. A newly proved schema defect returns to reviewed0033 work before release with review evidence; no silent unrelated additions.

Exact work: enum policy/default queue/ordinary HTTP strictness; result source entirely immutable current facts; four optional metadata slots + stable public serialization; all consumer signature compatibility; real no-request state/page. Existing labels remain except report_not_requested badge '未请求', message '检测已整体定稿，尚未请求系统报告；有效检测结果不依赖 PDF 生成。'. No withdrawal advice/blank iframe/retry/first-request action there. Invalid facts: '当前定稿资料无法核实，请联系实验室核对。'. Specific single-sample NULL-token legacy correction guidance can remain; it does not imply aggregate current-source failure. No visible token/schema/report version added.

Required RED/GREEN:
- Public NO_REQUEST -> FINALIZED/current fact -> report_not_requested, claim None, retry/file409; real Trends/Health/Alarm consume valid adopted points. All identity/QC/multitest/warnings blockers identical. HTTP extra policy422; normalPOST queues.
- QUEUED/GENERATING/FAILED/file missing never erases valid facts. Removing/changing request at owner fault seam cannot erase valid facts; no result SQL report join remains.
- Withdrawal stops current results/file; NO_REQUEST re-finalize new token/no matching request despite stale row; ordinary re-finalize queues. Old finalization/generation/claim cannot complete after either.
- Real DB races finalize/finalize one success/409; withdrawal versus complete; expired lease reclaim/stale fail/complete; share-locked download; queue/event/audit failure after fact capture.
- Preserve grouping/qualifiers/ties/current-tree aggregate/duplicate serial/replacement isolation; alarm dedup/ack/later-normal recovery/withdrawn recovery/retirement/new token/late tied qualifier. No invented scientific/date semantics.
- Real PG mixed qualification regression: legal0006->0007 FINALIZED/ASSOCIATED NULL-token record and lawful current sample coexist on one transformer, with another lawful current asset included in global alarms. After upgrade the tokenless sample contributes no measurement; TransformerTrends/DeviceHealth/AlarmCenter continue returning lawful current outcomes without503; single-sample view/report diagnostics remain missing_finalization_token/refinalization_required. Separately keep a nonnull-token missing-fact case and malformed-fact case beside lawful current data; each still makes the qualified source fail503 with no partial successful result.
- v1 observation fingerprints/persisted evidence stay unchanged with absent metadata; no duplicate health evidence or invalid old recovery. Explicit synthetic protocol metadata changes signatures; unsupported DATE unavailable.
- Actual browser ordinary finalize -> status -> verified PDF -> withdraw -> re-finalize. Separately seeded public NO_REQUEST -> actual report page '未请求'/no false advice/download -> existing analysis route shows result. No mocked upload/new import page.1920x1080, existing long barcode/safe return navigation/read-failure retry baseline.

Completion: scoped artifact with actual tests/hashes/screenshots/state/error/identity evidence and residual owners. Stop at independent S2 review. Controller next owns aggregate deepreview against fcea999e/fixes/reviews/checkpoints; slice doesn't claim draft-PR-pass/final closeout.

## 10. Failure/legacy matrix and inherited historical tests

| Seam | Observable expected result |
| --- | --- |
| v2 fact/event/audit/queue failure | OPEN rollback; no current view/job/download/point; later legal finalize succeeds |
| NO_REQUEST + blockers/current auth | Same errors/atomicity; no shortcut or report callback |
| Legacy malformed current snapshot | Raw migrated payload retained; typed503, not empty/partial; old READY bytes separately validated |
| Legal legacy NULL token + lawful current samples | No token/fact backfill; old sample produces no point; Trends/Health/global AlarmCenter remain readable; single-sample view missing_finalization_token/report refinalization_required |
| Nonnull current token missing current fact | Qualified missing fact remains503/no partial success; missing PDF request alone never fails a valid fact; no invented token/inventory; valid v1 never forced to refinalize |
| Frozen copy versus mutable current data | Frozen method/value/history, never current source substitution |
| Mutation/post-withdrawal retention | DB guard; token controls currentness; new token preserves old fact without serving it |
| Old claim across upgrade/retry/withdraw | v1 request renderable;3-token guards; uncertain COMMIT retains bytes |
| #50 0013/0030/0031 upgrade to head | OPEN sample/container/asset snapshot/v1 batch/source equal;0033 adds no fake fact |
| #50 safe SITES downgrade-to0031 + retained ASSETS guard | Fixtures have no facts, so empty0033 downgrade reaches intended0032/0031 refusal/message |
| Old config/operation/role/historical cases | Disposable schemas and older forward guards remain; only pre0033 finalize arrangement uses parent producer |
| Actual two-main branch upgrades |0014/0030 joins retained; no stamp/renumber/drop/recreate/user-data downgrade |

All3 new #50 migration test groups are explicit regressions: test_real_historical_upgrade_preserves_v1_states_asset_sample_and_source (0013/0030/0031->head), test_0031_sources_survive_0032_upgrade_and_safe_downgrade (head->0031->older guard->head), test_0032_downgrade_preserves_all_retained_asset_states (empty/STAGED/VALIDATED/FAILED/PUBLISHED). Their older schemas contain no lawful finalized report corpus. A future newer guard may execute before their expected older message: because those fixtures have no facts,0033 must allow empty drop. Never weaken a populated fact guard to make a fixture pass.

Existing test_laboratory_workbench.py:487 starts0024; its new finalize would require0033 table and current-auth columns. Use captured lawful old producer data for that arrangement, not app fallback. test_laboratory_configuration.py:223 and test_laboratory_sample_operations.py:174 only add tests/container operations before their older refusal; no finalize, so leave their intent. test_identity_management.py:277 and test_site_import.py:320/362 dynamically upgrade; identity/site guards still apply when facts empty. test_dual_main_upgrade.py:19 covers0025_site_export_audit/0029_oidc_callback to head with account/site/audit preservation. test_laboratory_integration.py:22 creates0013 sample before head, then exercises current finalize/reports after upgrade. Run all with real migration history.

No private table column order/React structure/private helper-call-count is business success. Owner SQL only arranges attested historic/corrupt states, injects actual DB faults or verifies immutable constraint; outcomes asserted through public view/result/report/bytes/audit. No broad mock analysis replacement.


## 11. Future execution environment and exact validation (NOT RUN in PLAN)

This gate ran no runtime bootstrap, listener mutation, test/migration/browser. All following commands are future implementation instructions after acceptance.

Use new own cluster R/.cache/issue51-tests/pgdata port18551, own API18571/frontend18171 and .cache/issue51-browser. Before use verify ports free and resolved data directory within R. If occupied, choose/record another free own port without stopping its owner. NEVER operate #50 18550/18570/18170 or original18148/18164/18165,18448/18464/18465. No global Docker restart/old cluster reseed/old fixture-memory reset.

Installed runtimes read-only:
- PostgreSQL17: C:/Users/weila/.codex/worktrees/issue-48-site-export/DGA Lab/.cache/issue-48-postgres/pgsql/bin.
- Python: C:/Users/weila/.codex/worktrees/issue-48-dual-main-sync/DGA Lab/.cache/test-venv/Scripts/python.exe.
- Node: C:/Program Files/nodejs/node.exe. Own pinned frontend lockfile/node_modules; npm ci only if needed in new checkout, no upgrades.

Native bootstrap future: initdb only new verified own path, role issue51_admin, UTF8. Hidden Start-Process pg_ctl start -D ownpath -l ownlog -o '-p 18551 -h 127.0.0.1' -w; wait ONLY pg_ctl via WaitForExit(60000), never Start-Process -Wait over descendant tree. Verify PID/listener/postmaster path/ready/lifetime. New dga_test LOGIN CREATEDB and owned dga_test DB only in that cluster. Do not copy old pgdata. Store commands/logs in own ignored .cache, no secrets. Before capture/migration assert connection's actual port/role/database matches this owned instance; logical URL host guard alone does not distinguish old18550.

From R/backend:
    $python='C:/Users/weila/.codex/worktrees/issue-48-dual-main-sync/DGA Lab/.cache/test-venv/Scripts/python.exe'
    $env:TEST_DATABASE_URL='postgresql+psycopg://dga_test@test-db:18551/dga_test'
    $env:DATABASE_URL=$env:TEST_DATABASE_URL
    $env:PGHOSTADDR='127.0.0.1'
    $env:PYTHONPATH='C:/Users/weila/.codex/worktrees/issue-51-finalization-facts/DGA Lab/backend'
    $env:PYTHONUTF8='1'
    $env:PYTHONDONTWRITEBYTECODE='1'

Don't repurpose HOME/CODEX_HOME. conftest keeps logical test-db/dga_test/dga_test restriction and real Alembic head; historical cases get disposable unique schemas, no shared test DB parallel runs. Preserve exit codes/logs.

Capture first (helper added BEFORE producer/migration edits; helper verifies exact base source):
    & $python -m tests.capture_finalization_legacy --expected-parent fcea999e313db51461cd9aefda66d70e6e34ed3b --output tests/fixtures/finalization_legacy/v1
Expected legal parent outputs/manifest/blob/JSON/PDF hashes/public observations. Capture isn't a general test-pass claim. Log checkpoint before publisher edits.

C1-S1:
    & $python -m pytest -q -rs -p no:cacheprovider tests/test_finalization_facts.py tests/test_finalization_facts_migrations.py tests/test_laboratory_workbench.py tests/test_laboratory_reports.py tests/test_laboratory_configuration.py tests/test_laboratory_integration.py tests/test_device_material_import_migrations.py tests/test_site_import.py tests/test_dual_main_upgrade.py tests/test_identity_management.py tests/test_architecture.py
Expected missing-view genuine RED then actual PG GREEN: complete/unknown inventories, rollback/legacy/bytes/lineage/current grants, legal0006->0007 NULL-token preservation alongside lawful current data. No blanket skip of a failed historical case.

C1-S2:
    & $python -m pytest -q -rs -p no:cacheprovider tests/test_finalization_facts.py tests/test_finalization_facts_migrations.py tests/test_laboratory_reports.py tests/test_transformer_trends.py tests/test_device_health.py tests/test_alarm_center.py tests/test_laboratory_sample_operations.py tests/test_architecture.py
Expected public no-request/three consumers/stable signatures/withdrawal/late-worker genuine RED->GREEN. Mixed legal NULL-token/current records must preserve all3 query availability and single-sample diagnostics; distinct nonnull missing/bad-fact cases still fail503/no partial success.

C2 from R/frontend:
    npm.cmd run build
Expected tsc --noEmit + Vite success, no new frontend test framework/weakening types.

C3 final whole backend, once after completed production changes; repeat only for justified changes/failures:
    & $python -m pytest -q -rs -p no:cacheprovider
Record totals/duration/exact source/skip owners. Native may skip existing40 configured MinIO/Azurite cases; never call that real configured-storage acceptance. Classify existing deprecation/intentional duplicate-ZIP warnings.

Configured storage canonical alternative/final CI from R:
    docker compose -p dga-issue51 -f compose.yaml -f compose.storage-test.yaml --profile test run --build --rm api-test
Focused container C1 explicitly overrides service command with: api-test pytest -q -rs -p no:cacheprovider <named test files>.
Current .github/workflows/ci.yml runs storage overlay: final exact-head CI must execute storage contracts, not just skip. Only a new own compose project if Docker available; never restart another project. Controller owns remote exact-head CI before PR acceptance.

CI duration risk is explicit: controller observed the parent Sungrow job nearly the current20-minute timeout (backend418.59s/browser4.3m/deploy-start6m23 plus build/cleanup). New #51 cases may exceed the budget. This plan chooses NO speculative CI edit and no skipped/sharded unsafe DB tests. Record full exact-head job timing; if a legitimate full job times out, controller opens a finite reviewed validation fix to .github/workflows/ci.yml changing ONLY timeout-minutes20->30, retaining every build/migration/backend/storage/browser/log/cleanup step and real assertions. It requires observed timeout/timing evidence, independent review and rerun of the same complete job; not permission for an implementation agent to silently edit CI. Budget failure remains a current-unit acceptance obligation, never a fake pass.


C4 own browser:
1. New own dga_browser role/database on18551, logical db hostname + PGHOSTADDR127.0.0.1. Existing guarded tests.seed_browser targets only own DB.
2. Own fixture finalization_browser_app uses unchanged create_app(file_store=existing fixture Files) plus real ReportWorker sharing that store, as current fixture pattern. API18571, built frontend preview18171 with own ignored proxy config. Hidden processes verified by exact path/PID; no termination by generic name/port. This is fixture storage, not a production provider.
3. Run ordinary linked flow first. Then tests.seed_finalization_browser seeds one own no-request sample with public SampleRegistry/Workbench NO_REQUEST; no files/external import. New frontend/tests/finalization-facts.spec.ts queries actual status and existing analysis route; no mocked no-request response.
4. BASE_URL=http://127.0.0.1:18171 and BROWSER_CHANNEL=chrome, from frontend:
    & 'C:/Program Files/nodejs/node.exe' node_modules/@playwright/test/cli.js test tests/laboratory-reports.spec.ts tests/laboratory-workbench.spec.ts tests/finalization-facts.spec.ts tests/transformer-trends.spec.ts tests/alarm-center.spec.ts --output ../.cache/issue51-browser/key
   S1 before new spec exists uses only tests/laboratory-reports.spec.ts tests/laboratory-workbench.spec.ts. S2 runs fixed full key selection above.
5. Finish all linked scenarios before any own baseline reset. Full browser once after completed changes: restore ONLY own seeded baseline after key chains; run existing whole suite. Preserve screenshots1920x1080/download SHA/current source fingerprints.
6. Standard browser CI compose.browser.yaml + compose.import-browser.yaml does not include compose.oidc-test.yaml. Existing OIDC_PROTOCOL_FIXTURE=1 skip is not closed by ordinary green/native CI. Optional protocol/real Okta acceptance owner#18; don't change CI to remove intentional baseline skip.

C0 checkpoint verification: branch/status, git diff --check, actual head0033/import architecture/scoped files/fixture and source hashes/run fingerprints. No stage/commit/push/PR by slice agent without separate controller dispatch.

## 12. Docs, residuals and completion/handoff

Update current checkout README/CONTEXT/PROJECT_PLAN narrowly: current effective facts versus optional PDF; default ordinary queue; incomplete legacy inventory/errors; internal snapshot versions; unchanged analyst grant; forward recovery. ADR0010 supplements accepted original ADR0009 without copying dirty original docs. Keep unrelated old domain passages separately owned; no full rewrite or delivered external/manual summary claim.

| Risk/uncovered area | Classification/owner |
| --- | --- |
| Parent #50 exact-head CI/base | Resolved at fcea999e by controller; any future parent change requires controller revalidation before acceptance |
| Lawful corpus/atomic faults/corrupt typed versus intact bytes, legal NULL-token mixed-record qualification | Fixed in S1/S2 now, not deferred#61; diagnostic-only legacy absence versus nonnull current corruption remains explicit |
| Complete v2 versus unknown v1/envelope consistency | Fixed S1 with explicit unknown/invalid classes |
| Optional metadata/retained observation signatures | Fixed S2, persisted dedup/recovery proof |
| Configured storage40/exact-head CI and20-minute budget | Current unit/controller; native skips not acceptance; observed timeout requires finite reviewed budget fix with all checks retained |
| Real Azure/deployment and corporate Okta/optional overlay | Existing deployment/#18; credentials/provider unchanged, fixture not acceptance |
| Manual first summary/formal imports/DATE/original PDFs | Later existing approved bulk-import work#53+; no partial upload/summary here |
| Broad cancellation/lease/orphan/uncertain storage-COMMIT platform | Existing#60; preserve initial-write atomicity/stale guards now |
| Combined-chain/load/inherited context-depth20 versus graph100 | Existing#61/#53 formal lab import; no new regression fix here |
| Scientific ASTM/compatibility/thresholds/branding | Existing business/configuration owners, isolated TEST values only |
| Newly proved material blocker | needs-more-evidence/controller adjudication; no silent deferral/new scope/fake pass |

Each slice artifact must include exact branch/base/head/diff; changed interfaces/files; capture provenance/version/blob/JSON/PDF hashes; actual RED/GREEN commands/logs/totals/skips; real PG migration/failure/race/public observations; browser hashes/screenshots/downloads if run; docs; findings states; every residual classified/owned; exact next independent review gate. Do not substitute older fingerprints for latest changes.

After S2 controller owns aggregate fcea999e..current deepreview/fix/re-review/accepted checkpoint, push/draft PR, independent PR review/fix/re-review/final push and exact-head CI. PR remains draft/unmerged, preceding branch base and correct #51 link. External closeout comments lack authorization: prepare exact batch comment and retain final-closeout-pending, not false closeout pass. No #52 implementation from this plan.

This PLAN gate wrote only issue-51-plan.md and issue-51-goal-confirmation.md. Validation here: read-only source/domain/git inspection only. All tests/runtime/migration/browser commands above are future and NOT RUN. No blocking product/architecture question remains; independent planreview may challenge these concrete decisions. Parent exact-head CI green is controller-provided evidence, not a test run by this PLAN agent. Stop at that handoff, with no commit/implementation/controller change/plan-pass claim.





