# Method version help — acceptance follow-up

Goal confirmed by user: add plain-language text describing method-version purpose and controlled settings. Base0ee2171, existing issue14 branch; preserve untracked closeout documents and all data. One copy-only slice in ConfigurationPage with a browser visibility assertion. No new deletion behavior, schema, API, state transition, scientific default or external write.

Text explains a saved configuration selected during entry, units/precision/limits/qualifiers and QA requirements, new version for changed rules, historical evidence retention, distinction from report versions, and deactivation instead of deletion. Keep text visible above new-version controls, using semantic paragraphs and existing layout. No abstraction or CSS necessary.

Validation: isolated read-only browser test verifies visible explanation; production TypeScript/Vite build. Rebuild frontend only with --no-deps, do not run migrations/seeds. Do not reload user's unsaved tab. Review exact diff against existing immutable configuration and deactivation behavior.

Risks: publication feedback visibility separately identified during acceptance; outside this copy-only change, requires separate user decision. New deletion feature also requires separate scope/retention decision. No blocking question for explanatory copy. No push/merge authorized.

Plan review accepted f279731; slice accepted fb86d54 after build and1 read-only browser test passed. Aggregate review docs/reviews/code-review-20260913-104458.md passed. Local acceptance frontend18104 updated without dependencies/reseeding; original tabs/inputs untouched. Current next entry after accepted deepreview checkpoint: ready-to-open-draft-PR → push, stopped by explicit no-push scope. No remote changes or merge; future instruction required for publication.
