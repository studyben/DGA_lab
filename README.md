# DGA Lab

[中文](#中文--chinese) · [English](#english)

## 中文 / Chinese

中文现场资产与油样管理门户。当前交付 [Issue #2](https://github.com/studyben/DGA_lab/issues/2) 的工程基础，完整 MVP 规格见 [Issue #1](https://github.com/studyben/DGA_lab/issues/1)。

这是绿地项目的初始生产工程：#2 门户导航与测试基础，#3 本地账号、权限、会话和审计，#4 正式资产搜索，#5 油样收样与共享条码，#6 条码检测工作台、类型化检测结果和原始附件，#7 整体检测定稿，以及 #8 条码中文报告已经实现。其他未实施业务页明确显示待开放，不展示原型假数据。

### 启动

安装并启动 Docker Desktop（Linux containers）或 Docker Engine 与 Compose v2+，在仓库根目录运行：

```sh
docker compose up --build -d --wait
```

打开 http://127.0.0.1:8080 。首次启动需要下载镜像/依赖；无需本机安装 Python、Node 或 PostgreSQL。端口占用时设置环境变量 `DGA_PORT=18080` 后执行同一命令。浏览器深链可直接访问 `/assets`、`/lab`、`/lab/workbench`、`/lab/reports`；顶部提供两个工作区，状态分析归属资产侧栏。

```sh
docker compose ps
docker compose logs --tail=100 api migrate frontend
docker compose down
```

普通 `down` 保留数据库卷。请勿在要保留本地数据时加 `--volumes`。本地数据库开发凭据已在 Compose 中明确标记，只用于本机，只有前端端口绑定 127.0.0.1；数据库/API 不发布宿主端口。本地 HTTP 使用非 Secure cookie，仅用于开发；请勿将此 Compose 直接暴露公网。

#### 首次初始化管理员

应用不会自动创建默认账号，也不包含固定登录密码。启动后，在自己的终端运行：

```sh
docker compose exec -it api python -m dga.shared.auth.cli bootstrap --username admin --display-name Administrator
```

按提示输入并确认 15–128 字符初始密码（输入不回显、不放在命令行参数中）。然后浏览器登录并强制修改初始密码，才能进入业务门户。bootstrap 在任何账号已存在时拒绝执行，不会重置或覆盖密码。不要把实际密码提交到 Git、截图或聊天中。

Issue #18 提供 `/settings/users` 用户与角色管理。新建本地密码账号仅用于管理员恢复；普通员工首次通过 OIDC 登录创建账号，既有本地普通账号保留用于受控迁移。管理员首次改密后也可用交互命令：

```sh
docker compose exec -it api python -m dga.shared.auth.cli create-user --admin admin --username recovery --display-name Recovery --role system_admin
docker compose exec -it api python -m dga.shared.auth.cli set-status --admin admin --user-id USER_UUID --status DISABLED
docker compose exec -it api python -m dga.shared.auth.cli set-roles --admin admin --user-id USER_UUID --role field_engineer
```

USER_UUID 使用用户详情接口或创建命令返回的 ID。所有管理命令都校验当前权限；无自助注册。系统保护最后一个启用且有本地密码的管理员。恢复、迁移影响报告及 OIDC 配置见 [Issue #18 操作手册](docs/identity-operations.md)。本地模拟测试不代表真实 Okta 验收，#18 仍须完成 IT 联调。

| 角色代码 | 初始能力 |
| --- | --- |
| system_admin | 所有当前能力，包括账号管理、审计读取 |
| asset_manager | 三模块读取、现场基础资料编辑 |
| lab_admin | 实验室经理：资产维护、实验室写入/定稿/配置、规则维护、报警确认、审计读取、普通用户管理 |
| analyst | 三模块读取、实验室写入/定稿、报警确认 |
| field_engineer | 三模块读取、报警确认；首次 OIDC 登录默认角色 |
| management | 三模块读取、现场基础资料编辑、普通用户 AM 角色增减 |
| management_readonly | 历史兼容读取角色，保留既有分配，不再新增分配 |

角色可叠加，权限取并集。尚未交付的能力仍可能只有授权契约，不表示对应业务已经实现。前端按能力隐藏工作区或禁用子页，直接访问未授权路径有明确提示；后端模块公开入口仍独立校验，不信任前端角色声明。

### 运行与配置

nginx 提供 React/TypeScript 静态构建，并将 `/api/` 转发给 FastAPI；迁移任务成功后才启动 API。应用 readiness 成功后启动前端。PostgreSQL 17 使用命名卷。

- `DATABASE_URL`：后端必填，格式 `postgresql+psycopg://user:password@host:5432/database`。凭据可用 URL 编码，不能提交正式凭据。
- `BUSINESS_TIMEZONE`：默认 `America/Chicago`，必须是有效 IANA 时区。
- `DGA_PORT`：Compose 前端宿主端口，默认 8080；应用数据和测试数据有独立数据库与存储。
- `COOKIE_SECURE`：应用默认 true；本机 Compose 显式 false。生产必须使用 HTTPS + Secure cookie。
- `SESSION_HOURS`：本地密码登录的绝对会话时长，默认 8，小于 1 或大于 24 拒绝启动。OIDC 会话固定为最近一次成功验证后 8 小时，不随此值改变、不滑动续期。
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
- `PUT /api/laboratory/samples/{barcode}/report-result`：同类型存在多份有效检测时选择该条码报告采用的结果；只有一份时整体定稿自动选择。`POST /api/laboratory/samples/{barcode}/finalization` 执行整体检测定稿，身份待确认、没有有效检测、缺少多结果选择或未确认 QA 警示时返回结构化阻塞原因；定稿后基础信息、检测和报告结果选择均只读。
- `POST /api/laboratory/samples/{barcode}/finalization-withdrawals`：具有 `laboratory.finalize` 权限的人员填写原因后撤回定稿并恢复编辑；条码标签仍可重打，当前报告同步失效。
- `GET /api/laboratory/reports/by-barcode/{barcode}`：查询当前条码报告的不可用、排队、生成中、就绪或失败状态；`POST .../retry` 由具有定稿权限的人员安全重试失败任务；`GET .../file?disposition=inline|attachment` 代理返回校验过 SHA-256 的当前 PDF。未定稿不出报告，撤回后旧文件不可访问，重新定稿只替换当前报告，不显示版本历史。独立 `report-worker` 从 PostgreSQL 领取带租约的任务，将中文简版报告写入 S3 兼容对象存储。

密码使用 Argon2id（19MiB、2 次、并行度 1）；只存哈希。会话为随机不透明凭据，数据库只存会话凭据 SHA-256。退出撤销当前会话，改密撤销全部旧会话并创建新会话；停用/锁定撤销旧会话，重新启用不会复活它们。每次请求读取当前状态/角色。连续 5 次错误密码后账号临时限制 15 分钟；接口不透露账号是否存在。前端每 30 秒及重新聚焦时检查会话，后端每次请求校验，因此撤销后的数据接口立即受限。

审计只追加（登录成功/失败、退出、密码变更、账号/角色/状态操作，以及收样、资产关联、条码打印、检测变更、报告结果选择、定稿尝试与撤回），通过受权共享公开查询读取。未匹配账号的失败登录 actor 为空，另保存声称的用户名；不伪造用户 ID，不记录密码/会话/CSRF。结构化非法请求在认证前返回通用错误，不回显输入。审计查询为最小 operator/application 接口，无审计管理 UI。生产还需 #20 的 TLS、反向代理级限流、监控和最小数据库权限；应用内账号节流不替代外围防滥用。

未来 Lightsail 的外部托管数据库、对象存储和备份配置由 #20 提供；本地 Compose 已包含报告 worker，但不作为生产配置。

### 测试

```sh
docker compose --profile test run --build --rm api-test
docker compose -f compose.browser.yaml up --build -d --wait frontend
docker compose -f compose.browser.yaml --profile test run --build --no-deps --rm browser-test
```

API 测试会启动独立 `test-db` PostgreSQL，先执行与应用一致的 Alembic migration，然后从 HTTP/公开应用接口观察行为。测试 URL 限制为 test-db/dga_test/dga_test，避免误迁移应用数据。测试存储为 tmpfs，停止后不保留。当前 migration downgrade 验证按串行执行；请勿对同一 test-db 并发运行多份套件。不同开发任务可使用不同 Compose project name 隔离。

浏览器套件使用独立 dga-browser Compose 项目、临时 PostgreSQL、临时 MinIO、真实报告 worker 和匹配版本的 Playwright Linux 镜像，在 18080 提供测试门户。fixture 脚本严格拒绝非 dga_browser 数据库；测试账号仅存在于此隔离环境，不在正常应用中生成。验证登录/权限、Logo、导航与服务重试，并覆盖正式资产搜索、收样条码、检测录入与整体定稿，以及未定稿不可出报告、异步生成、在线预览、下载、撤回失效和重新定稿重建当前报告。附件的失败原子性在共享文件端口使用测试实现验证；失败重试和待确认 QA 警示仅在 HTTP 外部边界注入，其余走真实 API，不依赖 React 组件树、CSS 类名或内部表。

首次改密测试会改变测试账号密码。重复执行前，仅重置隔离 fixture（不能用于正常应用）：

```sh
docker compose -f compose.browser.yaml run --rm --no-deps migrate python -m tests.seed_browser
docker compose -f compose.browser.yaml --profile test run --build --no-deps --rm browser-test
docker compose -f compose.browser.yaml --profile test down
```

开发者也可在 `frontend/` 运行 `npm ci`、`npm run build`。`npm run dev` 启动 5173，默认把 `/api` 代理至已运行的本地 Compose 8080；若修改 DGA_PORT，相应调整 Vite 开发代理。CI 使用上述容器命令，构建包含 TypeScript 检查。

### 模块边界

| 目录/公开入口 | 所有权 | 可调用的其他业务模块 |
| --- | --- | --- |
| `backend/dga/assets/public.py` | 正式资产身份、现场和设备生命周期 | 无 |
| `backend/dga/laboratory/public.py` | 油样、检测、整体检测定稿、条码报告 | assets.public |
| `backend/dga/condition_analysis/public.py` | 趋势、阈值、报警、健康派生 | assets.public、laboratory.public |
| `backend/dga/shared/` | 配置、基础设施与公共协作类型 | 无 |
| `backend/dga/main.py` | 运行时组装、HTTP 入口 | 各模块公开入口 |

资产公开入口还提供 `AssetDirectory.search` 和 `AssetDirectory.resolve_sampling_context` 两个只读查询；实验室模块复用资产模块拥有的正式资产选择器和 HTTP 适配器，不读取资产私有表。共享身份的公开服务提供认证和 operator 命令，已验证的不可变 ActorContext 由可信组装层传给业务模块；不得从请求 JSON 构造角色/权限上下文。跨模块只允许显式 public import；禁止动态 import/反射绕过检查，禁止调用对方内部实现或直接读写对方私有持久化。`backend/architecture.py` 验证绝对/相对 import 及依赖方向。

前端的三个 `features/` 目录分别拥有页面定义，门户外壳负责导航和公共布局。`/assets` 是业务路由，构建静态文件必须放在 `/static`，避免 nginx 目录冲突。

### 数据库演进

首个 Alembic migration 是空业务 schema 基线；0002 增加身份与审计；0003 增加正式资产和安装关系；0004 增加油样、身份快照、共享条码和容器；0005 增加检测中状态、只读方法版本、通用检测头、三类一对一结果表及对象元数据；0006 增加报告结果选择、整体定稿元数据和生命周期事件；0007 增加当前条码报告、不可变定稿快照及异步任务租约。序列号刻意不唯一，系统资产号唯一。0005 只提供待配置的方法占位，不预置未经确认的 ASTM 参数；完整配置管理属于 #14。0006 降级会把已定稿样品恢复为检测中并移除该版本的选择与定稿事实，以保证随后可再次升级；downgrade 仅允许隔离测试库使用，已有真实数据的环境不得执行。

```sh
docker compose run --rm migrate alembic current
docker compose run --rm migrate alembic upgrade head
```

升级前备份重要数据；downgrade 必须按具体业务 migration 评估，本票仅在隔离测试库演练空基线 downgrade。迁移文件位于 `backend/migrations/`，通过修改后构建镜像分发；源码可在安装锁定依赖后运行 Alembic 创建 revision。

依赖由 `backend/requirements.in` 和 `frontend/package.json` 声明，分别使用带哈希的 requirements.txt 与 package-lock.json 锁定。更新 Python 依赖时在 Python 3.12 环境执行 `pip-compile --generate-hashes --output-file backend/requirements.txt backend/requirements.in`，之后验证 Linux 镜像；不要手改哈希。

### Issue #12：新增资产批量导入

管理员在 `/assets/import` 下载固定 XLSX 模板和已有客户/现场/物料参考资料，上传后查看后台校验结果。仅新增资产及初始安装关系，不更新、合并或覆盖既有资产，也不通过文件创建客户、现场或物料。新资产ID和系统资产编号自动生成。序列号重复不是唯一性错误；页面列出冲突资产编号/型号并要求确认这些是不同物理设备。

模板 `Assets` 的必填列为 `record_key, serial_number, material_number, product_line, machine_type, status, location_kind, effective_at`。可选列见模板 Instructions。`parent_record_key` 只指向本批次中的父记录，不按序列号关联。已有父设备下的新部件，可先导入维修中心，再使用已有受控资产移动功能安装。直接归属现场仅允许光伏整机/储能系统；维修中心不填写客户/现场。导入只接收当前开放关系，不接收关系结束日期或多段历史。

- 输入上限：2 MiB XLSX、展开10 MiB、100个ZIP成员、500条资产行、全文件20000个单元格（包括参考表）、每单元格1000字符。参考表各列前500条，可删除参考表但需保留 Assets。拒绝公式、宏、外链、加密、空文件、重复列名、未知字段、远处隐藏数据，不做任意格式识别。
- 标识使用文本保留前导零。`effective_at` 填带时区的 ISO 日期时间，如 `2025-01-01T08:00:00Z`；不允许未来时间。`commissioning_date` 使用 `YYYY-MM-DD`。MW/MWh 最多6位小数，PV 的 MWh 留空。
- 只有 `assets.import` 权限可以访问导入入口/API，迁移默认仅授予 system_admin；一般 `assets.write` 不等于导入权限。所有HTTP写操作校验Origin/CSRF。
- `STAGED` 等待后台校验；`VALIDATED` 可包含错误/警告；`FAILED` 保留失败诊断和源文件；`PUBLISHED` 保留发布结果。错误阻止整批发布，警告需明确勾选确认。发布时重新校验当前主数据；预览变化会要求再次确认。并发/重试发布返回同一组资产，不重复创建。
- 修正后上传新批次，旧批次和源文件保留。发布超时不能认定失败：先刷新该批次确认状态。数据库行写入、安装关系、批次结果和成功审计处于同一事务，任一失败全部回滚，不跳过坏行。

#### 物料与迁移注意事项

`0013_asset_import` 增加物料目录和导入批次。只从已有资产中迁移非空、完全一致的物料/型号/资产类型映射；歧义或缺失映射不会猜测修复，原资产不变。空数据库需要管理员先准备客户、现场产品线和物料目录，否则导入会明确报缺失引用。此工单不提供新的主数据维护页面。存在保留批次时，降级迁移会拒绝静默丢弃导入审计。

#### 后台进程与失败恢复

普通 `compose.yaml` 包含 `import-worker`，执行 `python -m dga.assets.import_worker`；`--once` 处理最多一个批次，供操作检查使用。进程用数据库行锁领取待校验批次：崩溃释放锁，下一次继续处理；异常校验记录失败码，不无限重试同一个坏批次。长时间处于 STAGED 时先检查 worker 日志与数据库可用性。恢复后对于 FAILED 文件重新上传，不手改批次状态。

源文件使用既有 S3 兼容 FileStore，配置沿用 `OBJECT_STORE_*`。对象存储失败不生成可发布批次；上传成功后数据库写入失败会尝试删除该次孤立对象，删除失败日志记录对象键供管理员核对。S3与PostgreSQL不是分布式事务；生产源文件保留、备份与孤立对象清理由部署 #20 运维策略负责，不自动删除已发布源文件。

例外：如果已开始 COMMIT 而提交响应丢失，结果可能已经落库，此时**保留源文件而不删除**，日志记录对象键供核对。用户先查批次历史确认是否已有批次，再决定是否重新上传。只有明确发生在 COMMIT 之前的失败才尝试即时清理孤立源文件。

隔离验收可使用 `compose.browser.yaml` 加 `compose.import-browser.yaml`，项目名 `dga-issue12-browser`、`DGA_BROWSER_PORT=18095`；它使用临时测试数据和独立MinIO，**不可与现有验收 override 混用**。`tests.seed_import_browser` 只用于隔离假数据，不用于用户验收库。浏览器输入fixture由 `python -m tests.make_import_fixture <frontend/tests/fixtures/asset-import.xlsx>` 生成。后端行为测试使用 `dga-issue12` 的 `test-db`，不使用18093数据。

### 交付顺序

#### Issue #14：方法配置、仪器校准与 QA/QC

- `/lab/configuration` 提供方法版本、三类检测类型、仪器与校准、检测包配置。系统管理员及实验室管理员具有 `laboratory.configure`；实验室只读用户可查询，不能维护。
- 方法内容不可覆盖，调整时复制为新版本。配置字段名称、单位、小数位、检出限、定量限、录入上下限、允许限定符和人工 QA/QC 检查项。未批准的 ASTM 编号与科学参数留空，不预填推测值；不增加任意检测类型、计算规则或单位换算。
- 检测可关联仪器。校准按检测时刻在 America/Chicago 的日期选取最近一条已发生记录，截止日当天有效；无记录或无截止日为未知。失败、过期或未知校准，以及未执行/失败的 QA/QC，要求定稿时明确确认。手填仪器名不是校准证据。
- 每次保存检测冻结仪器、校准、QA/QC 及警告证据；修改检测会产生新警告标识，旧确认不覆盖新结果。以后修改配置不会改写已保存的检测或报告。报告快照保存被评估的质量证据及确认人/时间，PDF仅从快照生成。
- 检测包为不可覆盖的项目模板；应用到未定稿油样时保存快照，必做类型缺失阻止定稿。应用不创建空检测、不删除已有记录；替换要求客户端提供原检测包 ID，记录操作历史。方法/类型停用后不允许新选用，历史检测仍可读。
- 迁移链 `0015_lab_operations → 0016_lab_configuration → 0017_lab_instruments → 0018_lab_packages` 保留旧数据；存在新增配置/质量证据时拒绝破坏性降级。部署先备份并执行 `alembic upgrade head`，禁止在验收或生产环境运行测试 seed。

独立自动化环境使用 `dga-issue14`（真实 PostgreSQL 公共接口测试）及 `dga-issue14-browser`（端口18104，临时浏览器夹具）。原18093/18097环境不变。测试科学参数如 `TEST-UNIT` 仅是自动化数据，不能作为实验室正式方法。

本地迭代若只重建 API 容器，nginx 可能保留旧容器地址；出现 upstream connect refused/502 时，应重启同一 Compose 项目的 frontend 后检查登录 API。不要为此清空数据库或对象存储。生产滚动更新与动态 DNS 策略留给 #20 部署验收。

#### Issue #13：实验室运营

本地开发基线已整合 #7/#8 至 `0014_merge_laboratory`，保留资产侧 #9–#12 的迁移链。`0015_lab_operations` 在其后新增油样操作修订号、容器状态和不可修改的操作历史；已有油样/条码/检测不重建，已有容器初始显示“已接收”，不补造历史。存在操作历史时禁止直接降级丢弃记录。部署/升级须先备份，不能对验收或生产数据运行测试 fixture。

- `/lab` 显示检测中油样、今日检测数量、今日创建数量、总创建数量。日期口径为 America/Chicago，夏令时按实际23/25小时自然日。检测中指已有有效检测但未整体定稿；今日检测按记录实际创建时间统计（含后来移除的记录），不是检测时间；油样创建按创建时间，不是收样时间。
- `/lab/samples` 可按条码、油样编号、现场、设备序列号（含已保存整机路径）、状态、检测类型和日期过滤，支持排序、分页、列显示设置。筛选/排序/页码保存在URL。状态从身份、当前检测与当前报告派生：身份待确认、已收样、检测中、检测完成、已报告。撤回定稿后不再显示旧报告状态。
- `/lab/identity` 选择待确认油样，在其采样时刻搜索整机/变压器序列号并明确选择变压器，填写原因后确认。保留原条码、容器和检测，记录原始身份及确认后快照。已关联油样不能在此再次换绑；基础信息在搜索期间发生变化会拒绝旧修订提交。
- 检测工作台新增容器面板：已接收→使用中/留样/破损/处置；使用中与留样可互转，亦可耗尽/破损/处置；耗尽或破损只能处置；已处置不可回退。每次填写原因并保存操作人、时间、前后值。容器实物状态与科学检测定稿独立，定稿后仍可处置瓶子，但不改变报告。
- 写操作均要求 laboratory.write、Origin/CSRF及当前修订号；管理只读用户可查首页/台账/操作历史，无写入口。冲突保留输入并提示重新读取；超时不自动重试不确定的提交。

公开接口为 laboratory.public.LaboratoryOperations，资产上下文仍由 assets.public 拥有；身份确认先调用资产公开 lock_sampling_context 稳定资产关系，再锁定油样并复用调用事务的资产公开查询参数，避免锁内再次申请数据库连接，不跨模块读写私有表。测试连接真实独立PostgreSQL，浏览器仅覆盖关键链路及权限/冲突恢复。网络标签打印、库存、复杂审批、正式ASTM参数、阈值和PDF品牌细节不在 #13 范围。

当前隔离开发验收：Compose项目 `dga-issue13-browser`，端口18097，配置 `compose.browser.yaml` + `compose.import-browser.yaml`（临时数据库和对象存储）。管理员 `browser-admin`、只读 `operations-reader`，测试密码均为 `Browser changed passphrase 84!`。仅测试夹具账号，不用于生产。原18093验收环境及其数据不受影响。

#2 工程基础 → #3 登录/权限/审计身份 → #4 资产搜索/采样上下文 → #5 收样条码 → #6 检测录入 → #7 整体定稿 → #8 条码报告。随后按依赖补全 #9–#19，#20 完成部署和恢复验收。服务工单、ASTM 编号、正式阈值和 PDF 品牌细节不在本票范围。

## English

A Chinese-language portal for field asset and oil-sample management. Engineering foundations are specified in [Issue #2](https://github.com/studyben/DGA_lab/issues/2); the complete MVP specification is in [Issue #1](https://github.com/studyben/DGA_lab/issues/1).

This is the initial production codebase for a greenfield project. Implemented capabilities include #2 portal navigation and test infrastructure, #3 local accounts/permissions/sessions/audit, #4 formal asset search, #5 oil-sample reception and shared barcodes, #6 the barcode test workbench with typed results and original attachments, #7 overall test finalization, and #8 Chinese barcode reports. Additional delivered capabilities are described below. Business pages that have not been implemented explicitly indicate that they are unavailable; they do not display prototype data.

### Getting started

Install and start Docker Desktop with Linux containers, or Docker Engine with Compose v2 or later. From the repository root, run:

```sh
docker compose up --build -d --wait
```

Open http://127.0.0.1:8080 . The first startup downloads images and dependencies; you do not need to install Python, Node.js, or PostgreSQL on the host. If the port is occupied, set the environment variable `DGA_PORT=18080` and run the same command. Browser deep links include `/assets`, `/lab`, `/lab/workbench`, and `/lab/reports`. The top navigation provides the asset and laboratory workspaces; condition analysis appears in the asset sidebar.

```sh
docker compose ps
docker compose logs --tail=100 api migrate frontend
docker compose down
```

Plain `down` preserves the database volume. Do not add `--volumes` when retaining local data. The development database credentials in Compose are explicitly local-only. Only the frontend port is bound to 127.0.0.1; the database and API do not publish host ports. Local HTTP uses a non-Secure cookie for development. Do not expose this development Compose configuration directly to the public internet.

#### Initial administrator setup

The application does not create a default account or provide a fixed login password. After startup, run this command in your own terminal:

```sh
docker compose exec -it api python -m dga.shared.auth.cli bootstrap --username admin --display-name Administrator
```

Enter and confirm an initial password of 15–128 characters when prompted. Input is hidden, and the password is not passed as a command-line argument. Sign in through the browser and change the initial password before accessing the portal. Bootstrap refuses to run if any account already exists; it does not reset or overwrite passwords. Do not put real passwords in Git, screenshots, or chat.

Issue #18 provides user and role management at `/settings/users`. New local password accounts are restricted to administrator recovery. Ordinary employee accounts are created on their first OIDC login; existing ordinary local accounts remain for controlled migration. After changing the administrator's initial password, interactive commands are also available:

```sh
docker compose exec -it api python -m dga.shared.auth.cli create-user --admin admin --username recovery --display-name Recovery --role system_admin
docker compose exec -it api python -m dga.shared.auth.cli set-status --admin admin --user-id USER_UUID --status DISABLED
docker compose exec -it api python -m dga.shared.auth.cli set-roles --admin admin --user-id USER_UUID --role field_engineer
```

Use the ID returned by the user-detail API or account-creation command for `USER_UUID`. Management commands enforce current permissions; self-registration is unavailable. The system protects the last active administrator with a local password. Recovery, migration-impact reporting, and OIDC configuration are documented in the [Issue #18 operations guide](docs/identity-operations.md), currently in Chinese. Local protocol simulations do not constitute real Okta acceptance; #18 still requires integration testing with IT.

| Role code | Capabilities |
| --- | --- |
| system_admin | All current capabilities, including account management and audit reading |
| asset_manager | Read all three modules and edit basic site information |
| lab_admin | Laboratory manager: asset maintenance, laboratory entry/finalization/configuration, health-rule maintenance, alarm acknowledgement, audit reading, and ordinary user management |
| analyst | Read all three modules, enter/finalize laboratory tests, and acknowledge alarms |
| field_engineer | Read all three modules and acknowledge alarms; the default role on first OIDC login |
| management | Read all three modules, edit basic site information, and add/remove the AM role for ordinary users |
| management_readonly | Legacy read-only role; existing assignments are retained, but new assignments are prohibited |

Roles can be combined; permissions are their union. A permission contract for an undelivered capability does not imply that its business workflow exists. The frontend hides workspaces or disables pages according to permissions and explains denied direct access. Public backend module interfaces independently enforce authorization and do not trust frontend role declarations.

### Runtime and configuration

Nginx serves the React/TypeScript static build and proxies `/api/` to FastAPI. The API starts only after the migration task succeeds; the frontend starts after application readiness succeeds. PostgreSQL 17 uses a named volume.

- `DATABASE_URL`: required by the backend, in the format `postgresql+psycopg://user:password@host:5432/database`. Credentials can be URL-encoded. Do not commit production credentials.
- `BUSINESS_TIMEZONE`: defaults to `America/Chicago`; it must be a valid IANA time zone.
- `DGA_PORT`: the Compose frontend host port, defaulting to 8080. Application and test environments use separate databases and storage.
- `COOKIE_SECURE`: defaults to true in the application and is explicitly false in local Compose. Production requires HTTPS and Secure cookies.
- `SESSION_HOURS`: the absolute lifetime of local password sessions, defaulting to 8; values below 1 or above 24 prevent startup. OIDC sessions expire eight hours after the latest successful verification, independently of this setting, without sliding renewal.
- `AUTH_ALLOWED_ORIGINS`: comma-separated complete origins, including scheme, host, and port. Authentication POST requests must carry a matching Origin; same-origin browsers send it automatically. Deployment configuration should list only approved HTTPS origins.
- `OBJECT_STORE_ENDPOINT`, `OBJECT_STORE_BUCKET`, `OBJECT_STORE_ACCESS_KEY`, and `OBJECT_STORE_SECRET_KEY`: together configure path-style S3-compatible object storage. `OBJECT_STORE_REGION` defaults to `us-east-1`. If required storage configuration is incomplete, ordinary test entry remains available, while attachment saving fails explicitly without recording false success. Local Compose runs isolated MinIO. Do not commit production credentials.
- `GET /api/health`: returns 200 with `{ "status": "ok", "database": "ok" }` when the database is reachable and its migration revision matches the application. Connection or migration failures return 503 with `unavailable` values. This endpoint does not run migrations or expose database exceptions or credentials.
- `GET /api/modules`: returns authorized modules with stable codes and labels after login and any required initial password change. This is not a business CRUD endpoint.
- `/api/auth/login`, `/api/auth/password`, and `/api/auth/logout` use POST; `/api/auth/session` uses GET. Session cookies are HttpOnly/SameSite=Lax and are not stored in localStorage. Password changes and logout require the current session's `X-CSRF-Token`.
- `/api/assets/access`, `/api/laboratory/access`, and `/api/condition-analysis/access`: protected module-access contexts. Anonymous access returns 401; missing permissions or a required password change returns 403. Responses contain the verified actor ID. These endpoints are not business CRUD operations.
- `GET /api/assets/search?q=...&effective_at=...`: searches full or partial main-unit/transformer serial numbers for formal assets eligible for association at the specified time. Duplicate serial numbers return customer, site, model, status, system asset number, and match reason for disambiguation. Main-unit results include eligible transformers installed at that time.
- `GET /api/assets/{asset_id}/sampling-context?sampled_at=...`: resolves customer, site, and the full equipment path at a timezone-aware sampling timestamp. Both asset queries require `assets.read`; these query endpoints do not edit or import assets.
- `POST /api/laboratory/samples`: registers an oil sample linked to a formal asset or explicitly marked as awaiting identity confirmation. Formal association captures the customer, site, equipment path, and serial numbers at sampling time. One oil sample may have 1–20 physical sample containers sharing its barcode.
- `GET /api/laboratory/samples/by-barcode/{barcode}`: retrieves reception information and containers by scanning or entering the oil-sample barcode. `POST /api/laboratory/samples/{barcode}/label-prints` records an audit event before opening browser printing. Both reception and label-print POST requests require a same-origin Origin and current-session CSRF token.
- `GET /api/laboratory/workbench/{barcode}`: returns sample information, containers, testing status, active method configurations, and all valid tests. `PATCH /api/laboratory/samples/{barcode}` corrects basic information; `POST/PUT/DELETE /api/laboratory/samples/{barcode}/tests...` adds, edits, or logically deletes DGA, moisture, and breakdown-voltage records. Repeated tests are independent records under the same barcode, without a separate retest entity. ND stores no numeric value; LT/GT stores a boundary value. Formal ASTM method numbers, units, precision, and detection limits remain subject to configuration and confirmation.
- `PUT /api/laboratory/samples/{barcode}/report-result`: selects the result used in the barcode report when multiple valid tests of the same type exist. Overall finalization selects automatically when only one exists. `POST /api/laboratory/samples/{barcode}/finalization` finalizes the overall testing. Pending identity, no valid test, missing result selection, or unacknowledged QA warnings return structured blocking reasons. Finalized sample information, tests, and report-result selections are read-only.
- `POST /api/laboratory/samples/{barcode}/finalization-withdrawals`: users with `laboratory.finalize` provide a reason to withdraw finalization and restore editing. Barcode labels remain printable; the current report becomes invalid.
- `GET /api/laboratory/reports/by-barcode/{barcode}`: returns the current barcode report's unavailable, queued, generating, ready, or failed state. `POST .../retry` lets users with finalization permission safely retry failed tasks. `GET .../file?disposition=inline|attachment` proxies the current PDF after SHA-256 verification. Reports are unavailable before finalization; withdrawn reports cannot be accessed. Re-finalization replaces the current report without displaying version history. A separate `report-worker` claims leased PostgreSQL tasks and writes the simplified Chinese report to S3-compatible storage.

Passwords use Argon2id with 19 MiB memory, two iterations, and parallelism 1; only hashes are stored. Sessions use random opaque credentials, whose SHA-256 hashes are stored in the database. Logout revokes the current session. Password changes revoke all previous sessions and rotate the current one while preserving its original expiry. Disabling or locking an account revokes its sessions; reactivation does not revive them. Each request reads current account status and roles. Five consecutive incorrect passwords temporarily restrict login for 15 minutes; responses do not reveal whether the account exists. The frontend checks sessions every 30 seconds and on window focus; the backend validates every request, so revoked sessions immediately lose data access.

Audit records are append-only: successful/failed login, logout, password changes, account/role/status operations, sample reception, asset association, barcode printing, test changes, report-result selection, finalization attempts, and withdrawals. Authorized shared public queries expose audit records. An unsuccessful login with no matching account has a null actor and separately records the claimed username; no user ID is fabricated. Passwords, session credentials, and CSRF tokens are not recorded. Structurally invalid requests return a generic error without echoing input. Audit querying is a minimal operator/application interface, without an audit-management UI. Production TLS, reverse-proxy rate limiting, monitoring, and least-privilege database access belong to #20; application account throttling does not replace perimeter protections.

Future Lightsail external database, object storage, and backup configuration belongs to #20. Local Compose includes a report worker but is not a production deployment configuration.

### Testing

```sh
docker compose --profile test run --build --rm api-test
docker compose -f compose.browser.yaml up --build -d --wait frontend
docker compose -f compose.browser.yaml --profile test run --build --no-deps --rm browser-test
```

API tests start a separate PostgreSQL `test-db`, apply the application's Alembic migrations, and observe behavior through HTTP and public application interfaces. Test URLs must match test-db/dga_test/dga_test to avoid migrating application data. Test storage is tmpfs and does not survive container shutdown. Migration downgrade checks run serially; do not run concurrent suites against the same test database. Separate development tasks can use different Compose project names.

Browser tests use the independent `dga-browser` Compose project, temporary PostgreSQL and MinIO, a real report worker, and a matching Playwright Linux image. Its portal is available on port 18080. Fixture scripts strictly reject any database other than `dga_browser`; fixture accounts are created only in this isolated environment. Tests cover login/permissions, the logo, navigation and service retries, formal asset search, reception/barcodes, test entry and overall finalization, report blocking before finalization, asynchronous generation, preview/download, withdrawal invalidation, and report regeneration. Attachment failure atomicity is tested through a shared file-port test implementation. Failed retries and pending QA warnings are injected only at external HTTP boundaries; other flows use the real API. Tests do not depend on React component trees, CSS class names, or internal tables.

The initial-password-change test changes the fixture account's password. Before repeating tests, reset only the isolated fixture, never the ordinary application:

```sh
docker compose -f compose.browser.yaml run --rm --no-deps migrate python -m tests.seed_browser
docker compose -f compose.browser.yaml --profile test run --build --no-deps --rm browser-test
docker compose -f compose.browser.yaml --profile test down
```

Developers may also run `npm ci` and `npm run build` in `frontend/`. `npm run dev` starts port 5173 and proxies `/api` to the running local Compose application on port 8080. Adjust the Vite development proxy if `DGA_PORT` changes. CI uses the container commands above; the build includes TypeScript checking.

### Module boundaries

| Directory / public entry point | Ownership | Other business modules it may call |
| --- | --- | --- |
| `backend/dga/assets/public.py` | Formal asset identity, sites, and equipment lifecycle | None |
| `backend/dga/laboratory/public.py` | Oil samples, tests, overall finalization, and barcode reports | assets.public |
| `backend/dga/condition_analysis/public.py` | Trends, thresholds, alarms, and derived health | assets.public, laboratory.public |
| `backend/dga/shared/` | Configuration, infrastructure, and shared collaboration types | None |
| `backend/dga/main.py` | Runtime composition and HTTP entry points | Each module's public interface |

The asset interface exposes the read-only queries `AssetDirectory.search` and `AssetDirectory.resolve_sampling_context`. The laboratory reuses the formal-asset selector and HTTP adapter owned by the asset module without reading private asset tables. The shared public identity service owns authentication and operator commands. Trusted composition passes a verified, immutable `ActorContext` to business modules; role/permission contexts must not be constructed from request JSON. Cross-module dependencies must use explicit public imports. Dynamic imports/reflection to bypass checks, calls into another module's internals, and direct access to its private persistence are prohibited. `backend/architecture.py` checks absolute/relative imports and dependency direction.

The three business `features/` directories own their page definitions; the portal shell owns navigation and common layout. `/assets` is a business route. Build output must be served under `/static` to avoid conflicts with Nginx directories.

### Database evolution

The first Alembic migration is an empty business-schema baseline. 0002 adds identity and audit; 0003 adds formal assets and installation relationships; 0004 adds oil samples, identity snapshots, shared barcodes, and containers; 0005 adds testing status, read-only method versions, common test headers, three one-to-one result tables, and object metadata; 0006 adds report-result selection, overall-finalization metadata, and lifecycle events; 0007 adds current barcode reports, immutable finalization snapshots, and asynchronous task leases. Serial numbers are intentionally non-unique; system asset numbers are unique. 0005 supplies method placeholders without unconfirmed ASTM parameters; full configuration management belongs to #14. The early 0006 downgrade returns finalized samples to testing and removes its selection/finalization facts so that the schema can be upgraded again. Downgrades are restricted to isolated testing and must not be run in environments containing real data.

```sh
docker compose run --rm migrate alembic current
docker compose run --rm migrate alembic upgrade head
```

Back up important data before upgrading. Evaluate downgrade behavior for each business migration; the foundation's empty-baseline downgrade was exercised only in isolated testing. Migration files live in `backend/migrations/` and are distributed through rebuilt images. Developers can create Alembic revisions from source after installing locked dependencies.

Dependencies are declared in `backend/requirements.in` and `frontend/package.json`, then locked in hash-verified `requirements.txt` and `package-lock.json`. When updating Python dependencies, run `pip-compile --generate-hashes --output-file backend/requirements.txt backend/requirements.in` under Python 3.12 and validate the Linux image. Do not edit dependency hashes manually.

### Issue #12: new-asset batch import

Administrators download the fixed XLSX template and existing customer/site/material reference data at `/assets/import`, upload a file, and review background validation. Import creates new assets and initial installation relationships only. It does not update, merge, or overwrite existing assets, or create customers, sites, or materials from a file. New asset IDs and system asset numbers are generated automatically. Duplicate serial numbers are not uniqueness errors; the page lists conflicting asset numbers/models and requires confirmation that they represent different physical devices.

The required columns in the `Assets` sheet are `record_key, serial_number, material_number, product_line, machine_type, status, location_kind, effective_at`. Optional columns are described in the template's Instructions sheet. `parent_record_key` refers only to a parent record in the same batch, never by serial number. To add a component under an existing parent, import it into the repair center and then install it through the controlled asset-movement workflow. Only PV main units and ESS systems may be directly assigned to a site. Repair-center rows must omit customer/site references. Import accepts only current open relationships, not relationship end dates or multiple historical periods.

- Input limits: 2 MiB XLSX, 10 MiB uncompressed content, 100 ZIP members, 500 asset rows, 20,000 cells across the entire file including reference sheets, and 1,000 characters per cell. Reference data includes the first 500 records per reference list; reference sheets may be deleted, but `Assets` must remain. Formulas, macros, external links, encryption, empty files, duplicate column names, unknown fields, and distant hidden data are rejected. Arbitrary formats are not detected or converted.
- Use text for identifiers to preserve leading zeros. `effective_at` must be a timezone-aware ISO timestamp, such as `2025-01-01T08:00:00Z`, and cannot be in the future. Use `YYYY-MM-DD` for `commissioning_date`. MW/MWh values allow up to six decimal places; leave MWh blank for PV.
- Import UI/API access requires `assets.import`, granted by migration only to system_admin. General `assets.write` does not grant import permission. Every HTTP write validates Origin/CSRF.
- `STAGED` awaits background validation; `VALIDATED` may include errors/warnings; `FAILED` retains diagnostics and the source file; `PUBLISHED` retains publication results. Errors block the entire batch; warnings require explicit acknowledgement. Publication revalidates current master data; changed previews require confirmation again. Concurrent or retried publication returns the same assets without duplicates.
- Corrections require uploading a new batch; the old batch and source file are retained. A publication timeout is not proof of failure: refresh the batch to confirm its state. Asset rows, installation relationships, batch results, and successful audit commit in one transaction. Any failure rolls back the entire batch; invalid rows are not skipped.

#### Materials and migration considerations

`0013_asset_import` adds the material catalog and import batches. It migrates only nonempty, unambiguous material/model/asset-type mappings from existing assets. Missing or ambiguous mappings are not guessed; original assets remain unchanged. An empty database requires customer records, site product lines, and material master data before import can succeed. Missing references are reported explicitly. This work unit does not provide new master-data maintenance pages. Downgrade refuses to silently discard retained batch audit data.

#### Background processing and failure recovery

Ordinary `compose.yaml` includes `import-worker`, running `python -m dga.assets.import_worker`. `--once` processes at most one batch for operational checks. The worker claims pending validation using database row locks; a crash releases its lock so another run can continue. Validation exceptions record a failure code rather than endlessly retrying the same invalid batch. If a batch remains `STAGED`, check worker logs and database availability. After recovery, upload a new batch for a `FAILED` file; do not edit batch states directly.

Source files use the existing S3-compatible `FileStore` with `OBJECT_STORE_*` configuration. Object-storage failures do not create publishable batches. If upload succeeds but the database write fails, the application attempts to delete that operation's orphaned object. Cleanup failures log its key for administrator review. S3 and PostgreSQL do not share a distributed transaction. Production source retention, backups, and orphan cleanup belong to #20 operations; published source files are not deleted automatically.

Exception: if COMMIT has started and its response is lost, the batch may already be persisted. The application **retains the source file rather than deleting it**, logging the object key for review. Check batch history before deciding to upload again. Immediate orphan cleanup is attempted only for failures known to occur before COMMIT.

Isolated acceptance uses `compose.browser.yaml` plus `compose.import-browser.yaml`, project `dga-issue12-browser`, and `DGA_BROWSER_PORT=18095`. It has temporary test data and separate MinIO; **do not mix it with existing acceptance overrides**. `tests.seed_import_browser` is only for isolated fixtures, not user acceptance databases. Generate the browser input fixture with `python -m tests.make_import_fixture <frontend/tests/fixtures/asset-import.xlsx>`. Backend behavior tests use the `dga-issue12` test database, not port 18093's data.

### Delivery sequence

#### Issue #14: method configuration, instrument calibration, and QA/QC

- `/lab/configuration` provides method versions for the three test types, instruments/calibrations, and test packages. System administrators and laboratory managers have `laboratory.configure`. Read-only laboratory users may query configuration but cannot maintain it.
- Method content cannot be overwritten; changes require copying to a new version. Configuration controls result names, units, decimal places, detection/quantification limits, input bounds, allowed qualifiers, and manual QA/QC checks. Unapproved ASTM numbers and scientific parameters remain blank. No arbitrary test types, calculation rules, or unit conversions are added.
- A test may reference an instrument. Calibration selects the most recent record that had occurred on the test's America/Chicago date; the expiration date is inclusive. No record or no expiration date means unknown validity. Failed, expired, or unknown calibration and missing/failed QA/QC require explicit acknowledgement at finalization. A manually typed instrument name is not calibration evidence.
- Saving a test freezes instrument, calibration, QA/QC, and warning evidence. Editing a test produces new warning identifiers; previous acknowledgements do not cover new results. Later configuration changes do not rewrite saved tests or reports. Report snapshots retain evaluated quality evidence and acknowledgement actor/time; PDFs are generated only from snapshots.
- A test package is an immutable project template. Applying it to an unfinalized sample saves a snapshot; missing required test types block finalization. Applying a package does not create empty tests or delete existing records. Replacement requires the previous package ID and records operation history. Inactive methods/types cannot be newly selected; historical tests remain readable.
- The migration chain `0015_lab_operations → 0016_lab_configuration → 0017_lab_instruments → 0018_lab_packages` preserves existing data. Destructive downgrade is refused when new configuration or quality evidence exists. Back up before deployment and run `alembic upgrade head`; do not run test seed scripts against acceptance or production environments.

Independent automated environments are `dga-issue14` for real PostgreSQL public-interface tests and `dga-issue14-browser` on port 18104 for temporary browser fixtures. Original environments on ports 18093/18097 remain unchanged. Scientific parameters such as `TEST-UNIT` are test fixtures, not formal laboratory methods.

If only the API container is rebuilt during local iteration, Nginx may retain its old container address. On upstream connection refusal/502, restart the frontend in the same Compose project and verify the login API. Do not clear the database or object storage. Production rolling updates and dynamic DNS strategy belong to #20 deployment acceptance.

#### Issue #13: laboratory operations

The local development baseline integrates #7/#8 through `0014_merge_laboratory` while preserving the #9–#12 asset migration chain. `0015_lab_operations` then adds sample operation revisions, container states, and immutable operation history. Existing oil samples, barcodes, and tests are not recreated. Existing containers initially appear as received, without fabricated historical events. Downgrade cannot directly discard retained operation history. Back up before deployment/upgrades; do not run test fixtures against acceptance or production data.

- `/lab` shows oil samples being tested, tests created today, samples created today, and total samples created. Dates use America/Chicago, including actual 23/25-hour daylight-saving days. A sample is being tested if it has valid tests and is not finalized. Today's test count uses record creation time, including subsequently removed tests, rather than measurement time. Sample creation counts use creation time, not reception time.
- `/lab/samples` filters by barcode, sample number, site, equipment serial number including captured main-unit paths, status, test type, and date; it supports sorting, pagination, and visible-column settings. Filters, sorting, and page are stored in the URL. Status is derived from identity, current tests, and current report: identity pending, received, testing, testing complete, or reported. Withdrawing finalization removes the old report status.
- `/lab/identity` lets users select a pending-identity sample, search main-unit/transformer serial numbers at its sampling time, explicitly choose a transformer, and confirm with a reason. Barcode, containers, and tests are retained; original identity and the confirmed snapshot are recorded. Already linked samples cannot be rebound here. Basic-information changes during search cause stale-revision submission to be rejected.
- The workbench container panel supports received → in use/retained/broken/disposed. In-use and retained containers may move between those states or become depleted/broken/disposed. Depleted or broken containers may only be disposed; disposed is terminal. Each change records a reason, actor, timestamp, and before/after values. Physical container state is independent of scientific finalization; bottles may be disposed after finalization without changing the report.
- Writes require `laboratory.write`, Origin/CSRF, and the current revision. Read-only management users may read home/ledger/history but have no write actions. Conflicts preserve input and request a reload. Timeouts do not automatically retry uncertain writes.

The public interface is `laboratory.public.LaboratoryOperations`; `assets.public` continues to own asset context. Identity confirmation first calls the asset public `lock_sampling_context` to stabilize asset relationships, then locks the sample and reuses the calling transaction through the asset public query interface. It does not acquire another connection while holding the lock or read/write another module's private tables. Tests use real isolated PostgreSQL; browser tests cover key workflows, permission denial, and conflict recovery. Network label printing, inventory, complex approvals, formal ASTM parameters, thresholds, and PDF branding are outside #13.

The documented isolated development acceptance environment is Compose project `dga-issue13-browser` on port 18097, with `compose.browser.yaml` plus `compose.import-browser.yaml` and temporary database/object storage. Its fixture administrator is `browser-admin`, and its read-only user is `operations-reader`; both use the test password `Browser changed passphrase 84!`. These are test-fixture accounts only, not production accounts. The original port 18093 acceptance environment and its data are unaffected.

Implementation order: #2 foundations → #3 login/permissions/audit identity → #4 asset search/sampling context → #5 sample reception/barcodes → #6 test entry → #7 overall finalization → #8 barcode reports. Subsequent #9–#19 capabilities follow their dependencies; #20 completes deployment and recovery acceptance. Service work orders, unconfirmed ASTM method numbers, formal thresholds, and PDF branding details remain outside those initial slices.
