
# CODE REVIEW

- Task: 轮询瘦身——refresh加参区分自动/手动，自动轮询不再调loadVocab/loadPresets/loadVocabCandidates
- Commit: 未提交工作区（`git status`见M；本轮hunk仅app/index.html内refresh三处，其余numstat 154/21多为既有未提交链遗留）
- Reviewer: code-reviewer（独立复核，未改代码）
- Result: 过（PASS；P0/P1零问题，P3建议2条不挡道）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## P0 / P1 Findings

- 无。本轮hunk经`git diff -- app/index.html`逐行核对（仅三处）：
  1. `function refresh()`→`function refresh(autoPoll){autoPoll=autoPoll===true;}`（index.html:1268-1269）；
  2. `loadVocab/loadPresets/loadVocabCandidates`三调用包进`if(!autoPoll){…}`（index.html:1290-1294），p1（/api/status+limit=200→renderTape/renderRuns）与p2（/api/start→renderLock）仍在if外常走（index.html:1281-1289），任务进度轮询本身未动；
  3. `btnRefresh.onclick refresh()`→`refresh(false)`（index.html:1353）；首屏`refresh(false)`+`setInterval(function(){refresh(true);},5000)`（index.html:1559）。
- 硬门逐项过：
  - 未动后端：`src/server.py`不存在（仅`app/server.py`存在）；`git diff --numstat`中`app/server.py 388/17`为既往收口链遗留（HANDOFF 15:30/16:30/17:10），本轮三hunk无一落server.py；
  - 手动刷新未破：手动/首屏/裸调`refresh()`（btnStart:1449、btnStop:1466、doClear:1542、reapplyAll）走`autoPoll=false`分支，仍全量拉词库三件套，与旧行为一致；
  - 增删后重载未破：addVocab成功→`loadVocab()`（1198）、delVocab成功→`loadVocab()`（1208）、savePresetDomains→`loadVocab()`（1239）、importPresets→`loadVocab()`（1257）、applyVocabCandidates→`loadVocab()+loadVocabCandidates()+refresh()`（1182）均原地未动；
  - 无真实库写、无密钥：diff内`grep -i "api[_-]?key|secret|token|password"`零命中；改动纯前端fetch wiring，无DB/文件写、无密钥字段。

## P2 / P3 Backlog Findings

- P3-1（可不改）：裸调`refresh()`四处（1449/1466/1542/reapplyAll内）语义=手动分支，每次附带三词库请求；高频操作后若觉多余可显式传参或保持现状（保持现状即旧行为，无回归）。
- P3-2（可不改）：自动轮询5s不再刷候选清单，候选勾选态最长 stale 到下次手动刷新；候选仅在AI审查/apply后变化，当前策略合理；若以后候选变为高频写，再考虑轻量版本号轮询。
