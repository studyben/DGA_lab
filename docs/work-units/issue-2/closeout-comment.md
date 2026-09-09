Issue #2 的工程基础已实现，交付于 draft PR https://github.com/studyben/DGA_lab/pull/21 。

- 完成双工作区 React/TypeScript 门户、FastAPI 三模块公开入口、PostgreSQL/Alembic 迁移和就绪检查、本地 Compose、真实 PostgreSQL 测试基座及 CI。
- 本地与 GitHub runner 已验证 11 项后端检查、4 项浏览器验收、TypeScript/生产构建；本地另验证了全新环境启动和数据库故障恢复。
- 审查发现 S2-1（/assets 路由与静态目录冲突）已修复并复审；没有未解决的已接受 findings。完整证据见 PR 中 docs/reviews 和 docs/work-units/issue-2。
- 剩余范围及负责人：#3 交付认证/权限/审计；#4–#19 交付相应业务能力；#20 交付 Lightsail、安全暴露、备份和恢复验收。本票本地 Compose 不可直接暴露公网。Docker Desktop 运行目录故障已通过保留备份的方式恢复；未来宿主环境维护仍需独立检查。
- PR 保持 draft，未自动合并或关闭本 Issue。PR body 已包含 Closes #2，合并到默认分支后预期自动关闭 #2。合并后下一开发入口为 #3，再按依赖推进 #4 → #5 → #6 → #7 → #8。
