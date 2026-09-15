# BUGS

## 结论

**PASS（无 P0/P1 阻断；`QA-P13-P2-3-UNKNOWN-STATE` 已 CLOSED；仅保留既有 `QA-P13-P2-4-REAPPLY-MUTEX` backlog）**。

本轮只复验 P2-3 与 P3-新1：独立真函数、三套回归、上一轮坏例集、随机端口真 HTTP 与两条反向证伪均完成。P2-3 已统一为唯一真源并通过未知/空 state 与缺键防误伤矩阵；P3-新1 尾句已删除且三链共用锁定真话保留。真机 UI 未验证。

## 七查证据

| 检查 | 结论 | 命令与证据（rc） |
|---|---|---|
| unit | 过 | `python3 tests/selftest_p1_2_contract.py` → `SELFTEST ALL PASS（429 项断言）`，rc=0；独立 tmp 合成坏例 16/16 PASS，rc=0。所有 handler 夹具首行断言 `data_root` 位于系统 tmp。 |
| build | 过（脚本级） | `PYTHONPYCACHEPREFIX=/tmp/qa-p13-pycache python3 -m compileall -q app` → rc=0；前端脚本由 `python3 tests/selftest_p1_2_frontend.py` 解析执行，rc=0。仓库无独立构建配置。 |
| lint | 未覆盖 | `find . -maxdepth 2 -type f \( -name package.json -o -name Makefile -o -name pyproject.toml -o -name 'requirements*.txt' \)` 未发现可用 lint 配置；`git diff --check` 无输出，rc=0。不能据此推断 lint 通过。 |
| API | 过（真 HTTP） | 独立内联 Python 探针：`ThreadingHTTPServer(('127.0.0.1', 0), Handler)`，随机端口首页与 `/api/vocab/candidates` 真请求，16/16 PASS，rc=0；端口断言 `!=8765`，服务已 shutdown/close。 |
| logs | 过（脱敏静态与回归） | `rg -n '/Users/|/private/var|/var/folders|/tmp/' app/index.html app/server.py` rc=0，仅命中示例占位文案/脱敏扫描器词面；无动态真实路径出口。合同自测 D-12 相关断言 rc=0。 |
| regression | 过 | `python3 tests/selftest_p1_2_frontend.py` → `FRONT ALL PASS` / `FRONT SELFTEST PASS`，rc=0；`python3 tests/selftest_v26_presets.py` → `SELFTEST ALL PASS`，rc=0；主题浅色 `app/index.html:2` 静态在位。 |
| DoD 覆盖 | 过（含已知 P2） | 七项逐项见下表；真机 UI 不覆盖。 |

## 七项验收与独立坏例

| # | 结论 | 证据与独立复验 |
|---|---|---|
| 1 无目标不画 100% | 过 | `app/index.html:1433-1436` 的 `vocabApplyPct` 在 `total<=0` 返回 0；主进度入口与唯一候选进度入口均有总量守卫。前端自测 S8a/S8j/S8j2 rc=0；空候选/无目标独立夹具确认零目标文案与 0% 口径。 |
| 2 运行中参数锁定 | 过 | 前端 `app/index.html:1345-1359` 禁用策略/范围/批量控件并写锁定提示；后端 `_handle_vocab_candidates_apply` 的运行锁在版本锁前，`_vocab_apply_locked_response` 回 409 人话且同目录才回 `locked_params`。独立 tmp 变更提交 → 409，快照字节不变，零执行零写盘。 |
| 3 零目标/坏文件 | 过 | `_vocab_candidates_read`：`app/server.py:3233-3257` 区分 missing/corrupt/ok；前端 `app/index.html:1380-1392` corrupt 不落“暂无待审候选”。独立夹具：missing/corrupt 分开、corrupt 原文件不变；空 indices → 400，含“没有勾选/零目标”。 |
| 4 五桶统计可复算 | **过（P2-3 CLOSED）** | `STATE_BUCKET`/`_state_bucket` `app/server.py:1767-1795` 为唯一真源；两链分别在 `:1798-1800`、`:5570-5592` 派生。独立覆盖未知、空串、空白、None、合法 `PUBLISHED` 与无 state 键；逐条同源等式通过，五桶 `total==Σ`/balanced 通过。 |
| 5 elapsed/可离开提示 | 过 | `_elapsed_seconds` `app/server.py:4281-4308`；前端 `app/index.html:1420-1427`。独立坏/缺时间戳返回 0 不抛；前端自测 S8c 与回归通过。未做强制取消，符合范围。 |
| 6 二选一不得双空 | 过 | 策略控件 `app/index.html:1648-1658`；范围 `:2120-2137`。前端自测 S8f/S8h：双空回安全侧并提示，不生成双空语义；rc=0。 |
| 7 `/api/retry` data_root | 过 | 前端 `app/index.html:1090-1106` 与单/批量接线；后端 `app/server.py:5009-5050`。独立 tmp：跨目录 409 且 worker 快照不变；相对路径 400；缺键对当前任务返回旧行为 202。 |

独立坏例还覆盖：真 HTTP Handler、corrupt/missing、运行中 409、五桶复算、未知 state、elapsed 坏值/缺失、零目标文案、`/api/retry` 三路径。未使用用户视频目录或 Obsidian 库。

## 上一轮返工重点复验

- P2-1：`app/index.html:1186`、`:1195` 明确“需保持本页打开”；`reapplyAll` `:1270` 明确同步服务端任务可离开；异步词库任务 `:1424`、`:1427` 保留可离开提示。通过。
- P2-2：`retryRootHint:1090-1091`、本地门 `retryBody:1099-1106`、批量 `noteBad:1188-1202` 均透出 400/409 人话；前端自测 S9c-S9h 通过。通过。

## BUG 清单

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注 |
|---|---|---:|---|---|---|---|
| QA-P13-P2-3-UNKNOWN-STATE | P2 | 否 | 独立探针覆盖 `WEIRD_UNKNOWN`、`""`、`"   "`、`None`、合法 `PUBLISHED` 与缺 state 键 | **CLOSED，本轮复验通过** | DEVELOP-P1-3 | 未知/显式空 state → `failed`；合法 `PUBLISHED` → `success`；缺 state 键且 `ok=true` → `success`。与 `_recovery_bucket` 对照逐条通过；反向证伪两条均有牙。 |
| QA-P13-P2-4-REAPPLY-MUTEX | P2 | 否 | 静态核对 `app/server.py:3501-3502` 内部调用 `_handle_reapply_post`，而 `:5968-5994` 无运行中互斥；运行中可另起 `/api/reapply` 并行 | OPEN，既有残留 | DEVELOP-P1-3 | 本轮未引入；需后续用 `internal=True`/明确互斥修复，不能在当前内部调用上直接加锁，否则会自锁。 |

无 P0/P1；无因本轮变更新引入的 P0/P1。

## DoD 覆盖表

| DoD | 结论 | 证据 |
|---|---|---|
| 无目标不画 100% | 过 | `index.html:1433-1436`、前端 S8a/S8j；总量守卫。 |
| 运行中参数锁定 | 过 | `server.py:3638` 附近锁定响应、`app/server.py` 异步入口锁检查；tmp 409 零写盘。 |
| missing/corrupt 分流 | 过 | `server.py:3233-3257`；独立 missing/corrupt 夹具。 |
| 失败五桶可复算 | 过 | `STATE_BUCKET` 唯一真源；未知/空 state fail-closed，缺 state 键仍按既有 `ok` 回落；独立 6 类矩阵与五桶复算通过。 |
| elapsed 与可离开提示 | 过 | `server.py:4281`、`index.html:1424-1427`；坏时间戳独立通过。 |
| 二选一安全默认 | 过 | `index.html:2120-2137`、前端 S8f/S8h。 |
| `/api/retry` data_root | 过 | `server.py:5009-5050`、`index.html:1090-1106`；跨目录/相对/缺键独立通过。 |
| D-12 脱敏、No-Clobber、词库三铁律、浅色默认 | 过（代码级） | 三套自测 rc=0；`index.html:2`；坏候选读取前后字节一致；路径扫描未发现动态绝对路径出口。 |

## 未覆盖项

- 真机能力预检、Canary、截图、读屏、点击、输入、滚动、像素 UI 目检：**NOT_VERIFIED**，本次未启动 8765，也未执行原生桌面 UI 自动化。
- lint：仓库未提供可执行 lint 配置/命令，未覆盖。
- 真实 whisper、61 篇规模、真实长视频耗时：未覆盖，不能推断通过。
- 多标签页真实并发、`/api/reapply` 注入级并行写盘竞争：未覆盖；P2-4 以静态证据保留。
- 用户真实视频目录与 Obsidian 库：按硬约束未读写。

## 真机 QA 会话能力预检结果

- 日期/任务名：2026-09-15 / DEVELOP-P1-3
- session ID：N/A（代码级 QA，未开启真机 session）
- 模型精确 ID：按 `USER_MODEL_OVERRIDE.md` 为 `codex/gpt-5.6-luna`；本报告由当前 QA 会话执行
- Runtime：未启动真机 Runtime；未执行 Orca 权限查询
- 原生 CUA 是否实际注入：本次未使用，未验证读屏/截图/点击能力
- 可用工具精确名称：未将桌面 CUA 纳入本轮；仅使用 shell/Python/Node 代码级工具
- 读屏/截图/点击/输入/滚动/界面恢复：均未执行，不能以静态源码或命令输出冒充
- 最终结论：**NOT_VERIFIED**
- 是否允许进入正式真机 QA：否；本报告仅覆盖代码级 QA

## Fix Attempt Fingerprint

- Task ID：`DEVELOP-P1-3`
- Root Cause Hypothesis：本轮修正进度零目标、批量参数锁、候选清单三态、统计统一、elapsed、二选一与 retry 目录身份。
- Approach：外置系统 tmp 合成数据；独立 handler 探针；随机端口真实 HTTP；前端现有 Node 桩；静态行号与反例核对。
- Files Changed：仅新增本报告；未改业务代码、测试代码、其它 docs；未 commit/push。
- Verification：合同 429/0、前端 selftest rc=0、词库 selftest rc=0、独立坏例 16/16、真 HTTP rc=0、diff-check rc=0、py compile rc=0。
- Failure Reason：首轮曾确认 P2-3 未知 state fail-closed 不一致；本轮返工复验已关闭该 BUG。真机/lint/真实 whisper 仍未覆盖。
- Difference From Previous Attempt：本轮补跑 445/87/词库回归、独立 6 类 state 矩阵、19 项坏例/随机 HTTP，并用两条旧形态反向证伪确认修复有牙且无过度修正；不采信 builder 自测作为唯一证据。

心跳：目标＝完成 P1-3 代码级 QA｜剩 P0/P1＝无｜下一步＝复验 P2-3/P3-新1。

## 复验（2026-09-15，同链续 session）

### 结论

**PASS。`QA-P13-P2-3-UNKNOWN-STATE` 同意 CLOSED；`QA-P13-P2-4-REAPPLY-MUTEX` 保持 OPEN（既有残留，TM 已判本链不修，进入 backlog）。**

本节只复验 P2-3 与 P3-新1，没有重新执行上一轮全量取证。真机 UI 仍为 `NOT_VERIFIED`；8765 无监听。

### 实跑命令与 rc

| 命令 | 结果 | rc |
|---|---|---:|
| `python3 tests/selftest_p1_2_contract.py` | `SELFTEST ALL PASS（445 项断言）` | 0 |
| `python3 tests/selftest_p1_2_frontend.py` | `FRONT ALL PASS` / `FRONT SELFTEST PASS`（87） | 0 |
| `python3 tests/selftest_v26_presets.py` | `SELFTEST ALL PASS` | 0 |
| `git diff --check` | 无输出 | 0 |
| 独立内联 Python：P2-3 6 类矩阵＋上一轮坏例集＋随机端口 HTTP | 独立检查 19/19 PASS；所有 handler 夹具首行断言 `data_root` 位于系统 tmp；HTTP 端口 `!=8765`，结束后 shutdown | 0 |
| 反向证伪 1：临时退回旧 `_reapply_result_bucket`，断言未知 state 必须 failed | 断言失败，证明旧形态仍暴露 BUG | **1（预期）** |
| 反向证伪 2：临时把 `if "state" in item` 改为 `if True`，断言无 state 键仍 success | 断言失败，证明过度修正会误伤旧条目 | **1（预期）** |
| `sha256sum app/server.py app/index.html`（还原后） | `433dd62c…657f14b`、`858080fc…d4c38c`，与动手前给定基线逐字一致 | 0 |
| `lsof -nP -iTCP:8765 -sTCP:LISTEN` | 无监听 | 0（无输出） |

补充：独立探针第一次把浅色主题断言写成过严的 `<html data-theme="light">`，源码实际为 `<html lang="zh-CN" data-theme="light">`，因此首次探针为 30/31、rc=1；修正探针后重跑为 19/19、rc=0。该次为 QA 探针误报，不是业务 BUG。

### P2-3 独立复验明细

| 输入 | `_reapply_result_bucket` | `_recovery_bucket` 对照 | 结论 |
|---|---|---|---|
| `{"ok":true,"state":"WEIRD_UNKNOWN"}` | `failed` | `still_failed` | 过，唯一真源映射一致 |
| `{"ok":true,"state":""}` | `failed` | `still_failed` | 过，显式空值不回落 |
| `{"ok":true,"state":"   "}` | `failed` | `still_failed` | 过，显式空白不回落 |
| `{"ok":true,"state":None}` | `failed` | `still_failed` | 过，显式 None 不回落 |
| `{"ok":true}` | `success` | 不适用（恢复链只接收 state） | 过，缺键保留旧条目兼容行为 |
| `{"ok":true,"state":"PUBLISHED"}` | `success` | `recovered` | 过，合法成功态不被误伤 |

逐条核对 `STATE_BUCKET`、`_state_bucket`、`_RECOVERY_BUCKET_NAMES`：有 state 键的 5 类输入均满足 `reapply == _RECOVERY_BUCKET_NAMES[_state_bucket(state)]`；缺 state 键单独走既有 `ok` 回落分支。

### P3-新1 复验

- `app/index.html:1360` 当前 `#batchLockHint` 只写“批量任务进行中：本次执行参数（范围、策略、rerun_old、目标候选集合）已锁定，本次不改，跑完再改。”，越界尾句“进度条会显示已用时”已删除。
- 既有前端断言 `S8d` 与 `9b` 通过：锁定原因与参数范围仍在；`9b1` 通过：没有把只对错词重跑成立的进度条/已用时指针误写到三链共用提示。
- 源码对照：错词重跑自己的 `app/index.html:1424-1427` 仍保留“可离开＋已用时”；批量重试 `:1186/:1195` 仍明确需保持页面打开；重新成稿 `:1270` 仍保留服务端同步可离开事实。三条链的锁定真话未被删。

### 复验后 BUG 状态

| Bug ID | 状态 |
|---|---|
| `QA-P13-P2-3-UNKNOWN-STATE` | **CLOSED**：独立矩阵、同源等式、445/87/词库回归、反向证伪均通过。 |
| `QA-P13-P2-4-REAPPLY-MUTEX` | **OPEN**：既有残留；TM 已判本链不修，进入 backlog。 |

### 复验真机门禁

真机 UI 预检、Canary、截图、读屏、点击、输入、滚动均未执行，结论仍为 **NOT_VERIFIED**；未启动服务，未编造像素或真机证据。

复验心跳：目标＝复验 P2-3/P3-新1｜剩 P0/P1＝无｜P2-3＝CLOSED、P2-4＝OPEN backlog｜下一步＝交 supervisor 复检。

## supervisor 复检（2026-09-15，`opencode-go/muse-spark-1.3-contributor`／本窗口）

- **结论：PASS（收口）**。本链累计打回 **0/2**（本轮新增 0 —— 无 P0 未闭环、无审查意见未闭环、无缺输出）。**无 blocking**。只读复核：**未改业务代码/测试代码、未改任何报告正文**（本文件只在尾部追加本节）、未 commit/push、未起 8765、未请求线上服务、未读写用户真实视频目录与 Obsidian 库。工作树 7 改＋2 新，与两报告申报范围一致，无夹带未申报改动。

### ① 实跑命令与 rc（我自己跑的，不看转述）

| # | 命令 | 实测输出 | rc |
|---|---|---|---|
| 1 | `python3 tests/selftest_p1_2_contract.py` | `SELFTEST ALL PASS（445 项断言）`（`^PASS` 445 行） | **0** |
| 2 | `python3 tests/selftest_p1_2_frontend.py` | `FRONT ALL PASS`＋`FRONT SELFTEST PASS`（`^PASS` 87 行） | **0** |
| 3 | `python3 tests/selftest_v26_presets.py` | `SELFTEST ALL PASS`（`^PASS` 58 行） | **0** |
| 4 | `git diff --check` | 无输出 | **0** |
| 5 | `shasum -a 256 app/server.py app/index.html` | `433dd62c…f14b`／`858080fc…d38c`，与派单书给定基线**逐字一致** | 0 |
| 6 | `lsof -nP -iTCP:8765 -sTCP:LISTEN` | 无输出（无监听） | 0 |
| 7 | `python3 /tmp/sv13_probe.py`（**我方独立探针**，43 项） | `PROBE ALL PASS` 43/43 | **0** |

三套自测 rc 全 0、断言数与两报告复验节（445／87／58）**逐项对上**。抽跑段位：`S9` 段 19 条（9a×5／9b×2／9b1／9b2／9c×3／9d／9e／9f×3／9g／9h）全 `PASS`；`10a3`／`10a4` 段 16 条全 `PASS`。

### ② 两道账本校验（只看 exit 码）

- `TASK-MODEL-LOG.jsonl`（**50 行**）→ **exit 0**（静默，无坏行）。
- `DISPATCH-LOG.jsonl`（**56 行**）→ **exit 0**（8 键齐、`used` 恒 `主`、`result`/`runtime` 枚举合法）。
- **负控（防「只计算不 exit(1)」的历史坑）**：我另造坏行跑同两块——`runtime="bogus"`＋`result="MAYBE"` → **exit 1**；`rework=true`（bool 不算 int）→ **exit 1**。⇒ 校验器**有牙**，本轮 exit 0 不是空转。

### ③ 三处对账：**不匹配行数 = 0**

对账口径＝HANDOFF 执行链 11 派（`:35-47` ①②③④⑤⑥⑦⑧⑨⑩⑪）↔ `DISPATCH-LOG` L46-56（11 行，逐行 `role`/`model`/`runtime`/`result` 核）↔ `TASK-MODEL-LOG` L50（本链任务级 1 行）。

| 派 | HANDOFF | DISPATCH-LOG | role／model／runtime 对 `USER_MODEL_OVERRIDE.md` | 逐字一致 |
|---|---|---|---|---|
| ① builder 首派 | FAIL（429 中断） | L46 FAIL | builder＝`opencode-go/deepseek-v4.1-flash`／本窗口 | ✔ |
| ② builder 续做 | PASS | L47 PASS | 同上 | ✔ |
| ③ code-reviewer 首轮 | PASS | L48 PASS | `opencode/muse-spark-1.3-contributor-free`／本窗口 | ✔ |
| ④ builder 返工 P2-1/P2-2 | PASS | L49 PASS | builder 行同表 | ✔ |
| ⑤ code-reviewer 复核二 | PASS | L50 PASS | reviewer 行同表 | ✔ |
| ⑥ qa 独立 QA | PASS | L51 PASS | `codex/gpt-5.6-luna`／**codex** | ✔ |
| ⑦ builder 返工 P2-3 | PASS | L52 PASS | builder 行同表 | ✔ |
| ⑧ code-reviewer 复核三 | PASS | L53 PASS | reviewer 行同表 | ✔ |
| ⑨ builder 返工 P2-三1＋P3-新1 | PASS | L54 PASS | builder 行同表 | ✔ |
| ⑩ code-reviewer 复核四 | PASS | L55 PASS | reviewer 行同表 | ✔ |
| ⑪ qa 复验 | PASS | L56 PASS | qa 行同表 | ✔ |

- 角色分布实测 `{builder:5, code-reviewer:4, qa:2}` ＝ 11，与 HANDOFF「builder×5／code-reviewer×4／qa×2」**逐字一致**；`grep -c 'P1-3'`：DISPATCH **11** 行（L46-56，无缺无余）、TASK **1** 行。
- **builder 首派那条 FAIL 该不该记、记法是否如实 → 裁定：该记，且记法如实。** 理由：① 账本体例是「逐派一行」，被平台 429 中断的派工同样是一次派工，删掉它就没有「半成品为何在工作树、前端自测为何一度 rc=1」的可审计线索；② 枚举只有 `PASS/FAIL`，环境中断如实落 `FAIL` 比落 `PASS` 诚实，且 `note` 已写明是**平台 429（环境/模型侧）而非任务挂**、并写明「已由续做轮吸收」，符合 AGENTS「FAIL 须说明是任务挂还是模型挂」的精神；③ 它与 HANDOFF `:36` 的「如实记 FAIL 不掩盖」一致，未掩盖。
- `rework` 口径：AGENTS 现行条文＝「被 supervisor 打回次数」，本链 supervisor 打回 **0** 次 ⇒ TASK 行 `rework=0` 正确，**无少报**（本链唯一 FAIL 出自 builder 首派 429，另 4 次 FAIL 出自更早各链的 code-reviewer/QA，按口径均不计入本链 rework）。

### ④ 审查意见闭环抽查（逐条到源码，不采信报告）

| 项 | 报告位置 | 我到源码核（工作树行号） | 在位 |
|---|---|---|---|
| **P2-1** 批量重试文案与事实 | `index.html:1186/1195/1359-1360` | `:1186`「需保持本页打开：离开或刷新后，剩下没排上的不会继续重试（已排上的会照常跑完）」；`:1195`「（需保持本页打开，离开则剩余任务不会再排队）」；`:1360` 共用锁定提示**已不含**「可离开」与「进度条/已用时」，只剩「已锁定／本次不改／跑完再改」（越界尾句已删，P3-新1 闭环） | ✔ |
| **P2-2** 原因透传＋本地门 | `index.html:1088-1092/1099-1107/1188-1223` | `retryRootHint():1090-1091` 单点人话；`retryBody():1099-1107` 本地门 `if(root&&!isAbsRoot(root))return null;`＋`if(root)p.data_root=root`；`noteBad:1188-1192` 留首因；批量 `:1211-1214` 本地拦＋`:1221` 回显 `x.o.error` | ✔ |
| **P2-3** 五桶唯一真源 | `server.py:1746-1800` 真源＋`_state_bucket`；`:5590` 判据 | `STATE_BUCKET:1767-1780`（单表）、`_state_bucket:1793-1795`（`.strip().upper()`，表外→`failed`）、`_recovery_bucket:1798-1800`（逐位映射派生，无自写 if 链）、`_recovery_bucket_counts:1803-1808`；`_reapply_result_bucket:5570-5592`，判据行为 `:5590` `if "state" in item:` | ✔ |
| 其余文案真话落位 | — | `:1425/:1428` 错词重跑「可离开本页面」（服务端任务，属实）、`:1270` 重新成稿「也可离开页面，后台会继续跑完」（复核二已用真 socket RST 实证）**均保留未被误删**；全文 `grep '可离开|稍后回来|保持本页打开'` 无第二处矛盾文案 | ✔ |

**我方独立探针（`/tmp/sv13_probe.py`，43 项，exit 0）——六类输入同源矩阵，全部命中报告口径**：

| 输入 | `_reapply_result_bucket` | `_state_bucket` | `_recovery_bucket` | `f"== _state_bucket"` |
|---|---|---|---|---|
| `{"ok":True,"state":""}` | **failed** | failed | still_failed | ✔ |
| `{"ok":True,"state":"   "}` | **failed** | failed | still_failed | ✔ |
| `{"ok":True,"state":None}` | **failed** | failed | still_failed | ✔ |
| `{"ok":True,"state":"WEIRD_UNKNOWN"}` | **failed** | failed | still_failed | ✔ |
| `{"ok":True,"state":"PUBLISHED"}`（已知成功态） | **success** | success | recovered | ✔ |
| `{"ok":True}`（**缺键**） | **success**（存量形状，不误伤） | —（恢复链条条必带 state，不适用） | — | ✔ |
| `{"ok":False}`（缺键） | failed | — | — | ✔ |

另核：表内 14 个 state 两链逐条同源（14/14）；`STATE_BUCKET = {` 与 `def _state_bucket(` 全仓**各仅 1 处**；`RECOVERY_BUCKETS` 与 `FIVE_BUCKETS` 逐位映射一致且值逐字未变（`recovered/still_failed/skipped/needs_human/interrupted` ↔ `success/failed/skipped/needs_human/interrupted`）；任何输入必落且只落一个桶（五桶完备 6/6）。
**口径自我更正（如实记）**：该探针**首跑 rc=1（6 项 FAIL）**——是我把两链**对外字段名**直接相等比对（`success` vs `recovered`），而 `server.py:1781-1782` 明文约定「两链对外字段名不同、只做名字映射，判据仍只有那一张表」。属**我的探针口径错，非代码缺陷**；改按 `_reapply_result_bucket(item) == _state_bucket(item["state"])` 比对后 43/43 PASS、rc=0。

### ⑤ 反向证伪抽查（「自测有牙」）：我**自己动手做 2 条**，2/2 rc=1

做法＝唯一锚点替换 → 跑自测 → **要求 rc=1** → 整文件还原 → **sha256 必须与给定基线一致**。判据**只用 rc 与 FAIL 行**。

| 抽检 | 改回什么旧形态 | 实测 | 还原校验 |
|---|---|---|---|
| **A**（本链最关键，P2-三1 原形态） | `server.py:5590` `if "state" in item:` → `if str(item.get("state") or "").strip():` | `contract` **rc=1**，`FAIL` 4 条，含 `10a4 {"ok":True,"state":""} → failed`、`10a4 显式空白/None 同样以键为准走表`（detail 实测被抬成 `success=2/failed=0`）、`10a4 判据单点` | ✔ `433dd62c…f14b` **逐字一致**；还原后复跑 rc=0（445） |
| **B**（P2-1 原形态） | `index.html:1186` 文案 → 「可离开本页面，稍后回来仍能看到结果。」 | `frontend` **rc=1**，`FAIL 9a 首条文案不承诺可离开`＋`9a 明说需保持本页打开`＋`9a 逐条进度文案同样不提可离开`（detail 打出被改回的整串） | ✔ `858080fc…d38c` **逐字一致**；numstat 回 `232/32` |

⇒ 这两条断言**不是自我实现的假信心**：A 咬住本链中心语义（空/坏 state 的 fail-closed 与两链同源）、B 咬住「文案与事实相反」那一类。其余断言我只抽这 2 条，**不为其背书**。

### ⑥ Phase Integrity 五查

1. **PLAN 期禁 business 派工**：按 `DISPATCH-LOG` 日期×角色统计，`2026-09-13`（PLAN 期）仅 `planner×4／product-reviewer×2／supervisor×1`，**无 builder/qa 业务派工** ✔。
2. **WAITING 禁自动开发**：HANDOFF `:10` `PLAN_GATE=APPROVED` 系用户 2026-09-14 明确「第二阶段，开发」后进 Phase2；无自动跨越 ✔。
3. **DEVELOP 必有基线**：HANDOFF `:11` `DEV_BASELINE=PRODUCT_PLAN_V1.3` 在位 ✔。
4. **C 类不得绕 Controlled Reopen**：本链 `CHANGE_REQUEST=B`（P2-7 扩 `/api/retry` 带 `data_root`，属局部功能变化，只更新局部 Requirement/DoD，留在 DEVELOP）；交付面无产品/架构级变更，无需 `PLAN_REOPEN_REQUIRED` ✔。
5. **TM 持续推进**：HANDOFF「二、下一步」有明确 Next Single Action（P1-4 默认下一项）＋backlog，恢复窗口可直接续跑，无停摆 ✔。

### ⑦ 红线抽查

- **无 commit／无 push**：`git rev-parse HEAD`＝`git rev-parse origin/main`＝`3af2da7`（P1-3 交付**全在工作树未提交**，与派单书一致）；`git reflog` 最近一条 commit 仍是 `3af2da7`（改 HANDOFF），本链零新提交 ✔。
- **未碰 secrets**：本链 4 个改动文件密钥型扫描，命中项仅为「retry-plan/retry-batch 的一次性确认 token（服务端随机摘要、非凭据）」与「只回字段名不回原值」的注释，**无 API Key／私钥／`.env`** ✔。
- **未改封存件／`docs/sop/`**：`git status --porcelain` 与 `docs/sop/`、V1.10/V2.0、`.env`、`env.err` **零交集** ✔。
- **测试卫生**：`part10` 首行三连 `assert_tmp(root_a/root_b/noroot)`（`tests/selftest_p1_2_contract.py:1443-1445`）在位；`10a4` 段**不调 handler**（故不涉 `data_root` 门）✔。**我独立复验复核四的勘误**：本链连跑 `contract` 2 次＋`frontend` 2 次，跑后系统 tmp `p12_*/p13_*` **新增 0 个**（现存 10 个 mtime 全 ≤ `08:02:48`，我的运行在 `08:42-08:44`）⇒ 「每跑必漏」前提不成立，`shutil.rmtree` 清理点实测在位（`:719-720`、`:1059-1060`），**同意 P3-新2 划掉**。
- **主题默认浅色**：`app/index.html:2` ＝ `<html lang="zh-CN" data-theme="light">`（本链未回退）；自动化**未点真机主题开关** ✔。
- 服务：8765 无监听，未起服务；真机 UI 结论仍为 `NOT_VERIFIED`（不冒充）。

### ⑧ 未修项是否如实申报：**如实，未被含糊掉**

- `QA-P13-P2-4-REAPPLY-MUTEX`：QA 报告 BUG 表标 **`OPEN，既有残留`**、复验节与「复验后 BUG 状态」表再次写明 **OPEN**；code-reviewer 复核四 Findings 末条写明 **仍开**；HANDOFF `:68` 已进 **待排期 backlog**（并写明修法须把内部调用改 `internal=True` 再上锁，直接加锁会自锁）。**独立核实成立**：`_handle_reapply_post` 内部调用点 `server.py:3536`（带 `progress_cb`）、HTTP 入口 `:6165`，函数体（`:6015` 起）与入口均**无运行中互斥**（`409/locked/running` 0 命中）⇒ 运行中确可另起一次并行重跑。
- code-reviewer 的 P3 清单**如实挂在报告里**：复核一 P3-1～P3-9、复核二 P3-新1／P3-新2、复核三 P3-三1／P3-三2、复核四 P3-四1～四4（含**勘误撤 P3-新2**）与 §九「九处各写一套」清单均原文在位；HANDOFF `:68` 已按 V1.3 处置表分流收录。
- 已知缺口如实标注：真实 whisper／61 篇量级／长视频 elapsed／多标签页真并发／真机 UI/HTTP（本链已跑）在各报告「未覆盖项」逐条标注，**无「推断通过」字样**。

### ⑨ 非阻断待办（不拦收口，交 TM／收尾 neat-freak）

1. **HANDOFF `:28` 数字为 08:29 快照口径残留，建议 TM 改一行**（不拦收口）：其实测应为 `app/index.html` **232/32**（写 231/32）、`tests/selftest_p1_2_frontend.py` **346/1**（写 347/1）、`DISPATCH-LOG` **＋11**（写 ＋6，且与本文件自身 `:27` 的「45→56」**自相矛盾**）、漏列 `TASK-MODEL-LOG ＋1`。核过 `:27` 的「45→56＝本链 11 派」才是最终正确口径；属快照笔误，**非失实、不打断口**（同 P0-3 先例口径）。
2. **DISPATCH-LOG 待补本链第 12 行**（supervisor 复检那一行，`used=主`、`runtime=本窗口`、`model=opencode-go/muse-spark-1.3-contributor`）——按体例由 TM 在收工时落盘；`TASK-MODEL-LOG` 本链任务级行已由 TM 判 PASS 落盘（L50），SUPERVISOR 校验留痕同批办。
3. **QA 报告行号为快照**：BUG 表引的 `server.py:3501-3502`（现 `:3536-3537`）、`:5968-5994`（现 `:6015` 起）已漂移，**实质独立核实成立**；按体例不改正文，可留 neat-freak 加注。
4. **首轮节数字残留**：本文件 `:13` 七查表仍为 `429 项断言`（首轮快照），与 `:106` 复验节的 `445` 并存；建议 neat 加注指向复验节（同 P1-2 先例，低报文字残留、不阻断）。
5. **backlog 清单（继承，非阻塞）**：`QA-P13-P2-4-REAPPLY-MUTEX`（P2）＋code-reviewer 的 P3（`.upper()` 轻微放宽、`10a4` 源码文本守卫脆性、注释溯源标记、混合形态两链优先级不同、`V25_POSTPASS` 待决归属、`_recovery_job_read` 兜底硬编码 `interrupted=1`、九处「按 state 归类各写一套」）＋前序链 P1-2 的 15×P3／P0-3 的 2×P2；**真实 whisper／61 篇／长视频／真机 UI 未跑**。

### ⑩ 结论

- **PASS（收口）／无 blocking**。本链 supervisor 累计打回 **0/2**（本轮新增 **0**）。三处对账**不匹配 0 行**；两账本校验 **exit 0**（并已用坏行负控证明校验器有牙）；三套自测 rc 全 0（445／87／58）；P2-1／P2-2／P2-3 三条审查意见**逐条到源码在位**，我方独立探针 43/43 复现六类输入同源口径；自做反向证伪 2/2 rc=1 且还原 sha256 与基线逐字一致；Phase Integrity 五查过；红线抽查过（无 commit/push、无 secrets、未改封存件、测试只写外置 tmp＋合成数据、主题浅色在位、8765 无监听）。
- 遗留：`QA-P13-P2-4-REAPPLY-MUTEX` 保持 **OPEN** 进 backlog；⑨ 五条非阻断待办交 TM／neat-freak。**放行收口。**

