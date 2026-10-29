# Issue #48：目标确认

日期：2026-10-28。Gate：goal confirmation。状态：用户于2026-10-29明确确认目标及范围，goal confirmation pass；进入plan，尚未开始implementation。

## Work unit及授权

- 工单： https://github.com/studyben/DGA_lab/issues/48 。父规格： https://github.com/studyben/DGA_lab/issues/47 。工单无原生阻塞依赖，均为OPEN。
- 用户授权从最新main建立独立分支、完成当前工单的本地Gateflow；明确禁止推送、合并、启动后续工单。没有外部Issue评论/状态变更授权。
- 原目录 G:/Sungrow Develop/DGA Lab 在main上，CONTEXT.md和PROJECT_PLAN.md有既有修改，并有既有未跟踪目录；这些修改不搬移、不暂存、不提交、不清理。
- 已通过应用管理工具建立隔离工作树 C:/Users/weila/.codex/worktrees/issue-48-site-export/DGA Lab ，分支 codex/issue-48-site-export 。创建前新树干净，基线及远程最新main均为68e4d278e3e2a6b3e976036e3581b3ff2a7a773a。
- 未启动/停止任何现有运行环境、未执行迁移或重置验收数据。后续仅可运行隔离测试环境，不复用现有验收数据库或Compose项目。

## 需求及第一性原理判断

用户需要准备批量导入时看到目前系统已经有哪些现场，拿到稳定编号来引用，避免只凭名称重复建场或将设备连到错误现场。完整现场汇总是一条独立读取能力，不以客户/现场导入功能先上线为前提，也不要求建设智能体。

当前旧模板的现场参考表只列前500条，并按产品线输出行；不能承诺全部现场或一个物理现场一行。已有列表受产品线、过滤及分页影响，不能以循环拿当前页资料代替一致的完整导出。因此本work unit成立，范围可保持为资产模块拥有的单一导出链。

父规格#47完整正文已读取并与已确认的本地发布正文比对一致；未见新增评论或业务变更。项目使用GitHub Issues和ready-for-agent词汇；原目录用户提供的Agent规则及领域文档作为约束，主线旧术语不得否定本次已确认零设备现场等规则。

## 目标及成功信号

1. 在资产导入入口和现场列表加入“下载当前现场汇总”，明确输出所有有权读取的当前现场，而非当前页/当前筛选或单一产品线。
2. 生成统一XLSX，每实际现场一行，包括无设备、同名不同编号和多产品线现场。沿用UUID作为正式现场/客户编号，固定机器可读列名、中文说明、生成时间及读取范围。
3. 字段涵盖现场及客户编号/名称、位置、产品线、光伏MW、储能MW/MWh、Commissioning Date、并网调试/投运状态及来源备注。未知仍为空，不导出并网年份、不编造来源；本工单不新增来源备注的业务写入能力。
4. 超过500条仍完整；一致读取、稳定排序、有界生成；文字不执行公式，编号按文本，无资料时仍返回有表头文件。
5. 公开应用能力及HTTP均检查assets.read，遵循现有实际读取范围。无权限不能下载，不通过此按钮获得assets.import或其他写入权限。
6. 仅完整生成成功才提供文件；页面有处理中/失败反馈，必要生成/提供下载审计保存真实操作者、范围、数量及时间，不能宣称已确认浏览器本地保存成功。
7. 资产、客户、现场容量和安装历史不变；除本导出必要审计外无业务写操作，既有资产模板和列表行为保持。

## 直接代码证据

证据均来自本工作树相同main基线：

- backend/dga/assets/imports.py:78–85：AssetImports.template要求assets.import，现场/物料参考查询均有限500；现场参考按产品线连接。
- backend/dga/assets/dashboard.py:66–86：dashboard按已选产品线/筛选及分页查询，不能作为全部现场导出契约。
- backend/dga/assets/public.py:124、143、190：AssetDirectory已有只读公开目录/列表/详情，是本工单的高层业务测试接缝。
- backend/dga/assets/http.py:78：已有/sites/{site_id}路由，新增静态export路径必须避免被该参数路由当UUID处理。
- frontend/src/features/assets/pages.ts:4–28：现场与仪表板用assets.read，导入页用assets.import；导出本身应服从读取授权，不扩展导入权限。
- frontend/src/features/assets/DashboardPage.tsx:52–65：DashboardPage承载现场列表；frontend/src/features/assets/AssetImportPage.tsx:99–100有现有模板按钮。
- backend/dga/shared/auth/public.py:69–94：共享AuditTrail已有追加接口，但当前调用参数没有范围/记录数载荷；计划须以本工单最小必要审计元数据方案落实，不预先扩建完整审计平台。
- backend/requirements.in已有openpyxl；既有资产模板明确把字符串写为文本单元格，可复用该安全实践，无需新增第三方服务/收费依赖。

## 非目标及scope边界

- 不实施#49及后续工单：不新增/更改现场、客户、物料、设备，不修改资产安装关系或批量导入发布规则。
- 不建设AI、自动匹配/自动发布，不做完整业务包导出、通用导出任务平台或完整审计检索UI。
- 不更换对象存储、不新增云资源/凭据、不改Okta/RBAC角色矩阵、不以本工单修复全部陈旧领域文档。
- 不为未来数据来源写入提前建设数据库结构；当前缺来源说明时保留空列，后续来源与汇总整合由#49/#50及#61验收。
- 不在未验证规模压力前引入新队列/消息服务。是否需要最小附加审计结构及有界生成策略，在plan gate基于代码决定，不把正常下载做成大型基础设施项目。

## 测试接缝及验证边界

沿用用户已确认策略：AssetDirectory公开导出/查询接口连接真实隔离PostgreSQL，检查实际XLSX语义；HTTP补会话/权限、MIME/安全下载头和路由测试。覆盖超过500现场、多产品线、无设备、同名、空值、特殊文本、无记录、一致快照、失败及审计。浏览器仅新增现场列表下载的一条关键链，导入入口行为补必要验证；不测试内部表布局或React内部实现。

仅检查了测试配置/保护约定，尚未运行应用测试。运行环境/测试接缝的具体命令和隔离Compose名称在批准后的plan固定，禁止用现有验收环境数据做fixture。

## Open questions和residual risks

- Blocking open questions：无业务范围阻塞问题，等待本目标gate的明确确认。
- 审计范围/数量载荷：tracked by existing issue（#48；在后续plan确定最小方案，尚未批准任何implementation slice）。
- 超过500条及多产品线重复行：tracked by existing issue（#48；后续计划与测试驱动切片必须覆盖，尚未批准slice）。
- 现有主线没有来源备注写入：assigned to later work unit（#49/#50及最终#61）；本工单输出空值不造事实。
- 未来AI整理与自动发布：tracked by existing issue（父规格#47的范围外约束；未来如需另行授权，本次不创建新工单）。
- 本地Docker曾有历史故障：tracked by existing issue（#48；后续plan核实隔离验证条件，若基础确不可用按证据报告阻塞，不提前更改运行环境）。

## Gate decision及下一入口

本目标在代码和父规格约束下成立。当前gate仍为goal confirmation，等待用户确认；通过后进入plan，再执行planreview、测试驱动slice、deepreview及本地checkpoint。用户明确不推送，故后续最多到ready-to-open-draft-PR；不会执行push或创建PR，不声称draft-PR-pass/final closeout pass。

Artifact：docs/work-units/issue-48-goal-confirmation.md。


2026-10-29目标gate裁决：用户明确确认后通过。此前提供的AGENTS.md指令已由用户撤销，按当前用户指示、Issue #48及父规格#47执行；旧目标中的项目规则记录仅作历史证据。后续设计及验证以本work unit计划为准。

