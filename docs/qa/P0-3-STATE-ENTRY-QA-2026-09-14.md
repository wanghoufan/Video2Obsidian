# P0-3 QA 复验｜2026-09-14

- 结论：**PASS（P0）**
- 范围：D-16 / D-19 / D-23；未写业务代码，未启动或触碰 8765，未操作真实目录/Vault，未切换主题。

## 证据

### 1. tmp 合成四层 mismatch

在 `/private/tmp/p03-qa-z41wwev1` 创建临时 SQLite 夹具，4 个 run 均构造为展示状态 `FAIL`、持久状态 `FAILED_RETRYABLE` 的 mismatch。

- 4/4 `display_persisted_mismatch=true`
- 4/4 降级为 `recovery_eligibility=NEEDS_HUMAN`
- 4/4 `retry_policy=MANUAL_REVIEW`
- 4/4 `will_call_whisper=false`
- 诊断前后 `state.db` SHA-256 均为 `63900abac89acf4f77d7f9604292e948650f2c519b8398c6f75ff7438b618caf`
- 结论：fail-closed 且 DB 字节不变，PASS。

### 2. 静态 DOM / JS

- 16 条长文复制：`#msg` 仅走短句，正文进入可主动打开的长文面板；`say()` 截断 120 字，PASS。
- 长文面板：关闭按钮、Esc、遮罩关闭、关闭后焦点返回触发控件，PASS。
- 窄屏高度：`max-height:min(70vh,560px)` 且正文内部滚动，PASS。
- 统一恢复入口：首屏 `#recoverBox` 含三种后果/Whisper 成本的入口，核心动作两次操作内可达，PASS。
- 监听未监听 / 监听中 / 停止收尾三态：run 自身持久状态、展示状态和颜色不随监听开关改写；仅 ACTIVE 且有 worker 阶段时显示阶段文案，PASS。

## BUG

- P1：旧三入口仍残留，未作“已删除”的断言：
  1. 列表头 `重试全部失败`；
  2. 词库区 `全部应用新词库重跑`；
  3. 详情高级 `应用新词库重跑`。
- P2：D-23 要求短提示“3 秒消失或可点击关闭”；当前 `#msg` 仅 3 秒自动消失，无点击关闭。

## 复验命令

- tmp 合成：`PYTHONPATH=.:src python3` 内联夹具调用 `app.server._handle_failure_diagnosis`
- 静态断言：复制短句/截断/面板退出/窄屏/统一入口/三态监听

---

## supervisor 复检（2026-09-14，`opencode-go/muse-spark-1.3-contributor`／本窗口）

- **结论：打回（FAIL）**，本链累计 **1/2**（rework=1）。范围：只读复核 `M app/index.html`＋`M app/server.py`（基于 b94845e，+112/−11）；未写业务代码、未跑 handler、**未起服务**（8765 实测无监听：`lsof -nP -iTCP:8765 -sTCP:LISTEN` 计数 0）；未碰真实目录/Obsidian 库/主题开关。

### 打回项（必须返工）

- **P1-1（阻断）FR-14 收敛未完成 → P0-3 DoD 明文验收句不达成**。旧三入口实测仍在：
  - `app/index.html:605` `#btnRetryAllFailed`「重试全部失败（N个）」（任务表头；L609 绑 `retryAllFailed` —— 与新首屏 `#recoverBox`「重新转写」绑**同一函数**，属纯重复入口）。
  - `app/index.html:270` `#btnReapplyAll`「全部应用新词库重跑」（词库区；L1446 绑 `reapplyAll`）—— 新首屏箱内**无等价能力**，收敛动作实为「新增第 4 个入口、旧 3 个原样保留」。
  - `app/index.html:742` 详情高级 `data-reapply`「应用新词库重跑（转写0次）」（L752 绑 `reapplyOne`）。
- **裁定理由**：① 该句是 P0-3 自身 DoD 的明文验收句（`docs/pm/PRODUCT_PLAN.md:116` 处置表 P0-3 行「全文不再出现三个互不关联的批量重跑入口」＋FR-14 `:67` 点名这三条要收敛），不是衍生要求；② 这三条正是用户「追加反馈二」抱怨的"同族动作散落三处"，未删＝用户原始投诉未闭环；③ code-reviewer 与 qa 留了**同一条 P1**，属"审查意见没闭环"（角色卡：P0没完打回、审查意见没闭环打回）。挂账等于承认 DoD 有未达标项仍收口，不可。
- **返工要求（全部落在 V1.3 基线内，属 Change A/B 级，不召 Planner、不走 Change C）**：
  1. 删表头 `重试全部失败` 与词库区 `全部应用新词库重跑` 两个入口；
  2. 词库区那条删除后不得丢能力：`#recoverBox`「从已有文字重新成稿」须就地给出**范围**（当前所选／全部已完成）并沿用既有 confirm 语义（转写0次、库内改过跳过、不覆盖）—— D-19 本就要求「显示范围、资格和 Whisper 调用」，属 FR-14「收敛」本身，**不是新增范围**；
  3. 详情高级单条 `应用新词库重跑`：按 FR-14 第二句「详情内仅保留当前任务的上下文快捷操作」**允许保留**，但文案须标明"当前任务"、与首屏区隔，且全文不得再出现第二个**批量**入口；
  4. 删 UI 入口不得动后端 API/函数；返工后重走 code-reviewer＋qa，qa 补一条静态断言：全文批量入口唯一、每个动作标明范围＋whisper 成本。
  - 若 TM 认为该 DoD 句应按「详情上下文快捷不算三入口」改口径：属 **Change B**（TM 分类、局部 Requirement/DoD 更新、留 DEVELOP），**先落文档再派返工**，不得由 builder 自行解释。

### 2×P2 裁定

- **P2-1（`#msg` 无点击关闭）→ 记 backlog，不返工**。FR-17/D-23 原文是「短提示 3 秒自动消失**或**可点击关闭」，`say()` 已实现 3 秒清空（`index.html:1022`），满足二选一。builder 本轮既已返工，允许顺手加"点击 `#msg` 清空"一行，但**不作验收项、不因此扩范围**。
- **P2-2（`openLongPanel/closeLongPanel` 用 `className` 整覆盖）→ 记 backlog，不返工**。`#longPanel` 当前无其它类，无实际缺陷；改 `classList.add/remove` 属硬化，非本轮验收条件。

### 独立复测断言（只读）

- `python3 -m compileall -q app/server.py` → **exit 0**；无 `__pycache__` 残留（仓内 `find` 为空）。
- `git diff --numstat` → index.html 93+8=101、server.py 19+3=22，合计 **+112/−11**，与 reviewer/qa/HANDOFF 记数一致。
- **FR-13（server）**：mismatch 只降级 `AUTO_RETRANSCRIBE/AUTO_REUSE/AUTO_PUBLISH` → `NEEDS_HUMAN/MANUAL_REVIEW/whisper=False`，并把 `next_action` 改写为"原因待验证"；diff 内**零 DB/manifest/产物写**。逐行复核确认：16 条真实缺源件走 `SOURCE_LOCATION_REVIEW`→`NEEDS_HUMAN`，**不在**降级集合内，其 `next_action`＝「确认替代路径后重新诊断」与 `reason` 未被覆盖，**无回归**。`persisted_state_at/display_state_source/display_state_at/display_persisted_mismatch/recovery_eligibility_source/at` 均已输出。
- **FR-17/D-23**：`say` 截断 120 字＋3 秒清；`copyText(t,opts)` 成功只出短句、失败只出短错、正文只进 `lastLongText`＋`#btnViewLong`（不自动开面板）；面板具标题/关闭按钮/Esc/遮罩/焦点返回，`#longPanelText{max-height:min(70vh,560px);overflow:auto}` ✓。`copyAllFailedReasons` 传 `shortOk:"已复制 N 条失败原因"` ✓。
- **FR-13（前端）**：`statusCN` 加 `isActive` 闸（仅 run 自身 ACTIVE/RUNNING 且有 worker 阶段才出阶段文案），与监听开关脱钩 ✓；`renderLineage` 并列告警且无回写 ✓。新按钮 `btnRecTranscribe/btnRecReuse/btnRecPublish` 绑定的 `failedRuns/retryAllFailed/reapplyOne/retryRun`、`selected/cache` 均实际存在（L481/1094/1142/1081/319）✓。
- **主题**：`index.html:2` `<html data-theme="light">` 未动、diff 无主题改动 ✓（浅色默认未回退）。
- **挂账观察（不拦、记 backlog）**：① 前端并列不一致用启发式（persisted∈{QUEUED,ACTIVE} 且文案含失败/受阻），未展示 `display_state_source/at`（P3）；② `#recoverBox` 在 DOM 中位于 `#progress` 之后，"首屏无需滚动可见"目前只有静态 DOM 证据，真机可见性未验（归 P1-6 布局验收）。

### 第二道校验（整块照跑，看 exit 码）

- `docs/model/TASK-MODEL-LOG.jsonl`（**46 行**）→ **exit 0**；无缺键、result/escalated 枚举合法、rework 均为 int（无 bool）。
- `docs/model/DISPATCH-LOG.jsonl`（**24 行**）→ **exit 0**；8 键齐、`used` 恒"主"、runtime 枚举合法。
- **P0-3 补记三行核对（TM 依根表补记）**：builder `opencode-go/deepseek-v4.1-flash`／本窗口、code-reviewer `opencode/muse-spark-1.3-contributor-free`／本窗口、qa `codex/gpt-5.6-luna`／codex —— 与根 `USER_MODEL_OVERRIDE.md` **逐字一致**，`used`＝主，**无不一致，不打回**。
- **本打回后待 TM 落盘**：DISPATCH 补 supervisor 行（`result:"FAIL"`＝本回复检结论）；`TASK-MODEL-LOG` 的 `DEVELOP-P0-3-IMPL（FR-13/14/17；D-16/19/23）` 行 `rework` 由 **0 → 1**（口径＝被 supervisor 打回次数），最终 `result` 待返工收口后判。

### 三处对账（HANDOFF＋TASK-MODEL-LOG＋DISPATCH-LOG）

- 角色链：三处均为 P0-3 已过 builder→code-reviewer→qa、差 supervisor ✓。
- 行数：HANDOFF 记「账本 46 行／派工 24 行」＝实测 **46/24** ✓。
- 打回计数：HANDOFF「P0-3 本链 0/2」＝DISPATCH 无 P0-3 supervisor 行＝TASK 行 `rework:0` ✓（本打回后应为 **1/2**，需 TM 同步三处）。
- 链 ID／Session：本链为普通 subagent（留空），符合"普通 subagent 留空合法" ✓。
- **三处对得上**，本次无因账本产生的打回项。

### Phase Integrity 五查

1. PLAN 禁 builder/qa 业务派工：本阶段新增派工全为 DEVELOP 角色，无 PLAN 期业务派工 ✓。
2. WAITING 禁自动开发：HANDOFF `PLAN_GATE=APPROVED`＋用户 2026-09-14 明说「第二阶段，开发」，非私自跨越 ✓。
3. DEVELOP 必有基线：`DEV_BASELINE=PRODUCT_PLAN_V1.3`（HANDOFF:11）✓。
4. C 类变更禁绕 Controlled Reopen：`CHANGE_REQUEST=NONE`；本次打回要求全部落在 V1.3 的 FR-14/D-19 基线内，未绕开 ✓。
5. TM 持续推进：本轮 TM 已补 P0-3 三行派工＋账本一行并同步 HANDOFF，无停摆 ✓。

- 额度/耗时：本次复检零外部模型调用（本窗口只读）。
- `python3 -m compileall -q app/server.py`：`COMPILE_OK`
- `git diff --check`：通过

> neat-freak 加注（2026-09-14，只记不改）：本文件尾部 supervisor 复检节为当时历史快照，正文不动。当时记 `+112/−11`（index 93+8、server 19+3）、账本 46 行／派工 24 行；当前工作树已推进为 `+209/−34`（index 181/31、server 28/3），DISPATCH／TASK-MODEL-LOG 行数亦有 TM 落盘新增。引用行号（`:605/:270/:742` 等）为当时位置，旧三入口现全文 0 命中（见 RETEST2 与语义修复链报告）。P0-3 本链打回计数当时 `1/2`，语义修复链未新增 supervisor 打回，仍为 `1/2`。
