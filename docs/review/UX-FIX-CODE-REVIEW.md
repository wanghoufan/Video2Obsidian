# CODE REVIEW｜UX-FIX 返工复核（app/ V2.1 P1×2＋UX P0×6＋P1×8）

- Task: 复核 app/ 返工（V2.1 P1×2：except 补 FAIL 记录、queue 加 failed 三态；UX P0×6＋P1×8 按 docs/review/UX-REVIEW.md 验收口径）
- Commit: 无（非 git 工作区；基于 app/server.py 1142 行＋app/index.html 724 行＋app/start.sh 40 行现状复核；py_compile 通过）
- Reviewer: code-reviewer（opencode-go/glm-5.3-flash）
- Result: 打回＋改法（仅 1 处 P1 必补：PUBLISH_BLOCKED lineage 丢原因＋无重试；补完即过。V2.1 P1×2 与其余 P0/P1 均 PASS）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## P0 / P1 Findings

- P1（必补，打回唯一原因）：UX-P0-4 残留——PUBLISH_BLOCKED 在 lineage 走成功分支丢原因、无重试。`app/index.html:343-351` 把 `PUBLISH_BLOCKED` 与 `PUBLISHED/RENDER_ONLY` 同分支，只显通用结论“初稿已保留，入库未完成”＋输出路径，不显 `detailsByRun.verdict` 的原因/下一步（后端 `app/server.py:760,778-783` 明明给了带 `→` 的人话 verdict，如“笔记库不可写…”），也不给重试按钮。UX-REVIEW P0-4 现状明确含 PUBLISH_BLOCKED，验收要求“行级失败必显：人话原因＋下一步＋重试可点”。表格列有重试（`index.html:295-296` FAIL/PUBLISH_BLOCKED 均有重试，符合 P1-1），但点行进详情的用户看不到为什么。改法（二选一，最小）：① lineage 分支把 `PUBLISH_BLOCKED` 从 343 条件摘出，并入 352 的 FAIL 红块分支（`failbox`＋`→` 切分＋`重试这个视频`按钮；结论文案可用“初稿已保留，入库未完成”作 reason 前缀），输出行保留 `rendered_path` 可复制；② 或在 343 分支内追加红块原因＋重试按钮。qa 重放：造 vault 不可写 1 个，点行即见红块原因＋下一步＋重试可点，刷新后不丢。
- PASS（V2.1 P1×2）：except 补 FAIL——`app/server.py:869-882` 未知异常记 `{state:FAIL, verdict:…→点重试…}` 再进 done，不静默丢任务；SKIP 不进 done（`867-890`）；双重记账被 `details_by_run` 按 run_id 去重吸收，不翻倍。queue failed 三态——`_listener_snapshot:334-348,377-378` `queue={pending,done,failed,total}`，`total=pending+done+failed`，pending 排除 `merged.keys()`（FAIL 亦排除，不重复计），未监听时 `total=done+failed` 重起不归零；`_scan_disk_states:130-193` 磁盘终态映射 FAIL/PUBLISH_BLOCKED 并校验输出存在性。py_compile 通过，`normalize_path` 去引号、`→` verdict 11 处抽查全带下一步。
- PASS（UX-P0-1/2/3/5/6，P1-1/2/3/4/5/7/8）：P0-1 中文标签＋人话占位、vault 为空后果句（`index.html:138-158,304-306`）、data_root 折叠默认收起（`details.adv` 无 open），框面无 `input_root/ob_vault_root/Render`（JS 属性名 `o.input_root` 等仅存代码，属“变量名只留代码里”允许范围）；P0-2 常驻绿条＋`btnStart` 置灰“监听中…”＋`btnStop`（POST /api/stop，`server.py:992-1027`）＋409 黄字非红（`index.html:702` warn）＋运行中改输入黄条（`675-681`），`refresh()` 只写 `#msg` 不覆盖绿条；P0-3 lineage 四行（输出可复制＋人话结论＋`fmtDur` 耗时＋失败见 P0-4，`339-351`）＋runs“输出”列（`293-294` 打开位置/复制）＋vault 映射预览（`server.py:196-215`＋`index.html:452`），全文无“（worker）”裸露（命中仅 JS 状态机字符串，属代码内）；P0-5 人话五步＋心跳＋排队/成功/失败（`400`）、双层条＋“步骤进度非精确百分比”（`403-407`）、>60s 兜底（`402`），无“标准化/渲染”裸词；P0-6 前后端人话错误表（`server.py:429-472,950-972` 绝对路径/存在/目录/本地盘/权限全覆盖，mlx 缺失→一键启动指引＋前端复制命令 `706-708`）＋去引号回显（`624-627`），页面无 stage0bench/mlx_whisper/PRECHECK 裸词（`CODE_MLX_MISSING` 仅 JSON code 字段，前端不渲染）；P1-1 单 run 重试幂等（`_handle_retry_post:1030-1082` 同 run 去重、连点不重复）；P1-2 磁盘成功跳过＋计数不归零（`819-860`）；P1-3 空 vault 绿条追加＋RENDER_ONLY 路径可复制；P1-4 浏览计数＋空目录黄字＋样例（`server.py:218-244,454-472`＋`index.html:588-606`）；P1-5 长视频估算提示（>500MB 注明估算，`602,650-652`＋转写中“长视频分段中”）；P1-7 失焦即验＋红/绿＋开始高亮仍可点（`617-691`）；P1-8 中文状态映射（`statusCN:231-247`＋`cnOfState`），渲染层英文状态词零裸露（代码内除外）。

## P2 / P3 Backlog Findings

- P2：P1-6 toast 点行不跳转——`app/index.html:497-503` toast 点击仅关闭，未选中对应行；文案“点行查看”需用户手动找行。核心提醒（toast 3s＋成功/失败变色＋文件名＋Notification 首次申请 `505-513`）已齐，建议 toast onclick 改为 `selected=行号;renderRuns;renderLineage` 后再 dismiss，不改不卡。
- P2：`app/start.sh:13,23` 终端 WARN 裸抛 `stage0bench/mlx_whisper/PRECHECK_MLX_MISSING` 无人话下一步；页面/400 已人话，终端仅开发者可见。建议改人话一句“转写环境没就绪：用 ./app/start.sh 在自带环境重开后再点开始监听”，保留命令原样。
- P2：`app/server.py:1051-1052` `already_queued` 死变量；`_handle_retry_post` 重启后 FAIL（不在 `_worker_done` 但在磁盘 FAIL）走“已在排队”分支，worker 下轮会自动重跑，语义可接受但文案易误解；顺手清掉/注释即可。
- P3（范围外，仅记）：P2-2 支持格式行缺失（页内搜“支持 mp4/暂不支持”零命中，`index.html` 无格式白名单行）、P2-5 搜索框、P2-6 Finder 显示、P2-3 断网“刷新中”保持、P2-4 焦点陷阱，均不在本次 P0×6＋P1×8 范围，不卡收工。

---
目标：UX-FIX 返工复核｜剩 P0：无（P1×1 必补：PUBLISH_BLOCKED lineage 红块＋重试，补完即过）｜下一步：builder 补 P1 后交 qa 按 UX-REVIEW 口径重放（重点 P0-4 三类失败＋PUBLISH_BLOCKED），结论落 qa 报告。
