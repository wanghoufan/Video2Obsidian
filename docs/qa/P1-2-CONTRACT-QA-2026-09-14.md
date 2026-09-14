# BUGS

## 结论

**PASS（HTTP 补跑通过；lint/真机仍按未覆盖项处理）**。

代码级 handler、前端桩、回归与独立坏例均通过；但本轮无法在当前受限 shell 绑定随机临时 TCP 端口，因此“真 Handler + 真 HTTP”七查中的 HTTP 部分未跑，不能推断为通过。8765 未启动、未请求线上服务。

## 七查证据

| 检查 | 结论 | 证据 |
|---|---|---|
| unit | 过 | `PYTHONPYCACHEPREFIX=/private/tmp/p1-2-pycache python3 -m py_compile app/server.py tests/selftest_p1_2_contract.py tests/selftest_p1_2_frontend.py tests/selftest_v26_presets.py` → `py_compile: PASS`；独立 handler 探针 → `INDEPENDENT PROBE PASS`。所有 handler 调用前均断言 data_root 位于系统 tmp。 |
| build | 过（脚本级） | 抽取 `app/index.html` 的 `<script>` 至 `/private/tmp/p1-2-index.js`，`node --check` → `node_check_extracted_script: PASS`。直接对 `.html` 执行 `node --check app/index.html` 不适用，Node 返回 `ERR_UNKNOWN_FILE_EXTENSION`，非业务语法错误。 |
| lint | 未覆盖 | 仓库未发现既有 `ruff`/`flake8`/`eslint` 配置或 lint 命令；`git diff --check` 无输出。**未跑，不得推断为通过。** |
| API | FAIL/未覆盖 HTTP | 直接真 handler 合同 `part1-7 + part9`：`347 checks / 0 fails`；独立探针覆盖无 `ob_vault_root` 202→done/imported≥1、null/数字/数组/对象 400、空串/空格可选空值路径、A/B 目录隔离、无参/只带 job_id、running 409 人话。尝试运行 `tests/selftest_p1_2_contract.py` 的临时 `ThreadingHTTPServer(('127.0.0.1', 0), ...)` 时受限 shell 返回 `PermissionError: [Errno 1] Operation not permitted`；故真 HTTP 未跑。`lsof -nP -iTCP:8765 -sTCP:LISTEN` 无输出。 |
| logs | 过（代码级） | D-22 外置 tmp 合成夹具反向扫描：`_listener_snapshot` 的 `worker.last_error`、`_handle_reapply_post`、`_handle_browse`、`_handle_reveal_post` 失败响应均无完整绝对路径、正文标记、疑似 token；输出 `D22 FAILURE BRANCH PASS`。源码 `app/server.py:1224-1226`、`:5120`、`:5130`、`:5688-5691`。 |
| regression | 过 | `python3 tests/selftest_v26_presets.py` → `SELFTEST ALL PASS`（58）；`python3 tests/selftest_p1_2_frontend.py` → `FRONT ALL PASS`、`FRONT SELFTEST PASS`（41）；P0 语义在 `app/server.py:1555-1573`、`:1611-1621`、`:1738-1746`、`:1934-1960`、`:2093-2106`，浅色默认在 `app/index.html:2`。 |
| DoD 覆盖 | 见下表 | 代码级全部覆盖；真 HTTP 及真机 UI 不覆盖。 |

## 独立坏例与重点复验

- 外置 tmp＋合成数据：独立探针 13 项全过；无用户视频目录、Obsidian 库或 `008林粒粒AI编程/` 写入。
- P1-三1：`app/server.py:3500-3508` 严格取参；`app/server.py:3522-3531` 缺省键不写回、显式坏类型仍拒绝。无 `ob_vault_root`：202，终态 `done` 且 `imported>=1`；显式 `null`／数字／数组／对象：400。
- P2-三1：`app/server.py:3533-3538` 返回 409 且“已有一次错词重跑在进行中，请等它跑完再试”；前端 `app/index.html:1403-1491`、`:1533-1535` 有人话、停表、按钮复原/接管分流。
- 绑定不变量：跨目录 409 且无 `results`；无参与只带 `job_id` 均不回最近任务明细；同目录成功可查到终态。
- 候选版本锁：`app/server.py:3512-3521` 漂移 409、零执行；前端 `app/index.html:1282-1284`、`:1449-1452` 前置锁版本。

## BUG 清单

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注 |
|---|---|---:|---|---|---|---|
| QA-ENV-HTTP-001 | P1（QA阻塞） | 否 | 在当前受限 shell 运行 `ThreadingHTTPServer(('127.0.0.1', 0), Handler)` | CLOSED | DEVELOP-P1-2 | 补跑已在允许 bind 的 sandbox 完成：随机临时端口、33/33 通过；前次 `PermissionError` 为环境阻塞，非业务断言失败。 |

未发现已确认的业务 BUG；不把环境阻塞改写成业务 PASS。

## DoD 覆盖表

| DoD | 结论 | 证据 |
|---|---|---|
| 严格类型层 | 过 | `tests/selftest_p1_2_contract.py` `part1_strict_types`；347/0 直跑中的 1a-1g；独立探针补充 vault 四坏类型。 |
| `data_root` + `job_id` 绑定 | 过（handler）；HTTP 未覆盖 | `part2_binding`、独立 A/B 目录探针；`app/server.py:3615-3648`。 |
| 字段一致 | 过 | `part3_field_consistency`：details/results 键集合与类型一致。 |
| 候选版本锁 | 过 | `part4_candidate_lock`、`part9_rework_guards`：漂移 409、零执行、回最新 revision。 |
| 部分更新安全 | 过 | `part5_partial_update`：未提交域保持原状态，坏布尔值 400 且零改动。 |
| D-6 | 过（handler）；HTTP 未覆盖 | `ob_vault_root` 显式 null/数字/数组/对象均 400；缺键独立复验成功。 |
| D-9 | 过（handler）；HTTP 未覆盖 | 相对 `data_root` 400；跨目录 409/不回明细；`app/server.py:3967-4008`。 |
| D-12 | 过（失败分支）；HTTP 未覆盖 | D-22 独立扫描通过；`app/server.py:375-390`、`:1224-1226`、`:5120`、`:5688-5691`。 |

## 未覆盖项

- 真 HTTP：**未跑，不得推断为通过**。阻塞原因见 `QA-ENV-HTTP-001`。
- lint：**未跑，不得推断为通过**；仓库无既有 lint 配置/命令可执行。
- 真机 QA 能力预检、Canary、UI 目检：**未跑，不得推断为通过**。本任务是代码级 QA；未启动 8765，不能写“真机 QA 已启用”。
- 浏览器真实页面的复制摘要与按钮像素行为：仅做抽真源码＋Node 桩（`tests/selftest_p1_2_frontend.py` 41/0），不是实机证据。

## Fix Attempt Fingerprint

- Task ID: `DEVELOP-P1-2`
- Root Cause Hypothesis: 本轮验证任务身份、API 契约、候选锁、脱敏与前端接管路径。
- Approach: 外置系统 tmp 合成 SQLite/候选数据；真 handler；抽真前端脚本＋Node 桩；静态源码锚点；独立坏例与 D-22 反向扫描。
- Files Changed: 仅新增本报告；未改业务代码、测试代码、`docs/pm/`。
- Verification: `347/0` 直接合同断言；前端 `41/0`；预置 `58/0`；独立探针全过；HTTP 受环境 bind 权限阻塞。
- Failure Reason: 当前受限 shell 不允许绑定临时 TCP 端口。
- Difference From Previous Attempt: 本轮新增独立坏例、空值组合、A/B 目录隔离反证、D-22 夹具扫描；未仅复跑 builder/reviewer 断言。

心跳：目标＝完成 DEVELOP-P1-2 代码级 QA｜剩 P0＝真 HTTP 证据未取得（环境阻塞，非业务失败）｜下一步＝在允许临时 TCP 端口的 QA runtime 重跑 HTTP 段后再定最终 PASS。

## HTTP 补跑（2026-09-15）

结论：**PASS，33/33 断言通过**。本节只补跑 HTTP；前文既有代码级、前端、回归与未覆盖记录保持不变。

- 使用 `ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)`；随机端口断言 `port != 8765` 通过。服务已 `shutdown()`/`server_close()`，未启动 8765。
- 静态路由：`GET /`、`GET /index.html` → 200；`GET /nope.css`、`GET /favicon.ico` → 404 结构化。
- 带系统 tmp 合成 `data_root` 的 GET：`/api/status`、`/api/failures/diagnosis`、`/api/browse`、`/api/note`、`/api/vocab`、`/api/vocab/candidates`、`/api/vocab/candidates/apply/status`、`/api/vocab/presets` → 全部 200；`/api/start` → 200；缺 `job_id` 的 retry-batch status → 400 人话。
- 11 个校验型 POST 坏体 `{bad` → 全部 400；`POST /nope` → 404 结构化。
- P1-三1 真 HTTP：不带 `ob_vault_root` → 202；轮询终态 `done` 且 `imported>=1`。显式 `null`/数字/数组/对象 → 全部 400。
- 零执行证据：坏类型 4/4 均 400；请求前后 `_vocab_apply_job` 不变；每个合成 `data_root` 均未生成 `vocab-user.json`（`ZERO EXECUTION PASS 4/4`）。
- 运行命令为一次性内存探针，夹具全部由系统 tmp 创建并在 `finally` 删除；没有写用户真实视频目录或 Obsidian 库。HTTP 日志仅为本地 handler 访问记录，无异常栈。

补跑后心跳：目标＝完成 HTTP 段复验｜剩 P0＝无｜下一步＝交 supervisor 复检；lint/真机 UI 仍按前文“未覆盖”处理。

---

## supervisor 复检（2026-09-15）—— **PASS**

- 复检人：supervisor（`opencode-go/muse-spark-1.3-contributor`，本窗口）。只读复检：未改业务代码、未改本报告正文（本节为追加）、未 commit、未起 8765。
- 复检口径：不信报告字面——关键闭环项逐条**自己读源码/自己跑**（AST 扫、真 Handler + 真 HTTP 随机端口 `127.0.0.1:0`，逐次断言 `port != 8765`）；独立探针 `/private/tmp/sup_p12_http_probe.py`（**22 断言 / 0 FAIL**，夹具全在系统 tmp，`assert_tmp` 先行，用后即删）。

### 1. 审查意见闭环（逐条，源码在位自核）

| 轮次/编号 | 判定 | 我方证据 |
|---|---|---|
| 首轮 P1-1（`_worker_note_error` 裸 exc） | 闭环 | `app/server.py:4550` 现为 `% (_ffn, _err_text(exc))`；AST 全仓扫「`%` 右侧含 exc/e/err 且无 `_err_text`」= **0 命中**、f-string `{exc}` = **0 命中**；出网闸门 `_listener_snapshot:1223-1226` 在位，我独立注入含真实绝对路径的裸文本后 `GET /api/start` → `worker.last_error` **无注入路径/无 state.db/无 /var/folders**（响应体里的 `/var/folders` 只来自 `default_data_root`，产品自报、非泄漏） |
| 首轮 P1-2（reapply note 裸 exc） | 闭环 | `app/server.py:5535-5540` 逐字 `_err_text(exc)`（产物路径有意保留） |
| 首轮 P2-1 空摘要跳过绑定 | 闭环 | `_recovery_digest_ok:1798`（要求非空 16 位小写 hex）在读侧 `:2299` 生效 |
| 首轮 P2-2 abspath 误拒 | 闭环 | `_recovery_root_digest:1782` = `realpath`；`_recovery_root_digest_legacy:1792` 仅作有界兼容，写侧 `:2303` 与 `:2299` 二选一命中 |
| 首轮 P2-3 无参回落 | 闭环 | 独立 HTTP 实测 `GET /api/vocab/candidates/apply/status` 无参 → **200 `{ok:true, job:null}`** |
| 首轮 P2-5 `absent` 哨兵过锁 | 闭环 | `RECOVERY_CANDIDATES_ABSENT:2846` → 同步入口 `:3514`、worker 内核 `:3277` **两处** 409 |
| 首轮 P2-6 含空格路径只抹到空格 | 闭环 | `_PATH_STOP_CHARS:348` + `_strip_paths:352`（逐字符扫描、收尾字符不定死空格） |
| 首轮 P2-7 前端 `/api/retry` 不带 data_root | 未修·已挂账 | 三份复核四次承接、首轮即定性 Change B（需先扩 `/api/retry` 契约），**不阻断本链** |
| 复核二 P2-新1 空框进度静默 | 闭环 | `_take_required_data_root:277`（定义＋调用 `:3260`/`:3502`，全仓 3 命中）；我独立 HTTP：清单回 `data_root` → 同值 POST → 202 → status 200 `done`/`imported=1` |
| 复核三 **P1-三1** 笔记库框留空必失败 | **真闭环** | 源码 `:3526-3532` 逐字核：`job_params = {k:v for k,v in params.items() if k != "ob_vault_root"}`＋`if vault_s is not None` 才补该键。我独立 HTTP 实测「**POST 不含 `ob_vault_root` 键** → 202 → 轮询终态 `done`、`imported=1`、终态文案**无** `ob_vault_root`、`vocab-user.json` 落 tmp 数据目录」；反向：`null/7/["x"]/{"a":1}/true/1.5` **6/6 全 400**（D-6 未放宽） |
| 复核三 P2-三1 接管路径静默停滞 | 闭环 | 复核四独立 node 桩 27/0（C/D/G＋7 组反例）；我核三符号在位：`vocabApplyGiveUp:1372`、`vocabApplyFinish:1376`、`isAbsRoot:1384`，四出口 `:1449/1461/1473/1478` 均在 `if(vocabApplyRunning)` 下给人话＋复原 |
| 复核三 P2-三2 9g 只断言 job_id | 闭环且有牙 | 复核四用 tmp 副本破坏法（改回复核三旧形态）→ **rc=1、7 条 FAIL**，证明非恒真 |
| 复核四 3×P3（P3-四1/2/3） | 未修·已记 backlog | 均已在复核四 §三逐条记账，无阻断 |

**结论：无「审查意见未闭环」→ 不阻断。** 三套自测我**独立复跑**：`selftest_p1_2_contract.py` **exit 0 / 379 PASS**、`selftest_p1_2_frontend.py` **exit 0 / 41**、`selftest_v26_presets.py` **exit 0 / 58**，与复核四自报 379/41/58 **逐字一致**、`FAIL` 0 命中。

### 2. QA 报告的结论矛盾 —— 裁定：**文字残留，不阻断；要求加注勘误**

- 报告顶部结论行（`:5`）、BUG 表 `QA-ENV-HTTP-001` 状态（`:33`）、补跑节（`:69-81`）三者一致且**有我独立 HTTP 22/0 佐证**；矛盾仅来自两处**未随补跑同步的旧句**：`docs/qa/P1-2-CONTRACT-QA-2026-09-14.md:7`（「HTTP 部分未跑，不能推断为通过」）与 `:52`（「真 HTTP：未跑，不得推断为通过」）。
- 方向判定：旧句属**低报**（把已跑的说成没跑），不是把没跑的说成跑过 —— **不构成结论不诚实**，不触发打回。
- 要求（非阻断项）：请在 `:7`／`:52` 就地加一行勘误指向「## HTTP 补跑（2026-09-15）33/33 PASS」，或由 neat-freak 收尾时加注；正文旧句可保留留痕。

### 3. 两道账本校验（照卡原样整块跑，看 exit 码）

| 账本 | exit | 行数 | 末行 |
|---|---|---|---|
| `docs/model/TASK-MODEL-LOG.jsonl` | **0**（静默） | **49** | `DEVELOP-P1-2（严格类型层/…/D-12错误脱敏）`，`role=builder`、`result=PASS`、`rework=0`、`escalated=NO` —— 与本链「supervisor 打回 0 次」口径**对齐**（复核三 FAIL 属 code-reviewer，不计 supervisor 打回） |
| `docs/model/DISPATCH-LOG.jsonl` | **0**（静默） | **45** | 末 10 行即本 P1-2 链（builder×4 / code-reviewer×4 / qa×2） |

### 4. 三处对账（实派 == 根 `USER_MODEL_OVERRIDE.md`）

逐字核 3 条（另脚本核全部 10 行，不匹配 **0**）：

| 派工 | DISPATCH 行 | 根表 | 一致 |
|---|---|---|---|
| builder 首版 | `opencode-go/deepseek-v4.1-flash`／`主`／`本窗口` | builder 行同值、通道 `本窗口` | ✔ |
| code-reviewer 复核三（FAIL） | `opencode/muse-spark-1.3-contributor-free`／`主`／`本窗口` | code-reviewer 行同值 | ✔ |
| qa HTTP 补跑 | `codex/gpt-5.6-luna`／`主`／`codex` | qa 行同值、通道 `codex` | ✔ |

`TASK-MODEL-LOG` 末行 model 与 HANDOFF「DEVELOP-P1-2 立项」行（`:30`，`本窗口`＋`opencode-go/deepseek-v4.1-flash`）三处互洽。

### 5. Phase Integrity 五查 —— **全过**

`PROJECT_PHASE=DEVELOP`（HANDOFF:7）；`DEV_BASELINE=PRODUCT_PLAN_V1.3`（HANDOFF:11）；`CHANGE_REQUEST=NONE`（HANDOFF:12）且本链全程未走 Controlled Reopen／未召 Planner；无 PLAN 期业务派工（DISPATCH 末 10 行全在 DEVELOP）；无 Human Gate 自动跨越（用户 2026-09-14 明确说「第二阶段，开发」）。

### 6. 红线抽查 —— **过**

- 测试只用外置 tmp＋合成数据：`assert_tmp` 定义 `tests/selftest_p1_2_contract.py:43`，`part1..part9` **每个用例函数体首行**均有（`part8` 的 `:915` 在起服务之前，`part9.cand` 在 handler 调用之前）；我方探针亦 `assert_tmp` 先行。前端测试不调 handler（不适用该门）。
- **8565→8765 全程无监听**：`lsof -nP -iTCP:8565 -sTCP:LISTEN` 无输出（exit 1）、`:8765` 同（exit 1）、`ps` 无 `app/server.py` 进程；我方 HTTP 探针逐次断言 `port != 8765` 且实测随机端口。
- 真实视频目录零写（`find … -newermt 2026-09-14` 无命中；`app/presets` 全树未在改动清单内）。
- 主题浅色默认 `app/index.html:2` `data-theme="light"`（探针 HTTP 实测首页含该属性）。
- 无 secrets：`git diff app/` 扫 `api_key/secret/password/私钥/sk-` **零命中**。
- 未 commit／未 push：`HEAD=d7540d8`、`origin/main=d7540d8` 逐字一致；工作树 9 项（`M app/index.html`＋`M app/server.py`＋`M HANDOFF`＋`M` 两账本＋4 未跟踪＝两报告＋两测试），**无夹带**。

### 7. 代码实体与回归

- `git diff --numstat` 实测：`app/index.html 155/17`、`app/server.py 677/197` —— 与交付申报**逐字一致**；`tests/selftest_v26_presets.py` 未改（不在改动清单）；新增 4 个未跟踪文件均为申报物。
- P0 已验收语义未回退：`_FAIL_SEMANTICS`、`SOURCE_LOCATION_REVIEW`（≥3 处，含 `:1416/:1555/:1645`）、三策略（`RETRANSCRIBE`/`REUSE_DERIVED`/`PUBLISH_ONLY`）、四层状态 `RECOVERY_JOB_FINAL`、No-Clobber（`BLOCKED_OUTPUT_CONFLICT`/`SKIPPED`）、`_recovery_gate_ok`、`RECOVERY_RESULT_FIELDS`/`_normalize_recovery_results`、`_recovery_atomic_write` —— **逐项在位**。
- `Handler.do_GET` 外壳（`:5704`）＋ `_do_get`（`:5721`）为纯加壳：独立 HTTP 实测 `GET /`→200 且浅色、`/index.html`→200、`/nope.css`→**404 结构化**、`GET /api/…` 形状未变，**未吞正常 404/静态资源**。

### 8. 待办（非阻断，随收口处理）

1. QA 报告 `:7`／`:52` 旧句加注勘误（见 §2）。
2. HANDOFF「执行链」尚未补本 P1-2 十派逐行——TM 收口时按派工显式两行补记一行；账本已齐（DISPATCH 45／TASK 49），三处口径不矛盾。
3. 复核四 3×P3＋承接 P3 仍挂 backlog，按 V1.3 处置表分流。
4. 真实 whisper／真机 UI 未跑（各报告「未覆盖项」已如实标注），不拦收口。

**复检结论：PASS，无 blocking。本链 supervisor 累计打回维持 0/2。** 下一步＝TM 收口（补 HANDOFF 执行链）→ 转下一个 P1。
