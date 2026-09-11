
# CODE REVIEW

- Task: 复核src/stage10/（对照STAGE10-PLAN + §26强验/G3/A/B/C语义/Overwrite=0/Mis-delete=0/Stage11+禁入）
- Commit: n/a（工作区无 git，核对对象为 src/stage10/ 七文件现状：__init__.py / verify_archive.py / level_a.py / level_b.py / level_c.py / gate.py / commit.py）
- Reviewer: code-reviewer（opencode-go/glm-5.3-flash）
- Result: 打回（P0 全过；P1×1 必修见下，builder 修完 + QA 重跑 A-cross 路径即可关；P2×5 + P3×4 记 backlog；本复核独立静态 + 外置合成实测，改法见各条）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## P0 / P1 Findings

- P0 全过。本轮硬门逐项通过，证据如下（本机独立实测于 /tmp/s10cr + /tmp/s10cr2，外置合成、最大文件 1024B；`python3 -m py_compile src/stage10/*.py` 通过）：
  - P0-1 §26 强验（S10-T01）：`verify_archive.py:110-223` 无条件重算 SHA256（`_sha256_file_hex:62-65` 复用 `stage1.ingest.sha256_file`，无 size/mtime 快捷）+ 前后 fstat 对比（`_fstat_capture:68-71` 复用 stage1，前 138-186 不可读/中途消失三路全进 `BLOCKED_SOURCE_CHANGED`，187-223 仅当 `current_hash==content_identity 且前后 fstat 零漂移` 才 PASS）。本机篡改夹具（首字节改写后恢复 mtime_ns，size/mtime 双同）必 `BLOCK/BLOCKED_SOURCE_CHANGED/hash_recomputed=True`，复原后回 PASS。
  - P0-2 Level A（S10-T02，§56）：`level_a.py:188-223` 目标 `lexists` 预检 + `makedirs` 后复检双 BLOCK（199-220）→ 同盘 `link(2)` 提交 + 删源（133-143，EEXIST 即 `BLOCKED_ARCHIVE_EXISTS`，92-106）→ 跨盘目的端 tmp + 拷贝 + hash 验 + `link` 提交 + 双删（146-185，提交点恒为 no-cover link，Final 路径无 O_EXCL 预留，与 B 机制分离）。本机同盘成功（源消失、Final 哈希==原 hash、`ARCHIVE_COMMITTED`）+ 目标已存在 BLOCK（源留、目标字节 intact、cover 0）。真双盘跨 FS 本机无二卷可证，代码走读成立，QA U-6 同盘模拟声明延续（记 P2-5）。
  - P0-3 Level B（S10-T03，§57/Case 10）：`level_b.py:248-331` 全序=预 Strong Verify → O_EXCL 独占建 Final → sidecar PREPARED 落盘 fsync → copy → fsync → SHA256 → Receipt 落盘 → 源复验 → 删源（210-245，复验不等即拒删源）；`recover_midcopy:346-433` 无归属 sidecar 即 `ArchiveRefused`（未知 Final 永不动）/ 缺失 Final 即 INCOMPLETE 可重入 / 完整即 Repair Forward（Stage1 Truth Model，零转写）/ 半截即截断重拷；存在≠完成（无 Receipt 不成功）。本机 Reservation 成功 + kill 注入（`on_chunk` 中断）后源留、PREPARED 在、经 recover Repair Forward 得 `ARCHIVE_COMMITTED`。
  - P0-4 Level C + Conflict/Overwrite=0 + G3（S10-T04，§58/§3.12/§3.13/G3）：`level_c.py:69-79` 恒抛 `BLOCKED_UNSUPPORTED_ARCHIVE_FILESYSTEM`，结构上零写删（仅源读 hash 作 intact 证明，43-66）；`gate.py:148-193` 装配 verify → G3 publish 重确认 → 用户编辑优先 → 目标预检（`lexists` 即 BLOCK，cover 恒 0）→ A/B/C 分流（194-226），前后缀双 guard（archive 外 `ARCHIVE_PATH_ESCAPE`、input 外拒收）；`verify_archive.py:317-378` G3 双腿：runs→norms→renders→PUBLISHED 链无行即 `BLOCKED_ARCHIVE_NO_PUBLISH`，诱饵缺失/被改即对应 BLOCK（覆盖计数恒 0，模块零写）。本机四例全中：C BLOCK 源 intact、无 Publish BLOCK、诱饵 append 一字节 BLOCK 且用户字节保留、跨 root escape FAIL。
  - P0-5 Source 四列更新（§59/§7/Case 7）：`commit.py:99-214` 全 Stage 唯一写点：持单实例锁 → level 限 A/B → Receipt 状态/路径/hash 三验 → Final 磁盘复算 → 确定性 commit_id + 幂等（同 source+final 直接回）→ `BEGIN IMMEDIATE` 内 `INSERT archive_commits` 一行 + `UPDATE sources` 恰四列 → 列级 diff 断言（非四列任一即回滚，186-189 非白名单/非恰四列双拒）→ `resolve_current_path:78-96` 双算（DB 值==磁盘真实路径 + isfile + hash 一致）。`_SOURCES_COLS:39-45` 十五列与 `stage2.store` DDL 逐列对齐（已核 `store.py:134-150`），`archive_commits` 六列与 DDL（`store.py:222-229`）对齐；G3 链四表列名与 DDL 全对齐（`store.py:151-221`）。本机 happy：恰四列 `current_path/location/status/archived_at`（`ARCHIVE/ARCHIVED`）、`current_path==磁盘真实 Final`、Case 7 `exists+hash_match`。
  - P0-6 STOP EXPANSION 门：`rg "run_asr_single_file|launchagent|menu|golden|cer|openai|anthropic|requests\.|llm|summar|polish|paraphras|rewrite|force|overwrite|clobber" src/stage10/` 零命中（`repair_forward` 含 `forw` 不含 `force`，已逐字确认；文档用 No-Cover 避词）；`rg "sqlite3|INSERT|UPDATE|DELETE"` 命中仅 `commit.py`（`sqlite3` import + `_read_archive_row` SELECT + `INSERT INTO archive_commits` + `UPDATE sources SET current_path…` 四列 + SELECT 只读，其余六文件 SELECT 只读或零命中）；`run_asr_single_file` 七文件零命中（`whisper` 仅 `whisper_calls: 0` 证据字段）；`rg -i "launchagent|menu.?bar|golden|faultsuite|fault_injection"` 零命中；文件名七个无 Stage11+ 关键词；import 面仅 `stage1.ingest(sha/fstat 只读)` + `stage2.store(锁/时间戳)` + `stage4.volume_probe(只读)` + `stage10.*`（stage3/5/6/7/8/9 零 import 零调用）；`os.rename` 零使用（commit 点为 `link(2)`，Stage4 先例等价）；`src/stage1-9/` diff 门：工作区无 git，静态替代——stage10 内无任何写盘路径指向 `src/stage1-9/`（写操作仅 Final/sidecar/archive_root 下 + input 源删，`rg unlink/remove/open` 已全量核对），文件级 diff 留 QA 在有基线环境补断言。
  - P0-7 外置合成门：属 QA 执行域；代码侧无真实目录/真实库/云调用路径（写删目标全由调用方传入 root 决定 + 双 guard 拒收前缀外；网络/音频/转写 import 零）。
- P1-1 `level_a.py:146-185` 跨盘路径删源前缺源复验（§3.13，BLOCK + 源保留）：`_move_cross_device` 入口算 `source_hash` → 拷 tmp → 验 tmp → `link` 提交 → 验 Final → `os.unlink(source_abs):182`，中间未重读源。若源在拷贝窗口内被外部改写（单实例锁管不住外部写者），将归档旧字节却删掉新字节。同模块同盘路径有提交后 Final hash 校验兜底，`level_b._finish_after_valid_final:234-239` 有删源前源复验（不等即拒删），A-cross 独缺，属同保证内部分叉。改法（5 行）：182 行前加 `fresh="sha256:"+_sha256_file_hex(source_abs); if fresh!=source_hash: try: os.unlink(tmp_abs) except OSError: pass; raise ArchiveError("source changed during copy … source kept")`（tmp 已提交为 Final 时同盘理：保留 Final 现场、源保留，交 `BLOCKED_ARCHIVE_EXISTS` 语义由 gate 目标预检收口；单加源复验不断现有 QA 单线程用例）+ QA 补一例（hook 在 tmp fsync 后改源一字节，期望拒删源、源新字节在）。

## P2 / P3 Backlog Findings

- P2-1 `level_a.py:188-190` `expected_hash=None` 时跳 §26（独立调用可绕强验；gate 常传 `content_identity` 故 happy 无碍，Stage11 LaunchAgent 直接调即敞口）。改法：改为必填（`expected_hash: str` 去默认，或 None 即 `ArchiveError` 拒动），与 `level_b:262-263`（无 `sha256:` 即拒）对齐。
- P2-2 sidecar/Receipt 平写竞态：`level_b.py:305-317/109-112/210-214` 三处 `_write_json_fsync` 用普通 `open(path,"wb")` 截断同 Final 配套的 `.archive_prepared.json/.archive_receipt.json`。双进程同 Final 交错时后写者盖先写者归属（Final 本体有 O_EXCL 守住不丢字节，但归属可能错乱）。改法：sidecar 首写改 O_EXCL 建（EEXIST 即重读比对归属，非归属即 BLOCK），或文档注明“归档并发以单实例 + 同 Final 串行为前提”，QA 加一例双源同 Final（一 BLOCK 一 PASS + 源双留其一）。
- P2-3 G3 多 publish 语义：`verify_archive.py:338-354` 任一 PUBLISHED 行 canonical 未改即 PASS（其余行被改不拦）。单 publish QA 无碍；多 canonical 源（同源多 render 发布到多路径）下“用户改过其中一个”是否应拦归档，基线未明。改法：不改代码，TM/supervisor 拍板（严：任一已编辑即 BLOCK；宽：保持现状）并记 HANDOFF，qa 加一例双 publish 一改一未改。
- P2-4 同盘 A 残留 Final：`level_a.py:133-143` link 后 Final hash 不等（仅磁盘错乱可达）即 raise 但不清理刚建的 Final，后续重入恒 `BLOCKED_ARCHIVE_EXISTS` 需人工清。fail-closed 无丢字节，仅运维性。改法：raise 前 `try: os.unlink(final_abs) except OSError: pass`（仅当本调用建的 link；EEXIST-BLOCK 路径不动）。
- P2-5 跨 FS 真二卷举证缺：本机单卷，`_move_cross_device` 仅走读 + QA U-6 同盘模拟。改法：保持现状，supervisor 在有双卷环境补一例真跨盘（不同 `st_dev`）成功 + 目标存在 BLOCK。
- P3-1 `gate.py:53/79` probe 为“只读”却 `os.makedirs(dest_dir, exist_ok=True)` 建目录（文档 47 行称无字节暂存不确切）。改法：文档改“除目的父目录建链外无字节暂存”，或 probe 改纯 `os.stat` 不建目录（建目录留给 level）。
- P3-2 `gate.py:255-269` `_fail` 以子串（outside/escap/unknown）映射 code，脆但仅守卫路径。改法：调用点直传 code，不改亦可。
- P3-3 `level_b.py:436-438` `fresh_commit_id()` 无调用者（默认走确定性 `archive_commit_id_for`，与 commit 侧确定性 id 一致，正确）。改法：删之或标 test-only。
- P3-4 七文件 `sys.path.insert(0,…/src)`（含 `__init__.py` 重导出）。沿 stage1-10 既有模式，不改；仅记一笔。

## 复核（2026-09-11）
- P1-1 CLOSED：`level_a.py:182-192` 已在删源前加源复验（`fresh_source` 重算比对 `source_hash`，不等即清 tmp 抛 `ArchiveError(source changed during copy … source kept)` 拒删源，`os.unlink(source_abs):192` 仅复验通过后执行），与本报告 P1-1 改法逐字一致、与 `level_b._finish_after_valid_final:234-239` 同语义同异常类型；`py_compile` 通过，复验顺序正确（fresh_check 在删源前）。残留 `tmp` 重复 unlink 为无害冗余，记 polish 不阻塞。
