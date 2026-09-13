# Slice 2 fix — CR-201

## Accepted finding

CR-201: ReportLab drew valid long values as one line, allowing content to leave the A4 page.

## Fix

- Measure text using the configured PDF font and size.
- Split mixed Chinese/ASCII text at the maximum value-column width.
- Apply the page-floor check to every continuation line.
- Stop truncating valid snapshot text in the renderer.
- Add focused width assertions and repeat visual QA with adversarial long content.

## Validation

- Focused post-fix suite: 18 passed.
- Complete backend suite: 74 passed.
- Normal and long PDFs rendered and visually inspected; text extraction remained successful.

## Residual risk classification

- Formal typography and brand layout: assigned to later product work, outside Issue #8.
