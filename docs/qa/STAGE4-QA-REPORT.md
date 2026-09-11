# QA-REPORT｜Stage4 S4-T06 验收套件 + §72子集门（Video2Obsidian V1.8 §69）

- QA：qa（opencode-go/glm-5.3-flash，本窗口 subagent；未改业务代码，只写本报告）
- 被测：`src/stage4/`（volume_probe.py/publish_commit.py/publish.py/conflict.py/lineage_ext.py/__init__.py）+ `src/stage1/`（probe_volume/build_raw_content/validate 只读复用）+ `src/stage2/`（store/candidate/source/runs/instance 只读复用：open_db/持锁写库/AUTO Run）+ `src/stage3/`（normalize/render/artifact_commit/lineage 只读复用：Rendered Final 只读输入 + verdict 语义 + Whisper guard）
- 计划：`docs/pm/STAGE4-PLAN.md` S4-T06（P0-1~P0-8；happy1+异常7+回归三行；合成副本 + 外置诱饵 Output Root；禁真实长视频/真实库；坏例只看 exit 码；结论只落本报告）
- 基线：V1.8 §72 Implementation Acceptance Gate（Stage4 子集：Atomic No-Clobber implementation / Output Race Fault Injection / Unknown-User-edited Overwrite=0 / Initial Publish / Subsequent 不自动覆盖 / PENDING_PUBLISH / CANONICAL_OUTPUT_EXISTS）
- QA 执行目录（仓库外）：`/tmp/s4qa/`（happy/a1~a7/lin_missing/reg_s2/reg_s3 各独立 data_root + 合成 `.bin` 副本 + `s4qa_results.json`）+ `/tmp/s4qa_out/<case>/`（各用例外置诱饵 Output Root，与仓库/真实笔记库无交集；canonical 一律 `OUTPUT_ROOT/s4/clip.md` §48 映射）；仓库内零写盘除本报告
- **结论：PASS（happy 1 遍 + 异常 7 个全过 + lineage 并入 + 回归三行，107/107 断言双轮稳定，Runner exit 0；坏例只看 exit 码：tamper exit 1=PublishInvalid、race/gate exit 2=BLOCK；archive/Whisper/Overwrite 三零：各库 archive_commits=0、whisper_calls=0、BLOCK 分支 canonical 字节不变；结论只落本报告）**

## 1. 输入复核（src/stage4 落盘 5+1 文件，只读消费；builder 口径锁定沿用）

- `volume_probe.py`（S4-T01）：`probe_volume` 实测 §54 九字段（stat/st_dev + O_EXCL 探针 + 同目录 rename 探针 + flock，不编造；`supports_exclusive_rename=False` 为 POSIX 诚实值）；`gate_output_root` 为 §55+#3.14 唯一门（无可靠 No-Clobber→`BLOCKED_UNSUPPORTED_OUTPUT_FILESYSTEM`；iCloud/network/remote→`BLOCKED_UNSUPPORTED_ROOT_FOR_V1`）；发布路径无 Reservation Copy Fallback。
- `publish_commit.py`（S4-T02）：§49 六步（Rendered→expected 预持久化 `publish_records PENDING`+`artifacts PREPARED` 同事务→gate 复检→same-dir tmp→flush/fsync→`link(2)` No-Clobber Commit→Final Hash Verify→`PUBLISHED`+Receipt+`COMMITTED`）；`os.rename` 永不落 Final（注释1行除外，代码零调用）；`recover_publish` 拥抱 §53 分支①；`on_tmp_ready` 为 Case12 唯一抢建缝（None 即生产）。
- `publish.py`（S4-T03）：§12 Initial 分支首次启用（缺席→`PENDING→PUBLISHING→PUBLISHED` 经 S4-T02 + `state_events`；存在→直接委托 `conflict.publish_or_block`，本模块零写盘）；成功仅回填 Run `initial_publish_record_id`+`updated_at` 两列（列级 diff 硬门）；`publish_mode=INITIAL` 唯一。
- `conflict.py`（S4-T04）：§50/§51+§53（缺席→S4-T03；存在+PUBLISHING 行对上+hash 对上→Recovery Forward；同字节→`BLOCKED_OUTPUT_EXISTS`；异字节/对不上→`BLOCKED_OUTPUT_CONFLICT`；BLOCK 分支字节级不变 + `canonical_writes=0`）；§51 口径锁定：BLOCK 落一行 verdict 行，race 碰撞原地更新 open 行（S4-T06 按同一口径验收）。
- `lineage_ext.py`（S4-T05）：只读复用 `stage3.lineage.get_lineage` + 追加 Canonical 环（`publish_record_id/render_revision_id/rendered_artifact_id/canonical_output_path/expected_hash/published_hash/publish_mode/status`）；`record_publish_receipt` 经 Stage3 append-only 写 Manifest + §52 Ownership 五件套；缺环标 missing。
- 上轮 builder 链搭建配方：中央库 `<data_root>/data/state.db`（Stage2 DDL）+ per-job `data/jobs/<job_id>/`（raw/normalized/render/manifest）+ 确定性 `publish_record_id=pub_<sha12(render_rev|canonical|hash)>` + canonical `0444` 只读；QA 以公开 API 自建仓库外 Runner（见§3声明），符合“结论只落 qa 报告”约束。

## 2. 用例简表（坏例只看 exit 码；三零列见右）

| 用例 | 前置 | 动作 | 期望 | 实测 | exit 码 / Count | archive/Whisper/Overwrite |
|---|---|---|---|---|---|---|
| HAPPY 首次发布 | 新 root+out+合成 `clip.bin`+COMMITTED Raw（合成经门）+缺席 canonical | norm(create)→render(create, probe=缺席 canonical)→initial_publish | PUBLISHED+三方 hash 一致+Ownership 五件套+Run 回填两列+COMPLETED | 一致（`pub_3226e81b395b`，`5236638f…`） | Runner exit 0；publish=1 | 0/0/— |
| PROBE 九字段 | 同上 out | probe_volume+gate | 9 字段全非空+whisper0+gate 放行 | 一致（APFS local，xcre=True/xren=False 诚实） | — | —/0/— |
| A1 Case12 Output Race | 新链至 Rendered | initial_publish(on_tmp_ready=抢建异字节) | BLOCK（CONFLICT）+抢建方字节不变+行终态 BLOCK 非 PUBLISHED | 一致 | 子进程 exit **2** | 0/0/0 |
| A2 用户编辑 BLOCK | HAPPY 后诱饵 append 一字节 `U` | publish_or_block | `BLOCKED_OUTPUT_CONFLICT`+诱饵保留用户字节+Overwrite=0 | 一致 | — | 0/0/0 |
| A3 同字节重发 BLOCK | HAPPY 后无改动 | publish_or_block | `BLOCKED_OUTPUT_EXISTS` 非 PUBLISHED+字节不变 | 一致 | — | 0/0/0 |
| A4 PUBLISHING 残留 Forward | prepare 后置 PUBLISHING+手写 valid Final | recover_publish | PUBLISHED+`publishing_final_exists_repair_forward` | 一致 | — | 0/0/— |
| A5 tmp-only 续 Commit | prepare 后仅 tmp 在 | recover_publish | PUBLISHED+`prepared_tmp_only_continue_commit` | 一致 | — | 0/0/— |
| A6 Final 篡改判无效 | HAPPY 后 append 一字节 | recover_publish（子进程） | `PublishInvalid` 永判无效 | 一致 | 子进程 exit **1** | 0/—/— |
| A7 无能力卷 BLOCK | 新链至 Rendered+monkeypatch 双 False | gate+initial_publish | `BLOCKED_UNSUPPORTED_OUTPUT_FILESYSTEM`+零 staging | 一致 | 子进程 exit **2** | 0/—/0 |
| LIN-full | HAPPY 库 | get_lineage_with_publish(source) | 全链+Canonical 环 9 字段+Manifest 4 receipts | 一致 | — | — |
| LIN-missing | Rendered 未发布链 | get_lineage_with_publish | `publish=missing` 非异常 | 一致 | — | — |
| STOP 门 | 全仓 | grep+行数+diff | 无 run_asr/无 fallback/无 force/rename 不落 Final；archive 全库 0；stage1-3 diff N/A | 一致（grep 空） | — | 0/0/— |
| REG-S1 | 合成门 | probe ALLOW+validate 拒非法 | ALLOW+非法拒收 | 一致 | exit 0 | — |
| REG-S2 | 新 root | startup→discover | 5 步有序+PROMOTED+Source=1+Run=1 | 一致 | exit 0 | 0 |
| REG-S3 | 新 root | norm→render | COMPLETED→PUBLISH_EVALUATION+verdict 双值域 | 一致 | exit 0 | 0 |

Runner：`/tmp/s4qa_run.py`（仓库外）→ `/tmp/s4qa/s4qa_results.json`（107 断言 JSON 已落盘，可复算；双轮 `TOTAL 107/107 exit=0`）；坏例子进程：`--bad tamper` exit **1**、`--bad race` exit **2**、`--bad gate` exit **2**（判据只用 exit 码，不看打印）。

## 3. 每用例明细（前置/动作/期望；口径变更单列）

- HAPPY：前置见§2；动作 `create_normalization_revision`（corr-v1）→`create_render_revision`（para-v1，probe=缺席 canonical `/tmp/s4qa_out/happy/s4/clip.md`）→`initial_publish`；期望 `PUBLISH_EVALUATION`/`PENDING_PUBLISH`→`PUBLISHED`（`publish_mode=INITIAL`，`published_at` 置值，`state_events≥3`），中央 `publish_records` §35 九字段齐 + `artifacts canonical COMMITTED` + Manifest 追加 `Stage4-S4-T02:PUBLISHED` Receipt（含 Ownership 五件套） + Run 列级 diff 仅两列变 + 状态 COMPLETED + 三方 hash `5236638f…` 一致 + Raw/Rendered 复算不变 + 诱饵 out 内落盘 + 真实库零触碰；实测全中。
- A1：前置新链至 Rendered；动作 hook 在 tmp fsync 后 Final commit 前抢建异字节 `racer wins…`；期望 `link(2)` EEXIST→`BLOCKED_OUTPUT_CONFLICT`（用户=抢建方文件字节级不变，Overwrite=0，open 行原地更新为 BLOCK，`PUBLISHED` 计数 0）；实测全中（in-process + 子进程 exit 2 双证据）。
- A2：前置 HAPPY；动作 chmod 644 后 append `U` 模拟用户编辑；期望 `BLOCKED_OUTPUT_CONFLICT` + `canonical_sha_before==after（edited）` + `canonical_writes=0` + verdict 新行（§51 口径）；实测全中，Overwrite=0。
- A3：前置 HAPPY 无改动；期望 `BLOCKED_OUTPUT_EXISTS`（同内容亦 BLOCK 不静默认领）+ 字节不变 + 非 PUBLISHED；实测全中。
- A4：前置 prepare（PENDING）→UPDATE PUBLISHING + 手写 valid Final；期望 `repair_forward=True` + `publishing_final_exists_repair_forward` + 不重建 tmp；实测全中。
- A5：前置 prepare（PENDING）+ 手写 tmp（Final 缺）；期望 `repair_forward=True` + `prepared_tmp_only_continue_commit` 经 `_link_and_finish` 落盘；实测全中。
- A6：前置 HAPPY；动作 chmod 644 后 append `X`；期望 `PublishInvalid`（half-Canonical 永判无效，子进程 exit **1**，判据只用 exit 码）；实测全中。
- A7：前置新链；动作 monkeypatch 双 False；期望 gate 抛 `BLOCKED_UNSUPPORTED_OUTPUT_FILESYSTEM` + publish 路记 verdict 行后抛 `PublishBlocked`（零 staging，无 fallback 路径 grep 空）；实测全中（in-process + 子进程 exit 2）。
- LIN：HAPPY 库 `get_lineage_with_publish(source)` 返回 Source/Run/Raw/1 NormRev/1 RenderRev + Canonical 环（`pub_3226…/rendrev_26a5…/rendered_…/…/clip.md/sha256:5236…/PUBLISHED`）；未发布链 `canonical_publish=[{status:missing}]`；未知根沿 Stage3 语义 KeyError（未单列断言，缺环反例已覆盖）。
- STOP：`rg run_asr_single_file src/stage4` 空；`rg Reservation|fallback` 空；`rg force|Force|FORCE|overwrite|Overwrite|O_TRUNC` 空；`os.rename(` 仅 volume_probe 探针 + publish_commit 文档行（代码零落 Final，`link(2)` 为唯一 commit）；13 库 `archive_commits` 全 0（happy/publish 系 1~2 行，reg/空链 0 行）；canonical 全在 `/tmp/s4qa_out/<case>/` 内（仓库外，与真实库无交集）。
- 口径变更（R3）：stage2 原 `assert_stage3_tables_empty` 四表口径中 `publish_records` 本 Stage 起正式写行（happy=1、a2/a3=2 均为预期），QA 不得要求它通过，不得为此改 `src/stage2/`；Stage4 自带 `archive_commits=0` 子集断言全库通过（13/13）。
- 回归：REG-S1 `probe_volume→ALLOW` + 非法 Raw 拒收；REG-S2 `startup` 5 步逐字有序 + PROMOTED + Source=1 + AUTO Run=1；REG-S3 `COMPLETED→PUBLISH_EVALUATION` + verdict∈{PENDING_PUBLISH,CANONICAL_OUTPUT_EXISTS}；`src/stage1-3/` 本轮 QA 未触碰（目录非 git 仓库，`git diff` 口径 N/A，以三回归 PASS + QA 零改代证）。

## 4. §72 子集门（Stage4 7 断言逐项）

- [x] Atomic No-Clobber implementation（HAPPY link(2)+三方 hash+A5 tmp-only，rename 零落 Final）
- [x] Output Race Fault Injection（A1 hook 抢建→BLOCK + 用户字节不变 + 行 BLOCK）
- [x] Unknown-User-edited Overwrite=0（A2 一字节编辑→CONFLICT + 诱饵保留用户字节）
- [x] Initial Publish（HAPPY `PENDING→PUBLISHING→PUBLISHED` + §35 九字段 + `published_at`）
- [x] Subsequent 不自动覆盖（A3 同字节亦 `BLOCKED_OUTPUT_EXISTS`，零写盘）
- [x] PENDING_PUBLISH（HAPPY verdict 缺席分支 + REG-S3 双值域）
- [x] CANONICAL_OUTPUT_EXISTS（Stage3 verdict 语义沿用；Stage4 存在分支走 BLOCK，S4-T03 零写盘已验）

## BUGS（照 BUGS.template.md；本轮无 P0/P1）

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| 无 | — | 否 | 107/107 双轮 exit 0；坏例 exit 1/2 符合预期 | CLOSED | 无需 builder 修 | 详见 `/tmp/s4qa/s4qa_results.json` |

## Fix Attempt Fingerprint

- Task ID: S4-T06 Stage4 验收套件 + §72 子集门 + Stage1/2/3 回归（首轮 QA 执行）
- Root Cause Hypothesis: 不适用（PASS；中间 1 处为 Runner 自身门写法问题——`os.rename` grep 把 publish_commit 文档行计入，改仅判代码行后复跑 107/107；非业务缺陷）
- Approach: 仓库外 `/tmp/s4qa` 各用例独立 data_root + 外置诱饵 Output Root；合成确定性 `.bin` + `build_raw_content` 经 `validate_raw_artifact` 门合成 COMMITTED Raw（不绕校验）+ Run 置 COMPLETED（列级 diff 硬门）+ norm/render 经 Stage3 公开 API；Count/行数/SQLite 直查为正常路径判据；hash 篡改/竞态/无能力卷走子进程取 exit 码；grep 四重 STOP 门；lineage 含缺环反例
- Files Changed: 仅新增本报告 `docs/qa/STAGE4-QA-REPORT.md`；业务代码零改；测试写盘只在 `/tmp/s4qa` + `/tmp/s4qa_out`（H2 外置目录约束延续）
- Verification: 双轮 `TOTAL 107/107 FAILS=[] exit=0`（`s4qa_results.json` 可复算）；`TAMPER_EXIT=1` + `RACE_EXIT=2` + `GATE_EXIT=2` 三坏例 exit 码已取；13 库 `archive_commits` 全 0；诱饵用户字节双用例不变；`src/stage1-3/` 未触碰
- Failure Reason: 无 FAIL 项（业务侧）
- Difference From Previous Attempt: 首轮，无上一轮

## 未闭环清单（交 supervisor/product-reviewer 定，不卡本 PASS）

- U-1 真实长视频未测（PLAN 已定：真实长视频一律不测直到产品完成；本套件用确定性 `.bin` 合成副本 + 合成 segments）。
- U-2 Stage1 T01→T06 per-job 全链未在本套件重跑（Raw 经 `build_raw_content` + 门合成；门本身回归反证 PASS；provenance 门与音频内容无关）。
- U-3 Runner 在仓库外（`/tmp/s4qa_run.py` + `--bad` 三子进程），未进 `docs/qa`，复现找 QA 要路径（H2 外置目录约束延续；Stage1 U-4/Stage2 U-3/Stage3 U-3 同 Pattern）。
- U-4 残留待清：`/tmp/s4qa`（13 data_root）+ `/tmp/s4qa_out`（13 诱饵 out）+ Stage3 残留（`/tmp/s3qa`）+ Stage2 残留（`/tmp/s2t07_qa` 约 1.9M）+ Stage1 残留（`/tmp/s1t*` + `$TMPDIR`），交 neat-freak 收尾。
- U-5 `src/stage1/`/`src/stage2/`/`src/stage3/ git diff 为空`口径 N/A（当前目录非 git 仓库；以三回归 PASS + QA 零改代证，未改业务代码）。
- U-6 builder 自验 harness 未在工作区落盘（happy1+异常7清单按 S4-T06 口径由 QA 覆盖；若 builder 后补 harness，以本报告 exit 码为准对账）。

---
目标：Stage4验收S4-T06｜剩 P0：无（QA 口径 PASS；闭环判定以 supervisor 复检为准）｜下一步：交 product-reviewer 验 + supervisor 复检（HANDOFF 只记状态，不代写结论）。
