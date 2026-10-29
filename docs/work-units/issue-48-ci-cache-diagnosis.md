# Issue48 PR62 CI cache-header diagnosis and fix

Gate PRreview→fix。Skill diagnosing-bugs，目标只修复真实代理链浏览器断言，不绕过checks。

## Phase1/2: red-capable loop
真实CI42e018a：343backendpassed/2existingwarnings；45browser中44passed/1failed，期望no-store实际no-store,no-store。先用既有真实API和原首条浏览器下载路径，在networkboundary replay捕获到的Cache-Control；最小化到首条test+重复header一项变量，未模拟私有应用对象。

Command frontend/: npx playwright test --config .cache/repro.config.ts --timeout=15000
RED 1failed，Expected no-store / Received no-store,no-store（716ms）。loop agent可运行、确定、秒级。普通本地Vite路径原10tests已green，只有生产Nginx代理有该重复形态。

## Phase3/4: ranked falsifiable hypotheses / probes
1. 断言把有效list当单值：如果是根因，仅重放duplicateheader会red、token语义会green；确实如此。
2. Backend重复/遗漏安全头：若backend有缺陷，directHTTP合同测试不会精确no-store；既有directHTTPpass，source assets/http.py:26只一次，排除backend漏/重复生成。
3. 下载错误响应/格式：若是根因，MIME/PK/filename/完整download先失败；所有这些先于header断言通过，排除。

假设顺序在测试前已commentary展示。读取CONTEXT与当前接口；本worktree无docs/adr，当前父规格/issue/已确认plan为约束。nginx.conf:17明确add_header no-store always，与backend同值；无须泛化日志/instrumentation或production改动。

## Phase5: minimal fix / controls
只改既有browserassert：对逗号分隔指令trim/casefold后toContain完整no-store token；不是substring放宽，没有移除cacheassert或test，API/NGINX原配置未改。重复值replay1pass（899ms），普通路径10browserpass；反向replay public,max-age=60仍在no-store断言处fail（622ms），证明安全要求未绕过。backend/React/schema/依赖/CIworkflow无变更。

## Phase6: cleanup / remaining validation
两个ignored临时replay/config文件已显式删除；无新增debuglog，无生产instrumentation。source regression留在原有首条browsertest，实际NGINX CI就是该回归接缝。最新commit必须在完整Linux生产构建CI复验；该remote复验是剩余owner=currentPRgate，不提前宣称成功。commit/PR说明需记录Nginx+API同指令合并这一根因。

原worktree/验收data保持；不新增凭据、收费服务或存储更换；无后续工单/merge。无架构接缝缺失，故不启动架构改造skill。
