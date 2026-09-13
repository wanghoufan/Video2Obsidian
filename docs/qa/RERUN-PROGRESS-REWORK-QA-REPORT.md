# BUGS

## 测试结论

**PASS。** 本轮独立复验真实工作树中的 M1-M4 返工，未发现新增 Bug。

- 上轮 QA-RR-01：**CLOSED**。`Thread(...)` 构造异常与 `.start()` 异常均不再遗留 `running` 单例。
- 上轮 QA-RR-02：**CLOSED**。`progress_cb=None` 不再额外调用 `_run_source_path_map`。
- 上轮 QA-RR-03：**CLOSED**。单次轮询失败会继续重试，达到连续失败阈值或累计超时才停表。
- P1-1 主题默认浅色：**CLOSED**。旧版遗留 `v2o-theme=dark` 且无迁移标记时，多轮加载首轮强制浅色并写迁移标记；迁移后手动 dark 可保持。
- **新增 BUG：0。**
- M1-M4 与要求的回归项全部通过；本轮 DoD：**全过**。

## 环境与命令

- 项目根：`/Users/zzymima0000/Developer/coding/1.Active/ing丨 0910 本地视频转文字工具`
- Python：`/private/var/folders/mp/mnxk3h8x4wq5ztr7__vlplp40000gn/T/opencode/stage0bench/venv/bin/python3`
- 测试脚本（均在系统临时目录）：`/tmp/qa_rr_rework.py`、`/tmp/qa_rr_rework_node.js`
- 命令：

  ```text
  /private/var/folders/mp/mnxk3h8x4wq5ztr7__vlplp40000gn/T/opencode/stage0bench/venv/bin/python3 /tmp/qa_rr_rework.py
  node /tmp/qa_rr_rework_node.js
  ```

- 未请求、未重启、未 kill 8765（PID 72407）；未改业务代码；未 commit/push；未访问真实库、vault 或 secrets。
- Python handler 测试夹具首个可执行数据断言确认 `data_root` 位于系统临时目录且不等于 `DEFAULT_DATA_ROOT`。Node 测试抽取 `app/index.html` 真实源码执行，未点击真实主题开关，也未把真实主题改回深色。

## 用例统计

| 范围 | 通过 | 失败 | 未执行 | 证据强度 |
|---|---:|---:|---:|---|
| QA-RR-01 / M3 | 8 | 0 | 0 | Python handler 级真实源码 + 两处异常注入 |
| QA-RR-02 | 2 | 0 | 0 | Python 调用计数断言 |
| P1-1 / M1 | 4 组 | 0 | 0 | 真实 HTML 源码 + Node 多轮共用 store 桩 |
| M2 / M4 | 2 组 | 0 | 0 | 真实 HTML 源码 + Node 异步 fetch/timer 桩 |
| 回归 | 5 | 0 | 0 | apply 链、旧 all 入口内部语义、并发单例 |

## 用例逐项证据

### QA-RR-01 / M3：起线程失败不悬挂

分别将异常注入 `threading.Thread(...)` 构造行和 `.start()` 行。两条路径均实测：

1. handler 返回 `500`；
2. 单例为 `state=failed`，同时有 `error`、`finished_at`；
3. `_handle_vocab_apply_status({})` 返回该 failed 任务；
4. 下一次提交立即返回 `202`，不再永久 `409`。

结论：**PASS / QA-RR-01 CLOSED**。这是异常注入模拟，不是自然线程耗尽。

### QA-RR-02：`progress_cb=None` 不多扫 state.db

使用两个可重跑状态的临时任务并替换 `_run_source_path_map` 为计数桩：

- `progress_cb=None`：调用次数 `0`；
- `progress_cb=callback`：调用次数 `1`。

结论：**PASS / QA-RR-02 CLOSED**。

### P1-1 / M1：主题迁移与脏值

从 `app/index.html` 抽取真实 `el`、`applyTheme`、`initTheme` 源码，在 Node 桩中执行：

- 初始 store 为 `v2o-theme=dark`、无迁移标记：首轮为 `data-theme=light`，写入 `v2o-theme-migrated=1`，最终主题为 light；
- 后续共用同一 store，手动存入 dark 再加载：保持 dark；
- 空值、大小写/空格污染、`true`、中文等非法值：均回 light 并自愈写回 light；
- `getItem`、`setItem`、`removeItem` 抛异常：仍为 light，不抛出测试错误。

结论：**PASS / P1-1 CLOSED**。全程未操作真实浏览器主题按钮。

### M2：首轮 status 失败后可续看

Node 桩先让第一次 status fetch reject：timer 仍存在（1 个），按钮未被永久锁死，文案为“正在重试”。下一次 status 返回 `running 3/10` 后，页面恢复显示 `3/10` 进度。达到阈值后 timer 才清理并解禁按钮。

结论：**PASS**。

### M4：停表文案对应原因

- 连续失败第 8 次：显示“进度读取连续失败8次”；
- 已超过 10 分钟且本次失败：显示“进度刷新累计超过10分钟仍未完成”；
- 两条分支未串文案。

结论：**PASS**。

### 回归

- `/api/reapply` 的 `all=true` 旧同步入口：通过 `_reapply_all` 临时任务夹具，返回正常结果结构；`progress_cb=None` 不引入额外映射查询；
- 两线程同时提交 apply：结果恰好为一个 `202`、一个 `409`；
- apply 链校验：短词、撞基表、重复、越界、已 imported 均拒收；有效候选只导入一次；`rerun_old=false` 不触发重跑；
- 未执行真实 whisper、真实用户库/Obsidian vault、61 篇量级真实端到端重跑。

结论：**PASS**。回归夹具均为临时目录合成数据。

## Bug 表

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注 |
|---|---|---|---|---|---|---|
| QA-RR-01 | P2 | 否 | 原两处异常注入路径均可复现验证修复 | CLOSED | RERUN-PROGRESS-REWORK | 500、failed 终态、status 可见、立即 202 |
| QA-RR-02 | P2 | 否 | `progress_cb=None` 调用计数为 0 | CLOSED | RERUN-PROGRESS-REWORK | 有回调时映射恰调用 1 次 |
| QA-RR-03 | P2 | 否 | 单次 status reject 后 timer 保留并重试 | CLOSED | RERUN-PROGRESS-REWORK | 连续失败/超时才停表 |
| P1-1 | P1 | 否 | 旧版 dark 残留、无迁移标记多轮加载可复现验证修复 | CLOSED | RERUN-PROGRESS-REWORK | light 首帧、迁移标记、手动 dark 记忆均通过 |

## 证据强度与限制

- **真跑**：Python 3.12.13 执行真实 `app/server.py` 函数；Node 执行从真实 `app/index.html` 抽取的源码；共用 store、异常注入、fetch/timer 行为均由断言验证。
- **未跑**：真实 whisper 转写、真实用户数据、真实 Obsidian vault、61 篇量级端到端耗时、真实自然线程耗尽；这些不能推断为通过。
- 本轮未启动独立 HTTP 端口服务；QA-RR-01 的“请求 500”以真实 handler 返回 HTTP 状态码等价验证，未做 TCP 层注入复现。

## Fix Attempt Fingerprint

- Task ID: rerun-progress-rework-qa-2026-09-13
- Root Cause Hypothesis: 复验返工后的线程启动保护、重跑映射查询条件、前端轮询失败容错与主题一次性迁移。
- Approach: 临时目录隔离；Python handler/并发/计数夹具；Node 抽取真实 HTML 源码并执行多轮 store、fetch、timer 桩。
- Files Changed: 仅新增本报告；未改业务代码。
- Verification: Python 18 项断言通过；Node 主题、M2、M4 全部通过；无新增 BUG。
- Failure Reason: 无。
- Difference From Previous Attempt: 独立重新覆盖返工四条，新增旧版 dark 残留多轮迁移断言，以及构造行和 start 行分别注入。

> Attempt ID / Dispatch ID / Model-Backend 系字段 2.0 已废弃，不填。

## 复检（supervisor｜deepseek-v4.1-flash）

**判定：PASS。**

1. **输出齐**：reviewer 报告 `docs/review/RERUN-PROGRESS-CODE-REVIEW.md`（含「返工复核」「返工复核二」两节）、qa 报告 `docs/qa/RERUN-PROGRESS-QA-REPORT.md`（上轮）+ `docs/qa/RERUN-PROGRESS-REWORK-QA-REPORT.md`（本轮）均已落盘，账本本 Task 一行在位（L39）。
2. **意见闭环**：返工复核一的 P1-1、P2-1 与返工复核二的 P3-1、P3-2 全部 CLOSED；QA 复验明确将上轮 QA-RR-01/02/03 与 P1-1 判 CLOSED 且新增 BUG=0；四条均由 code-reviewer 与 QA 分别独立验过（前者 61/28 项、后者 Python/Node 两套），无「声称已修但无人独立验」的项。
3. **账本 schema 第二道校验**：整块照粘执行，**exit 码 = 0**（无 L行号报错）。
4. **返工数**：L39 记 `"rework": 2`，与本 Task 上下文一致——code-reviewer 两轮返工复核（一判需返工、二判 PASS），supervisor 0 次打回、senior 未启用，无少报/多报。

- 独立抽查（不改业务代码，只读真源）：M1 迁移 `app/index.html:331-334`、静态首帧 `<html data-theme="light">`:2、`:root[data-theme="light"]`:17；M2 `app/index.html:1296`（202 先建表）；M3 `app/server.py:2301-2307`（try 前移包住构造）、`2308-2315`（failed 终态 + job_id 守卫）；M4 `app/index.html:1244-1249`（连续失败 vs 累计超时文案分流）；R3 `app/server.py:4307-4313`（`fn_map` 仅在 `progress_cb is not None` 时求值）。以上与两报告声称一致。
- 证据强度（如实）：本轮未重跑 reviewer 的 61/28 项与 QA 的 Python/Node 套件，只做真源码行级抽查 + schema 脚本执行；「返工复核二」与「QA 复验」两份独立证据已在原报告内。
- 观察（非打回，供 TM）：① 账本 rework 口径与 `AGENTS.md`「rework=被 supervisor 打回次数」字面不同（本条按 TM 当次指定口径核对，数字自洽）；② `docs/handoff/HANDOFF.md:14` 仍写「重跑进度条…未开工」，与已完工现状不符，属 stale，需 TM/neat 收口；③ 未验项与两报告一致：线上 8765 进程仍为旧代码（后端改动需重启才生效，本轮未重启/未请求线上）。
