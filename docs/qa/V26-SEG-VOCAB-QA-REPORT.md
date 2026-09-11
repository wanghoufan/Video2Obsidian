# BUGS｜V26分段+预置词库运行期验收（2026-09-11）

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| V26-SEG-450 450字无标点合成段全≤120且段数增加 | P0 | 否（已PASS） | 合成`甲`*450直调`render_with_v2` | PASS | 运行期验收通过 | 独立复验count=4 max=120 join原样无空段；自测同断言PASS |
| V26-SEG-DUAL 引擎与生产双路一致 | P0 | 否（已PASS） | /tmp合成job直调`_apply_v25_postpass` vs 引擎直算+`assemble` | PASS | 运行期验收通过 | byte_equal True paras=4 max=120；`_engine_params`读`PARA_PARAMS_V2`；缺文件fail-open不炸 |
| V26-SEG-RERUN 存量重跑whisper恒0/Raw不变/用户改过md跳过 | P0 | 否（已PASS） | 静态守卫+空库fail-safe（硬约束禁碰真实库） | PASS | 运行期验收通过 | `whisper!=0`拦截+Raw哈希比对+`BLOCKED_OUTPUT_CONFLICT`跳过三守卫均在码；空库`_reapply_one`回ok False不炸 |
| V26-VOCAB-PRESETS 三域条数≥50+结构 | P0 | 否（已PASS） | 只读`app/presets/vocab/*.json` | PASS | 运行期验收通过 | finance66/programming83/crypto68；错词≥2字≠正词同域去重含source |
| V26-VOCAB-IMPORT 导入合并+bump+幂等 | P0 | 否（已PASS） | /tmp data_root直调`_handle_vocab_presets_import` | PASS | 运行期验收通过 | added=217==三域去重；revision `s9-corr-v2-user-`；落盘vocab-user.json；二次added=0 revision不变 |
| V26-VOCAB-HIT 新转写命中替换 | P0 | 否（已PASS） | 同上revision直调`normalize.apply_corrections` | PASS | 运行期验收通过 | `市盈绿/美联署/区块连`→`市盈率/美联储/区块链`；新job profile revision一致 |
| V26-VOCAB-BASE-REJECT 撞基表拒收 | P0 | 否（已PASS） | /tmp独立preset+data_root，`Github`撞基表 | PASS | 运行期验收通过 | rejected_base含Github且不落库；真实三域rejected_base_count==0 |
| V26-VOCAB-SINGLE 单字拒收保留 | P0 | 否（已PASS） | 同上`a→bb`+坏例400 | PASS | 运行期验收通过 | 读取层丢弃单字，added==1仅合法条；空domains/全未知/非JSON均400只看exit码 |
| V26-SELFTEST-HARNESS builder自验脚本 | P0 | 否（已PASS） | `python3 tests/selftest_v26_presets.py` | PASS | 运行期验收通过 | SELFTEST ALL PASS EXIT=0（50断言全PASS） |

## Fix Attempt Fingerprint

- Task ID: V26-SEG-VOCAB-QA-2026-09-11
- Root Cause Hypothesis: 无（验收未发现业务bug；三处硬约束内全过）。
- Approach: 只用外置/tmp+合成+stub，直调函数；禁碰用户真实目录与OB库、禁碰8765服务；先`py_compile`再跑builder自测看exit码，另写独立脚本复验双路/落盘/坏例（坏例只看exit码）。
- Files Changed: 无（QA不改业务代码；只写本报告）。
- Verification:
  - `python3 -m py_compile src/stage9/formatter_v2.py app/server.py tests/selftest_v26_presets.py` → PY_COMPILE_OK EXIT=0。
  - `python3 tests/selftest_v26_presets.py` → SELFTEST ALL PASS EXIT=0（50行PASS：version/target80/hard120/min30；450 max≤120段数>1无空段字面未改写；engine 3键==常量；postprocess cap≤120决定论；profile bump para-v2.6；check_rule_order all_pass；防碎3碎段并1；三域存在/≥50/≥2字/≠正词/去重/含source；可扩展新增域+坏文件跳过；导入200 added217零撞基表revision用户哈希落盘；二次幂等added0跳过217 revision不变；新转写profile一致+金融/币圈替换；坏例空domains400；撞基表Github拒收不落库+单字丢弃added1+未知域400）。
  - QA独立分段：`甲`*450 → count4 max120 join==原样 PASS；`乙`*300 postprocess决定论+cap≤120 PASS；3×`ab`防碎len1 PASS；engine==常量80/120/30+profile para-v2.6 PASS。
  - QA独立双路：/tmp job `norm.json`(甲450)+`rend.md`走`_apply_v25_postpass` → fixed True paras4 max120，文件==`render_with_v2`+`assemble_markdown`字节一致 PASS；缺norm回`{fixed False, error normalized缺失}` fail-open PASS；源码三守卫`whisper!=0拦截/原文被改动Raw不变/BLOCKED_OUTPUT_CONFLICT库内改过跳过`均存在 PASS。
  - QA独立词库：只读三域66/83/68去重≥2字 PASS；/tmp data_root导入added217==去重合计 revision用户哈希落盘 PASS，二次幂等 PASS，新job revision一致+`市盈绿/美联署/区块连`替换 PASS；独立/tmp preset撞基表Github拒收不落库+单字丢弃added1 PASS；坏例空domains400/全未知400/非JSON400 PASS。
  - QA重跑fail-safe：空/tmp库`_reapply_one(no-such-run)` → ok False `状态库不可读`不炸不碰whisper PASS。
- Failure Reason: 无（首轮即全PASS，无打回）。
- Difference From Previous Attempt: 首轮运行期验收；此前无V26 QA报告。

## 未闭环（打回项）

- 无（两项9行全PASS；限制明示：存量重跑全链路未用真实用户库/OB库，系硬约束禁碰所致，以三守卫静态+fail-open+空库fail-safe覆盖；8765服务未碰）。
