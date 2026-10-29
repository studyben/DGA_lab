# Issue48 S3 implementation

Scope: shared download button on DashboardPage and AssetImportPage, CSS, public browser acceptance and README. PrerequisiteS2 accepted14b1952。

RED: browser could not find download button. GREEN: real download works with field-user (no import grant), administrator import entry. Busy/status/alert/no-filter behavior; nativefetch+blobURL,60s timeout/unmount AbortController and timer cleanup. No new business state or next-ticket content.

Validation: npm run build pass,8 Playwright tests pass (two legacy dashboard tests); actual downloaded XLSX separately opened and verified bothsites. Screenshots1920×1080/1366×768 checked. Isolated browser DB dga_browser@18448 distinct from API test dga_test; existing fixture guards retained. Runtime/cache ignored; acceptance data untouched.

Full backend first run299passed/40skipped/1failed exposed optionalmetadata old-schema insert mismatch. S3-R1 accepted, fixed in shared audit; no-metadata calls keep originalSQL, explicit metadata uses newcolumn. Upgrade regression now29 focusedtests pass with older events{} verified. No weakening/deletion of existing assertions.

Residual: full rerun/timeout-unmount transport boundary covered by current aggregate gate; external storage40skips tracked by existing storageCI; no push/PR until authorized. Docs README only intended capability. Next accepted S3 commit→aggregate deepreview.
