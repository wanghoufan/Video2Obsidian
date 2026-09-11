# QA-REPORT｜UX-FIX返工验收（V2.1 P1×2 + UX P0×6 + P1×8，按UX-REVIEW逐条重放）

- QA：qa（opencode-go/glm-5.3-flash，本窗口 subagent；未改业务代码，只写本报告）
- 被测：`app/index.html`（724行，36376B，09:08）+ `app/server.py`（1142行，48312B，09:08）+ `app/start.sh`（40行，1376B，07:45）（UX返工后现状；`src/` 只读复用）
- 任务目标：验收返工（V2.1 P1×2 + UX P0×6 + P1×8，按docs/review/UX-REVIEW.md逐条验收口径重放：中文标签、绿条常驻+停止、人话错误、失败红块+重试、进度人话+心跳、输出路径可复制、浏览视频计数、失焦即验、状态全中文；合成+stub；外置目录；用户真实目录与ob库禁碰；坏例看exit码）
- QA 执行目录（仓库外）：`/tmp/v2o-uxfix-data`（worker主库）+ `/tmp/v2o-uxfix-data-live`（live202隔离库）+ `/tmp/v2o-uxfix-input`（clip_a/b双2s合成）+ `/tmp/v2o-uxfix-input-live`（live隔离输入）+ `/tmp/v2o-uxfix-vault`（PUBLISHED出md）+ `/tmp/v2o-uxfix-empty`（空目录对照）+ `/tmp/v2o-uxfix-runners`（4脚本）；仓库内零写盘除本报告
- 合成小视频：`ffmpeg testsrc 320x240 rate10/12 duration2 + sine 440/880Hz → clip_a.mp4`（30262B）+ `clip_b.mp4`（30726B），ffprobe各2.0s，FF_EXIT=0
- stub：`server._transcribe_audio` 猴补丁两档——快返固定中文+1 segment+engine_calls=1；抛错档`raise RuntimeError(mlx missing sim)`，全程不碰 `mlx_whisper`/`extract_temp_wav` 真转写
- 端口隔离：8765常驻实例零探测零POST；live走8767（mlx缺失分支）+8769（mlx-stub就绪分支）+8768（排障用，已释），测后全停，lsof空
- **结论：PASS（V2.1 P1×2 + UX P0×6 + P1×8 共16项全CLOSED；STATIC 41/41 + WORKER 32/32 + LIVE 13/13 + LIVE-RETRY 202/409 + SUPP长视频/引号/状态映射/零外部全PASS；NEG exit 1；py_compile/sh-n exit 0；零外部；用户真实目录/ob库零碰；结论只落本报告）**

## 1. 用例简表（坏例只看 exit 码）

| 用例 | 动作 | 期望 | 实测 | exit 码 |
|---|---|---|---|---|
| UX-P0-1 中文标签 | 读label/placeholder/adv折叠+可见区搜EN | 视频文件夹必填/笔记库选填/高级收起，可见区input_root/ob_vault_root/data_root/Render零命中 | LABELS三中文+PLACEHOLDERS人话+visible 0/0/0/0 | STATIC_EXIT=**0** |
| UX-P0-1 空vault后果 | 空状态empty分支 | “不填笔记库也能转，md在数据目录的jobs里，每行会给路径” | 双分支全含 | STATIC_EXIT=**0** |
| UX-P0-2 绿条常驻+停止 | liveBar/btnStop/api/stop+btnStart置灰 | 监听中绿条“监听中：{input}，把视频丢进去即可”常驻，btnStart禁用变“监听中…”，btnStop停后锁回未监听 | liveBar+stop 200+restart 202（8769） | WORKER/LIVE_EXIT=**0** |
| UX-P0-2 409人话非红 | POST重复start | “已经在监听同一文件夹，无需重复操作”走warn非err | POST2 409+`say(...,"warn")`（8769隔离库证） | LIVE_RETRY **PASS** |
| UX-P0-2 运行中改输入黄条 | input事件 | “修改下次启动生效，当前监听…”黄条 | 静态含+`editHint warn` | STATIC_EXIT=**0** |
| UX-P0-3 输出可复制 | 各造PUBLISHED+RENDER_ONLY各1 | lineage必显输出/结论/耗时+复制，runs表输出列“打开位置+复制”，vault映射预览 | PUBLISHED `/tmp/v2o-uxfix-vault/clip_a.md`存在+RENDER_ONLY render md存在+preview“→库内…式样” | WORKER_EXIT=**0** |
| UX-P0-3 无worker后缀 | 全文搜（worker） | 零命中（代码内除外） | html 0命中 | STATIC_EXIT=**0** |
| UX-P0-4 三类失败红块+重试 | 源缺失/mlx缺失/vault不可写各1 | 每行lineage红块“原因+下一步”+重试可点，禁ArchiveError裸词，刷新后读后端verdict不丢 | 三FAIL全“→…点重试”+snapshot details持久+`data-retry` | WORKER_EXIT=**0** |
| UX-P0-5 进度人话+心跳 | renderProgress文案/双条/60s兜底 | “正在X（第N步/共5步：发现→听写→整理→成稿→入库）·已用时Ys·心跳Zs前更新·排队/成功/失败”+步骤条注明非精确+超60s“还在跑…” | 静态全含，可见区标准化/渲染零命中 | STATIC_EXIT=**0** |
| UX-P0-6 人话错误 | mlx/相对/不存在/文件/409/500 | mlx→“转写环境没就绪：请用自带一键启动重开…”+start.sh复制，路径类全“请点浏览重选”，可视区stage0bench/mlx_whisper/PRECHECK零裸露 | 三browse 400人话+live start mlx400+`./app/start.sh`配中文 | WORKER/LIVE_EXIT=**0** |
| UX-P0-6 去引号回显 | 失焦stripQuotes | “已自动去掉首尾引号”黄字 | `normalize_path('"/tmp/a b"')==/tmp/a b`+前端回显 | SUPP **PASS** |
| UX-P1-1 单run重试幂等 | POST /api/retry连点两次 | 首202“已重新排队只重跑这一个”，次202“已在排队无需重复”，不产重复任务 | 202/202双断言 | WORKER_EXIT=**0** |
| UX-P1-2 重起跳过已完成 | 清内存模拟重启读磁盘 | 磁盘PUBLISHED≥1，重起done不归零，pending排除磁盘done，无重复whisper | disk 4+restart done≥1+pending排除 | WORKER_EXIT=**0** |
| UX-P1-3 空vault绿条+路径 | vault=None跑1个 | 绿条追加“未填笔记库只存数据目录”，RENDER_ONLY路径真实可复制 | verdict含数据目录+render md存在+preview空vault空串 | WORKER_EXIT=**0** |
| UX-P1-4 浏览视频计数 | /api/browse input/empty | 每子目录“（N个视频）”，当前“有N个视频（如a、b）”，空目录黄字“无视频文件选了也转不出东西” | input total2+empty total0+counts | WORKER/LIVE_EXIT=**0** |
| UX-P1-5 长视频提示 | 稀疏600M+input失焦/browse | >600s或>500MB估算提示“检测到长视频N个，转写可能超Y分钟，分段请勿关”，转写中注明“长视频分段中” | sparse600M long_estimate=1+`longHint/分段` | SUPP **PASS** |
| UX-P1-6 完成提醒 | toast+Notification | done/failed变化页内toast绿/红3s含文件名，初次申请Notification权限，拒绝只toast不报错 | `toast+Notification+3000`静态+`转写完成/失败`文案 | STATIC_EXIT=**0** |
| UX-P1-7 失焦即验 | blur三输入调/api/browse | 错即框红+人话，対即框绿，全対开始高亮（仍可点防race） | blur监听+`good/bad+ready`+文件非目录400“须为目录” | WORKER_EXIT=**0** |
| UX-P1-8 状态全中文 | 状态映射表+色板 | 排队中/发现中/听写中/整理中/成稿中/入库中/已入库/已成稿未入库/失败/入库受阻，可见区QUEUED/PUBLISHED/RENDER_ONLY零裸露 | 10映射全含+visible 0/0/0 | SUPP **PASS** |
| V2.1-P1-1 未知异常补FAIL | _process抛OSError模拟 | except补`FAIL“处理时遇到意外…点重试”`再进done，不静默丢任务 | 补记命中+代码“处理时遇到意外” | WORKER_EXIT=**0** |
| V2.1-P1-2 failed/total | snapshot queue | queue含pending/done/failed/total，total=pending+done+failed，前端“排队/成功/失败” | `{pending:1,done:2,failed:2,total:5}`数学成立 | WORKER_EXIT=**0** |
| V2.1-P2-1全量映射（顺带） | details_by_run | 全量details（≤100+磁盘），非20窗口，防21+文件老run回落QUEUED | details+merged+20win显示共存 | SUPP **PASS** |
| 零外部 | 正则https/script-src/link | 0行 | `https==0+无script src` | SUPP **PASS** |
| 坏例负控 | 故意202==400 | 应FAIL且exit 1 | FAIL | **NEG_EXIT=1** |
| 编译 | py_compile+sh -n | exit 0 | 均为0 | **PY_COMPILE_EXIT=0/SHN_EXIT=0** |

注：STATIC初轮`P0-3 preview`曾FAIL系QA脚本把服务端字符串“式样”错查到HTML可见区所致（preview文本由后端`_preview_mapping`下发，前端只设`textContent`），修正为“html有preview位+srv有式样+resolve_canonical”后41/41 PASS，以**STATIC_EXIT=0**为准（打印错不改exit结论，同V2.1 OBS-3 pattern）。LIVE-202首轮在复用worker旧库时POST2回202非409，系旧库fcntl/DB残留致首轮`_launch→run_startup`失败翻转running的测试隔离问题，换`/tmp/v2o-uxfix-data-live`隔离库后POST1 202→POST2 409复现PASS（见LIVE-RETRY节），非产品回归。

Runner：STATIC静态41断言+WORKER直接调`_process_one_run/_handle_browse/_handle_retry/_handle_stop/_preview_mapping/_scan_disk_states`（mlx bypass靠stub）+LIVE urllib直调8767（HTTPError取code断言）+LIVE-RETRY 8769测202/409/重起（`_mlx_available` stub True）+SUPP稀疏600M/引号/映射/零外部+NEG错期望证exit1+双编译；8765零扰动；`grep -c`零命中rc=1按正确语义不判FAIL。

## BUGS（照 BUGS.template.md；本轮无 P0/P1）

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| 无（UX-FIX侧16项全绿） | — | 否 | STATIC41+WORKER32+LIVE13+LIVE-RETRY202/409+SUPP全码一致；负控exit 1 | CLOSED | 无需builder修 | 三失败FAIL全人话重试+双PUBLISHED/RENDER_ONLY路径存在+409人话 |
| OBS-1（观察） | P3 | 否 | `_handle_start_post`回包含`code:PRECHECK_MLX_MISSING`字段，前端只渲染`error`人话不显示code；属机器码+人话双通道，非裸抛 | CLOSED | 无需修（前后端同文，人话已配start.sh复制） | live mlx400复现，页面文案零PRECHECK |
| OBS-2（观察） | P3 | 否 | `start.sh`含`stage0bench`路径字样但配中文WARN+复核回显，属UX口径“命令按钮内start.sh例外需配中文说明” | CLOSED | 无需修 | sh 40行中文齐 |
| OBS-3（观察） | P3 | 否 | `server.py:69`注释含“标准化/渲染”系禁词说明注释本身，非用户文案；可见区零命中 | CLOSED | 无需修 | vis 0/0已证 |
| OBS-4（观察） | P3 | 否 | `processed`仍保留`[-20:]`显示窗口，行级映射走全量`details_by_run`（merged内存+磁盘），21+文件不丢映射 | CLOSED | 无需修（V2.1-P2-1已闭） | SUPP已证 |

## Fix Attempt Fingerprint

- Task ID: UX-FIX返工验收（首轮QA，业务零修）
- Root Cause Hypothesis: 不适用（16项全PASS；`__pycache__`若刷新为import产物，`.py` mtime app 09:08早于QA 09:13，源零改成立）
- Approach: 外置六目录+ffmpeg双合成2s+stub两档（快返/抛错）+同库双run种子（PUBLISHED/RENDER_ONLY）+三失败（源删/mlx抛/vault文件）+重试幂等双调+清内存模拟重启读磁盘+稀疏600M估长视频+引号三态+8767/8769双live（缺失/就绪分支）+错期望负控证exit1+双编译+零外部+8765零扰动
- Files Changed: 仅新增本报告 `docs/qa/UX-FIX-QA-REPORT.md`；`src/`+`app/`零改；测试写盘只在 `/tmp/v2o-uxfix-*`（data×2+input×2+vault+empty+runners，交neat-freak收尾）
- Verification: STATIC_EXIT=0（41/41）+ WORKER_EXIT=0（32/32，PUBLISHED canonical存在+RENDER_ONLY rendered存在+三FAIL人话+重试202双幂等+queue 1/2/2/5）+ LIVE_EXIT=0（13/13）+ LIVE-RETRY PASS（202→409→stop→restart202）+ SUPP PASS（稀疏长视频1+引号3态+10映射+零外部）+ NEG_EXIT=1 + PY_COMPILE/SHN 0 + 三端口已释
- Failure Reason: 无FAIL项（UX-FIX侧；NEG系故意FAIL以证exit1；STATIC/LIVE首轮各1脚本cosmetic见注）
- Difference From Previous Attempt: 首轮，无上一轮（PACKAGING-V2.1报告另存，不混；V2.1 P1×2本轮复用worker+snapshot复证）

## 未闭环清单（交 supervisor/product-reviewer 定，不卡本 PASS）

- U-1 真实转写未测（mlx缺，live-8767走PRECHECK人话400分支；全链以stub代证，whisper_calls=1；需stage0bench venv+60s真实切片一次，用户定时间）。
- U-2 真实目录/ob库零碰以“六目录全`/tmp/v2o-uxfix-*` + 8765零探测零POST + 仓库内零写盘除本报告”代证；无真实库快照（按禁令不得写）。
- U-3 默认库 `/var/…/T/v2o-console-data` 非本轮所用（WORKER/LIVE全显式data_root指向`/tmp/v2o-uxfix-data*`两库）；本轮两库残留交收尾。
- U-4 `__pycache__` mtime可能因import刷新（`.py` mtime未动，源零改成立；pyc为构建产物）。
- U-5 非git仓库，`git diff`口径N/A；以app mtime 09:08早于QA 09:13+本轮零写代证（同V2.1 U-5 Pattern）。
- U-6 残留待清：`/tmp/v2o-uxfix-data*`（含jobs/manifests）+ input×2/vault/empty+runners（交neat-freak收尾）；三live端口已释无常驻；8765常驻实例非本轮资产，不动。
- U-7 进度口径：queue done仅计PUBLISHED/RENDER_ONLY成功数，failed单列，total=pending+done+failed，前端“排队/成功/失败”三分（V2.1-P1-2已按code-reviewer改法落地）。
- U-8 长视频时长>600s分支未用真实600s视频覆盖，以稀疏600MB（>500MB估算注明估算）代证“检测到长视频1个”；真实>600s提示出现/不出现各1例待用户长视频验收时补。

---
目标：UX-FIX返工验收｜剩 P0：无（QA 口径 PASS；闭环判定以 supervisor 复检为准）｜下一步：交 product-reviewer 验＋supervisor 复检（HANDOFF 只记状态，不代写结论）。

## 修订 2026-09-11 PUBLISH_BLOCKED定向补测（只测lineage红块，不重跑16项）

- QA：qa（opencode-go/glm-5.3-flash，本窗口 subagent；未改业务代码，只改本报告）
- 锁定：`app/index.html` 735行 MD5 3972edec0d2fca1674d21a6d4aabc849 + `app/server.py` 1142行 MD5 185952ffc603f54299893563b306fe14（测后复核一致，业务零改）
- 造法（复server.py:778-783 except分支）：外置 `/tmp/v2o-pb-data` + `/tmp/v2o-pb-input/pb_clip.mp4`（ffmpeg testsrc 320x240 rate10 duration2 + sine 440Hz新合成29835B，ffprobe 2.0s）+ stub快返固定中文engine_calls=1 + vault指向文件 `/tmp/v2o-pb-vault-dir-notafile`（`initial_publish`抛`[Errno 17] File exists`）；用户真实目录/ob库零碰（全`/tmp/v2o-pb-*`，8765零探测零POST，仓库内零写除本报告）
- 实测：`run_b76c3fd628698c1c` state=PUBLISH_BLOCKED，verdict=`笔记库不可写：[Errno 17] File exists…→检查库路径权限后点重试`（含→可切分）；rendered_path `/tmp/v2o-pb-data/data/jobs/run_b76c3fd628698c1c/render/rendrev_7210f2fd2e5d.md` 存在（可复制输出）；manifest末receipt PUBLISH_BLOCKED且verdict一致（receipts_n=4）
- 点行（复刻renderLineage 352分支+outPathFor 280-281）：结论`初稿已保留，入库未完成`（html:356命中）＋输出列`data-copy`复制按钮（358命中）＋红块`原因/下一步`（365-368 failbox命中，reason=`笔记库不可写…` next=`检查库路径权限后点重试`）＋`data-retry 重试这个视频`可点（368/296命中，statusCN`入库受阻`242/504命中）；后端`_handle_retry_post`连调202`已重新排队只重跑这一个`/202`已在排队无需重复`幂等PASS
- 刷新不丢：`_scan_disk_states`磁盘仍PUBLISH_BLOCKED且verdict/rendered_path与out一致；清内存模拟重启后`_listener_snapshot details_by_run`仍BLOCKED且verdict一致
- STATIC：`sed -n 343p | grep -c PUBLISH_BLOCKED`=0（rc=1按正确语义）＋`352p`=1（rc=0），与任务口径`343无/352有`一致
- 结论：PASS（PUBLISH_BLOCKED×1全链：红块+复制+重试+刷新+STATIC；16项不重跑；残留`/tmp/v2o-pb-*`交收尾）

## 修订 2026-09-11 路径记忆小修验收（只验记忆，不重跑16项）

- QA：qa（opencode-go/glm-5.3-flash，本窗口 subagent；未改业务代码，只改本报告）
- 被测：`app/index.html` 777行 MD5 0593824dd94f8c87b4df36c502cb41ef + `app/server.py` 1163行 MD5 a818dfd9f5ce7c2573c4146d4d663f1a（UX-FIX后+53/+21行即本小修；测后复核一致，业务零改）
- 任务目标：验收路径记忆小修（localStorage三键保存/加载回填/清空不崩；后端last_*回显；成功条“上次监听”；外置测试；禁碰用户真实目录与ob库；坏例看exit码）
- QA 执行目录（仓库外）：`/tmp/v2o-pathmem-data` + `/tmp/v2o-pathmem-data-live` + `/tmp/v2o-pathmem-input`（空目录browse对照）+ `/tmp/v2o-pathmem-vault` + `/tmp/v2o-pathmem-runners`（static/backend/ls_logic/live/neg五脚本）；仓库内零写盘除本报告
- 用例简表（坏例只看 exit 码）：STATIC 19/19 EXIT=0（三键`v2o-input/vault/data-root`各1+savePaths/restore定义+202后save+加载即restore+刷新非running分支restore+清空removeItem×3+try/catch≥4+后端`_last_config`三键+snapshot注入三行+start update+stop不清记忆+成功条`上次监听：+已回填，点开始监听即重起`+display block+LS为主后端为辅）；BACKEND 19/19 EXIT=0（直调`_handle_start_post/_listener_snapshot/_handle_stop_post`全`/tmp/v2o-pathmem-*`：初snapshot含last_*三键+stub mlx+stub _launch后202+launch参数外置+snapshot回显I/D/V+二次409仍保留+stop 200后仍保留running False+空vault 202且last None+空data回DEFAULT 202+相对/不存在各400）；LS_LOGIC 5/5 EXIT=0（node仿真：存三键+空回填+清空删键留空不崩+抛错LS guarded不崩+成功条文案）；LIVE 7/7 EXIT=0（8775隔离服：初snapshot last_*全None+相对400后仍None+mlx缺失400`没就绪`后仍None+browse外置200；8765 PID 76485全程LISTEN零POST零探测）；NEG_EXIT=1（故意202==400 AssertionError证exit1）；PY_COMPILE_EXIT=0/SHN_EXIT=0；零外部`https==0/script src==0`（grep无命中rc=1按正确语义）
- BUGS：无P0/P1（记忆侧全绿；STOP段`_last_config`零命中即停后不丢记忆成立，符合“上次监听”需求；mlx失败/坏输入不污染last_*成立）
- Fingerprint：Task 路径记忆小修首轮QA，业务零修；Approach 外置五目录+三键静态19断言+直接调函数19断言（含空vault/空data/409/stop保留）+node行为仿真5断言+8775隔离HTTP 7断言+错期望负控+双编译+零外部+8765零扰动；Files Changed 仅本报告；Verification STATIC_EXIT=0+BACKEND_EXIT=0+LS_EXIT=0+LIVE_EXIT=0+NEG_EXIT=1+PY/SHN 0+8775已释8765未动；Failure 无FAIL（NEG系故意FAIL）
- 未闭环：U-PM1 真机localStorage跨重启持久未点（无头靠代码+仿真代证，需人肉开页一次）；U-PM2 真实长路径/中文空格路径未另测（归一stripQuotes旧口径已 cover）；残留`/tmp/v2o-pathmem-*`交收尾；非git口径N/A以MD5+行数代证
- 结论：PASS（记忆小修全链：三键存/填/清空不崩+后端last_*回显+成功条上次监听+外置+零碰+坏例exit1；16项不重跑）

---
目标：路径记忆小修验收｜剩 P0：无（QA 口径 PASS；闭环以 supervisor 复检为准）｜下一步：交 supervisor 复检（HANDOFF 只记状态，不代写结论）。
