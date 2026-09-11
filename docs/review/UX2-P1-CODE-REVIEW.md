
# CODE REVIEW｜UX2-P1-2~P1-8（builder codebuddy通道）

- Task: UX2-P1-2~P1-8（批量重试+复制原因／入库受阻单主按钮／预览用户编辑状态行／停后目录归属／停止三段式／来源列去哈希／进度条红绿灰分段）
- Commit: b22c464 + 未提交工作区（`app/index.html 43dc184..4da1d77`／`app/server.py 7b77bc9..c8f3837`；index.html 71838B／server.py 163552B）
- Reviewer: code-reviewer（真源 override code-reviewer 行）
- Result: 过（无 P0；P1 转 QA 实测兜底，不拦 QA）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## 验收逐条对照（口径取 `docs/review/UX-REVIEW-2.md:50-83`）

- P1-2 批量重试+复制原因：过。`app/index.html:486-533` 失败>1 给“重试全部失败（N个）”、>0 给“复制全部失败原因”；`983-1025` 逐个调已有 `/api/retry` 幂等＋“i/total 已排队”进度，`failPartsForRun:395-402` 拆 文件名＋原因＋下一步。见 P1-⑴⑵。
- P1-3 入库受阻单主按钮：过。行内 `542-556` 只留一主按钮（BLOCKED→“重试入库” else“重试”，已删行内重跑）；详情 `642-658` 失败只留一主按钮＋重跑收进 `<details>高级：应用新词库重跑`。行内搜“重跑”零命中。见 P1-⑴。
- P1-4 预览用户编辑状态行：条件过。前端 `697-705,713-721` 按 `note_hint/user_edited` 给黄条／灰字只读；后端 `app/server.py:3144-3264` 只读 manifest 判定不落盘。live 缺口见 P1-⑶。
- P1-5 停后目录归属：过。每行 `562` 经 `sourceLabelForRun:412-418` 给“尾段＋文件名”；未监听或多目录时头 `513-522` 按 input 分组 成功／失败／排队。兜底缺口见 P1-⑷。
- P1-6 停止三段式：过。后端 `2742-2788` 不清 current＋回 `{finishing,current,message}` 文案含三段（已停接新／当前跑完收尾／重起跳过＋半截重转）；前端 `790-820,852-856,1277-1292` 收尾中显“正在收尾…”＋禁重起，不立即误导“未监听”。刷新缺口见 P1-⑸。
- P1-7 来源列去哈希：过。列表 `562`＋详情 `614` 均改显人话标签、哈希只进 `title`；全文件 `esc(r.source_id` 仅剩 2 处 title。任务列 `560` 的 `…shortId` 系 run_id 片段非 source_id，口径内可过。
- P1-8 进度条红绿灰分段：过。`110-112,197,741-786` 绿成功／红失败／灰排队三段＋文案“成功A/失败B/排队C，共N”，收口明示“已收口（含失败B）／（全部成功）”，失败不再计成功。口径分裂见 P1-⑹。

## P0 / P1 Findings

- P0：无（无崩溃／无数据误删／无 secrets／`src/` 零碰见下）。
- P1-⑴ 申报与落地不符（过程）：任务称“只改 app/index.html，后端复用已有”，实测 `app/index.html 367行＋app/server.py 518行新增` 双改；server 含 P1 后端（`_dir_tail/source_dir_tail:766-808`／`_scoped_runs_summary groups:1448-1513`／`_handle_stop finishing/message:2781-2788`／`_note_user_edited/note_hint:3144-3214` 标 UX2-P1-4/5/6/7）。功能成立，但 HANDOFF／账本须正名为双文件＋新增契约清单，不可用“复用已有”误导 QA。
- P1-⑵ BLOCKED 无 detail 盲区（P1-2/P1-3）：`isFailedRun:389-393` 与行级 `546-549` 仅 detail 有 state 才认 BLOCKED，无 detail 回落只查 `FAILED/NO_SPEECH`，重启后 BLOCKED 行变“—”、批量漏数；而头计数后端已按 disk `FAIL_STATES` 含 BLOCKED（`1488-1500`），头行分裂。改法：无 detail 时以后端 disk／`/api/note` 兜底，或 recent_runs 附 disk_state；QA 加测“重启后 BLOCKED 行仍有一键重试”。
- P1-⑶ P1-4 非 live（预览即见不满足）：`_note_user_edited:3156-3165` 只看 manifest receipts 的 `BLOCKED_OUTPUT_CONFLICT`／verdict 关键词，手改 vault md 未重跑前无痕则仍回“库内未改”（`3208-3210`），黄条不现。spec“复用 BLOCKED 判定”字面做到，但 qa“手写改即见黄条”需活检。改法：加 vault 活检（canonical vs 库内同名文件 hash/mtime/size，fail-open）或书面降级 qa 前置“需先重跑一次留痕”；QA 必测手改未重跑即预览。
- P1-⑷ 每行归属无兜底（P1-5）：`sourceLabelForRun:412-418` tail 空回纯文件名，映射缺失行无归属；groups 侧已有“（无归属目录）”兜底（server `1503-1504`）。改法：tail 空回“（无归属目录）/”＋fn。
- P1-⑸ 刷新丢收尾态（P1-6）：`finishing:797` 依赖内存 `stopState.finishing`，刷新丢后 `!running && curNow` 仍显“未监听”，与后端不清 current 真相矛盾。改法：改纯后端推导（`!running && curNow` 即收尾）或 `/status` 附 finishing／sessionStorage 持久 stopState；QA 加测转中点停后刷新。
- P1-⑹ 进度与头口径分裂（P1-8）：进度用 `w.queue:735-749`，头用 `run_summary`（DB＋disk）；重启 queue 清零进度回“空闲”，头仍“共N／失败B”。不重启可过，重启即分裂。改法：无 current 且 queue 全零时回落 summary，或注释双口径；QA 加测重启后收口条。
- P1-⑺ 停后全重试需监听前置（P1-2）：`_handle_retry_post:2806-2807` 未监听 400，`retryAllFailed` 不预检 running，停后全点全 badN。单行同约束字面合规。改法：全重试前若 `!lastLock.running` 先提示“先开始监听再全重试”并禁按钮；QA 测停后点全重试。

## P2 / P3 Backlog Findings

- P2 行内 `data-reapply` 死绑定：`580-584` 仍绑 `[data-reapply]` 但行已无该按钮（仅详情 `667-669` 有），无害，建议清掉。
- P2 文案小分裂：行失败叫“重试”、详情叫“重试这个视频”（`554` vs `643`），BLOCKED 统一“重试入库”良好，建议统一为“重试这个视频”。
- P2 `copyText` 用 `execCommand('copy')` 兜底可用，现代 Clipboard API 失败时才走，可留。
- P3 本次不评 UX2-P0-1/P0-2 遗留（limit=200、clearModal 代价预览）与 P2-3 default_data_root。

## 合规核

- `src/` 零碰：`git diff --stat -- src/` 空。
- secrets：`git diff | grep -iE 'sk-|api[_-]?key|token|secret|password'` 仅命中模型名／注释人话，无实物。
- 治理：`AGENTS.md`／`docs/roles/` 零改；根 `USER_MODEL_OVERRIDE.md` 改动与真源包不同文（缺-y半句，且HEAD为作废声明、工作区旧表覆盖作废，已记HANDOFF未决待TM定夺是否恢复作废），非 P1 业务改，不记 builder 违规；`docs/review/UX2-P1-CODE-REVIEW.md` 为本角色唯一落盘。
