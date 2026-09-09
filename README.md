# DGA Lab

中文现场资产与油样管理门户。当前交付 [Issue #2](https://github.com/studyben/DGA_lab/issues/2) 的工程基础，完整 MVP 规格见 [Issue #1](https://github.com/studyben/DGA_lab/issues/1)。

这是绿地项目的首个生产工程切片：门户导航、模块公开入口、PostgreSQL 迁移和测试基座已经实现；资产业务、登录、收样、检测和报告由后续工单交付。导航下的业务页面明确显示待开放，不展示原型假数据。

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

普通 `down` 保留数据库卷。请勿在要保留本地数据时加 `--volumes`。本地开发用户名/密码已在 Compose 中明确标记，只用于本机，只有前端端口绑定 127.0.0.1；数据库/API 不发布宿主端口。本票尚无认证，请勿将此 Compose 暴露到公网。

## 运行与配置

nginx 提供 React/TypeScript 静态构建，并将 `/api/` 转发给 FastAPI；迁移任务成功后才启动 API。应用 readiness 成功后启动前端。PostgreSQL 17 使用命名卷。

- `DATABASE_URL`：后端必填，格式 `postgresql+psycopg://user:password@host:5432/database`。凭据可用 URL 编码，不能提交正式凭据。
- `BUSINESS_TIMEZONE`：默认 `America/Chicago`，必须是有效 IANA 时区。
- `DGA_PORT`：Compose 前端宿主端口，默认 8080；应用数据和测试数据有独立数据库与存储。
- `GET /api/health`：数据库可连接且迁移版本匹配时 200 `{ "status": "ok", "database": "ok" }`；连接失败或未迁移时 503，字段均为 `unavailable`。不自动执行迁移，不输出数据库异常或凭据。
- `GET /api/modules`：三个模块的稳定代码和中文标签；这是工程注册信息，不是业务 CRUD。

未来 Lightsail 的外部托管数据库、对象存储、worker 和备份配置由 #20 与对应业务工单提供，本地 Compose 不作为生产配置。

## 测试

```sh
docker compose --profile test run --build --rm api-test
docker compose --profile test run --build --rm browser-test
```

API 测试会启动独立 `test-db` PostgreSQL，先执行与应用一致的 Alembic migration，然后从 HTTP/公开应用接口观察行为。测试 URL 限制为 test-db/dga_test/dga_test，避免误迁移应用数据。测试存储为 tmpfs，停止后不保留。当前 migration downgrade 验证按串行执行；请勿对同一 test-db 并发运行多份套件。不同开发任务可使用不同 Compose project name 隔离。

浏览器套件使用匹配版本的 Playwright Linux 镜像，验证真实 nginx 构建、双工作区导航、刷新/返回、无效路由和服务失败重试。失败重试场景仅在 HTTP 外部边界注入 503；其余连接 smoke 使用真实 API。测试不依赖 React 组件树、CSS 类名或内部业务表。

开发者也可在 `frontend/` 运行 `npm ci`、`npm run build`。`npm run dev` 启动 5173，默认把 `/api` 代理至已运行的本地 Compose 8080；若修改 DGA_PORT，相应调整 Vite 开发代理。CI 使用上述容器命令，构建包含 TypeScript 检查。

## 模块边界

| 目录/公开入口 | 所有权 | 可调用的其他业务模块 |
| --- | --- | --- |
| `backend/dga/assets/public.py` | 正式资产身份、现场和设备生命周期 | 无 |
| `backend/dga/laboratory/public.py` | 油样、检测、整体检测定稿、条码报告 | assets.public |
| `backend/dga/condition_analysis/public.py` | 趋势、阈值、报警、健康派生 | assets.public、laboratory.public |
| `backend/dga/shared/` | 配置、基础设施与公共协作类型 | 无 |
| `backend/dga/main.py` | 运行时组装、HTTP 入口 | 各模块公开入口 |

当前公开入口只暴露不可变模块标识；具体业务接口随各自工单增加，不能把工程占位误认为已交付业务能力。跨模块只允许显式 public import；禁止动态 import/反射绕过检查，禁止调用对方内部实现或直接读写对方私有持久化。`backend/architecture.py` 在测试中检查绝对/相对 import 及依赖方向，并用禁止/允许的示例验证检查器。

前端的三个 `features/` 目录分别拥有页面定义，门户外壳负责导航和公共布局。`/assets` 是业务路由，构建静态文件必须放在 `/static`，避免 nginx 目录冲突。

## 数据库演进

首个 Alembic migration 是空业务 schema 基线，只建立迁移版本跟踪。后续业务表归其拥有模块，不提前复制数据库设计草案的所有表。

```sh
docker compose run --rm migrate alembic current
docker compose run --rm migrate alembic upgrade head
```

升级前备份重要数据；downgrade 必须按具体业务 migration 评估，本票仅在隔离测试库演练空基线 downgrade。迁移文件位于 `backend/migrations/`，通过修改后构建镜像分发；源码可在安装锁定依赖后运行 Alembic 创建 revision。

依赖由 `backend/requirements.in` 和 `frontend/package.json` 声明，分别使用带哈希的 requirements.txt 与 package-lock.json 锁定。更新 Python 依赖时在 Python 3.12 环境执行 `pip-compile --generate-hashes --output-file backend/requirements.txt backend/requirements.in`，之后验证 Linux 镜像；不要手改哈希。

## 交付顺序

#2 工程基础 → #3 登录/权限/审计身份 → #4 资产搜索/采样上下文 → #5 收样条码 → #6 检测录入 → #7 整体定稿 → #8 条码报告。随后按依赖补全 #9–#19，#20 完成部署和恢复验收。服务工单、ASTM 编号、正式阈值和 PDF 品牌细节不在本票范围。
