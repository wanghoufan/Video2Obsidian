# CODE REVIEW

- Task: P0-3 核心状态、恢复入口与可退出反馈（FR-13/FR-14/FR-17；D-16/D-19/D-23）
- Commit: 工作树未提交（基于 b94845e；diff 为 `M app/index.html` + `M app/server.py`，+112/-11）
- Reviewer: code-reviewer（本窗口，不写业务代码；只读，未启动服务；`python3 -m compileall -q app/server.py` = COMPILE_OK）
- Result: PASS（往下走 qa；含 1×P1 + 2×P2 交 qa/supervisor 裁决，不拦主线）

## P0 / P1 Findings

- P0-1 FR-13 四层状态 + mismatch 降级不回写DB：PASS。`app/server.py` 仅在 `_diagnosis_item` 内加局部变量 `persisted_state/mismatch`，mismatch 时 `eligibility→NEEDS_HUMAN/policy→MANUAL_REVIEW/whisper→False`，新增 `persisted_state_at/display_state_source/display_state_at/worker_stage_source/worker_stage_at/display_persisted_mismatch/recovery_eligibility_source/recovery_eligibility_at` 只读字段；diff 内无 DB/manifest/产物写操作。`app/index.html:statusCN` 脱钩（仅自身 ACTIVE/RUNNING + worker 当前阶段才显示阶段文案，否则忽略 `cur`），`renderLineage` 加"展示与记录不一致，原因待验证"并列告警且无回写。符合"fail-closed，不用页面状态回写"。
- P0-2 FR-14 统一恢复入口：PASS（首屏 `#recoverBox` 三按钮 + whisper 成本文案：重新转写/从已有文字重新成稿 whisper 0次/仅重新入库 whisper 0次 + 不覆盖；详情仅留上下文快捷的注释与实现一致）。P1-1：旧散落批量入口（表头"重试全部失败"、词库区重跑、详情高级）本次未删除，FR-14 验收句"全文不再出现三个互不关联的批量重跑入口"需 qa 实点裁决；若判为收敛不全，记 P1 返工（删旧入口回归风险高，不在本轮强行删）。
- P0-3 FR-17/D-23 可退出反馈：PASS。`copyText(t,opts)` 成功只 `say(shortOk)+toast`，`copyAllFailedReasons` 传 `shortOk:"已复制 N 条失败原因"`，长文只存 `lastLongText` + 显示 `#btnViewLong`，不自动开面板；失败路只短错，不拼正文不开面板。`say` 截断 120 字 + 3 秒清空。长文面板具标题/关闭按钮/Esc/遮罩关闭/焦点返回，CSS `#longPanelText{max-height:min(70vh,560px);overflow:auto}`。浅色默认未动（diff 无主题改动）。

## P2 / P3 Backlog Findings

- P2-1：D-23"短提示可点击关闭"——`#msg` 仅 3 秒自动消失，无点击关闭；建议 qa 确认是否补（极小）。
- P2-2：`openLongPanel/closeLongPanel` 用 `className="open"/""` 整覆盖 `#longPanel` 类，若日后该节点加别的类会被吞；建议改 `classList.add/remove`（不拦收口）。
