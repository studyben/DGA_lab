# 实验室检测资料暂存（格式 v1，S1）

入口为 /lab/imports，公开应用门面为 laboratory.public.LaboratoryImports。当前可下载模板/虚构示例，显式确认来源身份与用途，保存 XLSX 或两份 UTF-8 CSV 原件，重开批次、核对元数据/所采用的已确认原件并下载原始字节。当前不解析业务行、不发起验证任务；“原件已确认保存”只说明文件收件已经提交，不说明科学资料已核实。

暂存不会创建正式油样、检测、样品容器、临时/正式资产、有效定稿或报告任务。PDF 仅有文件名声明列，内容始终未提供。现有 analyst 的 laboratory.finalize 授权保持原状。

## 模板与文件

下载 GET /api/laboratory/imports/template?format=XLSX&version=1；example=true 下载明确标注虚构的示例。XLSX 包含 Format、Instructions 及两张中文业务表。Format 为 version=1、format=LABORATORY。format=CSV_PAIR 下载 ZIP，内含 samples.csv、tests.csv、instructions.json；ZIP 是下载包装，不可上传。上传时分别选择两份 CSV 的角色。

“油样信息”/samples.csv 的完整 18 列：

~~~text
source_lab_key,source_lab_name,external_sample_id,source_site_name,source_whole_unit_serial,source_transformer_serial,formal_asset_id,system_asset_number,sampled_at,sampled_timezone,sampling_context,physical_received,received_at,received_timezone,container_count,report_filenames,notes,source_note
~~~

“检测结果”/tests.csv 的完整 39 列：

~~~text
source_lab_key,external_sample_id,external_test_id,test_type,measured_at,measured_timezone,source_method,source_method_version,method_version_id,report_selected,source_instrument,source_analyst,source_qa,h2_value,h2_qualifier,h2_unit,ch4_value,ch4_qualifier,ch4_unit,c2h2_value,c2h2_qualifier,c2h2_unit,c2h4_value,c2h4_qualifier,c2h4_unit,c2h6_value,c2h6_qualifier,c2h6_unit,co_value,co_qualifier,co_unit,co2_value,co2_qualifier,co2_unit,result_value,result_qualifier,result_unit,notes,source_note
~~~

每个检测行表示一次完整来源检测；DGA 同行保留全部七项，复测使用另一个 external_test_id。外部油样/检测标识是最多160字符的文本，保留大小写和前导零。notes 与 source_note 分别保留，均最多2000字符。原检测者/QA/仪器陈述与上传核对人员分开。

空白、数值0、ND、LT、GT 含义不同。ND 无数值，LT/GT 使用真实边界值；不自动平均、换算单位或猜测 ASTM/方法兼容性。DATE 不补午夜；缺失时区/精度及 DST 折叠/间隙不能靠浏览器时区推断。模板字段说明列出精确长度和未来验证约束；这些行规则的解码、问题呈现及安全检查属于 S2，当前收件不会声称其已通过。

单 XLSX≤10MiB；每份 CSV≤10MiB，两份≤20MiB。上传 MIME 分别严格为 application/vnd.openxmlformats-officedocument.spreadsheetml.sheet 或 text/csv。文件名1–255字符，拒绝路径、控制字符和不匹配扩展名。业务上限500油样/2000完整检测、XLSX展开50MiB/200成员/150000单元格由后续 S2 实际解析验证；当前仅生成说明并执行原件/元数据边界，不提前实现解析器。

## 来源身份与核对

批次用途必须为 HISTORICAL 或 DAILY。可显式提供 IANA 来源时区及确认状态；上传时间不能充当采样、测量或实物接收时间。

source_lab_key 是批次内别名（字母开头，字母/数字/下划线/短横线，≤80），不等于全局身份。来源确认必须选择：

- NEW：明确名称、IN_HOUSE/THIRD_PARTY、确认理由及“独立来源”确认；先获取全部同名候选的 candidate_digest，再显式提交。目录非唯一名称，同名不会合并。
- REFERENCE：显式选择已有稳定 UUID 与理由；引用不修改名称或来源种类。

来源身份只在成功创建批次/核对修订事务中建立。候选变化返回 source_candidates_changed；原请求作为 REJECTED 保留，用户重新核对后才能明确创建新请求。不存在独立来源 CRUD。元数据、绑定或所采用原件的核对需 expected_revision、理由及新的 intent；过期修订返回 import_stale_revision，不能覆盖他人的核对。

## 收件、恢复与私有原件

创建/收件/核对使用 actor 私有 UUID Idempotency-Key，绑定确切操作及原参数摘要。同一 key 的相同请求返回原冻结结果；更改内容、文件名、角色或操作返回409。操作查询 /operations/{key} 只有原 actor 且当前拥有 laboratory.write 时可用。批次及原件历史可由其他当前实验室写入者访问，但不会暴露对象地址、存储 key、租约 token 或他人的 intent key。

收件先将 PENDING 操作与不可变文件身份提交到数据库，再在事务外写 FileStore，最后在当前授权、租约 token 和批次锁保护下确认 RECEIVED、冻结完成结果并递增 revision。第一次确认的该角色文件成为所采用原件；角色已占用时晚到收件只加入未采用历史，不自动替换。每次成功收件/核对均留历史并使旧验证结果失效；S1 不运行验证器。

PENDING/RETRYABLE 历史保留原上传者及恢复元数据和可能已写入的字节；没有取消、删除或代用他人 key 的动作。另一个当前 lab writer 可用自己的 intent 在同批上传替代原件，并明确选择已 RECEIVED 的文件。显式选择尚未 RECEIVED 的文件才返回 scoped files_pending，不会因无关历史阻塞整个批次。

浏览器发送前在 actor 专属 sessionStorage 保存并读回精确请求；不可保存时零 POST、保留输入。上传只保存文件名/MIME/长度/SHA等恢复元数据，不在网页存储中保存文件字节。重开先查询原操作；未确认收件时须重新选择同一原件，校验其元数据与 SHA 后使用同一 key。404/503、超时、401/403 或丢失 COMMIT 回执不等于已失败，不静默生成新 key。明确 REJECTED 后才能显式放弃旧请求并提交新意图。

上传进度百分比是已发送字节，100%后仍等待服务器确认；只有 FILE_RECEIVED 表示已提交。FileStore失败返回安全503且不得声称已收件。COMMIT结果未知时保留原 key 和文件，查询/重试恢复，不做自动清理。私有原件下载每次重新检查当前权限及字节长度/SHA，响应 private,no-store/nosniff，审计成功下载；损坏或不可读返回503。

## 权限与接口

所有暂存读写（含模板、来源目录、历史、操作查询、原件）均要求当前 laboratory.write；仅 laboratory.read/assets.read/analysis.read 不够。HTTP 变更还要求同源 Origin 和会话 CSRF。角色撤销后旧 actor 及会话不能访问；原对象不会因此删除。

S1 路由统一位于 /api/laboratory/imports：

- GET /template、/sources、空路径列表、/operations/{key}、/{batch_id}。
- POST 空路径创建；POST /{batch_id}/files 接收指定 role 的原始字节。
- GET /{batch_id}/files 分页原件历史；GET /{batch_id}/files/{file_id}/original 下载。
- POST /{batch_id}/revisions 核对元数据/绑定/所采用原件；GET 同路径分页核对历史。

列表、原件与历史固定20项/页；批次列表支持 q（批次号/文件名）、state、purpose、来源 UUID、参与 actor UUID、UTC创建日 created_from/to。JSON请求最大32MiB。格式/字段/角色错误为422或415，大小413，私有资源不存在404，冲突409，数据库变更结果未知503 import_write_unknown、读取暂不可用503 import_read_unavailable、对象存储503 object_storage_unavailable；均不暴露 SQL、凭据或原件内容。

## 验证边界

S1 通过公开门面+真实 PostgreSQL、HTTP、真实生产构建浏览器和配置化 MinIO/Azurite 工作流验证收件/恢复。独立迁移用历史命名空间；HTTP/browser使用独立整库，避免 create_app 的 options 覆盖 search_path。具体命令、日志、结果与资源归属见 work-units/issue-52-s1.md。S2/S3 尚需验收解析/后台验证/问题分页/逐行核对；#53 负责正式发布，本入口没有发布按钮。



## S1 收件恢复修复契约（独立审查后有限修复）

同一次待确认提交只占用一个保存意图；文件摘要读取或请求完成前重复点击保存不会产生第二个 key。成功后可发起下一次明确上传；失败或响应未知仍保留原 key、参数与输入，按原操作查询/重试。

服务端严格 CREATE/REVISE 模型拒绝时，实验室门面先核实该输入确实无效，再在当前授权和 actor/key 锁下提交 REJECTED 操作与安全审计，之后 HTTP 才可返回422：

~~~json
{"code":"invalid_import_input","disposition":"DURABLE_REJECTED","operation":{"state":"REJECTED","action":"CREATE","batch_id":null,"result":{"code":"invalid_import_input","status":422,"details":null},"error_code":null}}
~~~

前端只在这个严格证明或原 actor 的 operation 查询明确 REJECTED 时显示显式“准备新的核对”动作。用户点击后可更正原输入，下一次提交才使用新 key；不会自动丢弃或更换。服务器大小写敏感的 IANA 名称拒绝也能按此流程恢复，不依赖客户端某一个时区的特判。

该证明表示拒绝记录已提交、业务写入未执行。普通命令采用规范化严格模型摘要；预绑定拒绝采用独立 rejection_contract=1 命名空间，只保存原解析 JSON 的规范摘要及修订路由批次上下文，避免把非法 NUL 等文本写入 JSONB。已有不同 action/参数或已完成操作不会被覆盖。审计失败、COMMIT未知、未确认读回都不返回该证明；401/403/404/503、无证明的422、格式损坏或丢失响应继续保留原意图。这不是取消、删除或代用他人 key 的接口。

批次历史 q 的文件名/批次号比较统一使用 PostgreSQL lower 对查询及被查文本两侧执行同一规则；不修改保留原名，不使用 Python casefold，也不把 ß 与 SS 合并为同一文件名。总数和20项分页来自同一个完整查询快照。来源实验室候选目录原有的 casefold 候选语义及显式稳定身份规则保持不变。

