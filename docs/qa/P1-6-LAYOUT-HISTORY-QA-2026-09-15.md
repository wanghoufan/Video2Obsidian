# BUGS

## 结论

**PASS（代码级 QA；0 个业务 BUG）**。FR-10/11/12/15、HD-6=A、HD-7=A、HD-9=A、D-15 均有通过证据。HTTP 真 handler 绑定临时端口被当前沙箱禁止，真机 UI 未执行；两项均按“未跑，不得推断为通过”记录，不计业务 BUG。

基线：`HEAD=4d2686569dc8c614977ad6710b74a72b7fc90090`。QA 未改业务代码、未改 `docs/pm/`、未 commit/push；测试夹具均在系统 tmp，运行后清理。

## 七查

| 检查 | 结果 | 证据 |
|---|---|---|
| unit | 过 | `python3 tests/selftest_p1_2_frontend.py` → `FRONT SELFTEST PASS`，167 项 `PASS`、0 `FAIL`；独立 `/tmp` 合成 handler 探针 → `INDEPENDENT P16 PASS`。 |
| build | 过 | `PYTHONPYCACHEPREFIX=/private/tmp/p16_qa_pyc python3 -m compileall -q app src tests` → rc=0；抽取真实 `<script>` 后 `node --check` → rc=0。 |
| lint | 未覆盖 | 本仓无可执行 ruff/eslint 配置；`git diff --check` → rc=0 仅表示补丁无空白错误，不能替代 lint。未跑，不得推断为通过。 |
| API | 代码 handler 过；HTTP 未覆盖 | `_handle_status` 独立夹具通过：完成 10、`run_summary.done=10`、limit `1/3/20/200` 及 `0/-5/999` 钳制、页 `3/3/3/1`、坏游标 5 类 400、跨目录重放安全。`python3 tests/selftest_p1_2_contract.py` 前置 245 项 PASS/0 FAIL；在 `tests/selftest_p1_2_contract.py:949` 绑定 `127.0.0.1:0` 触发 `PermissionError: [Errno 1] Operation not permitted`，未进入 HTTP 断言。未跑，不得推断为通过。 |
| logs | 过（响应脱敏） | 独立坏游标响应均为 400、人话错误且不含临时绝对路径；代码统一由 `app/server.py:358` `_strip_paths` / `:391` `_err_text` 出口处理。测试 stderr 中的异常栈仅为沙箱阻止临时 socket 的本地测试栈，非业务 HTTP 响应。 |
| regression | 过 | `python3 tests/selftest_v26_presets.py` → `SELFTEST ALL PASS`，58 项；frontend 167 项全过；`git diff -- app/server.py app/index.html src tests` 无输出。8765 仅做 `lsof` 观察，未请求/绑定/停止。 |
| 真机 UI | 未覆盖 | 未跑，不得推断为通过。按要求应由本窗口 computer-use 另行完成预检与首页/窄屏/隐藏/展开操作。 |

## 重点独立证据

- 分页：手工创建 SQLite DDL、`jobs/*/manifest.json` 与合成 source；含 3 条相同 `completed_at`、9 条回退 `updated_at`、1 条孤儿映射和 1 条失败项。独立排序结果为 `orphan,r02,r01,r00,r08,r07,r06,r05,r04,r03`；`completed_total=10` 与 `run_summary.done=10` 一致；游标翻到底 `3/3/3/1`，无重复无遗漏。
- keyset：自算合法游标定位 `r02` 后严格返回更早项；不是 offset。用无密钥 SHA-256 自算签名的游标可被接受，确认前置评审 P3-1 的“可伪造”性质；它不是安全令牌，只能防普通篡改。
- 坏例：坏 base64、坏 JSON/格式、签名不匹配、改写 payload 后旧签名、超长 token 均 400；返回不泄漏 `data_root`。跨另一 tmp `data_root` 重放：当前实现返回 200 的无完成分页字段（空库错误快照），无原目录数据；如实记录为当前行为。
- 隐藏键：frontend S12 通过 abc/空串/中文 SHA-256 向量、不同目录隔离、切回保留、取消可逆、空输入使用 `effectiveDataRoot`；源码 `app/index.html:376-383` 仅 localStorage 读写，未与 `/api/clear` 或 DELETE 关联。业务清空入口是独立的 `app/index.html:2419,2462`。
- 布局：`app/index.html:33-41` 无 sticky/fixed，`.flowbar` 普通流、高度由 `padding:6px` 形成约 36px；两列 `minmax(0,1fr) 300px` 与 `@media(max-width:960px)` 单列；DOM 顺序 `:189` 横条→`:192` 主列。默认浅色 `:2` 未变。
- 零回退：`display_state`、`persisted_state`、`diagnosis_snapshot_id` 仍在 `app/server.py:1609-1665`，`_strip_paths` 在 `:358`；业务代码/测试目标范围相对 HEAD 无 diff。

## BUG 清单

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注 |
|---|---|---:|---|---|---|---|
| — | — | — | — | 无业务 BUG | DEVELOP-P1-6 | 已知沙箱禁止 loopback 临时 bind 与真机 UI 未跑，均为未覆盖/环境限制，不登记为业务 BUG。 |

## DoD 覆盖表

| DoD | 结论 | 证据 |
|---|---|---|
| FR-10 顶部横条 | 过 | `app/index.html:33-41,189-191`；frontend L1-L5 全过。 |
| FR-11 栅格响应式 | 过 | `app/index.html:35-36`；frontend layout checks 通过。 |
| FR-12 完成列表分层＋cursor 历史 | 过 | `app/server.py:2853-3016,4414-4421`；独立夹具与 contract part14 代码级断言覆盖。 |
| FR-15 隐藏已完成 | 过 | `app/index.html:376-383,717-767`；S12 10 项全过；只视图过滤、可恢复。 |
| HD-6=A | 过 | 完成统计与 keyset 分页独立实算，`completed_total == run_summary.done`。 |
| HD-7=A | 过 | SHA-256 前 8 位按 `data_root` 分区；不同目录隔离、切回保留、可逆。 |
| HD-9=A | 过 | 横条普通流、不 sticky、不收起；响应式布局静态断言通过。 |
| D-15 | 过 | 当前/失败/孤儿可达、完成标记、并列 `run_id DESC`、回退时间、尾页、坏游标、范围、幂等、state 字段均覆盖。 |

## 真机 QA 会话能力预检

- 日期/任务名：2026-09-15 / DEVELOP-P1-6
- session/model/runtime：未启动真机 session；不伪填模型或 Runtime。
- 最终结论：`NOT_VERIFIED`
- 是否允许进入正式 QA：NO
- 原因：本轮未执行 computer-use 真机预检；真机 UI 未跑，不得推断为通过。

## 未覆盖项（未跑，不得推断为通过）

1. 临时端口真实 HTTP 请求：contract 在创建 `127.0.0.1:0` server 时被沙箱 `PermissionError` 阻断。
2. computer-use 真机目检及真实点击/展开/隐藏/窄屏流程。
3. 真实视频转写、真实大规模历史数据性能。

## Fix Attempt Fingerprint

- Task ID: `DEVELOP-P1-6`
- Root Cause Hypothesis: 不适用；本轮未发现业务缺陷。
- Approach: 既有自测 + 独立 tmp SQLite/manifest 合成夹具 + 静态源码/Node 语法核验。
- Files Changed: 仅新增本 QA 报告；业务文件零改。
- Verification: contract 前置 245 PASS/0 FAIL（HTTP 段受环境阻断）；frontend 167 PASS；v26 58 PASS；compileall/node/diff-check/独立 P16 均 rc=0。
- Failure Reason: HTTP 真请求与真机 UI 未跑，原因分别为沙箱 loopback 限制与本轮未启动 computer-use session。
- Difference From Previous Attempt: 新增独立非 77 条夹具、极限 limit、keyset 无重复遗漏、P3-1 自算签名及跨目录重放复核。

---

## supervisor 复检（链收口，2026-09-15；模型 `opencode-go/muse-spark-1.3-contributor`，本窗口 subagent 直派）

- **裁定：PASS —— 放行 commit/push `main`**。本链打回计数 **仍 0/2**（本次未打回，不升级）。
- 交付实体核对：`HEAD=4d26865`（已提交、未推送，`origin/main..HEAD` = 1）；`git show --numstat HEAD` 实测 `app/server.py 178/1`、`app/index.html 178/25`、`tests/selftest_p1_2_contract.py 254/0`、`tests/selftest_p1_2_frontend.py 135/3` —— **与派单书声明逐字一致**（code-reviewer P3-2 的 numstat 口径差按实测收口，无残留分歧）。工作树仅 `M docs/handoff/HANDOFF.md`（TM 落盘）、`?? .codebuddy/`（会话产物，不提交）、本 QA 报告未跟踪。

### 1. 三套自测实跑（证伪前 1 轮 ＋ 还原后复跑 1 轮，共 2 轮，全部同数）
| 自测 | rc | PASS | FAIL | 备注 |
|---|---:|---:|---:|---|
| `tests/selftest_p1_2_contract.py` | 0 | **512** | 0 | 含 part8 真 HTTP 段 ＋ part14 D-15 段 |
| `tests/selftest_p1_2_frontend.py` | 0 | **167** | 0 | 含 S12 10 项 ＋ L1-L5 布局/零回退守卫 |
| `tests/selftest_v26_presets.py` | 0 | **58** | 0 | 词库域 |
- 与 builder／qa 声明数 **512/167/58 逐数一致**；qa 因沙箱只跑到 contract 前置 245 项，本窗口跑满 512。

### 2. qa「HTTP 未覆盖」补位（判定＝环境限制，已补位）
- `tests/selftest_p1_2_contract.py:949` 的 `ThreadingHTTPServer(("127.0.0.1", 0), ...)` 在**本窗口正常 bind**，part8 真 HTTP 段 27 项断言全 PASS；`PASS 8 端口不是 8765（不碰线上服务）` 在位（:951 硬断言）。
- 追加探针 `/tmp/p16_sup_http_probe.py`（**不入仓库**）：rc=0，**27 项断言全 PASS**。真 HTTP 起随机端口（硬断言 `port != 8765`），覆盖 qa 完全没碰到的 **P1-6 新面**：
  - `/api/status` 真请求：`completed_total=61 == run_summary.done`、`completed_limit` 默认 20、首页 20 条、`next_cursor` 存在、完成行 `completed:true`、`recent_runs` 原样全量 77；
  - cursor **真翻页**：页大小 20/20/20/1、61 条**无重复无遗漏**、顺序 ＝ 测试侧独立复算全序、同游标幂等；
  - 负例：篡改签名 400／坏格式游标 400／`completed_limit=abc` 400／`=5000` 钳到 200、400 响应体不含夹具绝对路径；
  - 首页响应体（真 HTTP 返回，非抽源码）：`.flowbar` 在位、`minmax(0,1fr) 300px`、`@media (max-width:960px)`、**无 `position:sticky`**、`"v2o-hide-done-"+sha256Hex` 摘要键；隐藏请求对夹具树字节零写。
- 结论：qa 的「①临时端口真实 HTTP 请求」确系 **codex 沙箱禁 loopback bind 的环境限制**，本窗口已补位通过 —— **不登记为业务 BUG，qa 该条判断正确**（qa 报告未覆盖项①可据此判 CLOSED）。

### 3. 反向证伪 4 条（全部有牙；备份 `/tmp/p16_sup_bak/`，还原用 `cp`，**禁 `git checkout`**）
| # | 改坏点 | 位置 | 结果 |
|---|---|---|---|
| M1 | keyset 边界 `<` → `<=`（越界回含上页尾） | `app/server.py:2988` | contract **rc=1**，3 FAIL：`14d 展开全 61 无重复遗漏`（实得 **64**）、`14d 页大小 20/20/20/1`（实得 20/20/20/**4**）、`14g keyset 非 offset` |
| M2 | cursor 签名校验短路（`if not hmac.compare_digest(...)` → `if False and ...`） | `app/server.py:2883` | contract **rc=1**，1 FAIL：`14h 篡改签名（坏游标 400 人话）`（实得 200） |
| M3 | 隐藏键改原始路径（`sha256Hex(dr).slice(0,8)` → `dr.slice(0,8)`） | `app/index.html:380` | frontend **rc=1**，1 FAIL：`L3 隐藏键按 data_root 摘要分区`（静态守卫抛 AssertionError） |
| M4 | `.flowbar` 加 `position:sticky;top:0` | `app/index.html:39` | frontend **rc=1**，1 FAIL：`L1 不 sticky（反向证伪：加回 sticky 即挂）` |
- 还原核验：`cp /tmp/p16_sup_bak/* ` 回位后 5 文件（server.py／index.html／两套测试／v26）**sha256 与改前基线逐字一致**（`shasum -a 256` 两次输出 `diff` 为空）；`git status --porcelain -- app/ tests/` 与 `git diff --numstat HEAD -- app/ tests/` **均为空**（工作树 == HEAD）。**未使用 `git checkout`**。

### 4. 两账本第二道校验 ＋ 负控（只看 exit 码）
- `docs/model/DISPATCH-LOG.jsonl`：非空 **78** 行（`_example` 0 行），8 键／`used` 恒 `主`／`result`／`runtime` 枚举全过 → **exit 0**。
- `docs/model/TASK-MODEL-LOG.jsonl`：非空 **53** 行（`_example` 0 行），11 键／`result`／`escalated` 枚举／`rework` int（含 int-vs-bool）全过 → **exit 0**。
- **行数对账**：派单书写「DISPATCH 现 79 行」，**实测真值 78 行**（与 HANDOFF「78 行」一致；差的 1 行＝**本次 supervisor 派工行**，按规矩由 TM 收口时补）。**TASK 53 行与 HANDOFF 一致**。
- **负控（坏例必须 exit≠0）**：11/11 有牙 —— TASK 校验器 6/6（缺键 task／result 枚举错／escalated 枚举错／`rework` 含 bool／`rework` 字符串／JSON 坏）；DISPATCH 校验器 5/5（缺键 note／`used` 非主／result 枚举错／runtime 枚举错／JSON 坏）。`{"_example":true,...}` 行两器均正确跳过（exit 0/0）。

### 5. 三处对账（表 vs `used` vs 实派）
- **本链 P1-6：0 不匹配** —— builder `opencode-go/deepseek-v4.1-flash`（本窗口）、code-reviewer `opencode/muse-spark-1.3-contributor-free`（本窗口），与 `USER_MODEL_OVERRIDE.md` 表逐字一致；supervisor 本次实派 `opencode-go/muse-spark-1.3-contributor`（本窗口）同表。全表 78 行 `used` **全部＝主**。
- **全表逐行对账发现 2 行历史不一致（不阻塞、不回改旧账）**：`L1 迁移整理` supervisor = `deepseek-v4.1-flash`/`codebuddy`、`L8 DEVELOP-P0-1首版` builder = `codex/gpt-5.6-luna`/`codex` —— 二者均为 **2026-09-13 表换代（4 列版）之前**的既成历史行（见 `经验一句话.md` 2026-09-13「表已换代」），非本链问题；建议 TM 不追改，只在本报告与 HANDOFF 记一句备查。
- Phase Integrity 五查：`PROJECT_PHASE=DEVELOP`、`DEV_BASELINE=PRODUCT_PLAN_V1.3` 在位；PLAN 阶段零 builder／qa 业务派工；无未授权的自动开发；无 C 类变更绕 Controlled Reopen → **过**。

### 6. 红线逐项
- **secrets**：HEAD 新增行 0 命中真实密钥（仅 HANDOFF 正文出现「不碰 secrets」字样）；无 `.env`／token 入库。
- **封存物**：HEAD 触碰 8 文件（4 业务/测试 ＋ HANDOFF ＋ DISPATCH-LOG ＋ 2 份 review 报告），**未碰 V1.10/V2.0 封存物、未碰 `008林粒粒AI编程/`**。
- **外置 tmp＋合成数据**：part14 夹具首行 `assert_tmp`（`tests/selftest_p1_2_contract.py:2098`）＋`make_data_root` 入口断言；本探针同样先断 `data_root` 在系统 tmp（实得 `/private/var/folders/.../T/p16_d15_*`）→ 过。
- **用户真实数据零写**：仓库 `data/`、`Downloads/需转录视频`、`Downloads/暂不转录视频`、Obsidian 库 **近 2h 内改动文件数全部为 0**。
- **8765 外部进程零扰动**：探针用随机端口且硬断言 `!=8765`；前后两次 `lsof -nP -iTCP:8765 -sTCP:LISTEN` 均为 **PID 6586**，`ps` 启动时间 **11:41:30 未变**（未杀、未 bind）。
- **探针落点**：全部落 `/tmp`（`p16_sup_*`），仓库内 `git status` 零残留。

### 7. 放行裁定与 TM 收口必办
- **裁定：PASS，放行 `commit/push main`**（`DEV_BASELINE=PRODUCT_PLAN_V1.3` 下 P1-6 链四角色闭环：builder PASS → code-reviewer PASS（无 P0/P1，P3×5 挂 backlog）→ qa PASS（0 业务 BUG）→ supervisor PASS）。
- TM 收口必办（均非打回项，随本次提交一并落盘）：① `DISPATCH-LOG` 补 supervisor 行（78 → 79）② `TASK-MODEL-LOG` 落 P1-6 任务行（53 → 54，`rework=0`、`escalated="NO"`）③ 本 QA 报告（含本节）＋ HANDOFF 回写一并 commit/push。
- 未覆盖项如实保留、不得推断为通过：② computer-use 真机 UI（含真点击展开/隐藏/窄屏）③ 真实视频转写与大规模历史性能 —— 均并入 P1-1，不拦本次提交。
