
# CODE REVIEW

- Task: 复核src/stage12/（对照STAGE12-PLAN + 只读门/动作面仅Refresh-Quit/rumps可选/零DB写）
- Commit: n/a（工作区无 git，核对对象为 src/stage12/ 四文件现状：__init__.py / status_snapshot.py / status_cli.py / menu_bar.py）
- Reviewer: code-reviewer（opencode-go/glm-5.3-flash）
- Result: 过（P0 全过；无 P1；P2×6 记 backlog 不卡关；本复核独立静态 + 外置合成实测）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## P0 / P1 Findings

- P0 全过。本轮硬门逐项通过，证据如下（本机独立实测于 /tmp/s12cr_* + /tmp/s12cr2_* + /tmp/s12cr3_* + /tmp/s12wal_*，外置合成、最大文件仅 SQLite 合成库无视频文件；`python3 -m py_compile src/stage12/*.py` 通过）：
  - P0-1 只读状态快照（S12-T01）：`status_snapshot.py:159-206` `collect(data_root, limit=5)` 返回 `{ok, counts_by_state, recent_runs, error_count, collected_at}`，失败返回 `{ok:false, code, message, collected_at}`（`DB_MISSING/DB_UNREADABLE/DB_SCHEMA_MISMATCH`）。`_connect_ro:86-96` `sqlite3.connect("file:…?mode=ro", uri=True)` + `PRAGMA query_only=ON`，永不建库（缺库先 `isfile` 判 `DB_MISSING`）。`_collect_open:108-156` GROUP BY 实查五表（至少含 sources/processing_runs，缺核心表即 `DB_SCHEMA_MISMATCH`），`recent_runs` 按 `updated_at DESC, created_at DESC LIMIT ?`（参数绑定，含 run_id/source_id/status/updated_at + 附带 created_at），`error_count` 逐字冻结定义（processing_runs `LIKE 'FAILED%' OR LIKE 'BLOCKED%'` + artifacts 同口径）。本机合成库复算一致（sources DONE/READY 各1、runs COMPLETED/FAILED_ASR/BLOCKED 各1、artifacts FAILED_FETCH/READY 各1 → error=3），顺序 `r3>r2>r1`、`LIMIT 2 → r3,r2`，空库五表 `{}` + error 0，坏库/缺库/无核心表均结构化无 Traceback，DB mtime/sha 前后不变（含 WAL 模式：mtime 稳、目录无新增文件）。注：直连 sqlite3 RO 未走 `stage2.store.open_db(require_lock_held=False)`，符合 T01 明示替代（`mode=ro 或等价只读语义`），且严格更优——`open_db` 即使传 False 仍 `PRAGMA journal_mode=WAL`（写柄），本实现零 WAL 写。
  - P0-2 CLI status + stdlib 菜单（S12-T02）：`status_cli.py:82-92` `run_status` json 与 P0-1 同构、text 三段人读（counts/recent/errors），成功 exit 0、缺库/坏库 exit 2 + 结构化 stderr（本机 json/text/missing 三路径已证，无 Traceback）。`run_menu:95-118` stdlib `input()` 循环仅 `show/refresh/quit`（1/show 与 2/refresh 同为重读快照，3/quit/q 退，未知回环，EOF/KeyboardInterrupt exit 0）。全文件 `rumps` 零出现（AST import 全量核 + 全文 grep），无 rumps 环境全绿。
  - P0-3 rumps 可选 Menu Bar（S12-T03）：`menu_bar.py:25-31` 顶层 try-import + `RUMPS_AVAILABLE` 旗。`build_title:44-52` 同口径三数（sources 总数/R 总数/error_count，`V2O S:%d R:%d E:%d` 属计划允许等价三段，字符集以实现为准）；`build_lines:55-83` 同口径三段只读文本；有 rumps 时 `V2OApp:88-114` 标题 + 只读下拉（`callback=None`）+ 仅 `Refresh`（重读快照）/`Quit`（退菜单），`MenuItem("…")` 字面仅 Refresh/Quit 两项已证；mock rumps 重载实测标题 `V2O S:1 R:1 E:0`、尾两项 Refresh/Quit、refresh 重读 OK。无 rumps 时 `main:134-162` 打印 stdlib CLI 指引 exit 0（本机 `RUMPS_AVAILABLE=False` 下 exit 0 已证），不崩溃不安装。`rg "pip install|subprocess.*pip|os\.system" src/stage12/` 零命中。
  - P0-4 STOP EXPANSION 门：`rg -i "launchagent|level_a|level_b|commit_archive|run_asr_single_file|openai|anthropic|requests\.|llm|summar|polish|paraphras|rewrite|force|overwrite|clobber|reprocess" src/stage12/` 零命中；`rg "INSERT|UPDATE|DELETE" src/stage12/` 零命中；`rg "CREATE TABLE|ALTER TABLE|DROP TABLE|init_db|get_or_create" src/stage12/` 零命中（仅表名字符串与注释）；`rg -i "start|stop|retry|pause|discover"` 仅命中 `discovery_candidates` 表名常量，无控制动词；import 面仅 stdlib + `stage2.store.central_db_path` 纯路径复用（`status_snapshot.py:79` 函数内 try-import，失败回退本地 join）+ `stage12.status_snapshot.collect`，无 LaunchAgent/Archive 写入口/Whisper/LLM/云/SDK；文件名仅 `__init__/status_snapshot/status_cli/menu_bar`，无禁入关键词；`src/stage1-11/` diff 门：工作区无 git，静态替代——stage12 内无任何写盘路径指向 `src/stage1-11/`（全文 `open(` 零命中生产写，`rg stage1|stage3…stage11` 仅注释/模块名），文件级 diff 留 QA 在有基线环境补断言。
  - P0-5 外置合成门：属 QA 执行域；代码侧读写目标全由调用方传入 root 决定，无真实视频/笔记/Archive/LaunchAgents 字面路径，无网络/转写引擎 import，无 `--menu` 外控制入口。
- P1：无。本轮未发现须打回的阻塞缺陷。

## P2 / P3 Backlog Findings

- P2-1 `status_cli.render_text:35-62` 与 `menu_bar.build_lines:55-83` 三段渲染逻辑重复约 15 行（当前输出一致已证）。改法：抽共享 `format_lines(snapshot)->list` 供两处复用，或文档注明以 snapshot 同构为准、QA 加一致性断言。
- P2-2 `status_snapshot.py:99-100` `_norm_status` NULL→"NULL" 分支在 Stage2 DDL 下不可达（sources/processing_runs/artifacts.status 均为 NOT NULL，本机 NULL 插入即 `IntegrityError`）。防御无害。改法：保留亦可，或加注“历史/外部库防御分支”。
- P2-3 标题字符集为 ASCII `S/R/E`（`menu_bar.py:48`），计划允许等价三段但示例为 emoji。改法：保持现状可，产品侧若要 emoji 标题须同步更新 `build_title` 断言，不单独返工。
- P2-4 全包 `sys.path.insert(0,…/src)`（`status_snapshot/status_cli/menu_bar`）。沿 stage1-11 既有模式，不改；仅记一笔。
- P2-5 空表返回 `{}` 而非显式零值（如 `{"sources":{}}`）。GROUP BY 语义正确（求和即 0），但“空库 counts 全 0”需按求和解读。改法：文档注明空即零，或 QA 断言用 `sum(states.values())==0` 而非键相等。
- P2-6 `collect(limit)` 无上界（本机 100000 直通）。数据量 trivial（runs 表行数级），不卡关。改法：如产品侧担心超大 LIMIT，加 `min(n, 1000)` cap 并记 HANDOFF，或保持现状。
- P3：无。
