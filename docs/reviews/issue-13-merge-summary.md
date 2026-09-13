# Laboratory integration and operations merge

## Scope
Integrate previously completed #7/#8 into main (including migration branch join 0014), then deliver #13 laboratory dashboard, ledger, identity confirmation, container lifecycle and audited operations (0015). Preserve #9-#12 and public module boundaries. No later ticket implementation.

Closes #7
Closes #8
Closes #13

## Validation
Local implementation evidence records 169 PostgreSQL backend tests, 25 browser tests, build/typecheck, migration single-head and code reviews. See issue-13-lab-operations work unit and code-review-20260912-231516.md. Remote CI must pass before merge.

## Manual acceptance / limitations
User confirmed home metrics, ledger, sample information, current report display and finalized data edit guards, then stopped remaining manual acceptance and authorized merge. This is not full manual acceptance. See issue-13-manual-acceptance.md for retained feedback: DGA field overlap, missing workbench partial-barcode search, confusing physical-container presentation, reception bottle-count feedback not reproduced, deferred scientific configuration labels, and earlier preview/session-expired failure (current display recovered, cause not established). No fixes for these are claimed. Formal ASTM parameters, thresholds and PDF branding remain deferred.

## Preservation
No changes to original dirty workspace or running acceptance databases; no reseeding, resets or deployment as part of this merge.
