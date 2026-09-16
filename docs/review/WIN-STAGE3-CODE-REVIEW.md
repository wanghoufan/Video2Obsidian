# WIN-STAGE3-CODE-REVIEW｜Windows 迁移 Stage 3（ASR 适配层接线）复核

- 复核人：code-reviewer（独立新鲜眼睛，非橡皮章）
- 日期：2026-09-16
- 范围：`git status` 全部未提交项（9 个 M + 4 个 ??，全部在 `windows/**` 内）
- 结论：**PASS**（附 P1×1、P2×2、P3×3；P1 为「单点迁移未完成项」而非本 diff 引入的回归，不阻塞 Stage 3 收口，但须挂账）

---

## 一、必做核查逐项证据

### 1. 隔离铁律 ✅

实测 `git status --short -- app src tests` 输出为空，`git diff --stat -- app src tests` 为空（仓根 `app/`、`src/`、`tests/` 零改动）。全部改动均限于 `windows/**`。

### 2. numstat 对账 ✅（差 0）

`git diff --numstat` 实测（M 文件 9 个，与派工清单逐项一致）：

| 文件 | +/− | 与清单 |
|---|---|---|
| windows/README.en.md | 5/5 | ✅ |
| windows/README.md | 5/5 | ✅ |
| windows/app/server.py | 20/15 | ✅ |
| windows/app/start.sh | 5/5 | ✅ |
| windows/src/platform_win.py | 68/0 | ✅ |
| windows/src/stage1/asr.py | 61/48 | ✅ |
| windows/src/stage7/prompt_builder.py | 23/8 | ✅ |
| windows/src/stage7/transcribe.py | 15/11 | ✅ |
| windows/src/stage8/transcribe_chunks.py | 26/12 | ✅ |

未跟踪新件：`windows/src/asr_backend/{__init__,manifest}.py`、`windows/tools/freeze_model_manifest.py`、`windows/models/MODEL_MANIFEST.json`（占位）、`windows/tests/selftest_win_stage3.py`。变异测试后已核 `git diff --stat -- windows/src` 恢复为 193/79（与原始一致）。

### 3. AST/逐函数级改动面 ✅

- diff hunk 全部落在清单声明范围内；`stage8/chunk_planner.py`、`merge.py`、`timeline.py` 不在 git status 中（未动）。
- 抽查「逐字未动」关键函数（读码比对 diff hunk 边界）：
  - stage8 `_check_chunks`（transcribe_chunks.py:88-108）、`build_chunk_asr_profile`、`chunk_asr_profile_hash`、`assert_asr_layer_only`：不在任何 hunk 内，未动。
  - stage8 chunk 规划 `plan_chunks` / merge 合并 / timeline 绝对化：整文件未动。
  - server.py 发布门（No-Clobber、`_is_under_root`、发布门复核采样）：diff 仅 4 处 hunk（预检 code、`_asr_engine_available`、`_diag_action` 关键字、`_exec_retranscribe` 文案），发布门逻辑未带歪。
  - `_diag_action` 新关键字 `asr_backend_missing` 与新 code `PRECHECK_ASR_BACKEND_MISSING` 小写后子串匹配成立（server.py:1742 与 :85 对得上）。

### 4. 档位锁与降级红线 ✅（逐条读码证实）

- **fp16 无 A/B 通行证必拦**：asr_backend/__init__.py:248-251，`compute_type != "int8_float16"` 且 `ab_approved=False` → `BLOCKED_COMPUTE_TYPE_NOT_APPROVED`。
- **batch>1 必拦**：:252-255 → `BLOCKED_BATCH_NOT_APPROVED`。
- **GPU 不可用 BLOCK、绝不静默切 CPU**：:258-262，`dev=="cuda"` 且 probe False → `BLOCKED_GPU_UNAVAILABLE`，人话明说「不会自己偷偷降级到 CPU」；只有显式 `explicit_cpu` / `V2O_ASR_FORCE_CPU=1` / `device="cpu"` 才走 cpu/int8（:232-243）。
- **离线门 fail-closed**：`enforce_offline`（:171-192）——显式 0/false/no/off → `BLOCKED_ONLINE_DOWNLOAD_ENABLED`；缺省/垃圾值 → 代码内补 1 并记 `closed_in_code`；显式 1 不动。stage1.transcribe_wav_file 的 `os.environ.setdefault` 不会覆盖用户显式 0，最终由 enforce_offline 拦下，链条闭合。
- **供应链门**：manifest.py `verify_entry`（:178-261）——revision 占位/非 hex、source/license 缺失或 unknown、路径非绝对、文件缺失、SHA-256 不符，逐项 fail-closed；`BANNED_SOURCE_MARKERS=("mlx-community",)`、`BANNED_REVISIONS`（Mac 旧 revision）黑名单在位（:34-35）。

### 5. run_chunks load-once 复用（重点审）✅

- **加载点**：transcribe_chunks.py:369-371，`engine is None`（真实路径）才 `asr_backend.load_model()`，桩路径零加载；加载失败（manifest/离线/GPU）→ AsrBlock 上抛，此时尚未产出任何 per_chunk 数据，无半成品。
- **单 chunk 失败污染**：循环内任何异常（切分失败 / AsrBlock / monotonic 守卫）直接上抛，`per_chunk`、`absolute_lists` 是局部变量，run_chunks 要么完整返回要么整体失败——与改造前（逐 chunk 加载、首个失败同样整体中止）失败语义一致，未引入新污染面。模型跨 chunk 复用不携带转写状态（faster-whisper `transcribe` 每次调用独立）。
- **No-Clobber**：在 server 上游，本 diff 未触碰，语义不变。
- **OOM 中途**：asr_backend:495-496 捕获 OOM → `BLOCKED_GPU_OOM` 上抛 → run 整体中止、无半成品（见 P3-5：模型无显式释放，非回归）。
- **桩路径契约**：engine 桩返回 dict 校验（:384-387）、call_count 对账（:404-405）逐字未动。

### 6. prompt ≤200 token 契约 ✅

prompt_builder.count_tokens（:44-54）→ asr_backend.count_tokens（:563-572），编码入参逐字为 `" " + text.strip()`，与 Mac 端口径一致；预算 200（prompt_builder `PROMPT_BUDGET_TOKENS=200`、stage7 `FROZEN_PROMPT_BUDGET_TOKENS` 校验 >200 即拒）。分词器只认模型自带 `tokenizer.json`（asr_backend:525-552），缺/坏即 BLOCK，不用其他分词器顶替。变异测试 M3 证实口径有测试盯着（见 §7）。

### 7. 自测有牙：独立复跑 3 条变异 ✅（改坏→测红→/tmp 备份还原→测绿）

全部文件级改坏（非运行时 monkeypatch），备份在 /tmp/stage3-review-backup/，还原后 diff numstat 与原始一致：

| # | 变异 | 结果 |
|---|---|---|
| M1 | 删 stage8 `_call_engine_once` 的 monotonic 守卫 raise | 测红：61 断言失败 1（`monotonic=False → ChunkTranscribeError`）→ 还原测绿 |
| M2 | `enforce_offline` 显式 0 不再 BLOCK、静默补 1 | 测红：失败 2（HF_HUB_OFFLINE=0 / TRANSFORMERS_OFFLINE=false 均静默放行）→ 还原测绿 |
| M3 | `count_tokens` 丢 `" "` 前缀（`text.strip()` 直编） | 测红：失败 3（计数失真 + 口径实测 `['你好世界']`）→ 还原测绿 |

### 8. manifest 占位 ✅

MODEL_MANIFEST.json 为占位模板：`source`/`revision`/`local_path` 全为 `REPLACE_WITH_*`，`files: []`；`license: "MIT"` 为字段示例值但 revision 未冻结，verify_entry 必然 BLOCK（自测 [6] 断言 `BLOCKED_MODEL_REVISION_NOT_PINNED` 实测通过）。无编造 revision/哈希/真实路径。freeze 工具对占位值、空目录、相对路径均拒绝生成。

### 9. 隐私/密钥扫描 ✅

全 diff 与新文件 grep `/Users/`、`C:\`、`D:\`、`api[_-]?key`、`secret`、`password`：零命中。人话文案（asr_backend MSG_*、manifest MSG_*）均不含本机路径；绝对路径只进 `detail`（排障字段）。windows/.gitignore 覆盖 `__pycache__/`（pyc 不会入库）。

### 10. 三套自测抽跑 ✅（仓库根 `.venv/bin/python`，windows/ 下）

- `compileall src app tools`：rc=0
- `tests/selftest_win_stage3.py`：断言 61 条失败 0，反向证伪 9/9 有牙，SELFTEST PASS
- `tests/selftest_win_stage12.py`：断言 138 条失败 0，反向证伪 13/13 有牙，PASS

---

## 二、问题清单

### P1-1｜stage8 分块切分未接入 ffmpeg 平台单点（单点迁移未完成）

- **位置**：windows/src/stage8/transcribe_chunks.py:112-132（`_cut_chunk_wav` 直调 `subprocess.run(["ffmpeg", ...])`）
- **影响**：本批在 platform_win.py 新立 ffmpeg 单点（`ffmpeg_resolve`/`run_ffmpeg`，:563-633），stage1.extract_temp_wav 已迁入并在 docstring 声明「FFmpeg 进程一律经 platform_win.run_ffmpeg（平台单点）」（stage1/asr.py:27,145）。stage8 未迁：Windows 交付机若 ffmpeg 不在 PATH、走随包 `third_party/ffmpeg/bin` 或 `V2O_FFMPEG` 时，短音频（stage1）能跑、长音频分块切分必 FileNotFoundError——同一 job 半路断链，且与 stage1 新增的单点契约声明直接矛盾。
- **判定理由**：`_cut_chunk_wav` 本 diff 未触碰，属既有代码，非 Stage 3 引入的回归，故不阻塞 PASS；但 platform_win 单点是本批交付物，「单点」声明与实现不一致属契约级缺口。
- **建议**：Stage 3 内补一行迁移（`cmd` 数组原样传 `platform_win.run_ffmpeg`）成本极低；或在本报告挂账，列为 Stage 4 真机清单首项。

### P2-1｜每个 chunk 重复全模型 SHA-256 校验

- **位置**：transcribe_chunks.py:157（`_call_engine_once` 每 chunk 调 `resolve_model_revision()` → manifest.verify_entry → 逐文件 `_sha256_file`）
- **影响**：load-once 只省了模型加载，没省哈希校验。large-v3-turbo CT2 ~1.6GB，N 个 chunk 就是 N 次全量哈希（几十 GB 级无谓 IO/CPU），真机长音频任务每次都付。
- **建议**：run 级校验一次（run_chunks 开头或随 load_model 一次），chunk 循环内免重验；或 manifest 校验结果按 mtime 缓存。

### P2-2｜模型复用后每 chunk 仍重新 resolve_runtime（含 GPU probe）

- **位置**：transcribe_chunks.py:163-171 传 `model=real_model` 但不传 `config` → asr_backend.transcribe_file（:482）`cfg = config or resolve_runtime(environ=environ)` 每 chunk 重跑
- **影响**：每 chunk 重复 `import ctranslate2 + get_cuda_device_count()`；且理论上存在 load 时档位与后续 chunk 解析结果不一致的窗口（环境变量中途被改），违反「一次 run 一个档位」的直觉。与 P2-1 同源：run 级状态没有真正 run 级化。
- **建议**：run_chunks 在 `load_model()` 时留存 `resolve_runtime()` 结果，循环内 `config=cfg` 透传。

### P3-1｜monotonic 守卫在真实路径恒真（保险带，不可达）

- **位置**：asr_backend/__init__.py:403（normalize_segments 排序后 `is_monotonic` 恒 True）→ stage7/transcribe.py:94-97、transcribe_chunks.py:172-175 的 raise 分支真实路径不可达
- **影响**：无正确性问题；但「守卫」实际由 normalize_segments 的排序 + 倒置 BLOCK 承担，测试经桩注入才有牙。知晓即可，不必改。

### P3-2｜OOM/失败后已加载模型无显式释放、chunk wav 不清理

- **位置**：run_chunks（失败路径）与 asr_backend.transcribe_file 的 OOM 分支
- **影响**：模型对象留待 GC，work_dir 的 chunk wav 留存——均与改造前行为一致，非回归；长驻服务连续 OOM 时显存回收慢一拍。
- **建议**：Stage 4 真机验收时观察；必要时失败路径补 `del real_model` + work_dir 清理。

### P3-3｜README 引用的 requirements.txt 哈希仍为占位（有意保留）

- **位置**：windows/requirements.txt（Stage 1+2 已入库，`--hash=REPLACE_WITH_REAL_DIGEST_*` 注释未启用）
- **影响**：文件头已明示「哈希未回填前请勿启用 --require-hashes」，意图清晰；Stage 3 冻结时须按头部命令回填真值。
- **建议**：随模型冻结（freeze_model_manifest.py）一并回填，别漏。

---

## 三、复核节（实测证据汇总）

- 隔离：`git status --short -- app src tests` 空；`git diff --stat -- app src tests` 空。
- numstat：9 个 M 文件与清单差 0（明细见 §1 表）。
- 变异复跑 3 条：M1/M2/M3 全部「改坏→测红→/tmp 还原→测绿」，备份留存 `/tmp/stage3-review-backup/`，还原后 `git diff --stat -- windows/src` 恢复 193/79。
- 自测：compileall rc=0；selftest_win_stage3.py 61 断言 0 失败、9/9 有牙；selftest_win_stage12.py 138 断言 0 失败、13/13 有牙（`.venv/bin/python`，windows/ 下实跑）。
- 未 commit/push；测试仅用外置 tmp + 合成 wav；未联网；未 bind 8765；业务代码零改动（变异已全部还原）。

**结论：PASS**——隔离铁律、档位锁、降级红线、离线 fail-closed、供应链门、load-once 失败语义、prompt 200 token 契约全部实证成立；P1-1 与 P2-1/P2-2 建议在 Stage 3 报告挂账或顺手补齐后再收口。

---

## 四、返工复核节（2026-09-16，code-reviewer，仅核三项返工）

复核范围：首轮报告 PASS 后 builder 针对 P1-1/P2-1/P2-2 的返工增量；首轮原文（上文一至三节）一字未动。

### R1｜P1-1 ffmpeg 单点迁移 ✅（落点真实）

- `git diff` 证实：transcribe_chunks.py 删本地 `import subprocess`（hunk @@ -11），新增 `import platform_win`（:22）；`_cut_chunk_wav` 参数数组由 `cmd = ["ffmpeg", ...]` 改名 `args` 并改调 `platform_win.run_ffmpeg(args, timeout=600)`（:133），数组内容逐项未动；rc!=0 → `ChunkTranscribeError` + `proc.stderr[-500:]` 语义不变（:134-138）。
- `run_ffmpeg` 实现在 platform_win.py:625-631（`subprocess.run` + `ffmpeg_argv` 数组传参 + UTF-8 + errors=replace），`ffmpeg_resolve` 三档（V2O_FFMPEG 绝对路径 → 随包 `third_party/ffmpeg/bin` → PATH 兜底）在位（:579-610）。
- 全仓 grep `subprocess`：stage8/transcribe_chunks.py 零命中（仅测试变异体文件级自含 import）。

### R2｜P2-1 run 级 manifest 校验一次 ✅（落点真实）

- `run_chunks` 真实路径 run 级 `model_info = resolve_model_revision()`（transcribe_chunks.py:383），循环内 `_call_engine_once(..., model_info=model_info, ...)`（:393）透传留存结果。
- `_call_engine_once` 签名加 `model_info: dict | None = None`（:149），体内 `info = model_info if model_info is not None else resolve_model_revision()`（:162），revision 漂移 raise 语义不变（:163-167）。

### R3｜P2-2 run 级 config 一次、同对象透传 ✅（落点真实）

- `run_chunks` :382 `run_config = asr_backend.resolve_runtime()`，:384 `load_model(run_config)`（档位与模型加载同一份 config，asr_backend.load_model:335-338 签名 `config: dict | None` 契合）；:393 `config=run_config` 透传，`transcribe_file` 签名收 `config`（asr_backend/__init__.py:470）。
- engine 桩路径不解析不加载（:381 `if engine is None` 才进），与首轮 load-once 契约一致。

### R4｜`_call_engine_once` 签名变化调用点全量核对 ✅（重点，无遗漏）

全仓 grep `_call_engine_once`：生产代码仅定义（transcribe_chunks.py:143）与唯一调用点（:391，已更新传 model/model_info/config）两处；其余命中全在 tests/selftest_win_stage3.py（:67 契约表、:608/:625/:645 用位置实参+`model=` 关键字，与新增 kwargs 默认值兼容，实测全绿）。无第三方调用方，无遗漏。

### R5｜改动最小性 ✅（无顺手改动）

- `git diff -- windows/src/stage8/transcribe_chunks.py` 全部 hunk 逐块核对：imports（删 subprocess/加 platform_win）、`_cut_chunk_wav`、`_call_engine_once`、`run_chunks` run 级三行 + 循环调用点，共 5 处 hunk，全部落在三项返工范围内；`_check_chunks`/`build_chunk_asr_profile`/`chunk_asr_profile_hash`/`assert_asr_layer_only` 及 merge/timeline/chunk_planner 不在任何新 hunk 内。
- 其余 8 个 M 文件 numstat 与首轮完全一致（platform_win 68/0、stage1 61/48、server 20/15 等），builder 未再碰；净增量 26/12→46/19（+20/+7）与三项落点规模吻合。

### R6｜numstat 重建法对账 ✅（差 0）

`git diff --numstat` 实测：stage8 46/19 = 首轮 26/12 + 返工 20/7，与 builder 自报一致；9 个 M 文件合计与首轮报告逐项一致；未跟踪 4 项（asr_backend/、tools/、models/、selftest_win_stage3.py）不变。

### R7｜自测实跑 ✅

- `cd windows && ../.venv/bin/python tests/selftest_win_stage3.py`：**断言 70 条失败 0，反向证伪 11/11 有牙，SELFTEST PASS，rc=0**（与自报 61→70、9→11 一致；新增 [11c] run 级校验一次/同对象 config/revision 漂移、[11d] run_ffmpeg 桩观察/timeout=600/参数透传/rc!=0 stderr 语义）。
- `../.venv/bin/python -m compileall -q app src tests`：rc=0。

### R8｜反向证伪自跑 2 条（文件级改坏→测红→/tmp 备份还原→测绿；未用 git checkout）✅

备份 `/tmp/stage3-recheck-backup/transcribe_chunks.py`（先 cp 后改）：

| # | 变异 | 结果 |
|---|---|---|
| F1 | 循环调用点 `config=run_config` 改 `config=None`（回退 P2-2） | 测红：70 断言失败 1（`每 chunk 透传同一 run 级档位 config`）→ /tmp 还原测绿 |
| F2 | `platform_win.run_ffmpeg(args, timeout=600)` 回退直调 `subprocess.run(["ffmpeg"]+args, ...)`（回退 P1-1） | 测红：[11d] `切分经 platform_win.run_ffmpeg 单点且超时 600 不变` FAIL + run_ffmpeg 桩 cut_calls 空 IndexError 崩出（断言盯的正是单点路由）→ /tmp 还原测绿 |

还原后终验：`git diff --numstat` stage8 恢复 46/19；selftest 70/0、11/11 有牙 rc0。

### R9｜隔离铁律 ✅

`git status --short -- app src tests`（仓根）实测为空；改动仍全部限于 `windows/**` 与 `docs/review/**`。未 commit/push；测试仅外置 tmp + 合成 wav；未联网。

**返工复核结论：PASS**——三项返工全部真实、最小、无副作用；测试新增断言有牙（F1/F2 实证）。首轮遗留 P1-1 已关闭，P2-1/P2-2 已关闭；剩余遗留仅首轮 P3-1/P3-2/P3-3（知晓级/Stage 4 挂账项，不阻塞）。无新增遗留问题。
