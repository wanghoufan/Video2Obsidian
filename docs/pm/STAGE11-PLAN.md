# PLAN｜Stage 11 LaunchAgent + Full Reliability + Fault Injection（Video2Obsidian V1.8 §69）

> 基线：`docs/2026-09-10 丨 MAC 丨 GPT 网页端 丨 Video2Obsidian 本地视频自动转写工具开发计划-交接上下文 丨 V1.8.md`
> 基线状态：`V1.8 ARCHITECTURE FROZEN`（§71）+ Stage1~Stage10 实现已落盘（`src/stage1/` 单视频 Raw 闭环 + Repair Forward + `src/stage2/` Candidate/Source/AUTO Run + 中央 `<data_root>/data/state.db` + Single Instance + `src/stage3/` Revision 链 + `src/stage4/` Initial Canonical Publish + Ownership + `src/stage5/` Watch/Scan/Reconcile 到 RUNNING（§62 11 步装配）+ `src/stage6/` Path Mirror + `src/stage7/` Vocabulary/Prompt/Language + 单文件接线 + `src/stage8/` VAD advisory + ChunkPlanner（10min/2s）+ Absolute Timeline + Overlap Merge + `src/stage9/` 新版 Correction 规则表 + 新版 Paragraph formatter + `src/stage10/` Archive A/B/C + Strong Verify（§26）+ G3 落地 + Source 四列更新；LaunchAgent plist、§67 Crash Guarantee 矩阵、完整 Fault Injection Suite 均未实现）。
> Stage1~Stage10 冻结输入：`src/stage1/`（`run_asr_single_file` 单文件直转 + `recovery.py` Repair Forward Truth Model：Filesystem Valid + Expected Hash = Truth，SQLite 落后 Repair Forward，不重跑 Whisper，只读复用）与 `src/stage2/`（`candidate.discover` 唯一发现入口 + `runs.get_or_create_auto_run` UPSERT + `instance.py` Single Instance 锁 + `store.py` 中央库 DDL，只读复用）与 `src/stage3/`（Revision 链公开 API，只读复用）与 `src/stage4/`（`initial_publish` + Ownership + `conflict` 用户编辑优先，只读复用）与 `src/stage5/`（`startup.py` §62 全序装配 + Watch/Scan/Reconcile 三路语义，只读复用不复制）与 `src/stage6/`（`resolve_canonical` 纯映射，只读复用）与 `src/stage7/`（vocab/prompt/language，只读复用）与 `src/stage8/`（VAD/Chunk/Timeline/Merge，只读复用）与 `src/stage9/`（`rules_v2`/`formatter_v2`，只读复用）与 `src/stage10/`（`verify_archive`/`level_a`/`level_b`/`level_c`/`gate`/`commit`，只读复用；恒经 `gate` 调用，`expected_hash` 必填——Stage10 review P2-1 独立直调敞口本 Stage 以装配约束关闭，不改 stage10 文件）——本 Stage 只做加法，不改 `src/stage1/` ~ `src/stage10/` 任一文件（改了即 FAIL；新增只进 `src/stage11/`）。
> 最高约束：`STOP ARCHITECTURE EXPANSION`（§65-71）+ `STOP EXPANSION（Stage11 only）`——本 Stage 只实现 §69 Stage11 定义的事项（LaunchAgent plist 常驻 + §67 Crash Guarantee 本 Stage 实现 + Full Reliability + Fault Injection 全套件本 Stage 搭建 + §62 全序端到端装配 + G3 复用不断链（Stage10 已落地，不重实现）+ §70 Case 9/10/15 复用 + 新故障 + §72 Root/LaunchAgent 子集 + §73-21/22/45/46/48/52/53/54），Stage12（Menu Bar）一律 Out，写了即 FAIL；§2.2 禁止项（LLM/云/总结改写润色）出现即 FAIL；永不写入真实 LaunchAgents 目录（`~/Library/LaunchAgents`、`/Library/LaunchAgents` 任一触碰即 FAIL）；永不覆盖用户笔记、永不误删源（模块内出现 `force|overwrite|clobber` 即 FAIL）。

## Product Goal

Video2Obsidian 是一个运行在 Apple Silicon Mac 上的零 API 成本、本地常驻视频知识入库工具：用户只需要把视频放入已经分类好的本地文件夹，系统自动完成本地 Whisper 转写、专业词增强、自然分段、目录镜像、Obsidian Markdown 安全写入和源视频安全归档（V1.8 §1.2）。目标设备：Mac mini M4 / 24GB RAM。本 Stage 只做其中“常驻与可靠”的那一块：在 Stage5 §62 启动链与 Stage1 Recovery 语义、Stage10 Archive/G3 之上，LaunchAgent plist（只写测试目录）→ Cold Boot 到 RUNNING 可证明 → §67 必须恢复矩阵（process crash / kill -9 / application restart / LaunchAgent restart / normal macOS reboot 等价证明）全恢复 → Fault Injection 全套件 PASS（复用 Case 8/9/10/12/13/15 + 新故障，无永久卡死 §73-54）→ 全程用户覆盖恒 0、Source Mis-delete 恒 0、Repair 路径 Whisper 增量恒 0 → Stage1~10 回归（`src/stage1-10/` diff 为空）。

## Current Stage

- Stage ID: Stage 11 — LaunchAgent + Full Reliability + Fault Injection（V1.8 §69）
- Goal: 测试目录内 plist 生成/校验/加载演练可证明（Absolute Binary Paths，真实 LaunchAgents 零触碰）→ Cold Boot 经 §62 11 步到 RUNNING 可证明 → §67 五项必须恢复可证明（掉电仅 Best Effort 语义记账，不真测；物理故障 Out）→ Fault 全套件（复用 7 类 + 新增 ≥4 类）全绿且无永久卡死可证明 → 合成小批量 Lost Job=0 / Duplicate=0 可证明（20 长视频 Batch 不做）→ §72 Root/LaunchAgent 子集 + §73-21/22/45/46/48/52/53/54 可证明 → Stage1~10 回归（`src/stage1-10/` diff 为空）。

Stage1~Stage10 地基复用约定（加法约束）：
```text
src/stage1/ 原样复用（回归只读查 + Recovery 语义只读装配）：verify/post_verify
  强校验 + recovery Repair Forward（kill 后 Final Hash == expected 即补
  Receipt，不重跑 Whisper；Whisper 增量断言恒 0）
src/stage2/ 原样复用（import，不复制不修改）：candidate.discover（唯一发现
  入口；停机补回/风暴投递只经此入口）/ runs.get_or_create_auto_run（UPSERT；
  重启/重投不新增 Run，新增即 FAIL）/ store.open_db 持锁断言 / instance
  单实例锁（agent 重启后第二实例仍 exit 3）
src/stage3/ 零调用（本 Stage 不派生 Revision；回归只读查）
src/stage4/ 只读复用（Ownership/Conflict 用户编辑优先语义只读装配进 recovery
  与 fault 断言，不复制覆盖逻辑）
src/stage5/ 只读复用（import，不复制不修改）：startup.run_startup §62 全序
  （agent_boot 只做装配调用，不重写顺序；顺序倒置即 FAIL）/ watcher+scan+
  reconcile 三路语义（补回/风暴只经 discover 投递）
src/stage6/ 零调用（回归双算不断链）
src/stage7/ 零调用（回归不断链；单文件接线语义只读引用，不新起转写链）
src/stage8/ 零调用（回归不断链）
src/stage9/ 零调用（回归不断链）
src/stage10/ 只读复用（import，不复制不修改）：gate.archive_source 为 Archive
  侧唯一入口（expected_hash 必填，独立直调 level_a/level_b 即 FAIL；
  Stage10 review P2-1 以装配约束关闭）/ commit 成功语义复用 / Mid-copy
  Recovery 语义复用进 fault 用例
src/stage11/ 新增：launch_plist.py（plist 生成/校验）/ agent_boot.py（§62
  装配 + RUNNING）/ reliability.py（§67 crash 矩阵 helpers）/
  fault_suite.py（全套件注册表 + runner）（命名以实现为准，前缀恒为
  stage11，禁止 stage12 关键词文件名如 menu）
中央库位置：<data_root>/data/state.db（沿用 Stage2；本 Stage 不新增表/列；
  Recovery 写只许经 stage1/stage2/stage10 既有 Repair 语义并逐行披露；
  normalization_revisions/render_revisions/publish_records 非预期新增即
  FAIL；archive_commits 仅复用 S10 成功语义时允许新增并逐行披露）
输入源视频：外置合成小文件（仓库外独立合成 Input Root；ffmpeg 本地合成秒级
  mp4/wav，不扫真实视频目录；长视频不测，用例最大文件 ≤ 合成小文件；
  文本/ASR 内容不断言，词准确率/Golden/CER/幻觉指标属 Stage11+ Out）
诱饵 canonical：外置合成目录内诱饵 md（用户编辑优先断言只用诱饵文件比对
  “存在且不变”，零触碰真实笔记；覆盖计数恒 0）
LaunchAgents 输出：仓库外独立测试 LaunchAgents 目录（plist 只写此目录；
  真实 ~/Library/LaunchAgents、/Library/LaunchAgents 零触碰，验收前断言
  路径前缀；launchctl load/unload 只对测试 plist 演练且演练后立即 unload
  无残留；禁用 launchctl enable 开机持久化）
reboot 证明方式：不等价真机 reboot——以 stop-all + relaunch + Recovery
  Bootstrap + RUNNING + Lost/Duplicate 0 为 reboot 等价证明（记账声明）
掉电证明方式：Best Effort 只记语义（flush/fsync + PREPARED/Receipt 已由
  Stage1/10 落地），不真拔电、不做断电柜测试
```

## Stage P0（P0=本 Stage 非做不可、缺它不算完的事项，由 planner 初定、Task Manager 拍板；同时作为 qa / product-reviewer 的 P0 Blocking 参照。TM已拍板：按初定通过，本节即执行口径）

- [ ] P0-1 LaunchAgent plist 常驻可证明（§69 Stage11 + §72 Root/LaunchAgent）：测试目录内 plist 生成 → 字段完备（Label 测试域命名 + ProgramArguments 全绝对路径 + WorkingDirectory + RunAtLoad + KeepAlive + ThrottleInterval + StandardOut/Error 落 `<data_root>/logs/`）→ `plutil -lint` 过 + 读回断言绝对路径 → `launchctl load` 测试 plist 后 `list` 可见，演练后立即 `unload` 且无残留（`list | grep <label>` 为空）→ 真实 `~/Library/LaunchAgents`、`/Library/LaunchAgents` 零触碰（路径前缀断言 + 演练前后快照）；`launchctl enable` 出现即 FAIL。
- [ ] P0-2 Cold Boot 经 §62 全序到 RUNNING + Single Instance 重证可证明（§62/§64 + §73-46/48）：`agent_boot` 装配复用 `stage5.startup` 与 `stage2.instance`，返回 order 数组逐字 11 步（Static Preflight → … → RUNNING，倒置/跳步即 FAIL）→ Cold Boot 后停机期间加入的合成视频被补回（Lost=0，小 N 合成）→ agent 重启后第二实例仍 exit 3 且零写盘（DB mtime 不变）→ Archive/转写入口恒经既有 gate（`expected_hash` 必填；独立直调 `level_a`/`level_b` 即 FAIL）。
- [ ] P0-3 §67 Crash Guarantee 矩阵可证明（必须恢复 5 项 + Best Effort 记账）：process crash（SIGKILL job 中）/ kill -9（rename/manifest 前 + mid-copy，Case 9/10 复用）/ application restart / LaunchAgent restart（unload + load 测试 plist）/ reboot 等价（stop-all + relaunch + Recovery Bootstrap）——每项恢复后 RUNNING 可达 + Lost Job=0 + Duplicate Source/Run=0 + 半截文件≠成功（无 Receipt 不成功 §73-22）+ Repair 路径 Whisper 增量恒 0（Final Hash==expected 即 Repair Forward §73-21，不得重跑）+ SQLite 落后 Repair Forward（Case 15 复用 §73-45）→ 掉电仅 Best Effort 语义记账（不真测）→ 物理硬盘/文件系统损坏/用户手删库（§67 Out）不测。
- [ ] P0-4 Fault Injection 全套件可证明（§72 Fault Injection Suite + §73-54 + §70 复用 + 新故障）：复用故障（Case 8 同 size+同 mtime+异字节篡改 BLOCK / Case 9 rename-manifest kill / Case 10 mid-copy kill 源保留 / Case 12 Output Race 用户字节不变 Overwrite=0 / Case 13 历史碰撞认新源 / Case 15 SQLite 落后 Repair Forward / 半截 artifact≠成功）+ 新增故障 ≥4 类（如 PREPARED 后 DB 行丢、归档 commit 前 kill、publish 前 canonical 被改 race、双实例并发投递风暴）→ runner 逐用例 verdict + exit 码 → 全绿 → 套件跑后 RUNNING 可达（无永久卡死 §73-54）→ 任一 BLOCK 路径源保留（Mis-delete=0 §73-52）+ 用户/诱饵覆盖恒 0（§73-53）。
- [ ] P0-5 STOP EXPANSION 门可证明：`src/stage1/` ~ `src/stage10/` git diff 为空；不新增表/列（DDL 快照对比）；`normalization_revisions`/`render_revisions`/`publish_records` 非预期新增即 FAIL（快照对比举证）；Stage11 代码永不 import Menu Bar、Golden/CER、LLM/云/SDK（`rg "menu|golden|cer|openai|anthropic|requests\.|llm|summar|polish|paraphras|rewrite" src/stage11/` 零命中举证；`launchagent/plist/agent_boot/reliability/faultsuite` 为本 Stage 合法词，不在禁入列）；直写 DB 仅经既有 Repair/Commit 语义并逐行披露（`rg "sqlite3|INSERT|UPDATE|DELETE" src/stage11/` 命中必须逐行对应披露，无多余写）；真实 LaunchAgents 目录任一触碰、真实 reboot、真掉电测试、`launchctl enable` 任一出现即 FAIL。
- [ ] P0-6 外置合成验收门可证明（TM 已定）：一切输入位于外置合成目录 + 外置 Data Root + 外置合成 Archive Root + 诱饵 Output Root + 测试 LaunchAgents 目录内（验收前断言，与真实视频目录/真实 Obsidian 库/真实 Archive 目录/真实 LaunchAgents 目录无交集）；异常路径一律合成副本（原片不动，只动副本；canonical 只用诱饵文件比对“存在且不变”，零触碰真实笔记）；真实长视频一律不测（用例最大文件 ≤ 合成小文件，作为 PASS 条件写进报告；20 Video 长视频 Batch 不做，代之以 small-N 合成小批量 Lost/Duplicate 0；文本内容不断言）；任一用例触碰真实目录/发起云调用/写真实 LaunchAgents 即 FAIL。

## In Scope

- LaunchAgent plist 生成/校验/加载演练（只写测试目录；Absolute Binary Paths；RunAtLoad/KeepAlive/ThrottleInterval；日志进 `<data_root>/logs/`；演练后 unload 无残留；禁 `enable`）。
- Cold Boot 经 §62 11 步到 RUNNING（复用 `stage5.startup` + `stage2.instance` 装配；停机补回 Lost=0；第二实例 exit 3 重证）。
- §67 必须恢复矩阵（process crash / kill -9 / application restart / LaunchAgent restart / reboot 等价；掉电 Best Effort 记账；物理故障 Out）。
- Fault Injection 全套件搭建（复用 Case 8/9/10/12/13/15 + 半截≠成功 + 新增 ≥4 类；runner + verdict/exit 码；跑后 RUNNING 可达；Mis-delete=0；Overwrite=0）。
- G3 复用不断链（Recovery 后、Archive 前重确认 Publish + 用户编辑优先语义只读装配进 recovery/fault 断言，不重实现 Stage10 文件）。
- 合成小批量可靠性抽查（small-N 合成小文件；Lost Job=0 / Duplicate Source=0 / Duplicate AUTO Run=0）。
- §72 Implementation Acceptance Gate 中仅属于 Stage11 的断言子集：LaunchAgent Cold Boot / Absolute Binary Paths / Single Instance（agent 下重证）/ VolumeCapabilityProbe（复用）/ iCloud-Remote Root BLOCK（复用）/ Fault Injection Suite。
- §73-21/22/45/46/48/52/53/54 + §73-2（停机补回）联动。
- Stage1~10 回归（十回归不断链；`src/stage1-10/` diff 为空）。

## Out of Scope

- Stage12 全部：Menu Bar（核心稳定后可选；本 Stage 出现 `menu` 模块/文件即 FAIL）。
- Golden Dataset / CER / 词准确率 / 幻觉与重复文本指标（文本内容不断言；合成正弦无语音空文本合法口径延续）。
- 20 Video 长视频 Batch 与一切真实长视频测试（用户明确：真实长视频一律不测直到产品完成；本 Stage 只做 small-N 合成小批量）。
- 真机 reboot、真掉电/拔电测试、物理硬盘/文件系统损坏、用户手删库（§67 Out；reboot 以等价证明记账，掉电以 Best Effort 语义记账）。
- 真实 LaunchAgents 目录的安装/写入/启用（`~/Library/LaunchAgents`、`/Library/LaunchAgents` 零触碰；`launchctl enable` 禁入；开机持久化不做）。
- 转写/派生/发布/归档语义升级（Whisper/Normalization/Paragraph/Publish/Archive 只读复用；Repair 路径 Whisper 增量恒 0；`publish_records` 非预期新增即 FAIL；为常驻改 stage1-10 原文即 FAIL）。
- 任何 §2.2 禁止项：AI 总结/改写/润色/校稿、LLM、云端 ASR、任何云 API、Redis/PostgreSQL、微服务、Docker、消息队列、RAG/Embedding/向量库、复杂 UI、Obsidian 插件、SaaS/手机端/浏览器上传、iCloud File Coordination、新模型、自动覆盖用户笔记、Reprocess UI、复杂历史版本 UI。
- Replace Policy（后续派生自动覆盖 canonical，不属 V1.8；G3 只 BLOCK 不覆盖逻辑延续复用）。
- 永久删除 Archive（§60 默认 never，本 Stage 不删 Archive）。
- 真实目录扫描/写入/真实 Obsidian 库/真实 Archive 目录/真实 LaunchAgents 触碰（测试一律指向合成 Input Root + 外置 Data Root + 合成 Archive Root + 诱饵 Output Root + 测试 LaunchAgents 目录）。
- 不改 `src/stage1/` ~ `src/stage10/`、不改 V1.8 架构基线、不动治理表（账本由执行链按 AGENTS 分工写，planner 不代写）、不 push、不碰 secrets。

## Task Breakdown

| Task ID | Priority | Role | Status | Notes |
|---|---|---|---|---|
| S11-T01 LaunchAgent plist 生成/校验/加载演练 | P0 | builder | TODO | 输入：stage2 `instance` 锁语义（只读）+ stage5 `startup` 装配点（只读）+ §62/§64 + TM 测试目录约束。输出：`src/stage11/launch_plist.py`（`build_plist(label, abs_binary, data_root, test_agent_dir)` 生成 plist dict：Label 测试域命名 + ProgramArguments 全绝对路径 + WorkingDirectory + RunAtLoad + KeepAlive + ThrottleInterval + StandardOut/Error 进 `<data_root>/logs/`；`write_plist` 路径前缀断言恒在测试目录内，不在即拒写；`validate_plist`：`plutil -lint` 过 + 读回断言全绝对路径 + Label/RunAtLoad/KeepAlive 字段存在）。验收：plist 落测试目录 + 真实 LaunchAgents 零触碰证据（前后快照）+ `launchctl load <测试plist>` 后 `list` 可见、演练后立即 `unload` 且 `list` 无残留 + `enable` 零出现 + Whisper 0 + 零 DB 写证据。禁动 `src/stage1-10/`；禁 menu/golden/LLM；禁真实 agent 目录。 |
| S11-T02 Cold Boot §62 全序装配 + Single Instance 重证 | P0 | builder | TODO | 输入：S11-T01 的 plist 演练 + stage5 `startup.run_startup`（只读装配调用，不重写顺序）+ stage2 `instance`（只读复用）。输出：`src/stage11/agent_boot.py`（`cold_boot(data_root, input_root)`：调既有 startup 全序，返回 order 数组 + RUNNING 哨兵；Archive/转写调用恒经既有 gate，`expected_hash` 必填，独立直调 `level_a`/`level_b` 结构上不可达）。验收：order 逐字 11 步（倒置/跳步 FAIL）+ Cold Boot 后停机期间加入的合成视频补回（Lost=0，small-N 合成）+ agent 重启后第二实例 exit 3 且 DB mtime 不变 + Whisper 增量 0（boot 不转写）+ 四表非预期零新增证据。禁动 `src/stage1-10/`；禁重写 startup 顺序；禁 `enable`/真实目录。 |
| S11-T03 §67 Crash Guarantee 恢复矩阵 | P0 | builder | TODO | 输入：S11-T02 的 cold_boot（重入入口）+ stage1 `recovery` Truth Model（只读复用）+ stage10 `gate`/`commit`/mid-copy 语义（只读复用）+ G3 预门语义（只读装配）。输出：`src/stage11/reliability.py`（`snapshot`/`kill9`/`relaunch`/`assert_recovered` helpers：前快照 → SIGKILL/restart → cold_boot 重入 → Repair Forward → 后断言 Lost/Duplicate/Receipt/Whisper 增量）。验收矩阵每项恢复后 RUNNING 可达 + Lost=0 + Dup=0 + 半截≠成功 + Whisper 增量 0：① job 中 SIGKILL ② rename/manifest 前 kill（Case 9 复用：不重跑 Whisper）③ mid-copy kill（Case 10 复用：源保留）④ application restart ⑤ LaunchAgent restart（unload+load 测试 plist）⑥ reboot 等价（stop-all + relaunch + Bootstrap）⑦ SQLite 落后（Case 15 复用 Repair Forward）；掉电记 Best Effort 语义行（不真测）；G3 双腿不断链（Recovery 后 Archive 前重确认语义被调达）。禁动 `src/stage1-10/`；禁 Repair 顺手重跑 Whisper；禁真实 reboot/掉电。 |
| S11-T04 Fault Injection 全套件搭建 | P0 | builder | TODO | 输入：S11-T03 的 helpers + stage1~10 只读语义 + §70/§73 条目。输出：`src/stage11/fault_suite.py`（用例注册表 + runner：逐用例 前置/动作/期望 verdict 或 exit 码/Whisper 增量/DB 快照/hash/覆盖计数 证据采集；失败即非零 exit）。复用故障 7 类：Case 8 篡改 BLOCK / Case 9 / Case 10 / Case 12 race（用户字节不变，Overwrite=0）/ Case 13 碰撞认新源 / Case 15 lag / 半截 artifact≠成功；新增故障 ≥4 类：PREPARED 后 DB 行丢、归档 commit 前 kill、publish 前 canonical 被改 race、双实例并发投递风暴（只经 discover，Run 不新增）。验收：全绿 + 套件后 RUNNING 可达（§73-54 无永久卡死）+ 任一 BLOCK 源保留（§73-52）+ 覆盖恒 0（§73-53）+ Whisper 增量逐用例披露（Repair 类恒 0）。禁动 `src/stage1-10/`；禁半截当成功；禁真实目录/长视频。 |
| S11-T05 Stage11 验收套件 + §72/§73 子集门 + Stage1~10 回归 | P0 | qa（执行）+ builder（修） | TODO | 输入：S11-T01–T04 产物 + `src/stage1-10/` 只读复用。输出：Stage11 验收报告（happy 链 1 遍：合成源→discover→plist 演练→cold_boot RUNNING→小批量补回→fault 全套件绿→RUNNING 可达 + §67 矩阵 7 项逐项 + 异常/边界至少 10 个：篡改 BLOCK / race BLOCK / 碰撞新源 / lag Repair / 半截≠成功 / PREPARED 后行丢恢复 / commit 前 kill 恢复 / canonical 被改 BLOCK（覆盖 0）/ 风暴 Run 不新增 / 同 plist 重复 load 幂等或复用证据；每个用例：前置/动作/期望 verdict 或 exit 码/Whisper 增量证据/四表快照证据/诱饵 md 不变证据/最大文件 ≤ 合成小文件声明/外置四 Root + 测试 agent 目录路径证据/真实 LaunchAgents 零触碰证据；结论只落 qa 报告，HANDOFF 只记状态）+ 回归十行（Stage1 per-job happy 仍 PASS；Stage2 discover→AUTO Run=1 仍 PASS；Stage3 冻结版规则链仍 PASS；Stage4 单文件 PUBLISHED 仍可查；Stage5 Ready→Scan→Reconcile→RUNNING 语义不断链；Stage6 嵌套 Unicode mirror 双算一致；Stage7 装配→接线→profile executed 仍 PASS；Stage8 合成 wav→VAD→planner→timeline→merge 仍 PASS；Stage9 Case 4/5 派生仍 PASS（Whisper 0/Raw 同/诱饵不变）；Stage10 Same-FS Archive + 四列更新仍 PASS（合成小文件，Whisper 0）；`src/stage1-10/` git diff 为空）。验收：任一异常缺失、计数偏离、非预期表新增、Repair 重跑 Whisper、诱饵被改、真实目录/真实库/真实 Archive/真实 LaunchAgents/云/长视频/`enable`/真实 reboot 被碰、结论写进 HANDOFF 代报告，均为 FAIL。 |

- 并行性说明：S11-T01 → T02 → T03 → T04 → T05 严格串行（plist 是 boot 的前置；Cold Boot 可达是 crash 矩阵的前置；矩阵 helpers 是 fault 套件的前置；四件未就绪前验收无收口可查）。
- 角色说明：S11-T01–T04 = builder 实现；S11-T05 = qa 执行验收 + builder 修；code-reviewer / product-reviewer / supervisor 按 AGENTS 派工顺序在计划完成后介入，本计划不代派。

## Risks

- R1 plist“顺手”写真实目录：`~/Library/LaunchAgents` 最省事但违反 TM 已定。缓解：S11-T01 硬门——写前路径前缀断言 + 真实目录前后快照 + 触碰即 FAIL。
- R2 `launchctl load` 残留常驻：演练后忘 unload 即污染本机 launchd。缓解：S11-T01/T05 硬门——演练后立即 unload + `list | grep <label>` 为空证据 + `enable` 零出现审计。
- R3 真机 reboot/真掉电“求真”：最“真实”但违反 TM 已定且危险。缓解：reboot 以 stop-all + relaunch 等价证明记账；掉电以 Best Effort 语义记账；真操作出现即 FAIL。
- R4 Repair“顺手”重跑 Whisper：重跑最省事但违反 §73-21/Case 9。缓解：S11-T03/T04 硬门——Repair 类用例 Whisper 增量恒 0 + Final Hash==expected 即补 Receipt 断言。
- R5 套件把半截当成功：存在即成功最省事但违反 §73-22/§57 Receipt 语义。缓解：S11-T04 硬门——无 Receipt 不成功 + Mid-copy Kill 源保留复跑。
- R6 为常驻改 stage1-10 原文：改 startup 顺序/改锁语义最省事但违反加法约束。缓解：S11-T05 回归硬门——`src/stage1-10/` git diff 为空 + 装配只调公开入口审计。
- R7 真实长视频/真实目录误测：拿真实课程长视频验可靠最“真实”但违反用户明确禁令。缓解：TM 已定——一律合成小文件 + 合成副本；用例最大文件 ≤ 合成小文件写进报告 PASS 条件；文本内容不断言。

## Human Decisions Needed

- 无，按TM已定执行（本计划无阻塞项，不问人）。
- TM 已定事项备忘（执行，不复议）：① 外置测试目录（仓库外独立 Data Root + 独立合成 Input Root + 独立合成 Archive Root + 独立诱饵 Output Root + 独立测试 LaunchAgents 目录，Stage1 `/tmp/s1t*` 与 Stage2 H2 外置目录模式延续；真实 LaunchAgents 目录零触碰）；② 异常路径一律用合成副本（原片不动，只动副本；canonical 只用诱饵文件比对“存在且不变”，不碰真实笔记）；③ 真实长视频一律不测直到产品完成（用户明确，用例最大文件为合成小文件，20 Video 长视频 Batch 不做，代之以 small-N 合成小批量 Lost/Duplicate 0；词准确率/Golden/CER/幻觉指标属 Stage11+ Out）；④ `src/stage1/` + `src/stage2/` + `src/stage3/` + `src/stage4/` + `src/stage5/` + `src/stage6/` + `src/stage7/` + `src/stage8/` + `src/stage9/` + `src/stage10/` 只读加法（新增只进 `src/stage11/`，diff 为空为硬门）；⑤ STOP EXPANSION（Stage12 MenuBar 禁入；§67 Crash Guarantee 本 Stage 实现：process crash/kill-9/application restart/LaunchAgent restart/reboot 等价必须恢复，掉电 Best Effort 记账，物理故障 Out；G3 Stage10 已落地本 Stage 只复用不断链；Fault Injection 全套件本 Stage 搭建：Case 8/9/10/12/13/15 与半截≠成功复用 + 新增 ≥4 类；LaunchAgent plist 常驻只写测试目录，演练后 unload 无残留，禁 `enable`）。
