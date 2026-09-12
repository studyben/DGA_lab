# Issue #11 review and acceptance

Fixed base: 16fbaf013af37bd3722543dd46b1679e7db6745f.
Initial implementation: fadbca2. First review repair: bcdbc03.
User authorized the narrowed site/repair-center scope, push and merge after checks.

## Standards

Independent Standards review: no documented-standard violations. Asset writes
remain asset-owned, laboratory snapshot integration crosses public interfaces, and
tests exercise public behavior with real PostgreSQL. Two nonblocking heuristics:
public lifecycle commands could use stronger shared parameter types; the frontend
lifecycle form/history and repair-center listing could be split into smaller files.
These are maintainability suggestions, not correctness or acceptance failures.

## Spec

Initial review found three blocking issues: corrections bypassing lifecycle rules,
corrections opening history gaps, and missing formal repair-center sample linking.
Each received a public-interface regression followed by a fix. Re-review found two
variants of the first issue (unknown child state skipping parent validation and
same-parent interval extension); each was reproduced red, fixed and tested green.
Final independent static re-review confirmed all reported Spec blockers closed.

## Verification evidence

- Red/green cycles: detach/reinstall; state transition and restoration; atomic
  transformer replacement; correction authorization/overlap/cycle; competing moves;
  repair-center navigation; HTTP CSRF; repair-center sample snapshot; historical
  disabled-parent variants.
- Initial full backend: 66 passed. Initial full browser: 17 passed.
- Review-fix targeted public-interface suite: 11 lifecycle tests passed; earlier
  sampling integration regression: 15 passed.
- TypeScript/Vite production builds passed. Final full regression recorded below.
- Final review-fix regression: **69 backend tests passed**, **17 browser tests
  passed**, TypeScript/Vite production build passed. Two existing third-party
  deprecation warnings remain (Starlette test transport / AnyIO alias).
- Replacement test exercises second-half failure after the first write, confirming
  rollback of old-asset relation/revision; successful replacement keeps old/new
  physical IDs and sample histories separate.

## Residual constraints

No ASTM/threshold/PDF-brand guesses, warehouse/transit, inventory, service orders,
imports or later tickets. Unknown legacy state start dates are not fabricated.
History correction refuses unsafe independent date edits instead of guessing
adjacent dates. Global serialized graph writes and boundary scanning suit the
small MVP; scale/performance tuning remains a documented limitation.
