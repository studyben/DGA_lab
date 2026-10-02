# Issue17 S3

- Gate: implementation / code review / fix / re-review accepted.
- Files: analysis-owned alarm page/API/widgets/CSS, thin portal/dashboard/equipment wiring, browser tests.
- Behavior: URL-backed current/history filtering, pagination/counts, detail/source/timeline, required confirmation note and RBAC, historical severity labels, current location vs sampling snapshot, return context, polling with abort/timeout and no stale success on errors.
- Scope note: dashboard alarm badge explicitly uses product line/current site/customer only, not dashboard location/status filters; linked list receives the exact same supported filter set.
- TDD: first browser flow RED missing equipment alarm link, GREEN complete warning->ack->normal->history; readonly link regression RED then GREEN.
- Validation: fresh full browser37, final targeted2 after fixes, tsc/Vite passed; full PostgreSQL269; screenshot geometry1280/1920 checked and images viewed.
- Review artifact: docs/reviews/code-review-20260918-023502.md. Findings accepted/已修复. No blocker.
- Local isolated browser18117 uses only synthetic test thresholds. Existing18108 and original workspace/data not changed.
- Residual risks: final aggregate gate still required; load certification belongs deployment stage.
- Current gate / next entry point: aggregate deepreview. Do not push/merge.
