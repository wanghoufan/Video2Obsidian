
# CODE REVIEW

- Task: P0-3 返工二轮复核（supervisor累计1/2；P1-1新「仅重新入库whisper0承诺不兑现」是否闭环）
- Commit: 工作树未提交（基于 b94845e）。`M app/index.html` +181/−31、`M app/server.py` +19/−3（server计数与返工前一致，返工零后端改动）
- Reviewer: code-reviewer（本窗口，只读，不写业务代码；未起服务，未跑handler，未碰真实目录/Obsidian库/主题开关；`python3 -m compileall -q app/server.py` exit 0，抽`<script>`全文 `node --check` exit 0）
- Result: PASS（P1-1新已闭环；往下走 qa＋supervisor；含 1×P2 交 supervisor 裁决，不拦收口）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## P0 / P1 Findings

- P0-1 P1-1新闭环 → PASS。`publishOnlyRetry(run_id)`（`app/index.html` 新增约1093-1137行）真走 P0-2 已有 PUBLISH_ONLY 通路：`POST /api/failures/retry-plan` 取 plan（`run_ids:[单id]`＋data_root/vault透传）→ 集合内找 `hit`（不在则报"不在可恢复集合内（零执行）"）→ 校验 `hit.strategy==="PUBLISH_ONLY"`，非此策略报 warn 直接返回、零 batch 调用 → `POST /api/failures/retry-batch {confirm:true, plan_token, run_ids:[单id]}`。集合校验一致、单条 confirm、非PUBLISH_ONLY fail-closed 零执行，三项齐备。
- P0-2 三处whisper0承诺兑现 → PASS。调用点：首屏 `#btnRecPublish`（1818行）→`publishOnlyRetry`；行级 `data-retry-publish`（行表142行绑定）→`publishOnlyRetry`；详情 failbox `data-retry-publish`（195行绑定）→`publishOnlyRetry`。三处文案"只重新入库，whisper 0次"均不再走 `/api/retry`（`retryRun` 仅剩 `data-retry` 非publish路径），与上轮 FAIL 的两条路径（btnRecPublish＋详情PUBLISH_BLOCKED）正好对应消解。`retryRun` 本体未动，非publish失败仍走逐个 `/api/retry` 幂等，无串路。
- P0-3 旧要求①②③④无回退 → PASS。①两批量入口仍 0 命中（`btnRetryAllFailed|btnReapplyAll|全部应用新词库重跑` 全文 grep＝0）；②`#recoverBox` 范围 radio＋`syncRecScope`＋confirm 语义 intact；③详情高级单条保留且三处范围标注 intact；④后端零改动（server numstat 19/3 与返工前逐字相同）。FR-13 mismatch 降级零DB写、FR-17 四退出＋120字截断＋3秒清均未被触碰。
- P0-4 基线/Requirement/DoD → PASS。DEV_BASELINE=PRODUCT_PLAN_V1.3 一致；FR-14"执行前标明是否调用whisper＋每个动作标明范围"实质兑现（publish 路由已兑现承诺）；DoD"全文不再出现三个互不关联的批量重跑入口"维持（错词重跑为 FR-9 豁免项，见上轮裁决，本轮未新增批量入口）。
- P0-5 Diff越界/回归/回滚 → PASS。diff 仅 index.html 新增函数＋三处绑定分流＋文案；`retryAllFailed/reapplyAll/reapplyOne` 函数体保留；`copyAllFailedReasons` 改走 `shortOk/longText` 与 FR-17 一致；可回滚＝整段删除 `publishOnlyRetry`＋三处绑定改回 `data-retry` 即回 v1，无 DB/schema 变更。
- P0-6 主题浅色 → PASS。`git diff` 全文 `theme|dark|light` 0 命中；`:2` 仍 `<html data-theme="light">`。
- P1：无（上轮 P1-1新已闭环，本轮无新增 P1）。

## P2 / P3 Backlog Findings

- P2-1（文案术语残留，不拦收口）：详情高级 `obhint`（`app/index.html:741`）仍写"转写0次（whisper 不跑）"，与本轮其余位置统一后的"whisper 0次"术语不一致；最小改法：该句改为"whisper 0次（只重排整理与成稿，原文不动）"。supervisor 可直接放行并记 backlog。
- P3-1：`btnCandidateApply` title 已改为用户语言（"先改词库，再对全部已完成稿件重新成稿"），去术语 PASS；`rerun_old` confirm 仍有"转写0次"字样（1396行），与 P2-1 同类，可顺手统一，不拦收口。
- 已核不是缺陷：`#recoverBox` 静默跳过旧忧（`/api/retry` norm-COMPLETED 静默跳过）本次仅影响 `retryRun` 非publish 路径，publish 路径已绕开该通道；`#msg` 点击关闭、`className` 覆盖两项仍为既有 backlog，不重复记。
