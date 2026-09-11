# QA-REPORT｜PACKAGING-V2验收（三路径/去引号/browse/主题/端到端vault+RENDER_ONLY/无mlx400+PRECHECK）

- QA：qa（opencode-go/glm-5.3-flash，本窗口 subagent；未改业务代码，只写本报告）
- 被测：`app/server.py`（662行，V2OConsole/1.1）+ `app/index.html`（313行，16595B）+ `app/start.sh`（40行）（PACKAGING-V2；`src/` 只读复用）
- 任务目标：验收P0-1~6（三路径/去引号对照/browse/主题字符串/端到端vault出md+空vault RENDER_ONLY/无mlx时400/PRECHECK）；合成小视频+stub；只用外置测试目录，用户真实ob库只读浏览不写；坏例看exit码
- QA 执行目录（仓库外）：`/tmp/v2o-pkgv2-data`（168K：vault分支库）+ `/tmp/v2o-pkgv2-data-empty`（168K：空vault分支库）+ `/tmp/v2o-pkgv2-input`（32K：合成视频+file.txt+subA/subB）+ `/tmp/v2o-pkgv2-vault`（4K：vault出md）+ `/tmp/v2o-pkgv2-runners`（24K：validate_http/neg/e2e_stub/server.log/pid）；仓库内零写盘除本报告
- 合成小视频：`ffmpeg -f lavfi testsrc=320x240:rate=10:duration=2 + sine=440Hz:duration=2 → /tmp/v2o-pkgv2-input/clip_small.mp4`（29K，ffprobe duration 2.0s，FF_EXIT=0/PROBE_EXIT=0）
- stub：`server._transcribe_audio` 猴补丁返回固定中文文本+1 segment+engine_calls=1，全程不碰 `mlx_whisper`/ffmpeg转写；`extract_temp_wav` 未被调用
- **结论：PASS（P0-1~6全PASS；直接调用12项+live HTTP 13/13 exit 0+主题19串+零外部+E2E双分支PUBLISHED/RENDER_ONLY+坏例exit 1双证；py_compile/sh-n exit 0；src零改以mtime 06:25-34早于QA 07:51代证；真实库只读browse零写；结论只落本报告）**

## 1. 用例简表（坏例只看 exit 码）

| 用例 | 动作 | 期望 | 实测 | exit 码 |
|---|---|---|---|---|
| P0-2 去引号单元 | `normalize_path` 12例（单/双引号+空格/空/None/非str/孤引号） | 全对 | 12/12 PASS | 直接调用 EXIT=**0** |
| P0-2 status对照 | `_handle_status` 明文 vs `'...'` vs `"..."` | 三者 `DB_MISSING` 一致 | 一致（code 200 ok:false） | EXIT=**0** |
| P0-2 browse对照 | `_handle_browse` 明文 vs `'...'` | 同 path/dirs | 同 `/private/tmp/v2o-pkgv2-input` dirs `[subA,subB]` | EXIT=**0** |
| P0-2 start对照 | `_handle_start_post` 明文/单/双引号 input | 同 `PRECHECK_MLX_MISSING` | 同 400+code | EXIT=**0** |
| P0-3 browse空→home | `GET /api/browse?path=` | 200 home+dirs | 200 `/Users/zzymima0000` 107 dirs | live validator PASS |
| P0-3 browse input | `GET /api/browse?path=/tmp/v2o-pkgv2-input` | 200 `[subA,subB]` 排序只列目录 | 一致，排序真，file.txt被排除 | live PASS |
| P0-3 browse坏例 | 相对/不存在/文件路径 | 各 400 | 400+对应文案（须绝对/不存在/不存在） | live PASS（HTTP 400） |
| P0-1 三路径校验 | POST 空/相对/不存在 input；相对 data_root；相对/不存在 vault | 各 400 对应文案 | 全命中（请填写/须绝对/目录不存在） | 直接调用 EXIT=**0** |
| P0-1 三路径快照 | `GET /api/start` | 含 running/data_root/input_root/ob_vault_root/worker | 全含 + `started_at` 加法字段 | live PASS |
| P0-4 主题字符串 | index.html 19串（3 placeholder+3浏览+data-theme/浅色/深色/btnTheme/v2o-theme/冻结/磁带/开始监听/刷新/setInterval/三fetch/modal/选定） | 全含 | 19/19 PASS | 审计 EXIT=**0** |
| P0-4 零外部 | 逐行扫 `https?://\|<script src\|<link\|@import\|src="http\|href="http` | 0 行 | 0 行；`grep -c http` 空 rc=1 | EXT_EXIT=**0** |
| P0-5 vault端到端 | stub转写 `_process_one_run(data,vault)` | PUBLISHED + vault md | PUBLISHED `/private/tmp/v2o-pkgv2-vault/clip_small.md` 96B（title clip_small+转写文本），manifest末receipt PUBLISHED whisper_calls=1 | E2E_EXIT=**0** |
| P0-5 空vault | `_process_one_run(data,None)` | RENDER_ONLY + rendered md | RENDER_ONLY（verdict含RENDER_ONLY+PENDING_PUBLISH），`render/rendrev_*.md` 96B存在，manifest末RENDER_ONLY | E2E_EXIT=**0** |
| P0-5 坏例 | 源缺失 run / vanished run_id | FAIL“源文件不存在”/SKIP“run vanished” | 一致（stub未被调用） | BAD_E2E_EXIT=**0** |
| P0-6 无mlx400 | POST 合法三路径（mlx缺） | 400 `PRECHECK_MLX_MISSING` | 400+code一致（含vault/无vault/引号三路径） | 直接+live PASS |
| P0-6 PRECHECK | `_mlx_available()` + start.sh venv优先+mlx探针 | False + 三cand+探针文案 | False；start.sh:8三cand，:20探针，:13/:23双WARN（400提示换venv） | SHN_EXIT=**0** |
| live原子汇总 | `/tmp/v2o-pkgv2-runners/validate_http.py` 13断言 | 全PASS则exit 0 | TOTAL 13/13 FAILS=[] | **VALIDATE_EXIT=0** |
| 坏例负控 | `neg_http.py` 故意期望202 | 应FAIL且exit 1 | FAIL code=400 | **NEG_EXIT=1** |
| 编译 | `py_compile server.py` + `sh -n start.sh` | exit 0 | 均为 0 | **PY_COMPILE_EXIT=0/SHN_EXIT=0** |
| 进口审计 | AST imports | 仅stdlib+stage*，无pip第三方 | stdlib+json/os/sys/tempfile/threading/urllib/http/datetime + stage1/2/3/4/5/6/7/8/12（stage7/8系src只读复用非pip） | 审计 PASS |
| server日志对账 | `/tmp/v2o-pkgv2-runners/server.log` | 码与上表一一对应 | 200×N/400×N全对齐（含引号对照两行） | 日志 PASS |

Runner：urllib直调HTTPError取code断言（不看打印）+ 直接函数对照 + stub E2E + 双审计（主题串/外部资源）+ 双编译 + 日志对账；server起于 `python3 app/server.py`（127.0.0.1:8765，无venv python3.9.6，mlx缺），测后已停，端口已释。

## BUGS（照 BUGS.template.md；本轮无 P0/P1）

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| 无（V2侧） | — | 否 | P0-1~6全码一致；负控exit 1 | CLOSED | 无需builder修 | validate 13/13 + E2E双分支 + 日志三证 |
| OBS-1（观察） | P3 | 否 | `_process_one_run` 不改 `processing_runs.status`（仍QUEUED），同run重跑会重复转写；worker靠内存 `_worker_done` 去重 | CLOSED | 无需修（V2内存去重语义） | 重跑非幂等，报告备查 |
| OBS-2（观察） | P3 | 否 | dirty库上 `instance.startup` 会 `assert_stage3_tables_empty` 炸（E2E后Norm/Render各1行）；坏例改用 `acquire` 绕过 | CLOSED | 无需修（Stage2门语义） | 坏例以acquire代证，见E2E log |

## Fix Attempt Fingerprint

- Task ID: PACKAGING-V2验收（首轮QA，业务零修）
- Root Cause Hypothesis: 不适用（P0-1~6全PASS；`__pycache__` mtime刷新为import产物，`.py` mtime app 07:45-48/src 06:25-34均早于QA 07:51，源零改成立）
- Approach: 外置四目录+ffmpeg合成2s小视频+urllib原子13断言只看HTTP_CODE/exit+错期望负控证exit1+normalize 12例+三重去引号对照+主题19串+零外部+双编译+AST进口+stub双分支E2E（vault PUBLISHED/空RENDER_ONLY）+坏源FAIL/vanished SKIP+默认库mtime代证+HOME只读browse+日志对账
- Files Changed: 仅新增本报告 `docs/qa/PACKAGING-V2-QA-REPORT.md`；`src/`+`app/`零改；测试写盘只在 `/tmp/v2o-pkgv2-*`（data×2 168K+input 32K+vault 4K+runners 24K，交neat-freak收尾）
- Verification: VALIDATE_EXIT=0（13/13）+ NEG_EXIT=1 + E2E_EXIT=0 + BAD_E2E_EXIT=0 + THEME 19/19 + EXT 0行 + PY_COMPILE/SHN 0 + 日志码对齐
- Failure Reason: 无FAIL项（V2侧）
- Difference From Previous Attempt: 首轮，无上一轮（PACKAGING-V1报告另存，不混）

## 未闭环清单（交 supervisor/product-reviewer 定，不卡本 PASS）

- U-1 真实转写未测（mlx缺，PRECHECK挡202；E2E以stub代证链路，whisper冻结模型语义延续V1.8已知限制；需stage0bench venv+长视频一次，用户定时间）。
- U-2 真实库零碰以“只用 /tmp/v2o-pkgv2-* + HOME只读browse（107 dirs列出无写）+ vault写仅/tmp/v2o-pkgv2-vault + 仓库内零写盘除本报告”代证；无真实库快照（按禁令不得写）。
- U-3 默认库 `/var/.../T/v2o-console-data` 在QA前已存在（07:24早于QA 07:51，内data/ 6项），本轮未用默认（validator全显式data_root），mtime可证非本轮写。
- U-4 `__pycache__` mtime可能因import刷新（`.py` mtime未动，源零改成立；pyc为构建产物）。
- U-5 非git仓库，`git diff`口径N/A；以app/src mtime早于QA+本轮零写代证（同PACKAGING-V1 U-5 Pattern）。
- U-6 残留待清：`/tmp/v2o-pkgv2-data*`（336K）+ input/vault/runners + server.log/pid，交neat-freak收尾；8765已释无常驻。
- U-7 P0口径假设：P0-6=无mlx400+PRECHECK合并一项（任务斜杠7项按6收口）；`started_at`加法字段与P2-3竞态延续V1评审，不卡。

---
目标：PACKAGING-V2验收｜剩 P0：无（QA 口径 PASS；闭环判定以 supervisor 复检为准）｜下一步：交 product-reviewer 验＋supervisor 复检（HANDOFF 只记状态，不代写结论）。
