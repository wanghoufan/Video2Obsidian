# BUGS

## 测试结论

**PASS。** QA-P03-RR2-001 已通过：`PUBLISH_BLOCKED` 正常记录经过状态语义归一化后不再被误判为 mismatch，`PUBLISH_ONLY` 计划可达；真实 mismatch 仍 fail-closed。诊断与计划均未改变 `state.db`。

- 新增 BUG：0。
- P1：0。
- P2：0；reviewer 提到的只读 provenance 加性字段不影响本轮验收。
- 未启动服务；8765 实测 `NOT_LISTENING`。
- 未访问或写入真实数据目录、Obsidian 库；未点击主题开关。

## 环境与命令

- 基线：`DEV_BASELINE=PRODUCT_PLAN_V1.3`，Phase2 / DEVELOP。
- 代码范围：`app/server.py`、`app/index.html` 只读复验，未修改业务代码。
- 编译：`PYTHONPYCACHEPREFIX=/private/tmp/v2o-qa-p03-pyc python3 -m py_compile app/server.py` → PASS。
- 前端语法：从真实 `app/index.html` 抽取 script 后 `node --check` → PASS。
- 静态回归：批量入口、范围/whisper 文案、三态、面板退出、窄屏 CSS → 全部 PASS。
- 临时夹具：`/private/tmp/v2o-qa-p03-final-arrz9cbu`，仅合成 SQLite、合成 source/run；首个可执行断言确认 `data_root` 位于 `/private/tmp`。测试结束后已清理。

## 用例统计

| 范围 | 通过 | 失败 | 未执行 | 证据强度 |
|---|---:|---:|---:|---|
| 正常 `PUBLISH_BLOCKED` 诊断语义归一化 | 1 | 0 | 0 | 真实 `_handle_failure_diagnosis` + tmp SQLite |
| `retry-plan` 到 `PUBLISH_ONLY` 可达 | 1 | 0 | 0 | 真实 `_handle_retry_plan_post` + tmp SQLite |
| 真 mismatch 降级 | 1 | 0 | 0 | 持久态 `QUEUED` 与展示失败语义不一致，真实 handler |
| `state.db` 哈希诊断前后不变 | 1 | 0 | 0 | SHA-256 前后相同 |
| 批量入口零命中、范围/whisper 文案 | 1 | 0 | 0 | 真实 HTML 全文静态断言 |
| 三态监听文案 | 1 | 0 | 0 | Node 执行真实 `statusCN` |
| 面板四退出、窄屏 CSS | 1 | 0 | 0 | 真实 HTML/CSS 静态断言 |
| 真实 whisper、HTTP 服务、真机 UI | 0 | 0 | 3 | 按本轮约束未执行 |

## 用例逐项证据

### 1. 正常 `PUBLISH_BLOCKED`：PASS

真实 handler 返回：

```text
persisted_state=PUBLISH_BLOCKED
display_state=FAIL
display_persisted_mismatch=False
recovery_eligibility=AUTO_PUBLISH
retry_policy=PUBLISH_ONLY
will_call_whisper=False
```

这证明 `FAIL` 展示语义与 `PUBLISH_BLOCKED` 持久语义已归一化。

### 2. `PUBLISH_ONLY` 计划可达：PASS

对同一合成 run 调用真实 `_handle_retry_plan_post`：

```text
summary.eligible=1
summary.publish_only=1
summary.will_call_whisper=0
eligible[0].strategy=PUBLISH_ONLY
```

因此前端已有 `publishOnlyRetry` 的 plan→batch 前置链具备后端可达性；本轮未执行真实 batch 发布。

### 3. 真 mismatch：PASS

合成持久态为 `QUEUED`、展示层按失败语义处理，真实 handler 返回：

```text
display_persisted_mismatch=True
recovery_eligibility=NEEDS_HUMAN
retry_policy=MANUAL_REVIEW
will_call_whisper=False
```

对应 run 在 retry plan 中 `eligible=0 / publish_only=0 / excluded=1`，仍保持 fail-closed。

### 4. `state.db` 零写：PASS

诊断和两次 retry-plan 前后 SHA-256 均为：

```text
3a8808259cf32ce51d0371146796dcd65b59a0cd900126b5dee2b237d31913b9
```

### 5. 静态回归：PASS

- 通用批量入口 `btnRetryAllFailed`、`btnReapplyAll`、旧「全部应用新词库重跑」文案：全文 0 命中；FR-9 专用「错词重跑」保留 2 处。
- 范围与成本文案齐全：全部失败、全部已完成、当前所选任务；`whisper 会跑` 与 `whisper 0次` 均存在。
- Node 真实 `statusCN` 三态结果：`入库受阻 / 入库受阻 / 听写中`；监听开关不改变非 ACTIVE 任务持久态文案。
- 面板退出路径：关闭按钮、Esc、遮罩点击、焦点返回均存在。
- 窄屏：`@media (max-width:900px)` 下主布局单列规则存在。
- `git diff --check` → PASS。

## Bug 表

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注 |
|---|---|---:|---|---|---|---|
| QA-P03-RR2-001 | P0 | 是 | tmp 合成 `PUBLISH_BLOCKED` + 真实 diagnosis/plan handler | CLOSED / PASS | P0-3 SEMANTICS FIX QA | 正常受阻记录不再 mismatch；真 mismatch 保持 `NEEDS_HUMAN/MANUAL_REVIEW/whisper=False`；plan `PUBLISH_ONLY` 可达。 |

## 证据强度与限制

- **真跑**：真实 `app/server.py` diagnosis/plan handler、真实 SQLite DDL、真实 HTML 静态内容、真实 `statusCN` Node 执行；所有写入仅发生在 `/private/tmp` 合成夹具。
- **未跑**：真实 whisper、`retry-batch` 实际发布、TCP 服务、真机读屏/截图/点击/输入/滚动、真实用户目录、Obsidian 库。
- 因未做真机能力预检，不宣称真机 QA 通过；主题开关未点击。

## Fix Attempt Fingerprint

- Task ID: `QA-P03-RR2-001`
- Root Cause Hypothesis: FR-13 比较展示态与持久态时缺少失败语义归一化。
- Approach: 外置 tmp 合成 SQLite；真实 diagnosis→retry-plan；正例、真 mismatch、哈希不变；HTML/Node 静态回归。
- Files Changed: 仅新增本 QA 报告；未修改业务代码。
- Verification: `py_compile`、Node syntax、handler、SHA-256、静态断言全部 PASS。
- Failure Reason: 无。
- Difference From Previous Attempt: 新增 `_FAIL_SEMANTICS` 归一化后，正常 `PUBLISH_BLOCKED` 从错误 mismatch 恢复为 `AUTO_PUBLISH/PUBLISH_ONLY`。

> Attempt ID / Dispatch ID / Model-Backend 系字段 2.0 已废弃，不填。

## 末行心跳

over/under：over＝P0-3 语义修复与静态回归均通过；under＝真实 whisper、HTTP 服务、真机 UI 未执行且不影响本次代码级 QA 结论。

## supervisor 复检（2026-09-14，`opencode-go/muse-spark-1.3-contributor`／本窗口）

- **结论：PASS（收口）**。本链累计打回 **1/2**（本轮新增 0）。只读复核：未改业务代码/文档正文、未 commit、未跑 handler、未起服务；工作树 `M app/index.html 181/31`＋`M app/server.py 28/3`＋`M HANDOFF`＋两账本，新报告 7 份，无夹带未申报改动。
- **① 计数口径裁定**：`28/3` 与报告 `+19/−3` 的 9 行差**可解释为语义修复自身新增行**——返工前两处独立记录（`P0-3-STATE-ENTRY-REWORK-REVIEW.md:5`、`P0-3-STATE-ENTRY-REWORK2-REVIEW.md:5`）均为 server `19/3`，本轮 `_FAIL_SEMANTICS`＋归一化分支＋8 个只读 provenance 字段净增 9 行即 19+9=28，逐行归因无未申报内容 → **属修复前快照口径，非失实，不打断口**；仅需加注更正（neat 已于 `P0-3-SEMANTICS-FIX-REVIEW.md` 尾加注）。
- **② 两道账本校验**：TASK-MODEL-LOG 48 行 exit **0**；DISPATCH-LOG 34 行 exit **0**（均静默，无坏行）。
- **③ 三处对账抽查（实派==根表，used=主）**：DISPATCH L22 builder `opencode-go/deepseek-v4.1-flash`／本窗口、L29 code-reviewer `opencode/muse-spark-1.3-contributor-free`／本窗口、L32 qa `codex/gpt-5.6-luna`／codex，与 `USER_MODEL_OVERRIDE.md` 逐字一致；TASK L46-48 同栏对齐；HANDOFF「执行链」三处相符。
- **④ Phase Integrity 五查**：DEVELOP＋`DEV_BASELINE=PRODUCT_PLAN_V1.3` 在位 ✓；`CHANGE_REQUEST=NONE`、本轮返工未绕 Controlled Reopen ✓；无 PLAN 期 builder/qa 派工、无 Human Gate 自动跨越 ✓。
- **⑤ 红线抽查**：QA 首个可执行断言即 `data_root` 在 `/private/tmp` ✓；未写真实目录/Obsidian、未点主题开关，`index.html:2` 仍 `data-theme="light"` ✓；reviewer 未起服务/未跑 handler ✓。
- **⑥ 代码实体**：`_FAIL_SEMANTICS:1342`、`display_persisted_mismatch` 全文唯一写点 `:1373`、`publishOnlyRetry:1098` 及三处接线（`:658`/`:752`/`:1821`）均在位；三批量旧入口全文 0 命中；`QA-P03-RR2-001` CLOSED 三断言（正常 `AUTO_PUBLISH/PUBLISH_ONLY/eligible=1/whisper=0`、真 mismatch 仍 `NEEDS_HUMAN/MANUAL_REVIEW`、`state.db` 哈希不变）已闭环。
- **无 blocking 项**。遗留 P2（provenance 加性字段、术语残留 `obhint:741`）记 backlog，不拦收口；真实 whisper/batch 发布/真机 UI/HTTP 服务未跑，作已知缺口不拦。
- 本次复检零外部模型调用。
