# CODE REVIEW

- Task: UX2-P0-1（列表limit=200+总数+截断明示）与 UX2-P0-2（清空代价预览dry_run+只清失败only_failed+撤销指引）
- Commit: 工作区未提交（base `b22c464`；`M app/index.html` + `M app/server.py`；`M USER_MODEL_OVERRIDE.md` 为作废丢失待定（HEAD作废声明被工作区旧表覆盖，且与真源包不同文缺-y半句，已记HANDOFF未决）非本次被检；`?? docs/review/UX-REVIEW-2.md`；未 commit、未 push，符合红线）
- Reviewer: code-reviewer（被检文件只在 `app/`；`src/` 零碰以 `git status --short -- src/` 空佐证；技术分歧听 code-reviewer）
- Result: 过（P0 闭环，P1/P2 记 backlog，不拦 QA 67 重放）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## P0 / P1 Findings

- P0-1-① 过：前端 `refresh()` 必带 `limit=200`（`app/index.html:937`）；后端 `_handle_status` clamp 1–200 并附 `run_summary{total,done,failed,pending,shown,truncated,limit}`（`app/server.py:1988-2020`）；前端 `renderRunsHead` 渲染“共 N 个（成功 A/失败 B/排队 C），当前显示 M 个”，截断追加“仅显示前 M 个（共 N 个，还有 L 个未显示）”（`app/index.html:444-466`）。禁静默丢满足：`truncated = total > shown` 任何缺口必显。
- P0-1-② 过（合成实测）：纯 67 库（51 成功 disk PUBLISHED +16 失败）`_scoped_runs_summary` = total 67 / done 51 / failed 16 / pending 0；limit=200 时 shown=67、truncated=False。前端失败兜底 `dbFail`（库 `FAILED*`/`NO_SPEECH_DETECTED`）使无详情行仍可重试（`app/index.html:483-486`）。QA 仍须用真 67 库重放总数=67、可见=67、失败16行行行可点。
- P0-2-① 过：`POST /api/clear {dry_run:true}` 只读（`_open_ro` + `_clear_plan(only_failed=False)` + `_count_job_dirs`，无 DELETE、无 rmtree，`app/server.py:2882-2928`），返回 `preview{db_runs,jobs,total,success,failed,pending,est_retranscribe_minutes,avg_sec_per_video=120,only_failed{...},vault_note}` + 人话（含“失败 N 条建议先逐条重试”）；前端 modal 先显代价行才 enable 按钮（`app/index.html:1126-1166`）。合成 69 行库 dry_run 后行数不变（69），证无写。
- P0-2-② 过：modal 二选一“只清失败 / 全部清空”，初始双 disable，`failed==0` 时只清失败保持 disable，全部清空有二次 confirm（`app/index.html:1164-1190`）。默认不选全清满足。
- P0-2-③ 过：实清返回 `message` + `undo`（只删本 data_root 记录与 jobs，vault md 与源视频未动，换回旧 data_root 即见旧记录，源视频还在可重转，`app/server.py:3095-3098`）；前端 `say(message+undo)+toast`（`app/index.html:1180`）。
- P0-2-④ 过（破坏性实测，隔离 tmp 拷贝）：只清失败删 17（16+孤儿 fail）、留 52（51 成功+1 无归属 pending），`kept_success=51`，`cleared{candidates:16,artifacts:16,runs:17,sources:16}`，NULL archive 留 1，成功 jobs 留 51，源视频 67 未动。成功 51 不动满足。
- P0-安-① 过：jobs 删除仅 `jobs/<run_id>` 一层 + `abspath.startswith(jobs_base+sep)` 防穿越（`app/server.py:3063-3074`）；只动本 data_root DB + jobs，不碰 vault/源视频、他 data_root；`server.py` 无新增 import（`os/json/shutil/sqlite3` 均为既有 28–31 行），stdlib-only；diff 无 secrets 命中的行；未 push。
- P1-① 孤儿口径不一致（header 计入、列表不显示）：`_scoped_runs_summary` 中 `path is None`（LEFT JOIN 空，孤儿）计入 total（`app/server.py:1480-1482`），而 `_filter_status_runs` 对有映射但值空（`str(None or "")=""`）走 `_is_under_root("",…)=False` 丢弃，仅 `rid not in mapping` 才保留（`app/server.py:1175-1179`）。后果：header total 含孤儿但行不可见、不可重试，与 `_scoped_runs_summary` 文档“与 _filter_status_runs 同口径：孤儿视为可见”矛盾。改法（二选一）：A）在 `_filter_status_runs` 中把 `mapping[rid] in (None,"")` 视为保留（与 summary 一致）；B）summary 中同样丢弃空归属并在 header 注“不含无归属”。合成复现：69 行库 summary total=68（含孤儿、不含无归属空串），preview total=69（含两者）。
- P1-② 无归属空串 header vs 预览不一致：`current_path=""` 且 `pik=""` 的源之 run，summary/列表均丢（空串非 None），但 `_clear_plan` 纳入 `unatt_srcs` 并计入 preview total/待删（`app/server.py:1270-1290`）。后果：列表头 N 与“将删 DB N 条”在退化库下差 1（合成 68 vs 69）。改法：header 或预览任一侧加注“（含无归属 X 条）”，或全清预览单列 `unatt/orphan/null_arch` 行；QA 67 正常库无此行不拦。
- P1-③ 停后即清与收尾 worker 竞态（本次 diff 顺带改 `_handle_stop_post` 不再立即清 current，`app/server.py:2779-2790`）：`_handle_clear_post` 实清只拦 `_listener.running`，不拦 `_worker.current finishing`。停后收尾中立即清可删正在收尾 run 的行+jobs。改法：实清前若 `current.run_id` 在待删集则 409 人话“当前这个正在收尾，稍等收尾完再清”，或文档化“停后等 current 清空再清”并由前端在 finishing 时 disable 清空入口。QA 覆盖“停→即清”用例。

## P2 / P3 Backlog Findings

- P2-① 截断文案归因偏 limit：`collect()` 为全局 `ORDER BY updated_at LIMIT N` 后再按 input 过滤（`src/stage12/status_snapshot.py:123-128` + `app/server.py:1992-2003`），多 input 共库时 shown 缺口部分来自过滤而非 limit，但文案一律写“每次最多取 N 条”。改法：文案加“（按当前文件夹过滤后）”或将过滤下推到 SQL（src 零碰约束下建议仅改文案）。
- P2-② 预览未单列 NULL archive 行数：`preview{db_runs,jobs}` 不含 `null_arch_ids` 计数，全清时会带走 NULL archive（`app/server.py:3031-3037`）。改法：preview 加 `null_archive:N` 一行（只清失败恒 0 已分开处理，好）。
- P2-③ 只清失败无二次 confirm（全部清空有）：误删仍不可逆。改法：只清失败也加一次 confirm（文案区分“仅删失败 N 条，成功保留”）。
- P2-④ 本次 diff 捎带非 P0 范围（`_handle_stop_post` 收尾语义、`_note_user_edited` P1-4、`_attach_source_filenames` 归属列、`default_data_root` 回显）：功能上 fail-open、未破 P0，但 scope 膨胀。改法：下次按“P0 单独 diff”提交，或在 HANDOFF 注一句跳 planner/product 的原因（本次即记一句：单批 P0 顺手带 P1 小修）。
- P2-⑤ `USER_MODEL_OVERRIDE.md` 本地改动为治理表同步（与模板包真源对齐），非 builder 业务改动，不计入本次结论；HANDOFF/账本按真源:28 记调用行/回执即可。
- P3-① `renderRunsHead` 在无 `run_summary` 时回退显示“共 shown/显示 shown”（`app/index.html:450-454`），属 fail-open，可保留；建议 QA 覆盖 snap.ok=False 时 header 隐藏不断链。
