# Issue #15 goal confirmation — confirmed

Branch codex/issue-15-transformer-trends in independent worktree, base latest origin/main feab0f2e1ade0e7528738759fd77b15bfe5152ff. Root main remains dirty and untouched; no acceptance containers/database changed. No push/merge/later issue authorized.

Sources: GitHub #15 and parent #1; root working CONTEXT.md and docs/adr0002–0004; docs/product/design-ai-brief.md section5.9. Root domain docs are uncommitted and fuller than main's tracked CONTEXT; preserve and use as design constraints, do not overwrite or copy unrelated root edits into implementation.

Evidence: condition_analysis/public.py currently exposes access_context only. Laboratory SampleRegistry and LaboratoryWorkbench own samples, typed measurements, methods and finalization. Existing laboratory asset history returns summaries, not a trend measurement contract. AssetDirectory exposes equipment_detail and sampling context; analysis must consume public typed projections rather than read their private tables.

Goal: per physical transformer UUID, show finalized chosen report measurements, comparability exclusions and descriptive trend statistics; navigate from equipment and retain return context. No threshold/health/alarm/forecast or ASTM equivalence inference.

Proposed decisions for confirmation:

1. Group by physical UUID + type + analyte + exact configured unit + method-version ID. Different versions remain separate initially, even if ASTM text matches; no cross-version equivalence guessed. Missing unit or placeholder/unconfirmed method remains visible but excluded from comparable statistics. No unit conversion.
2. Use sampling timestamps, UTC elapsed-time arithmetic, America/Chicago display/date filters. Statistics cover selected date range and selected comparable group only.
3. Latest observed result displayed including qualifier; if non-EQ, keep visible and show latest numeric result separately rather than relabeling an older EQ as current. ND/LT/GT remain marked and excluded from arithmetic; never zero/half-limit substitution.
4. Min/max/arithmetic mean over EQ points; adjacent delta between consecutive EQ points. Annualized absolute change = delta / elapsed days *365.25, unit/year, not percentage or forecast.
5. Trailing three-point mean over three consecutive EQ points (at least3); ordinary least squares against elapsed time (at least2 distinct timestamps), slope unit/year. No interpolation.
6. Equal-time points retained and deterministically ordered; no rate for zero elapsed time. Insufficient data shows explicit reason, not zero. No automatic averaging of repeated samples.

Testing seam: public analysis queries through real PostgreSQL and owning-module public contracts; minimal browser navigation/filter/comparability acceptance. Implementation plan and final interface shapes deferred until these goals/statistical decisions are confirmed.

User confirmed all proposed goals and statistical rules on 2026-09-13. Current gate / next entry: plan. Placeholder is the built-in MVP-PLACEHOLDER method; laboratory-managed configuration with an omitted ASTM reference is NOT automatically unconfirmed. No new scientific approval process or cross-version compatibility editor is in scope.
