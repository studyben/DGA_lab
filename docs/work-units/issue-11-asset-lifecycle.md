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

## Integration and operational constraints

- AssetDirectory sampling contexts now expose location_kind (SITE / REPAIR_CENTER).
  Repair-center contexts have null customer_id and site_id; no artificial site or
  customer is created. The existing site_name display field carries 维修中心 for
  backward-compatible labels. Laboratory owns encoding/decoding its immutable JSON
  snapshot, with SITE as the default for older snapshots lacking location_kind.
- Existing installation rows expand to represent the single repair-center target.
  Routine changes maintain adjacent half-open intervals; historical corrections
  reject newly introduced gaps/overlaps and illegal state/parent periods. They do
  not silently cascade timestamp changes into adjacent records or sample snapshots.
- Routine commands serialize graph writes with one transaction advisory lock and
  stale revision checks. This favors correctness for this small MVP over write
  throughput. Historical graph validation currently scans effective boundaries;
  scaling this validation is a future optimization, not a remote service seam.
- Historical correction requires assets.history.correct (system_admin by default)
  in addition to assets.write. Legacy state start times stay explicitly unknown.
- Migration 0011 is intentionally forward-only to avoid silently deleting
  immutable lifecycle evidence. Roll back deployment by reviewed backup recovery;
  the health regression tests outdated migration readiness using a reversible step.
- No production deployment or changes to the existing 18089 preview are included.
