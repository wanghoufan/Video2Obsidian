# PLAN｜Stage 6 Obsidian Path Mirror + Unicode / Case Tests（Video2Obsidian V1.8 §69）

> 基线：`docs/2026-09-10 丨 MAC 丨 GPT 网页端 丨 Video2Obsidian 本地视频自动转写工具开发计划-交接上下文 丨 V1.8.md`
> 基线状态：`V1.8 ARCHITECTURE FROZEN`（§71）+ Stage1~Stage5 实现已落盘（`src/stage1/` 单视频 Raw 闭环 + `src/stage2/` Candidate/Source/AUTO Run + 中央 `<data_root>/data/state.db` + Single Instance + `src/stage3/` Revision 链 + `src/stage4/` Initial Canonical Publish（§48 单文件相对映射 → 外置诱饵 Output Root + Atomic No-Clobber + Ownership）+ `src/stage5/` Watch First + Startup Scan + Reconciliation 到 RUNNING；STAGE5-QA-REPORT 大写 `MP4` 照收已证后缀大小写不敏感，`path_identity_key` 沿 Stage2 原样存）。
> Stage1~Stage5 冻结输入：`src/stage1/`（job-scoped `data/jobs/<job_id>/` + per-job `job.sqlite` + Raw PREPARE/COMMIT + Immutable + Repair Forward）与 `src/stage2/`（`candidate.discover(path, data_root, asr_profile_hash)` 唯一发现入口 + `path_identity_key` 原样存 §23 + 两轮 size/mtime Stable 门 + `runs.get_or_create_auto_run` UPSERT + `reconcile_source/reconcile_run` §17/§18 收敛 + `instance.startup` §62 前五步 + `data/.lock` Single Instance）与 `src/stage3/`（Revision 链，RenderRev 止于 PUBLISH_EVALUATION）与 `src/stage4/`（`volume_probe.py` §54 九字段 + `publish_commit.py` §49 六步 + `publish.py::initial_publish` §48 单文件映射 + `conflict.py` §53 三分支 + No-Clobber 永不覆盖 §50/§51）与 `src/stage5/`（`watcher.py`/`scan.py`/`reconcile.py`/`startup.py` 三路只经 `discover()` 投递）——本 Stage 只做加法，不改 `src/stage1/`、`src/stage2/`、`src/stage3/`、`src/stage4/`、`src/stage5/` 任一文件（改了即 FAIL；新增只进 `src/stage6/`）。
> 最高约束：`STOP ARCHITECTURE EXPANSION`（§65-71）+ `STOP EXPANSION（Stage6 only）`——本 Stage 只实现 §69 Stage6 定义的事项（Obsidian Path Mirror + Unicode / Case Tests，§23/§48 + §53 冲突延续 + §54 `case_sensitive` 复用 + §70 Case 14 + §72 Canonical Publish 子集 + §73 第 34/35 条），Stage7+（Prompt/Vocabulary/Language Strategy、VAD/Chunk/Absolute Timeline、阈值调优、Archive A/B/C + `current_path` 更新、LaunchAgent、Menu Bar）一律 Out，写了即 FAIL；目录镜像只做路径映射（落盘只进外置诱饵 Output Root，不写真实 Obsidian 库，碰了即 FAIL）。

## Product Goal

Video2Obsidian 是一个运行在 Apple Silicon Mac 上的零 API 成本、本地常驻视频知识入库工具：用户只需要把视频放入已经分类好的本地文件夹，系统自动完成本地 Whisper 转写、专业词增强、自然分段、目录镜像、Obsidian Markdown 安全写入和源视频安全归档（V1.8 §1.2）。目标设备：Mac mini M4 / 24GB RAM。本 Stage 只做其中“目录长什么样、笔记就长什么样”的那一块：在 Stage4 单文件 §48 映射（`OBSIDIAN_OUTPUT_ROOT/<source_relative_path_without_ext>.md` → 诱饵 Output Root + No-Clobber）之上，实现完整目录镜像——任意层级嵌套相对路径逐字节映射（`INPUT: AI/博主A/DeepSeek V4 分析.mp4 → CANONICAL: AI/博主A/DeepSeek V4 分析.md` §48 例）+ 父目录安全创建 + 真实名字原样保留（中文/Unicode/大小写/空格/`丨`/括号 §23/§73-35），并用同 Volume 真机故障矩阵证明 Identity 行为（NFC/NFD/大小写 §70 Case 14：`st_dev + st_ino / file id` 同实体判定优先，§23）。

## Current Stage

- Stage ID: Stage6 — Obsidian Path Mirror + Unicode / Case Tests（V1.8 §69）
- Goal: 纯路径映射函数（`input_root` + 源绝对路径 → `source_relative_path` → 诱饵 `output_root/<rel_without_ext>.md`，越界逃逸 BLOCK，遍历只认合成 Input Root）→ 父目录安全创建（`mkdir -p` 语义，存在文件挡路即 BLOCK 不覆盖）→ Unicode/Case 原样矩阵（中文/空格/`丨`/括号/NFC/NFD/大小写逐字节保留，无 encode/slugify/casefold/NFC 归一）→ 同实体判定（`st_dev+st_ino` 同文件优先，Case 14 同 Volume 真机验证）→ Mirror × Publish 集成（经 Stage4 `initial_publish` 语义复用：已存在 canonical 一律 BLOCK，Overwrite = 0，大小写冲突在大小写不敏感卷上亦 BLOCK 不合并）→ §73-34（Canonical 路径完整镜像原目录）+ §73-35（原样保留）可证明 → Stage1~5 回归（`src/stage1-5/` diff 为空，中央库 Stage6 前表行语义不变）。

Stage1~Stage5 地基复用约定（加法约束）：
```text
src/stage1/ 原样复用（import，不复制不修改）：sha256_file（Strong Hash 只读）
src/stage2/ 原样复用（import，不复制不修改）：candidate.discover（唯一发现入口，
  path_identity_key 原样存 §23）/ runs.get_or_create_auto_run（AUTO UPSERT）/
  store.require_lock
src/stage3/ 零调用（Stage6 不产生 Revision、不改 verdict 语义）
src/stage4/ 原样复用（import，不复制不修改）：volume_probe（§54 case_sensitive
  只读复用，不重探针不改门）/ publish.initial_publish（Mirror 算出的
  source_relative_path + output_root 透传调用，不复制其 No-Clobber 实现；
  conflict BLOCK 语义沿用）/ publish_commit（不复制不重写）
src/stage5/ 零调用（Stage6 不起 Watcher/Scan/Reconcile、不动启动链；三路语义
  由回归用例复现不断链）
src/stage6/ 新增：mirror.py / unicode_cases.py（命名以实现为准，前缀恒为 stage6，
  禁止 stage7+ 关键词文件名）
中央库位置：<data_root>/data/state.db（沿用 Stage2；Stage6 只读 sources/
  processing_runs/publish_records 行做断言，新增写仅允许经 stage4 publish
  语义产生的 publish_records/artifacts 行，normalization_revisions/
  render_revisions/archive_commits 行数不变，变即 FAIL）
输入目录：外置合成 Input Root（仓库外独立目录；嵌套层级 + Unicode 文件名一律
  合成生成，不扫真实视频目录）
输出目录：外置诱饵 Output Root（仓库外独立目录，模拟 OBSIDIAN_OUTPUT_ROOT；
  真实 Obsidian 库零触碰，见 P0-6 路径断言）
asr_profile_hash：Stage0/Stage1 冻结值字符串透传（身份计算用，不解析不执行模型）
Stage6 全程 Whisper 调用恒为 0（转写执行不属本 Stage）
```

## Stage P0（P0=本 Stage 非做不可、缺它不算完的事项，由 planner 初定、Task Manager 拍板；同时作为 qa / product-reviewer 的 P0 Blocking 参照。TM已拍板：按初定通过，本节即执行口径）

- [ ] P0-1 Path Mirror 纯映射可证明（§48 + §73-34 完整镜像原目录）：`mirror.py` 提供纯函数 `resolve_canonical(input_root, output_root, abs_source_path) -> {source_relative_path, canonical_output_path}`：相对路径 = `os.path.relpath` 相对合成 Input Root（Input Root 外绝对路径/ `..` 逃逸一律抛错 BLOCK，不得映射到 Output Root 外）；`canonical = output_root / <rel_without_ext> + .md`（仅末尾视频后缀 strip，大写后缀照收如 `.MP4`；中间点号不动）；嵌套层级逐级保留（`A/B/C.mp4 → A/B/C.md`，三层以上用例必含）；函数本身零写盘（写盘只由调用方经 Stage4 publish 语义触发，mirror 内出现 open/write/mkdir 即 FAIL）；映射结果与 Stage4 单文件 §48 口径逐字节一致（同一输入双算差一字节即 FAIL）。
- [ ] P0-2 Unicode/Case 原样保留可证明（§23 + §73-35 中文/Unicode/Case/空格/`丨`原样保留）：中文、空格、`丨`、圆括号/方括号、大小写混合文件名经 `resolve_canonical` + `discover()` 全链逐字节保留（`path_identity_key == abspath` 逐字节，`source_relative_path` 逐字节，`canonical_output_path` 除后缀替换外逐字节）；全链无 URL Encode/slugify/casefold/NFC 归一（`grep -rn "quote\|slug\|casefold\|normalize(\"NFC\"\|normalize('NFC'" src/stage6/` 零命中，出现即 FAIL）；Stage2 P0-4 `测试 中文丨Case (A)` 口径在本 Stage 由矩阵延续，不得回退为单例。
- [ ] P0-3 Case 14 故障矩阵可证明（§70 Case 14 + §23 同实体优先）：同一合成 Volume 上真机矩阵全 PASS：① NFC vs NFD 不同字节名 → 不同 `path_identity_key` → 不同 Logical Source（吞并即 FAIL；不得假设 `NFC+casefold` 等同 Volume 比较语义）；② 大小写仅差名（`Clip.mp4` vs `clip.mp4`）→ 不同 `path_identity_key` → 不同 Source（合并即 FAIL）；③ 同一实际文件实体（硬链接/同 `st_dev+st_ino`）→ Candidate 活跃期同实体识别，不因字节名拼写重复建 Logical Source（`st_ino` 断言举证）；④ 大小写不敏感卷冲突（`volume_probe.case_sensitive == False` 时两名映射到同一 canonical 拼写）→ 第二个 publish 一律 BLOCK（`BLOCKED_OUTPUT_EXISTS`/`BLOCKED_OUTPUT_CONFLICT`），Overwrite = 0，合并覆盖即 FAIL；⑤ 空格/`丨`/括号名 discover→PROMOTED→Source=1 链正常（任一字符类建不出 Source 即 FAIL）。
- [ ] P0-4 Mirror × No-Clobber 集成可证明（§49/§53 延续 + §52 Ownership 只读）：嵌套 mirror 路径经 Stage4 `initial_publish` 真实落诱饵 Output Root：父目录自动创建（`mkdir -p`，中途有同名文件挡路即 BLOCK 不删不覆盖）；canonical 缺席 → PUBLISHED（`expected_output_hash == published_hash`，半个文件永不算成功）；canonical 已存在（同内容/用户编辑/他进程抢建任一）→ 一律 BLOCK（`BLOCKED_OUTPUT_EXISTS`/`BLOCKED_OUTPUT_CONFLICT`，诱饵字节级不变，Overwrite = 0）；Ownership 五件套只用于恢复/诊断，不授权 Subsequent 自动覆盖（出现 force/overwrite/clobber 标志或环境变量后门即 FAIL）。
- [ ] P0-5 §72/§73 子集门可证明（仅属于 Stage6 的断言）：Atomic No-Clobber implementation PASS（经 mirror 嵌套路径仍 PASS）+ Output Race Fault Injection PASS（mirror 路径下抢建仍 BLOCK）+ Unknown/User-edited Markdown Overwrite = 0 PASS + Initial Publish PASS（嵌套 mirror 首发）+ Subsequent Render Revision 不自动覆盖 Canonical PASS + `PENDING_PUBLISH` / `CANONICAL_OUTPUT_EXISTS` PASS + §73-34（Canonical 路径完整镜像原目录）PASS + §73-35（中文/Unicode/Case/空格/`丨`原样保留）PASS + Case 14（NFC/NFD/大小写/中文/空格/`丨`/括号真机）PASS。
- [ ] P0-6 STOP EXPANSION 门可证明：`src/stage1/`、`src/stage2/`、`src/stage3/`、`src/stage4/`、`src/stage5/` git diff 为空；`normalization_revisions` / `render_revisions` / `archive_commits` 行数恒为 0（有新增写即 FAIL）；`sources.current_path`/`status`/`archived_at` 任一被写即 FAIL（Archive Level A/B/C 禁入）；Stage6 代码永不 import/调用 Whisper 执行入口（`run_asr_single_file`）、Prompt/Vocab 模块、VAD/Chunk 模块、Archive 模块、LaunchAgent、Menu Bar（grep 零命中举证）；目录镜像落盘只进诱饵 Output Root（真实 Obsidian 库零触碰，验收前断言输出路径前缀恒为诱饵 Root）。
- [ ] P0-7 外置合成验收门可证明（TM 已定）：一切输入路径位于外置合成 Input Root + 外置 Data Root + 外置诱饵 Output Root 内（验收前断言，与真实视频目录/真实 Obsidian 库无交集）；异常路径一律合成副本（原片不动，只动副本；canonical/笔记一律用诱饵文件，不碰真实笔记）；真实长视频一律不测（用例最大文件 ≤ 合成小文件，作为 PASS 条件写进报告）；任一用例触碰真实目录即 FAIL。

## In Scope

- §48 完整目录镜像映射（纯函数 + 越界 BLOCK + 嵌套保留 + 后缀 strip 大小写不敏感 + 与 Stage4 单文件口径一致）。
- 父目录安全创建（`mkdir -p` 语义；文件挡路 BLOCK；不删除不覆盖）。
- Unicode/Case 原样保留（中文/Unicode/大小写/空格/`丨`/括号逐字节；禁 encode/slugify/casefold/NFC 归一）。
- Case 14 同 Volume 真机故障矩阵（NFC/NFD/大小写/同实体 `st_dev+st_ino`/大小写不敏感冲突 BLOCK/空格`丨`括号 happy）。
- Mirror × Stage4 Publish 集成（`initial_publish` 只读复用透传；PUBLISHED/BLOCK 三分支延续；Overwrite = 0；Ownership 恢复/诊断用途）。
- §54 `case_sensitive` 只读复用（只读探针结果做冲突分支断言，不重实现卷探针）。
- §72 Implementation Acceptance Gate 中仅属于 Stage6 的断言子集（见 P0-5）+ §73-34/35。
- Stage1~5 回归（Stage1 per-job happy 仍 PASS；Stage2 discover→AUTO Run=1 仍 PASS；Stage3 verdict 链仍 PASS；Stage4 单文件 PUBLISHED 行仍可查；Stage5 Ready→Scan→Reconcile→RUNNING order 语义不断链；`src/stage1-5/` diff 为空）。

## Out of Scope

- Stage7 全部：Prompt + Vocabulary + Language Strategy（`asr_profile_hash` 只做不透明身份字符串透传，不实现 Profile 内容语义；Correction 规则不升级）。
- Stage8 全部：VAD + Chunk + Absolute Timeline（不重切分、不重排时间线；转写执行本身亦不在本 Stage）。
- Stage9（阈值调优）：任何阈值调优不做（Stable 门两轮间隔沿 Stage2 常量，不调优）。
- Stage10 全部：Archive A/B/C + `current_path` 更新（`archive_commits` 零新增写；`sources.current_path`/`status`/`archived_at` 任一被写即 FAIL）。
- Stage11 全部：LaunchAgent + 完整 Fault Injection Suite（本 Stage 只做 P0 指定的 Case 14 矩阵 + Output Race（mirror 路径）+ 越界 BLOCK 单测；Cold Boot、Absolute Binary Paths 不做）。
- Stage12 全部：Menu Bar。
- 真实 Obsidian 库写入/真实库镜像（本 Stage 落盘只进外置诱饵 Output Root；真实库路径出现于任一用例即 FAIL）。
- 显式 Replace/覆盖开关：§51 冻结——不提供任何 force/overwrite/clobber 标志或环境变量后门（存在即 FAIL）。
- 转写/改写执行：Whisper 调用、Normalization/Render 新 Revision 语义变更、Run 状态机推进（除经 Stage4 publish 回填 `initial_publish_record_id` 外）一律不做。
- 任何 §2.2 禁止项：AI 总结/改写/润色/校稿、LLM、云端 ASR、任何云 API、Redis/PostgreSQL、微服务、Docker、消息队列、RAG/Embedding/向量库、复杂 UI、Obsidian 插件、SaaS/手机端/浏览器上传、iCloud File Coordination、新模型、自动覆盖用户笔记、Reprocess UI、复杂历史版本 UI。
- 真实长视频测试与真实目录扫描/写入（用户明确：真实长视频一律不测直到产品完成；测试一律指向合成目录 + 诱饵 Output Root）。
- 不改 `src/stage1/`、`src/stage2/`、`src/stage3/`、`src/stage4/`、`src/stage5/`、不改 V1.8 架构基线、不动治理表（账本由执行链按 AGENTS 分工写，planner 不代写）、不 push、不碰 secrets。

## Task Breakdown

| Task ID | Priority | Role | Status | Notes |
|---|---|---|---|---|
| S6-T01 Path Mirror 纯映射 + 父目录安全创建（§48 全镜像） | P0 | builder | TODO | 输入：Stage4 `publish.initial_publish(input: source_relative_path/output_root)` 口径（只读复用，不复制 No-Clobber 实现）+ §48 例 + §73-34。输出：`src/stage6/mirror.py`（`resolve_canonical(input_root, output_root, abs_source_path)` 纯函数：`relpath` 相对合成 Input Root + `..`/盘外逃逸抛错 BLOCK + `canonical = output_root/<rel_without_ext>.md`（仅末尾视频后缀 strip，后缀表复 Stage5 `VIDEO_SUFFIXES` 大小写不敏感语义，不重定义冲突口径）+ 本函数零写盘（出现 open/write/mkdir 即 FAIL）；`ensure_parent_dir(canonical_path)`：`mkdir -p` 建父目录，同名文件挡路抛错 BLOCK 不删不覆盖）。验收：三层嵌套 `A/B/C.mp4→A/B/C.md` + 大写 `.MP4` 照映射 + 中间点号不动（`my.clip.v2.mp4→my.clip.v2.md`）+ 越界（`../escape.mp4`、Input Root 外绝对路径）抛错 + mirror 内写盘 grep 零命中 + 与 Stage4 单文件口径双算一致。禁动 `src/stage1-5/`；Whisper 调用 0；只映射路径，落盘只许经 S6-T03 调 stage4 语义进诱饵 Root。 |
| S6-T02 Unicode/Case 原样 + Case 14 故障矩阵（§23/Case14/§73-35） | P0 | builder | TODO | 输入：S6-T01 的映射函数 + Stage2 `candidate.discover`（唯一发现入口，只读复用）+ §23（`st_dev+st_ino` 同实体优先）+ §54 `case_sensitive` 只读。输出：`src/stage6/unicode_cases.py`（`MATRIX` 常量：中文/空格/`丨`/圆括号/方括号/NFC/NFD/大小写文件名清单，全合成生成；`assert_byte_preserved(abs_path, path_identity_key, source_relative_path, canonical_path)` 逐字节断言 helper；同实体判定 helper：`os.stat` 取 `st_dev+st_ino`，同实体不重复建 Logical Source）；模块内无归一化逻辑（出现 encode/slugify/casefold/NFC normalize 即 FAIL）。验收：矩阵每项 discover→PROMOTED→Source=1（空格/`丨`/括号 happy 必含）+ NFC vs NFD 不同 Source + `Clip.mp4` vs `clip.mp4` 不同 Source + 硬链接同实体不建新 Source（`st_ino` 举证）+ 大小写不敏感卷（或模拟 `case_sensitive=False`）双名同 canonical 拼写时第二个 BLOCK。禁动 `src/stage1-5/`；只用合成副本。 |
| S6-T03 Mirror × Publish 集成 + 冲突 BLOCK（§49/§53 延续） | P0 | builder | TODO | 输入：S6-T01–T02 + Stage4 `publish`/`conflict`/`volume_probe`（只读复用）。输出：集成路径（逻辑进 `src/stage6/__init__.py` 装配导出 + `publish_mirrored(input_root, output_root, abs_source_path, ...)`：`resolve_canonical` 算路径 → `ensure_parent_dir` → 透传 `source_relative_path/output_root` 调 Stage4 `initial_publish`，本模块不复制 No-Clobber/commit 实现，出现 commit 内联即 FAIL）。验收：嵌套首发 PUBLISHED（`expected==published` hash + 父目录自动建）+ 已存在同内容 BLOCK + 用户编辑（诱饵 canonical 写一字节）后重发 BLOCK 且诱饵字节不变 + 他进程抢建（tmp fsync 后 Final commit 前抢建同路径）BLOCK 且 Overwrite=0 + 大小写冲突第二个 BLOCK。禁动 `src/stage1-5/`；无 force/overwrite 后门；Whisper 调用 0。 |
| S6-T04 Stage6 验收套件 + §72/§73 子集门 + Stage1~5 回归 | P0 | qa（执行）+ builder（修） | TODO | 输入：S6-T01–T03 产物 + `src/stage1-5/` 只读复用。输出：Stage6 验收报告（happy 链 1 遍：合成嵌套 Unicode 视频→discover→mirror→诱饵 Output Root PUBLISHED→§73-34/35 双断言 + 异常路径至少 8 个：NFC vs NFD 不同 Source / 大小写不同 Source / 同实体硬链接不建新 Source / 大小写不敏感冲突 BLOCK / 越界逃逸 BLOCK / 父目录文件挡路 BLOCK / 用户编辑 BLOCK（Overwrite=0）/ Output Race 抢建 BLOCK；每个用例：前置/动作/期望 Count 或 exit 码/`Duplicate Source/Run=0` 证据/三表（normalization/render/archive 行数恒 0）证据/`current_path` 零写证据/Whisper 调用=0 证据/外置合成三 Root 路径证据/诱饵 canonical 字节证据；结论只落 qa 报告，HANDOFF 只记状态）+ 回归五行（Stage1 per-job happy 仍 PASS；Stage2 discover→AUTO Run=1 仍 PASS；Stage3 verdict 链仍 PASS；Stage4 单文件 PUBLISHED 仍可查；Stage5 Ready→Scan→Reconcile→RUNNING 语义不断链；`src/stage1-5/` git diff 为空）。验收：任一异常缺失、计数偏离、三表行数变动、有转写/发布越权写（非 stage4 语义）、真实目录/真实库被碰、结论写进 HANDOFF 代报告，均为 FAIL。 |

- 并行性说明：S6-T01 → T02 → T03 → T04 严格串行（纯映射→矩阵→集成→验收；T02 在映射口径未冻结前跑无逐字节可对；集成在矩阵语义前定会吞掉 NFC/大小写冲突证据；验收在三件未就绪前跑无收口可查）。
- 角色说明：S6-T01–T03 = builder 实现；S6-T04 = qa 执行验收 + builder 修；code-reviewer / product-reviewer / supervisor 按 AGENTS 派工顺序在计划完成后介入，本计划不代派。

## Risks

- R1 越界映射写到真实库：`relpath` 配错 root 会把 canonical 算进用户 Obsidian 库。缓解：TM 已定——输入/输出恒为外置三 Root；`resolve_canonical` 越界抛错硬门；验收前断言所有输出路径前缀恒为诱饵 Output Root。
- R2 “智能”归一化吞掉新 Source：NFC/NFD 或大小写顺手 `normalize/casefold` 最省事但违反 §23。缓解：S6-T02 硬门——逐字节断言 + 归一化关键词 grep 零命中；NFC vs NFD 不同 Source 用例强制双建。
- R3 大小写冲突静默覆盖：在大小写不敏感卷上第二个文件覆盖第一个最易“顺手合并”。缓解：S6-T03 硬门——冲突一律 BLOCK（复用 §53），Overwrite = 0 字节级举证；无 force 后门。
- R4 为复用改 stage1-5 原文：把 `initial_publish` 改成通用 mirror 函数或动锁语义最省事但违反加法约束。缓解：新增只进 `src/stage6/`；S6-T04 回归硬门——`src/stage1-5/` git diff 为空。
- R5 父目录创建删掉用户文件：`mkdir -p` 遇到文件挡路时顺手 `shutil.rmtree` 最危险。缓解：`ensure_parent_dir` 挡路抛错 BLOCK；用户编辑 BLOCK 用例强制诱饵字节不变。
- R6 真实长视频/真实目录误测：Unicode 矩阵用真实视频最“真实”但违反用户明确禁令。缓解：TM 已定——一律合成小文件副本；用例最大文件 ≤ 合成小文件写进报告 PASS 条件。
- R7 Stage7+ 提前实现：Prompt/Vocab、VAD/Chunk、`current_path` 回填最易“顺手”。缓解：S6-T04 三表行数快照对比 + `current_path` 列级 diff + Stage7+ 关键词 grep 零命中。
- R8 mirror 自造 No-Clobber 实现分叉：Stage6 内联 commit 会与 Stage4 口径分叉。缓解：S6-T03 硬门——只透传调 stage4，不复制实现；commit 内联 grep 零命中。

## Human Decisions Needed

- 无，按TM已定执行（本计划无阻塞项，不问人）。
- TM 已定事项备忘（执行，不复议）：① 外置测试目录（仓库外独立 Data Root + 独立合成 Input Root + 独立诱饵 Output Root，Stage1 `/tmp/s1t*` 与 Stage2 H2 外置目录模式延续）；② 异常路径一律用合成副本（原片不动，只动副本；canonical/笔记一律用诱饵文件，不碰真实笔记）；③ 真实长视频一律不测直到产品完成（用户明确，用例最大文件为合成小文件）；④ `src/stage1/` + `src/stage2/` + `src/stage3/` + `src/stage4/` + `src/stage5/` 只读加法（新增只进 `src/stage6/`，diff 为空为硬门）；⑤ STOP EXPANSION（Stage7+ 禁入：Prompt/Vocab、VAD/Chunk、阈值调优、Archive A/B/C + `current_path` 更新、LaunchAgent、Menu Bar 一律 Out；目录镜像只映射路径（落盘只进诱饵 Output Root，不写真实 Obsidian 库）；Unicode/大小写/空格/`丨`/括号全覆盖：NFC/NFD/大小写/中文/空格/`丨`/括号矩阵必跑，Case 14 同 Volume 真机验证）。
