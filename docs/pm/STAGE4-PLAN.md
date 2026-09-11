# PLAN｜Stage 4 Initial Canonical Publish + Atomic No-Clobber + Output Ownership（Video2Obsidian V1.8 §69）

> 基线：`docs/2026-09-10 丨 MAC 丨 GPT 网页端 丨 Video2Obsidian 本地视频自动转写工具开发计划-交接上下文 丨 V1.8.md`
> 基线状态：`V1.8 ARCHITECTURE FROZEN`（§71）+ Stage3 已验收（STAGE3-QA-REPORT：happy 1 遍 + 异常 6 个全过，39/39 断言双轮 exit 0；RenderRev 止于 `PUBLISH_EVALUATION`，verdict 双值 `PENDING_PUBLISH` / `CANONICAL_OUTPUT_EXISTS`，零 Canonical 写盘；`publish_records` / `archive_commits` 恒为 0）。
> Stage1+Stage2+Stage3 冻结输入：`src/stage1/`（job-scoped `data/jobs/<job_id>/` + per-job `job.sqlite` + Raw PREPARE/COMMIT + Immutable + Repair Forward）与 `src/stage2/`（Candidate/Source/AUTO Run + 中央 `<data_root>/data/state.db` + Single Instance 锁 + `publish_records`/`archive_commits` DDL schema-only）与 `src/stage3/`（`artifact_commit.py` / `normalize.py` / `render.py` / `derive.py` / `lineage.py`，RenderRev 止于 PUBLISH_EVALUATION + 诱饵 `CANONICAL_OUTPUT_EXISTS` 探针语义）——本 Stage 只做加法，不改 `src/stage1/`、`src/stage2/`、`src/stage3/` 任一文件（改了即 FAIL；新增只进 `src/stage4/`）。
> 最高约束：`STOP ARCHITECTURE EXPANSION`（§65-71）+ `STOP EXPANSION（Stage4 only）`——本 Stage 只实现 §69 Stage4 定义的事项（Initial Canonical Publish + Atomic No-Clobber + Output Ownership，§48/§49/§52/§53 + §50/§51 不覆盖策略 + §54/§55 卷能力门 + §12 Initial Publish 分支 + §35 `publish_records` 全字段），Stage5+（Watch/Scan/Reconcile、Path Mirror、Prompt/Vocab、VAD/Chunk、阈值调优、Archive、LaunchAgent、Menu Bar）一律 Out，写了即 FAIL。

## Product Goal

Video2Obsidian 是一个运行在 Apple Silicon Mac 上的零 API 成本、本地常驻视频知识入库工具：用户只需要把视频放入已经分类好的本地文件夹，系统自动完成本地 Whisper 转写、专业词增强、自然分段、目录镜像、Obsidian Markdown 安全写入和源视频安全归档（V1.8 §1.2）。目标设备：Mac mini M4 / 24GB RAM。本 Stage 只做其中“第一次落盘”的一块：在 Stage3 Rendered Artifact（内部 `data/jobs/<job_id>/render/<render_revision_id>.md`）与 `PUBLISH_EVALUATION` verdict 之上，实现首次 Canonical 发布——Canonical 路径按 §48（`OBSIDIAN_OUTPUT_ROOT/<source_relative_path_without_ext>.md`，测试用外置诱饵 Output Root，不碰真实笔记库）→ `expected_output_hash` 预持久化 → same-directory tmp → flush/fsync → Atomic No-Clobber Commit（§49，有 canonical 缺席才建，有即 BLOCK，永不覆盖 §50/§51/§53）→ Final Hash Verify → `publish_records` 行 `PUBLISHED` + Ownership 五件套（`render_revision_id` / `rendered_artifact_id` / `publish_record_id` / `expected_output_hash` / `published_hash` + SQLite + Manifest，§52，只用于 Crash Recovery / Ownership / Conflict 诊断，不授权 Subsequent 自动覆盖）→ Lineage 延伸到 Canonical Publish（§4 全链最后一环）→ Case 12 Output Race 可证明（发布瞬间他进程建 canonical，用户文件不变，Overwrite = 0）。

## Current Stage

- Stage ID: Stage4 — Initial Canonical Publish + Atomic No-Clobber + Output Ownership（V1.8 §69）
- Goal: 卷能力探针（§54 全字段 + §55 无可靠 No-Clobber 即 `BLOCKED_UNSUPPORTED_OUTPUT_FILESYSTEM`，Output 不允许 Reservation Copy Fallback）→ Atomic No-Clobber 发布 helper（§49 六步：Rendered → expected 预持久化 → same-dir tmp → flush/fsync → No-Clobber Commit → Final Hash Verify → `PUBLISHED`）→ Initial Publish 生命周期（§12 `PUBLISHING→PUBLISHED` 分支首次启用；Subsequent 分支保持 Stage3 语义：canonical 已存在→`PENDING_PUBLISH` / `CANONICAL_OUTPUT_EXISTS`，零写盘）→ `publish_records` 写行（§35 全字段：`publish_record_id/render_revision_id/canonical_output_path/expected_hash/publish_mode/status/published_hash/created_at/published_at`；状态机 `PENDING→PUBLISHING→PUBLISHED` 主链 + `PENDING_PUBLISH/CANONICAL_OUTPUT_EXISTS/BLOCKED_OUTPUT_EXISTS/BLOCKED_OUTPUT_CONFLICT` 旁路）→ Output Conflict 三分支（§53：Ownership+Hash 可证是当前未完成 Initial Publish→Recovery Forward；其他→`BLOCKED_OUTPUT_EXISTS` / `BLOCKED_OUTPUT_CONFLICT`；绝不覆盖）→ Ownership 落盘（§52 五件套 + Manifest publish receipt + Run `initial_publish_record_id` 回填只写该一列语义见 S4-T03）→ Lineage 延伸（`get_lineage` 全链追加 Canonical Publish 环，缺环标缺不编造）→ Case 12 + §72 Canonical Publish 门可证明（No-Clobber / Output Race / Unknown-User-edited Overwrite=0 / Initial Publish / Subsequent 不自动覆盖 / verdict 双值）。

Stage1+Stage2+Stage3 地基复用约定（加法约束）：
```text
src/stage1/ 原样复用（import，不复制不修改）：COMMITTED raw.json 只读输入 /
  validate_raw_artifact / guarded_open_raw_for_write（Raw 写保护）/
  PREPARE→COMMIT→Receipt 语义（本 Stage 为 Canonical Publish 新实现一份，
  不得把 stage1/stage3 的内部 Artifact 专用函数改成通用函数）
src/stage2/ 原样复用（import，不复制不修改）：open_db（持锁断言）/
  init_db 建好的 publish_records 表（本 Stage 起对 publish_records 正式写行，
  archive_commits 仍 schema-only 零写入）/ instance.acquire 持锁写库 /
  Run 状态只读（Stage4 不推进、不回滚任何 Run 状态；仅回填
  initial_publish_record_id 一列，见 S4-T03 验收列级断言）
src/stage3/ 原样复用（import，不复制不修改）：evaluate_publish  verdict 语义
  （PENDING_PUBLISH=缺席可发布 / CANONICAL_OUTPUT_EXISTS=存在不覆盖）/
  Rendered Final 只读输入 / derive 的 Whisper guard（本 Stage 亦永不 import
  run_asr_single_file，调用计数恒 0）
src/stage4/ 新增：volume_probe.py / publish_commit.py / publish.py / conflict.py / lineage_ext.py
中央库位置：<data_root>/data/state.db（沿用 Stage2；per-job job.sqlite 与 Manifest 原地不动，只追加 Publish Receipt）
Canonical 输出：外置诱饵 Output Root（仓库外独立目录，模拟 OBSIDIAN_OUTPUT_ROOT §48 相对路径映射；真实 Obsidian 库零触碰，见 S4-T06 路径断言）
Rendered 输入：Stage3 链在合成输入上产出的 COMMITTED Rendered（T01→T05 happy 复用，不手写 rendered.md 绕过校验）；Stage4 全程 Whisper 调用恒为 0
```

## Stage P0（P0=本 Stage 非做不可、缺它不算完的事项，由 planner 初定、Task Manager 拍板；同时作为 qa / product-reviewer 的 P0 Blocking 参照。TM已拍板：按初定通过，本节即执行口径）

- [ ] P0-1 卷能力门可证明（§54/§55 + §3.14）：`volume_probe.py` 返回 §54 九字段（`filesystem_type/volume_id-st_dev/local_or_remote/case_sensitive/supports_atomic_rename/supports_exclusive_rename/supports_exclusive_create/supports_hardlink/supports_advisory_lock`）；无可靠 Atomic No-Clobber（既无 exclusive rename 又无 `O_CREAT|O_EXCL`）→ `BLOCKED_UNSUPPORTED_OUTPUT_FILESYSTEM` 拒绝发布；Output 不允许 Reservation Copy Fallback（有 fallback 即 FAIL）；iCloud/network/remote root → `BLOCKED_UNSUPPORTED_ROOT_FOR_V1`（§3.14）。
- [ ] P0-2 Atomic No-Clobber 发布可证明（§49 六步）：Rendered → `expected_output_hash` 预持久化（中央 `publish_records` 行 `PENDING` + `artifacts` 行 PREPARED，二者缺一即 FAIL）→ same-directory tmp → flush/fsync → Atomic No-Clobber Commit（`O_CREAT|O_EXCL` 独占创建，无竞态窗口；`link(2)`/rename 覆盖路径不存在即 FAIL）→ Final Hash Verify（`published_hash == expected_hash`，不等永判无效）→ `PUBLISHED`。半个 Canonical（hash 不等）永不视为成功。
- [ ] P0-3 Initial Publish 生命周期可证明（§12 Initial 分支 + §35 全字段）：`PENDING→PUBLISHING→PUBLISHED` 主链行写入中央 `publish_records`（§35 九字段齐全），状态变迁记 `state_events`；`publish_mode=INITIAL`；`canonical_output_path` 落 §48 相对映射；`published_at` 仅 PUBLISHED 置值。Subsequent 分支保持 Stage3 语义（canonical 已存在时只记 `PENDING_PUBLISH` / `CANONICAL_OUTPUT_EXISTS`，零写盘、零 `publish_records` 新行或只记 verdict 行见 S4-T04 定义二选一文档化）。
- [ ] P0-4 Subsequent 默认不覆盖可证明（§50/§51 + §3.10/§3.11）：canonical 已存在时无论 DB 能否证明旧 Canonical 出自本工具，一律不覆盖（§51：用户可能已手工编辑）；新的 Rendered 只42466192内部 Artifact，`CANONICAL_OUTPUT_EXISTS` 诱饵字节级不变；Unknown/User-edited Markdown Overwrite = 0（§3.11；向 canonical 诱饵写一字节“用户编辑”后重发 publish，必须 BLOCK 且诱饵保留用户字节）。
- [ ] P0-5 Output Conflict 三分支可证明（§53 + §52 Ownership）：Final 已存在时：① Ownership + Hash 可证是当前未完成 Initial Publish（`publish_record_id` 对上 + `expected_hash == final hash` + 状态 `PUBLISHING`）→ Recovery Forward（补 Receipt + 置 `PUBLISHED`，不重建 tmp）；② 其他一切情况 → `BLOCKED_OUTPUT_EXISTS`（同内容/空文件亦 BLOCK 不静默认领）或 `BLOCKED_OUTPUT_CONFLICT`（内容不同且 Ownership 对不上）；③ 绝不覆盖（任一分支出现 canonical 字节减少/被截断/被替换即 FAIL）。Ownership 五件套（§52）落 SQLite + Manifest，只用于恢复/诊断，不授权 Subsequent 自动覆盖。
- [ ] P0-6 Case 12 Output Race 可证明（§70 Case 12）：`PUBLISHING` 瞬间他进程创建 canonical（测试用子进程/线程在 tmp fsync 后 Final commit 前抢建同路径不同字节文件）→ 本进程 commit 必须失败为 BLOCK（`BLOCKED_OUTPUT_EXISTS`/`BLOCKED_OUTPUT_CONFLICT`），用户（抢建方）文件字节级不变，本进程 Overwrite = 0，且 `publish_records` 行终态为 BLOCK 系而非 `PUBLISHED`。
- [ ] P0-7 Lineage 延伸 + Run 回填可证明（§4/§41 + §32）：`get_lineage` 全链追加 Canonical Publish 环（Source→Run→Raw→NormRev→Normalized→RenderRev→Rendered→Canonical Publish：`publish_record_id/canonical_output_path/published_hash/status`），缺环标 missing 不编造；Run 行仅 `initial_publish_record_id` 一列被回填（列级 diff 断言：除该列 + `updated_at` 外 Run 行其余列不变，状态保持 COMPLETED）；Manifest 追加 Publish Receipt（只追加不改写历史条目）。
- [ ] P0-8 STOP EXPANSION 门可证明：`archive_commits` 行数恒为 0（有行即 FAIL）；`src/stage1/`、`src/stage2/`、`src/stage3/` git diff 为空；异常路径一律合成副本 + 诱饵 Output Root，真实长视频与真实 Obsidian 库零触碰；Stage4 代码永不 import/调用 Whisper 执行入口（`run_asr_single_file`），测试以调用计数 = 0 举证；Watch/Scan/Reconcile、Archive A/B/C、`current_path` 更新、Menu Bar、Path Mirror、Prompt/Vocab、VAD/Chunk、阈值调优任一出现即 FAIL。

## In Scope

- 卷能力探针与 Output 门（§54 全字段 + §55 BLOCK 语义 + §3.14 root 门；只探针不修复文件系统）。
- Atomic No-Clobber 发布 helper（§49 六步，面向 Canonical MD，落外置诱饵 Output Root §48 映射）+ 中央 `publish_records` 行（`PENDING→PUBLISHING→PUBLISHED`）+ `artifacts` 行（PREPARED→COMMITTED，canonical 类型）+ Manifest Publish Receipt 追加 + `state_events` 变迁记录。
- Initial Publish 生命周期（§12 Initial 分支首次启用；`publish_mode=INITIAL`；Final Hash Verify；`published_at`）。
- Subsequent 不覆盖策略（§50/§51：`PENDING_PUBLISH` / `CANONICAL_OUTPUT_EXISTS`，零写盘）+ Output Conflict 三分支（§53：Recovery Forward / `BLOCKED_OUTPUT_EXISTS` / `BLOCKED_OUTPUT_CONFLICT`，绝不覆盖）+ Ownership 五件套（§52：恢复/诊断用途，不授权覆盖）。
- Lineage 延伸（§4 最后一环 + Manifest Lineage Metadata + 中央库可查询组装；Stage3 `lineage.py` 只读复用，新增只进 `src/stage4/lineage_ext.py`）。
- §72 Implementation Acceptance Gate 中仅属于 Stage4 的断言子集：Atomic No-Clobber implementation / Output Race Fault Injection / Unknown-User-edited Overwrite=0 / Initial Publish / Subsequent 不自动覆盖 / `PENDING_PUBLISH` / `CANONICAL_OUTPUT_EXISTS`。
- Stage1 回归（per-job T01→T06 happy 仍可复现）+ Stage2 回归（discover→PROMOTED→Source=1→AUTO Run=1 链仍 PASS）+ Stage3 回归（COMMITTED Raw→NormRev COMPLETED→Rendered→verdict 链仍 PASS，`publish_records` 非空口径变更见 S4-T06：stage2 原 `assert_stage3_tables_empty` 四表口径中 `publish_records` 本 Stage 起正式写行，builder 不得改 `src/stage2/`，Stage4 自带 `archive_commits` 为空断言）。

## Out of Scope

- Stage5 全部：Watch First + Startup Scan + Reconciliation 真实实现（本 Stage 的 Rendered 输入来自 Stage3 指定路径复用，不起监听、不扫 Input 目录、不补跑视频）。
- Stage6 全部：Obsidian Path Mirror + Unicode/Case 完整故障套件（本 Stage 只按 §48 相对路径映射写诱饵 Output Root，不做真实库镜像、不跑 NFC/NFD/大小写真机套件；大小写冲突只按 §53 判 BLOCK 不解决）。
- Stage7 全部：Prompt + Vocabulary + Language Strategy（Correction/Render 侧沿 Stage3 冻结版，不做语义升级）。
- Stage8 全部：VAD + Chunk + Absolute Timeline（不重切分、不重排时间线）。
- Stage9（阈值调优）：Paragraph 阈值沿 Stage3 版本化定值，不调优。
- Stage10 全部：Archive A/B/C + `current_path` 更新（`archive_commits` 空表零写入；Source 行不碰，`current_path`/`status`/`archived_at` 任一被写即 FAIL）。
- Stage11 全部：LaunchAgent + 完整 Fault Injection Suite（本 Stage 只做 §53 三分支 + Case 12 Output Race 指定的恢复/竞态单测）。
- Stage12 全部：Menu Bar。
- 显式 Replace/显式 Publish UI：§51 冻结——未来安全 Replace 须单独设计，不属于 V1.8，本 Stage 不提供任何覆盖开关、force 标志、环境变量后门（存在即 FAIL）。
- 任何 §2.2 禁止项：AI 总结/改写/润色/校稿、LLM、云端 ASR、任何云 API、Redis/PostgreSQL、微服务、Docker、消息队列、RAG/Embedding/向量库、复杂 UI、Obsidian 插件、SaaS/手机端/浏览器上传、iCloud File Coordination、新模型、自动覆盖用户笔记、Reprocess UI、复杂历史版本 UI。
- 真实长视频测试与真实 Obsidian 库写入（用户明确：真实长视频一律不测直到产品完成；本 Stage 只用合成小文件/副本 + 诱饵 Output Root + 诱饵 canonical md）。
- 不改 `src/stage1/`、`src/stage2/`、`src/stage3/`、不改 V1.8 架构基线、不动治理表（账本由执行链按 AGENTS 分工写，planner 不代写）、不 push、不碰 secrets。

## Task Breakdown

| Task ID | Priority | Role | Status | Notes |
|---|---|---|---|---|
| S4-T01 卷能力探针 + Output 门 | P0 | builder | TODO | 输入：§54/§55 + §3.14。输出：`src/stage4/volume_probe.py`（`probe_volume(path)` 返回 §54 九字段实测值：`filesystem_type/volume_id-st_dev/local_or_remote/case_sensitive/supports_atomic_rename/supports_exclusive_rename/supports_exclusive_create/supports_hardlink/supports_advisory_lock`，以 `os.stat/st_dev` + `O_CREAT\|O_EXCL` 探针文件 + 同目录 rename 探针实测，不编造；`gate_output_root(path)`：无可靠 No-Clobber（exclusive rename 与 O_EXCL 皆无）→ 抛 `BlockedUnsupportedOutputFilesystem`；iCloud/network/remote root 特征 → 抛 `BlockedUnsupportedRoot`；publish 前必调 gate，不调即 FAIL）。验收：本机 APFS 外置测试目录探针 9 字段全非空 + 模拟无能力卷（monkeypatch supports_*=False）gate 抛 BLOCK + Output 无 fallback 路径（grep `Reservation Copy`/`fallback` 在 stage4 输出发布路径零命中）。禁动 `src/stage1-3/`。 |
| S4-T02 Atomic No-Clobber 发布 helper | P0 | builder | TODO | 输入：S4-T01 + Stage3 S3-T01 的 §38/§39 语义（只读照抄思路，不改原文）+ §49。输出：`src/stage4/publish_commit.py`（`prepare_publish(con, rendered_final_path, canonical_path, publish_record_id)`：读 Rendered Final 字节→`expected_output_hash`=SHA256→中央 `publish_records` 行 `PENDING`（§35 全字段，`publish_mode=INITIAL`）+ `artifacts` 行 PREPARED→COMMIT 事务；`commit_publish(...)`：gate 复检→same-dir tmp→flush→fsync→`O_CREAT\|O_EXCL` 独占建 Final（存在即停，零截断）→final hash 校验→`publish_records` 置 `PUBLISHED` + `published_hash/published_at`→Manifest 写 PUBLISHED Receipt→SQLite COMMITTED；`recover_publish(...)`：§53 分支① PUBLISHING + Final 在 + hash==expected→Repair Forward，其余判 BLOCK 系；hash 不等永判无效）。验收：happy（无 canonical→PUBLISHED + 三方 hash 一致：expected==final==行记录）+ tmp-only 续 Commit 用例 + final 篡改判无效用例 + 全程 Whisper 调用 0。Canonical 一律落外置诱饵 Output Root。 |
| S4-T03 Initial Publish 生命周期（PUBLISHING→PUBLISHED 首次启用） | P0 | builder | TODO | 输入：S4-T02 + Stage3 `evaluate_publish` verdict（只读）+ §12/§35/§48。输出：`src/stage4/publish.py`（`initial_publish(con, job_dir, render_revision_id, output_root, source_relative_path)`：verdict 缺席（`PENDING_PUBLISH`）→ §48 映射算 `canonical_output_path` → `PENDING→PUBLISHING→PUBLISHED`（经 S4-T02，变迁记 `state_events`）；verdict 存在（`CANONICAL_OUTPUT_EXISTS`）→ 直接走 S4-T04 不覆盖分支，本函数零写盘；成功回填 Run 行仅 `initial_publish_record_id` + `updated_at` 两列；模块内 Subsequent 自动覆盖路径不存在，存在即 FAIL）。验收：happy（1 RenderRev→1 publish_record PUBLISHED + Run 回填列级 diff 仅两列变 +诱饵 Output Root 落 canonical md + state_events 变迁齐）+ 已存在分支零写盘用例。 |
| S4-T04 Subsequent 不覆盖 + Conflict 三分支 | P0 | builder | TODO | 输入：S4-T02 + S4-T03。输出：`src/stage4/conflict.py`（`publish_or_block(...)`：canonical 缺席→调 S4-T03 Initial；canonical 存在→§53 判定：行状态 PUBLISHING + `expected_hash==final sha256` + `publish_record_id` 对上→Recovery Forward（S4-T02）；否则内容相同→`BLOCKED_OUTPUT_EXISTS`，内容不同/对不上→`BLOCKED_OUTPUT_CONFLICT`；所有 BLOCK 分支 canonical 字节级不变，Overwrite 计数恒 0；§51 文档化：`publish_records` 对 BLOCK 行是否落 verdict 行二选一，选定后 S4-T06 按同一口径验收）。验收：Case A 用户编辑诱饵（改一字节）→BLOCK + 诱饵保留用户字节 + Overwrite=0；Case B 同字节重发→BLOCK 系非 PUBLISHED；Case C PUBLISHING 崩溃残留 + hash 对上→Forward 得 PUBLISHED。 |
| S4-T05 Lineage 延伸到 Canonical Publish | P0 | builder | TODO | 输入：S4-T03–T04 落盘的行与文件 + §4/§41/§52。输出：`src/stage4/lineage_ext.py`（只读复用 `src/stage3/lineage.py` 的 `get_lineage`，不改原文：`get_lineage_with_publish(source_id_or_run_id, data_root)` 在 Stage3 全链后追加 Canonical 环 `publish_record_id/canonical_output_path/expected_hash/published_hash/status`；`record_publish_receipt(manifest, ...)`：Manifest 追加 Publish Receipt + Ownership 五件套（§52），只追加不改写历史条目；缺环显式标 missing 不编造）。验收：一条完整链（1 Raw→1 NormRev→1 Rendered→1 PUBLISHED）查询返回全链 ID 与 hash + Manifest 含 Publish Receipt；无 publish 的 source 查询标 `publish=missing` 非异常。 |
| S4-T06 Stage4 验收套件 + §72 子集门 + Stage1/2/3 回归 | P0 | qa（执行）+ builder（修） | TODO | 输入：S4-T01–T05 产物 + `src/stage1/`、`src/stage2/`、`src/stage3/` 只读复用。输出：Stage4 验收报告（happy 链 1 遍：COMMITTED Rendered→verdict 缺席→PUBLISHED→Ownership 五件套 + 异常路径至少 7 个：Case 12 Output Race / 用户编辑 BLOCK / 同字节重发 BLOCK / PUBLISHING 残留 Forward / tmp-only 续 Commit / Final hash 篡改判无效 / 无能力卷 BLOCK；每个用例：前置/动作/期望状态或 exit 码/`archive_commits` 行数=0 证据/Whisper 调用=0 证据/Rendered 与 Raw hash 不变证据/诱饵 Output Root 内用户文件字节不变证据/Run=COMPLETED 证据/Overwrite=0 证据；结论只落 qa 报告，HANDOFF 只记状态）+ 回归三行（Stage1 per-job T01→T06 happy 仍 PASS 且 `src/stage1/` diff 为空；Stage2 discover→AUTO Run=1 仍 PASS 且 `src/stage2/` diff 为空；Stage3 COMMITTED Raw→verdict 链仍 PASS 且 `src/stage3/` diff 为空；Stage4 自带 `archive_commits` 为空断言通过——stage2 原 `assert_stage3_tables_empty` 四表口径中 `publish_records` 已被本 Stage 正式写行取代，不得要求它通过，不得为此改 `src/stage2/`）。验收：任一异常缺失、计数偏离、`archive_commits` 非空、有 Raw/Rendered 写、诱饵用户字节被改、force/覆盖后门存在、结论写进 HANDOFF 代报告，均为 FAIL。 |

- 并行性说明：S4-T01 → T02 → T03 → T04 → T05 → T06 严格串行（探针→helper→生命周期→冲突策略→Lineage→验收；T04 的 BLOCK 口径在 T03 之前定会污染“存在即停”证据；Lineage 查询在 publish 落盘前跑会缺环；Case 12 竞态用例在 helper 未就绪前跑无 commit 窗口可抢）。
- 角色说明：S4-T01–T05 = builder 实现；S4-T06 = qa 执行验收 + builder 修；code-reviewer / product-reviewer / supervisor 按 AGENTS 派工顺序在计划完成后介入，本计划不代派。

## Risks

- R1 builder“顺手”实现 Subsequent 自动覆盖：§51 读到 Ownership 可证就想 replace。缓解：S4-T03 硬门——Subsequent 路径只记 verdict/BLOCK，模块内无覆盖写盘分支 + 验收用诱饵字节比对 + force/覆盖标志 grep 零命中；出现覆盖即 FAIL（显式 Replace 不属 V1.8）。
- R2 为复用改 stage1/stage3 原文：把内部 Artifact prepare/commit 改成通用发布函数最省事但违反加法约束。缓解：S4-T02 独立新文件实现；S4-T06 回归硬门——`src/stage1/`、`src/stage2/`、`src/stage3/` git diff 为空。
- R3 stage2 四表空断言被 publish 写行顶翻：`assert_stage3_tables_empty` 覆盖 `publish_records`，Stage4 落盘后它必 FAIL，有人会去“修” stage2。缓解：S4-T06 明确——不得改 `src/stage2/`，Stage4 自带 `archive_commits` 子集断言；qa 报告写清口径变更原因（`publish_records` 本 Stage 起正式写行）。
- R4 No-Clobber 被 rename 覆盖冒充：`os.rename` 在 POSIX 会静默覆盖，Case 12 形同虚设。缓解：S4-T02 硬门——只许 `O_CREAT|O_EXCL` 独占创建（macOS APFS 可用），rename 只用于 same-dir tmp 内部流转、永不直接落 Final；Case 12 用抢建子进程实测竞态窗口。
- R5 Run 回填顺手扩散：回填 `initial_publish_record_id` 时把 Run 状态机也“推进”了。缓解：S4-T03 列级 diff 断言——除该列 + `updated_at` 外 Run 行其余列不变，状态保持 COMPLETED；S4-T06 回归复查。
- R6 诱饵 Output Root 配成真实库：用例误配真实 Obsidian 库，BLOCK 用例真把用户笔记截断。缓解：TM 已定——一律外置诱饵 Output Root + 合成副本；验收前断言所有 canonical 路径位于外置测试目录内，与真实笔记库无交集；用户编辑用例只编辑诱饵副本。
- R7 真实长视频/真实笔记被触碰：用例误配真实目录。缓解：TM 已定——真实长视频一律不测；验收前断言所有输入路径位于外置测试目录内。

## Human Decisions Needed

- 无，按TM已定执行（本计划无阻塞项，不问人）。
- TM 已定事项备忘（执行，不复议）：① 外置测试目录（仓库外独立 Data Root + 独立诱饵 Output Root，Stage1 `/tmp/s1t*` 与 Stage2 H2 外置目录模式延续）；② 异常路径一律用合成副本（原片不动，只动副本；canonical 用诱饵文件，不碰真实笔记）；③ 真实长视频一律不测直到产品完成（用户明确）；④ `src/stage1/` + `src/stage2/` + `src/stage3/` 只读加法（新增只进 `src/stage4/`，diff 为空为硬门）；⑤ STOP EXPANSION（Stage5+ 不实现：Watch/Scan/Reconcile、Path Mirror、Prompt/Vocab、VAD/Chunk、阈值调优、Archive、LaunchAgent、Menu Bar 一律 Out，`archive_commits` 零写入；Canonical Publish 默认不覆盖用户笔记 No-Clobber §50/§51；Ownership 五件套归属明确 §52，只用于恢复/诊断，不授权覆盖）。
