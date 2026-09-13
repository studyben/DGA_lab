# 实验室方法配置、仪器校准与 QA/QC 警告

Closes #14

## Changes
- Laboratory public configuration interface and authenticated admin UI for existing test types, immutable method versions, instruments/calibrations and immutable test packages.
- Version-driven unit/precision/limits/qualifier validation; manual QA execution and measurement-date calibration evidence.
- Required package checks and explicit warning acknowledgement before overall finalization; frozen method/quality/acknowledgement evidence for PDF reports.
- Additive migrations0016–0018 retain existing data and refuse evidence-losing rollback. Assets/analysis public boundaries unchanged.
- No guessed ASTM IDs/scientific values, automated acquisition or accreditation workflows.

## Validation
-190 public-interface/backend tests passed with real dedicated PostgreSQL.
-28 browser acceptance tests passed; TypeScript/Vite build and diff checks passed.
-1280×720 configuration screenshot inspected,1920×1080 browser flows validated.
- Slice and aggregate review findings fixed and re-reviewed; artifacts in docs/reviews/code-review-20260913-005104.md and code-review-20260913-005931.md.

## Remaining scope
- Laboratory owner supplies approved scientific parameters/QA contents; test values are not production defaults.
- Existing#13 manual feedback stays tracked separately; deployment#20 owns production rollout/dynamic upstream handling. Local API replacement may require restarting the matching frontend container, not resetting data.
- This is a draft PR, not merge approval. PR review runs after creation; issue closeout comment requires separate authorization.
