# Issue #2 — 目标确认

- Work unit: https://github.com/studyben/DGA_lab/issues/2
- Parent: https://github.com/studyben/DGA_lab/issues/1
- Branch: `codex/issue-2-foundation`
- Base commit: `a1cc0ce`
- Current gate / next entry point: see `progress.md`
- Status: goal confirmed by user; implementation not started at confirmation

## 已授权事项与输入所有权

用户已允许创建工作分支、保留已有未提交项目输入，并仅提交当前工单涉及的文件。工作分支已经创建。
既有修改为 CONTEXT.md、PROJECT_PLAN.md；既有未跟踪目录/文件为 AGENTS.md、docs/、tools/。
本工单新增 artifact 位于 docs/work-units/issue-2/。后续提交须逐文件选择，不能整体 stage docs/。

## 目标、动机与成功信号

让开发者从空环境启动一个实际运行的中文统一门户，并建立后续业务能持续复用的运行、迁移和测试入口。
当前工作成立：仓库尚无生产前后端、依赖清单、migration 或测试套件，后续 #3 起的工单需要这些最小基础。

验收信号：

1. 一条文档化命令启动 React + TypeScript 前端、FastAPI API 和 PostgreSQL。
2. 顶部切换资产仪表板与 DGA 实验室；侧栏只显示当前工作区子页面。状态分析保留独立模块所有权，以专业子模块入口呈现。
3. 应用及数据库正常时健康检查成功，数据库不可用时明确失败。
4. 资产管理、实验室管理、状态分析公开应用接口位置及依赖方向有自动化约束或等效验证。
5. 至少一个 API 集成测试使用真实 PostgreSQL 测试库，执行与生产相同的 migrations 后通过。

## 范围与非目标

范围为正式工程骨架、门户导航、模块接口入口与依赖约束、配置管理、最小数据库迁移、本地 Compose、集成测试基座及启动烟雾验证。

不包含登录/RBAC、业务 CRUD、资产搜索、收样、检测、报告、对象存储、异步任务或云资源部署；这些由后续 tickets 交付。
不将全部数据库设计转换成第一批表，也不预建未使用的业务接口、通用平台、微服务或消息总线。
前端采用确认的方案 A 交互方向；原型仅作为参考，不复制假数据和 A/B/C 切换进入正式应用。

## 直接证据与约束

- `git ls-files` 当前只有 CONTEXT.md 与 PROJECT_PLAN.md，当前提交为 a1cc0ce；文件清单中不存在生产依赖清单、前后端应用或迁移。
- docs/product/prototypes/asset-dashboard/README.md 明确原型仅使用固定假数据和浏览器内存，无真实接口、数据库或持久化。
- Issue #2 已读取完整正文，无 blocking dependencies，明确上述五项验收条件及非目标。
- Issue #1 已读取：确认两个顶部工作区、三个业务模块、公开应用接口测试边界和真实 PostgreSQL；原型不能直接演进为生产代码。
- CONTEXT.md 定义资产、整机、变压器、油样、检测、整体定稿等领域身份和术语。
- ADR-0004 约束模块化单体和数据所有权；ADR-0006 约束未来 Lightsail 混合部署。其余 ADR 的资产、快照、类型化结果和定稿不变量作为后续能力约束保留。
- PROJECT_PLAN.md 部分早期总交付顺序与最新纵向 tickets 不同；本工单按 Issue #2 的最小范围执行。

## 验证环境与风险归属

- 已发现 Node、Docker CLI 和 Docker Compose。
- 当前 Docker daemon 未连接成功；执行真实数据库与 Compose 验收前需检查并启动本机 Docker Desktop。状态：待实现验证阶段解决，不能把未运行测试记录为通过。
- `gh` 不在 PATH；本次已通过登录的 GitHub 浏览器读取工单。后续 push / draft PR 阶段需验证可用路径。
- 正式 ASTM 配置、正式阈值和 PDF 品牌版式不影响本工单，归属后续对应工单/外部确认。

## 确认后的推进顺序

目标确认 → 实施计划 → planreview 与修复/复审 → 接受计划提交 → 按小切片测试驱动实现 → 每片 deepreview 与修复/复审/提交 → 汇总 deepreview → draft PR → PR review 与修复/复审 → final closeout。

建议项目串行顺序：#2 → #3 → #4 → #5 → #6 → #7 → #8，先形成首条条码报告闭环；随后 #9 → #10 → #11 → #12 → #13 → #14 → #15 → #16 → #17 → #18 → #19 → #20。该顺序满足已发布依赖；实际领取前再次核验前置工单合并状态。

## Docs decision 与 gate decision

本文件是目标确认 artifact，不是已批准的 implementation plan。现有领域文档不在本 gate 修改。
用户已明确确认 Issue #2 的目标与范围，并要求继续计划、测试驱动实现、审查和 draft PR，仅在真正阻塞时询问。
