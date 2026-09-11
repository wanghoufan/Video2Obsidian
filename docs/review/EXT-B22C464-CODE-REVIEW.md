# CODE REVIEW

- Task: 审计绕过评审链的外部提交（git diff 874aaf4..b22c464 中 app/ 与 src/ 业务增量；README/usage/troubleshooting 只顺眼看，不审）
- Commit: b22c464（range 874aaf4..b22c464；业务面 app/index.html +23 / app/server.py +728 / src/stage9/__init__.py +4 / src/stage9/formatter_v2.py +60；src/stage3 零碰）
- Reviewer: code-reviewer（本窗口 subagent，按真源 override 主用 codex/gpt-5.6-terra 通道）
- Result: 过（P0×0 / P1×0；P2×6 backlog 不卡合入；合入前仍须补 qa + supervisor，提交信息与内容不符须拆分见 P2-6；技术分歧以本结论为准）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## P0 / P1 Findings

- 无 P0/P1。对照 8 项均 PASS（b22c464 blob 实核）：
  - No-Clobber PASS：`_apply_v25_postpass` 只覆写引擎刚 mint 的 jobs 内 rendered md（b22c464:app/server.py:1441-1503，chmod 644→写→444 恢复提交态），vault canonical 仍走 `publish_or_block` present 永不覆盖 + `BLOCKED_OUTPUT_CONFLICT→skipped_user_edited`（3048-3157）；`_save_vocab_entries` 仍 tmp+rename 原子；启动门只读计数不删行。
  - STOP EXPANSION PASS：无新路由（8 路不变，仅 `do_POST` 外层 try 包 500 JSON，3327-3369）、无新 mechanics；src 只加 stage9 两个纯函数（见 src 改动面），stage3/冻结引擎零碰（`git diff --name-only -- src` 仅 stage9 两文件）。
  - 转写 0 次/whisper 计数 PASS：新增逻辑零 whisper 调用（`rg whisper` 新增仅计数透传）；`_db_success_run_ids_ro` 缺口补齐跳过旧账不再跑 whisper（232-283 + worker `skip_old` 2652-2680）；`_reapply_one` 保留 `whisper!=0` 拦截 + Raw 双 sha 比对（3048-3053）；`V25_POSTPASS` receipt 透传 `whisper_calls: engine_calls` 不重计。
  - vocab 单字门 PASS（新加路径）：`_validate_vocab_pair` `len<2` 拒收 + 纯标点/空格拒收（1343-1377）；`_handle_vocab_add` 第二段 `len<2` 复检覆盖单字亦 400（1559-1561）；前端 `len<2` 前拦 + `len<=3 confirm` 复用 delVocab 口径 + `preview.warnings` 回显（index.html:858-869）。`a→b/的→地/...→x` 新加均 400 口径已对（沿用 V2.5 复核结论）。
  - reveal 仅定位语义 PASS：`_handle_reveal_post` 本 diff 零改（diff 内仅 do_POST 外层缩进搬运，函数体 3281-3317 不动），仍绝对路径 + `exists` 校验 + 列表形 `subprocess.run(["open","-R",real])` 无 shell，直返 `{ok,path}` 不回文件内容。
  - stdlib-only PASS：diff 新增 import 仅 `string`（404）+ 函数内 `json`（441）+ 存量 `hashlib/sqlite3`，无第三方；stage9 新增复用 `_split_overlong/_enforce_hard_cap/_merge_shorts` 纯函数，无网络/模型。
  - src 改动面 PASS：仅 `src/stage9/__init__.py` 加 2 导出 + `formatter_v2.py` 加 `split_segments_for_engine/postprocess_paragraphs`（60 行，纯函数，读 `PARA_PARAMS_V2` 不硬编码，b22c464 仍 para-v2.5 `{120,200,40}`）；未改 `render_with_v2` 既有逻辑，未碰 stage3 任一文件。
  - 无 secrets PASS：`git diff` 全量 `rg -i api_key|secret|token|password|sk-|ghp_|AKIA` 仅命中 docs 账本旧行与治理注释，app/src 零命中。
  - 终态放行 fail-closed PASS：`_is_norm/rend/pub/arch/art_terminal` 未知/空→False→计拦（实测 `''/None/UNKNOWN→False`，`COMPLETED/FAILED_*/PUBLISH_EVALUATION/BLOCKED_*→True`），与 src 枚举对齐（normalize PENDING/NORMALIZING/COMMITTING 半截、render ARTIFACT_COMPLETED 半截见 render.py:49-53、publish PENDING_PUBLISH 终端见 publish_commit.py:53-69）；`artifacts` 新增门 PREPARED 拦/COMMITTED 放行方向为 fail-closed。

## P2 / P3 Backlog Findings

- P2-1 纯标点覆盖绕过（V2.5 复核 P2-①延续，非新加路径）：legacy 文件手造 `...→old` 时 `overwrite ...→new` 因第二段无纯标点复检而回 200（已实证第二段仅 `len<2`/基表复检，`all(ch in _punct)` 只在 `_validate`）。改法：第二段补与 `_validate` 同款纯标点/空格门，或 `if err is not None and wrong_s in existing and err 含单字/标点→仍 400`（仅“已在词库”覆盖文案放行）。
- P2-2 覆写后 DB `final_hash` 分叉（V2.5 复核 P2-③延续）：`_apply_v25_postpass` 覆写 md 后 `render_revisions.final_hash` 仍为 mint 时引擎稿哈希。改法二选一：生产改预切 `split_segments_for_engine` 再喂引擎保 hash 一致，或覆写后更新 DB `final_hash` + manifest 备注。
- P2-3 短词命中数未试算（V2.5 复核 P2-②延续）：2-3 字统一通用警告（命中超 50 请删），未调 `apply_corrections` 试算 `applied_count` 按 >50 分级。改法：add 成功前对 `wrong` 做一次内存试算回 `preview{applied_count}`，>50 才强警告。
- P2-4 终态口径需 planner 确认并文档化（STOP-EXPANSION 收口）：`artifacts` 新增门（PREPARED 拦）比旧门严、`_PUB_TERMINAL` 含 `PENDING_PUBLISH/CANONICAL_OUTPUT_EXISTS` 放行、`_ARCH_TERMINAL` 含 `ARCHIVED` 均为本笔新口径，方向安全但属行为变更。改法：planner 一句确认 + HANDOFF/注释记“有意”，`ARCHIVED` 若无源头则删或注来源；`counts["artifacts"]` 仅非零才设键与 orig 断言签名差一并注释。
- P2-5 绿条 N 行/润混用 + 500 透传内错（UI/信息收敛）：`_launch` `_n = len(_pre_all) or _runs or _rows` 行润混排（多表终态行可大于视频数），`_open_rw/do_POST` 500 回 `str(exc)` 含绝对路径。改法：N 统一 run 去重（无 run 回落 rows 并注“条=行”），500 对外脱敏（落盘记全量，前端只给人话）。
- P2-6 死导出 + 提交与链路收尾（process，不审 docs 内容）：`split_segments_for_engine/postprocess_paragraphs` 生产未直调（经 `render_with_v2` 重算等效，可接受但须 audit-only 注明或删）；本 commit 信息称“文档”实含 728 行业务码，且绕过 planner/qa/supervisor。改法：拆分为 docs 与 app/src 两提交并正名信息；本过仅替 code-reviewer 一环，合入前须补 qa 实测（启动门旧账放行 2 例 + 生产 450 单段 + 覆盖纯标点）+ supervisor 复检。

证据备注：`py_compile app/server.py + formatter_v2.py + __init__.py` 过；`rg` 零 stage3 触碰、零 secrets、reveal 零改（仅缩进）、终态谓词空/未知 fail-closed 实测；P2-1 第二段无 `_punct` 复检、`_handle_vocab_del` 不驱逐内存（V2.5 P2-4 延续，不另计数）已核。
