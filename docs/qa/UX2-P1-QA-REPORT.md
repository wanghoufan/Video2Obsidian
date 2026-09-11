# BUGS｜UX2-P1 运行期验收 P1-2~P1-8（2026-09-11）

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| UX2-P1-2 批量重试幂等（一键全重试＋复制全部失败原因） | P1 | 否 | /tmp合成态直调_handle_retry_post＋前端静态（禁8765/禁真实目录） | PASS | 运行期验收通过 | 已完成run重调202重排队、二次同run202已在排队不翻倍；坏例空体/坏JSON/缺run_id/未监听均400只看码；前端retryAllFailed逐个调/api/retry＋i/total已排队，nRetry>1才给按钮 |
| UX2-P1-3 单主按钮文案（行只留一主，重跑进详情高级） | P1 | 否 | 前端行模板计数＋后端REAPPLY口径对照 | PASS | 运行期验收通过 | 行模板data-retry恰1、无data-reapply、无>重跑<按钮；PUBLISH_BLOCKED行主按钮=重试入库；详情advDetail=应用新词库重跑；去注释后行内重试/重跑不并列 |
| UX2-P1-4 预览黄条/灰字（库内改过跳过只读判定） | P1 | 否 | /tmp合成jobs manifest＋_handle_note内存注入E2E | PASS | 运行期验收通过 | 改过manifest判True/未改False/缺文件False；只读不落盘；E2E黄条=库内你改过…跳过不覆盖、灰字=库内未改…会更新；前端notestatus.warn＋⚠＋o.user_edited |
| UX2-P1-5 停后分组（行行有归属＋按input分组头） | P1 | 否 | _dir_tail/_is_under_root/_attach合成＋前端分组静态 | PASS | 运行期验收通过 | 尾段…/待转写A、尾斜杠归一、空串；siblings前缀不串（A vs A_X）；attach补source_dir_tail/source_dir/未知文件；前端sourceLabelForRun＋按文件夹：rs.groups |
| UX2-P1-6 停止语义（三段式＋先收尾再切未监听） | P1 | 否 | 直调_handle_stop_post无/有current＋前端锁态静态 | PASS | 运行期验收通过 | 无current文案含已停止接新任务/重起后已完成跳过/半截重转且finishing假；有current含文件名＋会跑完收尾且finishing真；二次停止200幂等；前端正在收尾…＋stopState.message常驻＋收尾锁btn |
| UX2-P1-7 来源列无裸哈希（尾段＋文件名，哈希只进title） | P1 | 否 | 前端单元格/title正则＋_run_source_path_map fail-open | PASS | 运行期验收通过 | 来源列esc(sourceLabelForRun(r))；无裸source_id单元格；td侧零32位hex；哈希只进title=esc(r.source_id)；不存在库回{} |
| UX2-P1-8 进度条分段与100%口径（绿/红/灰＋收口明示） | P1 | 否 | 前端progFill三段＋收口分支静态 | PASS | 运行期验收通过 | progFillOk/Fail/Pending三段，旧progFill移除；文案成功A/失败B/排队C共N；排队0才收口，失败>0明示已收口（含失败B）；done/failed分别算宽，旧单绿pct公式无残留 |
| UX2-P1-QA-SCRIPT 初版2断言过严误报 | P1 | 否（QA自检口径） | python3 /tmp/ux2_p1_qa_independent.py 首跑66中2FAIL | CLOSED | 口径修正后全绿 | P1-3把JS注释计入行文案、P1-8把total兜底加和误判旧公式；去注释/收紧旧pct模式后66/0；业务零改，只改/tmp脚本 |

## Fix Attempt Fingerprint

- Task ID: UX2-P1-QA-2026-09-11
- Root Cause Hypothesis: 无业务Bug假设（验收任务）。首跑2 FAIL经核查为QA脚本断言过严：①P1-3行模板含“// 重跑收进详情…”注释， naive同时含重试/重跑即判并列；②P1-8把`total=pending+done+failed`兜底加和误判为旧`(done+failed)/total`单绿公式。去注释＋收紧旧公式模式（`(done+failed)*100|/total|pct=(done+failed)`）后全过，业务码无辜。
- Approach: 只用外置/tmp＋合成，直调函数（禁碰用户真实目录与OB库、禁碰8765服务、不起服务）；先`python3 -m py_compile app/server.py`，再跑builder脚本`python3 /tmp/ux2_p1_selftest.py`看exit码，另写`/tmp/ux2_p1_qa_independent.py`独立验证（保存/恢复_listener/_worker/_worker_done现场；坏例只看状态码；合成jobs/manifest/md全在mkdtemp用后rmtree）。
- Files Changed: 无（QA不改业务代码；仓内只写本报告。/tmp两脚本为外置验证 artifact：`/tmp/ux2_p1_selftest.py`为builder自验，`/tmp/ux2_p1_qa_independent.py`为QA独立脚本，`/tmp/ux2p1qa_*`合成目录已清）。
- Verification:
  - `python3 -m py_compile app/server.py` → EXIT=0 PASS。
  - `python3 /tmp/ux2_p1_selftest.py` → PASS 34 / FAIL 0，SELFTEST ALL PASS EXIT=0（语法门1＋后端契约9＋前端静态24）。
  - `python3 /tmp/ux2_p1_qa_independent.py` 首跑 → PASS 64 / FAIL 2 EXIT=1（上记2误报）；修正2断言后重跑 → PASS 66 / FAIL 0，QA INDEPENDENT ALL PASS EXIT=0。
  - P1-2幂等（合成_listener running=True＋data_root=None跳DB）：runA在done集首调202/QUEUED已重新排队且done摘除不翻倍，二调202已在排队；坏例{}→400、坏JSON→400、空run_id→400、running=False拒→400。前端：`function retryAllFailed`逐个fetch /api/retry，`i+"/"+total+" 已排队"`，`if(nRetry>1)`给重试全部失败（N个），`>0`给复制全部失败原因（文件名＋归属＋原因＋下一步）。
  - P1-3：行模板`data-retry=`计数1、`data-reapply`零、`>重跑<`零；`mainLabel=PUBLISH_BLOCKED?"重试入库":"重试"`；详情`id="advDetail"`＋应用新词库重跑；去`//`注释后行内重试/重跑不并列。
  - P1-4：合成`data/jobs/run_edited/manifest(BLOCKED_OUTPUT_CONFLICT)`→True，clean→False，缺文件→False；调用前后jobs文件数不变只读；`_handle_note`源码含黄条/灰字两文案；前端`noteStatusHtml/note_hint/.notestatus.warn/o.user_edited/⚠`全在。另附E2E（内存注入PUBLISHED＋合成md，直调_handle_note）：改过回200/user_edited True/黄条文案且text非空，未改回灰字库内未改…会更新，EXIT=0。
  - P1-5：`_dir_tail("/a/b/待转写A")=…/待转写A`、尾斜杠归一、空串；`_is_under_root`同目录真、siblings（A vs A_X）假；`_attach_source_filenames`缺映射补source_dir_tail/source_dir/source_filename=未知文件；前端`sourceLabelForRun＋source_dir_tail`、`按文件夹：＋rs.groups`。
  - P1-6：current空停机200/finishing假/文案三段全（含已停止接新任务/重起后已完成跳过/半截重转）；current={run_long/长视频60s.mp4}停机finishing真/文案含文件名＋会跑完收尾/current回显；二次停止200幂等；现场已恢复。前端`正在收尾…`＋`stopState.message`常驻＋`lock warn`收尾锁＋停止键文案“正在停止（先停接新任务，当前任务会跑完收尾）…”。
  - P1-7：来源列`esc(sourceLabelForRun(r))`；`esc(r.source_id)`仅出现在`title="'+esc(r.source_id`，裸单元格正则零命中；td侧32位hex零命中；`_run_source_path_map(不存在路径)=={}` fail-open。
  - P1-8：`progFillOk/Fail/Pending`三段在，旧`progFill`无残留；文案`成功 "+done+"/失败 "+failed+"/排队 "+pending+"，共 "+total`；`if(pending===0)`收口分支，失败>0给`已收口（含失败`；`done*100/total`与`failed*100/total`分别算宽；旧单绿pct（`(done+failed)*100|/total|pct=`）零残留（`pending+done+failed`仅为total兜底加和，非旧公式）。
  - 坏例（只看码）：retry三坏例400＋未监听400、note缺run_id 400、`_note_user_edited`缺文件False、`_run_source_path_map`缺库{}。
  - 约束遵守：全程仅/tmp合成＋`os.path.realpath`只读判定；未读/未写用户真实视频目录与OB库；未curl/未起8765服务；git仓内除本报告无改动（/tmp脚本不进仓）。
- Failure Reason: 首跑2 FAIL系QA断言过严非业务缺陷（见上）；修正后66/0＋E2E EXIT=0；builder自验34/0始终全绿。
- Difference From Previous Attempt: 首轮UX2-P1运行期验收；此前仅UX2-P0-QA-REPORT（P0-1/P0-2 PASS＋harness返工CLOSED）。本轮七项一次过，无返工。
- Scope 注记（非阻塞）：按硬约束未做三类真机：①67条 synthesis DB全量（16失败一键全回排队以done集幂等＋前端循环等价覆盖）；②60s真切片转中点停止（以current有/无两态文案＋收尾锁等价覆盖，未跑whisper）；③手写改vault md端到端以合成manifest＋合成md E2E等价覆盖（`_handle_note`真过hint分支）。三者留product-reviewer真机抽查，不拦QA PASS。

## 未闭环（打回项）

- 无（UX2-P1-2~P1-8 七项均为PASS；QA脚本误报已CLOSED；业务零改无打回）。
