# PLAN｜Stage 12 Menu Bar（可选，只读状态显示）（Video2Obsidian V1.8 §69）

> 基线：`docs/2026-09-10 丨 MAC 丨 GPT 网页端 丨 Video2Obsidian 本地视频自动转写工具开发计划-交接上下文 丨 V1.8.md`
> 基线状态：`V1.8 ARCHITECTURE FROZEN`（§71）+ Stage1~Stage11 实现已落盘（`src/stage1/` 单视频 Raw 闭环 + Repair Forward + `src/stage2/` Candidate/Source/AUTO Run + 中央 `<data_root>/data/state.db` + Single Instance + `src/stage3/` Revision 链 + `src/stage4/` Initial Canonical Publish + Ownership + `src/stage5/` Watch/Scan/Reconcile 到 RUNNING（§62 11 步装配）+ `src/stage6/` Path Mirror + `src/stage7/` Vocabulary/Prompt/Language + 单文件接线 + `src/stage8/` VAD advisory + ChunkPlanner（10min/2s）+ Absolute Timeline + Overlap Merge + `src/stage9/` 新版 Correction 规则表 + 新版 Paragraph formatter + `src/stage10/` Archive A/B/C + Strong Verify（§26）+ G3 落地 + Source 四列更新 + `src/stage11/` LaunchAgent plist（测试目录）+ Cold Boot + §67 Crash 矩阵 + Fault Injection 全套件；Menu Bar 未实现）。
> Stage1~Stage11 冻结输入：`src/stage1/`（`run_asr_single_file` + `recovery.py` Repair Forward，只读复用）与 `src/stage2/`（`candidate.discover` 唯一发现入口 + `runs.get_or_create_auto_run` UPSERT + `instance.py` 单实例锁 + `store.py` 中央库 DDL + `open_db(require_lock_held=False)` 只读诊断口，只读复用）与 `src/stage3/`（Revision 链公开 API，只读复用）与 `src/stage4/`（`initial_publish` + Ownership + `conflict` 用户编辑优先，只读复用）与 `src/stage5/`（`startup.py` §62 全序装配，只读复用不复制）与 `src/stage6/`（`resolve_canonical` 纯映射，只读复用）与 `src/stage7/`（vocab/prompt/language，只读复用）与 `src/stage8/`（VAD/Chunk/Timeline/Merge，只读复用）与 `src/stage9/`（`rules_v2`/`formatter_v2`，只读复用）与 `src/stage10/`（`verify_archive`/`level_a`/`level_b`/`level_c`/`gate`/`commit`，只读复用；恒经 `gate` 调用，`expected_hash` 必填）与 `src/stage11/`（`launch_plist`/`agent_boot`/`reliability`/`fault_suite`，只读复用，不重实现）——本 Stage 只做加法，不改 `src/stage1/` ~ `src/stage11/` 任一文件（改了即 FAIL；新增只进 `src/stage12/`）。
> 最高约束：`STOP ARCHITECTURE EXPANSION`（§65-71）+ `STOP EXPANSION（Stage12 only）`——本 Stage 只实现 §69 Stage12 定义的事项（Menu Bar 可选、核心稳定后：最小可用只读状态显示），无控制动作、无 Reprocess UI；§2.2 禁止项（LLM/云/总结改写润色）出现即 FAIL；永不覆盖用户笔记、永不误删源（模块内出现 `force|overwrite|clobber` 即 FAIL）；中央库零写（`src/stage12/` 内出现 `INSERT|UPDATE|DELETE` 即 FAIL）；不新增表/列（DDL 快照对比）。

## Product Goal

Video2Obsidian 是一个运行在 Apple Silicon Mac 上的零 API 成本、本地常驻视频知识入库工具：用户只需要把视频放入已经分类好的本地文件夹，系统自动完成本地 Whisper 转写、专业词增强、自然分段、目录镜像、Obsidian Markdown 安全写入和源视频安全归档（V1.8 §1.2）。目标设备：Mac mini M4 / 24GB RAM。本 Stage 只做其中“可选可见性”的那一块：在 Stage2 中央库与 Stage1~11 状态语义之上，提供最小可用 Menu Bar 状态显示——只读聚合中央库/SQLite 状态（counts by state + 最近 Run + 错误计数），无任何控制动作、无 Reprocess UI；macOS `rumps` 仅为可选依赖（try-import，缺失即干净降级），不新增重依赖时用 stdlib 降级为 CLI status 命令 + 可选文本菜单；Stage1~11 回归（`src/stage1-11/` diff 为空）。

## Current Stage

- Stage ID: Stage 12 — Menu Bar，可选（V1.8 §69）
- Goal: 只读状态快照可证明（sources / processing_runs 按 status 聚合计数 + 最近 Run N 条 + 错误计数，中央库零写）→ CLI `status` 命令可证明（stdlib，无 rumps 也可用；json/text 输出）→ rumps Menu Bar 可选显示可证明（有 rumps 则显示同口径状态；无 rumps 则干净降级为 CLI 指引，不崩溃、不 pip 安装）→ 外置合成验收全绿 → Stage1~11 回归（`src/stage1-11/` diff 为空）。

Stage1~Stage11 地基复用约定（加法约束）：
```text
src/stage1/ 零调用（回归只读查；Repair Forward 语义只读引用，不触发）
src/stage2/ 只读复用（import，不复制不修改）：store.open_db(data_root,
  require_lock_held=False) 只读诊断口 / central_db_path 寻址
  （Stage12 永不持锁写、不 init_db、不 discover、不建 Run）
src/stage3/~stage11/ 零调用（回归只读查；状态语义只读引用，不重实现）
src/stage12/ 新增：status_snapshot.py（只读聚合）/ status_cli.py（CLI
  status 命令 + 可选文本菜单）/ menu_bar.py（rumps 可选显示）
  （命名以实现为准，前缀恒为 stage12，禁止 launchagent/archive/
  golden/reprocess 关键词文件名）
中央库位置：<data_root>/data/state.db（沿用 Stage2；本 Stage 不新增表/列、
  不写任何行；读只经 require_lock_held=False 的只读连接，缺库时报结构化
  错误不崩溃；DB mtime 前后不变为硬门）
聚合口径（GROUP BY，不硬编码枚举——各 Stage 状态 heterogeneous）：
  counts_by_state = 各表 status 分组计数（sources / processing_runs /
  artifacts / discovery_candidates / archive_commits，至少含前两表）
  recent_runs = processing_runs 按 updated_at/created_at DESC LIMIT N
  （默认 5，含 run_id/source_id/status/updated_at）
  error_count = processing_runs 中 status LIKE 'FAILED%' OR status LIKE
  'BLOCKED%' 之和 + artifacts 同口径之和（定义冻结，实现逐字举证）
输入源视频：外置合成小文件（仓库外独立合成 Input Root；ffmpeg 本地合成秒级
  mp4/wav，不扫真实视频目录；长视频不测，用例最大文件 ≤ 合成小文件；
  文本/ASR 内容不断言，词准确率/Golden/CER/幻觉指标属 Stage12 Out）
诱饵 canonical：外置合成目录内诱饵 md（本 Stage 不写 canonical，不断言内容，
  仅“存在且不变”快照举证；零触碰真实笔记）
```

## Stage P0（P0=本 Stage 非做不可、缺它不算完的事项，由 planner 初定、Task Manager 拍板；同时作为 qa / product-reviewer 的 P0 Blocking 参照。TM已拍板：按初定通过，本节即执行口径）

- [ ] P0-1 只读状态快照可证明（中央库/SQLite 只读聚合）：给定外置 Data Root（含 Stage2 DDL 的 `state.db` 合成库），`status_snapshot.collect(data_root)` 返回 `{counts_by_state, recent_runs, error_count, collected_at}` → counts 覆盖 sources/processing_runs（GROUP BY 实查一致）→ recent_runs 为最新 N 条（含 run_id/source_id/status/updated_at，顺序可证）→ error_count 按冻结定义可复算 → 全程中央库零写（DB 文件 mtime/sha 前后不变 + `rg "INSERT|UPDATE|DELETE" src/stage12/` 零命中举证）→ 缺库/坏库报结构化错误（`{ok:false, code}`），不抛裸 Traceback、不建库、不修库。
- [ ] P0-2 CLI status 命令 + stdlib 可选菜单可证明（无 rumps 可用）：`status_cli` 以 stdlib `argparse` 提供 `status [--data-root R] [--format json|text] [--limit N]` → json 输出与 P0-1 同构、text 输出人可读三段（counts/recent/errors）→ exit 0（缺库时 exit 2 + 结构化 stderr，不崩溃）→ 可选文本菜单（stdlib `input()` 循环：show status / refresh / quit三项，无控制动作、无 reprocess 入口，出现即 FAIL）→ 全程不 import rumps（无 rumps 环境全绿）。
- [ ] P0-3 rumps 可选 Menu Bar 可证明（有则显示、无则降级）：`menu_bar.py` 顶层 `try: import rumps / except ImportError: RUMPS_AVAILABLE=False` → 有 rumps 时菜单标题行显示同口径摘要（如 `V2O ✅a ⚠️e ❌n` 或等价三段，字符集以实现为准）+ 下拉项为 P0-1 三段只读文本 + 仅 Refresh/Quit 动作（Refresh 只重读快照，Quit 只退菜单；任何 start/stop/retry/reprocess/discover 写动作出现即 FAIL）→ 无 rumps 时 `main()` 打印 CLI 指引并 exit 0（不崩溃、不 pip install、不提示安装）→ `rg "pip install|subprocess.*pip|os\.system" src/stage12/` 零命中举证。
- [ ] P0-4 STOP EXPANSION + 外置合成验收门可证明：`src/stage1/` ~ `src/stage11/` git diff 为空；中央库 DDL 快照对比无新增表/列；`src/stage12/` 永不 import LaunchAgent/Archive 写入口/Whisper 执行入口/LLM/云/SDK（`rg "launchagent|level_a|level_b|commit_archive|run_asr_single_file|openai|anthropic|requests\.|llm|summar|polish|paraphras|rewrite|force|overwrite|clobber|reprocess" src/stage12/` 零命中举证；`status/refresh/quit/menu/snapshot` 为本 Stage 合法词，不在禁入列）；一切输入位于外置合成目录 + 外置 Data Root 内（验收前断言，与真实视频目录/真实 Obsidian 库/真实 Archive 目录/真实 LaunchAgents 目录无交集）；用例最大文件 ≤ 合成小文件；真实长视频一律不测。

## In Scope

- 只读状态快照（counts by state + 最近 Run + 错误计数；GROUP BY 口径；冻结 error 定义；零写；缺库结构化错误）。
- CLI `status` 命令（stdlib argparse；json/text；exit 码语义；无 rumps 可用）。
- stdlib 可选文本菜单（show/refresh/quit；无控制动作）。
- rumps 可选 Menu Bar 显示（try-import；同口径摘要标题 + 只读下拉 + Refresh/Quit；无 rumps 干净降级）。
- 外置合成验收（happy 1 遍 + 异常/边界：空库 counts 全 0 / 缺库 exit 2 / 坏库结构化错 / 无 rumps 降级 / runs 含 FAILED/BLOCKED 时 error_count 可复算 / recent_runs 顺序与 LIMIT / DB mtime 不变）。
- §72 Implementation Acceptance Gate 中仅属于 Stage12 的断言子集：只读显示不断链（Stage1~11 回归不断链；`src/stage1-11/` diff 为空）。
- Stage1~11 回归（十一回归不断链；`src/stage1-11/` git diff 为空）。

## Out of Scope

- 任何控制动作：start/stop/retry/pause/discover/重投/删源/删库（出现写柄即 FAIL）。
- Reprocess UI（含 MANUAL_REPROCESS 入口、重跑按钮、任何“重新处理”文案对应的执行路径）。
- Golden Dataset / CER / 词准确率 / 幻觉与重复文本指标（文本内容不断言）。
- 长视频与真实长视频测试（用户明确：真实长视频一律不测直到产品完成；本 Stage 只用合成小文件）。
- LaunchAgent 安装/常驻/开机持久化（Stage11 已落地，本 Stage 只读引用，不碰 LaunchAgents 目录）。
- 转写/派生/发布/归档语义升级（Whisper/Normalization/Paragraph/Publish/Archive 只读引用；`publish_records`/`archive_commits` 非预期新增即 FAIL）。
- 任何 §2.2 禁止项：AI 总结/改写/润色/校稿、LLM、云端 ASR、任何云 API、Redis/PostgreSQL、微服务、Docker、消息队列、RAG/Embedding/向量库、复杂 UI、Obsidian 插件、SaaS/手机端/浏览器上传、iCloud File Coordination、新模型、自动覆盖用户笔记、复杂历史版本 UI。
- 新重依赖（rumps 仅 try-import 可选；`requirements`/安装脚本新增依赖即 FAIL；禁 pip install 逻辑）。
- 真实目录扫描/写入/真实 Obsidian 库/真实 Archive 目录/真实 LaunchAgents 触碰（测试一律指向合成 Input Root + 外置 Data Root）。
- 不改 `src/stage1/` ~ `src/stage11/`、不改 V1.8 架构基线、不动治理表（账本由执行链按 AGENTS 分工写，planner 不代写）、不 push、不碰 secrets。

## Task Breakdown

| Task ID | Priority | Role | Status | Notes |
|---|---|---|---|---|
| S12-T01 只读状态快照核心 | P0 | builder | TODO | 输入：stage2 `store` 只读口（`central_db_path` + `open_db(require_lock_held=False)`，只读复用，不 init/discover/建 Run）+ 冻结聚合口径（见 Current Stage）。输出：`src/stage12/status_snapshot.py`（`collect(data_root, limit=5)` 返回 `{counts_by_state, recent_runs, error_count, collected_at}`；只读连接：`sqlite3.connect("file:...?mode=ro", uri=True)` 或等价只读语义，缺库/坏库返回结构化 `{ok:false, code}`；零 `INSERT/UPDATE/DELETE`）。验收：合成库 GROUP BY 实查一致 + recent 顺序/LIMIT + error 可复算 + DB mtime/sha 前后不变 + 缺库坏库结构化错。禁动 `src/stage1-11/`；禁写柄；禁 rumps 依赖。 |
| S12-T02 CLI status 命令 + stdlib 可选菜单 | P0 | builder | TODO | 输入：S12-T01 的 `collect`。输出：`src/stage12/status_cli.py`（`status [--data-root R] [--format json\|text] [--limit N]`：json 同构输出/text 三段人读；缺库 exit 2 + 结构化 stderr；`menu` 子命令或 `--menu`：stdlib input 循环 show/refresh/quit，无控制动作）。验收：无 rumps 环境 json/text/menu 三路径全绿 + exit 码语义 + 全程不 import rumps。禁动 `src/stage1-11/`；禁控制动作/Reprocess 入口。 |
| S12-T03 rumps 可选 Menu Bar 显示 | P0 | builder | TODO | 输入：S12-T01 的 `collect`。输出：`src/stage12/menu_bar.py`（顶层 try-import rumps，`RUMPS_AVAILABLE` 旗；有则标题三段摘要 + 只读下拉 + Refresh（重读快照）/Quit（退菜单）；无则 `main()` 打印 CLI 指引 exit 0）。验收：有 rumps 时标题/下拉与 `collect` 同口径（mock rumps 或真机二选一举证，不强制真机常驻）+ 无 rumps 时降级 exit 0 + `pip install` 零出现 + 动作面仅 Refresh/Quit。禁动 `src/stage1-11/`；禁硬依赖 rumps；禁写动作。 |
| S12-T04 Stage12 验收套件 + Stage1~11 回归 | P0 | builder | TODO | 输入：S12-T01–T03 产物 + `src/stage1-11/` 只读复用。输出：Stage12 验收证据（happy 链 1 遍：合成库→快照→CLI json/text→菜单 show/refresh/quit→rumps 降级路径 + 异常/边界至少 7 个：空库全 0 / 缺库 exit 2 / 坏库结构化错 / 无 rumps 降级 exit 0 / FAILED/BLOCKED 混入 error 可复算 / recent 顺序+LIMIT / DB mtime 不变；每个用例：前置/动作/期望 verdict 或 exit 码/DB 快照证据/最大文件 ≤ 合成小文件声明/外置 Root 路径证据/真实目录零触碰证据；结论只落 builder 自证小节，正式结论留 qa 报告，HANDOFF 只记状态）+ 回归十一行（Stage1 per-job happy 仍 PASS；Stage2 discover→AUTO Run=1 仍 PASS；Stage3 冻结版规则链仍 PASS；Stage4 单文件 PUBLISHED 仍可查；Stage5 Ready→Scan→Reconcile→RUNNING 语义不断链；Stage6 嵌套 Unicode mirror 双算一致；Stage7 装配→接线→profile executed 仍 PASS；Stage8 合成 wav→VAD→planner→timeline→merge 仍 PASS；Stage9 Case 4/5 派生仍 PASS（Whisper 0/Raw 同/诱饵不变）；Stage10 Same-FS Archive + 四列更新仍 PASS（合成小文件，Whisper 0）；Stage11 plist 演练 + cold_boot RUNNING 仍 PASS（测试目录，演练后 unload 无残留）；`src/stage1-11/` git diff 为空）。验收：任一异常缺失、计数偏离、非预期表新增、DB 被写、诱饵被改、真实目录/真实库/真实 Archive/真实 LaunchAgents/云/长视频被碰、结论写进 HANDOFF 代报告，均为 FAIL。 |

- 并行性说明：S12-T01 → T02 → T03 → T04 严格串行（快照是 CLI 与菜单的前置；三件未就绪前验收无收口可查；builder 为主，全串行）。
- 角色说明：S12-T01–T04 = builder 实现 + 自证；code-reviewer / qa / product-reviewer / supervisor 按 AGENTS 派工顺序在计划完成后介入，本计划不代派。

## Risks

- R1 快照“顺手”写库：持锁 `open_db` 默认可写最省事但违反只读门。缓解：S12-T01 硬门——只读 URI/mode=ro + require_lock_held=False + DB mtime/sha 前后不变 + 写关键字 rg 零命中。
- R2 rumps 变硬依赖：`import rumps` 顶层直引最省事但无 rumps 环境即崩。缓解：S12-T03 硬门——try-import + `RUMPS_AVAILABLE` 旗 + 无 rumps 降级 exit 0 + pip 零出现审计。
- R3 只读显示滑向控制面板：Refresh 旁边加个 Reprocess 最“有用”但违反 TM 已定。缓解：P0-2/P0-3 硬门——动作面仅 show/refresh/quit，`reprocess` rg 零命中，任一写柄即 FAIL。
- R4 状态枚举硬编码：把 QUEUED/COMPLETED 写死最省事但各 Stage 状态 heterogeneous 会漏数。缓解：S12-T01 硬门——GROUP BY 实查 + 合成库复算一致，不许枚举断言。
- R5 为显示改 stage1-11 原文：改 store 加便捷函数最省事但违反加法约束。缓解：S12-T04 回归硬门——`src/stage1-11/` git diff 为空 + 只调公开只读口审计。
- R6 真实长视频/真实目录误测：拿真实库看一眼最“真实”但违反用户明确禁令。缓解：TM 已定——一律合成小文件 + 外置 Data Root；用例最大文件 ≤ 合成小文件写进报告 PASS 条件；文本内容不断言。

## Human Decisions Needed

- 无，按TM已定执行（本计划无阻塞项，不问人）。
- TM 已定事项备忘（执行，不复议）：① 最小可用只读 Menu Bar（counts by state + 最近 Run + 错误计数；无控制动作、无 Reprocess UI）；② macOS rumps 可选依赖（try-import 降级；不新增重依赖则 stdlib CLI status 命令 + 可选文本菜单）；③ 外置测试目录（仓库外独立 Data Root + 独立合成 Input Root，Stage1 `/tmp/s1t*` 与 Stage2 H2 外置目录模式延续；真实视频目录/真实 Obsidian 库/真实 Archive 目录/真实 LaunchAgents 目录零触碰）；④ 合成小文件（原片不动，只动副本；canonical 只用诱饵文件比对“存在且不变”，不碰真实笔记）；⑤ 真实长视频一律不测直到产品完成（用户明确，用例最大文件为合成小文件；词准确率/Golden/CER/幻觉指标属 Stage12 Out）；⑥ `src/stage1/` ~ `src/stage11/` 只读加法（新增只进 `src/stage12/`，diff 为空为硬门）；⑦ 中央库零写（不新增表/列；读只经只读连接；DB mtime 不变为硬门）。
