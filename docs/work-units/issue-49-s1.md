# Issue #49 S1 implementation

Gate implementation/code review; plan accepted70afe21. Customer/site-only v2 at AssetImports and AssetDirectory public seams, identity-owned transaction guard, append-only provenance/revisions, atomic operation results, source integrity verification and source_note export. New migration0031 only, legacy format1 defaults.

Red/green evidence: initial unsupportedformat, missing revise, duplicate file links, result IDs and revision-history public tests all observedRED before fixes. Real isolated PostgreSQL18465:30 site tests,107 combined asset import/export/basics/architecture checks. 500customer+500site and500site boundaries actually published;501/invalid file cases rejected. Public fault checks include lostCOMMIT response, last-audit rollback, stale catalog, simultaneoussameintent, currentgrantrevocation, sourcecorruption.

Affected production files: assets/imports,site_import_workbook,site_import_validation,site_imports,public,dashboard,site_export; shared/auth/public currentguard/policy; migrations0031. No laboratory/analysis internals touched. No source-file reinterpretation or original-data migration.

Findings fixed and re-reviewed in S1 code review artifact. Remaining HTTP/UI covered by S2; complex cancellation by#60, combined capacity by#61, IT realOkta by#18. No unclassified risk. Docs/domain usage will align with S2 before aggregate. Completion S1pass; next entrypoint implementationS2 after accepted slicecommit.
