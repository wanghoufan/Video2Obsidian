
# CODE REVIEW

- Task: P0-3 语义修复复核（supervisor累计仍1/2；QA-P03-RR2-001：PUBLISH_BLOCKED 被误判 mismatch）
- Commit: 工作树未提交（基于 b94845e）。本轮 server.py 单 hunk（`@@ -1331`，+19/−3 行内含 mismatch 语义块＋只读 provenance 附加字段）；`app/index.html` 的 +181/−31 为前序返工二轮 carryover（publishOnlyRetry 三处接线），本轮无新增前端改动
- Reviewer: code-reviewer（本窗口，只读，不改业务代码；未起服务，未跑 handler，未碰真实目录/Obsidian 库/主题开关；`python3 -m py_compile app/server.py` PASS 即 COMPILE_OK；`git diff` 单 hunk 抽查＋`_scan_disk_states:660-723` 全文对照）
- Result: PASS（QA-P03-RR2-001 根因已正对消解；往下走 qa 重验＋supervisor；含 1×P2 不拦收口）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## P0 / P1 Findings

- P0-1 FAIL 家族口径与 _scan_disk_states 一致 → PASS。`_FAIL_SEMANTICS={"FAIL","PUBLISH_BLOCKED","TRANSCRIBE_FAILED","RAW_FAILED","MIRROR_FAILED","NORM_RENDER_FAILED"}`（`app/server.py:1342`）为 `_scan_disk_states:713-716` 失败分支集合（PUBLISH_BLOCKED＋4×*_FAILED）再并上展示层字面 `"FAIL"`；`_scan_disk_states:715` 本就把该五态映射为 `PUBLISH_BLOCKED/FAIL` 语义，docstring `:664-665` 亦写"含 FAIL 语义"。display==FAIL 时 `persisted_state not in _FAIL_SEMANTICS` 才算 mismatch，故正常 `PUBLISH_BLOCKED` 不再误判，QA 复现式（display FAIL＋persisted PUBLISH_BLOCKED→mismatch True→eligible=0）本轮必为 False→可进 PUBLISH_ONLY 计划。`display==SUCCEEDED` 仅对 `SUCCEEDED`（display 推导 `:1334` 本就只在 `status==SUCCEEDED` 时取 SUCCEEDED，自洽）；else 分支字面比较兜底。真 mismatch 无漏判：`QUEUED/ACTIVE/UNKNOWN/SUCCEEDED-vs-FAIL` 均不在 FAIL 家族内，仍判 mismatch。
- P0-2 真不一致仍 fail-closed 降级 → PASS。`if mismatch:` 追加 conflict＋仅当 `eligibility in {AUTO_RETRANSCRIBE,AUTO_REUSE,AUTO_PUBLISH}` 才降 `NEEDS_HUMAN/MANUAL_REVIEW/whisper=False`＋改写 next_action；非 AUTO 资格不动，避免误伤 NEEDS_HUMAN 本身。语义为"降级恢复资格"，无回写 DB。
- P0-3 零 DB/manifest/产物写 → PASS。单 hunk 内无 `UPDATE/INSERT/commit/open(.*w)/manifest 写`；`persisted_state` 只是把 `row.get("status")` 提为局部变量复用；其余新增全为 return dict 只读附加字段（provenance 见 P2-1）。`_scan_disk_states` 只读未动。
- P0-4 越界（只动 mismatch 一块）→ PASS（附 P2-1 注记）。server.py 全文 diff 仅此一 hunk；P0-2 三策略/retry-plan/retry-batch/SCAN-FIX（2s/2000 预算/云根跳过/Volumes 顶层）零触碰。附加 provenance 字段超出字面"8 行"但纯加性只读，不改行为，记 P2 不打回。
- P0-5 P0-2 集合校验无回归 → PASS。retry-plan/batch 集合校验代码零改动（diff 无第二 hunk）；FAIL 家族归一化只影响 diagnosis 的 `display_persisted_mismatch` 与 eligibility 降级门，不改变 plan 的 eligible 集合定义——反而修复了"正常 PUBLISH_BLOCKED 被降级门挡掉导致 publish_only=0"的阻塞，使 P0-2/P0-3 publish-only 链路可达。可回滚＝整段删除 mismatch 块即回退，无 schema 变更。
- P0-6 浅色/前端未动 → PASS。本轮 index.html 零新增（diff 行数为返工二轮残留）；server diff 全文 `theme|dark|light` 0 命中。
- P1：无新增 P1。

## P2 / P3 Backlog Findings

- P2-1（加性字段兼容性注记，不拦收口）：本轮顺手多加 8 个只读 provenance 字段（`persisted_state_at/display_state_source/display_state_at/worker_stage_source/worker_stage_at/display_persisted_mismatch/recovery_eligibility_source/recovery_eligibility_at`）。均为加法、消费者未用即无影响；但 qa 重验时应断言旧消费者（前端/plan）忽略未知字段，建议 supervisor 放行并记 backlog，前端如需展示 mismatch 可后续消费 `display_persisted_mismatch`。
- P3-1：`_FAIL_SEMANTICS` 内 `"FAIL"` 在 `processing_runs.status` 现实枚举中是否出现尚无实证（receipt 写入均为 *_FAILED；FAIL 仅来自 disk 映射态），保留为防御性超集无害，不建议删除。

> neat-freak 加注（2026-09-14，只记不改）：本报告记 server.py `+19/−3`，当前工作树实测 `git diff --numstat` 为 `28/3`（index `181/31` 与报告一致）。差 9 行插入，疑为 provenance 只读附加字段计数口径差；正文结论不动，待 supervisor 复检时裁定。
