# Issue #17 goal confirmation — approved

User confirmed the proposed business scope with “是的”. Proceed through local plan, TDD and reviews; no push/merge. Confirmation permission includes Asset Manager as the issue's primary operator, alongside the listed operational roles; management_readonly remains read-only.

## Preflight / evidence

- User requests Gateflow, first business-goal confirmation, then plan/TDD/reviews; no push, merge or subsequent Issue.
- Latest fetched main: 15c36e61a87ea4c370b18a26bd76f82e275cfe37 (Issue16 PR37 merged).
- Isolated worktree .worktrees/issue-17-alarm-lifecycle, branch codex/issue-17-alarm-lifecycle created under explicit user authorization. Original dirty main, other worktrees and acceptance services/data untouched.
- Read Issue17 (OPEN), root CONTEXT, ADR0001/0004/0005 and product alarm requirements. More recent approved Issue16 decisions govern current health; older root docs are not silently rewritten.
- Existing condition_analysis/health.py DeviceHealth.query produces current latest finalized selected results, exact method/unit rules, current subtree and immutable evaluations. It has no persistent alarm lifecycle. LaboratoryTrendSource exposes current finalized snapshots through public APIs. Frontend analysis/pages.ts declares alarms route but main has no implemented alarm center. This work unit is needed to add acknowledgement and recovery history, not rebuild health evaluation.

## Proposed goal / success

AM and authorized staff see current/history alarms, acknowledge awareness without clearing abnormal health, inspect source and immutable timeline, and recover only from qualifying later normal evidence on the same physical device. Lists and asset red-entry counts share an analysis-owned projection and consistent scope. No direct cross-module table writes/reads; facts from asset/lab public interfaces.

## Proposed business decisions requiring user confirmation

1. Lifecycle UNACKNOWLEDGED -> ACKNOWLEDGED -> RESOLVED; normal evidence may also resolve an unacknowledged alarm. Acknowledgement records authenticated actor/time/required note, never changes severity. Resolved then genuinely later abnormal sampling opens a new episode. No hard deletion or manual force-normal.
2. One open episode per physical asset UUID + test type + analyte. Repeated evaluations, refreshes, parents and duplicate sequence numbers cannot duplicate alarms. Further abnormal evidence updates the episode timeline without clearing its acknowledgement; source/severity/rule changes remain auditable.
3. Recovery needs strictly later sampled_at than the episode's latest abnormal evidence, current finalized selected EQ results, exact same method-version/unit as that abnormal evidence, applicable active current rules and normal outcome. All tied latest evidence must be assessable normal; tied unknown/mismatch/abnormal blocks recovery. No old normal fallback, same-sample edit, relaxed rule alone or cross-method compatibility inference can recover an episode.
4. Rule retirement/expiry/change is not proof of recovery. Retain unresolved episode with reason (e.g. no applicable rule); current health still follows Issue16 and may be UNASSESSED or NORMAL under current policy. UI distinguishes current health from unresolved historical abnormal evidence; red alarm-entry count counts unresolved episodes, not the number of red health attributes.
5. Withdrawn triggering evidence remains historical and flagged no longer currently finalized, never silently cleared as normal. Withdrawal of recovery evidence invalidates that recovery in an appended correction event; restore the unresolved episode unless other eligible current later normal evidence proves recovery. Preserve original acknowledgement/recovery history and avoid two open episodes for one key. Re-finalization/correction rechecks actual current evidence, not a cached success.
6. Equipment change/move never closes the old physical transformer's alarm; current ancestors and location count only current installed descendants. New transformer's normal cannot clear old transformer's episode. Original trigger sampling snapshot retained separately from current location (repair center included).
7. Current list/count filters use current asset product line/site/customer/physical asset, type/analyte/severity/status and alarm occurrence dates; history retains trigger sampling context and labels it separately. Counts deduplicate physical episodes, same filters/snapshot scope as list; own and descendant contributions distinguishable.
8. Minimal confirmation permission separate from threshold-rule write permission; proposed system administrator, laboratory administrator/analyst and field engineer may acknowledge consistent with existing product role guidance. View-only users remain read-only; no new role-management UI. Exact existing role IDs and migration reviewed in plan.
9. MVP refresh follows Issue16 read-through: refresh on entering/reloading alarm center and asset views; show checked time, explicit failure, no silent old-success fallback. No always-on notification SLA, historical replay of every past evaluation, event bus or new service. Initial reconciliation evaluates current eligible evidence, not fabricated historical alarm occurrence times.

## Scope / non-goals / risk ownership

Included: current/history filtered lists, details and timeline, acknowledgement, evidence-based recovery/correction, consistent dashboard/device entry counts, public-interface real PostgreSQL tests and critical browser journeys.

Excluded: formal thresholds, ASTM compatibility guesses, service/repair orders, notification escalation, SLA, manual normal override, microservices. Test rules isolated only.

Scientific configuration remains authorized maintainer responsibility; global atomic cross-module snapshots and production load certification are not claimed. Rule/evidence invalidation and role/refresh scope above require explicit goal approval before plan. No implementation or migrations yet.

Next entry after approval: plan. No production edits occurred before approval.
