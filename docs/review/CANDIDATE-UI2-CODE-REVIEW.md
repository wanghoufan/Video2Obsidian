
# CODE REVIEW

- Task: UI2增量（待审三组折叠 + rerun_old二选一 + 预置域只读查看/启用开关；server.py与index.html今日新增部分，src冻结与之前会话改动不在范围）
- Commit: 工作树未提交（HEAD 65cfe2c + dirty；本轮只审 server.py UI2段与 index.html UI2段，src/stage9/formatter_v2.py与预置json/自验/HANDOFF同期改动不在范围）
- Reviewer: code-reviewer
- Result: 过（PASS，无 P0/P1；硬门全过，互斥可接受；遗留 1×P2 + 5×P3 进 backlog）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## 硬门逐项（任一命中即 FAIL，本轮全过）

- 未动 src：UI2 diff 只碰 `app/server.py`（域状态/候选rerun_old/预置GET扩展/domains开关/source标记）与 `app/index.html`（candidate三组/双范围框/预置查看+启用）；对 `stage9.rules_v2/stage3.normalize/formatter_v2` 均为函数内只读复用（内存读表/内存注册/profile纯函数），无写 src 路径。`git diff --name-only` 含 `src/stage9/formatter_v2.py` 系之前会话 para-v2.7 改动，不在本轮范围，不计 FAIL。
- 无非 stdlib：顶层 import 无新增（json/os/shutil/sqlite3/sys/tempfile/threading/urllib/http.server）；diff 新增 `import` 仅函数内 `from stage9/stage3`（项目内只读）与 inline `string/hashlib/json`（stdlib）。`python3 -c ast.parse` 过。
- 未绕校验：候选 apply 逐条 `_validate_vocab_pair(wrong,right,existing,base)`（server.py:2069）+ 入库后 `_register_user_rules(entries)` 失败回滚到 `entries_before`（server.py:2091-2109）；预置导入同链（server.py:2449/2468）；容量门 `>=500` 无 off-by-one；`existing` 随本批已接受递增，防批内重复。
- 无失败静默：save 失败 500「词库保存失败，未生效…」；register 失败回滚+400/500「已回滚未生效…」；零导入早回「没有候选通过校验，未导入；未执行重跑」不重跑；`rerun_old=false` 回 `reapply:null + summary zeros + codesummary…；老稿未动 + message已导入N条；未重跑老稿`；重跑失败 200+`ok:false`+「词已入库，但重跑失败…」；domains 缺 enabled 400、写失败 500。前端按 `x.code===200&&o.ok` 标红/标绿。
- 未破 No-Clobber：`rerun_old=true` 复用 `_handle_reapply_post({all:true,+vault透传})` → `_reapply_one`（whisper0/Raw不变/CONFLICT跳过原样）；`false` 分支不调重跑；域开关只影响 `_norm_profile_for_new_jobs/_user_prompt_terms`（均走 `_active_vocab_entries`），老稿不动，人话「停用域只影响新转写，老稿需重跑」一致。
- 未写真实库：三处写全在 data_root 下原子写（vocab-user.json / vocab-candidates.json标记 / vocab-domains.json，tmp+rename+finally清tmp）；无 vault/src/真实目录写；候选/域路径均为常量文件名拼接，无用户可控路径。
- 无密钥：`git diff HEAD -- app/server.py app/index.html | grep -iE "api_key|secret|token|password"` 无命中。

## 要求点逐项证据

- 三组折叠：`loadVocabCandidates` 按 high/medium/low 分三 `<details class="candGroup">`（index.html:1110-1119），`level!=="low"?'open':''` 默认展开高中收起低，`level!=="low"?'checked':''` 默认勾高中；组头 `<input data-candidate-group>` 切组内全选（index.html:1122-1125），`syncCandidateSelectAll` 双向回写全选+组头（index.html:1128-1131）；evidence 折叠、`esc()` 包裹输出、空/失败置灰禁用（index.html:1107-1108/1126）符合。
- rerun_old二选一：`params.get("rerun_old",True) is True`（server.py:2031）缺字段→True 全量重跑兼容旧行为；`true` 走 `reapply_params={data_root,all:True,+vault_s透传}`（server.py:2134-2139）+ success/skipped/failed 自算 + `codesummary`；`false` 早回 `rerun_old:False/reapply:None/message老稿未动`（server.py:2121-2133）不调重跑。前端 `candidateRerunOld.checked` 直传布尔（index.html:1135/1138），confirm/进行中/结果文案双分支（index.html:1136-1137）。
- 预置只读+开关：GET 回 `enabled + entries全量`（server.py:2364-2376）只读预置文件不改；POST `/api/vocab/presets/domains` 白名单 `known` 域全量保存原子写（server.py:2379-2400），停用人话「停用域只影响新转写，老稿需重跑」；`_load/_save` 兼容缺失/损坏 fail-open 全启用；`_active_vocab_entries` 用户/候选源恒保留、仅预置域按开关过滤（server.py:1806-1813），新转写与重跑（server.py:1820/1904/3926）均走 active；`source` 落盘/回显（server.py:1669-1672/1685-1686/2077-2078/2225/2456，index.html:1086），`_user_rules_revision` 仅 `(wrong,right)` 排序哈希（server.py:1738）来源不影响哈希，实测 user/programming 同对同 revision。
- 互斥判断（另判项）：双框互斥可接受。入库恒对新视频生效（`_norm_profile_for_new_jobs` + `_user_prompt_terms` 均走 active），语义上双勾≡只勾已跑过；前端互斥（index.html:1148-1149）把后端状态收敛到单布尔 `rerun_old`，消除歧义；默认 `OnlyNew checked / RerunOld unchecked` 即安全默认只入库，防误全量重跑；双空边角仍按 false 只入库，无丢数无误重跑，仅展示歧义（P3-2）。

## P0 / P1 Findings

- 无。

## P2 / P3 Backlog Findings

- P2-1 展示 revision 与生效 revision 不一致：`_handle_vocab_get/_handle_vocab_add/_handle_vocab_del/_handle_vocab_candidates_apply/_handle_vocab_presets_import` 均按全量 entries 算 revision（server.py:1921/2266/2296/2093/2475），而新转写/重跑按 active 算（server.py:1820/3926）。停用一域后 UI revision 不变但实际新生效变（实测 full 7b8625df vs active 084d442f）。建议：GET/add/del/apply/import 同回 `revision（全量）+ effective_revision（active）` 或注明，不改行为只补字段。[neat-freak 09-13对齐注：本P2已返工修复——QA报告已验「停用后effective_revision变化、用户词条保留」，剩5×P3为backlog。]
- P3-1 `rerun_old` 严格同一性：`is True` 仅 exact-True 重跑，`1/"true"/1.0` 一律按 false 只入库，而缺字段按 true 重跑，非对称。前端恒传布尔无影响。建议注释写明或改 `bool()` 前先判 `is True/False` 非布尔 400。
- P3-2 双框可双空：两 `onchange` 仅 checked 时互斥（index.html:1148-1149），逐一取消可得双空，语义≡只入库但展示无范围。建议 apply 前若双空默认勾回 OnlyNew 或直接按 false 人话已足够，纯展示 polish。
- P3-3 组头 checkbox 在 `<summary>` 内：点组头勾选会同时冒泡开关 details（浏览器默认），勾选中低组易顺手收起。建议 `onclick="event.stopPropagation()"` 或把组 checkbox 移出 summary，功能不动。
- P3-4 全选初始不同步：有候选加载后 `all.checked=false`（index.html:1120）而高中默认已勾，全选显示未选。建议加载后调一次 `syncCandidateSelectAll()`。
- P3-5 domains 部分 POST 会回启未提及域：`{domain:bool(raw.get(domain,True)) for domain in known}`（server.py:2392）缺键默认 True；前端恒发全量无事，纯 API 直调 pitfall。建议缺键沿用旧状态而非 True，未知键忽略已对。
