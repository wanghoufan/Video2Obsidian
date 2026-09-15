# CODE REVIEW｜DEVELOP-P1-1-FIX「监听可靠性：cp 大文件必须被发现」首轮

- Task: **DEVELOP-P1-1-FIX**（修 qa 独立复现的 `BUG-P11-1`：首事件即投递＋`DEBOUNCE_S=0.25` 丢后续事件 → cp 大文件投半截、写完后不重投 → 偶发永久漏发现）。交付实体＝`watcher.py` 改「事件只重计时 + 1s 静默 + 0.5s 双采样稳定才投」、`reconcile.py` 新增 `PeriodicReconciler`(45s)、`startup.py` 接线启停、`__init__.py` 导出、`selftest_p1_2_contract.py` 新增 part15。
- Commit: **未提交**（工作树，基线 `HEAD=7b97aaa`）。`git diff --numstat HEAD` 实测＝`src/stage5/__init__.py 13/2`、`src/stage5/reconcile.py 102/0`、`src/stage5/startup.py 32/5`、`src/stage5/watcher.py 103/12`、`tests/selftest_p1_2_contract.py 238/0`（5 files，**+488/−19**），与 builder 自报「改 5 个文件、part15 新增 18 条断言」逐项相符。
- Reviewer: code-reviewer（本窗口 subagent 独立复核，与 builder 非同一审查上下文；先读 AGENTS → `docs/roles/code-reviewer.md` → `USER_MODEL_OVERRIDE.md` → HANDOFF → `经验一句话.md` → 本任务）
- Result: **打回（FAIL）—— 1 条 P1（P1-FIX-1）＋ P2×3 ＋ P3×6**。原 `BUG-P11-1` 的「永久漏发现」已确认修复（真机 `cp` 462MB → 2.1s 出任务行、投递时 size＝最终；双路（事件/周期）幂等；无线程泄漏；范围零越界），但**本修复自称的验收口径「只投 1 次且投递时 size==最终」在「生产者停顿 ≥ 静默窗+探针窗（1.5s）」下被确定性证伪**，且真实服务已把**截断笔记发布进 vault**（`publish_record_ids` 在位）。改法见 §六，最小改动在本次范围内即可闭环，结构性项建议 TM 判 Change B。

> 复核口径：只读业务代码 ＋ 独立跑三套自测 ＋ 自写探针（`/tmp/p11-cr-probe1.py`/`probe2.py`/`probe-stable.py`/`probe4.py` 进程内、`/tmp/p11-cr-real2.py`/`p11-cr-slow6.py`/`p11-cr-clean.py` 真机、`/tmp/p11-cr-falsify.sh` 5 条变异）。**未改业务代码**（变异一律「改坏→跑→从 `/tmp/p11-cr-backup/` 拷回→全量 `shasum -a 256` 逐字一致」，**全程未用 `git checkout`**）。真机用自己的临时端口 **8917/8918/8919/8921/8922/8923**（禁 8765，未碰 8899/8900，未碰 8765 的 PID 6586）；输入/数据/笔记库全部新建在 `/tmp/p11-cr-*`；真实视频只**读**`/tmp/p11-real/input/`，未写用户真实目录与 Obsidian 库；收工后端口全部释放、5 文件 sha256 与开工逐字一致、工作树仍只有 5 个 `M` ＋ 2 个既有 `??`。

---

## 一、我自己跑过的命令与退出码（实跑证据，非转述）

| # | 命令 | 实测输出 | rc |
|---|---|---|---|
| 1 | `.venv/bin/python tests/selftest_p1_2_contract.py` | `SELFTEST ALL PASS（535 项断言）`，含 part15 全绿（`^PASS 15` = **18**） | **0** |
| 2 | `.venv/bin/python tests/selftest_p1_2_frontend.py` | `FRONT ALL PASS`＋`FRONT SELFTEST PASS`（`^PASS`=**167**、`^FAIL`=0） | **0** |
| 3 | `.venv/bin/python tests/selftest_v26_presets.py` | `SELFTEST ALL PASS`（`^PASS`=**58**） | **0** |
| 4 | `git diff --name-only HEAD` ＋ 关键文件 `git show HEAD:f \| shasum` vs 工作树 | 改动＝5 文件；`app/server.py 3c4572e7…`、`app/index.html 5ad402f6…`、`src/stage2/candidate.py 8656e28a…`、`runs.py 3c937a1b…`、`store.py 7f1f9bea…`、`instance.py 1a336083…` **全部 SAME** | 0 |
| 5 | `python /tmp/p11-cr-scope.py`（AST 逐函数/类/常量比对 HEAD vs 工作树） | `same=53 changed=13 added=18 removed=0`；REMOVED 为空 | 0 |
| 6 | `python /tmp/p11-cr-probe1.py`（时序：停顿/慢写/饥饿/touch/线程/异常） | 见 §三 A/B/C/D | 0 |
| 7 | `python /tmp/p11-cr-probe2.py`（幂等/半截后果/周期成本/失败/stop 谎报） | 见 §四 | 0 |
| 8 | `python /tmp/p11-cr-probe-stable.py`（单事件+字节仍变） | 真实码：不投半截；M4 变异：投半截 | 0 |
| 9 | `python /tmp/p11-cr-probe4.py`（老 A5 抖动形状） | 投递 1 次、`status=PROMOTED`、写完 +0.69s | 0 |
| 10 | `bash /tmp/p11-cr-falsify.sh`（M1/M2/M3a/M3b/M4/M5 五条变异） | M1/M2/M3a/M3b **rc=1 咬住**；M4/M5 **rc=0 未咬住**；6/6 还原 sha256 逐字一致 | 0 |
| 11 | `python /tmp/p11-cr-real2.py $PWD 8918`（真机 cp 与流式写 462MB） | 两变体均 PASS（size==final，见 §五） | 0 |
| 12 | `python /tmp/p11-cr-slow6.py $PWD 8921`（真机分块 fsync 慢写 4.5s） | 写入期间零投递（观察窗内未出现 run） | 0 |
| 13 | `python /tmp/p11-cr-clean.py $PWD 8923`（真机 canary 协议 + 2.5s 停顿） | **半截投递=True（t=1.67s，size=8388608）＋写完补投完整（t=8.80s）** | 0 |
| 14 | 终态 `shasum -a 256`＋`git status --porcelain`＋`lsof` | 5 文件与开工逐字一致；8917-8923 **全部已释放** | 0 |

**基线 sha256（开工自分自算，收工已逐字复核）**：`__init__.py 77fbfa8e…bd5e`、`reconcile.py a4dbb136…0459`、`startup.py 159d2148…cbb7`、`watcher.py 4ea94711…a36b3`、`selftest_p1_2_contract.py b3b9c2fc…97e6`。备份：`/tmp/p11-cr-backup/`。

## 二、范围严查（复核重点 1）——**精确成立，无越界**

- **全树机器比对**：`git diff --name-only HEAD` 只列 5 个文件（git 的比对是逐字节的）；`git status --porcelain` 无新增未跟踪的源码/资源（只有 `.codebuddy/` 与本轮 qa 报告）。
- **`app/server.py` 与 `discover` 字节未变（机器证实，非目测）**：`git show HEAD:app/server.py | shasum -a 256` ＝ 工作树 ＝ `3c4572e7…12bdc2`；`src/stage2/candidate.py` ＝ `8656e28a…3eea8ec`（`src/stage2/` 其余 4 文件同证）。**builder 自报「`app/server.py` 与 `discover` 零改动」成立。**
- **函数级 AST 比对（`/tmp/p11-cr-scope.py`）**：`watcher.py`＝`DEBOUNCE_S` 改值 ＋ 新增 `STABLE_PROBE_S`/`FLUSH_TICK_S` ＋ `Watcher.__init__/start/stop/_on_fs_event` 改 ＋ 新增 `_ensure_flusher/_flush_loop/_flush_one/_stability/_deliver_safe`；`reconcile.py`＝纯新增 `RECONCILE_INTERVAL_S` ＋ `PeriodicReconciler`（10 成员）；`startup.py`＝改 `_fail_closed/run_startup/shutdown` ＋ import；`__init__.py`＝导出。**REMOVED=0**，`canonical/is_video_path/iter_video_files/deliver/wait_ready/is_ready/deliveries/wait_for_path/delivery_count/start_watch/_Handler/_reconcile_once/initial_reconcile/periodic_reconcile/STARTUP_ORDER/DeliveryWorkers` **逐字未动**（53 项 same 桶）。
- **下游回归面**：全仓 `stage5` 的外部消费者只有 `stage6/mirror.py`（只 import `VIDEO_SUFFIXES`）、`stage11/agent_boot.py`/`reliability.py`/`fault_suite.py`（只 import `STARTUP_ORDER`/`run_startup`/`shutdown`/`canonical`）、`app/server.py`（`run_startup`/`shutdown`）。`STARTUP_ORDER` 未改（仍 11 步，part15 15e 断言实测通过）；`shutdown()` 返回值**只增** `reconciler_stopped` 一键，属加法。除 part15 外**全仓无任何代码依赖投递时机**（`grep` `DEBOUNCE_S|_on_fs_event|deliveries()|wait_for_path` 于 `src/ app/ tests/` 仅命中新测试），故不存在「旧断言因语义变化而失败」的连带面（§三 F 详述 A5）。
- **红线**：未碰 secrets／封存物／`008林粒粒AI编程/`；未 commit/push；未改 `docs/pm/`；测试全用外置 tmp＋合成/真实只读拷贝。

## 三、时序语义独立推演＋探针（复核重点 2）

### A｜慢写：`1s 静默 + 0.5s 双采样` 会不会误判稳定并投半截 —— **会（P1-FIX-1，已确定性复现）**

- **判定条件（读码，`watcher.py:278-291`）**：`_stability(path)` 取 `os.stat` 两次，中间 `self._flush_stop.wait(STABLE_PROBE_S=0.5)`；两次 `(st_size, st_mtime_ns)` **完全相等**才判 `"stable"`。即「**0.5s 间隔的两次采样一致**」。投递条件是两段串联：静默窗（`DEBOUNCE_S=1.0`，每个同路径事件把 deadline 推后）+ 0.5s 探针一致 → **生产者停顿 ≥1.5s 即被当作写完**。
- **进程内探针 1-P1**（`/tmp/p11-cr-probe1.py`）：写 64KB → `_on_fs_event` → 停顿 **2.2s** → 续写。实测：停顿期间即已投递 `size=65536`（最终 131072）→ **半截**。停顿结束续写后第二次投递 `size=131072`（完整）。
- **真机探针 8**（`/tmp/p11-cr-clean.py`，端口 8923，canary 协议排除启动竞态）：写第 1 块 8MB → 停顿 2.5s → 写完 223.3MB。实测：**t=1.67s 建 run、`source_size=8388608`（当时文件确为 8MB）**；t=8.80s 第二个 run、`source_size=223306398`（完整）。**同一文件两条 run。**
- **后果（真机实证，最严重）**：半截 run（8MB 前缀）走完 raw→normalized→render→**publish**，产物在 `/tmp/p11-cr-stall-s7a/vault/stall.md`，manifest `lineage.publish_record_ids=["pub_ff566ffc4dca"]`，ASR 音轨 **40.19s**（完整 run 的 ASR 为 48.6MB wav / 约 25 分钟音频）。即：**用户 vault 里落下一篇看起来正常、实则只有开头 2.7% 的截断笔记**；按本项目 No-Clobber（`EXISTS/CONFLICT 只判不写`）**推断**，随后到达的完整 run 会在同一目标笔记上被判冲突而不写入（此项未跑完，列入未覆盖项）。
- **对照（证明这不是「旧码更差」就能带过）**：停顿 <1.5s 时新码表现正确（见 B/C），且真机快速 `cp` 场景实测完整（见 §五）——**修复对报告场景有效**；但**修复宣称的「只投 1 次且投递时 size==最终」不是不变量，而是「生产者静止 ≥1.5s」的经验条件**，本链 DoD 被证伪。

### B｜稳定慢写（事件连续到达）—— **PASS**

`/tmp/p11-cr-probe1.py` P2：每 0.2s 追加 32KB 共 5.2s（事件 25 次）。写入期间**投递 0 次**；写完 +1.59s 首投，`size=819200==final`。语义正确（1.0 静默 + 0.5 探针 = 1.5s 尾延迟）。

### C｜超大文件持续写入（饥饿）—— **PASS，无饥饿**

P3：连续写 10s（94 次事件）。写入期间**投递 0 次**；末块后 **1.48s** 首投，`size=1540096==final`。逻辑上事件持续到达只推后 deadline，不饿死；停下后 1.5s 内必定投递（`_flush_loop` 每 `FLUSH_TICK_S=0.1s` 巡查）。

### D｜`touch`/重复事件与线程/异常 —— **PASS（P3-6 记账）**

- P4：投递后 `utime` 改 mtime → **重投一次**（`size` 未变）。At-Least-Once 合法；`discover` 对同字节折叠 `MERGED` 并复用同 run（探针 2-Q1 实测 3 次 discover → `runs=1 sources=1`，候选 `MERGED×2+PROMOTED×1`）。
- P5：`stop()` 后 `s5-deliver-debounce`、`s5-periodic-reconcile` 线程数均归 **0**（不泄漏）。
- P6：`on_deliver` 抛错 → 记入 `deliveries()`（`error=repr(exc)`）且 flusher 存活、后续文件照投（**异常未被静默吞**）。
- P7（既有行为，非本次引入）：`stop()` 后 `start()` 仍会在 `watchdog Observer.start()` 抛 `RuntimeError: threads can only be started once`（`git show HEAD:src/stage5/watcher.py` 同形状，旧码亦不可重启）。新增隐患：`stop()` 不复位 `_flush_stop`，**若将来让 Observer 可重启，flusher 会「生而即死」**（P3-1）。

### E｜`startup.py` 接线 —— **PASS**

`:206-213` 在 Step 10 同一段内 `DeliveryWorkers(...).start()` 后 `PeriodicReconciler(...).start()`，`order.append("Start Workers")` 位置不变 → `STARTUP_ORDER` 11 步断言不漂移（15e 实测）；`:218-220` 异常走 `_fail_closed(watcher, workers, reconciler)`，`:139-148` 追加 reconciler 先停（顺序：reconciler→workers→watcher，合理，reconciler 不经 workers 投递）；`:235-264` `shutdown` 先停 reconciler 再 workers/watcher，幂等且容忍部分 handle。

### F｜旧断言「A5 期望 WAITING」连带 —— **无失败断言遗留，不属打回项**

- 全仓可执行断言里**没有** A5/`WAITING_FOR_STABLE_FILE` 形状：`grep -rn "WAITING\|PROMOTED" tests/` 仅命中 part15 自己的 `15c ... PROMOTED=1`（新写）；`grep -rln "抖动文件\|A5" --include=*.py --include=*.sh .`（排除 `.git/.venv`）为空。
- A5 只存在于**历史文档**：`docs/qa/STAGE5-QA-REPORT.md:24/:52/:65` 与 `docs/pm/STAGE5-PLAN.md:47`（P0-6「抖动文件仍 WAITING，门内 append 不提前 PROMOTED」）。按规矩历史报告不改正文。
- **实测新语义下的 A5 形状**（探针 4，真 watcher + 真 discover，1KB×2/40ms 抖动 60 次）：投递 **1 次**、写完 +0.69s、`status=PROMOTED`（旧期望 `WAITING_FOR_STABLE_FILE`）。判定：P0-6 的**实质**（不得绕过 Stable 门提前 PROMOTED）仍成立——抖动期间根本没投递；变的是「首个投递结果的状态」这一观测口径。**非缺陷**，但建议 neat-freak 在 `STAGE5-PLAN.md:47` 与 `STAGE5-QA-REPORT.md:24` 加一句口径注记（P3-5）。

## 四、周期兜底（复核重点 3）

| 检查点 | 结论 | 证据 |
|---|---|---|
| 宿主与启停 | PASS | `startup.py:211` 起、`:243-246` 停；`reconcile.py:163-165` `_loop` 用 `_stop.wait(interval)`（可中断，不 sleep 空转）；`stop()` 幂等（`Event.set` 可重入） |
| 幂等（事件路∪周期路） | PASS | 探针 2-Q1：同文件 3 次 discover → 1 run/1 source；part15 15c 亦断言；机制＝`discover` 的 `(path,size,mtime)` 活跃候选查询 + `content_identity` 折叠 `MERGED` + `get_or_create_auto_run` UPSERT（`candidate.py:136-160/:229-267`），**stage2 未改一个字** |
| 线程安全 | PASS（有界） | 与既有 `_lock` 不冲突：reconciler 只在自带线程跑 `periodic_reconcile`；`_passes/_last_error/_last_items` 均在 `self._lock` 内读写；`_last_items` 返回副本 |
| 失败不致命 | PASS | 探针 2-Q4：注入 pass 异常 → `passes=4`、`last_error` 有值、线程存活；**兜底不会静默哑火** |
| 成本（**P2-1**） | **需处置** | 探针 2-Q3：稳态（字节未变、已 PROMOTED）单遍 **0.36s / 48MB**（≈0.008 s/MB）→ **5GB 库单遍 ≈39s，而周期是 45s**；且每遍每文件新增 1 条候选行（`6→12→18`，**无清理**，6 文件即 +480 行/小时）。原因：`periodic_reconcile` 对**每个**现存视频调 `discover`，而 `discover` 在判定 `MERGED` 之前先做**全文件 SHA-256**（`candidate.py:227`）。即：本修复把「启动时一次性全库哈希」变成「**每 45s 全库永久哈希**」，会与 whisper 转写抢 I/O 并让 state.db 单调膨胀 |
| `stop()` 真实性（**P2-2**） | **需处置** | 探针 2-Q5：pass 耗时长于 join 超时（10s）时，`stop()` **耗时 10.0s 仍返回 True**，线程仍在跑且仍会写库；同时 `is_running()` 已返 False、`shutdown()` 已报 `reconciler_stopped=True` → **谎报**。5GB 库单遍 39s 已 >10s，非理论情形 |

## 五、独立真机复验（复核重点 6）

环境：`.venv/bin/python app/server.py` ＋ `V2O_PORT=<临时>`；夹具全新建于 `/tmp`（input/data/vault 三目录）；真实视频为 `/tmp/p11-real/input/2026-08-03第二周答疑直播-上.mp4`（**462.0MB**）只读复制；`source_size` 取自 `sources` 表（＝discover 落库时的尺寸），与落地最终 size 对账。

| 端口 | 变体 | 复制耗时 | 过程采样出半截态 | 任务行出现 | `source_size` vs final | 裁定 |
|---|---|---|---|---|---|---|
| 8918 | `cp` | 0.23s | **16 点**（12.5MB→443MB） | 复制完成后 **2.14s** | 462033894 == 462033894 | **PASS（非半截）** |
| 8918 | `cat > dst`（流式） | 0.21s | **17 点**（25MB→417MB） | 复制完成后 **2.05s** | 462033894 == 462033894 | **PASS（非半截）** |
| 8919 | 同 8918，但**临时改回旧语义**（首事件即投递） | 0.18s | 13 点 | 复制完成后 **0.53s** | 462033894 == 462033894 | **亦 PASS** |
| 8923 | canary 协议 + **人为停顿 2.5s** 的分块 fsync 写 | 6.79s | — | **t=1.67s（半截）/ t=8.80s（完整）** | **8388608（半截）** / 223306398 | **FAIL（P1-FIX-1）** |

- **报告场景（用户 cp 大文件）确认修好**：8918 两变体都在文件落地完整之后才建任务行（`source_size==final`），复制过程中确实出现过 16/17 个半截采样点 → 说明「投递发生在完整之后」不是采样没抓到，而是真被静默窗+探针挡住了。
- **旧语义对照（必须如实记）**：同样的 `cp` 脚本在 8919（临时改回旧语义）**也 PASS**（0.53s，size==final）。原因：本机 `cp` 462MB 仅 0.18-0.23s，而 FSEvents 事件到达自身有延迟 → 旧码「首事件即投递」在**本机快盘**上往往也撞不到半截窗口。**含义有两条**：① 用户报的「偶发永久漏发现」是**时序竞态**，真机 `cp` 不是稳定判别器（这也解释了为什么它是「偶发」）；② **本修复的真牙在进程内探针（probe1/3/4）与周期兜底**，验收不能只靠「真机 cp 出任务行」。builder 自报「改前同脚本投递时 size=0、60s 零任务行」**我在本机未复现**（我用同脚本跑旧语义是 0.53s、size==final）；该差异建议 builder 补出处（是文件更大？网络盘？还是 `dd` 小 bs？），不影响本次结论。
- **排除启动竞态的方法（供 QA 复用）**：`POST /api/start` 返回 202 时 `_listener["running"]` 已置 True，而 `run_startup` 仍在后台线程（`server.py:5163-5182`），此时放文件可能被 **Step8 Startup Scan** 直接 discover（我先跑 8921/8922 就被这个竞态污染：8MB 状态在 t≈0.1s 就进库）。正解：先在 input 放 canary → 等 canary 的 run 行出现（证明 Step8 已过）→ 再静置 2s → 才放被测文件。8923 就是用此协议得到的干净结论。

## 六、反向证伪表（复核重点 5，≥3 条；禁 `git checkout`）

全部走 `/tmp/p11-cr-falsify.sh`：`改坏 → 跑 contract → 从 /tmp/p11-cr-backup 拷回 → 5 文件 sha256 逐个比对`。

| # | 变异（人话） | 咬住的断言 | rc | 还原后 sha256 |
|---|---|---|---|---|
| M1 | 改回「首事件即投递」（旧语义） | `15a`×3 全 FAIL（`投递 3 次 / 投递时 size=65536 vs final=393216 / 早于写完`） | **1** | 5/5 逐字一致 |
| M2 | 周期线程空转（`_loop` 不调 `run_once`） | `15b`×3 全 FAIL（`≤1 周期内建任务` False；`passes=0`；status `total=0`） | **1** | 5/5 逐字一致 |
| M3a | `run_startup` 不启动周期兜底（只构造不 `.start()`） | `15e 真起了周期兜底线程` FAIL | **1** | 5/5 逐字一致 |
| M3b | watcher 不拉起 flusher 线程 | `15a`×3＋`15c 事件路径先建出 1 个 run` **4 条** FAIL | **1** | 5/5 逐字一致 |
| M4 | 双采样改成「单采样恒稳」 | **全 535 PASS、rc=0 → 未咬住**（part15 对稳定性门**无牙口**）；但**我的探针 3 咬住**：真实码下同形状「不投半截、写完 +0.87s 投完整」，M4 下「**投递 size=507904 < final=720896，且早于写完 0.69s**」 | 0 | 5/5 逐字一致 |
| M5 | `DEBOUNCE_S=1.0 → 0.0`（去掉静默窗） | **全 535 PASS、rc=0 → 未咬住**：part15 用 `debounce_s=0.2/stable_s=0.2` 显式传参，绕过了模块默认值；**全仓无任何断言钉住生产默认档**（`DEBOUNCE_S`/`STABLE_PROBE_S`） | 0 | 5/5 逐字一致 |

**读法**：M1/M2/M3a/M3b 证明 part15 对「投递语义/周期兜底/线程拉起」有真牙；**M4/M5 是覆盖缺口**（P3-3/P3-4），part15 若被 M4 那样「悄悄退化成单采样」仍会全绿——而这正是 P1-FIX-1 的直接防线。

## 七、P1 / P2 / P3 清单

**P1（打回项）**
- **P1-FIX-1｜停顿 ≥1.5s 的生产者会把半截当完整投递，并可发布截断笔记。** 根因：稳定判据纯时间启发式（`watcher.py:278-291` 两次采样相隔 `STABLE_PROBE_S=0.5` 相等即判稳），投递门槛＝`DEBOUNCE_S(1.0)+STABLE_PROBE_S(0.5)`。证据：进程内 probe1（2.2s 停顿→投 64KB/131072）、真机 8923（2.5s 停顿→`t=1.67s` 建 `source_size=8388608` 的 run，最终 223306398）、且该半截 run **已发布** `vault/stall.md`（`pub_ff566ffc4dca`，ASR 40.19s vs 完整 ~25min）。改法见下；**最小改动在本次范围内即可闭环**。

  改法（按优先级，builder 任选其一并落断言）：
  1. **把「稳定」从一次采样升级为连续两窗稳定**：`_stability` 改为 3 次采样/2 个 0.5s 窗全部相等（门槛 1.5s → ≥2.5s），并在 `_flush_one` 里对「本窗 Δsize>0」**直接重排**。
  2. **加「文件年龄」门槛**：投递前要求 `now - mtime ≥ DEBOUNCE_S + 2×STABLE_PROBE_S`（把「刚写过就稳定」这种最危险的形状排除）。
  3. **把口径写成真话**：本次 DoD 不得再写「投递时 size==最终」；应写「**生产者静止 ≥1.5s 后必投完整文件；生产者停顿 <1.5s 时不会投半截**」。
  4. **补机械断言 15f**（part15 现在缺这一形状，M4 全绿即证）：单事件 + 字节持续增长（无后续事件）→ 断言「不投半截」＋「投递时 size==final」。我的 `/tmp/p11-cr-probe-stable.py` 可直接搬成 15f（带 M4 变异可在 CI/复检里咬住）。
  5. **结构项（建议 TM 判 Change B，另开链）**：同一 `path_identity_key` 后续出现更大 `size` 时，把先前 run 标 `SUPERSEDED/SKIPPED` 且**禁止发布**（或发布前复核源文件 size/mtime 未变），从根上消除「截断笔记先到先发布 + No-Clobber 挡住正确笔记」。此项落在 stage2/stage3 或 server，**不属本次 stage5 修复范围**，但它是本类风险的唯一根治手段。

**P2（非阻断，但建议本次一并处置）**
- **P2-1｜周期对账成本与库膨胀**：45s 周期 × 全库全文件 SHA-256（实测 0.008 s/MB，5GB≈39s/遍；候选表每遍每文件 +1 行且不清）。建议：① 周期放宽到 180-300s；或 ② 在 stage5 侧加「本路径 (size,mtime) 未变则跳过投递、只做 `reconcile_source` 收敛」的旁路（`reconcile.py` 已 import `stage2.runs`，可不动 stage2）。至少应在报告/HANDOFF 记明该成本。
- **P2-2｜`PeriodicReconciler.stop()` 谎报成功**：`reconcile.py:184-190` `join(timeout=10)` 超时后仍 `return True`，且 `is_running()`（`:192-193`）只看 `_stop` 标志 → `shutdown()` 报 `reconciler_stopped=True` 而线程仍在写库（探针 2-Q5 实测）。建议：`stop()` 返回真实 join 结果、`is_running()` 用 `self._thread.is_alive()`；大库下把超时对齐单遍上界。
- **P2-3｜flusher 串行 × 0.5s/文件**：`_flush_loop:251-259` 逐个 `_flush_one`，每次 `_stability` 阻塞 0.5s → 批量投递吞吐约 **2 文件/秒**（61 个新文件批量落盘时，最后一个要多等 ~30s 才被投递）。周期兜底能兜住，但建议对同批 due 路径并发探针或按批共享一次采样。

**P3（backlog，非阻断）**
- **P3-1**：`stop()` 后 `_flush_stop` 不复位（`watcher.py:186`）；当前 watchdog Observer 本就不能重启（既有），但属埋坑。
- **P3-2**：`stop()` 竞态下仍可能投一次：`_flush_loop:257` 的 `_stopped` 检查在 `_flush_one` 之前，而 `_stability:284` 的 `wait` 在 stop 后会立即返回 → 两次采样退化为背靠背 → 可能判「stable」并投递（P1 修好后的下一条触发路径，建议与 P1-FIX-1 改法一并收紧）。
- **P3-3**：生产默认档（`DEBOUNCE_S=1.0`/`STABLE_PROBE_S=0.5`）**无断言钉住**（M5 全绿即证）；`FLUSH_TICK_S` 未进 `__all__`（与其他可调常量不一致）。建议加「默认值钉值」断言。
- **P3-4**：part15 缺「事件丢失 + 字节仍变」形状（M4 全绿即证）→ 见 P1-FIX-1 改法 4。
- **P3-5**：`docs/pm/STAGE5-PLAN.md:47`（P0-6 措辞）与 `docs/qa/STAGE5-QA-REPORT.md:24/:52/:65`（A5）在新语义下观测口径已变（首投 `PROMOTED`）；建议 neat-freak 加注不改正文（探针 4 有实测值）。
- **P3-6**：投递后 `touch`/重复事件会重复投递（At-Least-Once 合法，`discover` 折叠 `MERGED`、不新建 run，探针 2-Q1 实测）——记录为**非缺陷**，勿被后续复检当回归。

## 八、未覆盖项（如实标注，不推断为通过）

1. **「自然停顿」未验证**：我未能证明「本机普通 `cp` 会自然出现 ≥1.5s 停顿」（462MB `cp` 0.23s、分块 fsync 慢写 4.5s 全程最大间隙 <0.5s）。P1-FIX-1 的触发在本次是**人为 2.5s 停顿**；网络盘/下载中/磁盘繁忙的真实概率**未测**（这决定 P1 的实际暴露面，建议 QA 用网络卷或限速下载补测）。
2. **半截 run 的最终归宿未跑完**：`vault/stall.md` 已存在后，正确 run 是否真的被 No-Clobber 判 `EXISTS/CONFLICT` 而不写入——需要 223MB 视频的完整 whisper（约 25 分钟音频），本次预算内未跑；结论按项目既定 No-Clobber 规则**推断**。
3. **周期兜底的真机长跑未做**：>45s 的连续运行观察、周期 pass 与 whisper 抢 I/O 的实测影响未做；P2-1 的成本是单遍实测外推。
4. **未跑**：真实 61 篇基准、长视频端到端（属 P1-1 主体）、UI 目检（本次无前端改动）、`stage11` 启动链/故障套件的端到端（只做了静态依赖面核对）。
5. **未验证**：`_stability` 在文件被 `mv` 到别处/符号链接变化时的行为（只覆盖了「投递前消失 → 丢 pending」这一条路径的读码，未做真机探针）。

## 九、结论

**打回（FAIL）。** 三套自测 535/167/58 全 rc=0（与 builder 自报逐字相符）、范围零越界（5 文件、`app/server.py` 与 `src/stage2/candidate.py` 字节未变、AST 无 REMOVED）、原 `BUG-P11-1` 的「永久漏发现」与「周期兜底/幂等/线程清理/异常不吞」经独立探针与真机复验**确认已修**（真机 `cp` 462MB → 2.14s 出任务行、`source_size==final`；零事件场景 ≤1 周期内建任务；事件路∪周期路仍 1 run/1 source）。**但**：

1. 本修复的验收口径「只投 1 次且投递时 size==最终」**不是不变量**——生产者停顿 ≥1.5s 时会把半截当完整投递（进程内 probe1 ＋ 真机 8923 双重确定性复现），且真机已把 **40.19s 的截断转写发布进 vault**，正确 run 很可能被 No-Clobber 挡在外（P1-FIX-1）；
2. part15 对「双采样稳定门」与「生产默认档」**无牙口**（M4/M5 变异全绿），即退化成单采样也无人报警（P3-3/P3-4）；
3. 周期兜底引入两处新的运行时代价/失真（全库 45s 全文件哈希 + 候选表膨胀；`stop()` 谎报成功），建议随本次一并处置（P2-1/P2-2）。

**改法收口（最小、在本次范围内）**：P1-FIX-1 的 1＋2＋4（连续两窗稳定 + 文件年龄门槛 + 补 15f 断言）、P2-2（stop 真值）、P3-3（默认档钉值）；**P1-FIX-1 的结构项 5（同路径更大版本取代旧 run / 禁止发布半截）建议 TM 判 Change B 另开链**。若 TM 判 P1-FIX-1 的残留可接受，则**最低要求**是：口径改写为「生产者静止 ≥1.5s 后必投完整」＋记 P1 挂账（含本报告 §三 A 的 vault 证据）＋补齐 15f，不得以「已验证」字样收口。

---

> 取证留存（全部在系统 tmp，非仓库）：探针 `/tmp/p11-cr-probe1.py|probe2.py|probe-stable.py|probe4.py|scope.py|real2.py|slow6.py|clean.py|stall.py|falsify.sh`；日志 `/tmp/p11-cr-*.log`；备份 `/tmp/p11-cr-backup/`；真机夹具 `/tmp/p11-cr-real2-main2/`、`/tmp/p11-cr-clean-clean1/`、**`/tmp/p11-cr-stall-s7a/`（截断笔记与两条 run 的物证，vault/stall.md ＋ jobs/run_38f1*/manifest.json）**。本报告为本轮唯一新增文件。

---
---

# 返工复核（第二轮，接首轮打回项 P1-FIX-1 与 P2-1/P2-2/P2-3）

- Task: **DEVELOP-P1-1-FIX 返工复核**。builder 返工后自报改 **6 文件（新增 `app/server.py` +71，理由＝「半截不发布」需要 app 侧发布门）**、三套自测 **571/167/58**、真机 8912 复验、12 条变异全 rc=1。
- Commit: **未提交**（工作树，基线 `HEAD=7b97aaa`，未变）。`git diff --numstat HEAD` 实测＝`app/server.py 71/0`、`src/stage5/__init__.py 21/2`、`src/stage5/reconcile.py 179/7`、`src/stage5/startup.py 32/5`、`src/stage5/watcher.py 237/16`、`tests/selftest_p1_2_contract.py 571/0`（6 files，**+1111/−30**），与自报范围一致。
- Reviewer: code-reviewer（同链续做返工复核，独立复跑＋自写探针；首轮正文一字未改）
- **Result: PASS 带 P2/P3（本轮返工闭环，不再打回）** ＋ **1 条必须由 TM 拍板的开口**：首轮 P1-FIX-1 的**残留形态（「永久停在半截」＋可解码容器）本轮被我真机实证仍会发截断稿**——本次修复范围内无法关闭，须判 Change B 或写成产品已知限制（见 §R5「挂账裁定」）。

> 复核口径（同首轮）：只读业务代码 ＋ 独立跑三套自测 ＋ 自写探针（`/tmp/p11b-probeA.py` 阈值扫描/尾延迟/批处理/周期成本/stop 真值、`/tmp/p11b-probeB.py` 发布门矩阵与端到端、`/tmp/p11b-real.py` 真机、`/tmp/p11b-half.py` 永久半截、`/tmp/p11b-m4diff.py` 年龄门差分、`/tmp/p11b-falsify.sh` 7 条变异）。**未改业务代码**（7 次变异全部「改坏→跑→从 `/tmp/p11b-backup/` 拷回→6 文件 sha256 逐字一致」，**未用 `git checkout`**）。真机端口 **8925/8926/8927**（禁 8765，未碰 8899/8900）；夹具全在新 tmp 根；真实视频只**读** `/tmp/p11-real/input/`；收工后端口全释放、6 文件 sha256 与开工逐字一致（`SAME_ALL`）、工作树仍只有 6 个 `M` ＋ 2 个既有 `??` ＋ 本报告。

## R1｜我自己跑过的命令与退出码

| # | 命令 | 实测输出 | rc |
|---|---|---|---|
| 1 | `.venv/bin/python tests/selftest_p1_2_contract.py` | `SELFTEST ALL PASS（**571** 项断言）`（part15 扩到 `^PASS 15`=**54**） | **0** |
| 2 | `.venv/bin/python tests/selftest_p1_2_frontend.py` | `FRONT ALL PASS`（`^PASS`=**167**） | **0** |
| 3 | `.venv/bin/python tests/selftest_v26_presets.py` | `SELFTEST ALL PASS`（`^PASS`=**58**） | **0** |
| 4 | `.venv/bin/python -m py_compile app/server.py src/stage5/*.py` | 无输出 | **0** |
| 5 | `git diff --name-only HEAD` ＋ 关键文件 `git show HEAD:f \| shasum` | 改动＝**6** 文件；`src/stage2/*.py` 5 个关键文件、`app/index.html`、`src/stage1/3/4/6-12` 全部 **SAME**（逐字节） | 0 |
| 6 | `python /tmp/p11b-scope.py`（AST 逐函数/类/常量比对，含 app/server.py） | `same=285 changed=17 added=32 removed=0`；`app/server.py` 仅 **ADDED 1 常量＋1 函数、CHANGED 仅 `_process_one_run`** | 0 |
| 7 | `python /tmp/p11b-probeA.py`（阈值扫描/尾延迟/批处理/周期成本/stop 真值） | 见 §R3、§R4 | 0 |
| 8 | `python /tmp/p11b-probeB.py`（发布门矩阵＋端到端） | 见 §R2 | 0 |
| 9 | `python /tmp/p11b-real.py $PWD 8925`（真机：正常发布＋停顿＋正常 cp） | 见 §R4 | 0 |
| 10 | `python /tmp/p11b-half.py $PWD 8926 / 8927`（永久半截，两种容器） | 见 §R5 | 0 |
| 11 | `python /tmp/p11b-m4diff.py`（年龄门在/不在 差分） | 四形状无差异 | 0 |
| 12 | `bash /tmp/p11b-falsify.sh`（M1-M7） | **6/7 咬住**（M4 未咬住）；7/7 还原 sha256 逐字一致 | 0 |

**基线 sha256（开工自分自算，收工 `diff` 复核 `SAME_ALL`）**：`app/server.py c2644135…e2e3f0`、`watcher.py 233356fb…75f9ab8`、`reconcile.py b07dab0f…9332cb7`、`startup.py 159d2148…3e22f9b8`（与首轮相同，未再改）、`__init__.py 55707685…ee2a42a9`、`selftest_p1_2_contract.py e9f4e1ee…0f7ed428`。备份：`/tmp/p11b-backup/`。

## R2｜越界改动严查（`app/server.py` +71，本轮最关键）——**裁定：必要且可接受，不构成越界打回**

- **① 是否最小必要**：发布/不发布的**决策点在 app 侧 worker**（`_process_one_run` 的 raw→norm→render→`initial_publish` 链路），stage5 够不到；stage5 只能改「何时投递」，改不了「已建的 run 要不要写库」。两道门对应**两个真实窗口**：`queue→转写`（gate 1，省掉整段无用算力）与`转写几分钟→写库`（gate 2，本轮真机上正是它兜住的——写方在转写期间续写）。去掉 gate 1 只能省 ~10 行，但会让半截件白跑一遍 ffmpeg/whisper；去掉 gate 2 则回到「截断稿落库」。**结论：两门皆必要，~71 行中逻辑本体约 30 行（其余为文档/中文判词），近乎最小。**
- **② 会不会误伤正常发布 —— 独立实测：不会。** 探针 B1 六格矩阵（真源行＋真文件）：`未动 → None（0.000s，零成本）`；`仅 mtime 变但已静止 → None（付一次 2.004s 采样，不判死）`；`尺寸变 → 拦`；`mtime 变且仍在长 → 拦`；`快照 0/-1（旧行）→ None（不误杀历史数据）`；`文件不存在 → None（交给既有「找不到」分支）`。**真机端到端**（F1）：真实 30s 视频切片经 startup scan 发现 → 转写 → render → **`canary-clip.md` 已发布（261 字 / 3.6s）**——两道门在位时正常文件照常入库。
- **③ 失败路径只记 FAIL、不产生任何 vault/job 写入 —— 实测成立（gate 1）；gate 2 落地时必须已有 job 目录（转写已完成），但同样零 vault 写入。** 探针 B2（真 watcher 把半截件投成 run → 写方续写 → 真调 `_process_one_run`）：`state=FAIL`、`whisper_calls=None`、耗时 0.00s、`vault=[]`、`jobs/<run_id>` **不存在** ✓。**修正自报口径**：builder 自报「不建 job 目录」只对 gate 1 成立；gate 2 落点必然已有 `raw/normalized/render` 产物（它按设计在转写之后），只保证不写 vault。另：gate 2 会写一条 `STALE_SOURCE_SKIPPED` receipt 进 manifest（job 目录内，非 vault）。
- **④ 既有语义未破坏**：门在 `initial_publish` **之前**，No-Clobber（`EXISTS/CONFLICT 只判不写`）语义不受影响；判词只含尺寸数字（`大小 %d→%d`）**不含路径**，且走既有 `_worker_record → /api/status` 通道，D-12 脱敏口径不变；`_strip_paths`／`_handle_status`／`_scan_disk_states`／`_transcribe_worker`／`_worker_record`／`_handle_start_post` 等 **AST 全部 same**（server.py 的 CHANGED 只有 `_process_one_run`）；四层状态未改结构（新 FAIL 复用既有 FAIL 形状）。**但见 §R6 P2-c**：新门的终态口径在汇总层没接上，是真问题（非既有语义破坏，属新面）。
- **⑤ 范围机器证实**：除 6 文件外**零改动**；`app/index.html`、`src/stage2/`（含 `discover`）、`src/stage1/3/4/6-12/` 逐字节 SAME；AST `removed=0`。
- **口径重复（P3）**：`_stale_source_reason` 的「size/mtime 身份」判据与既有 `_diag_identity`（`app/server.py:1470-1486`，同为 size+mtime 比对，差异是它要求 hash 相等、mtime 不等即 MISMATCH）**同源但有意宽严不同**（新门容 `touch`）。建议加一句交叉注释或抽公共 `_source_snapshot_matches`，避免日后两处口径漂移。

## R3｜稳定门取值合理性与副作用（复核重点 3）

实测默认档：`DEBOUNCE_S=3.0`、`STABLE_PROBE_S=2.0`、`STABLE_ROUNDS=3`、`BUSY_CHECK=True` → 最小文件年龄 **7.0s**（15f 已全部钉值——首轮 P3-3 已闭环）。

- **停顿阈值扫描（默认档，真 watcher＋真行为）**：`2.5s → 不投半截`；`5.0s → 不投半截`；`6.5s → 不投半截`；**`7.5s → 投半截（size=8192 / final=65536，首投在写完前 0.47s）`**。即**实测边界落在 6.5–7.5s 之间，与文档「~7s」相符**；也说明这是**时间启发式的内在上限**，不是实现缺陷。
- **尾延迟（用户体感）**：64KB 与 4MB 文件均为**写完 +7.08~7.11s** 才投递（首轮 1.5s、原始版 0.25s）；真机 462MB 正常 `cp`（0.13s 落地）**任务行 11.60s 才出现**（含 tick/采样排程，7-12s 区间）。**裁定：可接受但属用户可感变化**（工具后续转写以分钟计），建议在文档/HANDOFF 记明「入队前静置约 7s 确认写完」，避免被当成卡顿；4 个常量已集中且被 15f 钉住，日后要调只需一处。
- **批处理**：6 文件同时落盘 → **全部 7.10s 投递、首末跨度 0.00s**（共享一次裁决）→ 首轮 P2-3 已闭环。
- **`BUSY_CHECK` 的诚实边界**：`flock` 只能探到持锁写方（本项目/部分下载器），`cp`/浏览器下载不持锁——docstring 已如实写明，不夸大。

## R4｜反向证伪（复核重点 4，抽验 7 条，禁 `git checkout`）

| # | 变异 | 咬住情况 | rc | 还原 |
|---|---|---|---|---|
| M1 | watcher 改回「首事件即投递」 | `15a`×3＋`15g`×4＋`15h` **共 8 条** FAIL | **1** | 逐字一致 |
| M2 | `STABLE_ROUNDS 3→1`（单采样） | `15f`×2＋`15g`×4＋`15l`×2 **共 8 条** FAIL ← **首轮「M4 型无牙」已补上** | **1** | 逐字一致 |
| M3 | `DEBOUNCE_S 3.0→0.0` | `15f`×2 FAIL ← **首轮「M5 型无牙」已补上** | **1** | 逐字一致 |
| M4 | **去掉最小年龄门（too-new）** | **全 571 PASS、rc=0 → 未咬住** | 0 | 逐字一致 |
| M5 | 去掉 app gate 1（转写前复核） | `15i`×3 FAIL（含「job 目录都没建」） | **1** | 逐字一致 |
| M6 | `PeriodicReconciler.stop()` 谎报 True | `15k` FAIL | **1** | 逐字一致 |
| M7 | 周期「身份未变不重投」改成永远不重投 | `15j`「文件变了必须重投」FAIL | **1** | 逐字一致 |

- **M4 的差分复核（我自己加做）**：年龄门「在 / 不在」两版各跑 4 个停顿形状（2.5/5/6.5/7.5s），**投递次数、尺寸、首投时刻逐格相同**。原因可推演：投递裁决发生在 `deadline+（轮数-1）×采样间隔`，而 `mtime ≤ 最后一次事件`，故`此刻年龄 ≥ 7s`在该排程下**恒真**——年龄门只在「最后一次事件之后仍有不带事件的续写」形状才显形。**裁定：该门是冗余防线（当前不可观测），且无断言（P3-a）**；建议 builder 要么补一条能咬住它的形状（无事件续写），要么删掉以免被误认为有牙。

## R5｜真机复验（复核重点 2/6）与挂账裁定（复核重点 5）

夹具＝新 tmp 根；真实视频 462.0MB（`/tmp/p11-real/input/` 最大的那个）只读；`source_size` 取自 `sources` 表（＝discover 落库快照）。

| 场景 | 端口 | 实测 | 裁定 |
|---|---|---|---|
| **正常发布不误伤**（真实 30s 切片） | 8925 | 发现→转写→render→**`canary-clip.md` 已发布（261 字，3.6s）** | **PASS** |
| **停顿 10s（>门）+ 续写** | 8925 | 半截（8MB）在门后仍被登记成 run（快照 8388608）；**gate 1 拦下**：`FAIL / 大小 8388608→462033894 / 这一条已跳过，不会写进笔记库`；**`jobs/` 无该 run 目录、vault 无该文件稿** | **PASS（首轮 P1-FIX-1 的「截断稿落库」已闭合）** |
| **写完后自动按最新内容重排** | 8925 | 同路径出现**第二条 run**（快照=462033894=final，13:31:16），worker 已开始转写完整件 | **PASS** |
| **正常 `cp` 462MB** | 8925 | 复制 0.13s；**任务行 11.60s 出现，快照==final** | **PASS（非半截）** |
| **永久半截①（非 faststart 容器）** | 8926 | 冻结的 8MB 前缀（永不续写）→ ffmpeg `moov atom not found` → `state=FAIL`，**vault 空** | 安全（容器救了） |
| **永久半截②（faststart 容器，实测可解码 28.4s/60s）** | 8927 | 冻结的 50% 截断件（12.0MB）→ 两道门都放行 → **`frozen-half.md` 已发布（250 字，state=PUBLISHED）** | **挂账②成立（P2）** |

**挂账裁定**

- **① 「停顿 >7s 的写方仍会被当写完」→ P2（非 P3，不须 Change B）**。实测后果已被两道门收窄为「白建一条 run ＋ 一次无用转写/或一次 gate1 秒拦 ＋ 一条 FAIL 行」，**vault 安全**（8925 实测）；属成本/噪声，不是内容风险。修法方向：无需新机制，把入队前的门做成可按文件大小/写入速率自适应（或接受 7s 固定档），并在 UI/文档说明「入队前静置」。
- **② 「永久停在半截仍会发截断稿」→ P2，且我判「需 Change B」**：8927 实证（faststart 截断件 → 250 字截断稿落库、`PUBLISHED`）；8926 说明该后果**依赖容器布局**（非 faststart 的 mp4 会在 ffmpeg 阶段安全失败）——但 faststart 是 ffmpeg/下载/手机导出的**常见**形态，不能靠运气。当前 size/mtime 门**原理上**判不了「静止但内容不完整」，故本次修复范围内不可关闭。一句话修法方向：**让同一 `path_identity_key` 的后续更大版本取代先前 run（旧 run 标 SUPERSEDED/SKIPPED 且禁止发布）**，或发布前要求「源内容身份已被最终确认」。**建议按 Change B 走**（若 TM 判其触及 No-Clobber/任务身份契约则升 C）；在开 Change C/B 之前，**必须把它写成产品已知限制**（用户可见提示或文档），不得静默。

## R6｜残留问题清单（本轮新增）

- **P2-a（最高优先，需 TM 拍板）**：「永久半截 ＋ 可解码容器」仍会发截断稿（§R5 8927 实证）。→ Change B 或产品已知限制。
- **P2-b**：停顿 ≥7s 的写方会白建一条 run ＋ 一次无用转写 ＋ 一条 FAIL 行（vault 安全）。成本/噪声，可接受但应记录。
- **P2-c（新的终态口径缺口）**：gate 拦下的 run **在汇总层不显示为失败**。真机实测 `run_summary={'total':4,'done':1,'failed':0,'pending':3}`——被 gate 1 拦下的行既无 job 目录也无 manifest，`run_summary`（`app/server.py:2802-2859`）只按 `_scan_disk_states` 分桶 → 判为 **pending（排队中）**，而判词只在内存 `worker.processed`（重启即失）→ 用户看到**永久「排队中」的幽灵行**且无解释。建议：让 `run_summary` 复用 `/api/status` 已有的「内存覆盖磁盘」合并（`_listener_snapshot` 里已有该合并逻辑，约 5 行），或给门写一个**不建 job 目录**的轻量终态标记（后者会与 15i「连 job 目录都没建」的断言冲突，需与 builder 对齐口径）。
- **P3-a**：最小年龄门**无任何断言**（M4 全绿）且差分实测当前不可观测（§R4）；建议补一条「无事件续写」形状的断言或删除该门。
- **P3-b**：入队尾延迟由 0.25s→1.5s→**7-12s**，属用户可感变化；建议文档/HANDOFF 记明（4 常量已集中且被 15f 钉住，便于调）。
- **P3-c**：`_stale_source_reason` 与 `_diag_identity` 判据同源、宽严有意不同；建议交叉注释或抽公共判定，防口径漂移。
- **P3-d**：gate 2（写库前）本轮**真机未端到端跑到**（8925 的窗口被 gate 1 更早拦下）；其有效性由单元（15i）×源码顺序（我 B3 实测：gate1 早于 job 目录创建；gate2 在 `STAGE_PUBLISHING` 之后、`initial_publish` 之前）＋首轮 8923 的「半截 run 曾走完 raw→normalize→render→publish」形状共同支撑。
- **既有（非本链引入，仅记账）**：`processing_runs.status` 在成功后仍为 `QUEUED`（8925 的 canary run 已 PUBLISHED 而 DB 仍 QUEUED）——qa 报告已记为终态口径异常，本次未扩大。

## R7｜未覆盖项（如实标注）

1. **gate 2 真机端到端**：需「gate 1 放行 → 转写期间写方续写」的窗口（本轮被判词文本与 job 目录存在性间接区分，未直接目击 second-window FAIL 的完整时序）。
2. **`BUSY_CHECK` 真机有效性**：in-process 15h 已验（持锁写方）；真机未构造持锁写方。
3. **周期兜底真机长跑**（>45s）与 5GB 级库的单遍成本：本轮只做了 6×8MB 的稳态实测（0.006s/遍）＋外推，未跑大库。
4. **未跑**：61 篇基准、长视频端到端（均属 P1-1 主体，不属本次返工复核）。
5. **产品已知限制的措辞**（P2-a/②）尚未在任何用户可见位置落字——属 TM/后续文档动作，不在本报告职责内。

## R8｜结论

**PASS 带 P2/P3（本轮返工闭环，不再打回）。** 依据：① 三套自测 **571/167/58 rc=0**（`py_compile` rc=0），与自报逐字相符；② 范围机器证实：仅 6 文件，`src/stage2`/`src/stage1,3,4,6-12`/`app/index.html` 字节未变，AST `removed=0`，`app/server.py` 只动 `_process_one_run`（+1 常量 +1 函数）；③ **越界改动裁定＝必要且可接受**（两门对应两个真实窗口、无更小等效改法、不破坏 No-Clobber/四层状态/脱敏，正常发布实测未被误伤：真实切片照常入库）；④ 首轮 P1-FIX-1 的**「截断稿落库」主危害已闭合**（真机 8925：半截 run 被门拦下、`vault` 零写入、`jobs/` 无该 run 目录；12 条变异我抽验 7 条，6 条咬住）；⑤ 首轮 P2-1（周期成本）**实测修复**：稳态每遍 **0.36s → 0.006s**、候选行不再每遍增长（`+0/+0`）、文件变了仍会重投；P2-2（stop 谎报）修复（跑不完时 `stop()=False`、`is_running()=True`）；P2-3（批处理串行）修复（6 文件跨度 0.00s）；⑥ 7 次变异 7 次 sha256 逐字还原。

**条件性开口（唯一）**：**P2-a「永久半截仍发截断稿」本轮真机实证（8927）**——本次修复的设计原理无法关闭它。请 TM 拍板：**(a) 开 Change B（推荐，修法：同路径更大版本取代旧 run＋禁止发布）**，或 **(b) 记为产品已知限制并在用户可见处写明**；两条路都不得「静默挂账」。其余 P2-b/P2-c 与 P3 可随链收口进 backlog（P2-c 建议本次顺手修，属 app 侧 ~5 行且直接影响用户看到的状态口径）。

---

> 返工复核取证留存（全部系统 tmp，非仓库）：探针 `/tmp/p11b-probeA.py|probeB.py|real.py|half.py|m4diff.py|scope.py|falsify.sh`；日志 `/tmp/p11b-*.log`；备份 `/tmp/p11b-backup/`（含 `sha256.txt`）；真机夹具 **`/tmp/p11b-real-8925/`（正常发布 `vault/canary-clip.md` ＋ 半截 run 无 job 目录的物证）**、**`/tmp/p11b-half-8927/`（截断稿 `vault/frozen-half.md` ＋ `PUBLISHED` 判词的物证）**、`/tmp/p11b-half-8926/`（非 faststart 半截在 ffmpeg 阶段安全失败的对照）、`/tmp/p11b-clip30.mp4`、`/tmp/p11b-fs60-trunc.mp4`。本报告为本轮唯一改动文件。
