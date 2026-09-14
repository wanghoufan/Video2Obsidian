# CODE REVIEW

- Task: P0-2 差异化批量恢复闭环（FR-4/FR-5/FR-6/FR-7/FR-8，D-4/D-5/D-6/D-7/D-8/D-9/D-20/D-21）
- Commit: 工作树未提交（基线 d807483；`app/server.py` +778/−0，全为新增）
- Reviewer: code-reviewer（本窗口 subagent，直派）
- Result: PASS（可进 qa；附 1×P1 + 3×P2，不拦主线）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## P0 / P1 Findings

- P0（全部通过，不打回）：
  - P0-1 原样保留：`git diff --numstat` 为 `778 + / 0 −`，零删除行；P0-1 诊断段（`DIAGNOSIS_VERSION`、`_handle_failure_diagnosis` 等）只被复用、未被改写。符合"222 行原样保留"要求。
  - FR-5 dry-run：`POST /api/failures/retry-plan` 只读组装、无业务写入；token 为 `os.urandom(32)` 不可猜测、服务端仅存摘要；TTL=600s（`RECOVERY_TOKEN_TTL_SEC`）；过期/快照变化/跨目录/集合不一致/指纹漂移一律 409 且零执行；`confirm != True` 400。`summary` 用逐项 recompute + `assert` 自检（D-4）。
  - FR-6 job 真源：`data/<root>/data/recovery_jobs/<job_id>.json` 原子写（tmp+fsync+os.replace，tmp 名带 pid/随机/线程 id）；逐项落盘；汇总恒等于逐项 recompute；同 token 重放返回既有 job（`idempotent:true`，202），并发占位中返回 409 不建第二 job（D-6/D-9）。
  - INTERRUPTED 不续跑：`_recovery_job_read` 对半文件/非对象/非终态（RUNNING 遗留）一律标 `INTERRUPTED` + 不自动续跑文案，并尽力持久化（D-9）。
  - 16 条排除：`_recovery_plan_items` + `_recovery_gate_ok` 双层卡 `SOURCE_LOCATION_REVIEW`（保持可见、排除自动重试、逐项 NEEDS_HUMAN），`QP` 旧入口未见接入（D-8 语义）。
  - 三策略分发：RETRANSCRIBE/REUSE_DERIVED/PUBLISH_ONLY 三分支齐全；REUSE 复用过门 `_reapply_one` 同一 derive 入口、whisper 恒 0；PUBLISH 只调过门 `initial_publish`，目标已存在双保险只判不写、`canonical_writes != 0` 拦截、CONFLICT→NEEDS_HUMAN、缺 vault 不创建（D-7/D-21 语义）。
  - No-Clobber：源永不写；旧版本不覆盖不删除；DB 失败路径 `rollback`；job_id 白名单正则防路径穿越；data_root 非绝对路径 400。
  - 可编译：`python3 -m compileall -q app/server.py` = COMPILE_OK（只读校验，未启动服务、未碰真实目录）。
- P1-1（不拦 P0-2，交 qa 验证，建议记报告）：RETRANSCRIBE 为 fail-closed 短路实现（源不可读/空→FAILED；引擎缺失/源可读→NEEDS_HUMAN，whisper_calls 恒 0），批量通道内从不真正调用转写引擎。安全方向正确且如实记录不冒充成功，但 FR-4"D-5 三策略真执行"中的 RETRANSCRIBE 真转写路径仍无端到端证据。改法：qa 在 tmp 夹具中断言 RETRANSCRIBE 两路（坏源→FAILED/whisper=0；好源→NEEDS_HUMAN/whisper=0 且旧产物不动），真机转写留 P1-1（blocking）另验；本项不打回。

## P2 / P3 Backlog Findings

- P2-1（脱敏，D-12/D-22）：`_exec_publish_only` 异常分支直接拼 `"%s" % exc`（"状态库不可读""入库失败"），sqlite/OS 异常串可能夹带绝对路径。改法：落盘/日志保留原文，HTTP 回包改用固定人话短句 + 脱敏码。
- P2-2（token 派生口径）：FR-5/Data-API 字面为"排序后 data_root_digest+snapshot+run/fingerprint+strategy+server_nonce 派生 token"，实现为 `urandom` 随机 token + 服务端绑定存储（绑定靠存储的 plan 而非 token 自包含）。功能等效且不可猜测，但与字面派生公式不一致。改法：二选一——(a) Plan 注释注明"绑定由服务端摘要存储保证，token 本身为随机 nonce"；(b) qa 加一条"伪造 token/跨目录 token 必 409"用例即视为覆盖。
- P2-3（FR-8 计数）：job 终态恒含 `source_location_blocked: 0`（被排除项根本不进 job，计数器永不增长）。当前语义自洽（排除在 plan 层），但与 FR-8"逐条返回最终状态"字面有落差。改法：status 回包附 `excluded_source_location_review` 或在文档注明"该类只出现在 retry-plan excluded，不进 job results"；数值口径由 qa 断言锁定。

目标/剩 P0/下一步：目标 P0-2 复核收口 / 剩 P0-2→qa、P0-3 未开工 / 下一步 qa 独立复验 + supervisor 复检。

---
## SCAN-FIX复核（2026-09-14，code-reviewer追加，只读）
- 对象：builder 对 `app/server.py::_diag_alternate_paths` 有界重写；`git diff` 核对 + `python3 -m compileall -q app/server.py`=COMPILE_OK（只读，未启动服务）。
- 结论：**PASS**（可进 qa；无新增 P0）。
- 核对（FR-4只读 / D-3零副作用 / fail-closed）：
  - `followlinks=False`：有（`os.walk(root, followlinks=False)`，server.py:1239）。
  - 预算 2s/2000目录：有（`_DIAG_SCAN_TIME_BUDGET_S=2.0`、`_DIAG_SCAN_MAX_DIRS=2000`，超限 `return` 部分结果，不抛）。
  - 跳过云同步根与大目录：有（`_diag_skip_dir` 覆盖 `cloudstorage`/`mobile documents`/`com~apple~clouddocs`/`.sparsebundle`/`.photoslibrary`/`node_modules`/`.git` 等；另跳过 dot 目录、depth>4 剪枝）。
  - `/Volumes` 只扫顶层：有（`if root == "/Volumes": dirs[:] = []`，不递归进各卷）。
  - 超限停不停抛：有（dir/时间超限走 `return list(dict.fromkeys(found))`；内外层 `except OSError: continue` + 最外层 `except Exception: return` 部分结果；空 recorded 返回 `[]`，永不抛）。
  - 字段契约不变：有（调用点 `recorded_exists` 为真时不扫描；无 MATCH 时 `identity=UNKNOWN`、`alternate=None→alternate_path_redacted=UNKNOWN`，`_diagnosis_item` 其余 FR-1 字段未动；fail-closed 方向正确）。
- 意见：无打回项。提醒 qa 在 tmp 夹具中断言两点即可：(1) 超大根/深目录下诊断 2s 级返回且 `identity_match=UNKNOWN`；(2) 真实目录与 vault 写次数为 0（D-3）。
