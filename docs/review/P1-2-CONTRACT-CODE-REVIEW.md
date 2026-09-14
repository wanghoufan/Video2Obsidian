# CODE REVIEW

- Task: DEVELOP-P1-2「任务身份与 API 契约加固」（严格类型层／data_root+job_id 绑定／字段一致／候选版本锁／部分更新安全／错误脱敏 D-12）
- Commit: **未提交**（工作树相对 HEAD `d7540d8`；`app/server.py` +547/−187、`app/index.html` +75/−11、新增 `tests/selftest_p1_2_contract.py` 998 行、`tests/selftest_p1_2_frontend.py` 284 行 —— 与 builder 自述**逐字一致**，已核）
- Reviewer: code-reviewer（`opencode/muse-spark-1.3-contributor-free`，本窗口 subagent 独立复核，与 builder 非同一审查上下文）
- Result: **PASS（带 P1×2 ＋ P2×7 ＋ P3×5；无 P0 阻断）**

> 复核口径：只读业务代码＋跑外置 tmp 合成数据自测；未改 `app/`、`tests/`、文档正文；未起 8765、未请求线上服务；用户真实视频目录与 Obsidian 库零写。
> 除复跑 builder 三套自测外，我方另写独立探针 `/tmp/p12_reviewer_probe.py`（191 项，其中 **171 项 PASS／2 项为「记录现象」的预期外行为／其余为修正后的真 PASS**），以及一个 HTTP 层探针（随机端口，非 8765）逐个打真路由。凡调 handler 的用例首行均断言 `data_root` 在系统 tmp 下。

---

## 一、逐条必查项证据

### 1. 严格类型层正确性 —— PASS

取参层定义在 `app/server.py:141-345`（`_MISSING:141`、`ParamError:149`、`_take_bool:172`、`_take_int:183`、`_take_int_list:235`、`_take_data_root:258`、`_query_int:297`、`_reject_duplicates:313`）。

| 用例（我方自造，非复跑 builder 断言） | 实测 |
|---|---|
| `_take_int(True/False)` | ParamError ✔（`server.py:192` 显式 `isinstance(value, bool)` 先判） |
| `_take_int(1.0 / 0.0 / "3" / "0" / None / [] / {} / (1,))` | 全 ParamError ✔ |
| `_take_bool(1 / 0 / "true" / "True" / "false" / 1.0 / None / [] / {})` | 全 ParamError ✔；`true/false` 正常取到 ✔ |
| `_take_int_list([true,0] / [0,true] / [1,0.0] / [1,"2"] / [null] / [[]] / [[1]] / [0,{}] / [nan])` | 全 ParamError ✔（`:248` 逐项排除 bool） |
| `_take_str_list([1] / [true] / [null] / [""] / ["  "] / [[]] / [{...}] / "abc")` | 全 ParamError ✔ |
| 上限：501 项 `run_ids` / 501 项 `indices` | 全 ParamError ✔（`:227`/`:246`） |
| `_reject_duplicates([1,1])`、`[true,1]`（bool==int 同值） | 全 ParamError ✔（`:318`） |
| `_body_json(b"[1]"/b"1"/b'"s"'/b"true"/b"null"/b"nope"/b"\xff\xfe")` | 全 ParamError ✔；空体 → `{}` ✔（`:161`） |

**重复键（同一 JSON 里两次）**：**无法拒收**——`json.loads` 天然 last-wins，实测 `{"confirm": false, "confirm": true}` → `{"confirm": True}`，且该请求**会真的执行**。这不是 builder 自述的承诺（builder 的 `_reject_duplicates` 指的是**数组内重复项**，已正确实现），也不在 P1-2 五条范围里，但属请求契约层的已知歧义 → 记 **P3-1**。

**端到端 400 且零执行零写盘**（真 handler，tmp 合成 data_root）：
- `/api/vocab/candidates/apply`：`indices:[true,0]`、`[0,"1"]`、`[0.5]`、`[null]`、`rerun_old:"true"`、`rerun_old:1`、`rerun_old:{}`、`candidates_revision:123`、`ob_vault_root:[]` → **全部 400**，且目录字节快照前后一致、`vocab-user.json` 未生成、`_vocab_apply_job` 未被触碰、`vocab-candidates.json` SHA-256 不变（对应 `server.py:3405-3416`）。
- `/api/failures/retry-batch`：`confirm` 取 `1`／`"true"`／`null`／`[]`／`{}`／`1.0`／`false` → **全 400 且 job 目录零新增**（`:2041-2053`）。
- `/api/vocab/presets/domains`：`enabled.programming` 取 `{"a":"false"}`／`[true]`／`1`／`"false"`／`null`／`0.0`，以及 `enabled` 整体为数组 → **全 400，`vocab-domains.json` 未落盘**（`:3730-3748`）。
- `/api/reapply` 的 `all`：`1`／`"0"`／`[]`／`{}` → **全 400**（旧实现 `"false"` 是 truthy，会触发**全量重跑**，此处为真实修复，`:5563`）。
- `/api/clear` 的 `dry_run`／`only_failed`：`"false"`／`1`／`null` → **全 400**（`:4751`）。
- 空体/坏体在 5 个 POST 入口（cand-apply／presets-domains／presets-import／reapply／clear）共 20 组 → **全 400 人话**。

### 2. data_root 绑定能否绕过 —— 绑定生效，但存在「空摘要」缺口与「同一目录换写法误拒」

**只认绝对路径**：`_take_data_root:258`／`_query_data_root:286` 均 `os.path.isabs` 拒相对路径，实测 `relative/x`、`./x`、`../x`、`~/x`、`x`、` tmp/x` 全 ParamError；显式 `null`／数字／布尔／数组/对象 → 400（不静默当默认）；**缺键或空串 → 默认目录（保留旧行为）**。

**摘要算法**：`server.py:2220` `hashlib.sha256(os.path.abspath(data_root).encode()).hexdigest()[:16]`（64 bit，写入侧 `:1828`）——无现实碰撞风险。

实测（`GET /api/failures/retry-batch/status`）：

| 场景 | 实测 | 判定 |
|---|---|---|
| 同目录＋同 job_id | 200 | ✔ |
| 尾斜杠 `/x/` | 200（abspath 归一） | ✔ |
| 含 `..` 的等价路径 `/x/data/..` | 200 | ✔ |
| job 文件被复制到另一 data_root | **409 且不回 `results`** | ✔ 达标 |
| job 无 `data_root_digest` 键 | **200 放行（返回 results）** | ✖ **P2-1** |
| `data_root_digest: null` / `""` | **200 放行** | ✖ **P2-1** |
| 同一目录的**大小写变体** | **409（误拒）** | P2-2 |
| 指向同一目录的**符号链接** | **409（误拒）** | P2-2 |

根因：`:2221` 写作 `if stored_digest and stored_digest != want_digest`，**摘要为空即整条绑定被跳过**；而 `_recovery_jobs_dir`/摘要全程用 `os.path.abspath`（非 `realpath`），本仓其它身份判定（`:360-361`、`:1971`、`:2667-2668`）都用 `realpath`，口径不一致 → 符号链接/大小写/挂载点差异一律误拒（是**拒绝**而非绕过，安全侧不倒）。

### 3. job_id 端到端 —— 基本达标，一处按设计保留的回落

**全部读取 job 的入口（穷举）**：
1. `GET /api/failures/retry-batch/status` → `_handle_retry_batch_status:2243`：**强制双键**，缺 `data_root`／缺 `job_id`／相对路径／非法 job_id（`../x`）→ 全 400 人话 ✔。
2. `POST /api/failures/retry-batch` 幂等分支 `:2080` → `_recovery_job_read(data_abs, existing)`，`data_abs` 与 `existing` 都来自服务端摘要表 ✔。
3. `GET /api/vocab/candidates/apply/status` → `_handle_vocab_apply_status:3472`：**传了才比对**；`data_root` 不符 → 409 且 `job:null`；`job_id` 不符 → 409 且**不回任何 job 字段**（含 job_id）✔。**但三个查询参数全缺时不报错，回落「最近一次 job」**（`:3486-3499` 实测 200）→ **P2-3**（前端 `resumeVocabApplyPoll` 已用 `if(!dataRoot())return` 自封，仓内不可达；属跨标签页/换目录的窄口）。

**前端轮询**：`index.html:1378`／`:1416` 均走 `vocabApplyStatusQuery()`（`index.html:1347-1352`，带 `data_root`＋`job_id`）；`applyVocabCandidates` 在 202 后钉住 `o.job_id`（`:1463`）；`/api/retry` 单条与批量重试（`index.html:1087`／`:1156`）**不带 data_root**，目标取监听态而非本页目录 —— 属 P1-2 未纳入的任务身份缺口 → **P2-7**。

### 4. 候选版本锁 —— PASS（真 409、真零执行、检查在写盘之前）

- `candidates_revision` = **候选文件字节的 SHA-256 前 16 位**（`server.py:3153-3160`），GET 回传（`:3141`）。覆盖范围＝候选清单内容本身（正是 index→候选 的映射依据）；不覆盖词库/预置，但 apply 只按 index 取候选，范围合理。
- **锁的检查位置**：同步入口 `:3417-3422` 在 `with _state_lock` 建 job **之前**；`_run_vocab_candidates_apply:3185-3193` 在 `_load_vocab_candidates`／写词库**之前**（worker 内二次校验，纵深防御）。
- 实测漂移：会话内 GET 取 rev1 → 改写候选文件 → POST 带 rev1 → **409**，且：未建 `data/recovery_jobs` 目录/文件、`vocab-user.json` 未生成、整棵目录字节快照不变、`_vocab_apply_job` 未启动、响应回最新版本便于前端刷新（`:3420-3422`）✔。
- 缺 `candidates_revision` → 400（不是静默放行）✔；前端在无版本时**前置拒绝提交**（`index.html:1449-1452`）✔。
- 副作用：文件被另一处 `_mark_vocab_candidates_imported` 改写 → 版本自然变化 → 陈旧页面后续提交 `409`，属正收益。
- 弱化点：**候选文件不存在时版本恒为字符串 `"absent"`**，客户端伪造 `"absent"` 可过锁并建一个空 job（实测 202，零写盘，因为无候选可应用）→ **P2-5**。

### 5. 部分更新安全 —— PASS

真预置域（3 个）下实测（`server.py:3727-3748`）：
- 先只提交 `{d2:false}` → 200，`d1` 仍 `true`；
- 再只提交 `{d1:false}` → 200，**`d2` 保持 `false`**（旧实现 `bool(raw.get(domain, True))` 会**回启**，此为本链真实修复），落盘 `vocab-domains.json` 同步保持；
- 提交未知域 `{"NOPE":false}` → 200 且忽略，既有状态不变；
- 提交空 `{}` → 200 且 `vocab-domains.json` **SHA-256 前后一致**（`_save_vocab_domain_state:2911` 用 `sort_keys=True` 确定性序列化）→ 无旁路副作用；
- 值必须真布尔，坏值 400 且**零落盘、不误删词库文件**。
- 布尔化后的调用点未失效：`reapply.all`（`:5566`，含内部 `:3286` 传 `True`）、`clear.dry_run/only_failed`（`:4751-4752`）、`rerun_old`（`:3178`）全部实测仍可用/按预期 400。

### 6. 错误脱敏有无旁路 —— 主体到位，**剩 2 处裸 exc ＋ 1 条响应链路未盖**

- 全仓扫描：`% (exc,)`／`% exc`／`str(e)`／`f"{e}"`／`repr(`／`traceback.` 在 `app/server.py` **已无命中**；约 30 处错误出口统一改走 `_err_text`（`:229-247`、`:1324`、`:1967`、`:2030`、`:2122`、`:2188`、`:2211`、`:2678`、`:2982-3028`、`:3238-3293`、`:3364`、`:3587`、`:3632`、`:3749` 等）。
- `/api/status` 坏库分支实测 200 + `ok:false` + 结构化，且**不含** data_root/state.db 绝对路径（`collect` 的 `message` 在 `:3865-3869` 出网前抹掉）✔。
- `_open_rw` 的两个 `FileNotFoundError` 与 connect 失败（`:5172-5184`）已用 `_diag_redact_path`／`_err_text`，`_reapply_one:5233` 的 `str(exc)` 只是转传**已被脱敏**的文本 ✔。
- `/api/browse` 的四条失败文案（`:3918`／`:3920`／`:3927`／`:3935`）已打码 ✔；`/api/clear` 的 `state.db` 文案（`:4757`）已打码 ✔。
- **旁路 1（P1-1）**：`server.py:4435` `_worker_note_error("任务 %s 处理时遇到意外：%s" % (_ffn, exc))` —— **未包 `_err_text`**，且 `_worker["last_error"]` 被 `GET /api/start` 原样出网（`Handler:5617-5618` → `_listener_snapshot:1174、1292`，该路由**没有任何脱敏**）。HTTP 实测：注入 `OSError('打不开 /private/var/folders/…/rvw_e6_uo0cfufh/data/state.db')` 后，`GET /api/start` 响应体里**真实绝对路径逐字出网**。
- **旁路 2（P1-2）**：`server.py:5417` `"note": "新稿已生成在数据目录：%s；入库未试：%s" % (os.path.abspath(new_rendered), exc)` —— 同一函数另有 6 处已改 `_err_text`，此分支漏改；`note` 会进 `/api/reapply` 响应（前端 `index.html:1197` `say("重跑完成："+x.o.note)` **直接渲染**）并写进 manifest receipt。
- **旁路 3（P2-4）**：`/api/reveal` 失败分支 `:5011` `% (err or real,)` 仍可能回真实绝对路径；`:3915`（browse）与 `:4999`（reveal）的 `% (raw,)` 回显用户原文（相对路径，风险低）。
- `_err_text` 本体：能抹绝对路径、压平换行、截断 180 字、坏 `__str__` 不二次抛（`:322-345`）；**含空格路径只抹到第一个空格**，实测 `/Users/zzy/My Data/vault/note.md 打不开` → `… Data… 打不开`（末段词泄漏）→ **P2-6**。
- 用户真实目录绝对路径仍在**成功响应**里出现（`data_root`／`input_root`／`canonical_output_path`／`/api/reveal` 的 `path`／verdict「已存入你的笔记库：…」）—— 这是 HD-2=A「错误摘要打码、不做完整路径导出」的既定口径，**不作为问题**，仅在此声明。

### 7. API 加严的仓内调用点同步 —— 全部合规（逐点清单）

`app/index.html` 内全部 `/api/*` 调用点逐条核对（列＝端点 → 行号 → 是否合规）：

| 端点 | 行号 | 关键字段 | 判定 |
|---|---|---|---|
| POST `/api/reveal` | 529 | `{path}`（绝对） | ✔ |
| GET `/api/note` | 797 | `run_id`＋`data_root`(非空即带) | ✔ |
| POST `/api/retry` | 1087／1156 | 仅 `{run_id}` | ⚠ 不带 data_root（P2-7，服务端未加严，不会 400） |
| POST `/api/failures/retry-plan` | 1105 | `run_ids`(数组)＋`data_root`＋`ob_vault_root` | ✔ |
| POST `/api/failures/retry-batch` | 1129 | `confirm:true`(真布尔)＋`plan_token`＋`run_ids`＋`data_root` | ✔ |
| POST `/api/reapply` | 1193／1206 | `run_id` 或 `all:true`(真布尔)＋`data_root` | ✔ |
| GET `/api/vocab` | 1250 | `data_root` | ✔ |
| GET `/api/vocab/candidates` | 1274 | `data_root` | ✔ |
| GET `/api/vocab/candidates/apply/status` | 1378／1416 | `data_root`＋`job_id` | ✔ |
| POST `/api/vocab/candidates/apply` | 1460 | `indices`(Number→int)＋`rerun_old`(真布尔)＋**`candidates_revision`**＋`data_root` | ✔ |
| POST `/api/vocab`（增） | 1484 | `reapplyPayload({wrong,right})` | ✔ |
| POST `/api/vocab/delete` | 1494 | `reapplyPayload({wrong})` | ✔ |
| GET `/api/vocab/presets` | 1503 | `data_root` | ✔ |
| POST `/api/vocab/presets/domains` | 1527 | `enabled` 全部 `<input>.checked`（真布尔） | ✔ |
| POST `/api/vocab/presets/import` | 1540 | `domains`（字符串数组） | ✔ |
| GET `/api/status` | 1570 | `data_root`(非空即带)＋`limit=200` | ✔ 非 200 分支已加人话（新） |
| GET `/api/start` | 1577 | — | ✔（但载荷含未脱敏 `worker.last_error`，见 P1-1） |
| GET `/api/browse` | 1600／1672 | `path` | ✔ |
| POST `/api/start` | 1727 | `data_root`／`input_root`／`ob_vault_root`（空值走 `undefined` 被 JSON 丢弃→默认） | ✔ |
| POST `/api/stop` | 1749 | 无体 | ✔ |
| POST `/api/clear` | 1784／1827 | `dry_run:true`／`only_failed:!!onlyFailed`（真布尔）＋`input_root` | ✔ |

跨仓核对：除 `app/index.html`／`app/server.py` 外，全仓无其它 `/api/*` 调用方（`scripts/` 只有 orchestration 看门狗）。**`/api/failures/diagnosis` 与 `/api/failures/retry-batch/status` 仓内无前端调用点** —— 因此这两条“相对 data_root 由静默改 400”“缺 job_id 400”的加严**不会造成线上 400**。逐点结论：**漏改 0 处**。

### 8. 回归不倒退 —— PASS

- `git diff` 的 hunk 覆盖范围（逐 hunk 读过）**只**落在：新增取参层、各处错误文案脱敏、`RECOVERY_RESULT_FIELDS`/归一化、`_recovery_job_read` 加摘要校验、`_handle_retry_batch_status`、`_candidate_detail`、`_vocab_candidates_revision`、`_run_vocab_candidates_apply` 取参与锁、`_handle_vocab_apply_status`、presets/domains 部分更新、`_handle_status`/`_handle_failure_diagnosis` 取参与脱敏、`Handler.do_GET` 外层接管。**未触碰**：`_scan_disk_states`／`_FAIL_SEMANTICS`／`_diagnosis_item` 语义块／`_exec_retranscribe|reuse_derived|publish_only` 策略体／No-Clobber 判定／`_recovery_gate_ok` 六门／`_handle_retry_post`／`_reapply_one|_all` 逻辑。
- 复核实证：`_FAIL_SEMANTICS` 在位、`SOURCE_LOCATION_REVIEW` 三处以上在位（诊断条＋计划排除＋gate 拒）、四层状态与 `RECOVERY_JOB_FINAL` 在位、三策略常量在位、No-Clobber/`SKIPPED` 语义在位、幂等 `job["idempotent"]=True:2083` 在位；builder 自测 7f/7g 亦实测 `PUBLISH_BLOCKED` 不降级、目标已存在→SKIPPED 且字节不变、缺库→NEEDS_HUMAN 不重建库。
- `Handler.do_GET`：新外层只做 `try/except`（`:5584-5599`），原路由体**逐字搬进** `_do_get:5601`。HTTP 实测：`/` → 200 `text/html`、`/index.html` → 200、`/nope.css` 与 `/favicon.ico` → **404 结构化 JSON（与旧行为一致，未吞）**、`GET /api/note`（缺参）→ 400、`GET /api/vocab|candidates|note|status` → 200、`POST /nope` → 404、`POST` 坏体 → 400。返回体形状未变。
- 主题默认浅色未回退（`index.html` 静态首帧）。

### 9. 测试质量抽查 —— PASS（含 2 处瑕疵）

- 退出码：`selftest_p1_2_contract.py` → **exit 0 / 257 PASS**；`selftest_p1_2_frontend.py` → **exit 0 / 19 PASS（FRONT ALL PASS）**；`selftest_v26_presets.py` → **exit 0 / 58 PASS**。断言数与 builder 自报（257／19）**逐字一致**。
- 真断言：抽查合同测试 §1（每坏例同时断言 400＋人话＋零写盘＋零 job）、§2（job 文件搬到别目录后 409 且 `"results" not in`，非恒真）、§3（`frozenset(d.keys())` 键集合一致 + `RECOVERY_RESULT_FIELDS` 集合相等）、§4（漂移前后 `_vocab_apply_job` 同一性与 `vocab-user.json` 不存在）、§5（空 `enabled` 比 `vocab-domains.json` SHA-256）；前端测试用「抽真源码＋node 桩」，断言查 URL query 串与 POST body 原文（`data_root=%2F…`、`"candidates_revision":"REV-1"`）、`TIMERS` 停表计数、页面文案关键字——**均非恒真**。
- tmp 门：合同测试每个 part 首行 `assert_tmp(...)`（`:55-59`），且 `:297` 之后所有 `data_root` 来自 `tempfile.mkdtemp`；`DEFAULT_DATA_ROOT` 亦在 `:197` 过了门。前端测试不调 handler（不适用该门），其假目录 `/tmp/p12-fake-rootA` 只存在于内存。
- 无跳过/软通过：无 `skip`／无 `sys.exit(0)` 早退；仅 `part5` 在“预置域 < 2”时有条件早退（真实 3 域，未触发），且该条件本身有断言兜住。
- 瑕疵：① `:506` 断言名「4c 漂移 -> 候选文件未被动过」实际断言 `sha(cand_path) != before_bytes`（因测试自己刚重写过该文件，成立），名实不符 → **P3-4**；② 6 处「多值 or」软断言（`:344` `in (404,409)`、`:391` `in (200,409)`、`:624`/`:639` `in (400,500)`、`:699` `in (400,409,500)`、`:801` `in (409,202)`）——收敛度偏松，但均排除了“错误方向”的结果。

### 10. 行为变更的可接受性 —— 4 条全可接受

1. **候选 apply 必带 `candidates_revision`**：仓内唯一调用点已同步（`index.html:1460`），并在无版本时前置拒绝（`:1449`）→ 无线上 400 风险。
2. **`/api/status`／diagnosis 相对 data_root 由「静默回落默认目录」改 400**：`/api/status` 唯一调用点在有值时恒为绝对路径（来源为 browse 的 `realpath` 结果／`/api/start` 的 `last_data_root`／localStorage 旧值），无值时整键省略走默认 → 合规；diagnosis **仓内无调用点**。唯一副作用：用户在数据目录框手输相对路径时，现在每次刷新会明确提示“须为绝对路径”而非静默改用默认目录 —— 正是 D-9 想要的 fail-loud，可接受。
3. **布尔字段严格化**：前端所有布尔位都是 `checked`／`!!x`／字面 `true`（逐点核过，见 §7），无调用点失效。
4. **`browse`/`clear` 错误文案改打码**：`_diag_redact_path` 保留末 3 段（`…/Downloads/需转录视频` 量级），仍够定位；文案保留“请点浏览重选”动作指引，未伤可操作性。唯一可议：末 3 段对含家目录的路径会带上用户名（HD-2=A 的示例只保留 2 段）→ **P3-3**。
5. 附：`indices: []` 由旧「200 无操作」变 400（`_take_int_list` 默认 `allow_empty=False`）——前端有 `if(!ids.length)` 前置门，仓内无影响 → **P3-2**。

---

## P0 / P1 Findings

- **无 P0 阻断。** P1-2 五条交付目标（严格类型层／data_root+job_id 绑定／字段一致／候选版本锁／部分更新安全／错误信息安全）经独立取证均**达成**；三套自测 exit 0；仓内调用点零漏改；P0-1/P0-2/P0-3 已验收语义无削弱。
- **P1-1（须修，交 qa 复验）**：`app/server.py:4435` 错误出口漏脱敏 —— `_worker_note_error("任务 %s 处理时遇到意外：%s" % (_ffn, exc))` 用裸 `exc`，而 `_worker["last_error"]`（`:1174`／`:1292`）会被 `GET /api/start`（`Handler:5617-5618`）**原样出网**，且该路由无任何脱敏；HTTP 实测真实绝对路径逐字出现在响应体里。归因：本链把其它 ~30 处出口统一改 `_err_text` 时**漏了这一处**（同一函数下一行 `:4441` 的 `verdict` 已改）。改法：`% (_ffn, _err_text(exc))`；并建议 `_listener_snapshot` 出网前对 `worker.last_error` 走同一脱敏函数（或 `/api/start` 复用 `_handle_status` 的脱敏口径）。
- **P1-2（须修，交 qa 复验）**：`app/server.py:5417` 错误出口漏脱敏 —— `"note": "新稿已生成在数据目录：%s；入库未试：%s" % (os.path.abspath(new_rendered), exc)` 用裸 `exc`；该 `note` 会进 `/api/reapply` 响应并被前端 `index.html:1197` **直接渲染给用户**，同时写入 manifest receipt。同函数另有 6 个分支已用 `_err_text`，口径不一致。改法：`exc` → `_err_text(exc)`（`os.path.abspath(new_rendered)` 是产品有意给出的产物路径，保留）。

## P2 / P3 Backlog Findings

- **P2-1** `_recovery_job_read:2221` `if stored_digest and stored_digest != want_digest`：**摘要为空即跳过整条绑定**。实测把无 `data_root_digest` 键／值为 `null`／空串的 job 文件放到**另一个 data_root** 下，`retry-batch/status` 仍 200 并回全部 `results`。改法：摘要缺失或非法一律 409（或退化为“按 job 文件所在目录归属”判定），把“空摘要 = 老文件兼容”改成显式的兼容白名单。
- **P2-2** 绑定摘要用 `os.path.abspath`（`:2220`／`:1828`）而本仓其它身份判定用 `os.path.realpath`（`:360`／`:1971`／`:2667`）。实测**符号链接**指向同一目录、以及同一目录的**大小写变体**，取 job 一律 409 误拒（不是绕过）。改法：两侧统一 `realpath`（或 `normcase(realpath())`），并加一条“同一目录两种写法都能取到 job”的回归断言。
- **P2-3** `_handle_vocab_apply_status:3472` 三个查询参数全缺时不报错，回落返回“最近一次 job”完整明细（`:3486-3499`，实测 200）。前端已自封（`resumeVocabApplyPoll` 无 data_root 不接管），但契约上仍留“缺 job_id 也能拿到当前 job 明细”的口子。改法：无任何键时回 `{ok:true, job:null}`，只允许“显式 data_root（+可选 job_id）”的查询。
- **P2-4** `/api/reveal` 失败分支 `:5011` `% (err or real,)` 仍会回真实绝对路径；`:3915`（browse）与 `:4999`（reveal）的 `% (raw,)` 回显请求原文。改法：统一 `_diag_redact_path` / `_err_text`。
- **P2-5** 候选文件缺失时 `_vocab_candidates_revision` 恒返回常量 `"absent"`（`:3159`），客户端伪造该值可过锁并建一个“空 job”（实测 202，零写盘、imported=0）。改法：`absent` 时直接 400/409（“没有待审清单可应用”）。
- **P2-6** `_err_text:334-337` 按空白切词再抹路径，含空格路径只抹到第一个空格：实测 `/Users/zzy/My Data/vault/note.md 打不开` → `… Data… 打不开`（末段词泄漏）。改法：先用正则整体抹 `(/[^\s'"]+)+` 再压平空白。
- **P2-7** 前端 `/api/retry`（`:1087`／`:1156`）不带 `data_root`，单条/批量重试目标取监听态而非本页目录 —— 与 P1-2「任务身份」同源但未纳入本链；若与 P1-3/P1-4 同批处理需先扩 `/api/retry` 契约（属 Change B 级）。
- **P3-1** JSON 同键重复被 `json.loads` last-wins 静默吞掉（实测 `{"confirm":false,"confirm":true}` → 真执行）；取参层无从拒绝。若要堵，需在 `_body_json` 用 `object_pairs_hook` 检出重复键并 400。
- **P3-2** `indices: []` 由「200 无操作」变 400（`_take_int_list` 默认不允许空数组）；前端有前置门，仓内无影响。
- **P3-3** `_diag_redact_path:1374-1379` 保留末 3 段，含家目录时会带上用户名（HD-2=A 示例只保留 2 段）；建议对 `_diag` 文案改成末 2 段。
- **P3-4** `tests/selftest_p1_2_contract.py:506` 断言名「候选文件未被动过」与断言式 `!=` 不符（应为「未被服务端回写」）；建议改名或改成“服务端未触碰”的直接取证（如比对 mtime 前值）。
- **P3-5** `_handle_status:3865-3869` 顶部脱敏只覆盖 `ok is False` 且只 `message`/`error` 两个键名；日后新增错误键名（如 `reason`）会静默漏掉。建议改成“递归扫全树里的错误类键”。
- 另记（非问题、供 supervisor 判）：P1-2 的 `/api/failures/retry-batch/status` 双键修复在**前端无调用点**（无 UI 轮询该 job），仅由自测覆盖；若产品后续要展示批量恢复进度，需补前端调用点。

## 回归结论

- **无倒退。** P0-1 诊断/`SOURCE_LOCATION_REVIEW` 排除、P0-2 批量恢复（dry-run＋token TTL＋confirm＋幂等单 job＋原子写＋三策略＋No-Clobber＋两路 fail-closed）、P0-3 四层状态与 `_FAIL_SEMANTICS` 归一化，在源码层面**未被改动**，在 builder 自测与我的复跑中**逐项仍在位**（含 7f/7g 实测）。
- `Handler.do_GET` 外层接管为纯加壳：静态首页/`/index.html` 200、未知路径 404 结构化、各 GET 端点返回体形状不变；未见吞掉正常 404 或静态资源，也未见返回体被改写。
- 三套自测：`selftest_p1_2_contract.py` exit 0（257）、`selftest_p1_2_frontend.py` exit 0（19）、`selftest_v26_presets.py` exit 0（58）。
- 本链唯一**新增行为面**是「请求字段坏类型 400」「无 revision 的候选 apply 400」「相对 data_root 400」三处 fail-loud，均已核对仓内调用点全部合规（§7 清单，漏改 0 处）。

## 未覆盖项（本复核未验，不得推断为通过）

1. **真实 whisper / 真实批量恢复执行级链路**（`_exec_retranscribe` 真调用、真实 16 条、长视频）——本复核全程合成数据，未跑真引擎。
2. **真机 UI 目检**（未起 8765、未点页面）；前端结论来自「抽真源码＋node 桩」与 HTTP 层探针，不替代真机。
3. **多标签页真并发**：job_id 隔离只做了函数级与桩级验证，未做两个真浏览器标签页抢同一 backend。
4. **挂载点/网络卷/APFS 大小写不敏感卷**：符号链接与大小写只有本机结论（P2-2），未在其它文件系统复核。
5. **`/api/failures/diagnosis` 与 `/api/failures/retry-batch/status` 的前端使用场景**（仓内无调用点），其加严只经 handler/HTTP 层验证。
6. **用户真实视频目录与 Obsidian 库**（红线禁写，未读未写）；`data/state.db` 真源仍未核（继承 HANDOFF 未决项）。

---

心跳：目标＝独立复核 DEVELOP-P1-2 交付并落盘报告｜结论＝PASS（无 P0 阻断；P1×2＋P2×7＋P3×5）｜下一步＝交 qa（建议针对 P1-1/P1-2 复验 `/api/start` 与 `/api/reapply` note 的脱敏）→ supervisor 复检。

---
---

# 复核二（2026-09-15）

- Task: DEVELOP-P1-2 返工复核（首轮 2×P1 ＋ 6×P2 是否真闭环）
- Commit: **未提交**（工作树相对 HEAD `d7540d8`；`app/server.py` **+642/−197**、`app/index.html` **+76/−11**、`tests/selftest_p1_2_contract.py` 1281 行、`tests/selftest_p1_2_frontend.py` 312 行 —— 与 TM 转述**逐字一致**，已核 `git diff --stat`）
- Reviewer: code-reviewer（`opencode/muse-spark-1.3-contributor-free`，本窗口 subagent 独立复核，与 builder 非同一审查上下文；**先读首轮正文全文再动手**）
- Result: **PASS（8/8 返工项闭环；无 P0/P1 阻断；新发现 1×P2 ＋ 4×P3；首轮 5×P3 承接未修）**

> 复核口径：只读业务代码＋外置 tmp 合成数据；未改 `app/`、`tests/`、首轮报告正文；未起 8765、未请求线上服务；用户真实视频目录与 Obsidian 库零写。
> 本轮另写**三个独立探针**（全部落在系统 tmp，未入仓）：`/tmp/p12_probe2.py`（94 断言 / **0 FAIL**）、`/tmp/p12_probe3.py`（59 断言 / **0 FAIL**）、`/tmp/p12_probe4_front_empty_root.py`（抽 `index.html` 真源码 + node 桩，专测新行为面）。凡调 handler 的用例首行均断言 `data_root` 在系统 tmp 下。
> 反面口径：**不信 builder 自述**——所有"已改"结论均由 AST 从真源码抽出**生产表达式**后实测（非我手抄），所有"某路由唯一"结论均由 AST 穷举 + 全路由 HTTP 横扫双重取证。

---

## 一、逐条必查项证据

### 1. P1-1 是否真闭环 —— **闭环**

**源头（`:4515`）**：用 AST 从真源码抽出该调用点表达式（未手抄）：

```
:4515 生产表达式 = '任务 %s 处理时遇到意外：%s' % (_ffn, _err_text(exc))     ← _err_text(exc) 已在
```

以此表达式对该 `OSError` 实测：`打不开 /Users/reviewer_secret_probe/My Data/state.db 与 /private/var/folders/zz_reviewer_probe/T/v2o（权限不足）` → `'任务 第七周.mp4 处理时遇到意外：打不开 …（权限不足）'`（**不含 `/Users`、`state.db`、`/private/var`；文件名保留**）。

**出网闸门（`:1199-1201`）**：`_listener_snapshot()` 构造 `worker` 前对 `last_error` 走 `_err_text`，覆盖所有复用该快照的路由。**独立注入裸文本**（模拟"未来再有裸 exc 写进来"）后 HTTP 实测 `GET /api/start`（真 Handler，**随机端口 56462 ≠ 8765**）：

| 断言 | 实测 |
|---|---|
| `GET /api/start` → 200 | ✔ |
| 响应体不含注入的 `/Users/reviewer_secret_probe` | ✔ |
| 响应体不含 `/Users` | ✔ |
| 响应体不含 `/private/var` | ✔ |
| 响应体不含 `state.db` | ✔ |
| 响应体不含注入路径（`SECRET_ABS`） | ✔ |
| `worker.last_error` 实际值 | `'任务 a.mp4 处理时遇到意外：打不开 …'` |
| `default_data_root` 字段仍在（`/var/folders/…/v2o-console-data`） | ✔ **非泄漏**（见下） |

> **口径澄清（重要，勿误判为漏）**：`/var/folders` **确实**出现在该响应体里，但**只**来自 `snap["default_data_root"]`（`:1332`）——那是后端自报的**自身默认目录**，与 `last_error` 无关，客户端本来就知道它；同理监听态下 `data_root/input_root` 是调用方自己传的。因此"全响应体不含 `/var/folders`"这一字面断言在本接口**不可能达成**（除非删掉 `default_data_root` 字段，那是产品功能不是安全项）。**可判定的安全断言是"注入的错误路径不得出现"**，实测通过。

**穷举所有复用 `_listener_snapshot` 的路由**：AST 全文件扫描该函数的调用点 → **共 1 处**，`Handler._do_get:5703`（即 `/api/start`）。无第二条。
**再加穷举式反证**：把 `last_error` 置为含真实路径的裸文本后，横扫 **全部 10 条 GET 路由**（`/`、`/api/status`、`/api/failures/diagnosis`、`/api/failures/retry-batch/status`、`/api/browse`、`/api/note`、`/api/vocab`、`/api/vocab/candidates`、`/api/vocab/candidates/apply/status`、`/api/vocab/presets`）＋ **全部 11 条 POST 路由** → **零泄漏**（`/api/start` 单独断言通过）。
**同类问题的其它可能出网口也已逐一排除**：`_worker["current"]`（`:1122` 只存 `run_id/filename/stage`）、`preview`（`_preview_mapping:1072` 异常一律回 `""`）、`_worker_record` 的 `verdict`（`_process_one_run` 的 5 个失败出口 `:4229/:4239/:4281/:4341/:4403` 与 `:4522` 全部已走 `_err_text`）。

### 2. P1-2 是否真闭环 —— **闭环**

**读 `:5497-5502` 分支源码窗口**（逐字）：

```
5497                except Exception as exc:
5498                    result.update({
5499                        "new_state": prev_state,
5500                        "note": ("新稿已生成在数据目录：%s；入库未试：%s"
5501                                 % (os.path.abspath(new_rendered),
5502                                    _err_text(exc)))})
```

**无裸 `exc`**。AST 抽出的生产表达式 = `'新稿已生成在数据目录：%s；入库未试：%s' % (os.path.abspath(new_rendered), _err_text(exc))`，代入 `OSError("入库失败 /Users/reviewer_secret_probe/My Data/vault/note.md 打不开")` 实测 → `'新稿已生成在数据目录：<tmp>/data/jobs/r1/rendered.md；入库未试：入库失败 …'`：**不含 `/Users`、不含 `vault/note.md`；产品有意给出的产物路径保留** ✔。

**全仓错误/文案出口扫描（`% exc`／`str(e)`／`f"{e}"`／`+str(`／`repr(`／`traceback.`）**——用 **AST** 而非 grep（grep 漏 f-string 与括号换行）：

| 模式 | 结果 |
|---|---|
| `%`-格式化的实参是 `exc/e/err/error` 且未包 `_err_text` | **0 处**（`:4515`、`:5500` 均已在位） |
| f-string 插值 `{exc}` 类 | **0 处** |
| `+str(` / `repr(` / `traceback.` | **0 处** |
| 残留 `str(exc)` | **13 处**，AST 逐处判定**全部**位于 `except ParamError as exc:` 内（`:1642/:1863/:2100/:2306/:3244/:3481/:3557/:3806/:3843/:3938/:4826/:5643/:5677`），加 `_err_text` 本体 `:357` |

`ParamError` 文案安全性的**独立取证**：`_bad()`（`:157-158`）只拼 `key`＋期望类型＋`_type_zh(value)`（**类型名，不回原值**），所有 `ParamError` 均为人话常量 → 无路径出口。
**helper 专查**：`_humanize_startup_error`（`:876-894`）已改 `text = _err_text(exc)`；`_reapply_one`（`:5315-5317`、`:5325`、`:5368`、`:5381`、`:5413`、`:5497-5502`、`:5554`）与 `_reapply_all`（`:5607-5611`）逐处已改；`_open_rw` 两个 `FileNotFoundError` 与 connect 失败（`:5257-5269`）已 `_diag_redact_path`／`_err_text`。
**结论：无漏网点 → 不 FAIL。**

### 3. `_strip_paths` 正确性 —— **实现成立（覆盖含空格路径、不外溢），过抹无实际伤害**

`_PATH_STOP_CHARS:323`／`_strip_paths:327-347`／`_err_text:350-366`。逐字符扫描：遇到 `/` 起，扫到引号/中文标点/括号/换行/`*?` 等收尾字符为止，整段替换为 `…`（连续路径合并为一个 `…`）。

| 坏例（我方自造） | 实测输出 | 判 |
|---|---|---|
| `/Users/zzy/My Data/vault/note.md 打不开` | `… 打不开`（**末段 `Data/vault/note.md` 未泄漏**） | ✔ 首轮 P2-6 原例已修 |
| `读不到 /a/b/c.md，请检查` | `读不到 …，请检查`（中文标点收尾，人话保住） | ✔ |
| `打开 ' /x/My Dir/f.md ' 失败` | 引号收尾，路径整段抹净 | ✔ |
| `打开 "/x/My Dir/f.md" 失败` | 同上 | ✔ |
| `A /p/q.txt 与 B /r/s.txt 都失败` | 两段路径全抹（`与 B` 被吞，见"过抹"） | ✔ 不泄漏 |
| CRLF `失败 /a/b.md\r\n下一行` | `\r` 为收尾字符 → 换行后文本保留 | ✔ |
| `C:\Users\x\a.md`（反斜杠） | **原样不动**（不脱敏） | ⚠ **P3-新2**（macOS 单平台，实际不可达） |
| `文件 /a/b/c.md`（末尾无空格） | 整段抹净 | ✔ |
| `打开/a/b/c.md失败`（紧跟中文） | 整段抹净（中文非收尾字符 → 一并吞） | ✔ 不泄漏 |
| `/Users/zzy/我的 数据/笔记/a.md 打不开` | 整段抹净 | ✔ |
| `失败 /a/b(1)/c.md 结束` | `(` 为收尾字符 → `…)` 后文保留 | ✔ |
| `//a//b//c 失败` | 整段抹净 | ✔ |
| `…/Downloads/需转录视频`（已打码再脱敏） | `…` | ✔ 幂等不堆省略号 |

**过抹（builder 自报两处）判定 —— 不伤既有用户可见文案，也不伤既有 QA 断言**：

1. `application/json` → `application…`：`_strip_paths` 的**唯一**调用点是 `_err_text`；该字面量只出现在 `send_header`（`:1339`、`:1354`），**不经** `_err_text` → 无影响。
2. 孤立 `/` → `…`：我做了**穷举式反证**——把 `app/server.py` 里所有会被 `_err_text` 改写的字面量全部列出（187 条），逐条判定"是否会真经 `_err_text` 出口"。结论：**真正经 `_err_text` 的只有 3 个二次脱敏点**（`:1201 last_error`、`:3947 snap[_k]`、`:5095 err or real`，AST 抽取），而：
   - 两处 `_worker_note_error` 模板（`:4484/:4515`）静态部分无斜杠；
   - `collect()` 的失败文案（`src/stage12/status_snapshot.py:173/182/198`）均"英文前缀＋路径在尾"；
   - 其余含斜杠的人话（`该任务已不在失败/受阻快照内`、`纯标点/空格不能作错词`、`正在监听/转写中`、`整数数组（…不收 true/false…）`、`检查磁盘空间/目录权限后重试`、`导入%d条/重跑成功%d篇/…` 等）**全部直接出网、不经 `_err_text`**。
   → **过抹只发生在"路径之外还有无标点分隔的纯文本"时**，production 文案无此形态 → **不 FAIL**。附实测"纯人话逐字不变"不变量：`打不开，请检查权限`／`磁盘空间不足`／`网络超时`／`转写失败：模型未就绪`／`候选清单已变化（零执行）…` 全部 `E(t) == t`。
3. **但有一条真退化**（我独立发现，比自报两处更实）：二次脱敏会把路径后紧跟的**纯中文词**一起吞掉，例如 `_open_rw` 的 `状态库不可读：尚未初始化（…/a/b/state.db 缺失），请先开始一次监听…` → 出网变 `…（…），请先开始一次监听…`（"缺失"被吞）。**动作指引仍在**，属可读性微降 → **P3-新3**。

### 4. 白名单是否又被绕过 —— **不绕过；「旧 abspath 摘要可取到 job」不等于绑定被绕过**

`:2273-2280` 读侧顺序：① `_recovery_digest_ok(stored)` 必须为**非空 16 位小写 hex**，否则 409；② `stored` 必须命中 `_recovery_root_digest(data_abs)`（realpath）**或** `_recovery_root_digest_legacy(data_abs)`（abspath），否则 409。

**坏摘要穷举（函数级 + HTTP 级，两条路径都打了）**：

| 构造 | 实测 |
|---|---|
| `data_root_digest` 正确（realpath） | **200**，含 `results` ✔ |
| 缺键 | **409**，不回 `results` ✔ |
| `null` | 409 ✔ |
| `""` | 409 ✔ |
| 15 位 | 409 ✔ |
| 17 位 | 409 ✔ |
| 大写 hex | 409 ✔ |
| 非 hex（`zzzz…`） | 409 ✔ |
| 数字 `1234567890123456` | 409 ✔ |
| **另一个 data_root 的合法 realpath 摘要** | 409 ✔ |
| **另一个 data_root 的合法 legacy 摘要** | 409 ✔ |
| 本目录 legacy 摘要（兼容） | 200，含 `results` ✔ |

HTTP 复核：`GET /api/failures/retry-batch/status?data_root=<dr2>&job_id=rec-b`（缺摘要）→ **409 且响应体无 `results`**；`job_id=rec-l`（本目录 legacy 摘要）→ **200 且含 `results`**。

**「旧 abspath 摘要可取到 job」= 不是绑定的绕过 —— 判定依据（三步取证）**：

1. **摘要函数是"请求目录"的函数，不是"job 文件所在目录"的函数**。读侧 `_recovery_job_read(data_root, job_id)` 先 `_recovery_jobs_dir(data_abs)` 用**请求目录**定位文件，再把 `stored` 与**请求目录**算出的摘要比。legacy 只是**第二个被接受的哈希函数**（`abspath` 口径），不是"跳过比对"。
2. **legacy 函数与改动前的写侧公式逐字一致**：`git show HEAD:app/server.py` → `:1574 data_digest = hashlib.sha256(data_abs.encode()).hexdigest()[:16]`（`data_abs = os.path.abspath(data_root)`），与 `_recovery_root_digest_legacy:1767-1770` **byte-for-byte 相同**。实测：对真实运行环境形态路径 `/var/folders/…/T/p12-compat-xxxx`（`abspath != realpath`），旧写侧摘要 `91da0f99cd1e7f41` == `_recovery_root_digest_legacy(该路径)`，与新 realpath 摘要 `e9f99e5d9357b118` **不同** → 兼容分支**非恒真**、真的在起作用（老 job 不会被误杀）。
3. **搬目录仍被拒**：把**本目录 legacy 摘要**的 job 文件复制到另一个 data_root 再请求 → **409 且不回 `results`**；把**本目录 realpath 摘要**的 job 文件同样搬走 → **409**。即"合法摘要"只在**它自己的目录**里有效。
   → 结论：legacy 白名单是**有界的兼容垫片**，绑定强度不变（既不放过跨目录，也不误杀同目录旧文件）。

### 5. realpath 口径 —— **有牙对照真实成立；大小写 fail-closed 不影响正常用户**

`_recovery_root_digest:1757-1764`（`realpath(abspath(...))`），写侧 `:1884`／`:1901`（plan 摘要）→ `:2158`（job 落盘），`_handle_retry_batch_post:2129` 目录身份比对，`_handle_vocab_apply_status:3566-3570` 对齐。

| 变体 | 实测 |
|---|---|
| 符号链接 → 真目录：摘要 | **相同** ✔ |
| 符号链接写法取 job | **200** ✔（旧实现 409 误拒） |
| 尾斜杠 `/x/`、`/x/.`、`/x/data/..`、`x//` 双斜杠 | 摘要全部一致；取 job **200** ✔ |
| **有牙对照 A**：`abspath` 口径下链接与真目录摘要 | **不同**（`legacy(real) != legacy(link)`）✔ |
| **有牙对照 B**：链接的 abspath 摘要 != 真目录 realpath 摘要 | ✔ |
| **有牙对照 C**（builder 自测 `:1184-1196` 独立复算过）：把 `_recovery_root_digest` 临时换回 `_legacy` → 符号链接写法确被 **409 误拒**，复原后恢复 200 | ✔ 证明修复"有牙"、断言非恒真 |
| 预览走符号链接、确认走真路径 | **202**（同目录不误判）✔ |
| **大小写变体**（本机 APFS 不敏感卷，`samefile` 判定为同一目录） | `realpath` **不归一大小写** → 摘要不同 → 取 job **409 fail-closed**（**拒绝**，非绕过）✔ |

**大小写 fail-closed 的可用性判定：不影响正常用户。** 依据：① 该口径只作用于 `_recovery_job_read`（`GET /api/failures/retry-batch/status`）与 `_handle_retry_batch_post` 的目录比对两处；② `retry-batch/status` **仓内无前端调用点**（首轮已核，本轮复扫 `app/index.html` 的 16 条 `/api/*` 调用点证实）；③ `retry-batch` 确认路径上，前端预览与确认**共用同一个 `dataRoot()` 取值**（`reapplyPayload`），大小写不可能中途变化；④ 只有"手输另一种大小写写法"才会命中，且命中的结果是**结构化 409 人话**（不是静默错数据）。→ 记 **P3-新3 类观察项**，不阻断。

### 6. 无参回落与 absent 锁 —— **均闭环**

| 用例 | 实测 |
|---|---|
| `GET /api/vocab/candidates/apply/status` 无参 | **200 `{ok:true, job:null}`** ✔ |
| 内存里**确有** running job 时无参 | 仍 **`{ok:true, job:null}`**（不回明细、无回落口）✔ |
| `data_root` 对、`job_id` 不符 | **409** 且响应体无任何 job 字段（含 `job_id`）✔ |
| `data_root` + `job_id` 都对 | 200 且回明细 ✔ |
| `retry-batch/status` 双键全缺 | 400 ✔；缺 `job_id` → 400 ✔ |
| **伪造 `absent` → 同步入口**（`POST /api/vocab/candidates/apply`） | **409** + 人话 ✔ |
| **伪造 `absent` → 异步内核**（`_run_vocab_candidates_apply`，worker 实际调的那个） | **409** ✔ |
| 零执行：`_vocab_apply_job` 单例 **同一性**未变 | ✔ |
| 零写盘：同步两轮 + 异步一轮，**目录字节快照（含子目录标记）前后一致** | ✔ |
| 有真候选清单但传 `absent`（漂移） | 409 ✔ 零写盘 ✔ |
| 有清单时指纹为真 16 位 hex（非哨兵） | ✔ |
| 哨兵常量位置 | `RECOVERY_CANDIDATES_ABSENT:2821`；`_vocab_candidates_revision:3212-3223` 缺失回哨兵；`:3251`（worker 内核）／`:3487`（同步入口）**两处**见哨兵即 409；前端 `app/index.html:1281` 把 `"absent"` 置 `null` ✔ |

### 7. 回归 —— **无倒退**

- **P0 已验收语义未回退**（源码级 + 探针 B）：`_FAIL_SEMANTICS` 在位；`SOURCE_LOCATION_REVIEW` 出现 ≥3 处（诊断条／计划排除／gate 拒）；三策略 `RETRANSCRIBE/REUSE_DERIVED/PUBLISH_ONLY` 在位；`RECOVERY_JOB_FINAL` 四层状态逐字在位；No-Clobber / `SKIPPED` / `BLOCKED_OUTPUT_CONFLICT` 语义在位；`_recovery_gate_ok` 在位；`RECOVERY_RESULT_FIELDS` 字段契约 + `_normalize_recovery_results` 在位。
- **启动门人话未被打坏**（这是 realpath/脱敏改动最可能误伤的地方，我实测 5 个真实样本）：`Stage3+ table not empty (STOP EXPANSION): %r`（含**带路径的 repr 值**）、`Run in transcription-stage status…`、`reconcile refuses transcription-stage status %r`、以及"路径在标记之后"的样本 → **GATE 码仍正确产出**（`GATE_STAGE3_BLOCKED ×3`／`GATE_RUN_STATE_BLOCKED ×2`），**文案不含真实路径**。
- **`Handler.do_GET` 外壳未吞 404/静态资源**：`GET /` → 200 `text/html`；`/index.html` → 200；`/nope.css` → **404 结构化 JSON**；`/favicon.ico` → 404；`POST /nope` → 404；`POST` 坏体 → 400；`GET /api/note` 缺参 → 400；`GET /api/vocab` → 200（未被外壳改成 500）；`/api/status?data_root=relative/x` → 400 人话。返回体形状与旧行为一致。
- **首轮 PASS 面未被新面破坏**：严格类型层（`_take_int/_take_bool/_take_int_list` 坏例全 400；`_reject_duplicates` 仍拒）；候选版本锁（`GET` 回 16 位指纹；漂移 → **409 且目录字节快照不变**；缺 `candidates_revision` → 400；锁在**建 job 之前**、worker 内核在**写词库之前**，位置由源码偏移量核过）；部分更新安全（真 3 域 `crypto/finance/programming`：只提交 d2 → d1 仍启用；再只提交 d1 → **d2 保持停用不回启**；坏布尔 400；空 `enabled` 200）；仓内调用点（`app/index.html` 16 条 `/api/*` 全部合规：apply 带 `candidates_revision`、status 带 `data_root+job_id`；`scripts/`／`src/`／`tests/` 无其它调用方）。
- **本轮改动范围**（逐 hunk 读过 `app/server.py` 1327 行 diff 全文）：只落在取参层、错误文案脱敏、`RECOVERY_RESULT_FIELDS` 归一化、job 摘要校验、`_handle_retry_batch_status`、`_vocab_candidates_revision`、apply 两入口取参与锁、presets/domains 部分更新、`_handle_status` 取参与脱敏、browse/reveal 打码、`Handler.do_GET` 外壳。**未触碰** `_scan_disk_states`／`_diag_*` 语义块／`_exec_*` 策略体／No-Clobber 判定／`_recovery_gate_ok`／`_handle_retry_post`／`_reapply_*` 业务逻辑。
- 三套自测：`selftest_p1_2_contract.py` **rc=0 / 320 PASS**、`selftest_p1_2_frontend.py` **rc=0 / 22 PASS（FRONT ALL PASS）**、`selftest_v26_presets.py` **rc=0 / 58 PASS** —— 全部与 builder 自报**逐字一致**。

### 8. 测试质量 —— **合格**

- 断言数：**320 / 22 / 58**（自报一致）；无 `skip`／无 `sys.exit(0)` 早退；无恒真 `check(…, True)`（AST 扫）；"多值 or"软断言 **6 处**（`in (404,409)`／`(200,409)`／`(400,500)×2`／`(400,409,500)`／`(409,202)`），与首轮记录的 6 处**同量**、未扩散，且均排除"错误方向"结果。
- **tmp 门**：`assert_tmp(root, who)` 定义于 `:43`；`part1..part9` **每个用例函数体内**均首行断言（`part1` 额外断言 `server.DEFAULT_DATA_ROOT` 也在 tmp 下），`make_data_root:118` 亦过门。唯一未自断言的 `plan_token_for:184` 是**辅助函数**（输入 root 由调用方 `part8/part9` 预先断言）→ 不构成缺陷（我的探针据此把辅助函数从"用例"口径排除）。
- **新增断言是真断言**：`part9_rework_guards:1018-1243` 逐条核过：9a 用**正则扫真源码**（`%\s*\(?\s*exc\s*[,)]` 必须为空）+ `_worker_note_error` 调用点计数 + **旧写法对照**（`note_path in old_note` 证明修复前会泄漏）+ `str(exc)` 白名单式；9b 用**真 tmp 含空格目录**实测；9c 断言"不含完整路径且含 `…/`"；9d 6 类坏摘要 + **"两种口径摘要确实不同（兼容分支非恒真）"**；9e **含"有牙对照"**（临时换回 legacy 口径必须 409）+ 复原后必须 200；9f 断言 `_vocab_apply_job is job_snapshot` + `tree_snapshot(noroot) == before` + `vocab-user.json` 不存在 + `recovery_jobs` 目录不存在。**均非恒真、非过宽**。
- 前端自测（22 条）用"抽真源码 + node 桩"，断言查 **URL query 原文**（`job_id=job-A`）、**POST body 原文**（`"candidates_revision":"REV-1"`）、`TIMERS` 停表、页面文案关键字；新增 S5 三条（哨兵置空／无版本前置拒提交／真版本未误伤）**构成完整对照**，非恒真。

---

## 二、首轮 8 项闭环判定（8/8）

| # | 首轮编号 | 结论 | 关键证据 |
|---|---|---|---|
| 1 | **P1-1** | **闭环** | `:4515` `_err_text(exc)`（AST 抽真表达式实测）；`:1201` 出网闸门；`_listener_snapshot` 调用点 AST 穷举**唯一**（`:5703`）；21 条路由横扫零泄漏 |
| 2 | **P1-2** | **闭环** | `:5500` `_err_text(exc)`（产物路径保留）；**AST 全仓扫描 0 漏网**；13 处 `str(exc)` 全在 `except ParamError`；`_humanize_*`／`_reapply_*` 逐处已改 |
| 3 | **P2-1**（空摘要即跳过绑定） | **闭环** | `_recovery_digest_ok:1773-1777` 要求 16 位小写 hex；缺键/null/空串/15/17位/大写/非hex/数字/别目录 9 类坏摘要**全 409 且不回 `results`**（函数级+HTTP 级） |
| 4 | **P2-2**（abspath 误拒） | **闭环** | `:1757` realpath；符号链接/尾斜杠/`.`/`..`/双斜杠同摘要且可取 job（旧实现 409）；**有牙对照三组实测成立**；`:2129`、`:3566` 同步对齐 |
| 5 | **P2-3**（无参回落） | **闭环** | `:3559-3560` 无 `data_root` → **200 `{ok:true, job:null}`**；有 job 也不回明细；`job_id` 不符 409 零字段 |
| 6 | **P2-4**（browse/reveal 回真实路径） | **闭环** | `:3994/:3998/:4000/:4007/:4015`→`_diag_redact_path`；`:4017`→`_err_text`；`:5081/:5085`→`_diag_redact_path`；`:5095`→`_err_text(err or real)`（纯路径实测回 `…`）；`% (raw,)`／`% (real,)` **0 命中** |
| 7 | **P2-5**（`absent` 伪版本过锁） | **闭环** | `:2821` 哨兵＋`:3212` 缺失回哨兵＋`:3251`／`:3487` 两入口见哨兵 409（**同步+异步实测**）；零执行（单例同一性）＋零写盘（目录字节快照）；前端 `:1281` 置 null |
| 8 | **P2-6**（含空格路径只抹到第一个空格） | **闭环** | `:323` `_PATH_STOP_CHARS`＋`:327` `_strip_paths` 逐字符扫描；14 组坏例**零泄漏**；纯人话逐字不变；builder **拒绝我首轮的正则建议**——**我方实测认可其判断**：其实现确实覆盖"含空格路径"且靠收尾字符**不外溢到人话**，比正则更可控（正则仍会在空格处截断，且难以处理"路径后紧跟纯中文"） |

**未纳入本轮范围（如实记账，不计失败）**：首轮 **P2-7**（前端 `/api/retry` 不带 `data_root`，单条/批量重试目标取监听态而非本页目录）**未返工**，仍在 ── 首轮已定性"与 P1-2 同源但需先扩 `/api/retry` 契约（Change B 级）"，与本轮 8 项口径一致。

---

## 三、新发现问题（分级）

### P2（新，须修；非本轮 8 项阻断，但属本轮返工**新引入**的前后端契约错配）

- **P2-新1｜数据目录框留空（=用默认外置测试目录）时，错词重跑进度显示静默失效。**
  - 复现（**抽 `index.html` 真源码 + node 桩**，未手抄、未点真机）：`el("inData").value=""` → `loadVocabCandidates()`（URL 无 `data_root`）→ `applyVocabCandidates()` → **实测 POST body = `{"indices":[0],"rerun_old":false,"candidates_revision":"REV-1"}`（无 `data_root`）** → 202 钉住 `job_id="job-D"` → 轮询 URL **实测 = `?job_id=job-D`（无 `data_root`）** → 后端 `_handle_vocab_apply_status:3558-3560` 按本轮新契约回 **`{ok:true, job:null}`** → 前端 `:1395` `if(!s){…vocabApplyStopPoll();btn.disabled=false;return;}`：**实测 `TIMERS=0`（停表）、按钮 `disabled=false`（变回可点）、进度区无任何文字、无任何人话提示**（`candidateApplyText` 仍是提交前那句"正在导入词库（老稿不动）…"）。
  - 可达性：**UI 明确放行该路径** —— `index.html:1670` `if(which==="inData"){done2(true,"用默认外置测试目录","ok");return;}`（留空被判**绿**）；`reapplyPayload` 在 `dataRoot()` 为空时**省略** `data_root`；前端**未缓存**后端已回的 `snap["default_data_root"]`（`app/server.py:1332`，`index.html` 全文 0 命中）。
  - 归因：本轮 P2-3 的后端加严（要求显式 `data_root`）**未同步前端**——返工前该轮询是**无参**调用、后端回"最近一次 job"，故空框也能显示进度；**这是本轮新引入的回归**，不是历史遗留。
  - 影响面：进度静默消失 + 按钮变回可点（用户可能重复点击）；`resumeVocabApplyPoll:1416 if(!dataRoot())return;` 同源，页面重载后续看同样失效（`index.html:338` 只在 localStorage 有值时恢复框值，首次/清空场景仍空）。
  - 建议改法（Change A 级，留 DEVELOP 不召 Planner）：前端在框为空时把后端 `default_data_root`（`/api/start` 已回）补进 `dataRoot()` 口径，`apply` 与 `status` 两处一致带上；或在 `pollVocabApplyStatus` 的 `!s` 分支给一句人话而不是静默停表。
  - **不判本轮 8 项 FAIL 的理由**：后端行为＝题目明列的返工要求（`:3544/:3559` 无参→`job:null`）；`P2-7` 同类"前端未跟"已在首轮归为 Change B 级挂账。此条属**要求已达成但需补前端**，故交 TM 定处置（建议随 P2-7 同批）。

### P3（新）

- **P3-新2｜`_strip_paths` 只处理 POSIX `/`，反斜杠路径不脱敏**：实测 `打不开 C:\Users\x\a.md` 原样出网。产品为 macOS 单平台（`open -R`、APFS、`os.sep` 全为 `/`），所有真实路径均为 POSIX → **实际不可达**。建议在 `:322` 注释声明"仅 POSIX 路径"，或日后再议。
- **P3-新3｜二次脱敏吞掉路径后紧跟的纯中文词**：`_open_rw` 的 `状态库不可读：尚未初始化（…/a/b/state.db 缺失），请先开始一次监听…` → 出网 `…（…），请先开始一次监听…`（"缺失"被吞）。动作指引保留，仅可读性微降。同类：库/引擎英文异常里路径后无标点的尾段会被吞（本就非人话，无害）。
- **P3-新4｜自测可移植性**：`tests/selftest_p1_2_contract.py:1154` `check("9d 两种口径摘要确实不同（兼容分支非恒真）", legacy != real)` —— 该等式只在 `TMPDIR` 与 `realpath` 不同时成立（macOS `/var/folders`→`/private/var` 成立）。换到 `abspath==realpath` 的环境会**误 FAIL**（不是产品缺陷，是测试断言依赖平台形态）。建议改成"用 job 文件所在目录的 legacy 摘要 + 另一目录 → 必 409"这类**不依赖平台**的对照。
- **P3-新5｜既有 QA 报告取证步骤因本轮契约变更而失效（需加注，勿当回归）**：`docs/qa/RERUN-PROGRESS-QA-REPORT.md` 的 A4/U8（无参轮询采样）与 U6（重载续看）在本轮新契约下**不再可复现**（无 `data_root` 现在回 `job:null`）。属**有意变更**（P2-3 要求），建议 qa 复验时更新步骤，或由 neat 在该报告尾加一条链路注记。

### P3（承接首轮，本轮未修 —— 均非本轮返工范围，如实记账）

- 首轮 **P3-1**（JSON 同键重复 last-wins）／**P3-2**（`indices: []` 由 200 变 400）／**P3-3**（`_diag_redact_path` 保留末 3 段，含家目录会带用户名；本轮 browse/reveal 新文案沿用同一函数 → 该面**被本轮扩大使用**，建议一并收敛为末 2 段）／**P3-4**（`tests/selftest_p1_2_contract.py:515` 断言名"候选文件未被动过"与断言式 `!=` 不符，**仍在**）／**P3-5**（`_handle_status:3940-3947` 脱敏只覆盖 `ok is False` 且只 `message`/`error` 两键；我已确认 `collect()` 是本文件唯一消费点且四个失败分支全为 `ok:False`，当前无漏；新增错误键名会静默漏掉）。

---

## 四、回归结论

- **无倒退。** P0-1（诊断/`SOURCE_LOCATION_REVIEW` 排除）、P0-2（dry-run＋token TTL＋confirm＋幂等单 job＋原子写＋三策略＋No-Clobber＋两路 fail-closed）、P0-3（四层状态＋`_FAIL_SEMANTICS` 归一化）在源码层**未被改动**，在探针 B（59 断言，0 FAIL）与两套复跑中**逐项在位**；启动门 GATE 码经 5 个含路径真实样本实测仍正确。
- `Handler.do_GET` 外层为纯加壳：静态首页 200、未知路径 404 结构化、各 GET 端点返回体形状不变；未吞正常 404/静态资源。
- 首轮 PASS 的严格类型层、候选版本锁、部分更新安全、仓内调用点零漏改**未被本轮新面破坏**（realpath 与白名单两个新面已单独取证，见 §5／§4）。
- **本链行为面变化共 4 条**，逐条判定：
  1. **`absent` → 409**：仓内调用点（前端 apply）已在前置门拦住；若真触发，前端走通用分支显示 `o.error` 人话 → **无失效**。
  2. **无参 status → `job:null`**：后端符合返工要求；**前端在"数据目录框为空"时不带 `data_root` → 进度静默失效**（见 **P2-新1**，唯一新问题）。
  3. **过抹文案**：经 187 条字面量穷举 + 3 个二次脱敏点实测 → **无用户可见文案、无既有测试断言因此失效**（仅 P3-新3 可读性微降）。
  4. **大小写 fail-closed**：仅影响 `retry-batch/status`（前端无调用点）与批量确认（前端两处同源取值）→ **不影响正常用户**。
- 三套自测 rc=0（320／22／58）；探针 A 94 断言 0 FAIL、探针 B 59 断言 0 FAIL。

---

## 五、未覆盖项（本复核未验，不得推断为通过）

1. **真实 whisper / 真实批量恢复执行级链路**（真引擎、真实 16 条、长视频、1200 篇量级）——全程合成数据；`_exec_*` 策略体只做源码级在位核对。
2. **真机 UI 目检**（未起 8765、未点页面）——前端结论来自"抽真源码＋node 桩"（含新增的空数据目录场景探针），**不替代真机**；P2-新1 建议 qa 在真机按"清空数据目录框 → 应用所选错词"复现一次。
3. **多标签页真并发**（两个真浏览器标签页抢同一 backend）：job_id 隔离只做函数级与桩级验证。
4. **挂载点／网络卷／非 APFS 卷**：符号链接与大小写只有本机结论（§5）。
5. **`/api/failures/diagnosis` 与 `/api/failures/retry-batch/status` 的前端使用场景**（仓内无调用点），其加严只经 handler/HTTP 层验证。
6. **用户真实视频目录与 Obsidian 库**（红线禁写，未读未写）；`data/state.db` 真源仍未核（继承 HANDOFF 未决项）。
7. **`src/` 底座**只读复用未改；`src/stage12/status_snapshot.py:173/182/198` 的原始路径文案依赖 app 侧出网脱敏兜住，本轮只验了 `_handle_status` 这一个消费点（已确认是唯一消费点）。

---

心跳：目标＝独立复核 P1-2 返工 8 项是否真闭环｜结论＝**PASS（8/8 闭环；无 P0/P1；新发现 1×P2＋4×P3；首轮 5×P3 承接）**｜下一步＝交 qa（建议按 **P2-新1** 在真机复现"空数据目录框 → 应用所选错词"并确认进度是否静默消失）→ supervisor 复检。

---
---

# 复核三（2026-09-15）

- Task: DEVELOP-P1-2 **窄范围返工复核**——复核二所报 **P2-新1**（数据目录框留空时 apply/轮询不带 `data_root` → 后端回 `job:null` → 进度静默消失）是否真闭环、有无新回归（后端新增 `_take_required_data_root`＋前端 `effectiveDataRoot` 口径）。
- Commit: **未提交**（工作树相对 HEAD `d7540d8`）。实测 `git diff --numstat`：`app/server.py` **+660/−197**、`app/index.html` **+106/−13**；`tests/selftest_p1_2_contract.py` 1361 行、`tests/selftest_p1_2_frontend.py` 458 行、`tests/selftest_v26_presets.py` 254 行（未改）——与 TM 转述**逐字一致**。
- Reviewer: code-reviewer（`opencode/muse-spark-1.3-contributor-free`，本窗口 subagent 独立复核，与 builder 非同一审查上下文；**先读首轮正文与复核二节全文再动手**）
- **Result: FAIL（1×P1 阻断 ＝ 新发现 P1-三1；P2-新1 本身判「闭环」；本次返工本身无新增回归）**

> 复核口径：只读业务代码＋外置 tmp 合成数据；未改 `app/`、`tests/`、本报告此前正文（本轮只追加本节）；**未起 8765**（HTTP 层用系统随机端口，并断言 `port != 8765`；实测 8765 当前无监听）；用户真实视频目录与 Obsidian 库零写；探针全部落系统 tmp（`/tmp`），未入仓。
> 本轮另写**两个独立探针**（自写抽取器、自写驱动，不复用 builder 的 harness/断言名）：
> ① `/tmp/p12_cr3_http_probe.py`——真 `Handler` + 真 `ThreadingHTTPServer`（随机端口），**60 项断言 / 59 PASS / 1 FAIL（FAIL 即 P1-三1 的取证项）**；
> ② `/tmp/p12_cr3_front_probe.py`——从 `app/index.html` **逐字抽真源码**（花括号配对抽取）+ node DOM/fetch 桩，**32 项断言 / 27 PASS / 5 FAIL（5 项全指向 P2-三1）**＋5 条 OBS 原文留证。
> 反面口径：不信 builder 自述——凡"已改"结论均由**真源码表达式**或**真 handler 实测**取得；凡"归属"结论均由**行号漂移算术**反推（见 §六）。

---

## 一、逐条必查项证据

### 1. 原问题是否真闭环 —— **闭环**（P2-新1 主场景）

**全链复现「数据目录框留空 → 点应用所选错词」**（抽真源码＋node 桩，场景 A；`/tmp/p12_cr3_front_probe.py`）：

| 断言 | 实测 |
|---|---|
| A1 空框时从前端同一份候选回包里学到生效目录 | `effectiveDataRoot === "/private/var/folders/zz/T/v2o-console-data"` ✔ |
| A2 `vocabJobDataRoot()` 空框时回该绝对目录 | ✔ |
| A3 POST body 带显式绝对 `data_root` | 实测 body 原文：`{"indices":[0],"rerun_old":false,"candidates_revision":"REV-A","data_root":"/private/var/folders/zz/T/v2o-console-data"}` ✔ |
| A4 body 里的 `data_root` 是绝对路径（非相对/空） | 正则 `"data_root":"\/…"` 命中 ✔ |
| A6/A7/A8 轮询 URL 带**同值** `data_root`＋`job_id` | 实测 URL：`/api/vocab/candidates/apply/status?data_root=%2Fprivate%2Fvar%2Ffolders%2Fzz%2FT%2Fv2o-console-data&job_id=job-A`；`decodeURIComponent` 回解 === POST 值 ✔ |
| A9 进度正常渲染 | 文案含「正在导入」且 `TIMERS>0`（未停表）✔ |
| A10 全链无任何请求使用空 `data_root` | 所有 URL 无 `data_root=&`／`data_root=` 结尾 ✔ |

**同一发请求打到真后端**（探针①，系统 tmp 合成数据，`assert_tmp` 先行）：`GET /api/vocab/candidates`（无参）→ 200 且 `data_root` 非空、绝对、指向系统 tmp、与 `server.DEFAULT_DATA_ROOT` 逐字相等、指纹是真 16 位 hex（非 `absent`）→ 以该值 `POST …/apply` → **202 + job_id** → `GET …/status?data_root=同值&job_id=同值` → **200 且 `job` 非空、`data_root` 与提交一致、进度字段齐（state/total/done/rerun_old）**，任务终态 `done`／`message='已导入1条；未重跑老稿，老稿未动'／imported=1`。→ **「提交成功 ⇒ 同目录必可查」在真实后端成立，前端取的就是这份回包，两端同源。**

**独立验证 builder 的「提交成功 ⇒ 同目录必可查」不变量（自造组合，不许有可达的"建成却查不到"）**：

| 组合（POST 用目录 A） | 实测 GET 结果 | 判 |
|---|---|---|
| `data_root=A`＋正确 `job_id` | **200，含 job（`job_id` 一致）** | ✔ |
| `data_root=B`（另一个 tmp 目录）＋正确 `job_id` | **409，`job` 为 null，且响应体无 `job_id/state/total/done` 任何字段** | ✔ 响亮拒绝，非静默 null |
| 无参 | **200 `{ok:true, job:null}`** | ✔ 查询侧严格性未被放宽 |
| `data_root=` 空串 | **200 `{ok:true, job:null}`** | ✔ 不回落"最近一次" |
| 只带 `job_id`（不带目录） | **200 `{ok:true, job:null}`** | ✔ 同上 |

→ **「建成却查不到」无"静默"可达组合**：能查到的只有同目录；不同目录是 **409 结构化人话**；缺参是 **`job:null`＋前端人话**（见 §4）。**P2-新1 的原始复现口径（空框 → 提交 → 进度静默消失）已不可复现。**

### 2. 对称加严的副作用 —— **只加严 apply，零漏改，不会造成线上 400**

- **只作用于 apply**：全仓 `_take_required_data_root` 命中 **3 处**，即定义（`app/server.py:277`）＋调用（`:3251` 同步内核／`:3493` 异步壳）。**同步入口与异步壳都覆盖**：`:3251` 活证——探针①里后台 worker 真的走到了该函数（失败任务的 `message` 出自该函数内的重新取参），`:3493` 由 HTTP 层坏例直接打中（下段）。
- **坏例实测（真 handler，HTTP 层，全部 400 且人话）**：`data_root` 取 缺键／空串／纯空格／相对路径／`null`／数字／布尔／数组 → **8/8 全 400**；且 **零执行**（`_vocab_apply_job` 单例同一性未变）＋**零写盘**（目录清单与目录字节快照不变）。相对路径的文案直给动作：「数据目录须为绝对路径，请点浏览重选」。
- **未误伤别的入口**（实测仍 200）：`GET /api/vocab`、`GET /api/vocab/candidates`、`GET /api/status`、`GET /api/vocab/presets` 带目录均 200；**非 apply 入口缺省 `data_root` 仍回落默认目录（旧行为逐字保留）**；`/api/start`、`/api/reapply`、`/api/retry-batch`、`/api/clear` 等仍用 `_take_data_root`（可缺省），未被连带加严。
- **仓内调用点清单（漏一个＝线上 400）**：

| 调用点 | 行 | 是否满足新必填 |
|---|---|---|
| `POST /api/vocab/candidates/apply`（**唯一前端调用点**） | `app/index.html:1486` | ✔ 提交前守卫 `:1474-1478` 保证 `submitRoot` 非空才发请求（node 桩实测：目录未知时**零请求**发出） |
| `GET /api/vocab/candidates/apply/status` | `app/index.html:1388`（轮询）、`:1435`（续看） | ✔ 均走 `vocabApplyStatusQuery()`，root 非空即带 |
| 合同自测（故意不带，期望 400） | `tests/selftest_p1_2_contract.py:955`／`:959` | ✔ 断言 `400`＋人话含「数据目录」 |
| 前端自测（202 正向） | `tests/selftest_p1_2_frontend.py:320` | ✔ body 断言含 `data_root` |

- **仓外调用方**：**无**。`scripts/` 仅 orchestration 看门狗、`src/` 全无 `/api/`、`app/start.sh` 的 `/api/start` 只出现在 echo 文案里（非调用）。→ **漏改 0 处，不产生线上 400。**

### 3. `effectiveDataRoot` 真源正确性 —— **两种情形结论不同：默认场景正确；相对路径场景会被污染（→ P3-三1）**

- **「第一次打开页面、框空、点刷新」→ 正确。** 清单请求不带 `data_root`，后端按 `DEFAULT_DATA_ROOT` 读并**回显同一个值**：实测 `GET /api/vocab/candidates` 回的 `data_root` 与 `server.DEFAULT_DATA_ROOT` **逐字相等**、绝对、在系统 tmp 下。→ 前端由此学到的目录**就是后端真正会用的目录**，无错配。
- **`/api/start` 的 `default_data_root` 兜底与之一致**：`_listener_snapshot` 写的是同一个模块常量（`app/server.py:1348`），实测 `/api/start` 回 `default_data_root` 与清单回包**同值**。→ 两真源同源、互为兜底，**不存在"清单读默认目录、POST 却带另一个目录"**（框空场景下）。
- **「用户手输相对路径被 400」→ 真源会被污染（P3-三1）**：`_handle_vocab_candidates_get` 用的是 `normalize_path()`（只 strip＋去引号，**不做 abspath**），所以框里是 `relative/x` 时**清单接口不 400、原样回显 `"relative/x"`**，前端 `:1286` 把它当生效目录记住；用户随后**清空框**（UI 判绿＝"用默认外置测试目录"）再点应用时，`vocabJobDataRoot()` 回的是这个**相对污染值**，实测 POST body＝`{"…","data_root":"relative/x"}`。→ 本地守卫未拦住（它只判非空），最后由服务端 400 人话兜住（**响亮、可操作、可恢复**，故记 P3 不阻断）。
- **「清单读的是默认目录、POST 却带另一个目录」的错配可能**：存在（用户改框但不点刷新），但**被候选版本锁兜住**——旧目录的指纹必然对不上新目录的清单（新目录多半 `absent`），实测一律 **409 人话、零执行、零写盘**，不会误应用。→ 安全侧不倒。

### 4. 人话分支质量 —— **主场景达标；仅 1 处同族缺口（→ P2-三1）**

- **`!s`（`job:null`）分支已不再静默**（本次返工直接相关处）：node 桩实测（场景 B）——`TIMERS===0`（停表）且文案非空、**不再是提交前那句「正在导入…」**、按钮 `disabled=false` 复原、进度区可见；文案含可操作指引（「请点「刷新」重看，或重开页面」）✔。
- **提交前置门文案可操作**：目录未知 → 「请先选择数据目录（或点「刷新」让页面读到当前生效目录）再提交」（实测零请求发出）；无候选版本 → 「候选清单还没读到版本，先点「刷新」重载待审清单再提交」（node 桩 S3/S5 与本次 E 场景均证）✔。
- **轮询异常分支都已带人话**：400／404／409 → `vocabApplyDropPoll(o.error||"进度读取被拒绝，请刷新后再看")`；5xx → 容错计数 + 「进度读取失败，正在重试…」；网络 reject → 同一容错口径（均实测有人话、按钮复原）✔。
- **缺口（P2-三1）**：**提交侧 409(running) 的"接管"路径无任何文案**（见 §5 与 §三）。此为本节唯一不达标处。

### 5. 竞态修复（`resumeVocabApplyPoll()` 移进 `Promise.all` 回调）—— **真消除，且我方独立隔离取证**

- **builder 自测 S6e 未能隔离该真源**（其 `/api/vocab/candidates` 路由**也**回了 `data_root`，两个真源同值，断言无论由谁置值都成立）。我方**独立隔离**（场景 G3）：让候选清单接口**直接 500**、只留 `/api/start` 的 `default_data_root` → 实测 `effectiveDataRoot` 被置为该值、`TIMERS>0`、`vocabApplyJobId==="job-S"`（成功接管），且该次续看请求**带显式 `data_root`** → **顺序依赖确实修好了，且不是靠"运气"通过。**
- **无新引入的顺序依赖**：apply 不依赖 refresh 完成——若在 refresh 回包前点 apply，无版本/无目录的**前置门**会给人话阻止且**不发请求**（实测）；G1（框空但生效目录已知→接管）、G2（目录未知→**不发请求**、不留半状态）均通过。
- 残留（**P3-三3**，当前不可达）：`resumeVocabApplyPoll()` 只在 `refresh(false)` 的 `Promise.all` 回调里被调一次，若那一刻两个真源都没给出目录就整页不再续看；当前后端两真源恒有值（`default_data_root` 是常量、清单回包恒带 `data_root`），故不可达，仅加注。

### 6. 无新回归 —— **无倒退**（用行号漂移算术把改动范围钉死）

- **server.py 的本次改动＝只有 3 处**。复核二引用的行号与当前实测的漂移呈**严格分段**（这正是"只在若干点插入"的指纹）：

| 复核二报告引用 | 当前实测 | 漂移 | 含义 |
|---|---|---|---|
| `_recovery_root_digest:1757` | `:1773` | **+16** | 改动点之前 |
| `_recovery_digest_ok:1773-1777` | `:1789` | +16 | 同上 |
| 读侧摘要判定 `:2273-2280` | `:2290／:2294` | **+17** | 同步入口调用点（`:3251`，+1 行）之后 |
| P1-1 源头 `:4515` | `:4533` | **+18** | 异步壳调用点（`:3493`，+1 行）之后 |
| P1-2 note 分支 `:5500-5502` | `:5518` | +18 | 同上 |

  拆解：`+16` ＝ 新函数块（`:277-292`，def＋docstring＋body＋2 空行＝16 行）＋ `+1`（`:3251`）＋ `+1`（`:3493`）＝ **+18**，与 `numstat` 的 `+660/−197`（相对复核二的 `+642/−197`，**净增 18 行、删除数不变**）**逐数吻合**。→ **server.py 除这 3 处外与复核二版逐字节相同**，故复核二的 8 项闭环实现**不可能被本轮破坏**（另做源码在位复核：`_FAIL_SEMANTICS`／`SOURCE_LOCATION_REVIEW`＋计划排除＋gate 拒／三策略常量／`RECOVERY_JOB_FINAL`／No-Clobber 的 `BLOCKED_OUTPUT_CONFLICT`／`_recovery_gate_ok`；P2-1 `_recovery_digest_ok`＋缺键/null/空串 409；P2-2 realpath＋legacy 兼容；P2-4 `_diag_redact_path`/`_err_text(err or real)`；P2-5 `RECOVERY_CANDIDATES_ABSENT` 两入口 409；P2-6 `_PATH_STOP_CHARS`/`_strip_paths`——**逐项在位**）。
- **index.html 改动集中在 vocab-apply 功能块内**（`git diff` hunk 逐块读过：`:1259-1266`／`:1278-1285`／`:1302-1305`／`:1350-1369`／`:1385-1428`／`:1428-1459`／`:1458-1489`／`:1593-1621`），**无一处落在其它 UI 区域**。漂移同样分段：`:1193／:1206`（reapply）**+0** → `:1347-1352`（statusQuery）**+12** → `:1484` 起 **+26** → `:1603`(GET /api/start) **+26** → `:1727`(POST /api/start) **+29**；`+3` 恰好＝`:1606-1607` 兜底 2 行＋`:1619` 注释 1 行。与自报改动清单一致。
- **P0 已验收语义未回退**：探针①源码级在位 8 项全 PASS；`Handler.do_GET` 外壳未吞 404/静态资源（`GET /`→200、`/index.html`→200、`/nope.css`→404 结构化、`/favicon.ico`→404）；`GET /api/vocab|candidates|status|presets` 带目录均 200（未被外壳改 500）。主题默认浅色未动（`app/index.html:2` `data-theme="light"`；自测 part8 亦断言）。
- **仓内零写红线**：`app/presets` 全树 SHA-256 前后一致；词库产物只落在 tmp 数据目录。

### 7. 测试质量 —— **合格（含 2 处瑕疵 → P2-三2／P3-三3）**

- 三套自测复跑（`python3.12`）：`selftest_p1_2_contract.py` **rc=0／337 PASS／0 FAIL**、`selftest_p1_2_frontend.py` **rc=0／34 PASS（FRONT ALL PASS）**、`selftest_v26_presets.py` **rc=0／58 PASS** —— 与 builder 自报 **337／34／58 逐字一致**。
- 新增断言数对得上：合同侧 `320→337`（**+17** ＝ 9g 组 15 条＋part8 的 2 条：`POST 缺 data_root → 400 人话（P2-新1 对称契约）`、`GET status 无参 → job:null`）；前端侧 `22→34`（**+12** 全在 S6）。抽查**非恒真**：9g 用 `tree_snapshot` 比目录字节、`_vocab_apply_job is job_snap` 判零执行、`got.get("job").get("job_id")==vjob_id`、`_take_required_data_root({"data_root": DEFAULT_DATA_ROOT})` 正向；前端 S6 断言查 **POST body 原文**与 **URL query 原文**（`data_root=<值>`＋`job_id=`），均非"多值 or"软断言。
- **tmp 门**：`part1..part9` 每用例函数体首行 `assert_tmp(...)`（`part8` 的 HTTP 用例 `assert_tmp(root,"part8_http_contract")` 在真 handler 调用之前；`make_data_root` 亦过门）；`part8` 断言 **`port != 8765 and port != 0`**。前端自测不调 handler（不适用该门），其假目录只存在于内存。
- 无 `skip`／无 `sys.exit(0)` 早退；"多值 or"软断言仍 **6 处**（未扩散）。
- **瑕疵①（P2-三2）**：`part9` 的 9g「提交成功 ⇒ 同目录一定能查到」**只断言 `job_id` 回显，不断言任务结局**——实测那次 job 实际上是 `failed`（因 P1-三1），断言照样 PASS → **测试给假信心**，与它在同一段落的"提交成功"语义名实不符。
- **瑕疵②（P3-三3）**：前端 S6e「refresh 后继看拿到 /api/start 的默认目录」**两真源同值、无法区分是谁置的值**（我方 G3 已隔离复验）。另 `:1154` 的 `9d` 依赖 `TMPDIR != realpath(TMPDIR)` 的平台形态（复核二已记 P3-新4，仍在）。

---

## 二、P2-新1 闭环判定 —— **闭环**

| 复核二原始口径 | 本次实测 |
|---|---|
| 空框 → `loadVocabCandidates()`（URL 无 `data_root`） | 后端按默认目录读并**回显同一目录**（实测与 `DEFAULT_DATA_ROOT` 逐字相等） |
| `applyVocabCandidates()` → POST body **无** `data_root` | POST body **有显式绝对 `data_root`**（与清单回包同源；body 原文已留证） |
| 轮询 URL **只有** `job_id` | 轮询 URL **同值 `data_root` + `job_id`**（解码回比一致） |
| 后端回 `job:null` → 前端静默停表、按钮复原、零提示 | 真后端**不回 `job:null`**（200＋明细）；**即便**回 `job:null`，前端也**给人话**（场景 B 实测） |
| 「提交成功但静默停表零提示」 | 原路径**已不可复现**（端到端 202→200→渲染进度） |

**判据**：后端查询侧严格性**未被放宽**（无参/空串仍 `job:null`），申请侧对称加严（缺/空/坏 `data_root` 一律 400 零执行），前端两处口径同源。→ **P2-新1 判闭环。**

**但「无论如何不再出现静默零提示」这一更强的验收句未完全成立**：静的出口还有一条**别的入口**（提交被 409 拒绝后的接管路径），见 **P2-三1**（非本次返工改动，但同族、同页面、同按钮）。

---

## 三、新发现问题（分级）

### P1（阻断，须修 —— 本次唯一阻断项）

- **P1-三1｜笔记库目录框留空时，「应用所选错词」POST 回 202 但后台任务**必失败**。**
  - **实测（真 handler，HTTP 层，系统 tmp 合成数据，`assert_tmp` 先行）**：POST body 与前端 `reapplyPayload` 完全一致（**不含 `ob_vault_root` 键**，实测 node 桩 body 原文已留证）→ **202 + job_id** → 轮询终态 **`failed`**，`message='ob_vault_root 须为字符串（收到 空值 null）'`，`imported=0`。**正对照**：同一份数据把 `ob_vault_root` 显式给成字符串 → 终态 **`done`**，`imported=1`，`vocab-user.json` 落到 tmp 数据目录。
  - **根因（逐行）**：异步壳 `app/server.py:3496` `vault_s = _take_str(params, "ob_vault_root", "", allow_empty=True) or None` → **`vault_s` 取值 `None`**；随后 `:3513-3515` `params = {**params, …, "ob_vault_root": vault_s, …}` **把这个 `None` 写回了 params**；worker 再进 `_run_vocab_candidates_apply`，`:3258` 同一句 `_take_str` 因"**键存在且值为 `None`**"抛 `ParamError`（`:206 isinstance(value, str)` 不通过）→ 返回 400 → 任务落 `failed`。旧版（HEAD）此处用 `params.get()`＋`isinstance` 容 `None`，故**属本链新引入的取参严格化副作用**，非历史遗留。
  - **可达性**：界面明文写「笔记库目录（**选填，不填也能转**）」（`app/index.html:198`／`:1697`），且 `rerun_old=false`（只导入词库）**根本不需要** vault；`reapplyPayload`（`:1182-1189`）仅当框非空才带该键 → 新用户（未配置 vault）／清空过框的用户**必中**；核心动作（导入所选错词）100% 失败，用户看到的是开发者口吻的内网文案。
  - **归属**：**不是本次返工引入**（见 §6 漂移算术：本轮 server.py 只多 18 行＝新函数＋2 个调用点，`:3513` 与复核二版逐字节相同）——属**复核二漏检**（其 9g 只断言 `job_id` 回显，见 P2-三2）。
  - **建议改法（1 行级，Change A 级、留 DEVELOP 不召 Planner）**：缺键就**别写这个键**——如 `params = {**{k: v for k, v in params.items() if k != "ob_vault_root"}, "data_root": data_root, …}`，仅在 `vault_s is not None` 时才 `params["ob_vault_root"] = vault_s`；**不要**去放宽 `_take_str` 对显式 `null` 的拒绝（那是 D-6 的既定契约）。
  - **复验口径（修完跑这两条即可判闭环）**：① `POST /api/vocab/candidates/apply`（无 `ob_vault_root` 键）→ 202 → 轮询终态必须 `done` 且 `imported>=1`（对照给 vault 时的正对照）；② 坏例 `ob_vault_root` 显式 `null`／数字仍应 **400**（不得因本次改法而放宽）。

### P2（须修，非本次返工引入）

- **P2-三1｜提交遇 `409 running` 的接管路径会静默停滞（无文案＋按钮禁用＋无计时器）。**
  - `app/index.html:1491-1493`：`if(x.code===409&&o.running){resumeVocabApplyPoll();return;}` —— 该分支**不再**给人话（HEAD 版此处是 `vocabApplySetText(String(o.error||"已有任务在进行中"),"warn")` 之后再接管），而 `resumeVocabApplyPoll` 有三条**静默 `return`**：`:1434`（目录未知）、`:1439`（`x.code===409/400/404`，即**正在跑的任务属于另一个 `data_root`**）、`:1447／1448`（`sameDataRoot` 不符／`state!=="running"`，即 **POST 与接管之间任务已跑完**）。
  - **实测（node 桩，抽真源码）**：
    - 场景 C（任务在**另一个数据目录**在跑）：POST→409 running，status→409 → 实测界面 `text="正在导入词库（老稿不动）…"`、`TIMERS=0`、**`btnCandidateApply.disabled=true`**、无任何提示 → **用户停在"正在导入"假象里、按钮点不动、无路可走（只能刷页面）**。
    - 场景 D（409 之后任务**已跑完**）：同上，**同样停滞**。
    - 对照：场景 B（`job:null`）已给人话 ✔、场景 F（400／5xx／网络错）已给人话 ✔。
  - **可达性（单标签页即可）**：目录框 B 起一次 apply（长任务，`rerun_old=true` 要重跑全部已完成）→ 把框改成 A → 下一次轮询命中"跨目录 409"→ 按提示按钮解禁 → 再点 apply → 命中本分支 → **停滞**。（多标签页/换目录场景同源。）
  - **归属**：该分支**不在本次返工自报的改动清单内**（自报 8 项为 `:1266/:1356/:1360/:1474-1479/:1486/:1409/:1607/:1619`），且 `:1463→:1484` 区间行数两版一致 → 判定为**复核二版遗留**，**复核二漏检**（其 §7 只按"轮询路径"验了跨目录 409，未覆盖"提交被拒后的接管"）。
  - **建议改法**：在该分支接管**之前**先落一句人话（如 `vocabApplySetText(String(o.error||"已有一次任务在进行中，请等它跑完再试"),"warn")`），或让 `resumeVocabApplyPoll` 的三条静默 `return` 在"按钮仍禁用/本页刚提交过"时也各给人话＋复原按钮。

### P3（新，不阻断）

- **P3-三1｜相对路径会污染 `effectiveDataRoot`（本地守卫不拦，靠服务端 400 兜）**：`_handle_vocab_candidates_get` 用 `normalize_path()`（**不做 abspath**）原样回显用户所输；框里 `relative/x` 时前端把 `"relative/x"` 记为生效目录，用户**清空框**后提交会带出该相对值（node 桩实测 body 原文）→ 服务端 400 人话（响亮、可恢复，点「刷新」即重新学到真目录）。建议前端在解析 `submitRoot` 时一并要求绝对路径（与后端同口径），把 400 提前成本地人话。
- **P3-三2｜`data_root` 类型错文案用了原始键名**：缺键/空串走 `_take_required_data_root` 的「请先选择数据目录（…）再提交」，而 `null`/数字/布尔/数组走 `_take_data_root → _bad()` 的「**data_root** 须为字符串（绝对路径）（收到 整数）」。同一入口两种口吻，建议统一为「数据目录」。
- **P3-三3｜续看只调一次**：见 §5 残留（当前后端两真源恒有值 → 不可达，仅加注）。
- **承接未修（如实记账）**：首轮 **P3-1～P3-5**（含 `indices: []` 变 400、`_diag_redact_path` 末 3 段带用户名、`:515` 断言名名实不符等）**仍在**；复核二 **P3-新2～P3-新5**（反斜杠不脱敏／二次脱敏吞中文词／9d 平台依赖／既有 QA 报告 A4/U8/U6 步骤因契约变更失效）**仍在，建议 qa 复验时按新契约更新步骤**。

---

## 四、回归结论

- **本次返工本身：无新增回归。** 硬证据＝§6 的分段漂移算术（server.py 净增 18 行＝新函数 16＋2 个调用点，其余逐字节同复核二版；index.html 改动全落在 vocab-apply 功能块内）＋复核二 8 项闭环实现在位复核 ＋ P0 三段语义在位（探针①源码级 8 项全 PASS）。
- **`Handler.do_GET` 外壳**：未吞 404／静态资源（`/`、`/index.html`→200；`/nope.css`、`/favicon.ico`→404 结构化），GET 各端点返回体形状未变。
- **三套自测**：`337／34／58`，rc=0，与自报逐字一致。
- **只读红线**：`app/presets` 字节零改动、仓内零写入；临时探针全部落 `/tmp`；**未起 8765**（随机端口 + 断言 ≠8765；实测 8765 无监听）。
- **本链未闭环新增 1 项（P1-三1）＋2 项 P2＋3 项 P3**；**P2-新1 判闭环**。

---

## 五、未覆盖项（本复核未验，不得推断为通过）

1. **真实 whisper／真实批量恢复执行级链路**（真引擎、真实 16 条、长视频、1200 篇量级）——全程合成数据；`_exec_*` 策略体只做源码级在位核对与 P0 语义关键字核对。
2. **真机 UI 目检**（未起 8765、未点页面）——前端结论来自"抽真源码＋node 桩"与 HTTP 层探针，**不替代真机**；建议 qa 至少真机复现：①（P1-三1）**清空笔记库框 → 应用所选错词** 看是否报 `ob_vault_root…`；②（P2-三1）A 目录起任务 → 改框到 B → 再点应用，看是否停在"正在导入…"且按钮点不动。
3. **多标签页真并发**（两个真浏览器标签页抢同一 backend）：job_id/dir 隔离只做函数级与桩级验证。
4. **挂载点／网络卷／非 APFS 卷**：符号链接与大小写只有本机结论。
5. **`/api/failures/diagnosis` 与 `/api/failures/retry-batch/status` 的前端使用场景**（仓内无调用点）。
6. **用户真实视频目录与 Obsidian 库**（红线禁写，未读未写）；`data/state.db` 真源仍未核（继承 HANDOFF 未决项）。
7. **`src/` 底座**只读复用未改。

---

心跳：目标＝独立复核 P1-2 窄范围返工（P2-新1）是否真闭环｜结论＝**FAIL（1×P1 阻断＝P1-三1「笔记库框留空时 apply 必失败」；P2-新1 本身判闭环；本次返工无新增回归；另 2×P2＋3×P3 新发现，承接首轮 5×P3／复核二 4×P3）**｜下一步＝交 builder 修 P1-三1（缺键不写键，1 行级）＋P2-三1（接管前补人话），修完按本报告 §三·P1-三1 的两条复验口径重跑，再进 qa → supervisor。

---
---

# 复核四（2026-09-15）

- Task: DEVELOP-P1-2 **窄范围返工复核（第二轮）**——复核三所报 **1×P1（P1-三1「笔记库框留空时 apply 必失败」）＋2×P2（P2-三1 接管路径静默停滞／P2-三2 9g 只断言 job_id）＋3×P3（P3-三1 相对路径污染／P3-三2 data_root 文案口吻／P3-三3 只记不修）** 是否真闭环、有无新回归。
- Commit: **未提交**（工作树相对 HEAD `d7540d8`）。实测 `git diff --numstat`：`app/server.py` **+677/−197**、`app/index.html` **+155/−17**；`tests/selftest_p1_2_contract.py` **1459 行（379 断言）**、`tests/selftest_p1_2_frontend.py` **550 行（41 断言）**、`tests/selftest_v26_presets.py` **254 行（58 断言，未改）** ——与 TM 转述**逐字一致**，已核。
- Reviewer: code-reviewer（`opencode/muse-spark-1.3-contributor-free`，本窗口 subagent 独立复核，与 builder 非同一审查上下文；**先读该报告首轮正文、复核二、复核三三节全文再动手**）
- **Result: PASS（5/5 返工项闭环；无 P0/P1/P2 阻断；新发现 0×P0 ＋ 0×P1 ＋ 0×P2 ＋ 3×P3）**

> 复核口径：只读业务代码＋外置 tmp 合成数据；未改 `app/`、`tests/`、本报告此前各节（本轮只追加本节）；**未起 8765**（HTTP 层全部用 `127.0.0.1:0` 随机端口并逐次断言 `port != 8765`，实测 8765 当前无监听）；用户真实视频目录与 Obsidian 库零写（`app/presets` 全树未动，`git status` 与复核前逐字一致）；探针全部落系统 tmp（`/tmp`），未入仓。
> 本轮另写**七个独立探针**（自写抽取器、自写驱动，不复用 builder harness/断言名）：
> ① `cr4_http_probe.py` **33 断言 / 0 FAIL**；② `cr4_none_probe.py` **8 / 0**（运行时侧信道：包住全部 `_take_*` 记录真实入参）；③ `cr4_ast_probe.py` **11 / 0**（AST 而非 grep）；④ `cr4_front_probe.py` **27 / 0**（从 `index.html` 逐字抽真源码 + node 桩）；⑤ `cr4_p3_probe.py` **34 / 0**；⑥ `cr4_reg_probe.py` **31 / 0**；⑦ `cr4_plan_probe.py` **3 / 0**。合计 **147 断言 / 0 FAIL**。凡调 handler 的用例首行均断言 `data_root` 在系统 tmp 下。
> **范围钉死手法升级**：不再只靠漂移算术。上一位复核者留在系统 tmp 的 `p12_server.diff`／`p12_index.diff`（00:15）＋ node bundle `v2o_p12c.js`（00:24）经校验确为**复核二/复核三版实体**（校验见 §6），据此**重建了复核二版快照**并在系统 tmp 内做「重建版 → 当前版」精确 diff，把本轮改动范围钉到 hunk 级。

---

## 一、逐条必查项证据

### 1. P1-三1 真闭环 —— **闭环**

**源码（`app/server.py:3522-3532`，逐字）**：

```
3522    # P1-三1：可选字段「笔记库目录」缺省/为空时**不要写回这个键**——写回 None 会让
3523    # worker 侧 `_take_str` 把「键存在且值为 None」判成类型错（显式 null 必须拒，
3524    # D-6 既定契约），于是「不填笔记库」这条合法路径必然 400→任务 failed。
3525    # 只归一必填/已知键；可选键按需补，缺省即不出现。
3526    job_params = {k: v for k, v in params.items() if k != "ob_vault_root"}
3527    job_params.update({"data_root": data_root, "rerun_old": rerun_old,
3528                       "indices": indices,
3529                       "candidates_revision": want_revision})
3530    if vault_s is not None:
3531        job_params["ob_vault_root"] = vault_s
3532    params = job_params
```

`_take_str` 对显式 `null` 的拒绝**未被放宽**（`app/server.py:206-207` `if not isinstance(value, str): raise _bad(...)` 原样在位）。

**真 handler + 真 HTTP（随机端口，实测 ≠8765；合成数据落系统 tmp）**：

| 口径 | 实测 | 判定 |
|---|---|---|
| ① POST 不带 `ob_vault_root` 键 | **202 + job_id** → 轮询终态 **200 / `state=done` / `imported=1`**、终态文案**不含** `ob_vault_root`、`vocab-user.json` 落该 tmp 数据目录 | ✔ 原 P1-三1 症状（`failed`＋开发者文案）**不可复现** |
| ①b（**源头式**）包住 `_run_vocab_candidates_apply` 记录 worker 实收 params | 实收键集合 = `['candidates_revision','data_root','indices','rerun_old']` —— **`ob_vault_root` 键根本不存在**（不是"值恰好是 None"） | ✔ 真修在源头 |
| ② `ob_vault_root` = `null`／整数 `7`／数组 `["x"]`／对象 `{"a":1}`／布尔 `true`／小数 `1.5`（HTTP 层） | **6/6 全 400**，且文案均含字段名 `ob_vault_root` | ✔ 契约未放宽 |
| ③ 自造：`ob_vault_root` = 空串 `""`／纯空格 `"   "` | **202 → 终态 done、`imported>=1`**（按"缺省/选填"处理） | ✔ 正确（该字段 UI 标注「选填，不填也能转」，空值与缺省同义；`_take_str(..., allow_empty=True) or None` 后键被丢弃，与 HEAD 的 `vault.strip() ... else None` 语义一致） |
| ④ 自造：**键存在但值为 `null`，直调同步入口** `_run_vocab_candidates_apply`（即复核三所称 `:3251` 路径，现 `:3260`） | **400**，文案 `ob_vault_root 须为字符串（收到 空值 null）` | ✔ 该 400 属 D-6 既定契约（显式 null 必须拒），**不是被打死的合法路径** |
| ④ 自造：同一入口 值为 `""`／`"   "`／显式字符串 `…/vault` | 分别 **200/200/200**，均 `imported>=1` | ✔ 合法路径全部存活 |
| ⑤ 自造：额外未知键＋`note:null` 同发 | 202 正常（只挑 `ob_vault_root` 一个键，其余原样透传） | ✔ 无越界误伤 |
| ⑤ 对照组：缺 `data_root` → 400；`GET status` 无参 → `job:null` | 均如期 | ✔ 同期加严未松动 |

**结论：无「新的合法路径被打死」** —— 故不 FAIL。原 P1-三1 的完整复现链（`POST 无键 → 202 → 终态 failed、message='ob_vault_root 须为字符串（收到 空值 null）'、imported=0`）已由 §4 的"破坏法"在系统 tmp 副本上重新造出，证明修复与症状**因果对应**。

### 2. 同类 None 写回扫查 —— **builder 三条归类全部正确**

用 **AST**（非 grep）全仓扫描（`cr4_ast_probe.py` 11/0）：

| 结论 | 独立实测 |
|---|---|
| ① `{**params, …}` 全仓**仅此 1 处**（即本次修掉的那处） | ✔ 全仓 `**name` 整表回写点共 5 处：`:5694/:5695`（`res` 响应体）、`:2207`（`want` 计划项）、`:2143`（`plan` 计划表）、`:2161`（`job` 幂等回包）、`:2198`（`cur` 计划表）；**其中 `{**params}` = 0 处**（旧形态已彻底消失，源码字面量 `"ob_vault_root": vault_s` 0 命中） |
| ② `:3373`（现 `:3382`）在 `if vault_s:` 守卫内本就正确 | ✔ AST 抽出的两处 `["ob_vault_root"] = vault_s` 写回点为 `:3382`（`reapply_params`）与 `:3531`（`job_params`），**两处都在 `if vault_s` 守卫内**；且 `:3382` 与 HEAD 逐字相同（`git show HEAD:app/server.py:2995-2997`），确属历史正确写法 |
| ③ `_RECOVERY_PLANS[...] = {**plan/cur, "job_id": None}` 是内部计划表哨兵、不同类 | ✔ 见下（自己追了一遍，没只信归类） |

**「元凶」旁证（运行时侧信道，`cr4_none_probe.py` 8/0）**：把全部 `_take_*` 包一层记录"取参层实际收到的 params"，再打前端真实形态的载荷——`/api/vocab/candidates/apply`（`reapplyPayload` 形态）经异步壳进 worker，取参层收到的 params 键集合为 `['candidates_revision','data_root','indices','rerun_old']`、**含 None 值的键 = 空集**；`/api/reapply`、`/api/vocab`、`/api/vocab/delete`、`/api/vocab/presets/domains` 同样**零 None 值**；而客户端**显式**发的 `ob_vault_root: null` 确实以 `None` 到达取参层并被 400 拒（**未被中途吞掉**）。

**`_RECOVERY_PLANS` 的 `job_id: None` 全链路追踪（自己追，未只信归类）**：
- 全部访问点穷举 **7 处**：`_RECOVERY_PLANS[digest]`（`:1907` 建计划）、`.get(digest)`（`:2136`／`:2196`）、`.pop(digest)`（`:2151`）、`[digest] = {**plan, "job_id": _reserved}`（`:2143`）、`[digest] = {**cur, "job_id": None}`（`:2198`）。
- `job_id` 读取点 **4 处**：`:2137`（`plan.get("job_id")` —— `None` 是 **falsy**，故走 else 分支**立刻预留新 id**）、`:2180`（`str(plan.get("job_id")) or _recovery_job_id()` —— 其上游 `:2145-2148` 已保证 `plan is not None` 且 `plan["job_id"]` 非空，故不会把 `str(None)`="None" 当 job 名）、`:2197`（`str(cur.get("job_id")) == job_id` 身份比对）、`:3537`（**另一张表** `_vocab_apply_job`，同名不同物）。
- **不流向取参层**：`_RECOVERY_PLANS` 的值只被 `_handle_retry_plan_post`／`_handle_retry_batch_post` 内部消费，从不作为 `_take_*` 的 `params` 实参。
- **不流向出网**：AST 扫出 `**plan`／`**cur` 只出现在**表写入**，无一进 `return`／响应构造（`:2199` 的 500 响应只带 `error` 人话）；`plan_token` 明文只存在于 `_handle_retry_plan_post` 的返回值（`:1929`），计划表里存的只有 `sha256(token)`。
- **运行时验证（`cr4_plan_probe.py` 3/0）**：把计划表种成 `job_id=None`，用「`digest = sha256(token)`」反查命中该计划，调**真** `_handle_retry_batch_post` → 哨兵被当作"**未占位**"，`plan["job_id"]` 被替换为新预留 id `rec-20260914T165110-cd555ee10a`；该次响应（409 诊断不可用）**不含 `job_id` 字段、不含字符串 `"None"`**。
→ **判为不同类成立**：它是内存释放占位哨兵，不间接流向任何取参层或出网路径。

### 3. P2-三1 真闭环 —— **闭环**（node 桩抽真源码，`cr4_front_probe.py` 27/0）

| 场景（复核三原始口径） | 本次实测 |
|---|---|
| **C**（任务在另一个 `data_root` 在跑：POST 409 running → status 409） | 文案 = 「最近一次任务属于另一个数据目录…请核对数据目录后重查」（**非**「正在导入…」）；`TIMERS=0`；按钮 `disabled=false`；`vocabApplyRunning=false`（**不留半状态**）；文案含可操作指引 | ✔ 原「停在假象＋按钮点不动」**不可复现** |
| **D**（409 → 接管时任务已跑完，status 回终态） | 直接落终态「已导入3条…」；**非**「正在导入…」假象；按钮复原＋`TIMERS=0`＋`running=false` | ✔ |
| **G**（409 → 同目录真接管） | `vocabApplyJobId==="job-G"`、`TIMERS>0`、文案「正在导入」、按钮保持禁用（防重复提交） | ✔ 接管路径未被修复打坏 |
| **冷启动反例 1** 本页从未提交过 + 接管遇 409 | 文案 `""`、`TIMERS=0`、按钮**原样**、`running=false`；且**确实发出了**查询请求（不是压根没查） | ✔ **不误报** |
| **冷启动反例 2** 未提交过 + 后端有终态 job | 不渲染别人的结果（文案 `""`、无计时器） | ✔ 「终态不打扰」保持 |
| **冷启动反例 3** 未提交过 + `job:null` | 静默、无文案、无计时器 | ✔ |
| **冷启动反例 4** 未提交过 + 相对目录 | **零请求**、无文案（P3-三1 本地拦生效） | ✔ |
| **`vocabApplyRunning` 泄漏反例 R1** 提交 400 后 | `running=false`、按钮复原、有人话 | ✔ |
| **R2** 紧接着做冷启动续看（遇 409） | **不嘴硬报错**（文案 `""`、无计时器）——证明 R1 的清标志真的生效，冷启动未被误判为"本页提交过" | ✔ |
| **R3** 提交触发网络 reject（`catch` 分支） | `running=false`、按钮复原、文案含「失败」 | ✔ 三条清标志路径全覆盖（`:1537` 非 202/409running、`:1540` catch、`vocabApplyDropPoll`/`vocabApplyFinish` 出口） |

源码四出口逐一核对（`app/index.html`）：`:1449`（非绝对目录）／`:1461`（400/404/409）／`:1473`（`job:null`）／`:1478`（目录不符）**四条**均在 `if(vocabApplyRunning)` 时才 `vocabApplyGiveUp(...)`（人话＋复原按钮），`:1491`（终态）改走 `vocabApplyFinish(s)`；提交侧 `:1533-1535` 409 running **先落人话再接管**。与 builder 自报一致。
**旁证**：冷启动且后端**持续 5xx** 时不停表、进入容错重试、按钮始终可点、`running` 始终 false（见 P3-四1 的文案观察项）。

### 4. P2-三2 有牙 —— **真断言终态，且"有牙"已独立证明**

- **读断言**：`tests/selftest_p1_2_contract.py:1356-1368` —— `9g 提交成功 ⇒ 同目录一定能查到` 现在追加三条**终态**断言：`state=="done" and imported>=1`、终态文案不含 `ob_vault_root`、`vocab-user.json` 落该 tmp 数据目录；另有 `:1020-1040` 的 `8(P1-三1①)` 同口径四条。**不再是只断言 `job_id` 回显**。
- **有牙（系统 tmp 副本破坏法，未动仓库文件）**：
  - 控制组：`cp -R app src tests` 到 `/tmp/cr4_teeth.*` → `rc=0 / 379 PASS`。
  - 破坏组：只把该副本 `app/server.py` 的 `:3522-3532` 换回复核三所报**旧形态** `params = {**params, …, "ob_vault_root": vault_s}`（一处替换，脚本内 `assert count==1`）→ **`rc=1`**，**7 条断言 FAIL**：`8(P1-三1①)`×3、`9g 不带笔记库键的任务真的跑成功（终态 done、imported>=1）`、`9g 终态文案里没有 ob_vault_root 开发者口吻`、`9g 词库确实落到该 tmp 数据目录`、`9h 源码不再把可选键以 None 写回参数`。
  - 破坏后实测到的失败证据正是**原 P1-三1 症状**：`state='failed'`、`error='ob_vault_root 须为字符串（收到 空值 null）'`、`imported=0`。
  → **9g 会 FAIL，不是恒真**；且这条链路同时是"修复前必失败"的负对照。

### 5. P3-三1／P3-三2 —— **两条闭环**

**P3-三2（文案统一，`cr4_p3_probe.py` 34/0）** —— 同一入口 8 种坏法，同步/异步两路全 400，文案分三类但**主语全部是「数据目录」**，无一以裸键名 `data_root` 作主语：

| 坏法 | 出网文案（实测） |
|---|---|
| 缺键 | `请先选择数据目录（data_root 必填，绝对路径）再提交` |
| 空串／纯空格 | `请先选择数据目录（data_root 不能为空，绝对路径）再提交` |
| `null`／整数／数组／布尔 | `数据目录须为绝对路径（收到 空值 null／整数／数组／布尔值），请先选择数据目录再提交` |
| 相对路径 | `数据目录须为绝对路径，请点浏览重选` |

（括号内出现 `data_root` 仅为**字段名提示**，不是口吻混用；复核三所报「**data_root** 须为字符串（绝对路径）（收到 整数）」已 0 命中，`"data_root 须为" not in error` 全部成立。）

**P3-三1（相对路径本地拦，与后端同口径）**：
- 后端口径 = `os.path.isabs`（经 `normalize_path` strip＋去引号后判定，`app/server.py:297-298`）；前端口径 = `isAbsRoot(p) = p.charAt(0)==="/"`（`app/index.html:1384`）。**10 例逐例对照全一致**（`/x`·`/`·`//x`·`/x/` → true；`rel/x`·`./x`·`../x`·`~/x`·``·` tmp/x` → false）。
- 提交侧 `:1517-1520`、续看侧 `:1449-1454` 两处本地拦：**实测零请求发出**、给人话、不留半状态。
- **复核三所述"污染场景"已堵**：框清空但 `effectiveDataRoot` 被相对值污染时（`loadVocabCandidates` 回包原样回显相对值）→ 实测**零请求**＋人话「数据目录须为绝对路径…」（不再靠服务端 400 兜）。
- **一处可议**（→ P3-四2）：前端不 `stripQuotes`，故用户输入带引号的绝对路径 `"/tmp/x"` 会被本地拦住，而后端 `normalize_path` 会接受 —— 方向是**更严**（fail-loud，不会静默放过），不构成绕过。

### 6. 无新回归 —— **无倒退**（范围已钉到 hunk 级）

**A. 范围钉死（比漂移算术更强的证据链）**
先用上一位复核者留在系统 tmp 的产物**重建复核二版实体**并校验其真实性：
- `p12_server.diff`（00:15）＋ `p12_index.diff`（00:15）经 `git archive HEAD` + `patch -p1` 应用成功；重建版 `server.py` 5817 行、`index.html` 1898 行；numstat 反解 **+642/−197** 与复核二自报**逐字一致**；且重建版内 bug 形态落在 `:3496`（复核三快照 `:3513-3515`，差 +18 恰等于复核三自报的本轮净增，**两版口径互洽**）。
- `v2o_p12c.js`／`v2o_p12d.js`（00:24/00:26，二者 md5 相同 `7ce1376e…`）为**复核三版** bundle：含 `effectiveDataRoot`×5、**不含** `vocabApplyGiveUp`／`isAbsRoot`／`vocabApplyFinish`（三个恰为本轮新增符号）。

**B. `server.py`：复核二 → 当前，全文件只有 4 个 hunk（+40/−5）**

| hunk | 位置 | 内容归因 |
|---|---|---|
| `@@ -274,6 +274,31 @@` | 新增 `_take_required_data_root`（`:277-299`） | 复核三本轮新增（+16）＋本轮 docstring 的 P3-三2 段＋类型错文案自判（**本轮**） |
| `@@ -3231,7 +3256,8 @@` | `:3260` 同步内核调用点改 `_take_required_data_root` | 复核三本轮（+1） |
| `@@ -3472,7 +3498,8 @@` | `:3502` 异步壳调用点同上 | 复核三本轮（+1） |
| `@@ -3492,9 +3519,17 @@` | `:3522-3532` apply 可选键归一（4 行注释＋`job_params` 构造＋`if vault_s` 按需补） | **本轮**（+12/−3） |

即：`+40/−5` − 复核三自报本轮 `+18/−0` ＝ **本轮 `+22/−5`**，且 **全部落在"apply `data_root` 取参＋可选键归一＋`data_root` 文案"这一处**。→ 除这 4 个 hunk 外，`server.py` 与复核二版**逐字节相同**，故**复核二的 8 项闭环实现不可能被本轮破坏**。

**C. `index.html`：本轮函数级逐字比对（bundle 抽真源码 vs 当前源文件）**

| 函数 | 判定 |
|---|---|
| `dataRoot`／`reapplyPayload`／`vocabJobDataRoot`／`vocabApplyStatusQuery`／`vocabApplyDropPoll`／`vocabApplyStartTimer`／`vocabApplySetText`／`vocabApplyStopPoll`／`renderVocabApplyProgress`／`renderVocabApplyFinal`／`vocabApplyNotePollFailure`／`sameDataRoot`／`loadVocabCandidates`／`setCandidateControls` | **14 个逐字未变** |
| `pollVocabApplyStatus` | −3/＋1：终态块收敛为 `vocabApplyFinish(s)` |
| `resumeVocabApplyPoll` | 四出口补人话＋复原；`if(!root)return` → `if(!isAbsRoot(root)){…}`；终态走 `vocabApplyFinish` |
| `applyVocabCandidates` | ＋P3-三1 绝对路径本地拦（4 行）＋409 running 先落人话（1 行） |
| `refresh` | 仅 ＋2 行注释（P3-三3 只记不修） |
| 新增 `vocabApplyGiveUp`／`vocabApplyFinish`／`isAbsRoot` | 本轮三个新符号 |

全文件 `diff`（重建版→当前）的 10 个 hunk 旧坐标全落在 `1261–1596`（即 vocab-apply 状态变量／清单加载／轮询／续看／提交／`refresh` 的 `/api/start` 处理），**无一处落在其它 UI 区域**。`index.html` 净增 = 1971 − 1898 = **+73**，其中复核三自报本轮 +28 → **本轮 +45（+49/−4）**，与"复核三快照 +106/−13 → 当前 +155/−17"两种算法**互相吻合**。

**D. 语义/外壳在位（`cr4_reg_probe.py` 31/0，真 handler＋随机端口）**
- P0 已验收语义**未回退**：`_FAIL_SEMANTICS`、`SOURCE_LOCATION_REVIEW`（≥3 处：诊断条／计划排除／gate 拒）、三策略 `RETRANSCRIBE/REUSE_DERIVED/PUBLISH_ONLY`、四层状态 `RECOVERY_JOB_FINAL`、`_recovery_gate_ok`、`BLOCKED_OUTPUT_CONFLICT`（No-Clobber）、`idempotent` 幂等标记、`RECOVERY_RESULT_FIELDS` 字段契约、`RECOVERY_CANDIDATES_ABSENT` 哨兵、`_recovery_atomic_write` 原子写 —— **逐项在位**。
- `_take_required_data_root` 全仓命中 **3 处**（1 定义 ＋ 2 调用＝`:3260`／`:3502`），**未波及其它入口**。
- `Handler.do_GET` 外壳**未吞 404／静态资源**：`GET /` → 200 `text/html`（含 `data-theme="light"`）；`/index.html` → 200；`/nope.css` → **404 结构化 JSON**；`/favicon.ico` → 404；`POST /nope` → 404；POST 坏体 → 400 人话；`GET /api/note` 缺参 → 400；`GET /api/vocab|candidates|status(相对→400)|start|failures/diagnosis` 返回体形状未变（未被外壳改成 500）。
- 主题默认浅色未回退（`app/index.html` 静态首帧 `data-theme="light"` ＋ HTTP 实测首页含该属性）。
- 只读红线：`app/presets` 全树字节零改动；`/tmp` 之外的仓库文件零写入（`git status --porcelain` 与复核前一致）。

### 7. 测试质量 —— **合格**

- **三套自测复跑（`~/.local/bin/python3.12`）**：`selftest_p1_2_contract.py` **rc=0／379 PASS／0 FAIL**、`selftest_p1_2_frontend.py` **rc=0／41 PASS（FRONT ALL PASS）**、`selftest_v26_presets.py` **rc=0／58 PASS** —— 与 builder/TM 自报 **379／41／58 逐字一致**。
- **本轮新增断言逐条对账**（与复核三版运行输出 `p12_contract_run3.txt`(337)／`p12_front_run3.txt`(34) 的断言名做差集）：**新增 42 条 / 消失 0 条**（合同侧）；**新增 7 条 / 消失 0 条**（前端 S7 五场景）。与 TM 转述的「42＋7」**逐数吻合**。
- **非恒真**：AST/正则扫全文件 `check(x, True)` → **0 处**；新增 42 条全部为实测比对（HTTP 状态码＋响应体字段＋`tree_snapshot` 目录字节＋`_vocab_apply_job` 单例同一性＋`os.path.isfile` ＋源码文本守卫）。前端 7 条查 **POST body 原文／URL query 原文／TEXT 原文／TIMERS／disabled**。**无 `skip`、无 `sys.exit(0)` 早退**。
- **过宽「多值 or」未扩散**：全文件仍 **6 处**（`:345` `(404,409)`、`:633` `(400,500)`、`:648` `(400,500)`、`:708` `(400,409,500)`、`:810` `(409,202)`、`:1256` `(404,409)`），与首轮记录的 6 处**同量**，且**无一条落在本轮新增段**（新增段在 `:1013-1055` 与 `:1356-1419`）。
- **tmp 门**：`assert_tmp` 定义于 `:43`；`part1..part9` 每个用例函数体首行均有（`part8` 的 HTTP 用例 `:915` 在起服务之前；`part9` 的 `:1077-1079` 与 **`:1299` `assert_tmp(cand_root,"part9.cand")`** 在所有 9g/9h handler 调用之前）；`make_data_root:118` 亦过门；`part8` 断言 `port != 8765 and port != 0`。
- **前端用例查真源码原文**：harness 由 `extract(src,name)` 花括号配对**逐字抽** `index.html` 真源码（`extract` 找不到函数即抛 `AssertionError`，改名会当场失败），`FUNCS` 已含本轮三个新符号；断言查 body/URL 原文而非桩内自造值。我方**另写一份独立抽取器**（`cr4_front_probe.py`）复现同结论，两套互证。

---

## 二、返工项逐条闭环判定（5/5）

| # | 复核三编号 | 判定 | 关键证据 |
|---|---|---|---|
| 1 | **P1-三1**（笔记库框留空→apply 必失败） | **闭环** | `app/server.py:3522-3532` 按需补键；真 HTTP ①无键→202→`done`/`imported=1`；①b worker 实收 params **无该键**；②6 类坏值全 400（未放宽）；③空串/空格按缺省→done；④同步入口 null→400、空串/字符串→200；破坏法复现原症状（7 FAIL） |
| 2 | **P2-三1**（接管路径静默停滞） | **闭环** | 四出口＋提交侧全部"先落人话＋复原按钮"（`index.html:1449/1461/1473/1478/1491/1533-1535`）；node 桩 C/D/G 三场景＋4 组冷启动反例＋3 组 `running` 泄漏反例 **27/0** |
| 3 | **P2-三2**（9g 只断言 `job_id`） | **闭环且有牙** | `:1361-1368` 真断言终态 `done`＋`imported>=1`＋无开发者文案＋词库落盘；tmp 副本改回旧形态 → **rc=1、7 条 FAIL**（含该终态断言） |
| 4 | **P3-三1**（相对路径污染 `effectiveDataRoot`） | **闭环** | 后端 `isabs`／前端 `isAbsRoot` 10 例同口径；提交＋续看两处本地拦；污染场景**零请求**＋人话；10/10 探针通过 |
| 5 | **P3-三2**（`data_root` 文案口吻不一） | **闭环** | 8 种坏法同步/异步两路文案全以「数据目录／请先选择数据目录」起头；复核三所报裸键名句式 **0 命中**；34/0 |

**未纳入本轮范围（如实记账，不计失败）**：首轮 **P2-7**（前端 `/api/retry` 不带 `data_root`）仍挂账（需先扩 `/api/retry` 契约，Change B 级）；复核三 **P3-三3**（续看只在本轮 refresh 里调一次，当前两真源恒有值 → 不可达）**只记不修，仍在**，本轮已在 `index.html:1663-1664` 加注说明。

---

## 三、新发现问题（分级）

### P0 / P1 / P2 —— **均无**

### P3（新，不阻断）

- **P3-四1｜冷启动（本页从未提交过）时若状态接口持续 5xx，文案会断言「后台任务可能仍在跑」。**
  - 实测（抽真源码＋node 桩，冷启动 + status 持续 500）：`resumeVocabApplyPoll` 的 `x.code!==200` 分支（`index.html:1465-1469`）冷启动也会**开表重试**，10 次后由 `vocabApplyNotePollFailure` 停表并落文案：`进度读取连续失败10次，已停止自动刷新；后台任务可能仍在跑，请点「刷新」或稍后重开页面查看` —— **本页从未提交过任何任务**，"后台任务可能仍在跑"是**无据断言**（按钮始终可点、`running` 始终 false，无实质伤害）。
  - 归属：该分支属**复核二轮**引入的轮询容错面（本轮未动，`git` 重建版对比：`vocabApplyNotePollFailure` 逐字未变），复核三 §4 判其"已带人话"**不与之矛盾**（此处只补记冷启动口径）。建议：冷启动（`vocabApplyRunning===false`）停表文案改为中性说法（如"进度读取连续失败，请点「刷新」重试"）。
- **P3-四2｜前端 `isAbsRoot` 不做 `stripQuotes`，比后端更严一格。**
  - 后端 `normalize_path` 会去掉首尾成对引号（`app/server.py`），故 `"/tmp/x"` 后端可接受；前端 `isAbsRoot(p)=p.charAt(0)==="/"`（`index.html:1384`）会因首字符是 `"` 而**本地拦住** → 用户输入带引号的绝对路径会收到「数据目录须为绝对路径…」。
  - 方向是**更严**（fail-loud、不自静默放过），且 UI 主路径是「浏览」选目录（回包不带引号）→ 记 P3，建议前端复用 `stripQuotes` 后判定，或文案补一句"不要带引号"。
- **P3-四3｜（历史遗留，非本轮引入）批量预览令牌在"确认失败后"会被占位毒化，随后的提示文案误导。**（本轮排查 `_RECOVERY_PLANS` 哨兵时顺带发现，按"发现即记"落账）
  - `_handle_retry_batch_post` 在 `:2142-2143` 先预留 `job_id` 写回计划表；若随后在 `:2146-2179`（计划过期／目录不符／执行集合不符／**诊断不可用**／指纹漂移）任一分支返回 409/500，**预留 id 已留在计划表** → 用户对同一 token 再确认时走 `:2156-2165` 的 `existing` 分支，因 job 文件不存在而永远回 `409 该预览正在执行中（零新增），请稍后用任务状态查询`，直到 token 过期（10 分钟）；而真实原因是"上一次没执行成"。
  - 归属证据：`git show HEAD:app/server.py` 中同样存在 `_reserved`（`:1817`）与同一句文案（`:1839`），**属 P0-2 既有设计，本轮未改动**（本轮 `server.py` 4 个 hunk 全在 apply 侧，见 §6B）。可达性：需"预览成功 → 确认时诊断恰好不可用/指纹漂移"这一瞬态组合；用户按提示"重新预览"即可恢复 → **P3**。建议：非成功出口把预留位清回 `None`（或文案改成"上一次确认未执行成功，请重新预览"）。

### 承接（如实记账）

- 首轮 **P3-1～P3-5** 仍在（含 `indices: []` 变 400、`_diag_redact_path` 末 3 段带用户名、`tests/selftest_p1_2_contract.py:515` 断言名名实不符）。
- 复核二 **P3-新2～P3-新5**（反斜杠不脱敏／二次脱敏吞中文词／`9d` 依赖 `TMPDIR != realpath(TMPDIR)` 平台形态／既有 QA 报告 A4/U8/U6 步骤因契约变更失效）仍在，建议 qa 复验时按新契约更新步骤。
- 复核三 **P3-三3**（只记不修）仍在，已加注。

---

## 四、回归结论

- **本轮返工本身：无新增回归。** 硬证据＝§6 的**重建快照 hunk 级归因**（`server.py` 复核二→当前仅 4 hunk `+40/−5`，减复核三自报 `+18/−0` 后本轮 `+22/−5`，且 4 个 hunk 全在 apply `data_root` 取参／可选键归一／文案一处；`index.html` 14 个相邻函数**逐字未变**、5 处变化＋3 个新符号全在 vocab-apply 块内）＋复核二 8 项闭环实现**不可能被触碰**（源码级在位复核通过）＋ P0 三段语义在位（源码级 12 项全 PASS）。
- **`Handler.do_GET` 外壳**：未吞 404／静态资源，各 GET 端点返回体形状未变（`/`→200 html、`/index.html`→200、`/nope.css`・`/favicon.ico`→404 结构化、`POST /nope`→404、坏体→400）。
- **三套自测**：`379／41／58`，rc=0，与自报逐字一致；断言增减对账 **+42／+7，消失 0**。
- **只读红线**：`app/presets` 字节零改动、仓内零写入；七个探针全部落 `/tmp`；**未起 8765**（随机端口 + 逐次断言 ≠8765；实测无监听）。
- **本链状态：复核三的 1×P1＋2×P2＋3×P3 全部收口（P3-三3 为"只记不修"加注项）；本轮新发现仅 3×P3，无阻断。**

---

## 五、未覆盖项（本复核未验，不得推断为通过）

1. **真实 whisper／真实批量恢复执行级链路**（真引擎、真实 16 条、长视频、1200 篇量级）——全程合成数据；`_exec_*` 策略体只做源码级在位核对。
2. **真机 UI 目检**（未起 8765、未点页面）——前端结论来自"抽真源码＋node 桩"与 HTTP 层探针，**不替代真机**；建议 qa 真机复现三条：① 清空笔记库框 → 应用所选错词（应出进度与 `done`，不得报 `ob_vault_root…`）；② A 目录起任务 → 改框到 B → 再点应用（应给人话、按钮可点，不停在"正在导入…"）；③ 数据目录框留空 → 点应用（应正常提交，进度可见）。
3. **多标签页真并发**（两个真浏览器标签页抢同一 backend）：job_id/dir 隔离只做函数级与桩级验证。
4. **挂载点／网络卷／非 APFS 卷**：符号链接与大小写只有本机结论。
5. **`/api/failures/diagnosis` 与 `/api/failures/retry-batch/status` 的前端使用场景**（仓内无调用点），其加严只经 handler/HTTP 层验证。
6. **用户真实视频目录与 Obsidian 库**（红线禁写，未读未写）；`data/state.db` 真源仍未核（继承 HANDOFF 未决项）。
7. **`src/` 底座**只读复用未改。
8. **重建快照的字节级完全性**：本轮范围归因依赖系统 tmp 中上一位复核者留下的 `p12_server.diff`／`p12_index.diff`／`v2o_p12c.js`；三者已用"numstat 逐数吻合＋bug 形态行号互洽＋新符号有无"三重校验，但**未逐字节哈希比对**（原快照非 git 对象，无权威哈希可比）。

---

心跳：目标＝独立复核 P1-2 第二轮返工（复核三 1×P1＋2×P2＋3×P3）是否真闭环｜结论＝**PASS（5/5 闭环；无 P0/P1/P2；新发现 0×P0＋0×P1＋0×P2＋3×P3；无新增回归）**｜下一步＝交 qa（建议真机按 §五·2 三条复现）→ supervisor 复检。
