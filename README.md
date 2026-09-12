# DGA Lab

中文现场资产与油样管理门户。当前交付 [Issue #2](https://github.com/studyben/DGA_lab/issues/2) 的工程基础，完整 MVP 规格见 [Issue #1](https://github.com/studyben/DGA_lab/issues/1)。

这是绿地项目的初始生产工程：#2 门户导航与测试基础，#3 本地账号、权限、会话和审计，#4 正式资产搜索，#5 油样收样与共享条码，以及 #6 条码检测工作台、类型化检测结果和原始附件已经实现。整体检测定稿和报告仍由后续工单交付；其他未实施业务页明确显示待开放，不展示原型假数据。

## 启动

安装并启动 Docker Desktop（Linux containers）或 Docker Engine 与 Compose v2+，在仓库根目录运行：

```sh
docker compose up --build -d --wait
```

打开 http://127.0.0.1:8080 。首次启动需要下载镜像/依赖；无需本机安装 Python、Node 或 PostgreSQL。端口占用时设置环境变量 `DGA_PORT=18080` 后执行同一命令。浏览器深链可直接访问 `/assets`、`/lab`、`/lab/workbench`；顶部提供两个工作区，状态分析归属资产侧栏。

```sh
docker compose ps
docker compose logs --tail=100 api migrate frontend
docker compose down
```

普通 `down` 保留数据库卷。请勿在要保留本地数据时加 `--volumes`。本地数据库开发凭据已在 Compose 中明确标记，只用于本机，只有前端端口绑定 127.0.0.1；数据库/API 不发布宿主端口。本地 HTTP 使用非 Secure cookie，仅用于开发；请勿将此 Compose 直接暴露公网。

### 首次初始化管理员

应用不会自动创建默认账号，也不包含固定登录密码。启动后，在自己的终端运行：

```sh
docker compose exec -it api python -m dga.shared.auth.cli bootstrap --username admin --display-name Administrator
```

按提示输入并确认 15–128 字符初始密码（输入不回显、不放在命令行参数中）。然后浏览器登录并强制修改初始密码，才能进入业务门户。bootstrap 在任何账号已存在时拒绝执行，不会重置或覆盖密码。不要把实际密码提交到 Git、截图或聊天中。

完整用户管理 UI 不在 #3 范围；管理员首次改密后可用交互命令添加账号：

```sh
docker compose exec -it api python -m dga.shared.auth.cli create-user --admin admin --username colleague --display-name Colleague --role field_engineer
docker compose exec -it api python -m dga.shared.auth.cli set-status --admin admin --user-id USER_UUID --status DISABLED
docker compose exec -it api python -m dga.shared.auth.cli set-roles --admin admin --user-id USER_UUID --role management_readonly
```

USER_UUID 使用创建账号时输出的 ID。所有管理命令都校验当前管理员权限；无自助注册或开放的用户创建 API。不要停用/降权最后一个管理员；账号恢复、密码重置与完整管理 UI 不在本票范围。

| 角色代码 | 初始能力 |
| --- | --- |
| system_admin | 所有当前能力，包括账号管理、审计读取 |
| asset_manager | 资产读写、状态分析读取 |
| lab_admin | 资产读取、实验室读写/定稿、状态分析读取 |
| analyst | 资产读取、实验室读写、状态分析读取 |
| field_engineer | 资产读取、状态分析读取 |
| management_readonly | 资产、实验室、状态分析读取 |

角色可叠加，权限取并集。写入/定稿等能力目前只建立授权契约，不表示对应业务已实现。前端按能力隐藏工作区或禁用子页，直接访问未授权路径有明确提示；后端模块公开入口仍独立校验，不信任前端角色声明。

## 运行与配置

nginx 提供 React/TypeScript 静态构建，并将 `/api/` 转发给 FastAPI；迁移任务成功后才启动 API。应用 readiness 成功后启动前端。PostgreSQL 17 使用命名卷。

- `DATABASE_URL`：后端必填，格式 `postgresql+psycopg://user:password@host:5432/database`。凭据可用 URL 编码，不能提交正式凭据。
- `BUSINESS_TIMEZONE`：默认 `America/Chicago`，必须是有效 IANA 时区。
- `DGA_PORT`：Compose 前端宿主端口，默认 8080；应用数据和测试数据有独立数据库与存储。
- `COOKIE_SECURE`：应用默认 true；本机 Compose 显式 false。生产必须使用 HTTPS + Secure cookie。
- `SESSION_HOURS`：绝对会话时长，默认 8，小于 1 或大于 24 拒绝启动。
- `AUTH_ALLOWED_ORIGINS`：逗号分隔的完整来源（协议、主机、端口），认证 POST 必须带匹配 Origin；同源浏览器会自动发送。部署时仅列允许的 HTTPS 地址。
- `OBJECT_STORE_ENDPOINT`、`OBJECT_STORE_BUCKET`、`OBJECT_STORE_ACCESS_KEY`、`OBJECT_STORE_SECRET_KEY`：共同配置一个 path-style S3 兼容对象存储；`OBJECT_STORE_REGION` 默认 `us-east-1`。四项缺失时普通检测数据仍可使用，但附件保存会明确失败且不会生成伪成功记录。本地 Compose 运行隔离 MinIO，生产凭据不得提交仓库。
- `GET /api/health`：数据库可连接且迁移版本匹配时 200 `{ "status": "ok", "database": "ok" }`；连接失败或未迁移时 503，字段均为 `unavailable`。不自动执行迁移，不输出数据库异常或凭据。
- `GET /api/modules`：登录且完成首次改密后返回获授权模块的稳定代码和标签；不是业务 CRUD。
- `/api/auth/login`、`/api/auth/password`、`/api/auth/logout`：POST；`/api/auth/session`：GET。会话 cookie 为 HttpOnly/SameSite=Lax，不放 localStorage；改密和退出需当前会话返回的 X-CSRF-Token。
- `/api/assets/access`、`/api/laboratory/access`、`/api/condition-analysis/access`：受保护的模块访问上下文，匿名 401、无权限/待改密 403，返回已验证 actor_id。不提供提前的业务 CRUD。
- `GET /api/assets/search?q=...&effective_at=...`：按完整或部分整机/变压器序列号搜索指定时点可关联的正式资产；重复序列号返回客户、现场、型号、状态、系统资产号和匹配原因供消歧，整机结果包含当时安装的可关联变压器。
- `GET /api/assets/{asset_id}/sampling-context?sampled_at=...`：按带时区的采样时间解析客户、现场和完整设备路径。两项查询均要求 `assets.read`，不提供资产编辑或导入。
- `POST /api/laboratory/samples`：以正式资产关联或明确的“身份待确认”方式登记油样；正式关联会保存采样时客户、现场、设备路径和序列号快照，一个油样可登记 1–20 个共享条码的样品容器。
- `GET /api/laboratory/samples/by-barcode/{barcode}`：扫描或输入油样条码取回同一组收样基本信息和容器；`POST /api/laboratory/samples/{barcode}/label-prints` 在调用浏览器打印前记录审计。两个 POST 均要求同源 Origin 和当前会话 CSRF。
- `GET /api/laboratory/workbench/{barcode}`：取回油样基础信息、容器、检测中状态、启用的方法配置和全部有效检测。`PATCH /api/laboratory/samples/{barcode}` 修正基础信息；`POST/PUT/DELETE /api/laboratory/samples/{barcode}/tests...` 新增、修改或逻辑删除 DGA、微水和击穿电压记录。重复检测是同一条码下的独立记录，不另建“复测”实体；ND 不保存数值，LT/GT 保存边界数值。正式 ASTM 方法编号、单位、精度和检出限当前明确待配置。

密码使用 Argon2id（19MiB、2 次、并行度 1）；只存哈希。会话为随机不透明凭据，数据库只存会话凭据 SHA-256。退出撤销当前会话，改密撤销全部旧会话并创建新会话；停用/锁定撤销旧会话，重新启用不会复活它们。每次请求读取当前状态/角色。连续 5 次错误密码后账号临时限制 15 分钟；接口不透露账号是否存在。前端每 30 秒及重新聚焦时检查会话，后端每次请求校验，因此撤销后的数据接口立即受限。

审计只追加（登录成功/失败、退出、密码变更、账号/角色/状态操作，以及收样、资产关联、条码打印），通过受权共享公开查询读取。未匹配账号的失败登录 actor 为空，另保存声称的用户名；不伪造用户 ID，不记录密码/会话/CSRF。结构化非法请求在认证前返回通用错误，不回显输入。审计查询为最小 operator/application 接口，无审计管理 UI。生产还需 #20 的 TLS、反向代理级限流、监控和最小数据库权限；应用内账号节流不替代外围防滥用。

未来 Lightsail 的外部托管数据库、对象存储、worker 和备份配置由 #20 与对应业务工单提供，本地 Compose 不作为生产配置。

## 测试

```sh
docker compose --profile test run --build --rm api-test
docker compose -f compose.browser.yaml up --build -d --wait frontend
docker compose -f compose.browser.yaml --profile test run --build --no-deps --rm browser-test
```

API 测试会启动独立 `test-db` PostgreSQL，先执行与应用一致的 Alembic migration，然后从 HTTP/公开应用接口观察行为。测试 URL 限制为 test-db/dga_test/dga_test，避免误迁移应用数据。测试存储为 tmpfs，停止后不保留。当前 migration downgrade 验证按串行执行；请勿对同一 test-db 并发运行多份套件。不同开发任务可使用不同 Compose project name 隔离。

浏览器套件使用独立 dga-browser Compose 项目、临时 PostgreSQL 和匹配版本的 Playwright Linux 镜像，在 18080 提供测试门户。fixture 脚本严格拒绝非 dga_browser 数据库；测试账号仅存在于此隔离环境，不在正常应用中生成。验证登录/权限、Logo、导航与服务重试，并覆盖正式资产搜索、收样条码，以及扫码后连续新增两份 DGA、修改和删除。附件的失败原子性在共享文件端口使用测试实现验证，浏览器套件不替代对象存储验收。失败重试仅在 HTTP 外部边界注入 503，其余走真实 API；不依赖 React 组件树、CSS 类名或内部表。

首次改密测试会改变测试账号密码。重复执行前，仅重置隔离 fixture（不能用于正常应用）：

```sh
docker compose -f compose.browser.yaml run --rm --no-deps migrate python -m tests.seed_browser
docker compose -f compose.browser.yaml --profile test run --build --no-deps --rm browser-test
docker compose -f compose.browser.yaml --profile test down
```

开发者也可在 `frontend/` 运行 `npm ci`、`npm run build`。`npm run dev` 启动 5173，默认把 `/api` 代理至已运行的本地 Compose 8080；若修改 DGA_PORT，相应调整 Vite 开发代理。CI 使用上述容器命令，构建包含 TypeScript 检查。

## 模块边界

| 目录/公开入口 | 所有权 | 可调用的其他业务模块 |
| --- | --- | --- |
| `backend/dga/assets/public.py` | 正式资产身份、现场和设备生命周期 | 无 |
| `backend/dga/laboratory/public.py` | 油样、检测、整体检测定稿、条码报告 | assets.public |
| `backend/dga/condition_analysis/public.py` | 趋势、阈值、报警、健康派生 | assets.public、laboratory.public |
| `backend/dga/shared/` | 配置、基础设施与公共协作类型 | 无 |
| `backend/dga/main.py` | 运行时组装、HTTP 入口 | 各模块公开入口 |

资产公开入口还提供 `AssetDirectory.search` 和 `AssetDirectory.resolve_sampling_context` 两个只读查询；实验室模块复用资产模块拥有的正式资产选择器和 HTTP 适配器，不读取资产私有表。共享身份的公开服务提供认证和 operator 命令，已验证的不可变 ActorContext 由可信组装层传给业务模块；不得从请求 JSON 构造角色/权限上下文。跨模块只允许显式 public import；禁止动态 import/反射绕过检查，禁止调用对方内部实现或直接读写对方私有持久化。`backend/architecture.py` 验证绝对/相对 import 及依赖方向。

前端的三个 `features/` 目录分别拥有页面定义，门户外壳负责导航和公共布局。`/assets` 是业务路由，构建静态文件必须放在 `/static`，避免 nginx 目录冲突。

## 数据库演进

首个 Alembic migration 是空业务 schema 基线；0002 增加身份与审计；0003 增加正式资产和安装关系；0004 增加油样、身份快照、共享条码和容器；0005 增加检测中状态、只读方法版本、通用检测头、三类一对一结果表及对象元数据。序列号刻意不唯一，系统资产号唯一。0005 只提供待配置的方法占位，不预置未经确认的 ASTM 参数；完整配置管理属于 #14。downgrade 仅允许隔离测试库使用，已有真实数据的环境不得执行。

```sh
docker compose run --rm migrate alembic current
docker compose run --rm migrate alembic upgrade head
```

升级前备份重要数据；downgrade 必须按具体业务 migration 评估，本票仅在隔离测试库演练空基线 downgrade。迁移文件位于 `backend/migrations/`，通过修改后构建镜像分发；源码可在安装锁定依赖后运行 Alembic 创建 revision。

依赖由 `backend/requirements.in` 和 `frontend/package.json` 声明，分别使用带哈希的 requirements.txt 与 package-lock.json 锁定。更新 Python 依赖时在 Python 3.12 环境执行 `pip-compile --generate-hashes --output-file backend/requirements.txt backend/requirements.in`，之后验证 Linux 镜像；不要手改哈希。

## Issue #12：新增资产批量导入

管理员在 `/assets/import` 下载固定 XLSX 模板和已有客户/现场/物料参考资料，上传后查看后台校验结果。仅新增资产及初始安装关系，不更新、合并或覆盖既有资产，也不通过文件创建客户、现场或物料。新资产ID和系统资产编号自动生成。序列号重复不是唯一性错误；页面列出冲突资产编号/型号并要求确认这些是不同物理设备。

模板 `Assets` 的必填列为 `record_key, serial_number, material_number, product_line, machine_type, status, location_kind, effective_at`。可选列见模板 Instructions。`parent_record_key` 只指向本批次中的父记录，不按序列号关联。已有父设备下的新部件，可先导入维修中心，再使用已有受控资产移动功能安装。直接归属现场仅允许光伏整机/储能系统；维修中心不填写客户/现场。导入只接收当前开放关系，不接收关系结束日期或多段历史。

- 输入上限：2 MiB XLSX、展开10 MiB、100个ZIP成员、500条资产行、全文件20000个单元格（包括参考表）、每单元格1000字符。参考表各列前500条，可删除参考表但需保留 Assets。拒绝公式、宏、外链、加密、空文件、重复列名、未知字段、远处隐藏数据，不做任意格式识别。
- 标识使用文本保留前导零。`effective_at` 填带时区的 ISO 日期时间，如 `2025-01-01T08:00:00Z`；不允许未来时间。`commissioning_date` 使用 `YYYY-MM-DD`。MW/MWh 最多6位小数，PV 的 MWh 留空。
- 只有 `assets.import` 权限可以访问导入入口/API，迁移默认仅授予 system_admin；一般 `assets.write` 不等于导入权限。所有HTTP写操作校验Origin/CSRF。
- `STAGED` 等待后台校验；`VALIDATED` 可包含错误/警告；`FAILED` 保留失败诊断和源文件；`PUBLISHED` 保留发布结果。错误阻止整批发布，警告需明确勾选确认。发布时重新校验当前主数据；预览变化会要求再次确认。并发/重试发布返回同一组资产，不重复创建。
- 修正后上传新批次，旧批次和源文件保留。发布超时不能认定失败：先刷新该批次确认状态。数据库行写入、安装关系、批次结果和成功审计处于同一事务，任一失败全部回滚，不跳过坏行。

### 物料与迁移注意事项

`0013_asset_import` 增加物料目录和导入批次。只从已有资产中迁移非空、完全一致的物料/型号/资产类型映射；歧义或缺失映射不会猜测修复，原资产不变。空数据库需要管理员先准备客户、现场产品线和物料目录，否则导入会明确报缺失引用。此工单不提供新的主数据维护页面。存在保留批次时，降级迁移会拒绝静默丢弃导入审计。

### 后台进程与失败恢复

普通 `compose.yaml` 包含 `import-worker`，执行 `python -m dga.assets.import_worker`；`--once` 处理最多一个批次，供操作检查使用。进程用数据库行锁领取待校验批次：崩溃释放锁，下一次继续处理；异常校验记录失败码，不无限重试同一个坏批次。长时间处于 STAGED 时先检查 worker 日志与数据库可用性。恢复后对于 FAILED 文件重新上传，不手改批次状态。

源文件使用既有 S3 兼容 FileStore，配置沿用 `OBJECT_STORE_*`。对象存储失败不生成可发布批次；上传成功后数据库写入失败会尝试删除该次孤立对象，删除失败日志记录对象键供管理员核对。S3与PostgreSQL不是分布式事务；生产源文件保留、备份与孤立对象清理由部署 #20 运维策略负责，不自动删除已发布源文件。

隔离验收可使用 `compose.browser.yaml` 加 `compose.import-browser.yaml`，项目名 `dga-issue12-browser`、`DGA_BROWSER_PORT=18095`；它使用临时测试数据和独立MinIO，**不可与现有验收 override 混用**。`tests.seed_import_browser` 只用于隔离假数据，不用于用户验收库。浏览器输入fixture由 `python -m tests.make_import_fixture <frontend/tests/fixtures/asset-import.xlsx>` 生成。后端行为测试使用 `dga-issue12` 的 `test-db`，不使用18093数据。

## 交付顺序

#2 工程基础 → #3 登录/权限/审计身份 → #4 资产搜索/采样上下文 → #5 收样条码 → #6 检测录入 → #7 整体定稿 → #8 条码报告。随后按依赖补全 #9–#19，#20 完成部署和恢复验收。服务工单、ASTM 编号、正式阈值和 PDF 品牌细节不在本票范围。
