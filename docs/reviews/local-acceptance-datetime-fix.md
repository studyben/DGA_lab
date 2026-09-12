# Local acceptance: lifecycle datetime input

## Final publication validation

User authorized push and merge. Standards review: zero documented violations, one nonblocking suggestion to extract the internal equipment picker (deferred maintenance within assets). Spec review: one P2 keyboard visibility finding, fixed and re-reviewed. The list now scrolls its own viewport to keep the active option visible without moving page/input focus.

Red: the last-option visibility assertion failed (expected true, received false). Green: all 17 browser tests passed with this assertion; all 70 backend tests passed against isolated PostgreSQL (two existing deprecation warnings). TypeScript/Vite build and diff whitespace check passed. Earlier narrow-test limitations below are superseded by these final full-suite results; multi-page search and historical correction input round-trip remain outside the added browser cases. No new business API/schema changes. Local compose.acceptance.yaml remains an untracked environment-only override and is not part of the PR.

## Follow-up: searchable target equipment

User approved replacing separate search and select controls with an editable combobox. Uses the existing paged asset catalog, retains serial/asset number/model/status disambiguation and revision validation. Typing clears selected identity; only choosing a result authorizes a target. Supports mouse, arrows/Enter, Escape, blur closing, loading/no-match messages, clear and candidate pagination. Existing useRead cancels stale requests; backend business rules unchanged.

Validation: TypeScript/Vite build passed. Expanded real-browser lifecycle acceptance passed (1 test): no-match result, typed-but-unselected submit rejection, keyboard selection, clear/reselect via mouse, replacement, same-day status ordering, repair-center layout and read-only permissions. Tests ran solely on dga-datetime-test; acceptance database unchanged. Residual scope: full browser suite and load testing were not rerun; API query is immediate without debounce. No GitHub publication.

Scope: user-approved date/time entry and clear conflict messages; includes the prior repair-center layout fix on the same local branch. No production backend, schema, lifecycle policy or existing data changes.

Cause: date-only input always appended T00:00:00Z, while the public application interface correctly requires strictly increasing effective timestamps.

Change: explicit UTC datetime-local input, retain input time when serializing, UTC timestamps in history and correction defaults, future-time validation at submission, clearer chronology and daily movement messages. Existing correction times retain millisecond precision in input defaults. Repair-center controls reuse dashboard styling.

Validation:
- Red: browser flow timed out locating the required datetime input on the old frontend.
- Green: lifecycle browser flow passed, including replacement at 08:00, equal-time rejection, same-day 09:00 status success, preserved sample history, repair-center layout and read-only access.
- Real PostgreSQL public application interface: 12 lifecycle tests passed, including equal/earlier rejection and historical status before/after a same-day change.
- TypeScript and Vite build passed.

Local review: request serialization appends explicit Z (no implicit browser timezone conversion); date ordering remains enforced by backend; no new API or database contract; no reset of acceptance data. Tests reset only the independent dga-datetime-test fixtures.

Limitations: UTC input is deliberate and explicitly labelled; automatic local-time conversion is outside scope. One move per UTC day remains unchanged. Full browser suite not rerun for this narrow fix. No GitHub push/PR/merge performed; local review is not a completed Gateflow PR review.
