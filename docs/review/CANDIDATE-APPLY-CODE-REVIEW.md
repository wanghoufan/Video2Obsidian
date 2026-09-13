
# CODE REVIEW

- Task: 待审候选入库（GET /api/vocab/candidates、POST /api/vocab/candidates/apply 及 index.html 待审清单 block + 错词重跑键）
- Commit: 工作树未提交（HEAD 65cfe2c + dirty；本次只审 server.py 候选接口段与 index.html 候选 UI 段，formatter_v2.py/预置词库/HANDOFF 等同期改动不在本轮范围）
- Reviewer: code-reviewer
- Result: 过（PASS，无 P0/P1；硬门全过，遗留 1×P2 + 5×P3 进 backlog）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## 硬门逐项（任一命中即 FAIL，本轮全过）

- 未动 src 冻结文件：候选 diff 只碰 `app/server.py`（+约211行，`_vocab_base_patterns/_vocab_candidates_path/_load_vocab_candidates/_candidate_confidence/_candidate_view/_handle_vocab_candidates_get/_candidate_detail/_handle_vocab_candidates_apply` + do_GET/do_POST 各一处注册）与 `app/index.html`（candidateBox 样式 + block + `loadVocabCandidates/syncCandidateSelectAll/applyVocabCandidates` + refresh 挂载）。对 `stage9.rules_v2/stage3.normalize` 均为函数内只读复用（内存读表/内存注册），无写 src 路径。server.py 内另有 5 处 para-v2.6→v2.7 注释行同步，无行为变更。
- 无非 stdlib 依赖：顶层 import 无新增（json/os/sqlite3 等原有）；新增函数内 import 仅 `stage9.rules_v2`、`stage3.normalize`（项目内）、`hashlib`（经 `_user_rules_revision` 间接）、`string`（`_validate_vocab_pair` 原有）。`python3 -c ast.parse` 过。
- 未绕过校验链：apply 逐条调 `_validate_vocab_pair(wrong, right, existing, base_patterns)`（签名一致，server.py:1683），`existing` 随已入库 + 本批已接受递增，防本批内重复；入库后调 `_register_user_rules(entries)`（server.py:1734），失败回滚文件到 `entries_before` 并回 400/500。容量门 `len(entries)+len(accepted) >= 500` 无 off-by-one（499+0 放行 1 条，499+1 拒）。
- apply 失败不明示问题不存在：save 失败回 500「词库保存失败，未生效…」；register 失败回滚 + 回 400/500「词库注册失败，已回滚未生效…」；重跑失败走 200 + `ok:false` + 「词已入库，但重跑失败，请检查失败明细后重试」，`reapply` 原 payload 与 `summary{success,skipped,failed}` 同回。前端 `x.code===200&&o.ok?"vhint ok":"vhint err"`（index.html apply 回调），失败标红非静默。
- No-Clobber 未破坏：重跑复用 `_handle_reapply_post({all:true})` → `_reapply_one`，CONFLICT 照旧跳过（server.py:3878/3898 `skipped_user_edited`），apply 计数把 `skipped/skipped_user_edited` 与失败分开。whisper 0 转写（Case4 同入口）未变。
- 测试/真实目录：本轮 diff 无新增测试，无写用户真实目录/Obsidian 库动作；`_save_vocab_entries` 原子写仅 data_root 下（tmp+rename）；`_vocab_candidates_path` 文件名常量拼接，无用户可控路径。
- 明文密钥：无（grep api_key/secret/token/password 在 server.py 无命中）。

## 要求点逐项证据

- 路由注册在先例位置：GET `/api/vocab/candidates` 紧跟 `/api/vocab` 之后、`presets` 之前（server.py:4060）；POST `/api/vocab/candidates/apply` 紧跟 `/api/vocab` 之后、`delete` 之前（server.py:4104）。未知路径 404 与外层 500 接管不受影响。
- 空候选文件 fail-open 人话：缺失/损坏/非数组一律回空清单（`_load_vocab_candidates` 捕 OSError/ValueError/UnicodeDecodeError），GET 回 `has_candidates:false + source_exists`；前端空态「暂无待审候选（未找到 vocab-candidates.json 时不会报错）」，按钮置灰。符合要求。
- indices 越界/重复/空数组：非数组 400；单条非法 int→逐条拒收（reason 人话）；重复下标拒收；越界拒收；`[]` 与全拒收走 `imported=0` 早回「没有候选通过校验，未导入；未执行重跑」，不触发无意义重跑。全对。
- 前端默认勾选高+中、键置灰：`level!=="low"?'checked':''` 且 details 仅高/中展开；`btnCandidateApply` 初始 disabled，空/失败态置灰、有候选才启用；apply 中禁用防连点，catch 重开；`candidateSelectAll` 双向同步。`esc()` 包裹 wrong/right/evidence/index 输出。`reapplyPayload({indices})` 携带 data_root/vault，与重跑入口一致；confirm 文案「转写0次，原文不动」与 Case4 语义一致。

## P0 / P1 Findings

- 无。

## P2 / P3 Backlog Findings

- P2-1 候选文件永不消费：apply 成功后不清空/不标记已导入项，清单与词库状态脱节；重复提交后果仅是整批拒收且不重跑（无破坏），但用户会困惑「明明入库了还在清单里」。建议：apply 成功后把已接受项从 `vocab-candidates.json` 移除或加 `imported:true` 标记（原子写，失败不碰）。[neat-freak 09-13对齐注：本P2已返工修复——QA报告已验「接受项标记imported:true且GET不再返回」，剩5×P3为backlog。]
- P3-1 `int(raw_index)` 过宽松：`True→1`、`1.5→1` 截断通过。建议严格 `isinstance(int) 且非 bool`，其余一律「候选索引无效」。
- P3-2 failed 口径与 `_handle_reapply_post` 自带 summary 不一致：apply 自算排除 skipped，后者 `failed=not ok` 把 skipped 也计入；仅无 results 的 fallback 分支用后者。建议统一口径（以 apply 口径为准）。
- P3-3 零目标重跑文案：词库有导入但无可重跑任务时报「已导入N条；重跑成功0篇，跳过0篇」且 `ok:true`。可接受，建议区分「无可重跑的已完成任务」。
- P3-4 腐坏文件与缺失同显「暂无」：后端已回 `source_exists`，前端未使用。建议 `source_exists && !has_candidates` 时给 warn 级提示（文件损坏请检查）。
- P3-5 GET/POST 间候选文件变化下标错位：枚举下标是快照，并发改文件会串项；现有 `details` 回显 wrong→right 兜底可接受。远期可加文件哈希乐观锁，非本轮。
