# Issue #7 — goal confirmation

User confirmed the following goal on 2026-09-10.

- Implement Issue #7 on an isolated stacked branch `codex/issue-7-finalization`, based on `origin/codex/issue-6-test-entry` (Draft PR #26), without touching the dirty root `main` worktree.
- Treat one barcode as one whole testing lifecycle. Keep the persisted/internal states `OPEN` and `FINALIZED`; present them as “检测中” and “已定稿”.
- Allow one report result selection per test type. A sole active result is selected automatically during finalization; multiple active results require an explicit selection.
- Finalization requires associated official-asset identity, at least one active valid test, and a complete report-result selection for every represented test type.
- Finalization locks sample basics, active tests, and report-result selections. A user with `laboratory.finalize` may withdraw finalization only with a reason, restoring editability.
- Audit report-selection changes, successful finalization, failed finalization validation, and withdrawal. Serialize finalization and competing writes with a sample row lock.
- Expose a minimal warning-confirmation shape for later QA/QC integration, but do not invent formal warning rules in Issue #7.

Success is demonstrated primarily through the laboratory public application interface against a real migrated PostgreSQL test database, including concurrency. Browser acceptance covers two DGA results, report-result selection, overall finalization, read-only state, and reasoned withdrawal.

Out of scope: report/PDF generation, report versions, per-test finalization, formal QA/QC rules, calibration/configuration administration, ASTM method details, and changes to asset-management or condition-analysis ownership.
