
# CODE REVIEW

- Task: 复核src/stage11/（对照STAGE11-PLAN + §67范围/禁真实目录禁enable/Stage12禁入）
- Commit: n/a（工作区无 git，核对对象为 src/stage11/ 五文件现状：__init__.py / launch_plist.py / agent_boot.py / reliability.py / fault_suite.py）
- Reviewer: code-reviewer（opencode-go/glm-5.3-flash）
- Result: 打回（P0 全过；P1×5 必修见下，builder 修完 + QA 重跑即可关；P2×7 记 backlog；本复核独立静态 + 外置合成实测，改法见各条）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## P0 / P1 Findings

- P0 全过。本轮硬门逐项通过，证据如下（本机独立实测于 /tmp/s11cr_* + /tmp/s11boot_* + /tmp/s11full_*，外置合成、最大文件 2816B；`python3 -m py_compile src/stage11/*.py` 通过）：
  - P0-1 plist（S11-T01，§69/§72）：`launch_plist.py:79-131` Label 强制测试域前缀 + ProgramArguments 全绝对路径（含 `--asr-profile-hash` 值跳过）+ WorkingDirectory/RunAtLoad/KeepAlive/ThrottleInterval/StdOut-Err 进 `<data_root>/logs/`；`write_plist:142-162` 测试目录前缀门 + 真实目录拒写；`validate_plist:165-235` `plutil -lint` 过 + 读回绝对路径/字段断言；`load/unload:247-301` 只对测试 plist 且 unload 后 `list` 无残留。本机 build→write→validate `PASS`，真实目录（`~/Library/LaunchAgents`）拒写已证，坏 Label 拒写已证。
  - P0-2 Cold Boot（S11-T02，§62 11 步）：`agent_boot.py:54-89` 直调 `stage5.startup.run_startup` 并逐字比对 `STARTUP_ORDER`（倒置/跳步 raise），`running` 非 True 即 raise；`assert_second_instance_blocked:136-174` 子进程 `startup` 必 `SecondInstanceError`→exit 3 且 DB mtime 不变。本机 order 11 步逐字一致、`RUNNING` 可达、第二实例 `PASS/3/mtime_stable`，`reboot_equivalent:99-111` 记账 `true_reboot_performed=False`（无真 reboot）。
  - P0-3 Crash 矩阵（S11-T03，§67）：`reliability.py:43-137` snapshot/assert_running/relaunch/assert_recovered（Lost=缩表判负、Dup=四表零动、`archive_commits` 非预约零动、whisper 增量恒 0）+ `archive_midcopy_drill:192-236`（pre-unlink 切 + `recover_midcopy` 修）+ `power_loss_best_effort_note:166-176`（`true_power_test_performed=False`，`PASS-BY-BOOKING`）+ `describe_reboot_equivalent:179-189`（`PASS-BY-EQUIVALENCE`）。本机 snapshot→assert_running `PASS`→零 delta `assert_recovered PASS`。
  - P0-4 Fault 套件（S11-T04）：`fault_suite.py:58-61` 注册表复用 7（F-R1~R7）+ 新增 4（F-N1~N4），`run_all:589-645` 逐用例 verdict/exit 码 + 套后 RUNNING 探针 + `max_file_bytes`/`small_files_only`。本机 `run_all`（预先 cold_boot）11/11 PASS、`running_probe PASS`、`max_file_bytes=2816`、`small_files_only=True`。全绿结论 harness 相关（见 P1-1/P1-3），归因强度见 P1-2。
  - P0-5 STOP EXPANSION 门：`rg -i "menu|golden|\bcer\b|openai|anthropic|requests\.|llm|summar|polish|paraphras|rewrite|force|overwrite|clobber|enable" src/stage11/` 零命中；`rg "sqlite3|INSERT|UPDATE|DELETE" src/stage11/` 零命中（中央库写只经预约路径：`fault_suite.py:398-426` `stage10.commit.commit_archive_success` 已在模块 docstring 披露为 booked writer，`reliability.archive_midcopy_drill` 经 `level_b` 公开调用，生产文件 `launch_plist/agent_boot` 零 level/gate 写柄）；生产 import 面仅 stdlib + `stage5.startup` + `stage2.store/instance`（`agent_boot`），`launch_plist` 纯 stdlib；文件名无 Stage12 关键词；`src/stage1-10/` diff 门：工作区无 git，静态替代——stage11 内无任何写盘路径指向 `src/stage1-10/`（写操作仅测试 agent 目录/data_root logs/外置 root 下，`rg unlink/remove/open` 已核），文件级 diff 留 QA 在有基线环境补断言。
  - P0-6 外置合成门：属 QA 执行域；代码侧写删目标全由调用方传入 root 决定，真实 LaunchAgents 恒拒（`_refuse_real_dir:57-62` + 四处调用点），`enable` 字串零出现（无持久化路径），网络/转写引擎 import 零（仅 `asr_calls/whisper_calls=0` 证据字段）。
- P1-1 `fault_suite.py:589-645` `run_all` 锁排序错：无预持锁直调 `run_all` 本机 7/11 FAIL（F-R1/R3/R4/R5/N1/N2/N3 全 `LockNotHeldError`，仅 stage1 作业目录的 F-R2/R6/R7 过）。`run_all` 只在套后才为 `running_probe` cold_boot，套前不断言/不建锁。改法（二选一）：首选 `run_all` 起始加 `if ctx.get("boot") is None: ctx["boot"] = _boot.cold_boot(…)`（持锁后再跑用例，与现有 `boot` 复用语义一致）；或入口 `require_lock` 失败即 fail-fast 明示“先 cold_boot 再 run_all”。+ QA 补一例无锁直调（期望 FAIL-fast 而非 7 个散 FAIL）。
- P1-2 `fault_suite.py:266-299` F-R4 与 `:449-492` F-N2 归因过弱：两者只断言 `verdict==BLOCK`，本机孤立重放 F-R4/F-N2 的 gate code 均为 `BLOCKED_ARCHIVE_NO_PUBLISH`（无 PUBLISHED 行先拦），目标已占（`BLOCK_ARCHIVE_EXISTS`）与诱饵被改（`BLOCK_CANONICAL_EDITED`）两条真卫从未被命中。F-N2 自带 note 承认“stops at NO_PUBLISH”，属用正确结论盖错原因的过宣。结构 tension：gate 全序 verify→publish→target，Stage11 四表零新增门下 publish 行建不出，真卫天然不可达。改法：不建 publish 行前提下二选一——(a) 收敛宣称：F-R4 改名断言“publish 门 BLOCK + 源留 + 目标零覆盖”（`cover==0` 已有）并记录实际 code，F-N2 同理记 `NO_PUBLISH` 而非 canonical-race；真 target/canonical 卫留给拥有 publish 夹具的阶段；(b) 建 publish 夹具则先找 TM/supervisor 豁免四表门（默认不选）。无论选哪，断言必须加 `code` 相等（现状任一 BLOCK 即过，回归卫不住）。
- P1-3 探测/用例与 RUNNING watcher 竞态，无重试：`fault_suite.py:109-112` `_discover` 单发，`source_id None`（`WAITING_FOR_STABLE_FILE` 或并入 watcher 未提升 provisional）即直接进 gate 得 `ARCHIVE_UNKNOWN_SOURCE`→FAIL。本机复现：同一 ctx 内手动 discover 成功后紧调 `case_r4_target_race` 得 `FAIL/ARCHIVE_UNKNOWN_SOURCE/source_id None`；`run_all` 同序另一次全绿（时序敏感）。改法：加 `_discover_ready(data_root, path, profile, tries=5, sleep=0.1)`（`source_id is None` 即重试，`WAITING` 亦重试；5 次仍 None 才 FAIL 并附末次 status），F-R1/R3/R4/R5/N1/N3 六处 `_discover` 全切过去；或 drills 期暂停 watcher（改动大，默认选重试）。
- P1-4 `agent_boot.py:92-111` + `reliability.py:82-94` 重启不断锁语义：`shutdown_agent` 只停 workers/watcher（`stage5.startup.shutdown` 本就不释锁），同进程 `relaunch/reboot_equivalent` 的 `acquire` 是 no-op（`instance.py:82-83` 同 key 直接 return），故“stop-all + relaunch”从未证明锁释放后重获——真重启恰恰要过这一关。改法二选一：(a) `reboot_equivalent/relaunch` 在 shutdown 后显式 `instance.release(data_root)` 再 `cold_boot`（证明重获；窗口内第二实例探针仍由 `assert_second_instance_blocked` 覆盖）；(b) 不改代码则收敛宣称：relaunch 只证 watcher/workers 重启 + 顺序/RUNNING，锁跨进程交接仅由子进程 exit-3 用例证明，并把 (a)/(b) 记 HANDOFF。默认选 (a)（`release` 缺 key 幂等，注意异常吞掉前先释锁）。
- P1-5 S11-T03 点名的 `kill9` helper 缺失，真信号路径零：`reliability.py` 只有 `snapshot/relaunch/assert_*`，无 `kill9` 具名函数；全部“kill”以 `on_pre_unlink` 抛异常扮演（`reliability.py:210-216`、`fault_suite` F-R3/N1 同）。异常钩与真 SIGKILL 不等价窗口（页缓存未刷、fd 未关、WAL 未 checkpoint）未被论证。改法：加 `kill9_child_relaunch`（子进程持 job 中 `os.kill(pid, SIGKILL)`→父进程 `relaunch`→`assert_recovered`），至少覆盖 job 中 SIGKILL 一项；其余窗口（rename 前/mid-copy）保留钩模拟亦可，但须在 `reliability.py` 头注逐窗写明“钩≈kill 的等价主张 + 未覆盖面”，QA 按窗验收。

## P2 / P3 Backlog Findings

- P2-1 `reliability.py:151-163` `write_small_bytes` 无合成上限（`fault_suite._write:75-85` 有 64KB 门）。改法：同加 `MAX_SYNTHETIC_BYTES=65536` 拒写，或文档注明仅 fault_suite 路径受 cap。
- P2-2 `agent_boot.table_snapshot:124-133` / `reliability.snapshot:43-63` / `fault_suite._snapshot_counts:88-95` 自称只读却用 `open_db(require_lock_held=True)` 默认值，无锁即 `LockNotHeldError`（P1-1 根因之一）。改法：纯读改传 `require_lock_held=False`，或文档注明“快照要求预持锁”。
- P2-3 macOS-only 未明示：`plutil -lint` + `launchctl load/unload/list` 在 Linux 无对应，本机 Mac 全过，Linux 下 F-N4 必 FAIL（`_list_has_label` 回 False）。改法：README/QA 注明套件限 Mac 跑，或 `run_all` 检不到 `plutil/launchctl` 即 SKIP F-N4 并记因。
- P2-4 `launchctl load/unload` 为遗留子命令（新系统主推 `bootstrap/bootout`）。改法：保持现状可，但加 TODO 注；若切新命令须重验“演练后无残留”。
- P2-5 `agent_boot.py:136-174` mtime ns 全等判稳：RUNNING watcher 后台投递恰在子进程窗口写库即误 FAIL。改法：子进程前后加静默等待或放宽为 `after >= before` + 本用例前后无本进程写断言，或 drills 期暂停 watcher（与 P1-3 同解）。
- P2-6 F-N4 断言过紧：`fault_suite.py:561-565` 要求 load 后 `list_visible is True`、unload 后即 `False`，launchd 可见性有时延。改法：可见/消失各加 bounded poll（如 5×0.2s），仍不见才 FAIL。
- P2-7 `build_plist` 未校验 `throttle_interval`（负数/零直进 plist）。改法：一行 `if int(throttle_interval) < 0: raise ValueError`（零是否合法听 TM，默认仅拒负）。
- P3-1 全包 `sys.path.insert(0,…/src)`（`agent_boot/reliability/fault_suite`）。沿 stage1-10 既有模式，不改；仅记一笔。

## 复核（2026-09-11，builder 返工 3 文件后复核，对照 P1-1~P1-5）

- P1-1 CLOSED：`fault_suite.py:670-699` `run_all` 起始无 `boot` 即 `cold_boot` 预持锁，失败走 suite FAIL-fast（`PRE-BOOT`），符合首选改法(a)；`py_compile` 过。
- P1-2 CLOSED：F-R4（`fault_suite.py:297-350`）与 F-N2（`:512-573`）均收敛宣称为 publish 门 `BLOCKED_ARCHIVE_NO_PUBLISH` + 源留 + 零覆盖，断言 pin 精确 `code`（任一 BLOCK 即过已消除），真卫不可达原因记 `converged_claim`；符合改法(a)。附带 F-R1 pin `BLOCKED_SOURCE_CHANGED` 为加严，不扣。
- P1-3 CLOSED：`fault_suite.py:116-135` 新增 `_discover_ready(tries=5, sleep=0.1)`（`source_id None`/`WAITING_FOR_STABLE_FILE` 重试，末次返回供 FAIL），F-R1/R3/R4/R5(×2)/N1/N2/N3（风暴含并发路径）已全切，无单发 `_discover` 直进 gate 残留。
- P1-4 CLOSED：`agent_boot.reboot_equivalent:99-124` 与 `reliability.relaunch:111-129` 均为 shutdown 后显式 `instance.release` 再 `cold_boot` 重获，release 独立 try（shutdown 异常仍释锁），符合改法(a)；跨进程交接仍由 exit-3 用例覆盖已在 docstring 记明。
- P1-5 CLOSED：`reliability.py:132-195` 新增 `kill9_child_relaunch`（子进程 `sleep` 持 job → 父 `os.kill(SIGKILL)` → 验 `-SIGKILL` → `relaunch` + `assert_recovered`/`assert_running`），头注 `27-44` 已逐窗写明钩≈kill 等价主张 + 未覆盖面（页缓存/fd/WAL），符合“至少 job 窗真信号 + 逐窗声明”。
- 复核结论：P1×5 全 CLOSED，可转 QA 重跑（须含无锁直调 `run_all`、`kill9_child_relaunch` 真信号、F-R4/F-N2 code 回归三例）；P2×7 仍记 backlog 不卡关。
