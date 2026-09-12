# Issue #11 — Asset lifecycle

Source: https://github.com/studyben/DGA_lab/issues/11
Base/review fixed point: 16fbaf013af37bd3722543dd46b1679e7db6745f.
Branch: codex/issue-11-asset-lifecycle.

## Confirmed scope

User confirmed customer sites and the single repair center only. No warehouse,
transit, inventory, service orders, import or analysis rules. User authorized push
and merge only after implementation, tests and review pass.

## Accepted seams and sequence

Asset public application commands/queries + real isolated PostgreSQL; no internal
table assertions or direct SQL to construct business success paths. Existing
official-asset fixtures represent pre-existing imported data. Critical browser
acceptance covers replacement and timeline. Review compares against the base above.

1. Move existing root/child assets with half-open effective histories.
2. State commands, valid tree checks and competing writes.
3. Atomic replacement preserving physical identity and laboratory snapshots.
4. Authorized reasoned historical correction and before/after audit.
5. Equipment current location/state/timeline and repair-center navigation.
6. Full tests/build; Standards and Spec review; fixes; commit, push, CI, merge.

Legacy status codes remain readable rather than guessing a migration mapping.
New commands use IN_SERVICE, UNDER_REPAIR, SPARE and RETIRED. Legacy unknown
historical state is not backdated as a made-up fact. Asset-owned change records
retain before/after values and are linked to shared audit events in one transaction.
