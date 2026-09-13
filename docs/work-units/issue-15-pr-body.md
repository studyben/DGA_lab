## Summary

Closes #15

- Add physical-transformer trends through assets/laboratory public interfaces; consume only current finalized selected report snapshots.
- Separate exact method-version/unit groups; disclose exclusions, preserve ND/LT/GT without numeric substitution.
- Add descriptive statistics, sampling-time chart, filters, result sources and equipment return navigation.
- No migration, scientific compatibility guesses, formal thresholds or subsequent issue implementation.

## Validation

- Real PostgreSQL full backend suite: 212 passed (including 22 trend tests).
- Production-build browser suite: 32 passed; TypeScript/Vite build passed; 1920/1280 desktop geometry checked.
- Migration head remains 0018_lab_packages. Initial browser setup missed the existing import-worker override; corrected CI-equivalent composition passed all tests, without business-code changes.
- Local aggregate deepreview passed; accepted findings fixed and re-reviewed. User reports basic manual acceptance complete with no issues.

## Boundaries and remaining gates

- Exact physical asset UUID; exact method version and unit only. Blank ASTM reference alone does not exclude configured methods.
- Statistics use EQ values only and actual elapsed sampling time. No health judgement or predictive claims.
- Original workspace edits and acceptance data preserved; isolated worktree and test environments.
- Draft only; no merge authorized. PR review evidence will be committed after review; hosted CI must be checked against the latest head.
- Capacity/load validation and formal scientific configuration remain separately authorized work, owned by project maintainer.

See docs/work-units/issue-15-plan.md and docs/reviews/code-review-20260913-122147.md.
