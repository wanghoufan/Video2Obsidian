# WIN-STAGE3 独立 QA 报告

- 日期：2026-09-16
- 对象：当前仓库 `windows/**` 全部未提交改动
- QA：独立夹具验证；未复用 builder/reviewer 断言作为结论依据

## QA 结论

**FAIL（环境限制导致回归套件未全部可验证；Stage 3 业务夹具本身 PASS）**。

Stage 3 独立夹具 16/16 通过，覆盖档位锁、GPU 不降级、CPU 显式门、离线门、manifest 三态、时间轴、单文件双向调用、run 级复用、FFmpeg 单点和 token 口径。未发现新的 Stage 3 代码缺陷。

但 `selftest_p1_2_contract.py` 在本沙箱尝试绑定 `127.0.0.1:0` 时因 `PermissionError: [Errno 1] Operation not permitted` 退出 rc=1。任务书要求不得把该环境限制推断为通过，因此总 QA 结论不能写 PASS；须在允许 loopback bind 的环境补跑。

## BUGS

| BUG-ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注 |
|---|---|---|---|---|---|---|
| WIN-STAGE3-QA-001 | P3 | No | 真实路径中 `normalize_segments` 排序后 `is_monotonic` 守卫恒真；桩注入可验证守卫 | OPEN / 挂账 | Stage 4 | 无当前正确性回归；保留保险带可接受 |
| WIN-STAGE3-QA-002 | P3 | No | OOM/失败路径未显式释放已加载模型，chunk wav 也未统一清理 | OPEN / 挂账 | Stage 4 | 与改造前行为一致；真机观察显存回收和临时文件残留 |
| WIN-STAGE3-QA-003 | P3 | No | `windows/requirements.txt` 哈希仍为 `REPLACE_WITH_REAL_DIGEST_*` 占位 | OPEN / 挂账 | Stage 3 模型冻结 | 文件头已明确禁止启用 `--require-hashes`；冻结模型时补齐 |
| WIN-STAGE3-QA-004 | P0 | NOT VERIFIED | `selftest_p1_2_contract.py` 绑定 `127.0.0.1:0` | BLOCKED（环境） | QA 环境 | 沙箱禁止 loopback bind，非代码失败；需可绑定环境复验 |

## 独立复现

夹具位于系统临时目录，使用合成 WAV、假 manifest 和桩引擎，执行后清理。结果：**16 通过，0 失败**。

覆盖要点：

- `fp16` / `batch>1` 无证阻断，有证放行；GPU probe=False 返回 `BLOCKED_GPU_UNAVAILABLE`，文案不含本机路径。
- `explicit_cpu`、`V2O_ASR_FORCE_CPU=1`、`device="cpu"` 均为 `cpu/int8`；CPU 非 int8 阻断。
- 离线显式 0 阻断；缺省补 1 并报告 `closed_in_code`。
- manifest 缺失、占位未冻结阻断；完整冻结清单按绝对路径通过。
- 乱序片段排序；`end < start` 阻断。
- 缺失音频不调用引擎；正常桩恰好一次调用，文本按片段直接拼接。
- 两 chunk 桩路径恰好两次调用；真实路径桩验证 `resolve_runtime`、manifest revision、`load_model` 各一次，两个 chunk 复用同一 config/model 对象。
- `_cut_chunk_wav` 只经 `platform_win.run_ffmpeg`，观察到 timeout=600、参数数组透传、非零 rc 转为 `ChunkTranscribeError`。
- tokenizer 口径为 `" " + text.strip()`；纯空白计数为 0；availability 预检不加载模型。

## 反向证伪

均先 `cp` 备份至 `/tmp/win_stage3_qa_backup/`，恢复使用 `/tmp` 备份，未使用 `git checkout`。

| 变异 | 改坏内容 | 测红 | 恢复复验 |
|---|---|---|---|
| M1 | GPU 不可用阻断条件改为不可达 | rc=1，断言“必须 `BLOCKED_GPU_UNAVAILABLE`”失败 | PASS |
| M2 | 离线 falsy 阻断条件改为不可达 | rc=1，断言“显式 0 必须阻断”失败 | PASS |
| M3 | token 计数去掉前导空格 | rc=1，计数断言失败 | PASS |

## 回归表

均在 `windows/` 下使用仓根 `../.venv/bin/python`。

| 命令 | rc | 结果 |
|---|---:|---|
| `../.venv/bin/python -m compileall -q app src tests` | 0 | PASS |
| `../.venv/bin/python tests/selftest_win_stage3.py` | 0 | PASS；70 断言、0 失败、11/11 反向证伪 |
| `../.venv/bin/python tests/selftest_win_stage12.py` | 0 | PASS；138 断言、0 失败、13/13 反向证伪 |
| `../.venv/bin/python tests/selftest_v26_presets.py` | 0 | PASS |
| `../.venv/bin/python tests/selftest_p1_2_frontend.py` | 0 | PASS |
| `../.venv/bin/python tests/selftest_p1_2_contract.py` | 1 | BLOCKED；loopback bind 被沙箱拒绝 |

## Reviewer 遗留项表态

- P2-2「模型复用后每 chunk 重复 resolve_runtime」：**同意已关闭**。返工代码在 `run_chunks` 保存 `run_config`，独立真实路径夹具观察到 resolve 一次，两个 chunk 收到同一 config 对象。
- P3-1「monotonic 守卫真实路径恒真」：**同意挂账**。排序和倒置时间阻断仍提供底层契约，守卫作为保险带保留；不构成当前阻塞。
- P3-2「OOM/失败后模型与 chunk wav 未显式释放/清理」：**同意挂账**。属既有失败语义，未发现 Stage 3 新增回归；Stage 4 真机观察。
- P3-3「requirements 哈希占位」：**同意挂账**。当前文件已 fail-safe 禁止启用 `--require-hashes`，模型/依赖冻结时必须补真值。

## 隔离与环境限制

- `git status --short` 全量：改动仅见 `windows/**`、`docs/review/**` 及本报告目标；无测试夹具落仓。
- `git status --short -- app src tests`：空。
- 变异恢复后 `git diff --numstat`：`windows/src/stage8/transcribe_chunks.py` 为 `46/19`，未留下变异差异。
- 本机为 macOS，无 CUDA，未安装 faster-whisper/CTranslate2；真实 Windows GPU/CT2/模型加载链未验证，需 Stage 4 真机验收。
- 未联网、未访问真实目录/Obsidian 库、未绑定 8765；contract 自测的临时 loopback bind 被沙箱策略拒绝。

---

## supervisor 复检节（2026-09-16，supervisor，收口前最后一环）

复检方式：全部自跑实测，非采信下游自报；本轮零代码改动，变异文件均先 `cp` 备份至 `/tmp/sup-stage3-recheck-backup/`（含 SHA-1 记录），还原后 shasum 与原始一致，未用 `git checkout`。上文 qa 原文一字未动。

### S1｜三套自测 + contract 独立复跑（仓根 `.venv/bin/python`，windows/ 下）

| 命令 | rc | 实测 |
|---|---:|---|
| `-m compileall -q app src tests` | 0 | PASS |
| `tests/selftest_win_stage3.py` | 0 | 70 断言 0 失败，反向证伪 11/11 有牙，SELFTEST PASS |
| `tests/selftest_win_stage12.py` | 0 | 138 断言 0 失败，反向证伪 13/13 有牙，PASS |
| `tests/selftest_p1_2_contract.py` | 0 | **600 项断言 ALL PASS**——独立复核 TM 补位结论成立，QA-004 环境阻塞已闭环 |

### S2｜隔离铁律 ✅

- `git status --short`：9 个 M 全在 `windows/**`；未跟踪为 `windows/{models,tools,src/asr_backend}/`、`windows/tests/selftest_win_stage3.py`、`docs/{qa,review}/WIN-STAGE3-*.md`，与 reviewer 报告清单一致。
- `git status --short -- app src tests`（仓根）：**空**。
- `git diff --numstat` 实测与 reviewer 报告逐项一致：README.en 5/5、README 5/5、server 20/15、start.sh 5/5、platform_win 68/0、stage1 61/48、prompt_builder 23/8、stage7 15/11、stage8 **46/19**（=首轮 26/12 + 返工 20/7，净增量吻合）；windows/src 合计 213/86=首轮 193/79 + 返工 20/7。未跟踪 4 项不变。

### S3｜独立夹具抽查 ✅（35 断言，两遍 rc=0 结果一致；脚本 `/tmp/sup_stage3_fixtures.py`，断言均为自建、不复用 reviewer/qa 设计）

- FX-A GPU 红线：`BLOCKED_GPU_UNAVAILABLE` message+detail 无 POSIX/盘符路径样式；detail 档位与请求一致（cuda/int8_float16 不被偷换）；probe 抛异常上抛不吞。
- FX-B 离线门：16 个 falsy 变体（`0/false/FALSE/False/no/OFF/" off "/\t0\n` × 2 键）全 BLOCK 且消息点名变量；缺省 `closed_in_code` 恰两键。
- FX-C run 级状态：3 chunks → manifest 校验恰 1 次、load_model 恰 1 次、引擎恰 3 次；每 chunk 收到**同一 config 对象**与同一 model 对象（id 级断言）。
- FX-D ffmpeg 单点：恰 1 次 `run_ffmpeg`、timeout 恰 600、数组 17 项（首 `-hide_banner` 末输出路径）、`-ac 1 / -ar 16000` 在位、无 shell 元字符、rc!=0 错误带 stderr 尾巴。

### S4｜反向证伪 2 条（文件级改坏→测红→/tmp 还原→测绿）✅

| # | 变异 | 测红证据 | 还原终验 |
|---|---|---|---|
| V1 | `resolve_runtime` GPU 不可用分支改为静默降级 CPU（破坏红线） | stage3 自测 68 断言失败 1：「GPU 不可用 → BLOCK（不降级）」 | shasum `c30b82ba` 一致；70/0 复绿 |
| V2 | run_chunks 循环 `model_info=model_info` 改 `None`（回退每 chunk 重解析，破坏 P2-1 返工） | stage3 自测失败 1：「run 级 manifest 校验恰好一次（实测 3 次）」 | shasum `770f1ac8` 一致；numstat stage8 复原 46/19；70/0 复绿；夹具复跑 35/0 |

### S5｜P1-1/P2-1/P2-2 关闭读码复核 ✅

- P1-1：`transcribe_chunks.py:133` 实调 `platform_win.run_ffmpeg(args, timeout=600)`；`import platform_win` 已加、本地 subprocess 已删；`_check_chunks`/`build_chunk_asr_profile` 等不在任何 hunk 内。
- P2-1：`transcribe_chunks.py:383` run 级 `model_info = resolve_model_revision()`，`:393` 透传；`_call_engine_once:162` 仅 `model_info is None` 才现场解析。
- P2-2：`transcribe_chunks.py:382` run 级 `run_config = asr_backend.resolve_runtime()`、`:384` `load_model(run_config)`（档位与加载同一份 config）、`:393` `config=run_config` 透传。

### S6｜qa BUG 表逐条核对 ✅

- QA-001/002/003（P3 挂账）：与 reviewer P3-1/P3-2/P3-3 一一同源，「无当前回归、挂账 Stage 4 / 模型冻结」定级合理，同意挂账。
- QA-004（P0/NOT VERIFIED）：确属 codex 沙箱禁 loopback bind 的**环境限制**而非代码失败——本窗口 TM 补位 + 本复检独立复跑均 600/600 rc=0，阻塞已闭环，定级与处置恰当。

### S7｜账本与红线 ✅

- `docs/model/TASK-MODEL-LOG.jsonl`（59 行）与 `docs/model/DISPATCH-LOG.jsonl`（101 行）一次性 python 逐行 `json.loads` 校验：**坏行 0**。Stage 3 链账本行未落盘（按流程 TM 放行后统一落），不算缺失。
- 全 diff + 新文件扫描 `api[_-]?key|secret|password|/Users/|C:\\|D:\\`：零命中；asr_backend/tools 无 requests/urllib/httpx/socket 等联网调用；`MODEL_MANIFEST.json` 确认全占位（`REPLACE_WITH_*`、`files: []`），无编造 revision/哈希/真实路径。

### 复检结论

**放行**（打回 0/2 口径）：隔离铁律、numstat 对账、三套自测、contract 600、独立夹具 35 断言两遍一致、证伪 2/2 有牙、三项返工落点真实、qa 定级恰当、账本合法、红线零命中——全部实测成立。遗留仅 P3 挂账 3 项 + Stage 4 真机清单（真实 GPU/CT2/模型加载链），均已在案，不阻塞 Stage 3 收口。
