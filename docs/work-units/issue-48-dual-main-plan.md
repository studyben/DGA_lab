# Dual-main synchronization plan

## Goal / authorization / evidence
User explicitly approved preserving both repositories' existing functionality and unifying versions, after being told GitHub lacks Sungrow's user management/OIDC/site-basics functionality. #62 already merged to GitHub main2d7318eadc45dd0c0b2ff07a6e56b4958b311ccc; #48 automatically CLOSED. Sungrow maincab4eeaa833b5fc9ccbb2e0aebdac563a8f3f58f includes existing#18,41,42 work. Commonbase4fa9efe0576d3200688e5df523a61a3af742bfde. No force/history deletion, no new business feature, no subsequent issue development. #18 remains OPEN; mocked OIDC validation must not be represented as real Okta acceptance.

Worktree:isolated issue-48-dual-main-sync, branchcodex/issue-48-dual-main-sync from GitHubmain2d7318e. Existing#18/#48 worktrees, dirtydocs,18148testportal and databases untouched.

## Exact merge decisions / ownership
Merge Sungrowcab4eea into isolated branch, preserve bothparents. Drymerge identifies fourconflicts:
- README:retain complete corporate bilingual/readme/identity deployment instructions and append current#48export usage (with English counterpart).
- assets/http.py:retain SiteBasicsInput/PUTsitebasics and publicSiteBasics composition; retain SiteExportFile/_SiteDownload/staticGETexport before UUIDGET.
- shared/auth/public.py:retain all corporate localrecovery/management/OIDC/session/policy behavior; preserve #48 optionalgenericdetails INSERT onlywhen explicitlyprovided, AuditTrail.append optionaldetails, auditquerydetails. Onejsonimport; no schema-introspection fallback.
- DashboardPage:retain useState/SiteBasicsEditor/revision+editing/refetch; add SiteExportButton at site list. No component rewrite.
Automerge assets.public/main.py etc must be reviewed for composition/signature and one-direction publicinterfaces.

## Migration / fixtures / contracts
Existing0025_site_export_audit and0025_identity_roles→...→0029_oidc_callback bothdescend0024; never edit/stamp/delete appliedmigration. Add0030_merge_site_export_identity with down_revision tuple('0025_site_export_audit','0029_oidc_callback'), emptyupgrade/downgrade graphmerge. Singlealembichead, both deployedbaselines can upgrade. Add public-behavior upgrade test at each actualbaseline: keep existing legacyaccount/site/precise capacity and auditmetadata, upgrade head, publiclogin/access/siteexport/audit stillwork. ExistingOIDC/sitebasics/role/report tests must remain; historical fixtures must target their historicalschema without making currentidentitymanagement commands serve oldschemas. Retain originalbehaviorassertions; fix migrationtestarrangement only when failure proves mismatch. Metadata rollback guard tested at its historicalrevision; combined upgrades coveredseparately. No realOkta activation/tenantconfiguration inference.

## Slices / validation
S1 integration:merge fourhunks, graphmerge, onlynecessary contract/fixture compatibility fixes. Run existingtest redbeforegraphmerge orcompatiblefixture fix; run newdual-baselineupgrade behavior. Primaryseams existing publicapplication interfaces/realPostgreSQL and HTTP, notprivateinternals. Review fullmerge delta vs bothparents before finishing mergecommit.
S2 delivery:TypeScript/Vite build, fullbackend and keybrowser tests, including inheritedidentity/sitebasics and#48export. Use existing remoteCI for fullprotocolstorage/productionbrowser. Push integrationbranch to bothconfiguredpushURLs and create GitHubintegrationPR main2d7318e, attach it, review exacthead/diff/CI. No Closes#18. Once latestCIpasses, merge authorized integrationPR normally, then fast-forward Sungrowmain to sharedresult if allowed. If branchprotectionrequires corporatePR, use nativePR and compare treecontent; never bypasschecks or overwrite corporateonly history. Final verifybothmain descendants of oldmain andsame intendedtree, Issue48CLOSED/Issue18OPEN. No nextwork.

## Isolation / tools
Reuse PostgreSQL17binary read-only from#48.cache, create a NEW cluster/data/port18463 and dga_test database/user for sync tests; existingtest-db fixtureguardhost/name/user unchanged, PGHOSTADDR127.0.0.1. Own venv/cache/node_modules; install lockfiledeps, no originalruntime edits. Separate syncbrowserDB if localbrowserneeded; existing18148acceptance untouched. Docker locallyunavailable:realPGfallback plus remoteCI (allstoragecases) mandatory. Do not migrate existing localacceptance/primarydatabases.

## Documentation / risk / completion
Artifacts under docs/work-units/issue-48-dual-main-* and timestampedreviews. Sourcechanges minimalmerge-owned only; no future framework. Risksclassified: dualmigrationhead fixedS1, historicalfixture compatibility fixedS1, fullCIcoveredS2, actualOktaITacceptance existingIssue18 staysOPEN, unrelatedexistingdata kept by worktree/runtime isolation. Reviewacceptedfindings fix/rereview, integrationPRlatestCI andmerge/sync evidence required. Userexplicitauthorization covers existingfunctionunion and normalmain merges; no additionalbusinessopenquestion. Currentgoalconfirmed, nextplanreview, then mergeimplementation.
