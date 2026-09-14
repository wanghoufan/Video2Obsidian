# BUGS

## 测试结论

**FAIL（P0）。** 静态接线、批量入口收敛、范围/whisper 文案、FR-13 fail-closed、三态监听、复制面板退出和窄屏 CSS 断言均通过；但 tmp 合成 handler 复验发现 `PUBLISH_BLOCKED` 被错误判为 mismatch，导致 `PUBLISH_ONLY` 计划永远无 eligible 项，前端 `publishOnlyRetry` 实际无法到达 `retry-batch`。P0-3 不可收口。

- 新增 BUG：1（P0）。
- P1：0。
- P2：0（旧观察项本轮未重复计入）。
- 未启动服务；8765 实测未监听。
- 未访问、未写入真实数据目录或 Obsidian 库；未点击主题开关。

## 环境与命令

- 基线：`DEV_BASELINE=PRODUCT_PLAN_V1.3`，Phase2 / DEVELOP。
- 工作树范围：复验用户指定的 `app/index.html`、`app/server.py`；未修改业务代码。
- 静态校验：

  ```text
  PYTHONPYCACHEPREFIX=/private/tmp/v2o-qa-pyc-3 python3 -m py_compile app/server.py  # PASS
  node --check <(extract app/index.html <script>)                           # PASS
  node static assertions                                                   # PASS
  git diff --check                                                         # PASS
  ```

- tmp handler 夹具：`/private/tmp/v2o-qa-p03-ztyayu01`（合成 SQLite、合成 `PUBLISH_BLOCKED` run；首个可执行测试断言确认 `data_root` 位于 `/private/tmp`，且不等于默认真实目录）。
- Node 状态断言：从真实 `app/index.html` 抽取 `statusCN`，使用合成状态执行；未操作浏览器。
- 端口：`lsof -nP -iTCP:8765 -sTCP:LISTEN` → `NOT_LISTENING`。

## 用例统计

| 范围 | 通过 | 失败 | 未执行 | 证据强度 |
|---|---:|---:|---:|---|
| publish-only 三处接线与 plan→batch 静态契约 | 1 | 0 | 0 | 真实 HTML 源码静态断言 |
| 批量入口唯一性 / FR-9 错词重跑豁免 | 1 | 0 | 0 | 真实 HTML 全文计数 |
| 范围＋whisper 成本文案 | 1 | 0 | 0 | 真实 HTML 源码断言 |
| FR-13 mismatch 降级＋state.db 哈希不变 | 1 | 0 | 0 | tmp SQLite + 真实 handler |
| PUBLISH_ONLY 实际计划可达性 | 0 | 1 | 0 | tmp SQLite + 真实 handler |
| 三态监听文案 | 1 | 0 | 0 | Node 执行真实 `statusCN` |
| 复制短句 / 面板四退出 / 窄屏回归 | 1 | 0 | 0 | 真实 HTML/CSS 静态断言 |
| 真实 whisper、真机 UI、HTTP 服务 | 0 | 0 | 3 | 本轮按约束未执行 |

## 用例逐项证据

### 1. P0-3 publish-only 接线：静态 PASS，运行链路 FAIL

- `publishOnlyRetry(run_id)` 唯一函数存在。
- 接线覆盖：首屏 `#btnRecPublish`、列表行 `data-retry-publish`、详情 `PUBLISH_BLOCKED` failbox；绑定均调用 `publishOnlyRetry`，非 publish 路径仍调用 `retryRun`。
- 函数静态包含：
  1. `POST /api/failures/retry-plan`；
  2. 单条 `run_ids:[run_id]`；
  3. 检查 `hit` 是否存在；
  4. 检查 `hit.strategy === "PUBLISH_ONLY"`；
  5. 仅策略通过后才 `POST /api/failures/retry-batch`，携带 `confirm:true`、`plan_token`、单条 `run_ids`。
- 非 PUBLISH_ONLY / 不在 eligible / plan 失败均在 batch 前 fail-closed，静态 PASS。

但 tmp 合成真实 handler 结果为：

```text
诊断：action=PUBLISH_BLOCKED, persisted_state=PUBLISH_BLOCKED,
      display_state=FAIL, display_persisted_mismatch=True,
      recovery_eligibility=NEEDS_HUMAN, will_call_whisper=False
计划：eligible=0, publish_only=0, excluded=1
```

根因：`_diagnosis_item()` 用展示态 `"FAIL"` 与持久态 `"PUBLISH_BLOCKED"` 做字面比较；正常的入库受阻记录因此被当成 mismatch，刚好被 FR-13 降级门挡住。结果是 publish-only UI 接线虽正确，但正常 `PUBLISH_BLOCKED` 数据永远不能取得 `PUBLISH_ONLY` plan，无法执行目标 `retry-batch`。

### 2. 全文批量入口唯一性：PASS

- `btnRetryAllFailed`：全文 0 命中。
- `btnReapplyAll`：全文 0 命中。
- 旧词库区「全部应用新词库重跑」：全文 0 命中。
- 「错词重跑」保留 2 处（按钮与说明），按 FR-9 豁免项如实记注；它是候选词变更后的专用流程，不计入通用批量恢复入口。
- `#recoverBox` 保留统一入口；详情只保留当前任务上下文快捷操作。

### 3. 范围与 whisper 成本：PASS

静态断言确认三类动作均有范围与成本表达：

- 全部失败重新转写：范围＝全部失败任务；whisper 会跑。
- 从已有文字重新成稿：范围＝当前所选任务或全部已完成任务；whisper 0 次。
- 仅重新入库：范围＝当前所选任务；whisper 0 次；不覆盖。
- 单条行级/详情动作分别标注本任务或当前任务及成本。

### 4. FR-13、哈希与监听：PASS（另有 P0-3 可达性回归）

- tmp 合成 mismatch 记录被降级为 `NEEDS_HUMAN / MANUAL_REVIEW / will_call_whisper=false`，未执行任何业务写入。
- 诊断前后 `data/state.db` SHA-256 相同：

  ```text
  ef9e5a14a7334ee27fb501a25fb665ce05b836ecd2c8f6149bd9556a89487d9a
  ```

- Node 三态断言通过：未监听与停止/非 ACTIVE 使用持久状态文案；监听中只有 run 自身为 `ACTIVE/RUNNING` 且有 worker stage 才显示阶段文案。样本结果：`入库受阻 / 入库受阻 / 听写中`。

### 5. 复制短句、面板四退出、窄屏：静态 PASS

- 复制失败原因只向 `#msg`/toast 输出短句，长文本进入可主动打开的面板；`say()` 截断 120 字并 3 秒清理。
- 面板退出路径和恢复检查均在源码：关闭按钮、Esc、遮罩点击、关闭后焦点返回。
- 面板正文 `max-height:min(70vh,560px); overflow:auto`，并存在 `@media (max-width:900px){main{grid-template-columns:1fr}}`；本轮为源码/CSS 回归，未做真机像素验证。

## Bug 表

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注 |
|---|---|---:|---|---|---|---|
| QA-P03-RR2-001 | P0 | 是 | tmp 合成 `processing_runs.status=PUBLISH_BLOCKED`，调用真实 `_handle_failure_diagnosis` 与 `_handle_retry_plan_post` | OPEN / FAIL | P0-3 STATE ENTRY RETEST2 | `_diagnosis_item` 将展示 `FAIL` 与持久 `PUBLISH_BLOCKED` 判为 mismatch，降级 `NEEDS_HUMAN`；plan `publish_only=0`、eligible=0，publish-only 无法进入 retry-batch。需修正状态语义映射，并补测 mismatch 真不一致仍 fail-closed、DB 哈希不变。 |

## 证据强度与限制

- **真跑**：Python 真实 `app/server.py` handler、真实 SQLite schema、真实 HTML 抽取后的 Node `statusCN`；所有写入仅发生在 `/private/tmp` 合成目录。
- **静态通过**：三处 publish-only 接线、旧批量入口零命中、FR-9 豁免、范围/whisper 文案、面板退出、窄屏 CSS。
- **未跑**：真实 whisper、TCP 服务、真机读屏/截图/点击/输入/滚动、真实用户目录、Obsidian 库；因此没有填写真机 QA 能力预检 PASS，也不宣称服务端到端 PASS。
- 主题开关未点击。

## Fix Attempt Fingerprint

- Task ID: `P0-3-STATE-ENTRY-RETEST2-2026-09-14`
- Root Cause Hypothesis: FR-13 直接比较展示态与持久态字符串，未将 `PUBLISH_BLOCKED` 与展示层失败/受阻语义归一化。
- Approach: 真实 HTML 静态断言；tmp 合成 SQLite；真实 diagnosis/plan handler；Node 状态函数断言；只读端口检查。
- Files Changed: 仅新增本报告；未修改业务代码。
- Verification: Python compile PASS；Node static/status assertions PASS；tmp mismatch/hash PASS；PUBLISH_ONLY plan 可达性 FAIL。
- Failure Reason: 正常 `PUBLISH_BLOCKED` 记录被 FR-13 mismatch 门错误降级，P0 publish-only 链路不可执行。
- Difference From Previous Attempt: 本轮补做了真实 tmp `retry-plan` 计划可达性检查，发现静态接线 PASS 与后端语义回归之间的差异。

> Attempt ID / Dispatch ID / Model-Backend 系字段 2.0 已废弃，不填。

## 末行心跳

over/under：目标＝完成 P0-3 retest2；剩 P0＝1（PUBLISH_ONLY 计划被错误降级）；下一步＝修正状态语义映射后重跑 tmp plan→batch、哈希与全套静态断言。

> neat-freak 加注（2026-09-14，只记不改）：本报告 FAIL 结论为当时快照，不改。本报告 Bug `QA-P03-RR2-001` 后续在语义修复链被 builder 修（`_FAIL_SEMANTICS` 归一化）→ reviewer 复核 PASS（`docs/review/P0-3-SEMANTICS-FIX-REVIEW.md`）→ qa 重验 CLOSED/PASS（`docs/qa/P0-3-SEMANTICS-FIX-QA-2026-09-14.md`）。P0-3 仍差 supervisor 复检，未收口。
