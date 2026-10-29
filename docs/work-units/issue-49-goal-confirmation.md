# Issue #49 目标确认

Gate：goal confirmation，用户已于2026-10-29确认目标、范围与公开测试接缝，并授权计划、审查、TDD、draft PR，不合并。独立分支 codex/issue-49-site-import；基线 GitHub main 8725ed8c67ba38b70e0f3d5d5e0ef5e6a3ac84c9，与 Sungrow main 同步。父规格 #47、实施工单 #49 均已读取；#49 原生 blocked_by 为空，ready-for-agent。

## 目标、动机和成功信号

在资产管理中交付“仅导入现场信息”纵向能力：v2 客户/现场表上传、后台校验、同名与属性差异核对、明确引用或确认新增、预览确认、整批发布、历史续看、源文件与来源备注追溯。允许引用已有客户或同批新增客户；没有设备或物料仍可合法建场。

成功信号：用户通过网页上传现场模板，解决同名差异后明确提交，在对应产品线看到零设备现场、原样容量、日期与状态及来源备注；同请求重试返回相同现场身份，晚期失败全部回滚，事实变化要求重新核对；原 v1 导入及现有数据保持有效。

## 直接证据

- backend/dga/assets/import_workbook.py:52 parse 强制 Assets 表；101 template 为 v1，Sites/Materials 仅参考；当前2 MiB等旧限制不能直接当作 v2 的批准限额。
- backend/dga/assets/imports.py AssetImports 已有保留批次、FileStore、后台 validate_next、publish 重验、单事务新增设备和审计；尚无客户/现场正式写入或网页核对修订。
- backend/dga/assets/dashboard.py SITE_CTE 以 sites 与 site_product_lines 产生现场；空设备不阻止已有现场/容量读取。
- backend/dga/assets/site_export.py #48 已提供全量下载，但 source_note 当前明确空白；#49 需要消费真实保存的来源资料，不能继续假装备注不存在。
- backend/dga/shared/auth/policy.py 及0025_identity_roles：lab_admin 已有经#18确认的其他资产维护权限，但未有 assets.import。本工单只增加所需 assets.import，保留现有矩阵、OIDC 和本地恢复；不顺带撤权或重做身份管理。
- 0030_merge_export_identity 是现有合并迁移头；新增迁移须承接该头，不重写或删除历史分支。

## 范围与约束

1. 客户与现场UUID保持正式身份；名称只用于候选，不按名称自动合并、新增或覆盖。引用已有现场不改客户归属、位置、容量或产品线；差异原值与决定保留。
2. 新现场支持已提供产品线集合、PV MW、ESS MW/MWh及现有可空日期/状态。未知留空，不恢复并网年份或现场级停运检修；每现场一行可映射多产品线。
3. 各客户/现场行可填最多2000字符source_note，与业务备注分开；保留源文件、表行、原始/核对值、决定、操作者和业务映射。既有主数据引用的新来源独立保留，不覆盖旧备注。
4. 客户/现场/容量/来源/成功标记同事务；具备持久幂等键、请求摘要、revision、明确警告确认、发布前当前权限/事实重验及结果查询。每类最多500业务行，v2采用父规格批准的10 MiB XLSX/50 MiB展开/200成员/150000单元格限制；旧批次及v1按旧语义兼容。
5. 资产模块拥有写入；实验室和状态分析公开边界保留。测试主要走AssetImports/AssetDirectory公开应用接口连接真实隔离PostgreSQL，补关键浏览器验收和失败/并发回归。测试阈值、负载和故障不进入原验收库。

## 非目标与过度设计边界

不提前实现 #50 设备/物料新增、实验室批量导入、已有主数据覆盖或归属变更、服务工单、AI智能体、通用跨模块导入平台、新队列/付费服务/存储方案。复杂取消/租约恢复属于 #60；本工单基本原子性、幂等、原件保存与发布重验不得延期。现有现场基础编辑保持，不能把UPDATE伪装为导入引用。

## 工作区、外部动作和剩余事项

原 G: 工作区与 #18/#48/双main整合 worktrees、未提交文档和18148验收数据保持。此工作树不运行真实环境迁移。Gateflow后续按确认的目标进行计划、planreview、测试驱动实现、deepreview、draft PR及PR审查；ready/merge和外部收尾评论遵守额外授权要求，不开始后续工单。

没有新的阻塞业务问题；当前 stop condition 是 Gateflow 要求的用户目标确认，不是重新访谈已冻结需求。#47 与当前分析员定稿权限差异属于后续实验室工单，不在 #49 改动。真实Okta验收继续由 #18 跟踪。

Docs decision：本目标记录等待确认；计划中随本切片对齐现场可无设备、容量、来源备注等领域说明。原工作区未提交领域文档不能整体复制或覆盖。

Next entry point：用户确认后进入 plan；当前尚无实现、测试或PR变更。

