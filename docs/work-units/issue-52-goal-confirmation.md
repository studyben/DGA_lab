# #52 目标确认记录（已由用户确认）

- Work unit：Issue #52 / BI-05，实验室统一模板、结构化资料暂存与预览；feature / public application interface + additive staging schema。
- Gate：goal confirmation 已由批次用户确认；此文件仅综合确认，不提出新访谈、不宣称实现或关闭工单。当前交接为 PLAN DOCS ONLY，下一 gate 是独立 planreview。
- 原始计划 preflight 基线：`C:/Users/weila/.codex/worktrees/issue-52-lab-import-staging/DGA Lab`，`codex/issue-52-lab-import-staging`，`077806b6cdcb67821de90982b3d7c6c334d567e0`；只读 preflight branch/HEAD/status 通过且起始 clean。迁移 head `0033_lab_finalization_facts`。
- 真源：G:/Sungrow Develop/DGA Lab/outputs/specs/bulk-data-import.md；outputs/phaseflow-50-52/issue-{47,52}.json；docs/work-units/phaseflow-50-52-control.md。当前 CONTEXT.md / PROJECT_PLAN.md / ADR-0007/0010 已读；ADR-0009 权威原件仍在 G:，保留不复制其它脏文档。

## 目标、动机与成功信号

用户已确认三张工单目标，#52 的问题是：第三方和历史实验数据需要先完整保存、核对、续办，而现有正式收样入口会创建油样与容器，不能用于缺日期、方法、设备身份或没有油瓶的资料。来源不明、日期精度不明也不应变成有效检测。故交付可独立使用的资料准备能力，明确“已暂存/待校验/待核对”，不暗示正式导入。

确认的结果：

1. 实验室拥有 LaboratoryImports 公开门面、版本化 Excel“油样信息/检测结果”两业务表或同批两份 UTF-8 CSV、说明和示例；保留原文件与原值、解析值、source_note，明确来源实验室 NEW/REFERENCE 稳定身份、外部样品/检测标识、用途和来源时区。
2. 后台安全解析/校验，完整 DGA 七项一行、复测另行；0/ND/LT/GT/空白不同；未知类型、方法、单位、资产、日期和 DST 歧义均可解释。分页按油样展开全部检测、文件声明和问题，支持核对修订、原文件鉴权、历史筛选和关闭重开。
3. 第一次写入起具备 laboratory.write/currentauth、CSRF、审计、revision、持久幂等操作和未知 COMMIT 恢复；文件失败不假成功。500 油样/2000 完整检测与冻结安全资源上限可验证。所有暂存对正式油样、检测、容器、资产、定稿事实、报告任务和正式业务查询无副作用。

## 第一性判断和直接证据

- `backend/dga/laboratory/public.py:178` 的 SampleRegistry.receive 会保存正式样品并生成容器；`:312` 要求带时区采样/收样时刻。`workbench.py:936` 要求正式类型化测量。暂存必须另立门面/表，不能向这两个写入口补默认值。
- `backend/migrations/versions/0033_lab_finalization_facts.py:4` 已在实际基线；`laboratory/public.py:346/:380` 公开 FinalizationReportPolicy / FinalizationFactsView；`workbench.py:245` 可读当前定稿事实；`trends.py:70` 已从独立事实读有效结果。这些是 #51 已实现前置，#52 不调用其正式写能力。
- 搜索实际 backend/frontend 未发现 LaboratoryImports 或 /api/laboratory/imports；实验室 pages.ts 无导入页。资产 V2Imports/解析器仍为资产私有，architecture.py 要求跨模块只用 public。
- shared FileStore/factory、IdentityService.authorize_current、AuditTrail 与现有数据库 claim/lease 模式可复用技术原则；不需要 Redis、新云资源或万能 ImportService。
- 资产公共 search/采样上下文仍主要是 exact-instant/当前路径能力；暂存可保留物理身份/历史关系未核实，不能自己读资产表补造历史。

## 非目标和保护边界

不创建正式 oil_samples、laboratory_tests、sample_containers、临时资产或来源到正式样品的映射；不执行导入 OPEN/FINALIZE、NO_REQUEST 定稿、发布、撤回、报告排队/PDF内容上传、汇总生成、历史关系写入或 #53+ 功能。PDF 名称可声明但始终“未提供”；页面无发布按钮。

不猜 ASTM/单位兼容/阈值/校准/原分析员/午夜时刻；缺配置只成为暂存问题。保留 analyst 当前 finalize grant，不借本工单改 #18 权限。保留 #50/#51/旧 UAT 和原脏工作区、文件及运行资源。共享解析技术若未实际抽为无领域依赖的契约，实验室不得导入资产私有实现；本计划选择实验室自有解析器，零资产解析行为迁移。

## 本 gate 已执行与停止条件

只读核对代码、规格、分支、迁移、指导文件和拟用端口；18552/18572/18172 未发现监听。没有安装、启动、迁移、测试、写源代码/测试/配置、提交、推送或外部操作。

原始计划写作时点：PR66 保持 draft；父基线最新 CI 在 root 解除 guard 前，不接受计划 commit，也不实现。本 Agent 只交付本文件与 issue-52-plan.md（可更新独立 evidence artifact），随后显式 COMPLETE 等 root；不自行启动完整 Gateflow，不接管总控。

Blocking open questions：无。技术 schema/列名/状态机由 plan 明确定义；已确认业务目标不再访谈。残余风险和后续工单 owner 见 plan。

Baseline pointer refresh: root已完成OWN52分支 --ff-only077→896d7072cfd81c07ac732404d286e160e9ed3459，保留本文件与plan。实际077..896只有 .github/workflows/ci.yml timeout20→30及 docs/work-units/issue-51-ci-timeout-fix.md、docs/reviews/pr-66-review-20261029-213806.md；backend/frontend/compose源码与0033公共契约不变。上文077 clean preflight是原时点事实，不改写为896。当下HEAD896已只读核实；本Agent没有FF/切branch。

基线pointer刷新写作时点：30分钟已配置且父修复已独立review/accepted，但新896 BOTH latest fullCI GREEN仍待root验证；077旧Sungrow cancelled不算pass。独立planreview可先docs-only进行；#52 accepted-plancommit/source/tests/runtime必须等待root解除新896双host全流程GREEN guard。本次只刷新文档pointer，方案/18与39列/三个slice不变。详见issue-52-plan-baseline-refresh.md。

当前有限plan-fix更新（root提供的已核验状态）：896 HEAD不变，GitHubPR40992909646/push40992903963和Sungrow312591896 ALLSUCCESS；两边684backend、78browser/1既有optionalOIDCskip，40provider均执行，GHE全job21m02在30min内结束。父CI预算failure已closed、guard已解除；本Agent未亲跑/查询CI，不将旧077 cancelled算pass。仍须finding01修复→独立re-review→accepted-plan后才能source/tests/runtime，当前仍DOCS ONLY。
目标和非目标不变。唯一acceptedfinding01的计划修复：校验仅依赖完整且RECEIVED/hash确认的active workingmanifest；历史inactive PENDING/RETRYABLE不阻塞，B可用自己的intent同批上传/选择新原件，A原actor-private操作/对象/恢复元数据保留，迟到A回执不替换active且按revision使旧job失效。无cancel/delete/代理旧key或正式数据写入。详见issue-52-plan-fix.md，独立re-review待完成。

