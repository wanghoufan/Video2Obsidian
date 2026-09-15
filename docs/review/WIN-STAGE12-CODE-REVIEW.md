
# CODE REVIEW｜windows/ 子目录 Stage 1 启动链 + Stage 2 文件安全

- Task: Windows 平台适配第一批（Stage 1 启动链 + Stage 2 文件安全）代码复核
- Commit: 未提交（工作树）；基线 main HEAD `21cacf9`（Mac 端，tag `v1.0-mac`）
- Reviewer: code-reviewer（只复核，未改任何代码）
- Result: **过（PASS）** —— P0 × 0、P1 × 0、P2 × 2、P3 × 6；P2/P3 均不阻断本批进入 QA，但 P2-1 必须在 Stage 2 判 PASS 前接线。

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

---

## 0. 口径核对（先核对再评）

### 0.1 隔离铁律：越界即 P0 —— **未越界**

`git status --short` 全量：

```
 M windows/app/server.py
 M windows/src/stage1/ingest.py
 M windows/src/stage11/launch_plist.py
 M windows/src/stage11/reliability.py
 M windows/src/stage12/menu_bar.py
 M windows/src/stage2/instance.py
 M windows/src/stage4/volume_probe.py
 M windows/src/stage5/watcher.py
?? .codebuddy/                      ← 工具目录，非业务，非本次改动
?? windows/requirements.txt
?? windows/src/platform_win.py
?? windows/start.bat
?? windows/start.ps1
?? windows/tests/selftest_win_stage12.py
```

**仓根 `app/`、`src/`、`tests/` 零改动** ✅。Mac 端三套自测（`tests/selftest_*.py`）未被引用、未被修改 ✅（新自测 `windows/tests/selftest_win_stage12.py:32-39` 只 self-insert `windows/src`，不 import `tests.*`）。

### 0.2 numstat 与 builder 自报逐项对

| 文件 | numstat（增/删） | 自报 | 结论 |
|---|---|---|---|
| `windows/app/server.py` | 29 / 10 | 29/10 | ✅ |
| `windows/src/stage1/ingest.py` | 65 / 5 | 65/5 | ✅ |
| `windows/src/stage11/launch_plist.py` | 35 / 0 | 35/0 | ✅ |
| `windows/src/stage11/reliability.py` | 17 / 25 | 17/25 | ✅ |
| `windows/src/stage12/menu_bar.py` | 29 / 5 | 29/5 | ✅ |
| `windows/src/stage2/instance.py` | 14 / 5 | 14/5 | ✅ |
| `windows/src/stage4/volume_probe.py` | 32 / 10 | 32/10 | ✅ |
| `windows/src/stage5/watcher.py` | 14 / 15 | 14/15 | ✅ |

新增文件行数实测：`src/platform_win.py` 572、`start.ps1` 59、`start.bat` 6、`requirements.txt` 25、`tests/selftest_win_stage12.py` 806 —— 与自报**完全一致** ✅。

`python3 -m compileall windows/src windows/app` 通过 ✅。builder 自测 `python3 tests/selftest_win_stage12.py` → 断言 111、失败 0、rc=0 ✅（复跑一致）。

---

## 1. 独立复算（自建夹具，不复用 builder 断言）

夹具：`/tmp/cr_win_stage12/indep.py` + `fakes.py`（假 msvcrt 锁状态落盘、假 `ctypes.windll.kernel32`、桩 `sys.platform`）。全部只用 `/tmp` 合成数据，未碰用户真实目录，未 bind/kill 任何端口。

**独立断言 54 条，通过 53，失败 1（见 P2-2）。**

| 组 | 项 | 结果 |
|---|---|---|
| [A] 锁 | 假 msvcrt 下第一实例拿锁、句柄 `fh.closed is False`（真持句柄）、**跨进程真子进程第二实例 exit 3**、DB 指纹未变、release 后可再取 | 7/7 ✅ |
| [B] 长路径 | 258→ALLOW、259→ALLOW、260→BLOCK、261→BLOCK、300→BLOCK；`limit=259`；policy=True→`ALLOW_EXTENDED`；BLOCK 带码 `BLOCKED_PATH_TOO_LONG_FOR_WINDOWS` | 8/8 ✅ |
| [B] 红线 | `platform_win.py` 源码无 `SetValueEx/CreateKey/DeleteKey/SetValue`；`start.ps1` 无 `-Verb RunAs`／`New-ItemProperty`／`Set-ItemProperty` | 2/2 ✅ |
| [C] 路径比较 | 大小写、不同盘符、斜杠归一、UNC 大小写、中文+空格、UNC vs 本地盘；`is_within` 子路径/前缀陷阱(`vault` vs `vaultx`)/自身；`to_extended_path` 本地盘与 UNC | 10/11（UNC 共享根见 P2-2） |
| [D] reveal | `explorer.exe /select,<p>` 数组构造；含逗号→降级 `open-folder`；含双引号→降级；降级 argv 不含逗号；argv 是 list（不经 shell）；macOS 仍 `open -R` 不回归 | 6/6 ✅ |
| [E] data root | `LOCALAPPDATA` 桩 → `…\Video2Obsidian\data`；缺失/空白 → `DataRootUnavailable` 且人话含「不会」；macOS 口径不变 | 3/3 ✅ |
| [F] 卷探针 | NTFS 判定、`drive_root="C:\"`、dt=3→local、dt=4→remote、UNC→remote(`\\srv\share`)、`CreateFileW` 正常句柄→未占用、返回 `-1`→占用、能力缺失→`PlatformCapabilityMissing`（不静默） | 10/10 ✅ |
| [G] 变异 | 6 条见 §2 | 6/6 有牙 |

**优雅跳过项实跑（桩 `sys.platform="win32"`）**：
- `stage11/launch_plist.py`：`LAUNCHD_SUPPORTED=False`；`build_plist`／`write_plist`／`validate_plist`／`load_test_plist`／`unload_test_plist` 五入口全部返回 `{"skipped": True, "reason": "Windows 11 没有 launchd / LaunchAgents…"}` 且带人话 CLI 指引，不抛异常、不调 `launchctl` ✅
- `stage12/menu_bar.py`：`IS_WINDOWS=True`、`rumps` **确实未被 import**（`'rumps' in sys.modules == False`）、`main()` 打印人话 + 替代 CLI 后 `rc=0` ✅

**重点风险逐条结论**：

| 风险项 | 结论 | 证据 |
|---|---|---|
| 平台分支是否收在单点 | ✅ 收在单点。`windows/src/**`、`windows/app/**` 中 `sys.platform` / `os.name` / `platform.system` 命中数 **0**（排除 `platform_win.py` 自身） | grep 全量零命中 |
| msvcrt 锁是否真持句柄 | ✅ 真持。`instance.py:103` `_FDS[key] = fh` 全程登记，实测 `fh.closed is False`；仅 `release()`（`instance.py:107-117`）才 close | `windows/src/stage2/instance.py:103` |
| 长路径是否绝不改注册表/UAC | ✅ 只读。`platform_win.py:142-161` 只 `OpenKey/QueryValueEx`，`except → None`（读不到视作未开→BLOCK）；无写 API；`start.ps1` 无提权 | `platform_win.py:154-157`、`:18-19` |
| `start.ps1` 端口单点 | ✅ 脚本内单点：`$Port` 只出现一次（`:14`），`$Url` 由 `$Port` 派生（`:15`），端口占用只报 PID 不杀进程（`:39-45`），未开 `0.0.0.0` | `windows/start.ps1:14-15,:39-45` |
| 脱敏红线 | ✅ 新代码未引入裸绝对路径输出。错误面统一走 `_err_text`→`_strip_paths`（`server.py:411-421`）、`_diag_redact_path`（`server.py:1529-1534`）；reveal 失败分支 `_err_text(err or real)` 继承自 Mac 既有口径，路径会被 strip | `windows/app/server.py:411`、`1529` |
| `requirements.txt` 移除 `mlx-whisper` | ✅ 生效行无 `mlx`（仅第 9 行注释说明「已移除」）；三个包全部 `==` 锁死；哈希占位字段已留（注释行 `--hash=sha256:REPLACE_WITH_REAL_DIGEST_*`） | `windows/requirements.txt:18-25` |
| watcher 稳定门未被改动 | ✅ AST 对账：`DEBOUNCE_S=3.0 / STABLE_PROBE_S=2.0 / STABLE_ROUNDS=3 / BUSY_CHECK=True`，Windows 与 Mac **逐项相等**（P1-1-FIX 成果未动） | `windows/src/stage5/watcher.py:87-90` vs `src/stage5/watcher.py` |

---

## 2. 反向证伪抽查（变异 → 断言必须变红）

**自查 6 条（独立夹具 §[G]），6/6 有牙**：

| # | 变异 | 改前 → 改后 | 有牙 |
|---|---|---|---|
| ① | `platform_win.lock_first_byte` 置为空函数 | 第二实例 BLOCKED → **ALLOWED** | 有牙 |
| ② | `USABLE_PATH_LIMIT` 259 → 4096 | 300 字符 BLOCK → **ALLOW** | 有牙 |
| ③ | `default_data_root` 改成静默回落固定目录 | RAISE → **NO_RAISE** | 有牙 |
| ④ | `build_reveal_argv` 去掉逗号/引号降级 | `open-folder` → **select** | 有牙 |
| ⑤ | `_win_drive_root` 把 UNC 强行解析成 `C:\` | `remote` → **local** | 有牙 |
| ⑥ | 占用探测能力缺失时静默返回 False | 抛 `PlatformCapabilityMissing` →（变异态）**不抛** | 有牙 |

**抽查 builder 自报 9 条中的 4 条**（`tests/selftest_win_stage12.py:62-75` 的 `teeth()` 口径为「mutate → probe 必须 False → restore」，是真变异不是空转）：

| # | builder 变异 | 判定 |
|---|---|---|
| 1 | 单实例锁恒成功后第二实例不再 exit 3（`:400-406`） | 有牙 ✅ |
| 2 | `USABLE_PATH_LIMIT` 放大后 261 不再 BLOCK（`:350-355`） | 有牙 ✅ |
| 3 | data root 改成静默回落后不再报错（`:494-509`） | 有牙 ✅ |
| 4 | reveal 去掉逗号/引号降级后不再 open-folder（`:447-462`） | 有牙 ✅ |

→ **抽查 4/4 有牙；加自查 6/6，合计 10/10 有牙。**
（口径提示：`teeth()` 未在 restore 后复跑 probe 验证「已还原」，建议后续补一步；不影响本次判定。）

---

## 3. P0 / P1 Findings

- **无。** 隔离铁律未越界、锁真持句柄、长路径不碰注册表/UAC、watcher 稳定门未动 —— 四条「改了即 P0/P1」的红线全部守住了。

---

## 4. P2 / P3 Backlog Findings

### P2-1｜长路径 / 路径比较能力零业务调用点（Stage 2 DoD 未闭环）

- 证据：`check_path_length`（`platform_win.py:164`）、`long_paths_enabled`（`:142`）、`is_within`（`:113`）、`same_path`（`:109`）、`to_extended_path`（`:126`）在 `windows/src/**` 与 `windows/app/**` 中**除 `platform_win.py` 自身与自测外无任何调用点**（全仓 grep 仅命中 `platform_win.py` 定义处 + `tests/selftest_win_stage12.py`）。唯一接进业务的只有 `volume_info` / `file_is_busy` / `lock_first_byte` / `default_data_root` / `build_reveal_argv` / `kill_child`。
- 影响：`docs/pm/WINDOWS-MIGRATION-PLAN.md:122` 要求「至少验证 … 280+ 中文路径」，但当前**没有任何代码路径会 BLOCK 超长路径** —— Windows 上 280+ 路径不会被干净拦下，只会在后续 `open()` 时抛裸 `OSError`，与人话 BLOCK 的契约不符。
- 改法（给 builder，非本批必须）：在写入/入库前的入口（Stage1 ingest 与 Stage4 publish 的「最贵那步之前」）接一次 `check_path_length`，BLOCK 时把 `message + guidance` 原样给人；`is_within` 接到 vault 包含性判定上。**Stage 2 判 PASS 之前必须接线。**

### P2-2｜`is_within` 对 UNC 共享根判 False（语义错，方向 fail-closed）

- 证据：`platform_win.py:113-123`。实测 `is_within("\\\\srv\\share", "\\\\srv\\share\\a")` 返回 **False**（应为 True）。
- 根因：`ntpath.commonpath(["\\\\srv\\share", "\\\\srv\\share\\a"])` 在 **Python 3.9.6 与 3.12 均抛 `ValueError: Can't mix absolute and relative paths`**（父路径恰为共享根时 `ntpath` 不认它是 absolute），被 `platform_win.py:122` 的 `except (ValueError, OSError): return False` 吞掉。
- 影响：当前**无业务调用**（P2-1），且错的方向是「判不在内」＝fail-closed，不会造成越权放行；但一旦按 P2-1 接到包含性判定上，UNC vault 根会被误 BLOCK。
- 改法：`is_within` 里对 UNC 共享根单独判（父 normcase 等于子的 `\\server\share` 前缀即 True），或 `commonpath` 前先做 `p.rstrip("\\") + sep` 的 commonprefix 兜底；并补一条「父 = UNC 共享根」的正向断言（builder 现有用例 `:276` 用的是 `\\srv\share\v`，恰好避开了这个边界）。

### P3-1｜`start.ps1` 与 `server.py` 各持一份 8899 字面量

- 证据：`windows/start.ps1:14`（`"8899"`）与 `windows/app/server.py:58`（`PORT = 8899`）。
- 说明：`start.ps1` **内部**已收敛为单点（`$Port` 一处、`$Url` 派生），与 Mac 端 `windows/app/start.sh:8`（`${V2O_PORT:-8899}`）同构，属既有被接受的口径，故只记 P3。风险是日后改 `server.py` 默认值时 `start.ps1` 打印的 URL 会漂移。
- 建议：`start.ps1` 加一条一致性断言（读 `server.py` 的 `PORT =` 行比对），或注释里写明「两处必须同步」。

### P3-2｜`watcher.py` 遗留无用的 `os.open`/`os.close`

- 证据：`windows/src/stage5/watcher.py:379-385` —— 原来给 `fcntl.flock` 准备的 fd 现在无人使用（占用判定已改走 `platform_win.file_is_busy`，内部自己再开一次），这段 open/close 是纯冗余 syscall。
- 影响：无功能影响（语义等价），但读代码的人会以为失败分支有意义。建议随下一次 watcher 改动清掉。

### P3-3｜`LAUNCHD_SUPPORTED` / `IS_WINDOWS` 是 import 期快照

- 证据：`windows/src/stage11/launch_plist.py:47`、`windows/src/stage12/menu_bar.py:34`。
- 说明：两个常量在 import 时就固化，monkeypatch `sys.platform` 无法在 import 之后翻转（必须 `importlib.reload`）。对交付到 Windows 真机**无影响**（真机 import 时就是 win32），但后续写桩测试是个坑。建议在模块 docstring 里写一句「改平台需 reload」。

### P3-4｜`requirements.txt` 哈希占位尚未回填 + wheel 可得性未验

- 证据：`windows/requirements.txt:19,22,25` 的 `--hash=` 全是**注释行**（形如 `# --hash=sha256:REPLACE_WITH_REAL_DIGEST_*`）。
- 说明：符合「留字段、Stage 3 冻结时回填」的意图（文件第 11-16 行已写明流程与「未回填前勿启用 `--require-hashes`」的警告）。**真机必验项**：`faster-whisper==1.1.0` / `ctranslate2==4.5.0` / `watchdog==6.0.0` 的 cp312 win-amd64 wheel 实际可得性，本仓（macOS）无法验证，不得推断为通过。

### P3-5｜`windows/app/start.sh`（Mac 启动脚本副本）仍留在 `windows/` 目录

- 证据：`windows/app/start.sh:2,7,8` 仍是 macOS 文案与 `${V2O_PORT:-8899}`；仓库内同时存在 `windows/start.ps1` + `windows/start.bat`。
- 说明：整目录拷贝到 Windows 端时会把这个 Mac 脚本一起带过去，容易误导。建议删除或改名标注「Mac 端，Windows 勿用」。

### P3-6｜`_probe_volume_windows` 不校验文件系统类型（观察项，需产品拍板）

- 证据：`windows/src/stage1/ingest.py:101-146` —— 只要 `GetDriveTypeW` 返回 FIXED(3)/RAMDISK(6) 就判 `local` 并 ALLOW，不看 `filesystem_type` 是否为 NTFS。
- 说明：方案 §2「卷」行只要求网络盘 BLOCK，故不违反本批契约；但 exFAT/FAT32 本地盘（U 盘/移动硬盘）在硬链接、原子 rename、大小写语义上与 NTFS 不同，`stage4` 的 `supports_hardlink` / `supports_exclusive_create` 是实测 fail-closed 的，暂不会误放行。**是否要把非 NTFS 本地盘也 BLOCK，属产品口径，不是本批缺陷**，建议列入 Windows 端待拍板清单。

---

## 5. 复核边界声明（本轮未做 / 做不到）

- 本机 macOS，**Windows 真实行为不可实测**：`msvcrt.locking` 跨进程互斥、`CreateFileW` 共享模式语义、`GetVolumeInformationW` 返回、Explorer `/select,`、PowerShell 实跑、长路径策略注册表读值 —— 全部为**桩测结论**，按 `HANDOFF.md:108` 一律列入 Windows 真机待验清单，**不得推断为通过**。
- 本轮未改任何代码（含 `windows/` 内），未 commit、未 push；测试只用 `/tmp` 外置目录 + 合成数据；未触碰用户真实目录；未 bind / 未 kill 8765。

## 6. 建议的收口顺序

1. QA 可基于当前版本开测（P0/P1 为 0）。
2. P2-1 在 Stage 2 判 PASS 前接线（长路径 BLOCK 落到 ingest / publish 入口）。
3. P2-2 与 P2-1 同批改（接线前改，避免带到真机）。
4. P3-1～P3-6 收尾或挂账，逐条处置不留空。
