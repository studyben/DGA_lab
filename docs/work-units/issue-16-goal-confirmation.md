# Issue #16 goal confirmation — approved

User confirmed the proposed scope and seven business decisions with “是”. Proceed locally through plan/TDD/review; no push or merge.

## Preflight and evidence

- Branch: codex/issue-16-health-rules; separate worktree .worktrees/issue-16-health-rules.
- Base: latest fetched origin/main 9f7ab5913e1d341d972c8d5c5589ea6713251f8d (PR #36 merged). Issue #15 dependency CLOSED; Issue #16 open, no comments.
- Original root remains dirty main with CONTEXT.md/PROJECT_PLAN.md edits and untracked tools/docs/frontend; preserved. No acceptance database/container changes.
- Read Issue #16, root CONTEXT, ADR-0004/0005, current analysis public query and laboratory snapshot source. assets/public.py equipment_detail currently returns hardcoded UNASSESSED; laboratory/trends.py supplies current-finalization selected snapshot projections. No rule lifecycle/evaluation store implemented yet.
- Existing module ownership: assets owns identity and current installation tree; laboratory owns finalized selected measurements; analysis owns rules, evaluations and aggregated health. Extend public interfaces as needed, no cross-module private-table access or reverse dependency.

## Proposed goal and success signal

Authorized staff can create/enable/retire versioned rules and trace current device health to physical source devices, finalized results, rule version and evaluation time. A child warning appears on its current ancestors without duplicated ancestor source alarms. No suitable rule/result means UNASSESSED, never invented normal.

## Proposed business decisions requiring confirmation

1. Lifecycle: editable DRAFT → ACTIVE after explicit authorized approval confirmation, recording approver/time/reason → RETIRED. Active/retired content immutable; changes copy to a new draft. Small-team MVP allows the authorized author to approve their own draft; no multi-person workflow. No hard deletion.
2. Rule scope: explicit test type, analyte, exact method-version UUID, exact unit, optional asset applicability, effective start/end instants and priority. No cross-version equivalence or unit conversion. Higher priority wins within one target; reject ambiguous equal-priority overlaps rather than arbitrary selection. Rules explicitly configure direction/bounds and severity; no scientific default values.
3. Current result: per physical asset/type/analyte take latest sampled current finalized selected result(s), not latest entry date. Never fall back to older normal/numeric/method-compatible results when latest is unassessable. If multiple samples tie at latest time, keep evidence for all; worst known severity wins, and disclose unassessable tied sources.
4. Only EQ receives numeric threshold judgement. ND/LT/GT, missing configuration/unit or method mismatch remain visible but UNASSESSED with reasons. No qualifier-to-zero substitution.
5. Rule time: current health uses rules active and effective at evaluation time against the latest available sampled result. Rule activation/retirement and source finalization/withdrawal trigger refreshed current evaluation; store new immutable evidence, never overwrite prior assessments. A current-rule reinterpretation of an older sample is disclosed, not represented as a historical evaluation.
6. Health: NORMAL/ATTENTION/WARNING/CRITICAL/UNASSESSED. Worst known abnormal result wins; mixed evaluated and unassessed evidence retains a visible incomplete-coverage indication. Normal means assessed applicable items did not trigger a rule, not certification of whole equipment. No evaluable item → UNASSESSED. No trend-rate/staleness prediction.
7. Aggregation: use current effective tree; propagate worst abnormal status to all current ancestors with source links, no duplicated source alerts. Removed child no longer affects former parent; physical child retains its evidence. Parent own and descendant health displayed separately; unknown portions disclosed rather than all-clear.

## Scope and exclusions

- Included: minimal rules page, permission/audit enforcement, immutable assessment evidence, device own/aggregate health presentation above attributes and source explanation; public-interface PostgreSQL tests, minimal critical browser acceptance.
- Excluded: Issue #17 current/history alarm lists, acknowledgement/closure workflow; production threshold seeding, ASTM guesses, automatic advice, notifications, service orders, generic rule language, microservices/message bus. Synthetic thresholds only isolated test fixtures.
- Detailed contracts/migrations/refresh mechanism and slices are deferred to plan after this goal approval, not invented during confirmation.
- Current gate / next entry: goal confirmation. No production edits, plan acceptance, push or merge yet.
