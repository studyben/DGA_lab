# Issue17 S2

- Gate: implementation / code review / fix / re-review accepted.
- Scope: alarm_state, alarm_query, alarm_http, AlarmCenter, public exports, main composition, tests/test_alarm_center.py.
- Decisions: recovery requires strictly later complete normal group and exact baseline method/unit. Source-group change (including new tied result or re-finalization token) invalidates retained recovery; rule-only retirement does not. Reconcile all invalidations before recovery. Preserve greatest observed abnormal baseline when consolidating.
- RED/GREEN: later normal; later abnormal baseline; recovery withdrawal; consolidation; rule reinterpretation dedup; explicit reason/validity; query filters; HTTP session and CSRF. Review regressions reproduced all three findings before fixes.
- Validation: final alarm suite 24 passed, earlier full suite 267 passed; isolated dga-issue17-test only. Original worktree and acceptance data untouched.
- Review/fix artifact: docs/reviews/code-review-20260918-022104.md; findings all accepted/已修复, no deferred blocker.
- Docs decision: work-unit and review artifacts only; don't overwrite original untracked domain docs.
- Residual risks: frontend, browser, final regression covered by S3/aggregate; production load certification assigned deployment stage.
- Current gate / next entry point: implementation S3.
