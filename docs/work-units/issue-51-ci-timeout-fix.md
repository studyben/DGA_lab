# Issue #51 PR CI finite timeout fix

Gate: PR CI FINITE FIX implementation COMPLETE; independent fix re-review and new-head GREEN remain pending. No PR/final-closeout pass is claimed.

Workspace R=C:/Users/weila/.codex/worktrees/issue-51-finalization-facts/DGA Lab. Branch codex/issue-51-finalization-facts, HEAD077806b6cdcb67821de90982b3d7c6c334d567e0 unchanged. PR66 remains draft with#50 stack base. Controller-owned untracked issue-51-closeout-comment.md and issue-51-final-closeout.md were preserved and not edited/staged. No commit/push/comment/ready/merge or next gate.

## Authority and observed RED

The accepted issue-51-plan.md:295 explicitly anticipates a real full-job timeout and permits a finite reviewed timeout-minutes20→30 change while preserving every check. Controller accepted this observed PR CI finding and dispatched only the one scalar and this artifact. This is no longer a speculative CI budget change.

Applied diagnosing-bugs after reading its full SKILL.md, current CONTEXT.md, relevant accepted plan/S2 validation ownership, ADR0010 and actual workflow. Existing GitHub final077 runs PR40989669058/push40989663104 were reported by controller SUCCESS:684 configured-provider backend cases,6 warnings323.68s and78 browser passes/1 intentional OIDC skip. That is controller-provided existing-head evidence, not a rerun by this fix agent or proof for the forthcoming changed head.

Actual Sungrow enterprise run312535641/check1723452531 is at the SAME077806b6 head, completed/cancelled. Controller first ran the annotation command below and observed the exact deadline diagnostic. This agent independently re-ran the command, then read bounded run/job metadata and the smallest useful job-log signals. Run URL: https://sungrow-usa.ghe.com/sungrow-usa-internal/dga-lms/actions/runs/312535641.

Read-only CLI feedback (existing authenticated gh, no token/header/env output):

    & 'G:/Sungrow Develop/DGA Lab/.tools/gh/bin/gh.exe' api --hostname sungrow-usa.ghe.com repos/sungrow-usa-internal/dga-lms/check-runs/1723452531/annotations

Actual failure annotation:

    The job has exceeded the maximum execution time of 20m0s
    The operation was canceled.

This is the direct runner reason, not a guess from the word cancelled. The separate checkout Node.js20 deprecation warning is unrelated and remains untouched.

Additional actual read-only feedback commands:

    gh api --hostname sungrow-usa.ghe.com repos/sungrow-usa-internal/dga-lms/actions/runs/312535641 --jq '{id,status,conclusion,head_sha,head_branch,event,run_started_at,updated_at,html_url}'
    gh api --hostname sungrow-usa.ghe.com repos/sungrow-usa-internal/dga-lms/actions/runs/312535641/jobs --jq '.jobs[]|{id,name,status,conclusion,started_at,completed_at,check_run_url,steps}'
    gh api --allow-escape-sequences --hostname sungrow-usa.ghe.com repos/sungrow-usa-internal/dga-lms/actions/jobs/1723452531/logs

The final log command was captured in memory, narrowed to summary/error/runner-loss signal patterns, stripped of terminal controls, and only the selected lines were printed/saved. A first invocation without --allow-escape-sequences was safely refused by gh because the response contains terminal escapes; it yielded no diagnostic output or source change. No complete job log, auth header or secret was printed or saved.

Actual selected log signals:

    2026-10-30T02:20:55.4372224Z 684 passed, 6 warnings in 488.03s (0:08:08)
    2026-10-30T02:25:58.9700248Z ##[error]The operation was canceled.

These enterprise runtime488.03s/backend step8m26s values are distinct from controller-reported GitHub runtime323.68s. They are not mixed into a single result.

| Enterprise verify step | Actual UTC interval | Result / duration |
| --- | --- | --- |
| Job |02:05:46→02:26:26 |cancelled;20m40 including always cleanup/post actions |
| Deployable portal/migrate PostgreSQL |02:05:51→02:12:30 |success;6m39 |
| Public PG/MinIO/Azure emulator interfaces |02:12:30→02:20:56 |success;8m26; actual684 pass/6 warnings |
| Browser production build/acceptance |02:20:56→02:25:58 |cancelled;5m02, no completed browser-success claim |
| Service logs |02:25:58→02:26:00 |success |
| Stop runner containers |02:26:00→02:26:23 |success |
| Checkout post / complete job |02:26:23→02:26:24 |success |

Runner was still processing logs/cleanup after the cancellation, rather than becoming unreachable. The explicit maximum-execution annotation identifies the deadline; the generic operation-cancelled annotation alone would not distinguish manual cancellation. Deploy/backend concluded success, the interrupted browser step concluded cancelled rather than assertion failure, and the bounded log signal has no failed-test summary. This establishes the proximate cause of this run's cancellation; it does not prove all interrupted browser tests would pass if allowed to finish. Only the forthcoming complete exact-head CI can establish that GREEN.

Own diagnostic cache, retained for review:
- .cache/issue51-ci-timeout/ghe-1723452531-annotations.json
- ghe-312535641-run.json and ghe-312535641-jobs.json
- ghe-1723452531-log-signals.txt
- ci-before.yml and one-variable-diff-proof.json

## Diagnosing-bugs phases and justified omissions

Phase1/2 feedback is the actual failed CI/check annotation plus run/job metadata above. Both controller and this agent observed the same deterministic old-run RED. The minimized signal is the one annotation identifying20m0s; full product setup and a second20-minute old-head execution are unnecessary and prohibited by this finite dispatch. The old run is immutable: querying its annotations after editing local YAML cannot turn that old result green. The end-to-end feedback loop must use the reviewed/new pushed head and its new run/check IDs; controller owns triggering and consuming that loop.

Phase3 multi-hypothesis generation and Phase4 product instrumentation/bisection are intentionally omitted: there is direct runner deadline evidence and successful post-cancel cleanup. Inventing3–5 competing hypotheses after that causal feedback adds no diagnostic value. No debug source logs, provider change, credentials, runtime/Docker operation or local product performance probe is needed. This is a cumulative job budget repair, not a claim to optimize product execution.

Phase5 correct regression seam is the unchanged complete remote workflow on the actual runners. A local test asserting YAML says30 would mirror the implementation and cannot reproduce the20-minute runner deadline. No such fake test or duplicate684/backend/browser run was added. The one-byte proof below is scope verification only, not GREEN.

Phase6 contains no added debug instrumentation/prototype to remove. Diagnostic evidence stays in its clearly named ignored cache. The skill's original-loop/regression-GREEN criterion remains explicitly pending the new-head remote runs; this finite implementation completion does not bypass it.

## One-variable change and verification

Only .github/workflows/ci.yml:11 changes:

    -    timeout-minutes: 20
    +    timeout-minutes: 30

The byte-preserving edit was compared against the captured pre-edit workflow. Exactly one byte changed (2→3), length and line endings stayed equal, and every other byte is identical. SHA256 of this Windows checkout file:

- before ec1b0d98160623fddd8295c1dd19c03b689fc66b7ca29e1244c3a2929e063bb1
- after35d647a5f3c2452840b759eeaa35153fd67230c1eefcc72ec52ea4e39c36474b

These are file byte hashes, not Git blob IDs and not a functional CI pass. git diff shows one line removed/one added; git diff --check passes. No trigger/permissions/runner/checkout version/provider/dependency/command/step/condition/assertion changes, no concurrency addition, no skip/sharding/retry workaround. Both always() log and container cleanup conditions remain byte-identical. Node checkout warning is deliberately outside this repair.

Only production configuration edit: the timeout scalar. Only new repository document authored here: this artifact. No application, tests, seeds, migration, other docs, retained runtime/data or controller file was modified. No old077 CI re-run was requested. No global Docker/new credentials/paid provider was started.

## GREEN obligation and residual owners

Current finite fix implementation COMPLETE. No blocking product question requires human interview. Stop for independent PR-fix re-review, then controller accepted commit/push to both hosts and complete CI on the exact new head. Required GREEN is both hosts' full unchanged deploy/migration/configured PostgreSQL/MinIO/Azurite backend/browser/log/cleanup workflow, including configured684 current tests rather than native40 skips. Existing intentional OIDC skip remains its defined baseline; real Azure/corporate Okta remain deployment/#18 acceptance. If the full new-head job exceeds30minutes or exposes any assertion failure, it is a new current-unit validation finding and must not be relabeled success or solved by skipping checks. Independent PR/final closeout and draft status remain controller-owned;#52 PLAN and#53+/#60/#61 residual boundaries are untouched.
