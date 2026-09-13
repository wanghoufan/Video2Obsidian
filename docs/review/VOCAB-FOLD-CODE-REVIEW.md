
# CODE REVIEW

- Task: VOCAB-FOLD（已导入词库列表改折叠：整块details默认收起+组头条数；展开后按来源四组折叠；删除保留且计数实时更新；过滤输入框实时筛错词/正词；待审空态文案）
- Commit: 工作树未提交（HEAD 65cfe2c + dirty；本轮只审 app/index.html VOCAB-FOLD段约+46/-7，server.py本轮未动，src/stage9与预置json等同期dirty系之前para-v2.7/UI2轮次，不在本轮范围）
- Reviewer: code-reviewer
- Result: 过（PASS，无 P0/P1；硬门全过；遗留 4×P3 进 backlog，不阻塞）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## 硬门逐项（任一命中即 FAIL，本轮全过）

- 未动 src：本轮增量纯前端 `app/index.html`（`#vocabListDetails/#vocabFilter/.vocabGroup` 样式 + `loadedVocabEntries/vocabGroupLabels/vocabGroupFor/renderVocabList/loadVocab` 改写 + `vocabFilter.oninput` + 待审空态一行）。无 `src/` 改动需求；`git diff HEAD --name-only` 含 `src/stage9/formatter_v2.py` 系之前 para-v2.7 轮次，不计本轮 FAIL。
- 无非 stdlib：本轮零 Python 改动，无新增 import；`python3 -c ast.parse(app/server.py)` 过（server.py 本轮未动，仅作只读证据引用）。
- 未破删除链路：`renderVocabList` 每次 `innerHTML` 重建后重绑 `[data-vocdel]` → `delVocab(wrong)`（index.html:1117-1120），`delVocab` 仍走 `POST /api/vocab/delete` + 成功后 `loadVocab()` 重拉重渲（index.html:1202-1211）。删除按钮输出经 `esc()` 包裹（`esc` 转义 `&<>"`，属性用双引号包裹，`getAttribute` 回解正确，index.html:330/1112）。
- 无计数造假：总条数用未过滤全量 `loadedVocabEntries.length`（index.html:1105），组头用过滤后 `items.length`（index.html:1109），头顶 `vocRev` 用后端 `o.count`（index.html:1127 ↔ server.py:1925）。删除/导入后走 `loadVocab()` 重拉，后端 `count=len(entries)`（server.py:1925/2307），两端一致，无前端硬编码数。
- 未写真实库：本轮无新增写接口/文件操作；仅复用已有 GET `/api/vocab` 与 POST `/api/vocab/delete`，`data_root` 经既有 `reapplyPayload` 携带，无用户可控路径拼接。
- 无密钥：`git diff HEAD -- app/index.html | grep -iE "api_key|secret|token|password"` 无命中（仅 data_root/vault 既有字段）。

## 要求点逐项证据

- 整块默认收起+组头条数：`<details id="vocabListDetails">` 无 `open`（index.html:235），`summary#vocabListSummary` 初始“已导入词库（0条）”，`renderVocabList` 每次更新为全量条数（index.html:236/1105）。
- 四组折叠：`programming/crypto/finance/user` 四 `<details class="vocabGroup">` 无 `open`（index.html:1107-1116），组头 `vocabGroupLabels[group]+（items.length条）`（index.html:1089/1109）。
- 删除保留且计数实时更新：行内 `删除` 按钮保留（index.html:1112），删后 `loadVocab→renderVocabList` 同时刷新总条数/组头数/后端 `vocRev`（index.html:1128-1129/1127）。
- 过滤实时筛错词/正词：`<input id="vocabFilter" type="search" placeholder="筛选错词或正词（空即显示全部）">`（index.html:237），`oninput=renderVocabList`（index.html:1265），`filter=trim().toLowerCase()` + `hay=wrong+" "+right` 大小写不敏感含入（index.html:1098/1101-1102）。
- 待审空态文案：`!o.has_candidates` 分支新文案“暂无待审候选，去跑一次AI审查生成清单（找编排者要提示词）”+ 置灰控件 + `all.checked=false`（index.html:1146），失败态仍为红字“读取失败，请刷新后重试”未动（index.html:1145/1164）。

## 另看三项（用户指定）

- 无来源标记条目归类：`vocabGroupFor` 对 `null/undefined/""` 经 `String((entry&&entry.source)||"")` 落到 `""` → 归 `user`（index.html:1090-1095），行内回显 `esc(e.source||"user")`（index.html:1112）；后端 `_load` 缺 source 回落 `"user"`（server.py:1669-1672）、`_save` 回落（server.py:1685-1686）。无丢失、无 crash，归类合理。遗留见 P3-1/P3-2。
- 无候选时组逻辑：指空词库/过滤零命中时四组各显“暂无匹配词条”（index.html:1110），`summary` 仍显示总数/组头显示 0，四组结构不塌；候选空态走独立分支（index.html:1146），与词库分组互不干扰。行为正确，noise 见 P3-3。
- 过滤空值行为：空串/`null`/纯空格均 `trim()` 后为 `""` → `if(filter&&...)` 短路显示全部（index.html:1098/1102），与 placeholder“空即显示全部”一致；`wrong/right` 缺失经 `String(...||"")` 防 crash（index.html:1101）。正确。

## P0 / P1 Findings

- 无。

## P2 / P3 Backlog Findings

- P3-1 组名与行内来源不一致（candidate）：`_handle_vocab_candidates_apply` 落盘 `source:"candidate"`（server.py:2083-2084），前端无 candidate 分支，一律归“我自己加的”（index.html:1090-1095），行内却显示“来源：candidate”。任务明确四组，当前行为可接受。建议：维持四组，仅把 user 组标签改为“我自己加的/候选导入”或行内 candidate 显示为“候选导入”，纯展示，不改行为。
- P3-2 `vocabGroupFor` 未 `trim`：仅 `toLowerCase` 未去前后空格（index.html:1091），`" programming "` 会误归 user。后端入库已 `strip`（server.py:1670/2235），实际命中率极低。建议加 `.trim()`，一行。
- P3-3 空库 noise：0 条时四组各一句“暂无匹配词条”（index.html:1110）。建议空库（`loadedVocabEntries.length===0`）时整块只显一句（如“暂无自定义词…”旧文案），过滤零命中才按组显示，纯 polish。
- P3-4 总数/过滤数双口径可读性：过滤中 `summary` 仍是总数、组头是过滤数（index.html:1105/1109），符合要求但首见易误读。建议过滤非空时 summary 追加“（匹配X条）”，纯展示，不改逻辑。
