# CODE REVIEW

- Task: P0-1 只读诊断 `GET /api/failures/diagnosis`（DEV_BASELINE=PRODUCT_PLAN_V1.3，FR-1/FR-2/D-1/D-2/D-3）
- Commit: 未提交工作树（`git diff -- app/server.py`，`f490ac3..3f02c66`，约 +214 行；基线 `d807483`）
- Reviewer: code-reviewer（本窗口 subagent）
- Result: 打回 + 改法（见 P0/P1；业务代码一字未动）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## 核对结论（先说通过项）

- 只读无写：`_handle_failure_diagnosis` 内 DB 经 `_open_ro`（`mode=ro` URI）+ 仅 `SELECT`（`processing_runs`/`sources`/`state_events`/`sqlite_master`）；诊断 helpers 经 AST 检查无 `commit/executemany/makedirs/remove/rename/rmtree/move/copy/write/connect`；文件侧仅 `os.stat/os.path.isfile/os.walk/open(rb)/open(manifest.json, r)` 只读。`whisper_calls` 恒 0（`will_call_whisper` 仅布尔输出，无调用）。符合 D-3 零副作用方向。
- UNKNOWN 兜底：`_diag_action` 末分支返回 `UNKNOWN/UNKNOWN/UNKNOWN/MANUAL_REVIEW/NEEDS_HUMAN`；缺 manifest/缺 state_event/无候选均回 `UNKNOWN`，未编造"不存在"。符合 FR-2/D-2 fail-closed 方向。
- 路由注册正确：`Handler.do_GET` 内 `parsed.path == "/api/failures/diagnosis"` → `_handle_failure_diagnosis` → `_send_json`，GET 只读位置正确；DB 缺失/缺表时 fail-open 返回 `ok:False + DB_MISSING/DB_SCHEMA_MISMATCH`，未抛 500。
- 路径脱敏主体到位：`recorded_path_redacted/alternate_path_redacted` 经 `_diag_redact_path`（`…/末三段`），`source_label` 仅 basename；`reason/next_action/confidence` 不含路径正文。
- 编译：`python3 -m compileall -q app/server.py` 通过（本复核实跑）。未启动服务、未碰真实目录（仅读代码 + AST + diff）。

## P0 / P1 Findings

- **P0-1（成功项隔离 broken，D-8/FR-8）：SUCCEEDED 行可能被计入诊断 items 且 display=FAIL。** `_handle_failure_diagnosis` 的纳入条件为 `action != UNKNOWN or status not in {SUCCEEDED, COMPLETED}`；而 `_diagnosis_item` 的 `display` 为 `SUCCEEDED 仅当 action==UNKNOWN 且 status==SUCCEEDED，否则 FAIL`。于是：一条 `status=SUCCEEDED` 但 manifest 含 `raw_path/normalized_path/rendered_path` 的行 → `_diag_action` 走 `REUSABLE_DERIVED_FAILURE` 分支（与 error 文本无关）→ `action != UNKNOWN` → 被纳入 `items` 且 `display_state=FAIL`。后果：61 个成功项在"有 manifest"时会被标 FAIL 并抬高 `incomplete_or_blocked_total`，违反 D-8"正常 UI 与恶意请求两路均排除 61 成功项"与 FR-8 双语义。当前 DB 全 QUEUED 时不可见，但属隔离性 P0。**改法**：纳入条件改为按持久态先排除成功（`status in {SUCCEEDED, COMPLETED}` 直接跳过，不参与 items/counts），或至少 `display` 对成功态恒为 `SUCCEEDED` 且不计入 `incomplete_or_blocked_total`；补一个合成用例：SUCCEEDED+有 manifest → 不在 items 中。
- **P1-1（counts 口径不对，FR-1 Data/API / D-8）：`auto_retryable_failure_count` 只数 `will_call_whisper=True`。** 当前 `counts.auto_retryable_failure_count = sum(will_call_whisper)`，仅 `RETRYABLE_TRANSCRIPTION/RETRANSCRIBE` 为 True；`REUSABLE_DERIVED_FAILURE/AUTO_REUSE` 与 `PUBLISH_BLOCKED/AUTO_PUBLISH` 的 `will_call_whisper=False` 但恢复资格为 AUTO（whisper=0 的自动恢复）被排除。计划 FR-8 第二层"恢复资格语义"与 D-8 断言的 `auto_retryable_failure_count` 应覆盖"可自动重试失败"（含复用/仅入库），而 `will_call_whisper` 只是"是否调 whisper"的成本维度，两者被混为一谈。当前 16 条下两者都是 0 所以 D-1/D-8 现实断言仍成立，但口径错。**改法**：`auto_retryable_failure_count = 命中 AUTO_RETRANSCRIBE/AUTO_REUSE/AUTO_PUBLISH 的条数`（即 `recovery_eligibility in {AUTO_RETRANSCRIBE, AUTO_REUSE, AUTO_PUBLISH}`），另保留 `will_call_whisper_count` 作成本维度；合成用例断言 REUSE/PUBLISH_ONLY 计入前者但 whisper 数为 0。
- **P1-2（七类互盖风险，FR-2/D-2）：manifest 检查排在 error 文本的 transient 检查之前。** `_diag_action` 顺序为 SOURCE_LOCATION → PRECONDITION → INPUT_MEDIA → PUBLISH → manifest-REUSE → transient-RETRYABLE → UNKNOWN。于是：一条带 `timeout/transient/asr` 文本且恰好有旧 manifest 的行会被判 `REUSABLE` 而非 `RETRYABLE`；一条带 `permission` 文本但有 manifest 的行幸好先被 PRECONDITION 截获，但反向（transient + manifest）无保护。FR-2 要求"三者不得互相覆盖或互相推导冒充事实"、D-2 要求"更改一轴不得偷换他轴"，当前优先级是隐式覆盖。**改法**：error 文本的瞬时/转写信号优先于"有 manifest 即复用"（或 manifest 分支追加 `且无 transient/asr 文本` 条件）；补合成用例：同一行分别断言 transient+manifest → RETRYABLE，publish+manifest → PUBLISH_BLOCKED，干净失败+manifest → REUSABLE，证明不互盖。

## P2 / P3 Backlog Findings

- **P2-1（回包绝对路径回显）：** 成功回包顶层含 `"data_root": data_root`（绝对路径原样回显）。请求方本就持有该值，不算新泄漏，且计划允许"data_root 对页面本机可用"；但 Data/API 列出的诊断返回字段（`ok/diagnosis_version/snapshot_id/generated_at/persisted_snapshot_at/page_snapshot_at/provenance_status/counts/categories/items`）不含 `data_root`，D-12/D-22 对"错误响应/复制摘要零绝对路径"有要求。建议：成功回包去掉 `data_root` 或仅在 debug 时回显；复制摘要（前端待做）必须只用 `*_redacted` 字段。P2，不卡 P0-1。
- **P3-1（provenance 顶层恒 NOT_TIME_ALIGNED）：** 顶层 `provenance_status` 写死 `NOT_TIME_ALIGNED`，逐项 `aligned = event_at == updated_at` 的对齐判定较弱（`updated_at` 未在 SELECT 中显式取，依赖 `pr.*` 隐含列）。与 D-1"时间未对齐时保留 NOT_TIME_ALIGNED"一致，当前可接受；待页面 snapshot 接入后再收紧。仅记录，不返工。
- **P3-2（`_diag_alternate_paths` 扫描边界）：** 以 `recorded 上两级 + ~/Downloads + /Volumes + data_root` 为根、walk 深度 ≤4、跳过点目录，有界只读，符合"先扫已挂载/常见根"方向；与计划 V1.3 证据矩阵的"九根 + Spotlight + 占位变体"范围不等（实现是运行态有界版，矩阵是离线审计版），差异应在 QA 报告注明"实现覆盖 ≠ 矩阵覆盖"，`alternate_path_checked` 布尔值建议未来改为枚举/列表。仅记录。
