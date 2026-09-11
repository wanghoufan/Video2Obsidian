# QA-REPORT｜Stage12 S12-T04 快照复算+CLI exit+菜单动作面+DB只读（Video2Obsidian V1.8 §69）

- QA：qa（opencode-go/glm-5.3-flash，本窗口 subagent；未改业务代码，只写本报告）
- 被测：`src/stage12/`（`status_snapshot.py/status_cli.py/menu_bar.py/__init__.py`）+ `src/stage2/store.py` 只读复用（`central_db_path` 纯寻址 + DDL 口径）
- 计划：`docs/pm/STAGE12-PLAN.md` S12-T04（P0-1~P0-4；happy 1 遍 + 异常/边界 7 个；外置合成 Data Root；合成小文件；坏例只看 exit 码；结论只落本报告）
- 输入：`src/stage12/` 落盘 4 文件 + 上轮 builder 自验入口缺失（根 HANDOFF 仍停 Stage2 CLOSED，`docs/review/` 无 STAGE12 复核报告；QA 按 S12-T04 口径独立合成，未发现 plan/qa 口径分叉）
- QA 执行目录（仓库外）：`/var/folders/mp/mnxk3h8x4wq5ztr7__vlplp40000gn/T/opencode/s12qa-z5hpv84s/`（`happy_data/empty_data/bad_data/schem_data/nodir_xyz` 各独立 data_root；确定性合成行，无合成媒体文件，最大非 DB 文件 0B；诱饵 canonical 不适用本 Stage，未建；仓库内零写盘除本报告）
- **结论：PASS（happy 快照 GROUP BY 实查一致 + recent 顺序/LIMIT + error 可复算 + CLI json/text/menu 全绿 + rumps 有/无双路径 + 异常/边界 7 个全过 + DB mtime/sha 不变 + STOP 三 rg 零命中；坏例只看 exit 码：缺库/坏库 CLI exit 2 符合预期；最大合成文件 0B；真实目录零触碰；结论只落本报告）**

## 1. 输入复核（src/stage12 落盘 4 文件，只读消费 + 黑盒调用）

- `status_snapshot.py`（S12-T01）：`collect(data_root, limit=5)` 成功返回 `{ok,counts_by_state,recent_runs,error_count,collected_at}`，缺库/坏库返回 `{ok:false,code,message,collected_at}`；只读 URI `file:...?mode=ro` + `PRAGMA query_only=ON`，经 `stage2.store.central_db_path` 纯寻址（`store.py` 读到 `require_lock_held` 存在）；聚合冻结口径逐字落地（GROUP BY 五表 + recent `ORDER BY updated_at DESC, created_at DESC LIMIT N` + error `processing_runs LIKE FAILED/BLOCKED + artifacts 同口径`）。QA 实测：见§2。
- `status_cli.py`（S12-T02）：`status [--data-root R] [--format json|text] [--limit N]` + `menu`/`--menu`（stdlib `input()` 循环 show/refresh/quit 三项）；成功 exit 0，缺库/坏库 exit 2 + 结构化 stderr；全程不 import rumps。QA 实测：见§2。
- `menu_bar.py`（S12-T03）：顶层 `try: import rumps / except ImportError: RUMPS_AVAILABLE=False`；有则标题 `V2O S:%d R:%d E:%d` + 只读下拉 + 仅 Refresh/Quit 动作；无则 `main()` 打印 CLI 指引 exit 0。QA 实测：无 rumps 真环境降级 exit 0 + mock rumps 下拉同口径 + 动作面仅 Refresh/Quit。
- 上轮 builder 口径：HANDOFF 未登记 Stage12 builder 自验计数值；`docs/review/` 无 STAGE12 复核报告；QA 独立合成覆盖 happy/异常/STOP/回归探针。

## 2. 用例简表（坏例只看 exit 码）

| 用例 | 前置 | 动作 | 期望 | 实测 | exit 码 / Count |
|---|---|---|---|---|---|
| HAPPY 快照复算 | 合成库（sources 3 行 READY×2/ARCHIVED×1 + runs 6 行 QUEUED/COMPLETED×2/FAILED_RETRYABLE/BLOCKED_SOURCE_CHANGED/FAILED_HARD + artifacts 3 行 READY×2/FAILED_VERIFY + candidates 1 + commits 1） | `collect(limit=5)` vs 直连 GROUP BY | counts 五表逐值等 + recent 5 顺序等 + error 4 可复算 | 一致（counts_match True；recent `[r6,r5,r4,r3,r2]`；error runs 3 + art 1 = 4） | —（函数 verdict PASS） |
| P0-1 DB 只读 | 同上 + mtime/sha 快照 | `collect`×2 后比对 | mtime 不变 + sha 不变 + `rg INSERT/UPDATE/DELETE` 零命中 | 一致（mtime True；sha True；rg rc=1） | rg rc=**1** |
| P0-2 CLI json | 同上 | `status --format json --limit 5` | exit 0 + json 同构 + recent 5 + error 4 | 一致 | exit **0** |
| P0-2 CLI text | 同上 | `status --format text` | exit 0 + 三段（counts/recent/errors） | 一致（state counts/recent runs/error count 全含） | exit **0** |
| P0-2 菜单 | 同上 | `menu` 喂 `1/2/3` + `9/3` | show/refresh 打印快照 + quit exit 0 + 坏选项提示 | 一致（prompt 有；quit 0；unknown 有） | exit **0** |
| P0-3 降级（无 rumps） | 同上（本机无 rumps 已证 `ModuleNotFoundError`） | `menu_bar.main` + 子进程 `-m stage12.menu_bar` | exit 0 + CLI 指引 + 不崩溃 | 一致（指引含 `status_cli`；stderr 空） | exit **0** |
| P0-3 有 rumps（mock） | 同上 + fake rumps 注入 | `V2OApp` 下拉 + Refresh | 标题 `V2O S:3 R:6 E:4` + 下拉三段同口径 + 动作仅 Refresh/Quit | 一致（actionable 恰 `[Refresh,Quit]`；refresh 后标题等） | —（函数 verdict PASS） |
| B-1 空库 | 新空 DDL 库 | `collect` | ok 真 + error 0 + recent 空 | 一致 | —（verdict PASS） |
| B-2 缺库 | 不存在目录 | `collect` + CLI | `{ok:false,code:DB_MISSING}` + CLI exit 2 + stderr 结构化 | 一致 | CLI exit **2** |
| B-3 坏库 | 非 sqlite 字节文件 | `collect` + CLI | `{ok:false,code:DB_UNREADABLE}` + CLI exit 2 | 一致 | CLI exit **2** |
| B-4 schema 缺核 | 仅 `foo` 表库 | `collect` | `{ok:false,code:DB_SCHEMA_MISMATCH}` | 一致 | —（verdict PASS） |
| B-5 LIMIT | happy 库 | `collect(limit=2)` | `[r6,r5]` | 一致 | —（verdict PASS） |
| STOP 门 | 全量 stage12 | 三 rg + 只读审计 + DDL 对比 | SQL 零命中 + pip 零命中 + banned 零命中 + rumps 不漏进 cli/snapshot + 无新表 + 无 `init_db/discover建Run` 柄 | 一致（三 rg rc=1；`mode=ro+query_only` 有；表 9/9 等；`discover` 仅表名 `discovery_candidates`，无动作柄） | rg rc=**1** |
| REG 十二行 | 外置合成 | stage1~12 import | 12/12 可导 | 12/12 OK | exit 0 |

Runner：本报告内直跑复验（`collect` 黑盒 + `status_cli` 子进程取 exit 码 + `menu_bar` 真降级/mock 双路径 + 三 rg）；最大合成文件 0B（纯合成行，无媒体文件；上限合成小文件门内；真实长视频零触碰；文本/ASR 内容不断言）；Whisper 不适用（本 Stage 无转写链）；`archive_commits` 仅合成预置 1 行（QA 自建，非业务写）；诱饵 canonical 不适用（本 Stage 不写不断言，仅零触碰）；真实视频/Obsidian/Archive/LaunchAgents 目录零触碰（输入全在外置 `s12qa-*`）。

## 3. 每用例明细（前置/动作/期望；exit 码 + DB 快照 + 外置路径）

- HAPPY：前置外置 `happy_data` + Stage2 DDL + 上表合成行（`asr_profile_hash` 逐行 distinct，避 `ux_auto_processing_run` 部分唯一）；动作 `collect(limit=5)` + 直连 `GROUP BY/ORDER BY/LIKE` 三复算；期望 counts 五表逐值等 + recent 5 顺序等 + error 4；实测全中（SNAP `counts_by_state` 含 sources/processing_runs/artifacts/discovery_candidates/archive_commits + recent `[r6..r2]` + `collected_at` ISO Z）。
- P0-1：前置同上 + `stat/sha256` 前快照；动作 `collect`×2；期望 mtime/sha 不变 + `rg "INSERT|UPDATE|DELETE" src/stage12/` rc=1；实测全中（`sqlite3.connect uri mode=ro` + `query_only=ON` 代码举证；`central_db_path` 仅寻址，无 `init_db/acquire` 柄）。
- P0-2：前置同上；动作三子进程（json/text/缺库/坏库）+ `menu` 双喂；期望 json 同构/text 三段/menu 三项/exit 语义（好 0/坏 2）；实测全中（json `recent_n=5 error=4`；text 三段全含；menu `1→show 2→refresh 3→quit` + `9→unknown`；缺库 stderr `{ok:false,code:DB_MISSING}`；坏库 stderr `{ok:false,code:DB_UNREADABLE}`；`rg rumps status_cli/snapshot` rc=1）。
- P0-3：前置同上；动作真环境（无 rumps）`main()` + 子进程 + mock rumps `V2OApp`；期望降级 exit 0 + 指引含 `status_cli` + mock 标题/下拉同口径 + 动作仅 Refresh/Quit；实测全中（真降级 stdout 指引 + stderr 空；mock 下拉 24 行 + `build_title V2O S:3 R:6 E:4` + `_on_refresh` 重读等；`rg "pip install|subprocess.*pip|os.system"` rc=1）。
- B-1~B-5：前置各独立外置 root；动作见表；期望见表；实测全中（空库 `error 0 recent []`；缺库 `DB_MISSING`；坏库 `DB_UNREADABLE file is not a database`；schema `DB_SCHEMA_MISMATCH`；LIMIT `[r6,r5]`；坏例判据只用 exit 码/结构化 code，不看打印）。
- STOP：动作三 rg + import 审计 + DDL 表对比；期望 banned（`launchagent|level_a|level_b|commit_archive|run_asr_single_file|openai|anthropic|requests\.|llm|summar|polish|paraphras|rewrite|force|overwrite|clobber|reprocess`）rc=1 + SQL rc=1 + pip rc=1 + `status/refresh/quit/menu/snapshot` 合法词不误杀 + 表 9/9 无新增 + `py_compile` 过；实测全中（`discover` 命中仅 `discovery_candidates` 表名，CLI/菜单无 discover 动作柄；`open_db(require_lock_held=False)` 未被 stage12 直调写柄，仅 doc 提及只读语义）。
- REG：动作 `import stage1..stage12`；期望 12/12 可导；实测全中（`src/stage1-11/` 本轮 QA 未触碰；git 非仓库口径见 U-5）。

## BUGS（照 BUGS.template.md；本轮无 P0/P1）

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| 无（业务侧） | — | 否 | happy 复算一致；坏例缺库/坏库 exit 2 符合预期 | CLOSED | 无需 builder 修 | `collect` + CLI 子进程 + 真降级/mock 双路径黑盒直跑 |

## Fix Attempt Fingerprint

- Task ID: S12-T04 Stage12 验收套件（快照复算+CLI exit+菜单动作面+DB只读；首轮 QA 执行，业务零修）
- Root Cause Hypothesis: 不适用（业务 PASS；同轮内 QA 自修 1 处：合成 runs 撞 `ux_auto_processing_run` 部分唯一，改逐行 distinct hash 后一致）
- Approach: 外置独立 data_root（happy/empty/bad/schem/missing）+ Stage2 DDL 确定性合成行；Count/顺序/LIKE 直连复算为正常路径判据；缺库/坏库/schema/LIMIT 走 `collect` 真路径（code 断言）+ CLI 子进程只看 exit 码（好 0/坏 2）；菜单双喂 show/refresh/quit；rumps 真降级 + mock 有包双路径；STOP 三 rg + 只读审计 + DDL 表对比；回归十二 import 探针
- Files Changed: 仅新增本报告 `docs/qa/STAGE12-QA-REPORT.md`；业务代码零改；测试写盘只在 `/var/folders/.../T/opencode/s12qa-z5hpv84s/`（KB 级，交 neat-freak 收尾）
- Verification: counts/recent/error 三复算 True；mtime/sha True；CLI json/text/menu exit 0，缺库/坏库 exit 2；降级 exit 0；mock 动作仅 Refresh/Quit；三 rg rc=1；`py_compile` 过；回归 12/12
- Failure Reason: 无 FAIL 项（业务侧）
- Difference From Previous Attempt: 首轮，无上一轮（同轮内 QA 自修 1 处：hash distinct）

## 未闭环清单（交 supervisor/product-reviewer 定，不卡本 PASS）

- U-1 真实长视频未测（PLAN 已定：真实长视频一律不测直到产品完成；本套件最大合成文件 0B；文本/ASR 内容不断言）。
- U-2 文本/词准确率/Golden/CER/幻觉指标 Out（PLAN 已定；本报告仅验计数/顺序/error/exit 码/只读）。
- U-3 诱饵 canonical 未建（本 Stage 不写不断言；零触碰成立，无“存在且不变”快照可附）。
- U-4 残留待清：`/var/folders/.../T/opencode/s12qa-z5hpv84s/`（本轮新增，KB 级）+ 更早 Stage 残留（Stage11 U-4 所列），交 neat-freak 收尾。
- U-5 `src/stage1-11/ git diff 为空`口径 N/A（当前目录非 git 仓库；以 QA 零改 + 回归十二 import PASS + 三 rg 零命中代证；同 Stage10/11 U-5 Pattern）。
- U-6 rumps 有包路径为 mock 举证（本机无 rumps；`try-import + RUMPS_AVAILABLE` 旗 + 真降级 exit 0 已证；若需真机常驻，装 rumps 后重跑 mock 节即可）。
- U-7 HANDOFF/复核滞后：根 HANDOFF 仍停 Stage2 CLOSED，未登记 Stage12 builder 自验入口；`docs/review/` 无 STAGE12 复核报告；本报告输入复核以 `src/stage12/` 落盘 4 文件 + PLAN S12-T04 为准，基线缺失不卡 QA（已独立覆盖）。

---
目标：Stage12验收S12-T04｜剩 P0：无（QA 口径 PASS；闭环判定以 supervisor 复检为准）｜下一步：交 product-reviewer 验＋supervisor 复检（HANDOFF 只记状态，不代写结论）。
