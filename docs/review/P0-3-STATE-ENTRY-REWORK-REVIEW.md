# CODE REVIEW

- Task: P0-3 返工复核（本链 1/2；supervisor 打回项 P1-1「FR-14 收敛未完成」是否闭环）
- Commit: 工作树未提交（基于 b94845e）。`M app/index.html` +130/−30、`M app/server.py` +19/−3；返工仅动 index.html（server.py 计数与 supervisor 返工前实测 19/3 **逐字相同**，可证返工零后端改动）
- Reviewer: code-reviewer（本窗口，只读，不写业务代码；未起服务，未跑 handler，未碰真实目录/Obsidian 库/主题开关）
- Result: **打回（1×P1）**。supervisor 四条返工要求 **① ② ③ ④ 全 PASS**（P1-1 已闭环）；打回原因是本 diff 新增的一处**用户可见成本承诺不被代码兑现**（P1-1 新），最小改法＝改文案或把该按钮接到 P0-2 已有 PUBLISH_ONLY 通路（零后端改动）。若 supervisor 判该句 DoD 只需「文案存在」不需「承诺兑现」，可降级为 backlog 由 supervisor 定，本报告结论按 P1 记。

> 口径说明：上轮我（v1）按「三按钮 + whisper 成本文案齐全」判 PASS；本轮按「每条承诺是否被实际调用路径兑现」复核，属新证据下的改判，非翻烙饼。

## P0 / P1 Findings

### 返工要求逐条核对

- **① 两个批量入口彻底删除 → PASS**。表头 `#btnRetryAllFailed`（v1 在 index.html:605）与其绑定（v1 L609 `var rb=el("btnRetryAllFailed")`）整段消失；词库区 `<div class="controls"><button id="btnReapplyAll">全部应用新词库重跑</button></div>` 整段消失（`app/index.html:267-269` 处已无该 div）。全文检索 `btnRetryAllFailed|btnReapplyAll|全部应用新词库重跑` → **0 命中（HTML/JS）**，无悬空引用；`node --check`（抽 `<script>` 全文）**exit 0**；`python3 -m compileall -q app/server.py` → **exit 0**，无 `__pycache__` 残留。表头只留只读诊断 `#btnCopyFailedReasons`（`app/index.html:603`，title 明示"只读…whisper 0次"），注释同步改写（`app/index.html:559`）。
- **② 删除后能力不丢（范围 + 既有 confirm 语义）→ PASS**。`#recoverBox`（`app/index.html:227-237`）内就地给范围：`#recScopeRow`（`:235`）radio「当前所选任务／全部已完成任务」，`syncRecScope()`（`:1746-1750`）把范围写进按钮文字。范围分流：`all` → `reapplyAll()`（`:1760`，`reapplyPayload({all:true})`，`:1157`）；`sel` → `reapplyOne(run_id)`（`:1766`）。既有 confirm 语义沿用于批量路径：`reapplyAll` confirm（`:1154`）如实含「范围＝全部已完成任务／whisper 0次（只重排整理与成稿，原文不动）／库内改过跳过／已发布不覆盖」；单条路径沿用详情按钮既有语义（本就无 confirm，`_reapply_one` 在 `app/server.py:4946` 有 `whisper_calls!=0` 硬拦截 + raw 字节不变校验，`:4947-4952`），与其"whisper 0次"文案一致。
- **③ 详情高级单条保留且标明"当前任务"→ PASS**。`app/index.html:736-740`：`<summary>高级：应用新词库重跑（仅当前任务；whisper 0次）</summary>`、`obhint` 首句「范围：当前任务…」、按钮文案「应用新词库重跑（范围：当前任务；whisper 0次）」+ title「范围：当前任务（单条，非批量）」。详情失败区 / 行内主按钮同样标注范围（`:724`、`:626-627`、`:719` 注释）。**"全文不得再出现第二个批量入口"** 见下节裁决（literal 口径有 1 处例外，需 supervisor 定）。
- **④ 只动 UI、后端 API/函数保留 → PASS**。返工未改 `app/server.py` 任何一行（numstat 19/3 与 supervisor 返工前实测一致）；`retryAllFailed`/`reapplyAll`/`reapplyOne` 三个前端函数体完整保留（`:1092`/`:1153`/`:1140`），仅供唯一入口调用；后端 `/api/retry`（`app/server.py:4314`）、`/api/reapply`（`:5195`）、`_reapply_all/_reapply_one`（`:5125`/`:4863`）零改动。

### 唯一调用点与范围参数（回归重点）→ PASS

- `retryAllFailed()` 唯一调用点 `app/index.html:1755`（首屏「重新转写全部失败」，范围＝`failedRuns()` 全部失败）。无第二调用点、无重复绑定。
- `reapplyAll()` 唯一调用点 `app/index.html:1760`（radio=all 且 confirm 通过才到）。`all:true` **不可能**在 sel 分支误触发（`:1758` 先判 scope）。
- `reapplyOne()` 三个调用点语义自洽：行级 `data-reapply`（`:658`）、详情高级（`:749`）、首屏 scope=sel（`:1766`）——全部为**单条**范围，无批量误用。
- 新增按钮绑定各 1 处（`:1751`/`:1757`/`:1768`），radio 绑定 1 次（`:1749`，静态 DOM，`refresh()` 不重渲染 `#recoverBox`，无绑定丢失/重复）；`#recoverBox` 所在 `<section>` 无任何 `innerHTML` 整体覆写（全文核过 `innerHTML=` 落点均为叶子节点）。
- 空态：`btnRecTranscribe` 无失败任务 → warn 返回（`:1754`）；`btnRecReuse`(sel)/`btnRecPublish` 未选任务 → warn 返回（`:1764`、`:1771`）。`recScopeVal()` 查不到 radio 时回落 `"sel"`（`:1743`），无 null 崩。
- `retryAllFailed` 逐个调 `/api/retry` 幂等（同 run 已在排队回 202「无需重复操作」，`app/server.py:4357-4366`），双击不会产生重复任务。

### 上轮 P0/FR 回归 → PASS

- **FR-13（server）**：`app/server.py:1331-1370` hunk 与 v1 复核时逐字一致；mismatch 仅降级 `AUTO_RETRANSCRIBE/AUTO_REUSE/AUTO_PUBLISH` → `NEEDS_HUMAN/MANUAL_REVIEW/whisper=False`，diff 内**零 DB/manifest/产物写**；新增字段（`persisted_state_at`/`display_state_source`/`display_state_at`/`worker_stage_source`/`worker_stage_at`/`display_persisted_mismatch`/`recovery_eligibility_source`/`at`）齐备。
- **FR-13（前端）**：`statusCN` 的 `isActive` 闸（`:375-385`）与 `renderLineage` 并列告警（`:690-696`）本轮未被触碰，无回归；无回写路径。
- **FR-17 / D-23**：`say` 截断 120 字＋3 秒清（`:1019`）；`copyText(t,opts)` 短句化（`:1051-1077`）；`copyAllFailedReasons` 传 `shortOk/longText`（`:1128-1130`）；长文面板四退出（关闭按钮 `:1774`、Esc `:1776-1778`、遮罩 `:1775`、焦点返回 `openLongPanel/closeLongPanel` `:1021-1032`）+ CSS `max-height:min(70vh,560px)`（`:171`）；不自动开面板。
- **主题**：`app/index.html:2` 仍为 `<html lang="zh-CN" data-theme="light">`；`git diff` 全文无 `theme|dark|light` 命中 → 主题零改动 PASS。

### P1-1（新，阻断）「仅重新入库」的成本承诺不被调用路径兑现 → FAIL

- 证据（文案）：`app/index.html:233`「仅重新入库（范围：当前所选任务；**whisper 0次**，只写不存在的新笔记，不覆盖）」；`:1769` 还先把它当既成事实写进 `recoverHint(...,"ok")`；`:724`（本次返工**新增**文案）详情失败区 PUBLISH_BLOCKED 分支「重试入库（范围：当前任务；**whisper 0次**）」+ title「只重新入库，whisper 0次」。
- 证据（实际路径）：两处都只调 `retryRun()`（`:1768-1772`、`:746`）→ `POST /api/retry`（`:1081`）→ `app/server.py:4314 _handle_retry_post`（只把 run 从内存 `_worker_done` 移除并回 202「已重新排队，只重跑这一个」，**不做任何"仅入库"分流**）。worker 拿到该 QUEUED run 后走 `_process_one_run`（`:3696`），**无条件先转写**：`:3776 _transcribe_audio(...)`（无产物复用短路，内部必 `extract_temp_wav` + stage7/8 调引擎）。而"仅重新入库/whisper 0"在项目里是**另一条通路**：P0-2 的 `PUBLISH_ONLY` 策略（`app/server.py:1712-1767`，`whisper_calls:0`）只挂在 `/api/failures/retry-plan` + `/api/failures/retry-batch` 确认流上，`/api/retry` 不经过它。
- 两种可能分支都不成立：① run 未被 `skip_old` 跳过（如 norm 未 COMPLETED）→ 真会重跑 whisper，与"whisper 0次"直接矛盾；② run 在 `skip_old` 内（`app/server.py:4025` 由 `disk_done_ids`∪`db_done_ids` 组成；`db_done_ids`＝`normalization_revisions.status='COMPLETED'`，`:238-290`）→ worker 在 `:4059` **静默跳过**，入库其实**没发生**，而 UI 仍弹「已重新排队：xxx，只重跑这一个」（`:1085`）→ 承诺的"仅重新入库"落空且反馈不实。
- 为什么算阻断：FR-14 第二句要求"执行前标明**是否调用 whisper**"，P0-3 DoD 明文"每个动作都显示作用范围和**是否重新转写**"；这是 P0-3 自己 DoD 的实质内容，且 `:724` 的这行文案是**本次返工新加**的（v1 旧文案只有「重试入库」，无 whisper 承诺），属本 diff 引入的缺陷。
- 改法（二选一，均零后端改动）：
  - 首选：`btnRecPublish` 与详情 PUBLISH_BLOCKED 的「重试入库」改接 P0-2 **已有**通路（`POST /api/failures/retry-plan` → 取 plan/token → `POST /api/failures/retry-batch`，`confirm:true`；单 run 传 `run_ids:[id]`），兑现"仅重新入库、whisper 0"。
  - 次选（最小）：文案如实降级，删掉两处"whisper 0次"，改为不承诺未实现的效果（例如「重新排队处理这个任务（可能重新转写；whisper 视任务状态而定）」），并让反馈与真实行为一致（不得对静默跳过的 run 报"已重新排队"）。
- 注：分支②涉及的 `/api/retry` 对 norm-COMPLETED 任务静默跳过、与 `app/server.py:3999` 注释「显式重试可经 /api/retry 重排」自相矛盾，疑似 **P0-2 遗留**；本窗口只读未起服务，未能实测，建议 qa 用 tmp 夹具实测确认（若实测证明入库重试确实生效，即我静态推断有误，本项可降级 backlog）。

## builder 自报判断的裁决（词库候选区「错词重跑」，`app/index.html:251`）

- **我的意见：保留**（不算 FR-14 三入口之一），但**文案需再澄清一句**；最终由 supervisor 定。
- 依据（支持保留）：① `docs/pm/PRODUCT_PLAN.md:62`（FR-9）明文「现有功能不回退：…词库、候选应用、**错词重跑**和浅色主题继续可用」——删它＝违反 FR-9；② FR-14（`PRODUCT_PLAN.md:67`）点名的收敛对象是"重试全部失败／应用新词库重跑／全部应用新词库重跑／入库重试"四条，**不含**错词重跑；③ 它有独立前置条件与独立副作用（先勾选候选 → 改词库 + 标记候选已导入），首屏 `#recoverBox` 无法替代。
- 但必须承认的硬事实（供 supervisor 用）：它在 rerun_old=true 时**确实以 `all=true` 触发批量重排**——`app/index.html:1351` 传 `{indices, rerun_old}`，后端 `app/server.py:2986-2991` 内部再调 `_handle_reapply_post({"all": True})`；前端 confirm 原文即「导入所选错词并**重跑全部已完成任务**吗？」（`:1346`）。所以若 qa 按"全文批量入口**唯一**"字面断言，**必然 FAIL**。
- 建议（低成本、纯文案）：① 按钮 title 现写的「导入后复用 `all=true` 重排重跑」是把实现术语暴露给用户，且等于自认第二个批量入口（`:251`）——改为用户语言，如实说明"会先改词库，再对全部已完成稿件重新成稿（whisper 0次）"；② qa 的验收断言按 **DoD 原句**写（"全文不再出现三个互不关联的批量重跑入口"），并把「错词重跑」列为**已裁决豁免项**（附 FR-9 依据），否则该断言不可通过。

## P2 / P3 Backlog Findings

- P2-1（supervisor 已裁 backlog）：`#msg` 无点击关闭（仅 3 秒自动消失）；FR-17 原文是"3 秒自动消失**或**可点击关闭"，二选一已满足，本轮不做。
- P2-2（supervisor 已裁 backlog）：`openLongPanel/closeLongPanel` 用 `className` 整覆盖 `#longPanel`（`app/index.html:1024`/`:1028`），建议改 `classList.add/remove`。
- P2-3（新）：`say()` 的 3 秒清空对**所有**状态行生效（`:1019`），长任务进行中提示会在 3 秒后变空白（例：`reapplyOne` 的「正在应用新词库重跑…」`:1142`、批量 `retryAllFailed` 的 N/total 进度 `:1109`），结果句也只留 3 秒（有 toast 的路径尚可，无 toast 的会丢）。建议对含「正在…」的进行中提示不设自动清空，或统一改走 `toast`。
- P2-4（新）：`#recoverBox` 常显（状态库未建立/无任务时也有三个按钮），空态下点击只出 warn；建议空态隐藏或 disabled，减少死按钮。
- P3-1：`app/index.html:602` `var nRetry=flist.length;` 现已只用于 `>0` 判定，注释（`:559`）与变量名可再收一句。
- P3-2：`#recoverBox` 说明行「批量恢复动作只在本框内」（`:229`）在"错词重跑"保留的前提下字面不严谨，可加"（词库候选导入流程的附带重跑除外）"。
- P3-3：两个 `keydown` 监听并存（`:1530` 关浏览弹窗 / `:1776` 关长文面板），极端情况下同按 Esc 会同时响应，无实际缺陷。
- P3-4：`#recoverBox` 位于 `#progress` 之后的"首屏无需滚动可见"目前仍只有静态 DOM 证据，真机可见性归 P1-6 布局验收（与 supervisor 观察一致）。
- 已核不是缺陷：主题浅色（`:2` 未动）、`reapplyOne` 与详情按钮文案一致、`复制全部失败原因` 仍为只读诊断（无 whisper 成本）、返工未引入重复事件绑定/重复调用/范围分流错误。
