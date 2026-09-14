
# CODE REVIEW

- Task: P0-1 只读诊断返工复核 `GET /api/failures/diagnosis`（DEV_BASELINE=PRODUCT_PLAN_V1.3，FR-1/FR-2/D-1/D-2/D-3/D-8；首轮 P0-1/P1-1/P1-2 三项）
- Commit: 未提交工作树（`git diff -- app/server.py`，`f490ac3..c4625a8`，+222 行；首轮报告 `docs/review/P0-1-DIAGNOSIS-CODE-REVIEW.md`）
- Reviewer: code-reviewer（本窗口 subagent，只复核不写业务代码）
- Result: 过（PASS；三项返工均到位；业务代码一字未动，未启动服务，未碰真实目录）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## P0 / P1 Findings

- P0-1（成功项隔离，D-8/FR-8）：CLOSED。`_handle_failure_diagnosis` 现按持久态先跳过 `status in {SUCCEEDED, COMPLETED}`（diff 新增 `continue` 分支），不再经 `_diag_action` 判纳入；61 成功项无论有无 manifest 均不进 items/counts。残留 `display` 行（`action==UNKNOWN and status==SUCCEEDED → SUCCEEDED`）已不可达，无影响。
- P1-1（counts 口径，FR-1/D-8）：CLOSED。`counts.auto_retryable_failure_count` 现按 `recovery_eligibility in {AUTO_RETRANSCRIBE, AUTO_REUSE, AUTO_PUBLISH}` 计数，另保留 `will_call_whisper_count` 作成本维度；资格语义与成本维度已分离，REUSE/PUBLISH（whisper=0）计入前者不计入后者。
- P1-2（七类互盖，FR-2/D-2）：CLOSED。`_diag_action` 内 transient/ASR 分支已移到 manifest-REUSE 分支之前；transient+manifest → RETRYABLE，干净失败+manifest → REUSABLE，publish+manifest → PUBLISH_BLOCKED（publish 分支仍在 transient 之前，仅影响 publish+transient 双关键词极端行，不属返工要求范围）。

## P2 / P3 Backlog Findings

- 沿用首轮 P2-1/P3-1/P3-2（回包 `data_root` 回显、顶层 provenance 恒 NOT_TIME_ALIGNED、alternate 扫描边界），本次返工未扩大范围，不卡 P0-1。
- 验证：`python3 -m compileall -q app/server.py` 通过（本复核实跑）；只读 `git diff` 核对，未启动服务，未碰真实目录。
