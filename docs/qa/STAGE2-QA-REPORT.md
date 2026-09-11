# QA-REPORT｜Stage2 S2-T07 验收套件 + §72子集门（Video2Obsidian V1.8 §69）

- QA：qa（opencode-go/glm-5.3-flash，本窗口 subagent；未改业务代码，只写本报告）
- 被测：`src/stage2/`（store.py/candidate.py/source.py/runs.py/instance.py/__init__.py）+ `src/stage1/` 只读复用（sha256_file/probe_volume/ingest→commit 链）
- 计划：`docs/pm/STAGE2-PLAN.md` S2-T07（P0-1~P0-8；合成副本，禁真实长视频；坏例只看 exit 码）
- 基线：V1.8 §72 Implementation Acceptance Gate（Stage2 子集 12 断言：Discovery/Identity 5 + AUTO Run 3 + Root/Single Instance 2 + Batch/Duplicate 2）
- QA 执行目录（仓库外）：`/tmp/s2t07_qa/`（各用例独立 data_root + 合成 `.bin` 副本 + `s2t07_results.json`，约 1.9M；仓库内零写盘除本报告）
- **结论：PASS（happy 1 遍 + 异常 6 个全过，27/27 断言双轮稳定，exit 0；坏例只看 exit 码；Stage3+ 四表行数恒 0；Whisper 调用恒 0；结论只落本报告）**

## 1. 输入复核（src/stage2 落盘 6 文件，只读消费）

- `store.py`：中央库骨架（9 表 DDL + 两 Partial UNIQUE + 获锁断言）；`candidate.py`：直接 API `discover()` 生命周期；`source.py`：Strong SHA256 promotion + UPSERT；`runs.py`：AUTO 身份 + `ON CONFLICT DO NOTHING`；`instance.py`：`flock` + 启动子序列 + CLI（exit 2/3）；`__init__.py`：装配导出。
- 上轮 builder 复跑入口：本轮未发现独立复跑脚本落盘，QA 以 `src/stage2/` 公开 API + `instance.py` CLI 为被测入口，自建仓库外 Runner（见§3声明），符合“结论只落 qa 报告”约束。

## 2. 用例简表（坏例只看 exit 码）

| 用例 | 前置 | 动作 | 期望 | 实测 | exit 码 / Count | Stage3+ 四表 | Whisper |
|---|---|---|---|---|---|---|---|
| HAPPY 端到端 | 新 data_root + 合成 `clip.bin`（64K 确定性字节） | startup→discover(+PROFILE) | PROMOTED + Source=1 + Run=1(QUEUED) + 启动 5 步有序 | 一致 | Count 1/1 | 0/0/0/0 | 0 |
| P0-1 中央库门 | 新 root | schema/WAL/FK 断言 + 无锁 init/discover | 9 表 + 两 UNIQUE 逐字 + WAL + FK=1；无锁两处 `LockNotHeldError` | 一致 | API 抛错（CLI 等价见 P0-8） | — | — |
| P0-2 生命周期 | 抖动文件（门内 append）/ 删失文件 | discover→reject→discover | WAITING→REJECTED→SOURCE_MISSING→PROMOTED→重发现 MERGED；零 ASR 引用 | 一致 | 状态机全中 | — | 0（grep） |
| P0-3 Case13 历史碰撞 | PROMOTED 后改 bytes 保 size+mtime（utime 恢复） | 再 discover | 新 Candidate→新 Source（nsrc=2，旧 Source 保留） | 一致 | Source=2 | 0 | 0 |
| P0-4 Unicode+Exactly Once | `测试 中文丨Case (A).bin` | discover×2 | path 原样存；重发现 MERGED；`Duplicate Logical Source=0` | 一致 | Source=1, dup=0 | — | — |
| P0-5 AUTO 身份 | 同 Source 双 PROFILE | get_or_create×3 + manual 预留 + SQL 审计 | 同 hash 同 run；异 hash 第二 run；MANUAL 抛 `NotImplementedError`；原子 UPSERT | 一致 | Run=2 | — | — |
| P0-6a Triple Race | 三线程同调 `discover()` 同一副本 | 并发跑 | Source=1 且 AUTO Run=1 | 一致（PROMOTED+2×MERGED） | 1/1 | 0 | 0 |
| P0-6b NO_SPEECH×10 | 先 `mark_no_speech` | reconcile×10 | 同一 run_id，Count=1 | 一致 | 1 | — | — |
| P0-6c RETRYABLE | 先 `mark_failed_retryable` | reconcile | 同一 run_id，`retry_count` 0→1，无新 Run | 一致 | Count 不变 | — | — |
| P0-7 第二实例互斥 | 父进程持锁 | 子进程跑 `instance.py` CLI | exit **3**，DB mtime 不变，零写盘 | 一致 | exit **3** | — | — |
| P0-8a iCloud-Remote BLOCK | input 含 `Mobile Documents/com~apple~CloudDocs` | 子进程跑 CLI | exit **2** + `BLOCKED_UNSUPPORTED_ROOT_FOR_V1` | 一致 | exit **2** | — | — |
| P0-8b 无锁 exit 码 | 无锁 data_root | 子进程 `discover()` | 非零 exit + `LockNotHeldError` | 一致 | exit **1** | — | — |
| Stage1 回归 | 合成 `s1.bin` + 计数桩 ASR | ingest→verify→gate桩→post→prepare→commit | verify/post PASS，桩 1 次，COMMITTED | 一致 | 全 PASS | — | 桩 1（Stage1 域） |

Runner：`/tmp/s2t07_qa_run.py`（仓库外）→ `/tmp/s2t07_qa/s2t07_results.json`（27 断言 JSON 已落盘，可复算；双轮 `TOTAL 27/27 exit=0`）。

## 3. 每用例明细（前置/动作/期望）

- HAPPY：前置空 root；动作 `startup()` + `discover(fp, dr, PROFILE)`；期望 PROMOTED；实测 Source=1/Run=1/`QUEUED`/Stage3+ 全 0/`hist={'QUEUED':1}`；启动 order 5 步逐字一致。
- P0-1：前置空 root；动作读 `sqlite_master` + `PRAGMA`（经 `open_db` 连接）+ 无锁 `init_db`/`discover`；期望 9 表 + `ux_auto_processing_run` §15 逐字 + `ux_candidate_provisional_active` §20 范围 + WAL + `foreign_keys=1` + 两处 `LockNotHeldError`；实测全中（注：直连裸 sqlite 读 `PRAGMA foreign_keys` 恒 0，属连接级语义，QA 改经 `open_db` 断言=1，见 Fingerprint）。
- P0-2：前置 `STABLE_ROUNDS_SLEEP=0.6` + 门内 append 777B；动作线程 discover；期望 WAITING；随后 `reject_candidate`→REJECTED；`gone.bin`→SOURCE_MISSING；稳定文件→PROMOTED；重发现→MERGED；`candidate.py` 全文无 whisper/mlx/asr_callable/Normalization 字样；实测全中。
- P0-3：前置 PROMOTED（32K，seed 31）；动作翻转 100B + `os.utime(ns)` 还原 mtime（断言 size+mtime 双同）；期望新 PROMOTED + 新 `source_id` + nsrc=2 + 旧行保留；实测全中（吞掉即 FAIL 项未触发）。
- P0-4：前置 Unicode 路径文件；期望 `sources.path_identity_key == abspath` 逐字节（含中文/空格/`丨`/括号/大小写）；重发现 MERGED + nsrc=1 + 逻辑身份零重复；实测全中。
- P0-5：期望 `auto_run_identity == source_id|hash` 落库 + `creation_mode='AUTO'` + 同对同 run + 异 hash 第二 run（§28）+ `create_manual_reprocess` 抛 `NotImplementedError` + `ON CONFLICT(source_id, asr_profile_hash) … DO NOTHING` 原子单语句（SELECT 只在 INSERT 后取行返显）；实测全中。
- P0-6：Triple 用 `ThreadPoolExecutor(3)` 真并发（非串行模拟）；NO_SPEECH 先置终态再 reconcile×10 同 id；RETRYABLE reconcile 后 `retry_count=1` 且 AUTO Count 不变（2=本库 happy 跑道 1 + retry 跑道 1）；任一 Count 偏离即 FAIL 项未触发。
- P0-7：父进程 `acquire()` 持锁后子进程 CLI；期望 exit **3** + `SECOND_INSTANCE` + DB mtime 纳秒级不变；锁路径运行时 `store.LOCK_RELPATH == data/.lock` 且 on-disk 存在（注：源码为 `os.path.join("data", ".lock")`，字面 grep `data/.lock` 误报，改运行时断言，见 Fingerprint）；顺序倒置检查由 HAPPY-ORDER 覆盖。
- P0-8：iCloud marker 路径（`Mobile Documents/com~apple~CloudDocs`）子进程 CLI exit **2** + `BLOCKED_UNSUPPORTED_ROOT_FOR_V1`；无锁子进程 `discover` exit **1** + `LockNotHeldError`；坏例判据只用 exit 码。
- Stage1 回归：`ingest_specified_path`（独立 job_id/进程级唯一）→verify PASS→`gate_transcription` 计数桩（`asr_calls=1`，写 `asr/transcript.txt`+`segments.json`）→`post_run_job` PASS→`prepare_raw`→`commit_raw`（receipt `COMMITTED`）；`src/stage1/` 零改（本轮无 git 仓库，`git diff` 口径 N/A，以本功能回归 PASS 代证；业务代码本轮 QA 未触碰）。

## 4. §72 子集门（Stage2 12 断言逐项）

- [x] Candidate Partial UNIQUE PASS（P0-1 DDL 逐字 + P0-2 MERGED 收口）
- [x] Historical Provisional Collision PASS（P0-3 新 Source=2，旧保留）
- [x] Logical Source Exactly Once PASS（P0-4）
- [x] Triple Discovery Race PASS（P0-6a Source=1/Run=1）
- [x] AUTO Run Partial UNIQUE implementation PASS（P0-5 逐字索引 + 原子 UPSERT 审计）
- [x] Watchdog + Scan + Reconciliation AUTO Run Count = 1（P0-6a；注：本 Stage 为三线程直调 `discover()` 并发模拟，不起 watchdog 线程，见 PLAN Out of Scope）
- [x] NO_SPEECH Reconciliation × 10 AUTO Run Count = 1（P0-6b）
- [x] FAILED_RETRYABLE 重试原 Run PASS（P0-6c）
- [x] Single Instance PASS（P0-7 exit 3 + mtime 不变）
- [x] iCloud Root Block PASS（P0-8a exit 2；Network/Remote 侧由同 `probe_volume` 门覆盖，plan 内只要求 iCloud-Remote 用例）
- [x] Duplicate Logical Source Count = 0（P0-4 dup 查询 0 行）
- [x] Duplicate AUTO Run Count = 0（全库同 `(source_id, hash, AUTO)` 无重复，Triple/×10 双反证）

## BUGS（照 BUGS.template.md；本轮无 P0/P1）

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| 无 | — | 否 | 27/27 双轮 exit 0，Count/exit 码全符合预期 | CLOSED | 无需 builder 修 | 详见 `/tmp/s2t07_qa/s2t07_results.json` |

## Fix Attempt Fingerprint

- Task ID: S2-T07 Stage2 验收套件 + §72 子集门（首轮 QA 执行）
- Root Cause Hypothesis: 不适用（PASS；3 处中间 FAIL 均为 Runner 自身断言写法问题，非业务缺陷——①裸连接读 FK；②字面 grep `LOCK_EX\|LOCK_NB`/`data/.lock`；③固定 job_id 重跑撞 Stage1 immutable 门；④桩函数多一参）
- Approach: 仓库外 `/tmp/s2t07_qa` 各用例独立 data_root；合成确定性 `.bin` 副本；CLI 坏例（互斥/iCloud/无锁）一律子进程取 exit 码；Count/行数/SQLite 直查为正常路径判据；Stage3+ 四表 + `processing_runs` 状态直方图每 happy 库反查；`src/stage2` 全文 grep Whisper=0
- Files Changed: 仅新增本报告 `docs/qa/STAGE2-QA-REPORT.md`；业务代码零改；测试写盘只在 `/tmp/s2t07_qa`（H2 外置目录约束延续）
- Verification: 双轮 `TOTAL 27/27 FAILS=[] exit=0`（`s2t07_results.json` + rerun log 可复算）；输入产物目录复查未动；`src/stage1/` 未触碰
- Failure Reason: 无 FAIL 项（业务侧）
- Difference From Previous Attempt: 首轮，无上一轮

## 未闭环清单（交 supervisor/product-reviewer 定，不卡本 PASS）

- U-1 真实长视频未测（PLAN 已定：真实长视频一律不测直到产品完成；本套件用 32–64K 确定性 `.bin` 合成副本）。
- U-2 真实 Watchdog/Scan/Reconciliation 未起（PLAN Out of Scope；Triple Race 为三线程直调 `discover()` 并发模拟）。
- U-3 Runner 在仓库外（`/tmp/s2t07_qa_run.py`），未进 `docs/qa`，复现找 QA 要路径（H2 外置目录约束延续；Stage1 U-4 同 Pattern）。
- U-4 残留待清（H5 延续）：`/tmp/s2t07_qa`（约 1.9M，本轮新增）+ Stage1 残留（`/tmp/s1t*` + `$TMPDIR`），交 neat-freak 收尾。
- U-5 `src/stage1/ git diff 为空`口径 N/A（当前目录非 git 仓库；以 Stage1 功能回归 PASS 代证，未改业务代码）。
- U-6 `MANUAL_REPROCESS` 仅模型预留（`NotImplementedError`），语义实现留后续 Stage；`NETWORK/Remote` 根门与 iCloud 共用 `probe_volume`，本轮只实测 iCloud marker 路径。

---
目标：S2-T07 验收（happy 1 + 异常 6 + Stage1 回归）｜剩 P0：无（QA 口径 PASS；P0-1~P0-8 闭环判定以 supervisor 复检为准）｜下一步：交 product-reviewer 验 + supervisor 复检（HANDOFF 只记状态，不代写结论）。
