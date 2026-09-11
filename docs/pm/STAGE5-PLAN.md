# PLAN｜Stage 5 Watch First + Startup Scan + Reconciliation（Video2Obsidian V1.8 §69）

> 基线：`docs/2026-09-10 丨 MAC 丨 GPT 网页端 丨 Video2Obsidian 本地视频自动转写工具开发计划-交接上下文 丨 V1.8.md`
> 基线状态：`V1.8 ARCHITECTURE FROZEN`（§71）+ Stage1~Stage4 实现已落盘（`src/stage1/` 单视频 Raw 闭环 + `src/stage2/` Candidate/Source/AUTO Run + 中央 `<data_root>/data/state.db` + Single Instance + `src/stage3/` Revision 链 + `src/stage4/` Initial Canonical Publish；STAGE2-QA-REPORT 三路并发为三线程直调 `discover()` 模拟，未起真实 watchdog 线程）。
> Stage1+Stage2+Stage3+Stage4 冻结输入：`src/stage1/`（job-scoped `data/jobs/<job_id>/` + per-job `job.sqlite` + Raw PREPARE/COMMIT + Immutable + Repair Forward）与 `src/stage2/`（`candidate.discover(path, data_root, asr_profile_hash)` 直接 API + 两轮 size/mtime Stable 门 + `runs.get_or_create_auto_run` UPSERT + `reconcile_source/reconcile_run` §17/§18 收敛 + `instance.startup` §62 前五步 + `data/.lock` Single Instance）与 `src/stage3/`（Revision 链，RenderRev 止于 PUBLISH_EVALUATION）与 `src/stage4/`（Atomic No-Clobber Publish + Ownership）——本 Stage 只做加法，不改 `src/stage1/`、`src/stage2/`、`src/stage3/`、`src/stage4/` 任一文件（改了即 FAIL；新增只进 `src/stage5/`）。
> 最高约束：`STOP ARCHITECTURE EXPANSION`（§65-71）+ `STOP EXPANSION（Stage5 only）`——本 Stage 只实现 §69 Stage5 定义的事项（Watch First + Startup Scan + Reconciliation，§3.1/§5/§16/§17/§18/§19/§20 + §62 后半段 + §72 Discovery/Identity 与 AUTO Run 门 + §73 第 1/2/3/7/8 条），Stage6+（Path Mirror、Prompt/Vocab、VAD/Chunk、阈值调优、Archive A/B/C、`current_path` 更新、LaunchAgent、Menu Bar）一律 Out，写了即 FAIL。

## Product Goal

Video2Obsidian 是一个运行在 Apple Silicon Mac 上的零 API 成本、本地常驻视频知识入库工具：用户只需要把视频放入已经分类好的本地文件夹，系统自动完成本地 Whisper 转写、专业词增强、自然分段、目录镜像、Obsidian Markdown 安全写入和源视频安全归档（V1.8 §1.2）。目标设备：Mac mini M4 / 24GB RAM。本 Stage 只做其中“自动发现常驻”的那一块：在 Stage2 直接 API 发现（`discover()` + Stable 门 + 两层去重 + §62 前五步启动子集）之上，实现真实的三路发现——Watchdog 文件系统事件监听（Watch First）+ 启动时全量补扫（Startup Scan Second）+ 周期/初始对账补漏（Reconciliation Third），三路一律只做 At Least Once 投递（§3.1），经 `stage2.discover` / `reconcile_*` 只读复用收口为 Exactly Once（§3.2/§3.3），并按 §62 完整顺序装配到 RUNNING（程序停止期间加入的视频启动后补回 §73-2；Watchdog 漏事件由 Reconciliation 补回 §73-3）。

## Current Stage

- Stage ID: Stage5 — Watch First + Startup Scan + Reconciliation（V1.8 §69）
- Goal: Watchdog Observer 真实启动（watchdog 6.0.0 已锁定依赖，file-system event，只投递不直写 DB、不绕 Stable 门；Watcher Ready 确认门）→ Startup Scan（Watcher Ready 之后全量递归扫合成 Input Root，停机期间加入的视频补回）→ Reconciliation（Initial + Periodic：FS/DB 对账补漏 + `FAILED_RETRYABLE` 重试原 Run §17 + `NO_SPEECH_DETECTED` 返回既有 §18）→ 三路并发收口（Case 3 Triple Race：Source=1、AUTO Run=1 延续；Case 2 NO_SPEECH×10：Run=1）→ §62 完整 11 步启动装配（复用 `stage2.instance.startup` 前五步 → Start Watcher → Confirm Watcher Ready → Startup Scan → Initial Reconciliation → Start Workers(delivery-only) → RUNNING）→ §72 Discovery/Identity + AUTO Run 子集门可证明 → Stage1~4 回归（`src/stage1-4/` diff 为空，四表零新增写）。

Stage1~Stage4 地基复用约定（加法约束）：
```text
src/stage1/ 原样复用（import，不复制不修改）：sha256_file（Strong Hash 只读）/
  probe_volume（Root 门语义 §61/§3.14，Stage5 Input/Data Root 复用）
src/stage2/ 原样复用（import，不复制不修改）：candidate.discover（唯一发现入口，
  含 Stable 门 + Provisional Partial UNIQUE + Case 13 新 Source 语义）/
  runs.get_or_create_auto_run（AUTO UPSERT）/ runs.reconcile_source/reconcile_run
  （§17/§18 收敛）/ source.promote 的 UPSERT 语义（经 discover 间接）/
  instance.startup（§62 前五步：Static Preflight→Lock→Open SQLite→Volume
  Preflight→Recovery Bootstrap；Stage5 在其返回后继续后半段，不另起锁）/
  store.require_lock（Stage5一切写库操作持锁断言）
src/stage3/、src/stage4/ 零调用（Stage5 不产生 Revision、不发布、不回填 Run
  的 initial_publish_record_id；经 discover 间接建 Run 仅到 QUEUED/复用既有）
src/stage5/ 新增：watcher.py / scan.py / reconcile.py / startup.py
中央库位置：<data_root>/data/state.db（沿用 Stage2；Stage5 只写 discovery_candidates/
  sources/processing_runs/state_events，normalization_revisions/render_revisions/
  publish_records/archive_commits 行数不变，变即 FAIL）
输入目录：外置合成 Input Root（仓库外独立目录；watchdog 真实启动可用 file-system
  event，但测试一律指向合成目录，不扫真实视频目录）
asr_profile_hash：Stage0/Stage1 冻结值字符串透传（身份计算用，不解析不执行模型）
Stage5 全程 Whisper 调用恒为 0（转写执行不属本 Stage）
```

## Stage P0（P0=本 Stage 非做不可、缺它不算完的事项，由 planner 初定、Task Manager 拍板；同时作为 qa / product-reviewer 的 P0 Blocking 参照。TM已拍板：按初定通过，本节即执行口径）

- [ ] P0-1 Watch First 可证明（§2.1/§3.1 + §62 Start Watcher/Confirm Ready）：`watcher.py` 用 watchdog Observer 真实监听合成 Input Root（file-system event：created/moved/modified 关闭写后事件去抖）；事件处理器只做投递——调 `stage2.candidate.discover`，不直写 DB、不绕 Stable 门、不做路径级去重（At Least Once，重复投递合法）；`wait_ready()` 在 Scan 前返回 Ready（Ready 前的 Scan 启动即 FAIL；顺序 Watch First/Scan Second/Reconcile Third 倒置即 FAIL）；非视频后缀事件忽略（只收 `.mp4` 等约定的视频后缀，大小写不敏感，后缀表放模块常量）；stop() 幂等，Observer 线程可 join。
- [ ] P0-2 Startup Scan 可证明（§73-2 程序停止期间加入的视频启动后补回）：`scan.py` 在 Watcher Ready 之后对合成 Input Root 做全量递归扫描（任意层级 MP4 §73-1），逐个调 `discover()` 投递；停机用例：停机期间（Observer 未启动）向合成目录放入 N 个新视频 → 启动 → Scan 后 N 个全部 PROMOTED 且无丢失（Lost Job = 0）；Scan 不做自有去重（Case 13 历史碰撞语义由 `discover()` 保证，Scan 内出现“同 path 跳过”逻辑即 FAIL）；Scan 期间新到的文件由 Watcher 路径重复投递，收口仍为 Exactly Once。
- [ ] P0-3 Reconciliation 可证明（§73-3 漏事件补回 + §17/§18/§16）：`reconcile.py` 提供 `initial_reconcile()`（启动链用）与 `periodic_reconcile()`（漏事件补漏用）：对账 = 枚举合成 Input Root 现存视频 × 中央库 Source/Candidate 状态 → 缺失投递调 `discover()`，既有 AUTO Run 按 `runs.reconcile_source` 收敛（`FAILED_RETRYABLE` → 同一 `run_id`、`retry_count+1`、不建新 Run §17；`NO_SPEECH_DETECTED` → 返回既有终态、零新增 §18；`QUEUED` 原样返回）；模拟漏事件用例：停掉 Watcher 投递（只停投递函数，不动 Observer）后放入视频 → Periodic 一次即补回（Source/AUTO Run 正常建立）；Case 2：NO_SPEECH Run 上连调 10 次 periodic，Run Count 仍为 1。
- [ ] P0-4 Triple Discovery Race 延续可证明（Case 3 + §3.1/§3.2/§3.3/§19）：Watchdog 事件投递、Startup Scan、Reconciliation 三路并发投递同一合成视频（线程级真并发，至少 3 路 × 多次）→ `Logical Source Count = 1` 且 `AUTO Processing Run Count = 1`；判定经中央库 `COUNT(*)` 实查，任一偏离即 FAIL（Stage2 S2-T05 的直接 API Race 结论在本 Stage 由真实三路延续，不得回退为串行模拟）。
- [ ] P0-5 §62 完整启动顺序可证明（11 步有序 + Single Instance 复用）：`startup.py` 装配 `run_startup(data_root, input_root)`：Static Preflight → Acquire Single Instance Lock → Open SQLite → Runtime/Volume Preflight → Recovery Bootstrap（前五步复用 `stage2.instance`，不另起锁文件、不改锁语义，第二实例行为沿用 exit 3）→ Start Watcher → Confirm Watcher Ready → Startup Scan → Initial Reconciliation → Start Workers → RUNNING；每步记序可断言（返回 order 数组逐字 11 步），任一步倒置/跳步即 FAIL；Workers 为 delivery-only（有界线程消费三路投递队列调 `discover()`，不推进 Run 转写状态机、不调 Whisper、不写 Stage3+ 表，出现转写/发布/归档调用即 FAIL）。
- [ ] P0-6 §72 子集门可证明（仅属于 Stage5 的断言）：Watch First / Scan / Reconcile implementation PASS + Stable File Detection PASS（抖动文件仍 WAITING，门内 append 不提前 PROMOTED）+ Candidate Partial UNIQUE PASS + Historical Provisional Collision PASS（Case 13 经 Scan/Reconcile 路径仍建新 Source）+ Logical Source Exactly Once PASS + Triple Discovery Race PASS + AUTO Run Partial UNIQUE implementation PASS + Triple AUTO Count=1 + NO_SPEECH×10 Count=1 + FAILED_RETRYABLE 重试原 Run PASS。
- [ ] P0-7 STOP EXPANSION 门可证明：`src/stage1/`、`src/stage2/`、`src/stage3/`、`src/stage4/` git diff 为空；`normalization_revisions` / `render_revisions` 行数恒为 0 且 `publish_records` / `archive_commits` 行数相对 Stage5 运行前不变（有新增写即 FAIL；Stage5 运行前后由验收套件同一断言快照对比）；Stage5 代码永不 import/调用 Whisper 执行入口（`run_asr_single_file`）与 Stage3+ 写模块（`publish.py`/`conflict.py`/`archive`），测试以调用计数 = 0 与 grep 零命中举证；Path Mirror、Prompt/Vocab、VAD/Chunk、阈值调优、Archive A/B/C、`current_path` 更新、LaunchAgent、Menu Bar 任一出现即 FAIL。
- [ ] P0-8 外置合成验收门可证明（TM 已定）：一切输入路径位于外置合成 Input Root + 外置 Data Root 内（验收前断言，与真实视频目录/真实 Obsidian 库无交集）；异常路径一律合成副本（原片不动，只动副本）；真实长视频一律不测（用例最大文件 ≤ 合成小文件，作为 PASS 条件写进报告）；任一用例触碰真实目录即 FAIL。

## In Scope

- Watchdog 真实监听与 Ready 门（watchdog 已锁定 6.0.0，无新依赖；file-system event；只投递；去抖；stop 幂等）。
- Startup Scan 全量补扫（递归；停机加入补回；Lost Job = 0；无自有去重）。
- Reconciliation 对账补漏（Initial + Periodic；§17 重试原 Run；§18 终态返回；Case 2 ×10；漏事件补回）。
- 两层去重延续（§19：Candidate 层 MERGED + AUTO Run 层返回既有；Case 3 三路真并发 Source=1/Run=1）。
- §62 完整启动装配（前五步复用 stage2.instance；后六步新增；order 可断言；delivery-only Workers；RUNNING）。
- Stable File 门延续（复用 `discover()` 内两轮 size/mtime 门；抖动停留语义不变；fast metadata 只做信号 §3.5）。
- §72 Implementation Acceptance Gate 中仅属于 Stage5 的断言子集（见 P0-6）。
- Stage1~4 回归（Stage1 per-job happy 可复现；Stage2 discover→AUTO Run=1 链仍 PASS；Stage3 verdict 链仍 PASS；Stage4 PUBLISHED 行仍可查且行数不变；`src/stage1-4/` diff 为空）。

## Out of Scope

- Stage6 全部：Obsidian Path Mirror + Unicode/Case 完整故障套件（本 Stage `path_identity_key` 沿 Stage2 原样存，不做归一化比较矩阵；NFC/NFD/大小写真机套件不跑）。
- Stage7 全部：Prompt + Vocabulary + Language Strategy（`asr_profile_hash` 只做不透明身份字符串透传，不实现 Profile 内容语义）。
- Stage8 全部：VAD + Chunk + Absolute Timeline（不重切分、不重排时间线；转写执行本身亦不在本 Stage）。
- Stage9（阈值调优）：任何阈值调优不做（Stable 门两轮间隔沿 Stage2 常量，不调优）。
- Stage10 全部：Archive A/B/C + `current_path` 更新（`archive_commits` 零新增写；Source 行 `current_path`/`status`/`archived_at` 任一被写即 FAIL）。
- Stage11 全部：LaunchAgent + 完整 Fault Injection Suite（本 Stage 只做 P0 指定的漏事件/Race/停机补回/顺序单测；Cold Boot、Absolute Binary Paths 不做）。
- Stage12 全部：Menu Bar。
- 转写/改写/发布执行：Whisper 调用、Normalization/Render 新 Revision、Canonical Publish、Run 状态机推进（除 §17 `retry_count+1` 与 §18 终态返回外）一律不做。
- 任何 §2.2 禁止项：AI 总结/改写/润色/校稿、LLM、云端 ASR、任何云 API、Redis/PostgreSQL、微服务、Docker、消息队列、RAG/Embedding/向量库、复杂 UI、Obsidian 插件、SaaS/手机端/浏览器上传、iCloud File Coordination、新模型、自动覆盖用户笔记、Reprocess UI、复杂历史版本 UI。
- 真实长视频测试与真实目录扫描（用户明确：真实长视频一律不测直到产品完成；watchdog 真实启动可用 file-system event，但测试一律指向合成目录）。
- 不改 `src/stage1/`、`src/stage2/`、`src/stage3/`、`src/stage4/`、不改 V1.8 架构基线、不动治理表（账本由执行链按 AGENTS 分工写，planner 不代写）、不 push、不碰 secrets。

## Task Breakdown

| Task ID | Priority | Role | Status | Notes |
|---|---|---|---|---|
| S5-T01 Watchdog 真实监听 + Watcher Ready 门（Watch First） | P0 | builder | TODO | 输入：Stage2 `candidate.discover`（只读复用，唯一投递入口）+ watchdog 6.0.0（已锁定依赖）+ §3.1/§5/§62。输出：`src/stage5/watcher.py`（`start_watch(input_root, data_root, asr_profile_hash, on_deliver=discover)`：Observer 递归监听合成 Input Root，created/moved/modified 事件去抖后只投递（调 `discover()`，返回结果记 `state_events` 备注，不直写业务表）；`wait_ready(timeout)`：Ready 前返回 False 时禁止 Scan 启动；`stop()` 幂等可 join；视频后缀白名单模块常量，大小写不敏感；持锁断言：投递经 `discover()` 间接持锁，本模块不自建锁）。验收：happy（合成目录放 1 新视频→PROMOTED + AUTO Run 建立）+ 抖动文件（门内 append→仍 WAITING，不提前 PROMOTED）+ 非视频后缀忽略 + stop 后再放文件不投递 + Ready 门（Ready 前调 Scan 入口抛错）。禁动 `src/stage1-4/`；Whisper 调用 0。 |
| S5-T02 Startup Scan 全量补扫（Scan Second） | P0 | builder | TODO | 输入：S5-T01 的 Ready 门 + `discover()`。输出：`src/stage5/scan.py`（`startup_scan(input_root, data_root, asr_profile_hash)`：前置断言 Watcher Ready（未 Ready 即抛错，顺序硬门）；递归枚举合成 Input Root 全层级视频文件，逐个调 `discover()` 投递并返回投递清单；模块内无去重逻辑（Case 13 由 `discover()` 裁决，出现“同 path 跳过”即 FAIL）；空目录返回空清单非异常）。验收：停机补回（Observer 未启动时放 N=3 新视频→启动→Scan 后 3 个全 PROMOTED，Lost Job=0）+ 重复 Scan 同目录（Source/Run 计数不变，Exactly Once）+ Case 13 经 Scan 路径（改 bytes 保 size+mtime→新 Source 产生）。只扫合成目录；禁动 `src/stage1-4/`。 |
| S5-T03 Reconciliation 对账补漏（Reconcile Third + §17/§18） | P0 | builder | TODO | 输入：S5-T01–T02 + `runs.reconcile_source/reconcile_run`（只读复用语义）。输出：`src/stage5/reconcile.py`（`initial_reconcile(input_root, data_root, asr_profile_hash)`：供启动链，枚举现存视频→缺失投递 `discover()`→既有 Run 经 `reconcile_source` 收敛；`periodic_reconcile(...)`：同语义可重复调，供漏事件补漏；`FAILED_RETRYABLE`→同一 `run_id` + `retry_count+1` 不建新 Run；`NO_SPEECH_DETECTED`→返回既有终态零新增；`QUEUED` 原样返回；对账本身不推进转写状态机）。验收：漏事件补回（屏蔽 Watcher 投递函数后放 1 视频→periodic 一次即补回）+ Case 2（NO_SPEECH Run 连调 10 次→Run Count=1）+ §17（RETRYABLE 调 2 次→同 run_id，retry_count 递增，无新 Run）。禁动 `src/stage1-4/`；Whisper 调用 0。 |
| S5-T04 §62 完整启动装配 + delivery-only Workers（到 RUNNING） | P0 | builder | TODO | 输入：S5-T01–T03 + `stage2.instance.startup`（前五步复用）。输出：`src/stage5/startup.py`（`run_startup(data_root, input_root, asr_profile_hash)`：调 `instance.startup` 跑前五步（复用其锁与 DB，不另起锁）→ Start Watcher（S5-T01）→ Confirm Watcher Ready（`wait_ready`，超时抛错不停留在半启动）→ Startup Scan（S5-T02）→ Initial Reconciliation（S5-T03）→ Start Workers（有界线程，消费三路投递队列调 `discover()`，delivery-only：模块内无转写/发布/归档 import，存在即 FAIL）→ 返回 `{"order": [...11步逐字...], "running": True}`；`shutdown()` 停 Observer + 停 Workers 幂等）。验收：order 数组 11 步逐字断言通过 + 顺序倒置用例（monkeypatch 调换 Scan/Ready 顺序即抛错）+ 第二实例沿用 exit 3（经 `instance` 语义，不另测锁，只断言 `run_startup` 不吞 SecondInstanceError）+ Workers 纯投递审计（grep 转写/发布/归档零命中）。 |
| S5-T05 Triple Discovery Race 真三路并发（Case 3 延续） | P0 | builder | TODO | 输入：S5-T01–T04 落盘模块。输出：三路并发装配（用例级，逻辑进 S5-T06 验收；本任务落 `src/stage5/__init__.py` 装配导出 + 线程安全复核：watch 事件投递 × Scan × periodic 三路真并发调同一合成视频，依赖 `discover()` 内 Provisional 原子竞争 + AUTO UPSERT 收口；本任务不新增持久化语义，只做装配与锁竞争复核）。验收：三路 × 多次并发→中央库实查 `Logical Source Count=1` 且 `AUTO Run Count=1`；任一偏离即 FAIL；`stage2` 的 `_retry_locked` 语义复用不断链（`database is locked` 不抛到验收层）。禁动 `src/stage1-4/`。 |
| S5-T06 Stage5 验收套件 + §72 子集门 + Stage1~4 回归 | P0 | qa（执行）+ builder（修） | TODO | 输入：S5-T01–T05 产物 + `src/stage1-4/` 只读复用。输出：Stage5 验收报告（happy 链 1 遍：合成目录放视频→Watcher 投递→PROMOTED→Source=1→AUTO Run=1→停机加视频→重启 Scan 补回→RUNNING order 11 步 + 异常路径至少 7 个：Triple Race 三路并发 / NO_SPEECH×10 / FAILED_RETRYABLE 重试原 Run / 漏事件 periodic 补回 / 抖动文件 WAITING / Case 13 新 Source / Ready 前 Scan 被拒；每个用例：前置/动作/期望 Count 或 exit 码/`Duplicate Source/Run=0` 证据/四表（normalization/render 恒 0，publish/archive 行数不变）证据/Whisper 调用=0 证据/外置合成路径证据/Run 非转写态证据；结论只落 qa 报告，HANDOFF 只记状态）+ 回归四行（Stage1 per-job happy 仍 PASS；Stage2 discover→AUTO Run=1 仍 PASS；Stage3 verdict 链仍 PASS；Stage4 PUBLISHED 行可查且行数不变；`src/stage1-4/` git diff 为空）。验收：任一异常缺失、计数偏离、四表行数变动、有转写/发布/归档写、真实目录被碰、结论写进 HANDOFF 代报告，均为 FAIL。 |

- 并行性说明：S5-T01 → T02 → T03 → T04 → T05 → T06 严格串行（Ready 门→Scan→Reconcile→装配→真并发→验收；T02 在 Ready 门未就绪前跑无顺序可证；Reconcile 收敛语义在 Scan 清单语义前定会污染补回证据；Case 3 真并发在三路未就绪前跑无收口可查）。
- 角色说明：S5-T01–T05 = builder 实现；S5-T06 = qa 执行验收 + builder 修；code-reviewer / product-reviewer / supervisor 按 AGENTS 派工顺序在计划完成后介入，本计划不代派。

## Risks

- R1 三路重复投递打爆 DB 锁：Watch/Scan/Reconcile 并发写同一 provisional key，`database is locked` 抛到业务层。缓解：投递只经 `discover()`（内含 `_retry_locked` + Provisional 原子竞争 + AUTO UPSERT），Stage5 不自造写路径；S5-T05 用真并发复现，不用串行模拟。
- R2 Scan 扫到真实目录：递归扫描配错 root 会触碰用户视频。缓解：TM 已定——测试一律合成目录；验收前断言所有输入路径位于外置合成 Input Root 内；watchdog 真实 file-system event 能力只在实现侧使用，测试侧 root 恒为合成目录。
- R3 半写文件被提前转交：Watcher 事件到达时文件仍在拷贝，绕过 Stable 门会产生坏 Source。缓解：S5-T01 硬门——事件只投递给 `discover()`（其内两轮 size/mtime 门裁决），Stage5 不设“事件即 PROMOTED”快路；抖动用例强制门内 append。
- R4 Workers 顺手执行转写：启动 Workers 后把 Run 推进到 TRANSCRIBING 最省事但违反范围。缓解：S5-T04 硬门——Workers delivery-only，模块内转写/发布/归档 import 零命中；S5-T06 反查 Run 状态不出 QUEUED/FAILED_RETRYABLE/NO_SPEECH_DETECTED（除经 discover 建的 QUEUED 外）。
- R5 为复用改 stage1-4 原文：把 `discover()` 改成通用投递函数或动锁语义最省事但违反加法约束。缓解：新增只进 `src/stage5/`；S5-T06 回归硬门——`src/stage1-4/` git diff 为空。
- R6 启动顺序倒置丢任务：Scan 在 Watcher Ready 前跑，Ready 前到达的文件两边都漏。缓解：S5-T02 Ready 前置断言 + S5-T04 order 11 步逐字断言；Watch First / Scan Second / Reconcile Third 倒置即 FAIL。
- R7 Scan 自作聪明去重吞掉 Case 13：扫描层按 path 跳过“见过”的文件，新字节视频被吞。缓解：S5-T02 硬门——Scan 内无去重逻辑；Case 13 用例经 Scan 路径强制建新 Source。
- R8 Stage6+ 提前实现：Path Mirror、VAD/Chunk、Archive、`current_path` 回填最易“顺手”。缓解：S5-T06 四表行数快照对比 + Source 行列级 diff（除 Stage2 语义内列外不变）+ Stage6+ 关键词 grep 零命中。

## Human Decisions Needed

- 无，按TM已定执行（本计划无阻塞项，不问人）。
- TM 已定事项备忘（执行，不复议）：① 外置测试目录（仓库外独立 Data Root + 独立合成 Input Root，Stage1 `/tmp/s1t*` 与 Stage2 H2 外置目录模式延续）；② 异常路径一律用合成副本（原片不动，只动副本；canonical/笔记一律不碰）；③ 真实长视频一律不测直到产品完成（用户明确，用例最大文件为合成小文件）；④ `src/stage1/` + `src/stage2/` + `src/stage3/` + `src/stage4/` 只读加法（新增只进 `src/stage5/`，diff 为空为硬门）；⑤ STOP EXPANSION（Stage6+ 禁入：Path Mirror、Prompt/Vocab、VAD/Chunk、阈值调优、Archive A/B/C、`current_path` 更新、LaunchAgent、Menu Bar 一律 Out；Triple Discovery Race 按 Source=1/Run=1（Case 3）延续；watchdog 真实启动可用 file-system event，测试用合成目录）。
