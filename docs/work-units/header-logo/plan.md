# SUNGROW header logo

## Goal confirmation and preflight

User confirmed the recommended scope with “按推荐来”: replace the existing D tile and DGA Lab wordmark in the shared header with the supplied SUNGROW SVG, retain 资产与油样管理 underneath, preserve original orange/proportions and home link across both workspaces. No theme redesign, prototype change, backend behavior, issue implementation or PR merge.

Source: C:/Users/weila/Downloads/logo.84e5bb0c.svg. Inspected SVG contains only paths, clipping and #FF7900 fills, viewBox 0 0 150 20; no script, external URL or embedded instructions. Existing header is frontend/src/main.tsx and .brand styles in styles.css. The confirmed layout can be changed at this shared seam without touching domain modules or data.

Branch: codex/sungrow-header-logo; base: codex/issue-2-foundation at 962f68efa59bd56bed6f955d07430d28d9518d82. The foundation PR is still draft: use a stacked draft against that branch so this change does not alter #21 or repeat its diff. Preserve all pre-existing dirty documents/tools. This is a user-requested small work unit, not another numbered Issue.

## One slice: header identity

- Allowed changes: frontend/src/assets/sungrow-logo.svg (exact supplied SVG), frontend/src/main.tsx, frontend/src/styles.css, frontend/tests/portal.spec.ts, and these work-unit/review artifacts.
- Use Vite-resolved SVG import with an explicit *.svg TypeScript declaration if required by this project's existing compiler config. Render img alt="SUNGROW" with intrinsic 150x20 dimensions; displayed width 180px and automatic height. Brand wrapper is a vertical, left-aligned column within the unchanged 220px header slot. Keep subtitle and href="/". Remove only now-unused brand tile/wordmark rules.
- Data flow: local packaged SVG -> Vite hashed static output -> shared header image. No image rewriting, remote hotlink, runtime dependency, state machine, database or module public contract changes. Retain sidebar/footer product text and existing responsive subtitle behavior.
- Reuse the already agreed browser public UI seam: add one test visiting assets and lab deep routes, asserting SUNGROW image loads and shows the supplied 7.5:1 aspect, subtitle remains and brand click returns home. No React implementation assertions or CSS selector snapshots.
- Red: run the added browser test against current nginx; it must fail because SUNGROW is missing. Green: apply the logo patch, build/redeploy only frontend with --no-deps, run all browser tests and TypeScript/production build. Inspect 1920x1080 screenshot for clipping and logo fidelity. No backend tests need rerunning for this static-only change.
- Stop only on missing source, wrong branch/ownership, unfixable validation or new scope question. No speculative theme system or new package justified.

## Reviews and delivery

Plan review -> accepted plan commit -> slice implementation/review/commit -> aggregate deepreview/commit -> push/stacked draft PR -> actual PR review/commit/final push -> final closeout. Do not comment on or close #2. No merge or later ticket authorized.

Residual risks: browser layout and resource packaging are fixed/verified in this slice; broader branding is deferred to an explicitly requested future theme work unit; foundation merge remains user-owned PR #21. Docs decision: no domain/ADR changes; record focused delivery evidence only. Final response: visible result, verification, draft link and unchanged scope.
