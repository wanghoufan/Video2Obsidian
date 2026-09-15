# 懒得笔记｜Windows 11 迁移施工计划

- 性质：Phase2 重规划，只出方案
- 目标机：联想 Y9000P／Windows 11／32GB RAM／RTX 3070 Ti 8GB
- 仓库：现有 PUBLIC 仓推送后改名 `wanghoufan/Video2Obsidian-Mac`；从冻结提交复制，新建 PUBLIC `wanghoufan/Video2Obsidian-Windows`；历史互不覆盖。
- 基线：保留 Web/SQLite/stage1–12/Markdown/Obsidian，只替换 ASR 与系统绑定。

## 1. ASR 引擎决策

绑定点：模型 `src/stage1/asr.py:49-58`；调用 `asr.py:178-190`、`stage7/transcribe.py:80-93`、`stage8/transcribe_chunks.py:149-167`；tokenizer `stage7/prompt_builder.py:26-39`。统一替换并保持输出、prompt、时间轴和离线契约。

| 候选 | 8GB 配置、依赖、预期 | 许可／结论 |
|---|---|---|
| **faster-whisper/CTranslate2** | CT2 `large-v3-turbo`；CUDA 12 cuBLAS+cuDNN 9；默认 `cuda/int8_float16/batch=1/worker=1`、10min+2s overlap。上游同为 RTX 3070 Ti 8GB 的 large-v2 非批量数据：fp16 4525MB/63s、int8 2926MB/59s（13min）；仅证明显存可行，**不是本项目 turbo 实测**。本地目录直载 | 均 MIT；**推荐**：Python 接线最短、显存余量大。[官方 README](https://github.com/SYSTRAN/faster-whisper)、[CT2 量化](https://opennmt.net/CTranslate2/quantization.html) |
| whisper.cpp CUDA | `large-v3-turbo` 约1.5GiB或 q5_0约547MiB；需 VS/CMake+CUDA 或固定二进制；CPU/GPU省内存，但 Python、segments/prompt 适配较多 | MIT；**首备**，CT2 DLL长期不稳才切。[官方模型](https://github.com/ggml-org/whisper.cpp/tree/master/models) |
| openai-whisper+Torch | `turbo/cuda/fp16`；官方约6GB VRAM，8GB余量小；官方 PyTorch CUDA wheel，实测 `torch.cuda.is_available()` | Whisper/权重 MIT；权威参照、依赖重，**次备**。[官方表](https://github.com/openai/whisper#available-models-and-languages) |
| CPU | faster-whisper `cpu/int8` 或 whisper.cpp q5_0；32GB可离线但慢 | 故障兜底，不承诺长视频速度 |

推荐只做薄 `asr_backend`、只发布 faster-whisper；fp16/batch>1 须同样本 A/B 通过文本、时间轴、prompt、峰值显存后启用。联网机冻结 CT2 checkpoint/revision（不可沿用 MLX revision），置于本地模型目录或 Release，生成来源/revision/许可/SHA-256 manifest；交付机验哈希并以绝对路径加载，设置 `HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`，禁静默下载。

## 2. 平台差异与处理

| 项目 | 判定与落地办法 |
|---|---|
| watchdog/去抖 | **小改**：复用 `Observer` 和 3s+2s×3 稳定门（`src/stage5/watcher.py:71-90`）；测 create/modify/move 重复、慢写、占用、批量复制。仅实证丢事件才切 `PollingObserver`。 |
| 单实例／文件忙 | **必须改**：`fcntl`（`src/stage2/instance.py:24,79-108`）→标准库 `msvcrt.locking` 非阻塞 1-byte 锁并持句柄，第二实例 exit3且 DB 不变；`watcher.py:368-393` 用 `CreateFileW` 共享模式探测，静默窗仍是主门。失败再提 portalocker。 |
| 卷／原子性 | **必须改**：`src/stage4/volume_probe.py:10-27` 的 `stat -f`/`fcntl` 改 Win 探针；实测 NTFS exclusive-create/replace/hardlink/case、目录 fsync、只读位、打开文件 rename/unlink；No-Clobber 不过即 BLOCK。 |
| 路径 | **小改**：Unicode `str`+`pathlib/os.path`，subprocess 只传数组；比较用 `normcase+commonpath`。测中文、空格、`丨`、emoji、盘符、UNC、大小写碰撞。 |
| >260 | **必须改**：检查长路径策略；未开则 BLOCK，不自动改注册表/UAC。完整链测280+；必要时仅 Win32 边界加 `\\?\`，Explorer/ffmpeg/Obsidian 分别验。[微软说明](https://learn.microsoft.com/windows/win32/fileio/maximum-file-path-limitation) |
| UTF-8/GBK | **小改**：`start.ps1` 进程级 `PYTHONUTF8=1`；文件显式 UTF-8，subprocess `errors="replace"`；测控制台、管道、重定向，不改系统 code page。[Python 文档](https://docs.python.org/3.12/using/windows.html#utf-8-mode) |
| 进程／线程 | **小改**：复用 `ThreadingHTTPServer`/worker；移除 POSIX signal/负 rc 假设（`src/stage11/reliability.py:132-174`），用 `terminate/kill/wait`，不依赖 shell job control。 |
| 端口 | **原样复用**：`127.0.0.1:8899`+`V2O_PORT`（`app/server.py:54-70`）；冲突退出提示换端口，不杀进程、不绑 `0.0.0.0`。 |
| Explorer | **必须改**：`open -R`（`app/server.py:5644-5683`）→参数化 `explorer.exe /select,<file>`；目录直接打开，测逗号/空格/中文。 |
| Obsidian | **小改**：复用 `obsidian://`（`server.py:3042-3065`、`index.html:576`）；相对路径转 `/`，真机验协议/中文/vault，失败可复制路径。 |
| 启动／自启 | **重写**：`start.sh`→主 `start.ps1`+薄 `start.bat`，用 `.venv\Scripts\python.exe`；`launch_plist.py` 改可选启动文件夹/计划任务，MVP不自启。 |
| Python／ffmpeg | **必须改**：官方64-bit Python3.12，`py -3.12 -m venv .venv`，依赖锁版本/哈希；固定 `third_party/ffmpeg/bin/ffmpeg.exe`+许可/哈希并走绝对路径（现命令 `asr.py:111-156`、`transcribe_chunks.py:109-137`）。 |
| 日志／temp | **小改**：正式 data root=`%LOCALAPPDATA%\Video2Obsidian\data`；`tempfile.gettempdir()`只存 chunk；只清带本应用 manifest 的陈旧 tmp。 |
| Defender/UAC | **验证**：用户目录、非管理员运行；被拦只给证据/人工指引，不自动排除。 |

## 3. 文件级复用与量级

| 分类 | 文件／动作 |
|---|---|
| 原样（约20–30文件） | `app/index.html`、presets、`stage3/*`、`stage6/*`、`stage9/*`、stage7 language/profile/vocabulary、stage8 planner/merge/timeline/vad、stage12 status_cli/snapshot；回归后复用。 |
| 小改（约12–20文件、数百行级） | `server.py`；stage1 asr/ingest；stage4 probe/publish；stage5 watcher/startup；stage7 prompt/transcribe；stage8 transcribe_chunks；stage10、README、tests：ASR、路径、卷、reveal、预检。 |
| 重写（约4–8文件、数百行级） | `start.ps1/.bat`、stage2 锁、stage11 launchd及测试、stage12 menu_bar；MVP保留 Web/CLI，暂不做托盘/自启。 |

`src/stage1/ingest.py:77` 还调用 Unix `mount`，stage11 含 launchd/SIGKILL，必须纳入；量级仅估计，Stage0按 Windows 扫描/测试失败校正。

## 4. 五阶段施工

| 阶段 | 目标与验收 | 回滚／风险 |
|---|---|---|
| 0 冻结建仓 | Mac推送改名；从指定 SHA 建 Windows PUBLIC 仓；`git rev-parse HEAD` 对账，`py -3.12 -m compileall app src` 列平台失败，隐私扫描0 | tag `windows-import-base`；脏树/隐私 |
| 1 启动 | venv/锁依赖/ffmpeg/PowerShell/UTF-8/LOCALAPPDATA；启动后 `Invoke-WebRequest http://127.0.0.1:8899/`=200，第二实例exit3，端口冲突不杀进程 | `win-stage1-boot`；DLL/Defender/编码 |
| 2 文件安全 | 锁、watchdog、卷探针、路径、Explorer/Obsidian；外置 tmp 合成夹具验证中文/280+/慢写/移动/重复仅投一次，既有 MD 哈希不变 | `win-stage2-fs`；占用/NTFS/Shell差异 |
| 3 ASR | 单一 adapter、离线 manifest、stage1/7/8/tokenizer、显式CPU兜底；断网跑合成60s+代表中文，segments单调、prompt≤200、merge通过，记录墙钟/VRAM/RAM/CER | `win-stage3-asr`；CUDA DLL/OOM/输出漂移 |
| 4 集成交付 | tmp内“发现→转写→分段→成稿→测试vault”，重启 Lost/Duplicate=0，OOM可显式CPU重试；干净Win用户按README复装 | `win-v1-rc`；UAC/协议/包体/误杀 |

每阶段走 builder→code-reviewer→qa→supervisor；真实视频目录与真实 Obsidian 库零写。

## 5. 风险与坑

- **P0**：Windows 文件占用及 NTFS 原子/硬链接/只读语义不同；No-Clobber、源保留、崩溃恢复决定放行。
- **P0**：驱动/CUDA12/cuDNN9/CT2 wheel 冲突；锁版本矩阵、干净机验，失败诊断但不联网修。
- **P1**：长路径/中文/大小写不敏感在 Python、Explorer、ffmpeg、Obsidian表现不同；必须全链测。
- **P1**：模型/tokenizer漏预置；manifest+断网门禁。8GB OOM则释放GPU并提供**显式**CPU int8，不静默切。
- **P1**：Defender误杀、UAC、模型包大；非管理员、校验和/来源、人工处理，不自动白名单。

## 6. 复用与注意事项速查

- Web/HTTP/SQLite/Markdown/Obsidian及 stage3/6/9：优先原样；MLX ASR/tokenizer/revision：全换 CT2。
- watchdog 可复用但重测；`fcntl`、`mount/stat -f`、launchd、rumps、`open -R`、`.sh` 不可复用。
- ffmpeg 参数可复用、exe 固定随包；8899/V2O_PORT 原样；正式状态进 LOCALAPPDATA，TEMP只放中间物。
- 多正式后端、托盘、自启、安装器均不进 MVP。

## 7. 待用户确认

按推荐暂定：①MVP无托盘/自启；②模型/ffmpeg放 Release 资产而非 Git；③data root 用 `%LOCALAPPDATA%`；④CPU int8 只显式兜底。开工前最终确认。

## 8. Windows 端开工提示词（一键复制）

```text
你是 Video2Obsidian-Windows 的 task-manager。目标：把公开仓库中的「懒得笔记」迁移到 Windows 11（联想 Y9000P、32GB、RTX 3070 Ti 8GB），先交付可用 MVP；严格按仓内 AGENTS.md 与 docs/pm/WINDOWS-MIGRATION-PLAN.md 执行。

已定边界：
- Mac 仓库为公开 `wanghoufan/Video2Obsidian-Mac`；Windows 仓库为独立公开 `wanghoufan/Video2Obsidian-Windows`，不得改写 Mac 仓历史。
- 保留 app/index.html、HTTP/SQLite、stage 流水线、Markdown 与 Obsidian；ASR 只首发 faster-whisper/CTranslate2，不同时维护多个正式后端。
- 默认 GPU 配置：`device="cuda"`、`compute_type="int8_float16"`、`batch_size=1`、单 worker、沿用 10min chunk+2s overlap。fp16/batch 只能在同样本 A/B 和显存证据通过后改。
- MVP 暂不做托盘、自启和安装器；交付 `app/start.ps1`，`start.bat` 只负责转调。

环境准备：
1. Windows 11 更新到稳定版；安装支持 CUDA 12 的 NVIDIA Studio Driver。不要先全局安装多套 CUDA/cuDNN。
2. 安装官方 64-bit Python 3.12、Git。创建环境：`py -3.12 -m venv .venv`，执行 `.\.venv\Scripts\Activate.ps1`。
3. 按锁文件安装固定版 faster-whisper/CTranslate2/watchdog 等；当前上游 GPU 组合为 CUDA 12 cuBLAS + cuDNN 9。把实际 `nvidia-smi`、包版本、`ctranslate2.get_supported_compute_types("cuda")` 落入验收证据。
4. 固定版 `ffmpeg.exe` 放 `third_party\ffmpeg\bin\`，记录来源、许可与 SHA-256，业务代码走绝对路径。
5. 在联网准备阶段把固定 revision 的 Whisper large-v3-turbo CT2 模型完整预置到 `models\whisper-large-v3-turbo-ct2\`，生成 `model-manifest.json`（来源/revision/文件哈希/许可）。运行阶段设置 `HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`，只加载本地绝对路径；断网不得下载。

仓库初始化：
- 从 TM 指定的 Mac 冻结 commit 整包复制，记录源 SHA，新建 Windows 仓；先扫描密钥、真实绝对路径、真实视频/笔记，任何命中先停并报告。
- 保持 `app/`、`src/stage1..stage12/`、`tests/`、`docs/` 结构。Windows 新增文件只放必要位置：`app/start.ps1`、`app/start.bat`、依赖锁、模型 manifest/下载说明、third_party notice。不要为“以后”搭框架。
- 默认正式 data root 为 `%LOCALAPPDATA%\Video2Obsidian\data`，临时 chunk 才用 `%TEMP%`。

按阶段执行，不跨阶段：
Stage 0 冻结/建仓/compileall 平台失败清单；Stage 1 启动、venv、ffmpeg、8899、UTF-8、单实例；Stage 2 Windows 锁/watchdog/卷探针/长路径/No-Clobber/Explorer/Obsidian；Stage 3 faster-whisper adapter 与离线 ASR；Stage 4 全流程、崩溃恢复、干净机安装和交付。每阶段建可回滚 tag，上一阶段未 PASS 不进入下一阶段。

实现要求：
- ASR 适配层统一输出 `text/segments/language`，同时替换 stage1、stage7、stage8 三处 MLX 调用与 prompt_builder 的 MLX tokenizer；保留初始提示词≤200 token、word timestamps 默认 OFF、no_speech_threshold=0.6 和 segments 单调契约。
- `fcntl` 单实例锁优先用标准库 `msvcrt.locking` 保持文件句柄；若真实跨进程测试不满足契约，写证据后再提 `portalocker`，不得直接加依赖。
- watchdog 保留 trailing debounce + 多轮 size/mtime + 发布前复核；Windows 文件占用探测用 Win32 语义。网络盘仍 BLOCK。
- 替换 `mount/stat -f`、LaunchAgent/launchctl、rumps、POSIX SIGKILL 断言、`open -R`、`.sh`；资源管理器定位用参数数组调用 `explorer.exe /select,<path>`。
- 路径内部使用 Unicode str 和 pathlib/os.path；比较用 normcase+commonpath；覆盖中文、空格、`丨`、emoji、盘符、UNC、大小写碰撞和 280+ 字符。
- 继续只监听 127.0.0.1；端口被占用时退出并提示 `V2O_PORT`，严禁杀占用进程或开放 0.0.0.0。

红线：
- 不得写用户真实视频目录、真实 Obsidian 库或 Mac 仓；测试只能使用外置 `%TEMP%\v2o-win-<随机>` 与合成音视频/测试 vault。调 handler 前先断言 data_root 位于该 tmp。
- No-Clobber：已存在笔记一字节都不能覆盖；文件占用、崩溃、OOM、源文件移动时源文件必须保留。
- 不得提交模型、ffmpeg 大文件、密钥、token、`.env`、真实路径/隐私；不得静默联网下载、静默 CPU 降级、自动改注册表、自动加 Defender 排除或要求管理员运行。
- 未获用户明确指令不得 push；commit/分支规则以 Windows 仓 AGENTS.md 为准。

验收与交付：
- 每阶段必须提供可复跑命令、exit code、日志路径和反向失败用例；至少验证第二实例 exit 3 且 DB 不变、端口冲突不杀进程、断网模型加载、60s 合成音频、代表性中文副本、10min 分块合并、280+ 中文路径、慢写/重复事件、文件占用、GPU OOM→显式 CPU 重试、崩溃恢复 Lost/Duplicate=0、现有笔记哈希不变。
- ASR 记录墙钟、峰值 VRAM、RAM、CER/关键术语命中；上游 benchmark 只能当参考，不得冒充本机数据。
- 最终在干净 Windows 用户账户从 README 复装，`Invoke-WebRequest http://127.0.0.1:8899/` 返回 200，并用合成数据完成发现→转写→分段→成稿→测试 vault 入库。
- 交付清单：源 SHA、依赖锁、模型 manifest、third-party notices、安装/启动/排错文档、所有 review/QA 证据、已知限制、回滚方式。

角色流程：每个阶段按 builder→code-reviewer→qa→supervisor；返工回原 session，supervisor 同一 Task 打回 2 次才升级 senior-expert。Runtime 自检不能替代独立 reviewer/QA/supervisor。task-manager 是唯一对用户说话的人。

现在只执行当前最早未完成阶段；先读 AGENTS.md、角色卡、USER_MODEL_OVERRIDE.md、HANDOFF、经验一句话，再读本计划和 git 状态。遇到需要改管理员策略、扩大真实数据权限、改变 ASR 主后端或仓库策略时停下找用户拍板。
```

---

## 收尾注记（neat-freak，2026-09-15 P1 收官本轮；只加注，未删原文、未改任何结论）

- 核对基准：冻结后工作树 = `5f06fdb`（HEAD，`tag v1.0-mac`）。本计划**只出方案不施工**，本轮无代码改动。
- **一致（逐项实跑核过原文引用，全部命中、文件均存在）**：§1 `src/stage1/asr.py:49-58`（`FROZEN_*` 单点，`:49-50` 为 `mlx-community/whisper-large-v3-turbo` rev `a4aaeec0…f6fb`）与 `:178-190`（`mlx_whisper.transcribe` 调用）、`stage7/transcribe.py:80-93`、`stage8/transcribe_chunks.py:149-167`、`stage7/prompt_builder.py:26-39`；§2 `stage5/watcher.py:71-90`（3s+2s×3 稳定门，常量实际在 `:84-87`）、`stage2/instance.py:24`＋`:79-108`、`stage4/volume_probe.py:10-27`、`stage11/reliability.py:132-174`、`server.py:5644-5683`（`open -R`）、`server.py:3042-3065`＋`index.html:576`（`obsidian://`）、`asr.py:111-156`／`transcribe_chunks.py:109-137`（ffmpeg 现命令）；§3 `src/stage1/ingest.py:77`（Unix `mount`）。
- **差异 1（端口行号，差 2 行）**：§2「端口｜原样复用：`127.0.0.1:8899`+`V2O_PORT`（`app/server.py:54-70`）」→ 端口真源块实际为 **`app/server.py:54-68`**（`:68` 为 `del _env_port`；`:70` 已是 `DEFAULT_DATA_ROOT`），与 `HANDOFF.md:50/:87` 记的 `:54-68` 一致。结论（默认 8899＋`V2O_PORT` 覆盖）不受影响。
- **差异 2（文件名）**：§3 原样复用清单写「stage12 **status_cli/snapshot**」→ `src/stage12/` 实际文件为 `__init__.py`、`menu_bar.py`、`status_cli.py`、**`status_snapshot.py`**（**无 `snapshot.py`**）。
- **时效说明（非差异）**：`src/stage5/watcher.py` 的稳定门口径为本轮 `P1-1-FIX` 定稿值（静默 3.0s／采样 2.0s×3 轮／最小年龄 7.0s／独占占用检测，见 `watcher.py:84-87` 与 `README.md:110/:116` 已知限制）；§1 引用的 8GB 上游 benchmark 与本仓 MLX revision 为当时取证数字，Windows 端须按 §1 重冻结 CT2 checkpoint/revision，不得沿用本仓 revision。
- **未决**：§7 四条待用户确认项（无托盘自启／模型与 ffmpeg 放 Release／`%LOCALAPPDATA%` data root／CPU int8 只显式兜底）**仍未拍板**；Windows 端尚未建仓、未施工。
