# Issue #48 本地交付与验收

状态：本地计划、计划审查、TDD实现、切片审查和整体deepreview完成。Gate停在ready-to-open-draft-PR；依用户指示未push、未创建PR、未merge、未修改GitHubIssue，未开始后续工单。不能宣称draft-PR-pass/final-closeout pass。

## 交付
- 现场列表与导入页都有“下载当前现场汇总”，输出全部可读现场XLSX，每现场一行，包含无设备/无产品线现场。筛选、分页和PV/ESS切换不限制导出。
- 导出site/customer现有UUID、名称/位置、产品线与分开容量、CommissioningDate、调试/投运状态、来源备注空列；未知不置零，无并网年份。固定机器列名+中文Instructions+UTC生成时间/范围/数量，文字不执行公式，容量精确保留十进制文本。
- assets.read授权；完整生成和audit提交后才提供下载。HTTP成功/失败/断开关闭文件；UI有busy、失败/重试和取消清理。audit只表明已准备提供下载，不声称用户已保存。
- migration0025在现有append-only审计上增加可选objectmetadata，旧记录{}，不允许降级丢失非空metadata。

## 证据
- Base68e4d278e3e2a6b3e976036e3581b3ff2a7a773a；branch codex/issue-48-site-export。
- Local checkpoints: acceptedplan9c4e8c5；S1 1a872d1；S2 14b1952；S3 063a556；accepteddeepreview ddf1b98。
- Aggregate re-review: docs/reviews/code-review-20261029-004755.md。Plan P1/P2、S1-R1、S3-R1、AG-R1/R2均accepted→已修复，无未裁决finding/blocker。
- Backend303passed/40skip/2既有弃用warnings。真实PostgreSQL17隔离cluster18448，APItest dga_test和browser dga_browser明确分开，既有保护guard未削弱。
-40skip为既有对象存储S3/Azure模拟服务合同测试，本机未启动对应环境；导出不依赖对象存储。未将skip算作pass。
- npm run build通过；10Playwright通过（8导出/失败边界+2原dashboard回归）；最新后端重启后的真实下载再1pass，落盘XLSX用openpyxl独立确认筛选外两现场及中文legend。1920×1080/1366×768截图人工检查。
- 原G:/Sungrow Develop/DGA Lab仍main及既有CONTEXT.md/PROJECT_PLAN.md修改和未跟踪目录，未暂存/提交/清理；原验收数据库/卷未迁移/seed/重置。仅本工单忽略.cache目录内建独立验证运行时。

## 本地验收（独立测试夹具）
访问 http://127.0.0.1:18148/assets 。此环境为本工单新建测试数据，非原验收数据；API18449、独立PostgreSQL18448。辅助进程为临时本地测试进程，重启电脑后不保证继续运行。

- 现场工程师：field-user
- 管理员：browser-admin
- 上述测试账号密码均为：Browser changed passphrase 84!

1. 用field-user登录现场列表，切储能、填一个查不到的现场关键词或改变分页，点击“下载当前现场汇总”。文件仍包含Prairie Sun与Desert Star两个现场，非筛选结果；UUID是文本，双产品线现场只占一行。
2. 打开Instructions，核对中文字段/状态说明、生成时间、all_readable_sites及数量2；容量未知为空，PV/ESS容量分列，无grid_year。
3. 用browser-admin登录/assets/import，同一按钮下载相同范围；原有“下载Excel模板与参考资料”保留独立功能。
4. 可检查下载过程中禁用与完成提示。401/403/503/网络/超时/会话失效卸载、磁盘/审计失败及数据并发等由自动化隔离测试覆盖，无需改动原验收数据复现。

## 后续边界
来源备注业务写入归#49/#50/#61；超过Excel原生行数上限明确失败，大规模替代输出不在当前工单。远程CI、draftPR及PR审查属于后续Gateflow入口；本地PR正文已准备在issue-48-pr-draft.md，含Closes #48但尚未发布。用户未授权前不推进这些动作。

## 更新：用户选择跳过人工验收

用户已明确授权继续#48 PR阶段，暂不合并。上述“仅本地/未push”是前一交付点的状态；以issue-48-progress.md和后续PRreview/closeout artifact为准。人工验收没有执行，不将自动化通过表述为用户验收通过。
