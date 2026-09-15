
# CODE REVIEW

- Task: DEVELOP P1-9（在制品接续落盘）——笔记库已有同名笔记 → 跳过转写，whisper 零调用
- Commit: `3d501a5`（基线父提交 `378eac2`；冻结 tag `v1.0-mac`＝`5f06fdb`）
- Reviewer: code-reviewer（本窗口直派，`opencode/muse-spark-1.3-contributor-free`）
- Result: **过（PASS）**——P0 ×0／P1 ×0／P2 ×1／P3 ×6；打回条件不成立
- 复核日期：2026-09-15

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。
> 复核红线遵守：全程**未改任何业务代码**（`app/`、`src/`、`tests/` 零写入，工作树复核前后均只有 `?? .codebuddy/`）；未 push；未碰 `~/Downloads/需转录视频`、`~/Downloads/暂不转录视频`、`~/Documents/ob 仓库`；夹具全在 `/tmp`（`p19rev_*`／`p19edge_*`，跑完即删）；未用 `git checkout` 还原任何文件。

---

## 一、改动实测（先核口径，再复核）

`git show --numstat 3d501a5`：

```
31   9   app/index.html
171  6   app/server.py
17   4   docs/handoff/HANDOFF.md
177  0   tests/selftest_p1_2_contract.py
50   1   tests/selftest_p1_2_frontend.py
```

与 HANDOFF §一.4 自报的 `+171/−6`、`+31/−9`、`+177/−0`、`+50/−1` **逐项一致**；`src/`（含 `watcher.py`、`reconcile.py`）零命中，与「未触碰 watcher」自述一致。

---

## 二、独立复算（自建夹具，不看现有断言）

夹具：本窗口 `.venv`，`tempfile.mkdtemp(prefix="p19rev_")`；真监听投递（`stage5.watcher.Watcher._on_fs_event`）落真 `source`/`processing_runs` 行，真 `stage2.instance.acquire`＋`init_db`；引擎用计数 stub 替换 `_transcribe_audio`（只数调用，不跑 whisper）；首行断言 `data_root` 在 tmp 下。脚本 `/tmp/p19rev_probe.py`、边界补刀 `/tmp/p19rev_edge.py`（均外置，不入库）。

**结果：51 项断言全 PASS（FAIL 0）**（下面每项均为实测，非读码推断）。

### 主路径 A：目标笔记已存在 → SKIPPED，whisper 真零调用（R1，10 项）

| 断言 | 证据 |
|---|---|
| `state==SKIPPED` | `app/server.py:4842`（门在 `:4840-4841`） |
| 引擎零调用（stub 计数 `[]`） | 门体在转写调用 `:4917` **之前**（`:4836-4871` vs `:4917`） |
| `whisper_calls==0` | `:4847` |
| 既有笔记字节不变（No-Clobber 未破） | 夹具 `vault/same.md` sha256 前后一致 |
| 不建 `raw/`、不建 `asr/` | 门内不执行 `:4886-4887` 的 `os.makedirs` |
| 人话含「已存在／未覆盖」 | `:4844-4846` |
| 只落一条轻量 receipt（state=SKIPPED） | `:4851-4869` |
| 磁盘可查、重启不回落排队中 | `_scan_disk_states` `:1004-1009` |

### 主路径 B：无同名 → 正常 PUBLISHED（R3，5 项）

`calls==1`、`state==PUBLISHED`、`vault/fresh.md` 真落盘、命名＝去扩展名单 `.md`、另一条既有笔记仍未被动 —— 全 PASS。

### 补做的三条独立路径

- **R4 子目录**：`sub/nested.mp4` 且 `vault/sub/nested.md` 已存在 → SKIPPED、零调用、字节不变（证明命名真源带子目录，不是扁平拼名）。
- **R5 未配笔记库**：`_process_one_run(..., ob_vault_root=None, ...)` → 引擎照跑、`RENDER_ONLY`，**不误跳**（`_vault_publish_target` `:1082` 的 `not vault_root` 兜底生效）。
- **R6 转写途中才冒出同名笔记**（stub 侧写文件模拟）→ 入库处撞名：state `PUBLISH_BLOCKED`、文案含「未覆盖」且**不含「权限」**（`:5100-5107`）、库里那篇内容未被覆盖 —— 走的是**真** `stage4.initial_publish` 状态码，不是合成 receipt。
- **E2/E3 边界**：`vault=""` 不误跳；`vault == input_root`（笔记库＝视频目录）正常 PUBLISHED，无异常。

### 命名真源是否真与入库同一函数（重点风险①）——**成立**

- 门侧：`_vault_publish_target`（`:1073-1089`）→ `_app_resolve_canonical`（`:1040-1070`）。
- 入库侧：`_process_one_run` `:4978-4980` 取 `source_rel＝_app_resolve_canonical(...)["source_relative_path"]` → `:5091` `initial_publish()` → `src/stage4/publish.py:169-170` → `src/stage4/publish_commit.py:118-136 canonical_path_for`。
- **等价性实测**：对 9 种命名（`a.mp4`/`09.xxx.mp4`/`sub/nested.mp4`/`sub/deep/名字 带空格.MP4`/`no_ext`/`a.b.c.mov`/`中文名.mp4`/`UP.MP4`/`x.mkv`）逐一比对「门算出的目标」与「入库真目标」，**9/9 全等**（R2）；实跑路径再验一次「实际落点 == 门算目标」（R3 末项）。
- 结论：**没有第二套命名规则**；`_app_resolve_canonical` 内部 `app_single_ext_fixed` 分支在本仓命名口径下不触发（即便触发，门侧与入库侧同用该函数，仍同源）。

### 队列／统计口径（R8，5 项）

`queue.skipped` 单列 ≥2；`failed` **未**被 skipped 污染（本夹具唯一 failed＝R6 那条 `PUBLISH_BLOCKED`，实测 `failed==1` 而非 3）；`total == done+failed`（skipped 不计入，`server.py:1362/1365`）；`processed_n` 含 skipped（`:1430`）；详情区该项 `state==SKIPPED`。

### 诊断（R7，10 项，用**真 data_root** 而非合成 manifest）

跳过项 `action_category==SKIPPED`、展示态 `SKIPPED`、`display_persisted_mismatch==False`；撞名项 `root_cause==PUBLISH_TARGET_EXISTS`、展示态 `SKIPPED`、`confidence==HIGH`、整条 JSON **不含「权限」**；`counts.skipped_note_exists>=2`；类别取值全在 `DIAGNOSIS_ACTIONS` 枚举内（`:1508` 已加 `SKIPPED`）。

---

## 三、反向证伪（变异测试）：**6 条 / 6 条全有牙**

| # | 变异做法 | 预期（证明哪条断言有牙） | 实测 |
|---|---|---|---|
| M1 | 摘掉第 0 道门（`_vault_note_already_there→None`） | A 的「零调用」必须挂：引擎真被调 | 有牙：`calls==1`，且要白跑整轮才在入库处撞名（`PUBLISH_BLOCKED`） |
| M2 | **放宽** `_PUB_TARGET_EXISTS_STATUSES`（加 `BLOCKED_OUTPUT_FS`） | 窄集合有牙：真权限/路径问题会被冒充成「已有同名笔记」 | 有牙：基线根因 ≠ `PUBLISH_TARGET_EXISTS`；放宽后 → `PUBLISH_TARGET_EXISTS` |
| M3 | **收紧**（删 `CANONICAL_OUTPUT_EXISTS`） | 漏收有牙：真同名回落旧分支 | 有牙：`CANONICAL_OUTPUT_EXISTS` 基线判同名，收紧后不再判 |
| M4 | 命名真源改第二套：扁平化（丢子目录） | 子目录场景立刻漏判 | 有牙：`sub/nested.md` 算不出来 → 该跳的不跳 |
| M4b | 命名真源指错（恒指到某存在文件） | 误伤方向有牙 | 有牙：无同名也被误判 SKIPPED、引擎 0 次 |
| M5 | 把 `SKIPPED` 塞进 `FAIL_STATES` | 「skipped 不计入 failed」有牙 | 有牙：`failed` 立刻从 1 涨到 3 |
| M6 | `_scan_disk_states` 不认 SKIPPED（模拟重启、内存清空） | 「重启后仍显示已跳过」有牙 | 有牙：该项从详情消失、`skipped` 归 0（即回落「排队中」） |

> 仓库自带的两条反向牙（`contract` 16C：摘掉 vault 检查 → 引擎真被调；摘掉 `_manifest_last_receipt` → 回落 `UNKNOWN`）本次一并跑通，与我的 M1/M3 互为独立印证。

---

## 四、逐函数 AST 对账（`378eac2` → `3d501a5`，顶层定义 sha256）

- `app/server.py`：顶层条目 161 → 165；**新增 4**：`_manifest_last_receipt`、`_pub_target_exists`、`_vault_note_already_there`、`_vault_publish_target`；**删除 0**；**改动 7**：`_scan_disk_states`、`_listener_snapshot`、`_diag_action`、`_diagnosis_item`、`_handle_failure_diagnosis`、`_stage_text_zh`、`_process_one_run` —— 7 个全部是本功能声明范围内的函数，**无一处越界**。
- 点名核验「未触碰」：`_err_text` ✅、`_strip_paths` ✅、`_stale_source_reason` ✅、`_is_under_root` ✅、`_app_resolve_canonical` ✅、`_handle_retry_post` ✅、`_state_bucket` ✅、`_reapply_result_bucket` ✅、`_handle_clear_post` ✅、`_attach_completed_view` ✅、`_handle_status` ✅、`_transcribe_worker` ✅（全部源码段哈希逐字相同）。
- `_scan_disk_states` 虽被改，改动内容仅为新增 `elif st == "SKIPPED"` 分支（`:1004-1009`），成功/失败分支逐字未动。
- **两道发布门逻辑未动**：第一道（转写前，`:4874-4881`）与第二道（写库前，`:5075-5088`）代码块在 diff 中零改动（仅 `job_dir` 计算行上移到 `:4835` 供门 0 复用，语义等价）；`watcher.py`/`reconcile.py` 未入本提交。
- `tests/`：`contract` 仅新增 `part16_p19_note_exists_skip`＋`main` 挂一行；`frontend` 仅改 `layout_checks`。

---

## 五、重点风险逐条裁定

1. **①命名真源** —— ✅ 成立（见第二节，9/9 等价＋实跑落点比对）。
2. **②`_PUB_TARGET_EXISTS_STATUSES` 漏收/误收** —— ✅ 判定正确。与 `src/stage4/publish_commit.py:54-56` 常量及 `src/stage4/conflict.py:129-130`（exists→`BLOCKED_OUTPUT_EXISTS`，内容不同→`BLOCKED_OUTPUT_CONFLICT`）、`src/stage3/render.py:58`（`CANONICAL_OUTPUT_EXISTS`）逐码对上，**三码齐、无漏**；误收方向实测 `BLOCKED_OUTPUT_FS` 未混入，且 `BLOCKED_OUTPUT_ROOT`/`PENDING_PUBLISH` 同样在外（`:1108-1112` 注释与代码一致）。
3. **③SKIPPED 是否污染既有状态机与统计** —— ✅ 未污染。`_state_bucket` 早有 `"SKIPPED"→BUCKET_SKIPPED`（`:1911`）、`RECOVERY_JOB_FINAL` 早含 `SKIPPED`（`:1884`），本次无需改；全部 `_scan_disk_states` 其余调用点（`:2779/:2949/:3070/:5175/:5325/:6370`、`:6142`）均以 `DONE_STATES` 或 `REAPPLY_ELIGIBLE`（＝`RENDER_ONLY/PUBLISHED/PUBLISH_BLOCKED`）过滤，SKIPPED 进不去完成列表、进不去重跑/重入库；`_transcribe_worker` 的 `skip_old` 只认 `DONE_STATES`（`:5175`），跳过项不会被误当「已完成」；重试入口 `_handle_retry_post` 会 `discard` `_worker_done`（`:5539-5540`），用户删笔记后点重试能真正重跑。
4. **④脱敏红线** —— ✅ 无新增泄漏（P3-1 记录）。诊断侧全程脱敏（`_diag_redact_path`，`:1765/:1768`；item 字段表 `:1760-1797` 无 canonical 路径）；异常文本仍走 `_err_text`（`:399-415`，边界 E1 实测异常路径已被抹成 `…`）。唯一含绝对路径的是 SKIPPED verdict（`:4844-4846`）与详情区「库里已有」一行（`app/index.html:896-898`），但**与既有 PUBLISHED verdict（`:5097-5098`，同样回绝对路径）同一口径**，属历史既定，不是 P1-9 引入。

---

## 六、P0 / P1 Findings

- 无。

---

## 七、P2 / P3 Backlog Findings

### P2（1 条，非阻塞，不影响放行）

- **P2-1 同一条任务两处口径相反：「入库撞名」在队列算 failed、在诊断面板算 SKIPPED「不算失败」**
  - 证据：`server.py:122`（`FAIL_STATES` 含 `PUBLISH_BLOCKED`）、`:1349-1350`（failed 计数）、`:1356-1365`（total）；同时间在 `:1726-1727` 把 `PUBLISH_TARGET_EXISTS` 的展示态判成 `SKIPPED`。实测（R6/R8）：同一条 `late.mp4`，队列 `failed=1`、诊断 `display_state="SKIPPED"`、`root_cause="PUBLISH_TARGET_EXISTS"`。
  - 说明：`state` 仍留 `PUBLISH_BLOCKED` 是**有意设计**（`:5103` 注释：便于用「重跑」重排成稿后重入库），数据层无害（初稿保留、未覆盖）；但用户会问「这条到底算不算失败」。
  - 建议（二选一，需产品/用户拍口径，不属本链必修）：① 队列对 `PUBLISH_TARGET_EXISTS` 也单列 skipped；② 诊断展示态改回 `PUBLISH_BLOCKED`。

### P3（6 条）

- **P3-1 脱敏口径**：SKIPPED verdict 回既有笔记绝对路径（`server.py:4844-4846`，经 `details_by_run` 出网）；与 PUBLISHED（`:5097-5098`）同口径，非新增。若要收紧，建议连同 PUBLISHED 一起改成 basename（跨链改动，需用户点头）。
- **P3-2 「已跳过」与「成功」同色**：`app/index.html:464-468` 的 `stClass` 只把「失败|受阻」判红，其余落 `st-ok`（绿），「已跳过（笔记已存在）」实测为绿 —— 建议加一个中性色，避免读成「已处理好」。
- **P3-3 门序**：第 0 道门（`:4840`）在第一道门「源未稳定」（`:4874`）**之前**。与 P1-1 已知限制（长停顿→半截稿落 vault、完整稿被 No-Clobber 挡）叠加时，会出现「源仍在写 + 库里已有半截同名笔记 → 直接 SKIPPED、不再自动重排、也不产生完整初稿」。本次未实测该叠加场景（静态推演），建议后续把「源未稳定」判据提到门 0 之前，或在已知限制里写明。
- **P3-4 非「同名」族仍用旧文案**：`PENDING_PUBLISH`（在途）、`BLOCKED_OUTPUT_FS/ROOT`（真权限/卷问题）落到 `:5108-5110`，文案仍是「检查笔记库权限后点重试」——P1-9 只改了「同名」这一支，这几类仍可能误导（与本次「文案不再误导」的目标留了个口子）。
- **P3-5 同名目标是「目录」**：`vault/x.md` 若是目录，`os.path.isfile` 为假（`:1103`）→ 不跳过 → 入库侧抛 `Is a directory`，落到 `:5126-5128`「笔记库不可写：…检查库路径权限」（边界 E1 实测）。P1-9 未新增此问题（改前同样如此），建议后续给「同名但不是文件」单列一句人话。
- **P3-6 历史挂账（不属本链）**：`contract` 15k「收不掉时 `is_running()` 仍为 True」flaky（与 P3-e `shutdown` 谎报 `reconciler_stopped` 同源）；仓库至今无依赖声明文件。

---

## 八、自测基线复核（本窗口 `.venv`，CPython 3.12.13）

| 套件 | 结果 |
|---|---|
| `.venv/bin/python tests/selftest_p1_2_contract.py` | **600/600 全 PASS，rc=0**（本次跑未复现 15k flaky） |
| `.venv/bin/python tests/selftest_p1_2_frontend.py` | **全 PASS**（含 S13：已跳过不画失败红、不进批量重试、监听脱钩、反向证伪） |
| `.venv/bin/python tests/selftest_v26_presets.py` | **58 全 PASS，rc=0** |

按任务书：15k flaky 属已挂账的时序敏感项（P1-9 未触碰 `watcher.py`，非本次引入），**不作为打回依据**；本次一次跑过、未复现，如实标注。

## 九、未覆盖（如实标注，不推断为通过）

- **真实 whisper 端到端**：全部用计数 stub 替引擎（要证的是「零调用」，stub 正合适）；真实视频下的跳过/撞名路径未跑真模型。
- **真机 UI 目检**：前端只过源码桩（`frontend` 套件 S13）；`SKIPPED` 行色/文案/toast/详情区重试入口未做浏览器目检（P3-2 即由此提出）。
- **P3-3 叠加场景**（半截稿 + 源未稳定）未实测。
- **Windows**：不在本链范围（`docs/pm/WINDOWS-MIGRATION-PLAN.md` 只出计划）。

## 十、结论

**PASS（放行）**。第 0 道门、命名真源、状态码族、SKIPPED 统计口径、诊断归类与文案四处改动均经独立复算（51/51）与双向变异验证（6/6 有牙），AST 对账证明未触碰无关函数与两道发布门；无 P0/P1；P2-1（队列 vs 诊断口径相反）与 6 条 P3 记 backlog，建议 qa/supervisor 按同一口径复验。

（复核全程未改业务代码、未 push、未碰用户真实目录。）
