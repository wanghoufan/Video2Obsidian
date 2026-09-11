# QA-REPORT｜PACKAGING-V2.3验收（runs含filename/未知兜底/未注册vault布尔+ob_url null+人话/已注册保持链接/新映射单.md旧不动）

- QA：qa（opencode-go/glm-5.3-flash，本窗口 subagent；未改业务代码，只写本报告）
- 被测：`app/server.py`（2215行，93617B，11:15）+ `app/index.html`（951行，47779B，11:16）+ `app/start.sh`（40行，1376B，07:45）（PACKAGING-V2.3增量；`src/` 只读复用）
- 任务目标：验收V2.3三项（runs含filename/未知文件兜底、未注册vault布尔+ob_url null+人话、已注册保持链接、新映射单.md、旧md不动；合成+stub；外置目录；用户真实目录与ob库禁碰；坏例看exit码）
- QA 执行目录（仓库外）：`/tmp/v2o-pkgv23-data`（140K：P0-1种子库，clipA/B双源）+ `/tmp/v2o-pkgv23-input`（128K：clipA 29835B/clipB 30111B/`09.demo.part.mp4`/subdir/nested.mp4）+ `/tmp/v2o-pkgv23-vault-unreg`（8K：无.obsidian，clipB.md）+ `/tmp/v2o-pkgv23-vault-reg`（12K：有.obsidian/app.json，clipA.md+old_keep.md）+ `/tmp/v2o-pkgv23-data-e2e`（168K：stub端到端vault库）+ `/tmp/v2o-pkgv23-data-e2e-empty`（168K：stub空vault库）+ `/tmp/v2o-pkgv23-input-e2e`（64K：clipE 29916B+clipA_copy）+ `/tmp/v2o-pkgv23-vault-e2e`（12K：old_keep.md+09.demo.part.md+clipE.md新产出）+ `/tmp/v2o-pkgv23-runners`（32K：v23_verify/v23_e2e/v23_neg/v23_live）+ `/tmp/v2o-pkgv23-vault-unreg-fileprobe`（.obsidian为文件反例）；仓库内零写盘除本报告
- 合成小视频：`ffmpeg testsrc=320x240:rate=10:duration=2+sine=440Hz → clipA.mp4`（29835B）+ `rate=12+sine=880Hz → clipB.mp4`（30111B）+ `660Hz → clipE.mp4`（29916B），ffprobe各2.0s，FF_A_EXIT=0/FF_B_EXIT=0/FF_E_EXIT=0/PROBE_A/B/E_EXIT=0；`09.demo.part.mp4`由clipA复制得（HASHCP_EXIT=0），专供多点号单扩展名用例；subdir/nested.mp4供子目录保持用例
- stub：`server._transcribe_audio` 猴补丁返回固定中文“合成小视频转写正文V2.3”+1 segment+engine_calls=1（E2E用），P0-1/P0-2/映射项直接调函数不碰 `mlx_whisper`/`extract_temp_wav` 真转写；另以抛错stub证FAIL带文件名分支
- 端口隔离：8765被常驻实例占用（PID 54274，初末一致），本轮未kill/未POST/未碰其data/input/vault；live HTTP改走8767独立进程（`ThreadingHTTPServer(127.0.0.1,8767)`+`server.Handler`），测后已shutdown，8767已释（lsof空）；对8765零请求、零写
- **结论：PASS（三项全绿：P0-1 runs/details/FAIL verdict/toast全含filename、缺失回未知文件；P0-2未注册vault_registered False+ob_url null+先在OB人话、已注册True+链接保持、未配库保持原人话；P0-3新产出单.md无.mp4.md、子目录保持、旧md sha双零改；verify 54/54 exit 0+E2E 16/16 exit 0+live 8/8 exit 0+前端13/13+NEG exit 1+双编译0；零外部；src零改以mtime 05:43-06:34早于QA 11:32代证；真实目录/ob库零用；结论只落本报告）**

## 1. 用例简表（坏例只看 exit 码）

| 用例 | 动作 | 期望 | 实测 | exit 码 |
|---|---|---|---|---|
| P0-2注册判定9例 | `_is_vault_registered(None/""/blank/不存在/unreg/reg/.obsidian文件/非str/文件路径)` | F/F/F/F/F/T/F/F/F | 全一致（reg True系`.obsidian`为目录，文件版False） | VERIFY_EXIT=**0**（54/54） |
| P0-3简单映射 | `_app_resolve_canonical(INA,V_REG,clipA.mp4)` | `clipA.md`非`.mp4.md` | `/tmp/.../clipA.md`，expected `clipA.md` | 同上 |
| P0-3多点号 | 同上 `09.demo.part.mp4` | `09.demo.part.md`单 | 一致，无`.mp4.md` | 同上 |
| P0-3子目录 | 同上 `subdir/nested.mp4` | 含subdir+`nested.md` | `/tmp/.../subdir/nested.md` | 同上 |
| P0-3无双后缀 | m1/m2/m3查`.mp4.md` | 0命中且`.md`结尾 | 全0命中 | 同上 |
| P0-3预览 | `_preview_mapping(INA,V_REG)/(INA,None)` | `示例视频.mp4→库内示例视频.md式样`/空 | 一致/空串 | 同上 |
| P0-1种子双源 | `seed(DATA,INA,clipA/B)`经`instance.startup+upsert+get_or_create_auto_run` | 双run_id不同 | `run_23002f…/run_59679d…` | 同上 |
| P0-1映射 | `_run_source_path_map(DATA)` | A→clipA.mp4/B→clipB.mp4 | 一致 | 同上 |
| P0-1附名三例 | `_attach_source_filenames({A,B,missing})` | clipA/clipB/未知文件 | 一致 | 同上 |
| P0-1无库兜底 | `_attach(...,/tmp/...no-db)` | 未知文件 | 一致 | 同上 |
| P0-1 status | `_handle_status({DATA,INA,limit20})` | 200全含filename | 200 n=2全`clipA/B.mp4` | 同上 |
| P0-1 details | `_listener_snapshot`（mem A+未知） | A=clipA/未知=未知文件 | 一致；vault_registered bool False | 同上 |
| P0-1 vanished | `_process_one_run(run_vanished)` | SKIP | SKIP `run vanished` | 同上 |
| P0-1缺文件 | 移走clipA后`_process_one_run(runA)` | FAIL+clipA.mp4+人话无裸run_id | FAIL `源视频文件找不到了：clipA.mp4→…` | 同上 |
| P0-1抛错 | stub raise后`_process_one_run` | FAIL+clipA.mp4 | FAIL一致 | 同上 |
| P0-2 note未注册 | `_handle_note(run_unreg1,V_UNREG)` | 200+False+null+先在OB+finder保留 | 全一致 | 同上 |
| P0-2 note已注册 | `_handle_note(run_reg1,V_REG)` | 200+True+obsidian://+reason null | `obsidian://open?vault=v2o-pkgv23-vault-reg&file=clipA.md` | 同上 |
| P0-2 note未配 | vault None | False+未配置/先在OB人话 | 一致 | 同上 |
| P0-2 note无md | `run_no_such` | text null+stage_text排队 | `排队等待处理：监听中会自动开始` | 同上 |
| P0-2 note缺参 | 无run_id | 400 | 400 | 同上 |
| P0-3 E2E vault | stub `_process_one_run(DATA_E2E,IN_E2E,V_E2E,clipE)` | PUBLISHED whisper1+clipE.md单+命名注 | PUBLISHED whisper1 `clipE.md` verdict含`去扩展名单.md…旧文件不动` | E2E_EXIT=**0**（16/16） |
| P0-3旧不动 | 对比前后sha256 old_keep/09.demo.part | 双零改 | `85677b…/754007…`前后一致 | 同上 |
| P0-3无双文件 | walk vault查`*.mp4.md` | 0个 | 0个 | 同上 |
| P0-3 vault正文 | 读clipE.md | 含stub中文 | len77含`合成小视频转写正文V2.3` | 同上 |
| P0-3空vault | `_process_one_run(EMPTY,IN_E2E,None,clipA_copy)` | RENDER_ONLY+文件名+render存 | RENDER_ONLY `clipA_copy.mp4` render存 | 同上 |
| E2E坏例 | vanished run_id | SKIP | SKIP | 同上 |
| 前端13例 | index.html含`filenameForRun/Id/source_filename/未知文件/vault_registered/needRegister/先在OB…/obsidian://open/toast用人名/taskCell用人名+shortId/obLinkFor/finderUrlFor` | 全含 | 13/13含（toast `source_filename\|\|filenameForRunId`+详情`…+sid`，run_id只留详情区） | FRONTEND_EXIT=**0** |
| 零外部 | 正则 `https?://\|<script src\|<link\|@import\|src="http\|href="http` | 0行 | 0行（`grep -c http`=0 rc=1为零命中语义） | 审计 PASS |
| 进口审计 | AST imports | 仅stdlib+stage* | `__future__/json/os/shutil/sqlite3/sys/tempfile/threading/urllib/http/datetime+stage1/2/3/4/5/6/7/8/12`，extra空 | IMPORT_EXIT=**0** |
| live status | `GET :8767/api/status?data+input` | 200双run含filename | 200 `clipA/B.mp4` | LIVE_EXIT=**0**（8/8） |
| live note | `GET :8767/api/note?run_live1` | 200 null+先在OB+finder | 一致 | 同上 |
| live index | `GET :8767/` | 200含source_filename+未知+注册人话 | 200 len43541 | 同上 |
| 坏例负控 | `v23_neg.py`故意期望202调合法start（实400 PRECHECK） | 应FAIL且exit 1 | FAIL got 400 `PRECHECK_MLX_MISSING` | **NEG_EXIT=1** |
| 编译 | `py_compile server.py` + `sh -n start.sh` | exit 0 | 均为0 | **PY_COMPILE_EXIT=0/SHN_EXIT=0** |

注：`grep -c http` 对index.html返回0行时grep进程exit=1——这是“零命中”的正确exit语义（审计脚本exit 0，此处直接以0行+rc=1双记，不判FAIL）。E2E中vault绝对路径经symlink解为`/private/tmp/...`（macOS /tmp→private/tmp），与`os.path.realpath`口径一致，不算错。`_process_one_run`缺文件分支verdict首段为人话文件名，`run_id`仅存`run_id`字段与详情区短尾（`…+shortId`），符合“run_id只留详情区”。

Runner：直接函数对照（注册9例/映射5例+预览/种子双源/附名三例+无库兜底/status/details双例/FAIL双例+抛错/vanished/note五例+E2E双分支+vanished SKIP）+ stub E2E（whisper_calls=1）+ urllib经8767（HTTPError取code断言，不看打印）+ 错期望负控证exit1 + 双编译 + AST进口 + 零外部 + 日志对账；8767起于`v23_live.py`（127.0.0.1:8767），测后已shutdown端口已释；8765常驻实例（PID 54274）零请求零扰动。

## BUGS（照 BUGS.template.md；本轮 P0×0）

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| 无（V2.3三项全绿） | — | 否 | 注册9/映射单/附名未知/未注册null+人话/已注册链接/旧sha零改/E2E双分支/live 8/8/NEG exit1全码一致 | CLOSED | 无需修 | verify 54+E2E 16+live 8+前端13代证 |
| V2.2遗留 | — | 否 | V2.2复验五项已CLOSED（接线/空归属/前端编码/运行中clear/NULL清），本轮未回归异常 | CLOSED | 无需修 | 见PACKAGING-V2.2-QA-REPORT复验修订 |

## Fix Attempt Fingerprint

- Task ID: PACKAGING-V2.3验收（首轮QA，业务零修）
- Root Cause Hypothesis: 不适用（三项全PASS；`__pycache__`若刷新为import产物，`.py` mtime app 11:15-16早于QA 11:32，源零改成立）
- Approach: 外置十目录+ffmpeg三合成2s（440Hz A/880Hz B/660Hz E，多点号/子目录复刻）+stub快返（engine_calls=1）+同库双源种子（A/B各1 run）+注册9例（None/空/不存在/unreg/reg/文件版/非str/文件路径）+映射三例（简单/多点号/子目录）+附名三例+无库兜底+status全含+details双例+缺文件移走复现+抛错stub+note五例（未注册null+人话/已注册链接/未配/无md/缺参）+stub E2E双分支（vault PUBLISHED单名+命名注+旧sha/空vault RENDER_ONLY）+无双文件walk+8767隔离live 8断言+错期望负控证exit1+双编译+AST进口+零外部+8765零扰动
- Files Changed: 仅新增本报告 `docs/qa/PACKAGING-V2.3-QA-REPORT.md`；`src/`+`app/`零改；测试写盘只在 `/tmp/v2o-pkgv23-*`（data140K+e2e168K+empty168K+input128K+e2e64K+runners32K+vault12K/12K/8K，交neat-freak收尾）
- Verification: VERIFY_EXIT=0（54/54）+ E2E_EXIT=0（16/16，PUBLISHED whisper1/RENDER_ONLY/SKIP）+ LIVE_EXIT=0（8/8）+ FRONTEND_EXIT=0（13/13）+ NEG_EXIT=1 + PY_COMPILE/SHN 0 + IMPORT 0 + 8767已释
- Failure Reason: 无（首轮即全绿，无打回）
- Difference From Previous Attempt: 首轮，无上一轮（PACKAGING-V2/V2.1/V2.2报告另存，不混；V2.2五项复验已绿，本轮无回归）

## 未闭环清单（交 supervisor/product-reviewer 定，不卡全绿）

- U-1 真实转写未测（mlx缺，start 400 `PRECHECK_MLX_MISSING`；E2E以stub代证链路，whisper冻结模型语义延续V1.8已知限制；需stage0bench venv+长视频一次，用户定时间）。
- U-2 真实目录/ob库零碰以“十目录全`/tmp/v2o-pkgv23-*` + runners/输入/vault/data全外置 + 8765常驻实例初末同PID 54274零请求 + 仓库内零写盘除本报告（app mtime 11:15-16早于QA 11:32）”代证；无真实库快照（按禁令不得写）。
- U-3 默认库 `/tmp/v2o-console-data` 非本轮所用（全显式data_root指向`/tmp/v2o-pkgv23-data*`）；本轮主库140K+e2e168K+empty168K残留交收尾。
- U-4 `__pycache__` mtime可能因import刷新（`.py` mtime未动，源零改成立；pyc为构建产物）。
- U-5 非git仓库，`git diff`口径N/A；以app mtime 11:15-16早于QA 11:32+本轮零写代证（同V2/V2.1/V2.2 U-5 Pattern）。
- U-6 残留待清：`/tmp/v2o-pkgv23-*`（data/e2e/input/vault/runners+fileprobe），交neat-freak收尾；8767已释无常驻；8765常驻实例非本轮资产，不动。
- U-7 P0口径：`DONE_STATES=(PUBLISHED,RENDER_ONLY)` + `FAIL_STATES=(FAIL,PUBLISH_BLOCKED)` 进度诚实延续V2.1；`started_at`窗口与P2-3直写等延续V2评审，不卡。
- U-8 E2E vault绝对路径显`/private/tmp/...`（macOS /tmp symlink，realpath口径一致，非bug）。
- U-9 底座`stage6.mirror.resolve_canonical`已单扩展名（VIDEO_SUFFIXES全覆盖本轮mp4），app包装为兜底校对（`app_single_ext_fixed` False亦PASS）；未来新增冷门后缀时包装仍保单，不卡。

---
目标：PACKAGING-V2.3验收｜剩 P0：无（verify 54+E2E 16+live 8全绿，NEG_EXIT=1，E2E 0）｜下一步：交 product-reviewer验＋supervisor复检（HANDOFF只记状态，不代写结论）。

## V2.4修订验收（2026-09-11 11:46-11:55，qa opencode-go/glm-5.3-flash，本窗口subagent；只改本文件，业务零改）

- 被测：`app/server.py`（95715B，11:44）+ `app/index.html`（48922B，11:44）+ `app/start.sh`（1376B，07:45）（V2.4增量：`_handle_reveal_post`+`POST /api/reveal`+行内`outCellFor`横排+`obhint`常驻；`src/`未动）
- QA执行目录（仓库外）：`/tmp/v2o-pkgv24-data`（0B）+ `/tmp/v2o-pkgv24-input`（64K：clipF 29835B 2.0s/`09.demo.part.mp4`复制）+ `/tmp/v2o-pkgv24-vault`（0B）+ `/tmp/v2o-pkgv24-runners`（16K：v24_verify/v24_frontend/v24_neg）；仓库内零写盘除本报告修订行
- 合成：`ffmpeg testsrc=320x240:rate=10:duration=2+sine=440Hz → clipF.mp4`（29835B，FF_F_EXIT=0，ffprobe 2.0s）+ `09.demo.part.mp4`由clipF复制得（HASHCP_EXIT=0）；mock：`subprocess.run`猴补丁断言`["open","-R"]`+returncode 0/1/FileNotFoundError三分支，不真弹访达
- 端口隔离：8765常驻实例（PID 69011，stage0bench venv，本轮前后一致）零请求零扰动；live改走8768独立进程（`ThreadingHTTPServer(127.0.0.1,8768)`+`server.Handler`），测后已shutdown（`lsof -i:8768`空，`:8767`空）；对8765零请求、零写
- **结论：FAIL（1项P0未闭环：无条件OB toast未删——`index.html:365`仍`toast("先在OB中把该文件夹打开为仓库后再点","err")`经`obClickHint:360`+`[data-obrun]`两处触发；其余全绿：reveal存在200+缺文件/相对/空400人话+open仅reveal语义PASS；行内横排访达OB无复制PASS；详情区保留复制PASS；常驻小灰字半PASS（行内+有url详情有，needRegister分支仅span无独立`.obhint`）；合成+mock open PASS；外置/禁碰PASS；坏例看exit码PASS；verify 22/22 exit 0+前端19/21 exit 1+NEG exit 1+双编译0；零外部；src零改以mtime 11:44早于QA 11:46代证需builder确认非本轮QA所写；真实目录/ob库零用；结论只落本报告）**

### 1. 用例简表（坏例只看 exit 码）

| 用例 | 动作 | 期望 | 实测 | exit 码 |
|---|---|---|---|---|
| P0-1存在 | `_handle_reveal_post({"path":clipF})` mock ok | 200 ok+realpath | 200 `/private/tmp/.../clipF.mp4`+`open -R`已调 | VERIFY_EXIT=**0**（22/22） |
| P0-1缺文件 | 同上 nope.mp4（mock禁调） | 400找不到了+移动或删除+不调open | 一致，open 0次 | 同上 |
| P0-1相对 | `clipF.mp4` | 400绝对路径 | 一致 | 同上 |
| P0-1空/缺键/None | `""`/无键/None | 400缺少文件路径 | 全一致 | 同上 |
| P0-1坏体 | `[1,2]`/`{not json`/`b""` | 400 JSON对象 | 全一致 | 同上 |
| P0-1引号 | `"clipF"` | 200（normalize去引号） | 200一致 | 同上 |
| P0-1 open失败 | returncode 1 stderr no such | 400定位失败 | 一致 | 同上 |
| P0-1无open | FileNotFoundError | 400 macOS不可用 | 一致 | 同上 |
| open仅reveal | `subprocess.run`计数+`open -R`计数+路由 | 各1处+无`/api/open`+有`/api/reveal` | `subprocess.run`=1（:2096）+`open -R`=1+`/api/open` 0命中 | 同上 |
| live缺文件 | `POST :8768/api/reveal` nope | 400找不到了 | 400一致 | 同上 |
| live空 | 同上空path | 400 | 400 | 同上 |
| live无open | `POST :8768/api/open` | 404未知路径 | 404一致 | 同上 |
| 行内无复制 | `outCellFor`切片查复制/访达/OB/reveal | 无复制+有访达OB+reveal+obbtn | 无`复制/data-copy/copyText`+有`访达/OB/data-reveal/obLinkFor` | FRONTEND_EXIT=**1**（19/21，两挂均为OB toast） |
| 行内横排 | CSS `.outrow` | flex+nowrap | `display:flex`+`flex-wrap:nowrap` | 同上 |
| 详情保留复制 | `renderOpenRow`+`renderLineage` | 有复制路径+复制 | `复制路径/data-copy2`+`复制</button>/data-copy="` | 同上 |
| OB toast删除 | 全文`toast("先在OB` | 0命中 | 1命中（:365经:360+行内/详情`[data-obrun]`触发）**FAIL** | 同上 |
| 常驻小灰字 | `.obhint`+行内+详情 | CSS+行内无条件+详情常驻 | CSS齐+行内:398无条件`打不开？确认OB中已打开同名库`+有url详情:523有；needRegister:524/不可用:525仅span无独立`.obhint`半PASS | 同上 |
| reveal走后端 | `fetch("/api/reveal"`+POST JSON | 有+无location跳转 | 有`JSON.stringify({path:p})`+`revealPath`内无`window.location` | 同上 |
| 零外部 | 正则 `http` | 0行 | 0行（`grep -c http`=0 rc=1为零命中语义） | 审计 PASS |
| 进口审计 | AST imports | 仅stdlib+stage*+http.server | `json/os/shutil/sqlite3/sys/tempfile/threading/subprocess(stdlib)/urllib/http/datetime+stage1/2/3/4/5/6/7/8/12`，extra空 | IMPORT PASS |
| 坏例负控 | `v24_neg.py`故意期望202调合法reveal（实200） | 应FAIL且exit 1 | FAIL got 200 `{'ok':True,...}` | **NEG_EXIT=1** |
| 编译 | `py_compile server.py` + `sh -n start.sh` | exit 0 | 均为0 | **PY_COMPILE_EXIT=0/SHN_EXIT=0** |

注：`grep -c http`返回0行时grep进程exit=1——零命中正确语义（审计PASS）。`/tmp`经symlink解为`/private/tmp`（realpath口径一致，非bug）。8765 PID由V2.3报告54274变为本轮69011（stage0bench venv），系环境变化非本轮QA所动，本轮对8765零请求以`lsof`前后一致+只用8768代证。app mtime 11:44早于QA首命令11:46，源零改指QA本轮零写，需builder确认11:44改动即V2.4增量本身。

Runner：直接函数对照（存在/缺文件/相对/空/缺键/None/非dict/坏json/空体/引号/open三分支）+ mock `open -R`断言 + urllib经8768（HTTPError取code断言，不看打印）+ 前端切片断言（outCell/renderOpenRow/renderLineage/obhint/toast）+ 错期望负控证exit1 + 双编译 + AST进口 + 零外部 + 8765零扰动；8768起于`v24_verify.py`内联进程，测后已shutdown端口已释。

### BUGS（照 BUGS.template.md；本轮 P0×1 FAIL，打回builder）

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| V2.4-B1 OB toast未删 | P0 | 是 | 置vault未注册→点行内/详情`OB`→弹`先在OB中把该文件夹打开为仓库后再点`toast（`index.html:365 obClickHint:360`，`[data-obrun]`两处绑定:444/:534）；期望V2.4无条件删除该toast只留常驻小灰字 | OPEN | builder删`obClickHint`内toast（或整函数去toast化）+ needRegister/不可用分支补独立`.obhint` div后交qa复验 | FRONTEND 19/21，`fe-no-ob-toast/fe-obclickhint-no-toast` FAIL |
| V2.4行内/详情/后端 | — | 否 | reveal 22/22+行内无复制横排+详情复制+小灰字行内常驻+mock三分支+live 404+零外部+NEG exit1全码一致 | CLOSED | 无需修 | VERIFY_EXIT=0+NEG_EXIT=1代证 |
| V2.3遗留 | — | 否 | V2.3三项已CLOSED（54+16+8+13），本轮未回归异常 | CLOSED | 无需修 | 见本报告V2.3原文 |

### Fix Attempt Fingerprint

- Task ID: PACKAGING-V2.4验收（首轮QA，业务零修）
- Root Cause Hypothesis: 不适用（后端全PASS；唯一挂项为前端`obClickHint`残留toast一行，删一行即闭环；`__pycache__`若刷新为import产物，`.py` mtime app 11:44早于QA 11:46，QA零改成立）
- Approach: 外置四目录+ffmpeg单合成2s（440Hz clipF+多点号复制）+mock open三分支（ok/returncode1/FileNotFound）+直接函数12例（存在/缺/相对/空/缺键/None/非dict/坏体/空体/引号）+open语义计数（subprocess 1/open-R 1/无api/open/有api/reveal）+8768隔离live三断言（缺400/空400/open404）+前端切片21断言（行内无复制横排/详情复制/OB toast计数/小灰字三处/CSS）+错期望负控证exit1+双编译+AST进口+零外部+8765零扰动
- Files Changed: 仅追加本修订节进 `docs/qa/PACKAGING-V2.3-QA-REPORT.md`；`src/`+`app/`零改；测试写盘只在 `/tmp/v2o-pkgv24-*`（input64K+runners16K+data/vault 0B，交neat-freak收尾）
- Verification: VERIFY_EXIT=0（22/22）+ FRONTEND_EXIT=1（19/21，两挂同因B1）+ NEG_EXIT=1 + PY_COMPILE/SHN 0 + IMPORT PASS + 8768已释
- Failure Reason: V2.4-B1（OB toast未删，P0阻塞，返工派须续本链）
- Difference From Previous Attempt: 首轮，无上一轮（V2.3原文85行不动，本节为追加）

### 未闭环清单（交 supervisor/product-reviewer 定，B1卡全绿）

- B1 P0阻塞：`obClickHint` toast删后复验前端21/21；needRegister分支建议补常驻`.obhint`以符“常驻”口径（supervisor定是否强制）。
- U-1 真实转写未测延续（mlx语义同V2.3 U-1；本轮reveal不依赖转写，mock代证）。
- U-2 真实目录/ob库零碰以“四目录全`/tmp/v2o-pkgv24-*`+8768隔离+8765零请求+仓库零写除本报告”代证；无真实库快照（按禁令不得写）。
- U-3 默认库 `/tmp/v2o-console-data` 非本轮所用（reveal直调path，无data_root依赖；主库0B残留交收尾）。
- U-4 `__pycache__` mtime可能因import刷新（`.py` mtime未动，QA零改成立；pyc为构建产物）。
- U-5 非git仓库，`git diff`口径N/A；以app mtime 11:44早于QA 11:46+本轮零写代证（同V2.3 U-5 Pattern）。
- U-6 残留待清：`/tmp/v2o-pkgv24-*`（data/input/vault/runners），交neat-freak收尾；8768已释无常驻；8765常驻实例（69011）非本轮资产，不动。
- U-7 app mtime 11:44系V2.4 builder增量，需builder/HANDOFF确认增量内容与本报告被测一致（QA只认mtime早于首命令+零写）。

---
目标：PACKAGING-V2.4验收｜剩 P0：B1×1（OB toast未删，前端19/21，VERIFY 22/22，NEG_EXIT=1）｜下一步：打回builder删toast+补小灰字后qa续本链复验（HANDOFF只记状态，不代写结论）。

## V2.4-B1复验（2026-09-11 11:49-11:51，qa opencode-go/glm-5.3-flash，本窗口subagent续链；只改本文件，业务零改）

- 被测：`app/index.html`（49522B，11:48，980行）+ `app/server.py`（95715B，11:44）+ `app/start.sh`（1376B，07:45）（V2.4-B1终版增量：`obClickHint`去toast化改写`.obhint`+`renderOpenRow` needRegister独立`.obhint`；`src/`未动）
- QA执行目录（仓库外）：`/tmp/v2o-pkgv24b1-data`（0B）+ `/tmp/v2o-pkgv24b1-input`（32K：clipG 30262B 2.0s）+ `/tmp/v2o-pkgv24b1-vault-reg`（0B：空`.obsidian`目录占位，未写入真实库）+ `/tmp/v2o-pkgv24b1-vault-unreg`（0B）+ `/tmp/v2o-pkgv24b1-runners`（12K：b1_frontend/b1_backend/b1_neg）；仓库内零写盘除本报告修订行
- 合成：`ffmpeg testsrc=320x240:rate=10:duration=2+sine=440Hz → clipG.mp4`（30262B，ffprobe 2.0s，PROBE_G_EXIT=0）；mock：`subprocess.run`猴补丁断言`["open","-R"]`+returncode 0三分支，不真弹访达
- 端口隔离：本轮未起HTTP server（直接函数对照+文件切片断言），对8765常驻实例零请求零扰动；无8767/8768残留；真实目录/ob库零用
- **结论：PASS（三项全绿：B1-1 `obClickHint`零toast（块内`toast(`=0，全文`toast("先在OB`=0命中，成功`return true`直通）；B1-2 needRegister独立`.obhint`（`renderOpenRow:535`含`<div class="obhint">先在OB中把该文件夹打开为仓库后再点</div>`，`ob.needRegister`分支+CSS+`data-obrun`6命中）；B1-3成功路径零打扰（OB成功点击零toast零preventDefault，行内无复制横排，reveal走后端无location跳转；成功分支被动小灰字2处延续V2.4首轮“行内+有url详情有”PASS口径，不计打扰，见注）；前端18/18 exit 0+后端8/8 exit 0+NEG exit 1+双编译0+进口extra空+零外部strict；外置/合成/禁碰PASS；坏例看exit码PASS；src零改以app mtime 11:48/11:44早于QA 11:49代证；结论只落本报告）**

### 1. 用例简表（坏例只看 exit 码）

| 用例 | 动作 | 期望 | 实测 | exit 码 |
|---|---|---|---|---|
| B1-1块零toast | `obClickHint`块查`toast(` | 0 | 0 | FRONTEND_B1_EXIT=**0**（18/18） |
| B1-1全文零toast先OB | 全文`toast("先在OB`/`toast('先在OB` | 0命中 | 0命中 | 同上 |
| B1-1改字 | `.obhint`+先在OB改`textContent`/新建div | 有 | `hint.textContent`/`createElement("div")+.obhint`齐 | 同上 |
| B1-1成功直通 | 非needRegister `return true` | 直通无prevent | `return true`，仅needRegister分支`preventDefault+return false` | 同上 |
| B1-2独立obhint | `renderOpenRow` needRegister分支 | 独立`<div class="obhint">先在OB…` | :535命中1处 | 同上 |
| B1-2 CSS/绑定 | `.obhint{`+`data-obrun` | CSS齐+≥4 | CSS齐+6命中（含:360/:444/:534三处绑定） | 同上 |
| B1-3行内无复制 | `outCellFor`切片 | 无`data-copy/copyText` | 无，有`data-reveal/OB` | 同上 |
| B1-3横排/后端 | `.outrow`+`fetch("/api/reveal"` | flex+nowrap+无location | `display:flex+flex-wrap:nowrap`+`revealPath`内无`window.location` | 同上 |
| 回归详情复制 | `data-copy2/复制路径` | 有 | 有 | 同上 |
| 零外部strict | `https?://|<script src|<link http|@import|src="http|href="http` | 0行 | 0行 | 审计 PASS |
| 后端存在 | `_handle_reveal_post({"path":clipG})` mock ok | 200 ok+open-R 1次 | 200 `/private/tmp/.../clipG.mp4`+1次 | BACKEND_B1_EXIT=**0**（8/8） |
| 后端缺文件 | 同上 nope.mp4 | 400找不到了+0次open | 一致 | 同上 |
| 后端相对 | `clipG.mp4` | 400绝对路径 | 一致 | 同上 |
| open仅reveal | `subprocess.run`计数+路由 | 1处+无`/api/open`+有`/api/reveal` | 1处+0命中+有 | 同上 |
| 坏例负控 | `b1_neg.py`故意期望202调合法reveal（实200） | 应FAIL且exit 1 | FAIL got 200 `{'ok':True,...}` | **NEG_EXIT=1** |
| 进口审计 | AST imports | 仅stdlib+stage* | `__future__/datetime/http/json/os/shutil/sqlite3/stage1/2/3/4/5/6/7/8/12/subprocess/sys/tempfile/threading/urllib`，extra空 | IMPORT_EXIT=**0** |
| 编译 | `py_compile server.py` + `sh -n start.sh` | exit 0 | 均为0 | **PY_COMPILE_EXIT=0/SHN_EXIT=0** |

注：成功分支被动小灰字2处披露（`outCellFor:409`无条件`打不开？确认OB中已打开同名库`+`renderOpenRow:534`有url分支同文案）——延续V2.4首轮“行内+有url详情有”PASS口径，被动灰字非popup不计打扰；“零打扰”本轮口径=OB成功点击零toast零preventDefault（`return true`直通）+行内无复制+无location跳转。若supervisor要“成功零hint”则需另起P0，当前终版按“零toast”口径PASS。`/tmp`解为`/private/tmp`系macOS symlink，realpath口径一致非bug。app mtime 11:48（index.html 49522B，较首轮11:44/48922B +600B即B1修复增量）早于QA首命令11:49，QA本轮零写app/src。

Runner：文件切片18断言（obClickHint块截取`obClickHint→revealPath`+全文计数+outCell/outrow/reveal/零外部）+直接函数对照（存在/缺/相对+open语义计数+路由）+mock `open -R`断言+错期望负控证exit1+双编译+AST进口+零外部+合成clipG外置+8765零请求；未起HTTP，无端口残留。

### BUGS（照 BUGS.template.md；本轮 P0×0，B1 CLOSED）

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| V2.4-B1 OB toast未删 | P0 | 是 | 首轮`index.html:365 toast("先在OB…`经`:360+[data-obrun]`两处触发；终版块内0+全文0命中，改写`.obhint`代证 | CLOSED | 无需修 | FRONTEND 18/18，`b1-obClickHint-no-toast/b1-no-toast-xianOB` PASS |
| V2.4-B1 needRegister无独立hint | P0 | 是 | 首轮needRegister仅span；终版`renderOpenRow:535`独立`<div class="obhint">先在OB…` | CLOSED | 无需修 | `b1-needRegister-independent-obhint-detail` PASS |
| V2.4行内/后端/回归 | — | 否 | 行内无复制横排+详情复制+reveal 8/8+mock+零外部+NEG exit1全码一致 | CLOSED | 无需修 | BACKEND 8/8+NEG 1代证 |
| V2.3遗留 | — | 否 | V2.3三项已CLOSED（54+16+8+13），本轮未回归异常 | CLOSED | 无需修 | 见本报告V2.3原文 |

### Fix Attempt Fingerprint

- Task ID: PACKAGING-V2.4-B1复验（续链，业务零修）
- Root Cause Hypothesis: 不适用（三项全PASS；`__pycache__`若刷新为import产物，`.py` mtime 11:44/index 11:48早于QA 11:49，QA零改成立）
- Approach: 外置五目录+ffmpeg单合成2s（440Hz clipG 30262B）+mock open（ok单分支，缺文件禁调）+文件切片18断言（obClickHint块0toast/改字/直通+needRegister独立div+CSS/绑定+行内无复制横排+后端无跳转+零外部strict）+直接函数8例（存在/缺/相对/open语义/路由）+错期望负控证exit1+双编译+AST进口+8765零请求
- Files Changed: 仅追加本修订节进 `docs/qa/PACKAGING-V2.3-QA-REPORT.md`；`src/`+`app/`零改；测试写盘只在 `/tmp/v2o-pkgv24b1-*`（input32K+runners12K+data/vault 0B，交neat-freak收尾）
- Verification: FRONTEND_B1_EXIT=0（18/18）+ BACKEND_B1_EXIT=0（8/8）+ NEG_EXIT=1 + PY_COMPILE/SHN 0 + IMPORT extra空 + 零外部strict PASS + 无HTTP残留
- Failure Reason: 无（B1终版一次绿，无打回）
- Difference From Previous Attempt: 首轮FAIL（19/21，两挂同因B1 toast未删+无独立hint）→终版18/18+8/8全绿；V2.3原文156行不动，本节为追加

### 未闭环清单（交 supervisor/product-reviewer 定，不卡全绿）

- U-1 真实转写未测延续（mlx语义同V2.3 U-1；本轮reveal不依赖转写，mock代证）。
- U-2 真实目录/ob库零碰以“五目录全`/tmp/v2o-pkgv24b1-*`+未起HTTP对8765零请求+仓库零写除本报告”代证；无真实库快照（按禁令不得写）。
- U-3 默认库 `/tmp/v2o-console-data` 非本轮所用（reveal直调path，无data_root依赖；主库0B残留交收尾）。
- U-4 `__pycache__` mtime可能因import刷新（`.py` mtime未动，QA零改成立；pyc为构建产物）。
- U-5 非git仓库，`git diff`口径N/A；以app mtime 11:48/11:44早于QA 11:49+本轮零写代证（同V2.3 U-5 Pattern）。
- U-6 残留待清：`/tmp/v2o-pkgv24b1-*`（data/input/vault-reg/unreg/runners），交neat-freak收尾；无端口残留；8765常驻实例非本轮资产，不动。
- U-7 成功被动小灰字2处（outCellFor:409无条件+renderOpenRow:534有url分支）按“零toast”口径不计打扰；若要“成功零hint”需supervisor另起P0（当前PASS口径已披露）。

---
目标：PACKAGING-V2.4-B1复验｜剩 P0：无（前端18/18+后端8/8全绿，NEG_EXIT=1）｜下一步：交 product-reviewer验＋supervisor复检（HANDOFF只记状态，不代写结论）。
