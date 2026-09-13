# #7/#8 integration and #13 manual acceptance

Environment: isolated http://127.0.0.1:18097, implementation de1f1c9.
User instruction: guide one operation at a time; record findings, no implementation fixes, push or merge.

## Confirmed by user
- User stopped remaining manual acceptance and subsequently authorized merge. Unchecked items remain unchecked; known feedback below is retained, not represented as fixed or fully accepted.
- Laboratory home four metrics display normally.
- Sample ledger displays normally.
- User confirmed loaded oil sample DGA-20260912-000010 matches its registered information.
- Following the refresh/re-authentication check request, user reports "报告正常". Current report display is user-confirmed normal; the exact recovery action and each preview path were not separately confirmed. Earlier preview/session failure remains recorded, not claimed fixed.
- User confirmed finalized sample test data cannot be added, modified or deleted ("都符合预期" in response to that specific check). This is not blanket acceptance of outstanding feedback or all #13 operations.
- Barcode filter not yet explicitly confirmed; do not mark passed.

## Feedback
   
### Report preview follow-up
Latest outcome: user now reports the report is normal. The failures below are historical observations; root cause and durable recovery remain unverified. No application fix performed.
Further screenshot codex-clipboard-2fd6e8d5-aa16-4ca7-9e2d-5792d8e05a4a.png displays JSON {"code":"session_expired"}. This establishes authentication rejection for that request, not the precise cause of the earlier blank viewer. Exact requested URL, HTTP status and cookie/session context are not shown. Next check: return to application and refresh/re-authenticate, then retry report preview; do not assume PDF corruption or disable authentication. No code change.
After being asked to use 在新窗口打开, user supplied codex-clipboard-e6adfdf7-6b7b-49eb-9cfe-9784407bd189.png: blank gray surface with failed-document icon, no report content. Record as failed open/preview follow-up; screenshot does not identify the precise URL or establish a browser/rendering/network root cause. Downloaded PDF remains user-reported normal. Both online preview paths remain unaccepted. No repair or external change authorized.

6. Report preview fails manual acceptance for DGA-20260912-000010. User reports downloaded PDF opens normally; screenshot codex-clipboard-5dd3a5c2-91b9-4004-8f96-a44f65b0106b.png shows READY report with blank dark embedded preview. Record download as user-confirmed working, embedded preview as failed. Root cause not established; do not attribute to browser compatibility or report corruption without reproduction. Next single check: use the existing 在新窗口打开 link and report whether PDF content renders there. No code/data changes.
1. Two container status cards look like duplicate states. Screenshot shows C01 and C02 for one oil sample; these are two separately tracked physical containers, not duplicate tests. Suggested presentation: sample bottle1/2 and total count. Record only; no UI change authorized.
2. User reports container count seems unchangeable during reception. Status: not reproduced in independent browser probe against the same18097 service; exact user-page interaction still to confirm.
   - Browser probe locates accessible field 样品容器数量, asserts changing1→2→1, checks editable/min/max. Result: editable=true,min=1,max=20,change_1_2_1=PASS,submitted=false. No sample registered or altered.
   - Invocation: isolated Compose browser-test running node probe using Playwright, with test authentication supplied via environment and never printed.
   - Source: ReceptionPage.tsx renders controlled number input under 03 / 收样登记 / 填写油样基本信息, submits container_count from its value. Existing registered oil samples are not edited by this new-reception form.
   - Next user check: locate that field and try changing it before submission; obtain screenshot/exact symptom if it remains blocked.

3. DGA entry layout fails manual acceptance. User screenshot codex-clipboard-1fa27d53-9fbf-45c0-9228-53aad29402fc.png shows adjacent gas result fields overlapping (H2/CH4, C2H2/C2H4, C2H6/CO). Visible defect confirmed from screenshot; CSS root cause not yet diagnosed, no fix made. Automated workflow pass did not establish this layout was correct at the user's viewport/zoom. Recheck the actual viewport and zoom when fixing.
4. User asks about unit/precision/detection-limit pending labels. WorkbenchPage.tsx renders these when method fields unit_code/display_decimal_places/detection_limit are null. Here precision means configured decimal places, not instrument accuracy. Current DGA method is explicitly MVP-PLACEHOLDER; formal scientific configuration was deferred, not inferred from ASTM. Keep separate from the layout defect; no configuration values fabricated. Suggested copy clarification: 小数位数待配置. No UI change yet.
5. Workbench partial barcode search is missing. User entered0010 and received sample-not-found (screenshot codex-clipboard-faa4d418-dd15-4bdf-9bc1-efb3db5b2046.png). LaboratoryWorkbench.load uses exact barcode_value=:barcode, consistent with this result; ledger substring filtering is a separate existing capability. Proposed enhancement, not implemented: retain exact scanner lookup; partial barcode/keywords show candidate oil samples (full barcode, site, equipment serial, sampling time), requiring explicit selection rather than silently opening the first match. Keyword field scope remains a proposal, not user-confirmed. No application code changed.

Diagnosis phases for the reception-count report remain incomplete because failure was not reproduced. The DGA overlap is confirmed visually but not root-caused. User requested recording only; no speculative cause or fix claimed. No production code/data changes, no push/merge.
