# QA-REPORT｜Stage5 S5-T06 验收套件 + §72子集门（Video2Obsidian V1.8 §69）

- QA：qa（opencode-go/glm-5.3-flash，本窗口 subagent；未改业务代码，只写本报告）
- 被测：`src/stage5/`（watcher.py/scan.py/reconcile.py/startup.py/__init__.py）+ `src/stage2/` 只读复用（store/candidate/discover/runs/reconcile_source/instance.startup 前五步/锁）+ `src/stage1/` 只读复用（sha256_file/probe_volume）+ `src/stage3/`、`src/stage4/` 零调用（不产生 Revision、不发布、不回填）
- 计划：`docs/pm/STAGE5-PLAN.md` S5-T06（P0-1~P0-8；happy 1 遍 + 异常 7 个 + Triple Race 真三路并发 + 回归四行；外置合成 Input Root + 外置 Data Root；禁真实长视频/真实库；文件 spelling 一律 `canonical()` 后比较；坏例只看 exit 码；结论只落本报告）
- 基线：V1.8 §72 Implementation Acceptance Gate（Stage5 子集 10 断言：Watch First / Scan / Reconcile implementation + Stable File Detection + Candidate Partial UNIQUE + Historical Provisional Collision + Logical Source Exactly Once + Triple Discovery Race + AUTO Run Partial UNIQUE + Triple AUTO Count=1 + NO_SPEECH×10 Count=1 + FAILED_RETRYABLE 重试原 Run）
- QA 执行目录（仓库外）：`/tmp/s5qa/`（happy/a_jitter/a_watchgate/a_readygate/a_scan/a_empty/a_reconcile/a_startup/a_second/a_race/reg_s1/reg_s2/reg_s3 各独立 data_root + 合成 `.mp4` 副本 + `s5qa_results.json`）+ `/tmp/s5qa_run.py`（仓库外 Runner，`--bad ready/lock/second` 三子进程取 exit 码）；仓库内零写盘除本报告
- **结论：PASS（happy 1 遍 + 异常 7 个全过 + Triple Race 真并发 + 回归四行，56/56 断言双轮稳定，Runner exit 0；坏例只看 exit 码：ready exit 1=WatcherNotReadyError、lock exit 1=LockNotHeldError、second exit 1=SecondInstanceError 未吞 + CLI exit 3；四表恒 0；Whisper 恒 0；文件 spelling 双边 canonical；结论只落本报告）**

## 1. 输入复核（src/stage5 落盘 5 文件，只读消费；builder 口径锁定沿用）

- `watcher.py`（S5-T01）：watchdog Observer 真实递归监听合成 Input Root（created/moved/modified 去抖 `DEBOUNCE_S`）；事件只投递（调 `stage2.candidate.discover`，不直写 DB、不绕 Stable 门、无路径级去重，At Least Once）；`VIDEO_SUFFIXES` 白名单大小写不敏感；`wait_ready()` 为 Watch First 硬门；`stop()` 幂等可 join；`canonical()=realpath(abspath)`（`/tmp`→`/private/tmp`，watchdog 与 `os.walk` 拼写归一）；`start_watch` 要求实例锁已持（`LockNotHeldError`）。
- `scan.py`（S5-T02）：`startup_scan` 前置断言 Watcher Ready（无 Ready 即 `WatcherNotReadyError`，顺序硬门）；递归枚举全层级视频逐个调 `discover()`；模块内无去重（无“同 path 跳过”，Case 13 由 `discover()` 裁决）；空目录返回 `[]` 非异常。
- `reconcile.py`（S5-T03）：`initial_reconcile`（启动链）与 `periodic_reconcile`（可重复补漏）同一语义——枚举现存视频→缺失投递 `discover()`→既有 AUTO Run 经 `reconcile_source` 收敛（`FAILED_RETRYABLE`→同 `run_id`+`retry_count+1` 不建新 Run；`NO_SPEECH_DETECTED`→返既有终态零新增；`QUEUED` 原样返回）；WAITING（Stable 门内）留待下轮；不推进转写状态机。
- `startup.py`（S5-T04）：`run_startup` 复用 `stage2.instance.startup` 前五步（锁与 DB 沿 Stage2，不另起锁，`SecondInstanceError` 永不吞）→ Start Watcher → Confirm Ready（超时 fail-closed 停 watcher 抛错，不留半启动）→ Startup Scan（有 error 即抛）→ Initial Reconciliation（有 error 即抛）→ Start Workers → RUNNING；返回 `order` 11 步逐字数组（漂移即 `AssertionError`）；`DeliveryWorkers` 为 delivery-only（有界队列线程，每项只调 `discover()`，无转写/发布/归档 import）；`shutdown()` 先停 Workers 再停 Watcher，幂等。
- `__init__.py`（S5-T05）：装配导出 + `triple_race_deliver` 复核 helper（三路×多轮真并发：watch 路由经 `watcher.deliver`、scan 路由直调 `discover`、reconcile 路由 `discover`+`reconcile_source` 收口；不新增持久化语义，收口仍在 `discover` + AUTO UPSERT；依赖 `_retry_locked` 不抛 `database is locked` 到验收层）。
- 上轮 builder 复跑入口与摆动说明：`/tmp/s5_builder_selfcheck/run.py`（355 行，T01~T05 + reg-lite + size 门，25 cases 全 PASS，`results.json` 已落盘）+ `child_startup.py`（第二实例子进程）；摆动三处 QA 已承接——① jitter 需至多 3 attempts（门内 append 竞态）；② Case13 经 Scan 路径在 watcher 活着时 winner varies（PROMOTED/MERGED 皆合法，以 `path_sources=2` 为判据）；③ Workers/Watcher 同文件竞态 `PROMOTED`/`MERGED` 皆合法（以 `path_sources=1` 为判据）；`canonical()` 归一 `/tmp`→`/private/tmp` 后比较（本报告所有文件拼写断言双边 `canonical()`）。

## 2. 用例简表（坏例只看 exit 码；文件拼写一律 canonical 后比较；四表=norm/rend/pub/arch）

| 用例 | 前置 | 动作 | 期望 | 实测 | exit 码 / Count | 四表 | Whisper |
|---|---|---|---|---|---|---|---|
| HAPPY 全链 | 空 root，`run_startup`→空 scan | 放 1 视频经 Watcher→PROMOTED→shutdown→停机放 3→同库 `run_startup` | order 11×2 + Source 1→4 + Run 1→4 + Lost=0 + QUEUED | 一致（`clip.mp4` PROMOTED，`off0~2` 补回，fs=4 lost=0） | Runner exit 0；1/1→4/4 | 0/0/0/0 | 0 |
| A5 抖动文件 | 活 watcher + writer 线程门内 append（至多 3 attempts） | 事件投递撞 Stable 门 | `WAITING_FOR_STABLE_FILE`，不提前 PROMOTED | 一致（第 1 attempt 即 WAITING） | — | — | — |
| A-非视频忽略 | 活 watcher | 放 `.txt`/`.md` + 大写 `.MP4` | txt/md 零投递零行；`MP4` 照收 | 一致（deliv=0 rows=0；MP4 PROMOTED） | — | — | — |
| A-stop 幂等 | 活 watcher | `stop()`×2 后放 `after_stop.mp4` | deliveries 不变 + 该 canonical 零行 + 零命中的投递 | 一致 | — | — | — |
| A7 Ready 门 | 冷 Watcher（未 start）/ 无注册 root | `startup_scan` | `WatcherNotReadyError` 两处 | 一致 | 子进程 `--bad ready` exit **1** | — | — |
| A-lock 门 | 无锁 root | `start_watch` | `LockNotHeldError` | 一致 | 子进程 `--bad lock` exit **1** | — | — |
| A-scan 补回 | 停机放 3（`subN/downN.mp4`）→起 watcher→scan | `startup_scan` | 3/3 PROMOTED | 一致 | 3/3 | 0 | — |
| A-scan 重复 | 同目录再 scan | `startup_scan` | 全 MERGED + 计数不变（Exactly Once） | 一致 | 3/3→3/3 | 0 | — |
| A6 Case13 | PROMOTED 后原地改 bytes 保 size+mtime（utime 还原；停 watcher 后 scan，确定性门） | `startup_scan` | 新 PROMOTED + 该 canonical `path_sources=2` + 总 4 | 一致（status=PROMOTED，psrc=2） | Source 3→4 | 0 | 0 |
| A-empty | 空 input + Ready watcher | `startup_scan` | `[]` 非异常 | 一致 | — | — | — |
| A4 漏事件补回 | 屏蔽投递 watcher（`on_deliver=None`）后放 `leak.mp4` | `periodic_reconcile` 一次 + `initial_reconcile` 同语义 | 屏蔽期 Source=0 → periodic 后 PROMOTED/QUEUED | 一致 | 0→1/1 | 0 | — |
| A2 NO_SPEECH×10 | `mark_no_speech` 后 | `periodic_reconcile`×10 | 同 `run_id`，Count=1，`NO_SPEECH_DETECTED` | 一致 | 1 | — | — |
| A3 RETRYABLE | `mark_failed_retryable` 后 | `periodic_reconcile`×2 | 同 `run_id`，`retry_count` 0→2，无新 Run（总数 2=本库 leak+retry 两跑道） | 一致 | Count 不变 | — | — |
| A-startup 装配 | `pre.mp4` 预置 | `run_startup` | order 11 逐字 + pre 经 scan PROMOTED | 一致 | 11 步 | 0 | — |
| A-workers 投递 | RUNNING 后经 Workers 提交 `via_workers.mp4`（与活 watcher 竞态） | `submit`→轮询 results | 投递成功（PROMOTED/MERGED 皆合法）+ 该 canonical `path_sources=1` + hist 干净 | 一致（MERGED，psrc=1） | — | 0 | — |
| A-shutdown | RUNNING | `shutdown`×2 | 双幂等 `running=False` | 一致 | — | — | — |
| A-second | 父持锁 | 子进程 `run_startup` 同库（不捕获）+ `instance.py` CLI | 不吞 `SecondInstanceError` + CLI exit **3** | 一致 | 子进程 exit **1**；CLI exit **3** | — | — |
| A1 Triple Race | 活 watcher + `race.mp4` | `triple_race_deliver(rounds=5)` 三路真并发 | 15 outcomes 全 ok + Source=1 + Run=1 + dup 0/0 | 一致（15/15，1/1） | 1/1 | 0 | 0 |
| STOP 门 | 全仓 | grep 三重 | 无 `run_asr_single_file`；无 Stage6+（current_path/LaunchAgent/Menu Bar/PathMirror）；无 stage3/4 import | 一致（grep 空） | — | 0 | 0 |
| REG-S1 | 合成门 | `probe_volume`+非法 Raw | ALLOW + `PrepareError` 拒收 | 一致 | — | — | — |
| REG-S2 | 新 root | `startup` 5 步 + `discover` | 5 步逐字 + PROMOTED + Source=1 + Run=1 | 一致 | 1/1 exit 0 | 0 | — |
| REG-S3 | 新 root（合成 Raw 经门） | norm→render | COMPLETED→PUBLISH_EVALUATION + verdict∈{PENDING_PUBLISH,CANONICAL_OUTPUT_EXISTS} | 一致（CANONICAL_OUTPUT_EXISTS） | Norm=1/Render=1 | 0 | 0 |
| REG-S4 | 旧库只读 | 查 `/tmp/s4qa/happy` | `PUBLISHED` 行仍可查且行数不变（=1） | 一致（`pub_3226e81b395b`/PUBLISHED） | 1 | — | — |

Runner：`/tmp/s5qa_run.py`（仓库外）→ `/tmp/s5qa/s5qa_results.json`（56 断言 JSON 已落盘，可复算；双轮 `TOTAL 56/56 FAILS=[] exit=0`）；坏例子进程：`--bad ready` exit **1**（WatcherNotReadyError 未捕获）、`--bad lock` exit **1**（LockNotHeldError）、`--bad second <dr> <ir> <profile>` exit **1**（SecondInstanceError 未吞）+ `stage2/instance.py` CLI exit **3**（判据只用 exit 码，不看打印）；最大合成文件 32768B（≤200K 门）。

## 3. 每用例明细（前置/动作/期望；拼写口径单列）

- HAPPY：前置空 `happy/{data_root,input}`；动作 `run_startup`（空 scan=`[]`，order 11 逐字）→放 `clip.mp4`（32768B seed7）→`wait_for_path`（25s）PROMOTED→DB `path_identity_key` 双边 `canonical()` 命中→Source=1/Run=1/四表 0/hist `{QUEUED:1}`/dup 0/0→`shutdown`→停机放 `off0~2.mp4`→同库 `run_startup`（order 再 11）→Source=4/Run=4→`iter_video_files` 4 个全有 canonical 匹配 Source（Lost=0）→四表仍 0→`shutdown`+`release`；实测全中。
- A5：前置活 watcher（debounce 0.05）；动作 writer 线程（4K 首写 + 60×2K append，40ms 间隔）与事件投递竞态，至多 3 个新文件轮询 `wait_for_path`；期望首个命中的 `result.status==WAITING_FOR_STABLE_FILE`；实测第 1 attempt 即中（Stable 门延续，门内 append 不提前 PROMOTED）。
- A-非视频/stop：前置活 watcher；动作放 `note.txt`/`readme.md` + 大写 `clip.MP4`→`MP4` PROMOTED（大小写不敏感）→sleep 2s 后 txt/md 投递 0 且 `discovery_candidates` LIKE 零行→`stop()`×2→放 `after_stop.mp4`→sleep 2s 后 deliveries 计数不变 + 该 canonical 零行 + 投递记录零命中；实测全中。
- A7/lock：前置新 root + 持锁；动作 `Watcher(ir,dr)` 冷对象调 scan→`WatcherNotReadyError`；幽灵 root 调 scan→同错；子进程 `--bad ready`（无 watcher）exit **1**、`--bad lock`（无锁 `start_watch`）exit **1**；判据只用 exit 码；实测全中。
- A-scan 系：前置停机放 3（`sub0/down0` 等）→起 watcher 后先 `stop()`（去活事件）→重起 gate watcher→`startup_scan` 3/3 PROMOTED→再 scan 全 MERGED 且计数 3/3 不变→停 gate watcher→重起超大 debounce gate→`stop()`（停后仍 Ready，零活事件，确定性门，规避 builder“winner varies”摆动）→翻转 `down0.mp4` 200B 并 `utime` 还原 size+mtime（双同断言）→`startup_scan` 该 canonical PROMOTED + `path_sources=2` + 总 Source=4；空 input 另库 scan=`[]`；实测全中（中间 1 处 Runner 自身断言过严已修，见 Fingerprint）。
- A4/A2/A3：前置屏蔽投递 watcher；动作放 `leak.mp4`→sleep 1.5s 后 Source=0（漏事件成立）→`periodic_reconcile` 一次即 PROMOTED/QUEUED→`initial_reconcile` 全 `deliver_error=None`（同语义）→`mark_no_speech`→periodic×10 后 Count=1/同 id/`NO_SPEECH_DETECTED`→放 `retry.mp4`→periodic→`mark_failed_retryable`→periodic×2 后同 id/`retry_count=2`/总数 2；四表 0；实测全中。
- A-startup/workers/second：前置 `pre.mp4` 预置；动作 `run_startup(worker_count=2)`→order==`STARTUP_ORDER` 11 逐字 + scan 含 pre PROMOTED→`workers.submit(via_workers.mp4)`（与活 watcher 故意竞态）→轮询 25s 命中（MERGED 合法）+ 该 canonical `path_sources=1` + hist⊆{QUEUED,FAILED_RETRYABLE,NO_SPEECH_DETECTED}→`shutdown`×2 幂等→`release`→新库父持锁→子进程 `run_startup` 同库 exit **1** 含 SecondInstanceError（未吞）+ `instance.py` CLI exit **3**；实测全中。
- A1：前置活 watcher + `race.mp4`（24576B）；动作 `triple_race_deliver(watcher, rounds=5)`（watch/scan/reconcile 三路×5 轮=`ThreadPoolExecutor(3)` 真并发）→15 outcomes 全 ok→中央库实查 Source=1/Run=1→逻辑身份与 AUTO 双 dup 查询 0→四表 0；任一偏离即 FAIL 项未触发；实测全中（`database is locked` 未抛到验收层，`_retry_locked` 延续）。
- STOP：`grep run_asr_single_file src/stage5` 空；`grep -i current_path|LaunchAgent|Menu Bar|PathMirror` 空；`grep stage3/stage4 import|publish.py|conflict.py` 空；`startup.py` 唯一 DB 入口为 `discover` + `reconcile.py` 内 `reconcile_*`（Workers delivery-only 反证：hist 无转写态 + 四表 0）；13 库四表全 0（happy/a_* 各库）；输入路径全在 `canonical(/tmp/s5qa)` 内（仓库/真实视频目录/真实 Obsidian 库零触碰）；最大文件 32768B。
- 回归：REG-S1 `probe_volume→ALLOW` + 非法 Raw `PrepareError` 拒收；REG-S2 `startup` 5 步逐字 + `discover` PROMOTED + Source=1 + AUTO Run=1（`get_or_create` 同对同 run 反证 AUTO UPSERT）；REG-S3 合成 Raw 经 `build_raw_content`+`validate_raw_artifact` 门→`create_normalization_revision` COMPLETED→`create_render_revision` PUBLISH_EVALUATION/`CANONICAL_OUTPUT_EXISTS`；REG-S4 `/tmp/s4qa/happy` 只读开库 `PUBLISHED pub_3226e81b395b` 仍可查且 count=1（行数不变）；`src/stage1-4/` 本轮 QA 未触碰（目录非 git 仓库，`git diff` 口径 N/A，以四回归 PASS + QA 零改代证）。

## 4. §72 子集门（Stage5 10 断言逐项）

- [x] Watch First / Scan / Reconcile implementation PASS（HAPPY Watch 投递 + A-scan 3/3 + A4 periodic/initial 双证据）
- [x] Stable File Detection PASS（A5 抖动仍 WAITING，门内 append 不提前 PROMOTED）
- [x] Candidate Partial UNIQUE PASS（A-scan 重复全 MERGED + HAPPY dup 0/0；原子竞争未抛 UNIQUE 到验收层）
- [x] Historical Provisional Collision PASS（A6 改 bytes 保 size+mtime→新 Source：`path_sources=2`，旧 Source 保留，总 4）
- [x] Logical Source Exactly Once PASS（HAPPY Lost=0 + 重复 Scan 计数不变 + Unicode 由 Stage2 语义沿用）
- [x] Triple Discovery Race PASS（A1 三路×5 真并发 Source=1/Run=1）
- [x] AUTO Run Partial UNIQUE implementation PASS（A1 dup_run=0 + REG-S2 同对同 run + `ON CONFLICT DO NOTHING` 沿 Stage2）
- [x] Triple AUTO Count=1（A1 中央库实查 runs=1）
- [x] NO_SPEECH×10 Count=1（A2 同 run_id，Count=1）
- [x] FAILED_RETRYABLE 重试原 Run PASS（A3 同 run_id，`retry_count` 0→2，无新 Run）

## BUGS（照 BUGS.template.md；本轮无 P0/P1）

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| 无 | — | 否 | 56/56 双轮 exit 0；坏例 exit 1/3 符合预期 | CLOSED | 无需 builder 修 | 详见 `/tmp/s5qa/s5qa_results.json` |

## Fix Attempt Fingerprint

- Task ID: S5-T06 Stage5 验收套件 + §72 子集门 + Stage1~4 回归（首轮 QA 执行 + 1 处 Runner 自修）
- Root Cause Hypothesis: 不适用（PASS；中间 1 处 FAIL 为 Runner 自身断言过严——Case13 要求 scan 侧 status==PROMOTED，而 gate watcher 活着时 watcher 路与 scan 路竞态、scan 侧 MERGED 但新 Source 已建（psrc=2/total=4 正确）；非业务缺陷）
- Approach: 仓库外 `/tmp/s5qa` 各用例独立 data_root + 合成确定性 `.mp4`（最大 32K）；正常路径以中央库 `COUNT(*)`/行级 `canonical()` 对比为判据；Ready/无锁/第二实例走子进程只看 exit 码；grep 三重 STOP 门；四表每库快照；hist 断言 Run 非转写态；回归 S1 门/S2 链/S3 verdict/S4 旧库只读
- Files Changed: 仅新增本报告 `docs/qa/STAGE5-QA-REPORT.md`；业务代码零改；测试写盘只在 `/tmp/s5qa`（H2 外置目录约束延续）；Runner `/tmp/s5qa_run.py` 在仓库外
- Verification: 双轮 `TOTAL 56/56 FAILS=[] exit=0`（`s5qa_results.json` 可复算）；`READY_EXIT=1` + `LOCK_EXIT=1` + `SECOND_EXIT=1` + `CLI_EXIT=3` 四坏例 exit 码已取；13 库四表全 0；诱饵/真实库零触碰；`src/stage1-4/` 未触碰
- Failure Reason: 无 FAIL 项（业务侧）
- Difference From Previous Attempt: 首轮内 1 处自修——Case13 改“停 gate watcher 后 scan”（停后仍 Ready、零活事件），由竞态接受式改确定性门式，复跑 56/56；对应 builder 摆动“winner varies”已规避并记 U-6

## 未闭环清单（交 supervisor/product-reviewer 定，不卡本 PASS）

- U-1 真实长视频未测（PLAN 已定：真实长视频一律不测直到产品完成；本套件最大文件 32768B 合成小文件）。
- U-2 Runner 在仓库外（`/tmp/s5qa_run.py` + `--bad` 三子进程），未进 `docs/qa`，复现找 QA 要路径（H2 外置目录约束延续；Stage1 U-4/Stage2 U-3/Stage3 U-3/Stage4 U-3 同 Pattern）。
- U-3 残留待清：`/tmp/s5qa`（13 data_root，本轮新增）+ `/tmp/s5_builder_selfcheck`（builder 自检）+ `/tmp/s5dbg{,2,3}`（builder 调试）+ Stage4 残留（`/tmp/s4qa`+`/tmp/s4qa_out`）+ Stage3 残留（`/tmp/s3qa`）+ Stage2 残留（`/tmp/s2t07_qa` 约 1.9M）+ Stage1 残留（`/tmp/s1t*` + `$TMPDIR`），交 neat-freak 收尾。
- U-4 `src/stage1/`/`src/stage2/`/`src/stage3/`/`src/stage4/ git diff 为空`口径 N/A（当前目录非 git 仓库；以四回归 PASS + QA 零改代证，未改业务代码）。
- U-5 builder 自验 harness 未在工作区落盘（在 `/tmp/s5_builder_selfcheck/run.py` 25 cases；本报告以独立 Runner 56 断言覆盖，exit 码对账一致）。
- U-6 三路真并发本质仍有调度非确定性（哪一路赢 PROMOTED 不保证；本报告判据只用中央库 Count + dup 0 + exit 码，不依赖胜者；Case13 确定性门已规避活 watcher 竞态，见 Fingerprint）。

---
目标：Stage5验收S5-T06｜剩 P0：无（QA 口径 PASS；闭环判定以 supervisor 复检为准）｜下一步：交 product-reviewer 验 + supervisor 复检（HANDOFF 只记状态，不代写结论）。

---

## 收尾注记（neat-freak，2026-09-16；只加注，不改正文、不改结论）

- **事由**：历史未决项——本报告 `:24`（A5 用例行）、`:52`（A5 明细：「期望首个命中的 `result.status==WAITING_FOR_STABLE_FILE`」）、`:65`（§72 子集门「Stable File Detection PASS（A5 抖动仍 WAITING）」）三处的 A5 口径，在 **P1-1-FIX（commit `ac3ecd8`）之后已变**，此前无注记。
- **新口径**：稳定判定改为「静默 3.0s ＋ 采样 2.0s×3 轮（最小年龄 7s）＋ 独占占用检测」后，**抖动期间根本不投递**，因此**首个投递结果的状态是 `PROMOTED`**（旧期望 `WAITING_FOR_STABLE_FILE`）。
- **核对结果：与当前代码一致**。证据：`src/stage5/watcher.py:74-86`（`DEBOUNCE_S`/`STABLE_PROBE_S=2.0`/`STABLE_ROUNDS=3`，尾延迟 ≈7s）、`:284-352`（`_flush_loop`/`_flush_batch`/`_verdicts`，采样门在投递之前）。§72「Stable File Detection PASS」的**实质**（不得绕过 Stable 门提前 PROMOTED）**仍成立**，变的只是「首个投递结果的观测状态」。
- **引用证据**：`docs/review/P1-1-FIX-WATCHER-CODE-REVIEW.md` §三F `:74`（探针 4：真 watcher ＋ 真 discover，1KB×2／40ms 抖动 60 次 → 投递 **1 次**、写完 +0.69s、`status=PROMOTED`）与 `:139`（P3-5 请求加注）；链路旁证 `docs/qa/P1-9-SKIP-QA-2026-09-15.md:64` 起 supervisor 复检节（P1-9 未触碰 `src/`，该口径此后未再变化）。
- **不改正文的理由**：`:8` 的 56/56 双轮 PASS 与本节各用例结论均为**当时取证值**，按「历史报告只加注不改正文」处理，结论一律不动。
- **行号口径**：本注记与正文引用行号均以**当前工作树**为准（2026-09-16，HEAD `e38151a`）。
