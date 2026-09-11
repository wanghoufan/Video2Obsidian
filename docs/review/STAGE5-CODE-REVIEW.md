
# CODE REVIEW

- Task: 复核 src/stage5/（对照 docs/pm/STAGE5-PLAN.md S5-T01~T06 + 三路只经discover投递/模块内零去重/Ready门fail-closed/Stage6+禁入）
- Commit: n/a（工作区无 git，核对对象为 src/stage5/ 五文件现状：__init__.py / watcher.py / scan.py / reconcile.py / startup.py）
- Reviewer: code-reviewer（opencode-go/glm-5.3-flash）
- Result: 过（无 P0；P1×1 + P2×4 + P3×3 记 backlog，不阻塞 QA；P1 建议 builder 在 QA 前修， mandated 用例均不受影响，改法见各条）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## P0 / P1 Findings

- P1-1 `watcher.py:162-176` `stop()` 不从 `_REGISTRY` 注销，停掉的 Watcher 仍被 `find_ready()` 当 Ready 返回，stop 后隐式 `startup_scan(input_root, ...)`（不传 watcher）仍被放行而非 `WatcherNotReadyError`（本机实测：`STALE-REGISTRY-AFTER-STOP: True` + `SCAN-AFTER-STOP-ALLOWED items=1`）。启动链本身不受影响（`startup.py:174` 传显式 watcher），且 mandated 用例“Ready 前 Scan 被拒 / stop 后不投递”均实测通过，故不定 P0。改法：`stop()` 内加注销（`_REGISTRY_LOCK` 下仅当注册值是 self 才 `pop(self.input_root)`），或 `is_ready()` 改为 `self._ready.is_set() and not self._stopped`（推荐两者都做：前者清注册，后者防野引用）。
- 无 P0。本轮四项硬门逐项通过，证据如下（qa 可复执行，下均为本机实测）：
  - 三路只经 discover 投递：`watcher.deliver` → `_default_deliver`（即 `stage2.candidate.discover`）；`scan.startup_scan` → `deliver(full, ...)`；`reconcile._reconcile_once` → `on_deliver(full, ...)` + `runs.reconcile_source` 收敛；`startup.DeliveryWorkers._loop` → `self._deliver(path, ...)`；`__init__.triple_race_deliver` 三路均为 discover（reconcile 路外加 `reconcile_source`）。`rg "sqlite3|open_db|INSERT|UPDATE|DELETE" src/stage5/` 零命中——Stage5 无自建写路径，一切 DB 效应经 `discover`（内含 `require_lock` + `_retry_locked` + Provisional 原子竞争 + AUTO UPSERT）与 `reconcile_source`。
  - 模块内零去重：`scan.py` 全循环逐个投递、无 seen-set（“同 path 跳过”逻辑零命中）；`reconcile.py` 同语义；`iter_video_files` 每次全量枚举排序返回。`rg -i "dedup|already|processed"` 仅注释声明。唯一抑制是 `watcher` 0.25s 去抖（`_last_seen` 时间窗，非路径级永久去重；重复投递仍合法，At Least Once 不变）与 `<data_root>/data` 跳过（防嵌套布局扫到中央库 side 文件，非去重）——两处均为 PLAN S5-T01 明示允许。
  - Ready 门 fail-closed：无 Ready watcher 调 `startup_scan` 即 `WatcherNotReadyError`（实测 `GATE-OK`）；显式传未 Ready watcher 同样拒绝（`_resolve_watcher:38-45`）；`run_startup` Ready 超时走 `_fail_closed` 停 watcher 后 raise，不留半启动（`startup.py:168-171 + 200-201`）；scan/reconcile 任一单项 error 即整体 raise（`:176-190`）；11 步 order 逐字断言 `order != STARTUP_ORDER → AssertionError`（`:198`），实测 `ORDER-OK: True`；`SecondInstanceError` 在 try 之外直接传播（跨进程实测子进程 `SecondInstanceError: second instance: lock held ...`，不吞）。
  - Stage6+ 禁入：`rg "run_asr_single_file|whisper|publish\.py|conflict\.py|archive|current_path|path.?mirror|Prompt|Vocab|VAD|Chunk|LaunchAgent|Menu.?Bar|threshold|RAG|Embedding|Redis|Docker" src/stage5/` 零命中；import 面仅 `stage2.store/instance/candidate/runs` + `stage5.*` + `watchdog`（`rg import` 全量核对）；实测中央库 `norm=0 render=0 pub=0 arch=0`；`asr_profile_hash` 全链路仅透传+非空校验，无解析无执行；Workers 仅调 discover。
  - 功能冒烟（合成目录，外置 Data Root + Input Root，最大文件 2KB）：`run_startup` → RUNNING；新文件 Watcher 实时投递 `PROMOTED`（`WATCH-DELIVERED: True`）；`.txt` 非视频后缀零投递记录；重复 Scan 收敛；`periodic_reconcile` 零 error；三路真并发 15 outcomes 零 error 且 `sources=1 runs=1`；`stop`/`shutdown` 双调幂等；锁可释放。

## P2 / P3 Backlog Findings

- P2-1 `scan.py:38-45` `_resolve_watcher` 只验 Ready，不验 `watcher.input_root` 与本次 `input_root` 是否同一根：`startup_scan(A, watcher_for_B)` 会被放行。改法：`_resolve_watcher` 内断言 `watcher.input_root == canonical(input_root)`，不等即 `WatcherNotReadyError`。
- P2-2 `startup.py:57` docstring 称 Workers 为 Bounded/有界，实为 `queue.Queue()` 无界（`startup.py:74`）。当前投递量小无溢出风险，故 P2。改法二选一：① docstring 去掉 Bounded/有界表述；② 构造加 `maxsize`（如 1024）并让 `submit` 满时抛错或阻塞（阻塞需注明关停语义）。
- P2-3 `scan.py:79` `assert is_video_path(full)`：`python -O` 下 assert 被剥离，且 `iter_video_files` 已过滤，本行为冗余。改法：删掉该行，或改为显式 `if not ...: raise`（推荐直接删，枚举器是唯一真相源）。
- P2-4 `watcher.py:142/196-199` `_last_seen` 随运行只增不减：常驻 daemon 下是慢泄漏。改法：`_on_fs_event` 写入时顺手清掉早于 `now - 60*DEBOUNCE_S` 的条目（数行即可）。
- P3-1 五文件头均有 `sys.path.insert(0, .../src)` 导入期副作用，与安装包并存时顺序相关。沿 stage1-4 既有模式，不改；仅记一笔：若将来打包，改相对导入并删 hack。
- P3-2 `startup.py:177-180/184-190` scan/reconcile 聚合报错把全量 item `repr` 进异常：大目录下日志巨大。改法：只记前 N 个 + 总数（如 `[:5]` + `total=%d`）。
- P3-3 `__init__.py:95-101` `triple_race_deliver` rounds 串行（每轮 3 并发），满足“3 路 × 多次”下限；若 QA 想加压，可把 rounds 内循环一次全提交（`rounds*3` 并发）或调大 rounds。当前不断言更多，不改也行。

## P1 复核（2026-09-11 builder 修后，code-reviewer 追加，只增不改原文）
- P1-1 CLOSED：watcher.py:159-160 `is_ready()` 改为 `is_set() and not _stopped`，162-170 `stop()` 加 `_REGISTRY_LOCK` 下 `is self` 才 pop 注销，97-103 `find_ready()` 经 `is_ready()` 过滤；实测 stop 后 `is_ready=False`、`find_ready=None`、注册表无残留、双调幂等、无 watcher 的 `startup_scan` 抛 `WatcherNotReadyError`（SCAN_AFTER_STOP_BLOCK_OK），原 STALE-REGISTRY-AFTER-STOP 复现已消除。
