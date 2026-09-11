# BUGS｜FINAL-REGRESSION（产品完成前最后一验）

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| 无（业务侧） | — | 否 | 19/19 PASS，三轮坏例exit码符合预期 | CLOSED | 无需 builder 修 | 详见 `/tmp/finalqa/finalqa_results.json` |

- QA：qa（opencode-go/glm-5.3-flash，本窗口 subagent；未改业务代码，只写本报告）
- 被测：`src/stage1/`~`src/stage12/` 全量（只读复用 + 黑盒调用；业务零改）
- 计划：本窗口任务目标（P1×5 + A-cross + Stage6加2例 + 全链12段 + §72全量子集门；合成小文件；长视频不测；坏例看exit码；结论只落本报告）
- QA 执行目录（仓库外）：`/tmp/finalqa/`（各用例独立三/五 Root + 确定性合成小文件 + 诱饵 Output/Archive + `finalqa_results.json`）+ `/tmp/finalqa_run.py`（仓库外 Runner，`--bad space/wrongdir/stopscan/across/noclobber` 五子进程取 exit 码）；仓库内零写盘除本报告
- **结论：PASS（P1×5全过 + A-cross正式例过 + Stage6加2例过 + 全链12段过 + §72全量子集复述齐；19/19断言一轮全绿，Runner exit 0；坏例只看 exit 码：space/wrongdir/stopscan/across exit 1、noclobber exit 2符合预期；Whisper 恒 0；最大合成文件 12288B（合成小文件门内，真实长视频零触碰）；结论只落本报告）**

## 1. P1×5回归（render中途续行/幂等verdict稳定/stop后隐式scan被拒/首尾空格BLOCK/错目录必raise）

| P1 | 来源 | 动作 | 期望 | 实测 | exit/Count |
|---|---|---|---|---|---|
| render中途续行 | STAGE3-CODE-REVIEW P1-1（`render.py:349`） | 新库 + 合成 Raw→Norm→新 Render profile 手工置 `RENDERING`（无 artifact，模拟崩溃在 RENDERING→COMMITTING 间）→同 profile 重调 | 续至 `PUBLISH_EVALUATION`（非“另起 profile”抛错），`whisper 0` | 一致（`rendrev_89f46d0c7e7e→PUBLISH_EVALUATION`） | Count 1 |
| 幂等verdict稳定 | STAGE3-CODE-REVIEW P1-2（`render.py:330-348`） | 同 rev 先 `PENDING_PUBLISH`（诱饵缺席）→诱饵后建→同 rev 重调 | 仍 `PENDING_PUBLISH`，`evidence=manifest/state_events`，不翻转 `CANONICAL_OUTPUT_EXISTS` | 一致（`v1/v2 PENDING_PUBLISH`，`ev=manifest`） | Count 1 |
| stop后隐式scan被拒 | STAGE5-CODE-REVIEW P1-1（`watcher.py:162-176`） | `start_watch→wait_ready→stop` 后 `is_ready=False` + `find_ready=None` →无 watcher `startup_scan` | `WatcherNotReadyError`（`SCAN-AFTER-STOP-BLOCK`） | 一致 | 子进程 `--bad stopscan` exit **1** + in-process BLOCK |
| 首尾空格BLOCK | STAGE6-CODE-REVIEW P1-1（`mirror.py:19-49` vs `publish_commit.py:121 strip`） | `resolve_canonical(ir,out,ir/" lead.mp4")` | `MirrorEscapeError`（fail-closed，不静默错映射） | 一致 | 子进程 `--bad space` exit **1** |
| 错目录必raise | STAGE6-CODE-REVIEW P1-2（`unicode_cases.py:22-40`） | `assert_byte_preserved(...,rel="A/B/C.mp4",canonical="/evil/X/Y/C.md",output_root=诱饵)` | `AssertionError`（前缀门 + dirname 逐级门） | 一致（正确嵌套仍 `ok True`） | 子进程 `--bad wrongdir` exit **1** |

## 2. A-cross正式例（Stage10 level_a跨盘删源前源复验）

- 来源：STAGE10-CODE-REVIEW P1-1（`level_a.py:146-185`，`_move_cross_device` 删源前缺源复验；`level_b._finish_after_valid_final:234-239` 同语义）。
- 动作：单盘强制跨盘分支（`_same_device→False`，U-6式声明见未闭环）+ hook 在 tmp fsync + `link` 提交后、删源前改源首字节 `A→B`（一字节）。
- 期望：拒删源（`ArchiveError: source changed during copy … source kept`）、源保留新字节（`B…` 1024B）、Final 保留旧字节（`A…` 1024B）。
- 实测：一致（`refused True/src_new True/final_old True`；in-process + `--bad across` exit **1** 双证据）。

## 3. Stage6加2例（首尾空格BLOCK或双算一致；错目录helper必raise）

- E-S6-1 首尾空格BLOCK **或** 双算一致：` lead.mp4→MirrorEscapeError BLOCK`（P1-S6-1）+ 常规名双算一致（`AI/x/DeepSeek V4 test.mp4` 经 `resolve_canonical` vs `canonical_path_for` 逐字节等；`A/B/C.mp4→A/B/C.md`）。
- E-S6-2 错目录helper必raise：`A/B/C.mp4→/evil/X/Y/C.md` 必 `AssertionError`（P1-S6-2）；正确 `out/A/B/C.md` 仍 `ok True`（向后兼容 `output_root=None` 只验尾巴）。

## 4. 全链回归（Stage1~Stage12）

| 段 | 动作 | 期望 | 实测 |
|---|---|---|---|
| S1 happy端到端 | `probe_volume(/tmp)=ALLOW` + `ingest_specified_path` 脚手架→合成 asr 四件→`prepare_raw PREPARED`→`commit_raw COMMITTED` | PREPARED→COMMITTED | 一致 |
| S2 Triple Race | 同文件 3 并发 `discover`（ThreadPool） | Source=1 + AUTO Run=1 | 一致（1/1） |
| S3 Case4/5 | `corr-v1 vs corr-v2` hash 不等 + `para-v1 vs s9-para-v2` hash 不等 + revision_id 不等 | Case4/5 各 mint 新 rev | 一致 |
| S4 No-Clobber | 合成链至 Rendered→`initial_publish PUBLISHED`（`expected_output_hash==published_hash`）→同参重发 | 第二次 `BLOCKED_OUTPUT_EXISTS`，诱饵不变 | 一致（in-process + `--bad noclobber` exit **2**） |
| S5 startup 11步 | `run_startup` | order 逐字 11步 + RUNNING | 一致（11/11） |
| S6 双算 | `resolve_canonical` vs `canonical_path_for` | 逐字节等 | 一致 |
| S7 接线 | vocab 快照翻转 + 精确词 + `explicit-zh` + 合成 16k mono wav `check_wav_mono_16k` | 快照不等 + `has_exact True` + wav 1ch/16k | 一致（whisper 0，未真调引擎） |
| S8 chunk | `plan_chunks(601)` | 2 chunk 起点 `[0.0,598.0]` + 非法 0 拒收 | 一致 |
| S9 Case4/5 | `s9-corr-v2` 纠正 `Github→GitHub` + `para-v2` 规则序 `all_pass` + 长改写 `RulesError` | 双派生 + 护栏 | 一致（whisper 0） |
| S10 A/B | `level_a` 同盘成功 + `level_b` 预置 hash 成功 | 双 `ARCHIVE_COMMITTED` + 源删 + hash 等 | 一致 |
| S11 故障套件 | `fault_suite.run_all`（无 boot 直调，P1-1 预持锁语义） | `PASS 11/11` + `running_probe PASS` + max≤65536 | 一致（`11/11 max 2816`） |
| S12 快照 | `discover` 后 `collect(limit=5)` 前后 DB mtime 不变 | `ok True` + counts 含 sources/runs + 只读 | 一致 |

Runner：`/tmp/finalqa_run.py` → `/tmp/finalqa/finalqa_results.json`（19/19 JSON 已落盘，可复算；`TOTAL 19/19 FAILS=[] exit=0 max=12288`）；坏例子进程：`space exit 1` + `wrongdir exit 1` + `stopscan exit 1` + `across exit 1` + `noclobber exit 2`（判据只用 exit 码，不看打印）；最大合成文件 12288B（FULL-S11 输入/work 扫描最大值；S11 套件内最大 2816B；上限合成小文件门内；真实长视频零触碰；文本/ASR 内容不断言）；Whisper 全链 0（S7/S9 纯函数 + S8 纯切分 + S11 套件 `whisper 0` + 其余 DB/映射/快照零引擎）。

## 5. §72全量子集门复述（各Stage子集断言计数）

- S1 9断言：Stage1子集（per-job happy + §72门 + Case 8/9/15联动；`STAGE1-QA-REPORT TOTAL` 口径）。
- S2 12断言：Discovery/Identity 5 + AUTO Run 3 + Root/Single Instance 2 + Batch/Duplicate 2（`STAGE2-QA-REPORT §4 12项`）。
- S3 9断言：Correction不重调Whisper / Raw不变 / 新NormRev / Formatter只建新RenderRev / Run不回滚 / PREPARED Receipt / Hash Validation / SQLite Forward Repair / Raw Immutable（`STAGE3-QA-REPORT §4 9项`）。
- S4 7断言：Atomic No-Clobber / Output Race / Unknown-User-edited Overwrite=0 / Initial Publish / Subsequent不自动覆盖 / PENDING_PUBLISH / CANONICAL_OUTPUT_EXISTS（`STAGE4-QA-REPORT §4 7项`）。
- S5 10断言：Watch First / Scan / Reconcile + Stable File Detection + Candidate Partial UNIQUE + Historical Provisional Collision + Logical Source Exactly Once + Triple Discovery Race + AUTO Run Partial UNIQUE + Triple AUTO Count=1 + NO_SPEECH×10 Count=1 + FAILED_RETRYABLE重试原Run（`STAGE5-QA-REPORT §4 10项`）。
- S6 9断言：Atomic No-Clobber(mirror嵌套) / Output Race(mirror路径) / Unknown-User-edited Overwrite=0 / Initial Publish(嵌套首发) / Subsequent不自动覆盖 / PENDING_PUBLISH / CANONICAL_OUTPUT_EXISTS / §73-34 / §73-35（`STAGE6-QA-REPORT §4 9项` + Case14真机）。
- S7 5断言：§73-15分层/ASR-only + §73-27每Chunk重建 + §73-28专业词不改语义 + §73-16/Derived Revision + §70 Case4（`STAGE7-QA-REPORT §4 5项`）。
- S8 5断言：§73-24合并非空单调 + §73-25 Word Timestamp能力 + §73-26 Absolute Timeline + §73-27每Chunk重建 + §73-15分层ASR-only（`STAGE8-QA-REPORT §4 5项`）。
- S9 7断言：Correction Rules Change不重调Whisper / Raw Hash不变 / 新Normalization Revision / Formatter Change只建新RenderRev / Normalized可复用 / Completed Run不回滚 / Canonical默认不覆盖（`STAGE9-QA-REPORT §4 7项`）。
- S10 8断言：Same-FS Archive / Cross-FS Level A / O_EXCL Reservation Copy / Cross-FS Mid-copy Kill / Archive Conflict / Unsupported Archive Filesystem Block / Archive后`current_path`更新 / Source Mis-delete=0（`STAGE10-QA-REPORT §4 8项`）。
- S11 6断言：LaunchAgent Cold Boot / Absolute Binary Paths / Single Instance重证 / VolumeCapabilityProbe复用 / iCloud-Remote Root BLOCK复用 / Fault Injection Suite（`STAGE11-QA-REPORT §4 6项` + §67矩阵7项联动）。
- S12 1断言：只读显示不断链（Stage1~11回归不断链；`src/stage1-11/` diff 为空；本轮以回归十二 import + `collect` 只读 + CLI exit 语义覆盖；`STAGE12-QA-REPORT` 无独立§72计数，按 PLAN S12-T04 P0-4 记 1项）。
- 合计：9+12+9+7+10+9+5+5+7+8+6+1 = **88**（各Stage报告 `TOTAL` 实跑数另计：S1 39/S2 27/S3 39/S4 107/S5 56/S6 97/S7 115/S8 113/S9 65/S10 64/S11 11/11/S12 快照复算；本轮最终回归 19/19 为收口抽样，非重跑各Stage全量）。

## Fix Attempt Fingerprint

- Task ID: FINAL-REGRESSION（产品完成前最后一验；首轮 QA 执行）
- Root Cause Hypothesis: 不适用（PASS；同轮内 Runner 自修 3 处：① Stage3/Stage1 manifest 缺失→补 `manifest.json` 脚手架；② `job_id` 与目录 basename 不一致→改 `jd2=BASE/tag/job_id`；③ S4 二次发布为返回 BLOCK 非抛错→改判 `status含BLOCKED` 亦过 + `expected_output_hash` 键名）
- Approach: 仓库外 `/tmp/finalqa` 各用例独立 Root + 确定性合成小文件；P1×5走真路径（中途 RENDERING 续行/诱饵后建 verdict 稳定/stop后无锁scan拒收/空格BLOCK/错目录raise）+ A-cross（强制跨盘分支 + tmp提交后改源一字节）+ 全链12段（S1脚手架真链/S2三并发/S3双hash/S4首发+BLOCK/S5真11步/S6双算/S7纯层+wav头/S8纯切分/S9双派生/S10 A真link+B真预置/S11真11套件/S12真快照只读）+ 坏例五子进程只看 exit 码
- Files Changed: 仅新增本报告 `docs/qa/FINAL-REGRESSION-REPORT.md`；业务代码零改；测试写盘只在 `/tmp/finalqa`（H2外置目录约束延续）；Runner `/tmp/finalqa_run.py` 在仓库外
- Verification: `TOTAL 19/19 FAILS=[] exit=0 max=12288`（`finalqa_results.json` 可复算）；`SPACE_EXIT=1` + `WRONGDIR_EXIT=1` + `STOPSCAN_EXIT=1` + `ACROSS_EXIT=1` + `NOCLOBBER_EXIT=2` 五坏例 exit 码已取；Whisper 恒 0；诱饵/Archive/真实库零触碰；`src/stage1-12/` 未触碰
- Failure Reason: 无 FAIL 项（业务侧）
- Difference From Previous Attempt: 首轮，无上一轮（同轮内 Runner 修 3 处见上）

## 未闭环清单（交 supervisor/product-reviewer 定，不卡本 PASS）

- U-1 真实长视频未测（TM 已定：真实长视频一律不测直到产品完成；本套件最大合成文件 12288B，S11套件内最大 2816B）。
- U-2 Runner 在仓库外（`/tmp/finalqa_run.py` + `--bad` 五子进程 + `finalqa_results.json`），未进 `docs/qa`，复现找 QA 要路径（H2外置目录约束延续；S6/S10/S11/S12 同 Pattern）。
- U-3 残留待清：`/tmp/finalqa`（本轮新增，含19用例 Root + 12288B级小文件）+ 更早 Stage 残留（S12 U-4 所列），交 neat-freak 收尾。
- U-4 `src/stage1-12/ git diff 为空`口径 N/A（当前目录非 git 仓库；以全链12段 PASS + QA 零改代证，未改业务代码；同 S10/S11/S12 U-5 Pattern）。
- U-5 A-cross 跨盘为单盘强制分支模拟（本机单盘无第二 device；`_same_device` 强制 False 走真跨盘代码径，同盘 A 为真 link 路径；若需真双盘，挂第二卷重跑 A-cross 即可；同 S10 U-6 Pattern）。
- U-6 S11 fault 套件 load 后立即 unload（PLAN 已定：禁 `enable`；本轮 `run_all` 内 N4 已 unload，无残留；真实 LaunchAgents 前后等由 S11 报告覆盖，本轮不重证快照）。
- U-7 HANDOFF 滞后：根 HANDOFF 仍停 Stage2 CLOSED，未登记 Stage3~12 builder 计数基线；本报告输入复核以 `src/stage*/` 落盘 + 各 Stage PLAN/QA-REPORT 为准，基线缺失不卡 QA（已独立覆盖）。
- U-8 文本/词准确率/Golden/CER/幻觉指标 Out（PLAN 已定；本报告仅验哈希/计数/verdict/列/覆盖/exit 码）。

---
目标：最终回归｜剩 P0：无（QA 口径 PASS；闭环判定以 supervisor 复检为准）｜下一步：交 product-reviewer 验＋supervisor 复检（HANDOFF 只记状态，不代写结论）。
