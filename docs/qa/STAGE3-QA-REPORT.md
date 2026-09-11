# QA-REPORT｜Stage3 S3-T06 验收套件 + §72子集门（Video2Obsidian V1.8 §69）

- QA：qa（opencode-go/glm-5.3-flash，本窗口 subagent；未改业务代码，只写本报告）
- 被测：`src/stage3/`（artifact_commit.py/normalize.py/render.py/derive.py/lineage.py/__init__.py）+ `src/stage1/`（prepare/commit 只读复用：validate_raw_artifact/guarded_open_raw_for_write）+ `src/stage2/`（store/source/runs/instance 只读复用：open_db/upsert/AUTO Run/锁）
- 计划：`docs/pm/STAGE3-PLAN.md` S3-T06（P0-1~P0-8；Case 4/5/6 + lineage 并入；合成副本 + canonical 诱饵；禁真实长视频；坏例只看 exit 码）
- 基线：V1.8 §72 Implementation Acceptance Gate（Stage3 子集：Correction 不重调 Whisper / Raw 不变 / 新 NormRev / Formatter 只建新 RenderRev / Run 不回滚 / PREPARED Receipt / Hash Validation / SQLite Forward Repair / Raw Immutable）
- QA 执行目录（仓库外）：`/tmp/s3qa/`（happy/case4/case5/recover/tmponly/missing 各独立 data_root + 合成 `.bin` 副本 + 诱饵 md + `s3qa_results.json`；仓库内零写盘除本报告）
- **结论：PASS（happy 1 遍 + 异常 6 个全过 + lineage 并入，39/39 断言双轮稳定，Runner exit 0；坏例只看 exit 码：tamper exit 1=ArtifactInvalid、guard exit 2=RawImmutableError；publish/archive 恒 0；Whisper 恒 0；结论只落本报告）**

## 1. 输入复核（src/stage3 落盘 6 文件，只读消费）

- `artifact_commit.py`（S3-T01）：tmp→flush→fsync→schema 校验→expected hash 预持久化（中央 artifacts PREPARED）→atomic rename→fsync(parent)→final 校验→Manifest COMMITTED→SQLite COMMITTED；三分支 recover（Final 在 Repair Forward / 仅 tmp 续 Commit / hash 不等判无效）；成功字典带 `whisper_calls=0`。
- `normalize.py`（S3-T02）：§29 六字段 profile hash + 确定性 Correction 纯函数（corr-v1/v2 冻结表）+ PENDING→NORMALIZING→COMMITTING→COMPLETED；行写中央 `normalization_revisions`，变迁记 `state_events`；Run 行不碰。
- `render.py`（S3-T03）：§30 五字段 profile hash + `render_paragraphs`（§47 优先级）+ PENDING→RENDERING→ARTIFACT_COMMITTING→ARTIFACT_COMPLETED→PUBLISH_EVALUATION（verdict 只记录，零写盘；模块内无 `PUBLISHING/PUBLISHED`）。
- `derive.py`（S3-T04）：correction 变更→新 NormRev + 下游新 RenderRev；formatter 变更→复用同一 normalized ID、NormRev +0；全程 `whisper_calls=0`。
- `lineage.py`（S3-T05）：Manifest 追加 Receipt + Lineage Metadata（不改历史）；`get_lineage` 组装 Source→Run→Raw→NormRev→Normalized→RenderRev→Rendered→verdict，缺环标 missing 不编造，未知根 KeyError。
- 上轮 builder 自验 harness 路径与 6 异常清单：本轮工作区内未发现独立复跑脚本落盘（`src/stage3/` 仅 6 业务文件），QA 以公开 API 自建仓库外 Runner（见§3声明），异常 6 项按 S3-T06 口径覆盖（Case4/Case5/Case6/RepairForward/tmp-only/hash 篡改），符合“结论只落 qa 报告”约束。

## 2. 用例简表（坏例只看 exit 码）

| 用例 | 前置 | 动作 | 期望 | 实测 | exit 码 / Count | publish/archive | Whisper |
|---|---|---|---|---|---|---|---|
| HAPPY 派生链 | 新 root + 合成 `clip.bin` + COMMITTED Raw（合成）+ 诱饵 md | norm(create)→render(create, probe=诱饵) | NormRev COMPLETED + RenderRev PUBLISH_EVALUATION/`CANONICAL_OUTPUT_EXISTS` + PREPARED Receipt + hash 链一致 | 一致 | Runner exit 0；Norm=1/Render=1 | 0/0 | 0 |
| P0-1hz/纯函数 | 同上 | 改一字段算 hash + corr-v1 替换 | hash 变 + `VIP COIN→Vibe Coding`/`Ai编程→AI编程` | 一致 | — | — | 0（grep 无模型 import） |
| P0-2hz/段落序 | 合成 segments | 长停顿/强标点/目标长+弱标点/硬上限各一例 | 各 2 段（硬上限 ≥2） | 一致 | — | — | — |
| Case4 | HAPPY 基线后 corr-v1→corr-v2 | derive_on_correction_change | 新 NormRev + 新 Rendered + Raw/decoy 不变 + Whisper 0 | 一致 | Norm=2 | 0/0 | 0 |
| Case5 | HAPPY 基线后 para-v1→para-v2 | derive_on_formatter_change | 同 normalized ID + NormRev +0 + 新 RenderRev | 一致 | delta=0 | 0/0 | 0 |
| Case6 | 派生前后 | 查 Run + guarded 写 Raw | Run=COMPLETED 不变 + `RawImmutableError` + Raw 字节不变 | 一致 | guard 子进程 exit **2** | — | 0 |
| REC RepairForward | COMMIT 后 SQLite 回拨 PREPARED + 删 manifest 条目 | recover_artifact | COMMITTED + `prepared_final_exists_repair_forward` + Whisper 0 | 一致 | Runner exit 0 | — | 0 |
| TMP-only | prepare 后（final 缺） | recover_artifact | COMMITTED + `prepared_tmp_only_continue_commit` | 一致 | Runner exit 0 | — | 0 |
| HASH-tamper | COMMIT 后改 final 一字节 | recover_artifact（子进程） | `ArtifactInvalid`，永不视为有效 | 一致 | 子进程 exit **1** | — | 0 |
| LIN-full | HAPPY 库 | get_lineage(source) | 1 Raw→1 NormRev→1 Rendered + verdict + manifest 含 Receipt | 一致（n=1/r=1） | — | — | — |
| LIN-missing | 新 source 无派生 | get_lineage | 缺环 `missing` 非异常；未知根 KeyError | 一致 | — | — | — |
| STOP 门 | 全库 | grep + 行数 | 无 `run_asr_single_file`/`PUBLISHING`/`PUBLISHED`；publish/archive=0（3 库） | 一致（grep 空） | — | 0/0 | 0 |
| 回归 | 新 root | S2 startup + S1 gate 拒写 | startup 5 步有序 + 四表空 + 非法 Raw 拒收 | 一致 | exit 0 | 0 | — |

Runner：`/tmp/s3qa_run.py`（仓库外）→ `/tmp/s3qa/s3qa_results.json`（39 断言 JSON 已落盘，可复算；双轮 `TOTAL 39/39 exit=0`）；坏例子进程：`/tmp/s3qa_bad_tamper.py`（exit **1**=ArtifactInvalid）、`/tmp/s3qa_bad_guard.py`（exit **2**=RawImmutableError）。

## 3. 每用例明细（前置/动作/期望）

- HAPPY：前置见§2；动作 `create_normalization_revision`（corr-v1）→ `create_render_revision`（para-v1，probe=诱饵）；期望 NormRev COMPLETED（`normrev_656a…`）、RenderRev `PUBLISH_EVALUATION` + verdict `CANONICAL_OUTPUT_EXISTS`、中央 Norm/Render 各 1、artifacts 2 COMMITTED、state_events 9、Raw hash `af069148…` 不变、诱饵 `6169e9d0…` 不变、Run=COMPLETED、PREPARED Receipt 落盘、final hash `sha256:` 前缀；实测全中。
- P0-1/2hz：`mechanical_cleanup_version` 改一字段→norm hash 变；`paragraph_formatter_version` 改一字段→rend hash 变；corr-v1 对 `VIP COIN 与 Ai编程` 输出 `Vibe Coding 与 AI编程`；段落 4 例全中（gap8s 强停顿/强标点+target/弱标点+target/硬上限）。
- Case4：基线 NormRev `…656a` + Rendered `…02f0`；动作 corr-v2 派生；期望新 NormRev `…e336`、新 Rendered `…0d93`、Whisper 0、Raw/诱饵不变、Norm=2；实测全中。
- Case5：基线 normalized `…5507`；动作 para-v2 派生；期望复用同一 normalized ID、delta=0、新 RenderRev `…121a`、Raw/诱饵不变；实测全中（`derive` 内置 delta 非 0 即抛）。
- Case6：派生前后 Run=COMPLETED；`guarded_open_raw_for_write` 抛 `RawImmutableError`（子进程 exit 2）；Raw 复算不变。
- REC：人为制造“SQLite PREPARED + Final 在 + manifest 落后”；期望 `prepared_final_exists_repair_forward` + COMMITTED + Whisper 0；实测全中。
- TMP-only：`prepare_artifact`（PREPARED）后直接 recover；期望 `prepared_tmp_only_continue_commit`；实测全中。
- HASH-tamper：COMMIT 后 chmod 644 + append 一字节；期望子进程 exit **1** + `ArtifactInvalid`（判据只用 exit 码，不看打印）；实测全中。
- LIN：`get_lineage(source)` 返回 source/run/raw（hash + manifest 条目）/1 NormRev（含 artifacts 行 + file_present）/1 RenderRev（含 rendered 行 + evaluation verdict manifest 证据）；新 source 无派生→`normalization_revisions[0].status=missing`；未知根→KeyError。
- STOP：`grep run_asr_single_file src/stage3` 空；`render.py` 无 `PUBLISHING`/`PUBLISHED`；happy/case4/case5 三库 publish/archive 均为 0/0；Raw 输入经 `validate_raw_artifact` 门（手写绕校验会被拒，回归反证 PASS）。
- 回归：S2 `startup` 5 步逐字有序 + 中央 9 表全 0 + `assert_stage3_tables_empty` 通过；非法 Raw（缺字段）被 `PrepareError` 拒收；`src/stage1/`、`src/stage2/` 本轮 QA 未触碰（目录非 git 仓库，`git diff` 口径 N/A，以回归 PASS + 零改代证）。

## 4. §72 子集门（Stage3 9 断言逐项）

- [x] Correction Rules Change 不重新调用 Whisper（Case4 `whisper_calls=0` + grep 无 import）
- [x] Raw Hash 不变（HAPPY/Case4/Case5 三复算一致）
- [x] 新 Normalization Revision（Case4 新 ID + Norm=2）
- [x] Paragraph Formatter Change 只新建 Render Revision（Case5 delta=0 + 新 RenderRev）
- [x] Completed Processing Run 不被 Revision 回滚（Case6 COMPLETED）
- [x] Normalized PREPARED Receipt（HAPPY/TMP 双证据）
- [x] Artifact Hash Validation（tamper 判无效 + final==expected 三方链）
- [x] SQLite Forward Repair（REC exit 0，落后方被修，不重跑转写）
- [x] Raw Immutable（guard REFUSED + 字节不变 + 0444）

## BUGS（照 BUGS.template.md；本轮无 P0/P1）

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| 无 | — | 否 | 39/39 双轮 exit 0；坏例 exit 1/2 符合预期 | CLOSED | 无需 builder 修 | 详见 `/tmp/s3qa/s3qa_results.json` |

## Fix Attempt Fingerprint

- Task ID: S3-T06 Stage3 验收套件 + §72 子集门（首轮 QA 执行）
- Root Cause Hypothesis: 不适用（PASS；中间 1 处为 Runner 坏例脚本自身写法问题——0444 final 先 append 后 chmod 致 PermissionError，已改先 chmod 后篡改，复跑得预期 ArtifactInvalid exit 1；非业务缺陷）
- Approach: 仓库外 `/tmp/s3qa` 各用例独立 data_root；合成确定性 `.bin` + `build_raw_content` 经 `validate_raw_artifact` 门合成 COMMITTED Raw（不绕校验）+ 诱饵 md；Count/行数/SQLite 直查为正常路径判据；hash 篡改/immutable 拒写走子进程取 exit 码；grep 三重 STOP 门；lineage 含缺环反例
- Files Changed: 仅新增本报告 `docs/qa/STAGE3-QA-REPORT.md`；业务代码零改；测试写盘只在 `/tmp/s3qa`（H2 外置目录约束延续）
- Verification: 双轮 `TOTAL 39/39 FAILS=[] exit=0`（`s3qa_results.json` 可复算）；`TAMPER_EXIT=1` + `GUARD_EXIT=2` 双坏例 exit 码已取；输入产物目录复查未动；`src/stage1/`、`src/stage2/` 未触碰
- Failure Reason: 无 FAIL 项（业务侧）
- Difference From Previous Attempt: 首轮，无上一轮

## 未闭环清单（交 supervisor/product-reviewer 定，不卡本 PASS）

- U-1 真实长视频未测（PLAN 已定：真实长视频一律不测直到产品完成；本套件用确定性 `.bin` 合成副本 + 合成 segments）。
- U-2 Stage1 T01→T06 happy 未在本套件全链重跑（Raw 经 `build_raw_content` + `validate_raw_artifact` 门合成；门本身回归反证 PASS；provenance 门与音频内容无关）。
- U-3 Runner 在仓库外（`/tmp/s3qa_run.py` + 双坏例子进程），未进 `docs/qa`，复现找 QA 要路径（H2 外置目录约束延续；Stage1 U-4/Stage2 U-3 同 Pattern）。
- U-4 残留待清：`/tmp/s3qa`（多 data_root，本轮新增）+ `/tmp/s3qa_bad_*` + Stage2 残留（`/tmp/s2t07_qa` 约 1.9M）+ Stage1 残留（`/tmp/s1t*` + `$TMPDIR`），交 neat-freak 收尾。
- U-5 `src/stage1/`/`src/stage2/ git diff 为空`口径 N/A（当前目录非 git 仓库；以 S2 startup 回归 + S1 门反证 + QA 零改代证，未改业务代码）。
- U-6 builder 自验 harness 未在工作区落盘（6 异常清单按 S3-T06 口径由 QA 覆盖；若 builder 后补 harness，以本报告 exit 码为准对账）。

---
目标：Stage3验收（P0+Case4/5/6+lineage）｜剩 P0：无（QA 口径 PASS；闭环判定以 supervisor 复检为准）｜下一步：交 product-reviewer 验 + supervisor 复检（HANDOFF 只记状态，不代写结论）。
