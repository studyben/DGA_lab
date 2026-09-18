# Issue16 S2 implementation

Gate: implementation -> code review -> fix -> re-review -> accepted slice commit.
Artifact: docs/work-units/issue-16-s2.md. Review: docs/reviews/code-review-20260913-153039.md.

Implemented public DeviceHealth query/evaluation and authenticated health/rule HTTP adapters; assets owns immutable current subtree facts, lab owns validated batched current-finalized results. Analysis only reads its own policy/evidence tables. Evaluation uses latest sample time before compatibility, preserves ties and qualified/unknown reasons, highest policy priority and current effective interval, own vs descendants, immutable deduplicated evidence.

TDD evidence: missing interface import red -> no-results green; expected WARNING got UNASSESSED -> real evaluation2passed; parent transformer_required -> tree/batch25relatedpassed; missing tie marker and stale NORMAL on concurrent source -> marker+double-read8passed; missing HTTP404 -> authenticated router. Test fixture typo corrected before true HTTP red. Review overlap test reproduced DID NOT RAISE -> owner active_counts guard green.

Validation: complete backend243passed, two existing Starlette deprecation warnings. New 0019->0020->0021 linear chain upgraded on isolated database; old0013->head and repeated upgrade probed on separate temporary test database. Original acceptance data untouched. No push/merge.

Plan refinement: migration steps split instead of rewriting applied0019; test_health.py isolation fix supports required regression and is not production expansion. Future source sampled times excluded, effective dates aware, unknown never silently normal. Existing trend API regression passes.

Docs decision: these work-unit records document contracts; user guide/UI labels S3. Residual risks: browser experience/refresh covered by approved S3, formal thresholds remain out of scope. No unclassified residual risk. Decision: S2 pass. Next entry point: implementation S3.
