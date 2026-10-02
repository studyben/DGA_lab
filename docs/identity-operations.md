# Issue #18 用户管理、恢复与 OIDC 联调手册

状态：独立实现与隔离验收；真实 Okta 尚未验收。不得仅凭自动化测试关闭 #18。不包含 #19 导出或 #20 生产部署实施。

## 权限与操作

所有六种角色都可读取三个业务模块。同一账号多角色取并集；UI 提供入口不是授权依据，公开应用接口仍校验当前权限。

| 能力 | 系统管理员 | 实验室经理 | 分析员 | 现场工程师 | AM | 管理层 |
| --- | --- | --- | --- | --- | --- | --- |
| 现场基础资料编辑 | 是 | 是 | 否 | 否 | 是 | 是 |
| 资产/安装/更换与历史修正 | 是 | 是 | 否 | 否 | 否 | 否 |
| 资产批量导入 | 是 | 否 | 否 | 否 | 否 | 否 |
| 油样/检测/整体定稿 | 是 | 是 | 是 | 否 | 否 | 否 |
| 实验室配置、健康规则 | 是 | 是 | 否 | 否 | 否 | 否 |
| 报警确认 | 是 | 是 | 是 | 是 | 否 | 否 |
| 安全审计读取 | 是 | 是 | 否 | 否 | 否 | 否 |
| 完整账号管理、OIDC 配置、恢复停用账号 | 是 | 否 | 否 | 否 | 否 | 否 |
| 普通账号资料/普通角色/停用/解锁 | 是 | 是 | 否 | 否 | 否 | 否 |
| 普通账号 AM 角色增减 | 是 | 是 | 否 | 否 | 否 | 是 |

普通账号不含系统管理员/实验室经理角色，也不属于本地恢复账号。管理层只能增减 AM，不改其他角色、资料或状态。非系统管理员不得修改自身角色。LOCKED 可由获准管理员解锁；DISABLED 只允许系统管理员恢复。密码失败冷却不是账号停用。所有写入以当前账号修订号校验，409 应先重读再核对，不能重试覆盖。

现场编辑仅改名称、位置、并网调试/投运状态、commissioning date、已有产品线 MW/MWh。不能修改客户归属、添加产品线或移动设备；历史油样快照不跟随更新。已移除的并网年份不恢复。

## 升级与旧角色

1. 备份 PostgreSQL、对象存储和部署机密；确认可以恢复，禁止在正式/用户验收数据库运行 `tests.seed_*`。
2. 新代码镜像在升级前对旧数据库执行只读报告：`docker compose run --no-deps --rm api python -m dga.shared.auth.cli role-impact`。报告含账号信息，按内部资料保护。逐账号核对 added/removed permissions，得到操作者确认后才升级。新代码正常业务 API 在旧 schema 上不可使用。
3. 执行所选环境的 `alembic upgrade head`，再部署新 API/前端；不要复制示例 Compose 的本地数据库到生产。链为 0024 → 0025 角色 → 0026 账号管理 → 0027 现场资料 → 0028 OIDC → 0029 候选回调。只有一个 head。
4. 旧角色/账号 UUID/密码/会话身份保留，新的权限矩阵立即生效；旧 management_readonly 不映射、不删除，也不能再分配。核对本地恢复管理员登录与审计。
5. 0028 旧候选没有冻结回调地址，0029 保留记录但明确拒绝使用；须在页面新建候选、重新测试和启用。不猜测旧地址或重新标记测试成功。

这些迁移保留安全证据，禁止通过自动 downgrade 删除审计/外部账号。回退采用经过演练的备份恢复或前向修复，不提供“reset”捷径。容器重建应连接原持久数据库及原密钥，不运行 bootstrap 覆盖已有账号。

## 本地恢复

首次空库初始化：`docker compose exec -it api python -m dga.shared.auth.cli bootstrap --username admin --display-name Administrator`。

已存在本地管理员遗失密码：可信服务器维护人员执行 `docker compose exec -it api python -m dga.shared.auth.cli recover-admin --username admin`，交互输入新初始密码；密码不放命令行、不提交日志。命令会撤销旧会话、解除登录冷却/LOCKED，要求登录后改密；不创建新管理员，不恢复 DISABLED。

恢复账号被停用时，应由另一个有效系统管理员明确恢复。最后一个启用的本地密码管理员不能被停用、锁定或降权。`/login/local` 不请求 Okta 可用性；仍需正确本地凭据，保留失败防护。既有普通本地密码账号仅作受控迁移兼容，不提供新普通本地账号注册。修改密码撤销旧会话并轮换当前凭据，但保留原会话到期时间，不视作重新登录；即使关联账号仍有本地密码，也不能借改密延长 OIDC 八小时上限。

## IT 与部署配置清单

- 独立的测试应用、测试员工分配，以及最终正式应用的归属/审批；不要复用正式员工和生产机密做自动化测试。
- IT 提供 issuer、client ID、client secret；应用类型为后端 Web 应用，Authorization Code，PKCE S256，客户端认证 secret basic；scope openid/profile/email，不请求 offline_access/refresh token。不假设付费自定义授权服务器或 `/oauth2/default`。
- 注册完整回调，例如 `https://<批准的应用域名>/api/auth/oidc/callback`。页面修改不会更新 Okta 注册，两端须一致。
- 部署环境：`OIDC_ENCRYPTION_KEY` 为 Fernet 密钥；`OIDC_ALLOWED_HOSTS` 为精确 Okta 主机名（逗号分隔、不带协议/通配符）；`OIDC_CALLBACK_ORIGINS` 为允许的完整应用 origin；`OIDC_CALLBACK_URL` 可选，仅为新候选默认值。未设置 origins 时，显式 default callback 的 origin 是唯一允许项。密钥和允许列表缺失时 OIDC 禁用，不影响本地恢复。
- `AUTH_ALLOWED_ORIGINS` 同时允许该应用 origin；生产必须 HTTPS 且 `COOKIE_SECURE=true`。仅本机 localhost/127.0.0.1/::1 可用 HTTP 回调。浏览器从与候选回调相同的 origin 发起登录；不共享跨域 Cookie。
- 候选 issuer、metadata 的授权/token/JWKS 主机全部须在允许列表；拒绝重定向和非 HTTPS 端点。代理须允许这些出站 HTTPS 请求；不通过跳过 TLS 或放宽 URL 校验解决联调失败。
- 开发 Compose 仅 API 显式接收以上 OIDC 环境变量。生产 Docker 注入仍由部署人员按 #20 安全方案配置，不能将开发 Compose 暴露公网。无须新增付费服务或改变对象存储。

加密密钥应在受控终端生成并通过受保护的部署机密注入，单独备份和限制访问；不要贴到 GitHub、聊天、截图或命令参数中。数据库中只有加密 secret；配置读取不会回显。丢失原密钥时恢复备份密钥，或使用本地管理员重新建立候选并测试；不要直接替换密钥后声称旧密文可用。Client secret 轮换需保留原 secret 有效至新候选真实测试/启用成功，再由 IT 撤销原 secret。当前不提供在线批量重加密旧候选；Fernet 主密钥轮换需单独受控维护与备份计划。

## 页面验收顺序

1. 本地恢复管理员登录 `/login/local`，进入“用户与角色”，检查搜索/状态/角色及按角色限制的操作。保留一个可用本地管理员。
2. `/settings/sso` 保存 IT 提供的候选。核对回调，确认当前生效项不变且 secret 不回显。
3. 点击“测试登录”，在 Okta 用已分配的测试员工验证。返回后本地管理员仍在登录，未自动启用；只有该管理员在十五分钟内可以明确启用。
4. 新浏览器会话从登记域名使用 Okta 登录：首次为现场工程师；管理员另行分配角色后，后续登录保留；邮箱/姓名变化不改变 issuer/sub 对应 UUID。
5. 同名现有账号应拒绝自动合并。管理员完成员工身份测试，在“核验并关联已有账号”明确选账号和 subject；角色和状态保持原值，已绑定身份不能覆盖。
6. 本系统停用员工应立即阻止旧会话和新登录；仅系统管理员恢复。对最后一个本地恢复管理员的停用/降权应失败。
7. IT 撤销应用分配及停用测试员工，分别验证新登录失败；既有会话最迟在成功验证后八小时失效，活动/刷新不得延长。紧急撤权同时在本系统停用。固定八小时是产品接受的上限，不承诺 Okta 撤权立即撤销既有本地会话。
8. 验证错误候选、不匹配回调、过期证明、Okta 不可用仍保留当前配置和本地恢复入口。恢复后可重新测试新候选。

真实证据记录：环境/登记 origin、候选ID（不含secret）、测试时间、执行人与 IT 确认人、测试账号内部ID/受控外部subject、场景、预期/实际、会话创建及到期时间、通过/失败、待处理责任人。不得记录授权码、token、Cookie、client secret。真实证据未完成不得填写“Okta验收通过”，PR 不应使用 Closes #18。

## 故障与日志

页面遇到 `oidc_callback_origin_mismatch`：从已登记应用地址重新登录；不要改浏览器Cookie范围。`oidc_key_unavailable`：恢复部署原密钥。`oidc_test_required`：同一管理员重新测试精确候选。`stale_oidc_configuration`：重读现行配置，不自动覆盖。`oidc_link_required`：管理员核验身份，不按邮箱自动合并。`oidc_provider_rejected`：核对 IT 注册、分配、端点允许列表及网络，不将远端原始错误直接展示或写日志。

OIDC 代理前缀仅记录无 URL/query 的方法、状态、上游状态和耗时；该前缀关闭 Nginx 原始 error channel（会附加完整 request line），应用访问日志过滤 query。使用安全失败码/审计和状态定位，不开启该前缀 debug/raw-request logging。新隔离环境已注入上游超时，普通与尾斜杠回调均保留504状态而不记录探针code/state。生产若另加边缘代理/访问日志，必须独立验证同样脱敏。

## 独立自动化环境（非真实 Okta）

本任务新建 `dga-issue18-test`（临时 PostgreSQL）与 `dga-issue18-browser`（18118），不使用原18117/18120验收数据。`compose.browser.yaml` 是新建临时环境专用，默认 migrate 会 seed，禁止用于原验收项目。已运行环境仅重建 API/前端时用 `--no-deps`，迁移显式运行，不重新 seed。

API 容器重建后，当前 Nginx 静态上游可能仍保存旧容器 IP。API 健康后，在**同一项目**执行 `docker compose ... exec frontend nginx -s reload`，再检查经前端的 `/api/health` 返回200，而不是仅检查静态首页。省略号表示该环境原有的 `-p`/`-f` 参数，不能省掉项目隔离参数直接操作其他环境。实测重建后502可通过仅重载该隔离代理恢复200，不需要重置数据库或修改鉴权检查。

`compose.oidc-test.yaml` 仅测试 overlay，明确以 `tests.oidc_browser_app:app` 启动签名 JWT 协议夹具；正式入口始终是 `uvicorn dga.main:create_app --factory`，没有 HTTP/env 开关绕过验证。测试浏览器把 Docker 内网传输映射到登记 loopback origin，因而它只验证页面/服务交互，不证明实际域名、TLS、Okta分配或第三方Cookie行为。完成测试后移除此 overlay 并恢复正常 API 入口；不要把夹具的公开测试密钥当部署机密。

参考：[Okta 后端授权码与 PKCE](https://developer.okta.com/docs/guides/implement-grant-type/authcodepkce/main/)、[Authlib OAuth 客户端](https://docs.authlib.org/en/stable/oauth2/client/http/index.html)。库当前支持的弃用提示已记录；不为消除提示升级整个 HTTP 栈，主版本更新前需重新验证协议适配器。
