# PR draft — Issue #48（仅本地，尚未发布）

## Title
feat: download complete current site reference workbook

## Body
Closes #48

为现场列表和资产导入页增加“下载当前现场汇总”。输出所有可读物理现场（含无设备、无产品线现场），不受筛选、分页或PV/ESS切换影响；双产品线仅一行，容量分别列出。使用现有UUID、稳定机器列名和中文说明，精确保留容量文本与未知空值。

资产公开接口拥有一致快照/工作簿与assets.read授权；HTTP负责完整文件下载及断开清理。新增最小可选审计metadata记录生成范围、数量、操作者和时间，保留旧事件及升级路径，审计只表示已准备下载。当前source_note缺写入来源时为空，后续#49/#50/#61接入。

验证：真实隔离PostgreSQL全量303passed；40既有MinIO/Azurite合同测试因未启动对应环境skip；TypeScript/Vitebuild通过；10Playwright浏览器测试通过，另最新API重启后真实下载复验通过。覆盖603现场、空数据/零容量、多产品线去重、快照并发、公式文本、高精度、权限、审计失败、磁盘写失败/临时文件、断开/超时、旧数据升级与拒绝破坏性降级。Planreview/slice/deepreview accepted findings全部已修复。

边界：导出超过Excel单表原生行数上限时明确失败。未运行远程CI或PRreview；原工作区改动/验收数据保留。本文件尚未发送GitHub，不执行后续工单。
