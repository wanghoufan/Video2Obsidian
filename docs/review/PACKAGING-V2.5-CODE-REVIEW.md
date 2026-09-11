
# CODE REVIEW

- Task: 复核V2.5（src/stage9/formatter_v2 para-v2.5参数+后处理、app/ vocab-user.json增删改查+revision bump、重跑derive入口whisper0+No-Clobber跳过用户编辑）
- Commit: N/A（非 git 仓库；评审对象为工作区现状 src/stage9/formatter_v2.py 305行 / derive_v2.py 112行 / rules_v2.py 164行 / app/server.py 2855行 V2.5段1040-1270+2444-2768 / app/index.html vocab+reapply段193-204/444-471/796-865；src/stage3只读对照 derive.py/normalize.py/render.py/publish.py/conflict.py）
- Reviewer: code-reviewer（opencode-go/glm-5.3-flash）
- Result: 打回+改法（P0×1 必修：生产渲染路径绕过V2.5后处理，200封顶/MIN防碎在生产不生效；P1×3 必修：重跑DB异常未接管掉线、单字词条 blast radius、无605保存序；修完可过）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## P0 / P1 Findings

- P0-1 生产路径从不调用 `render_with_v2`，V2.5两道后处理（X=200硬封顶、MIN=40防碎）在生产不生效，保证落空：`_render_profile_for_new_jobs`（server.py:1172-1176）与 `_reapply_one`（2552-2561）均把V2.5 profile直接喂给冻结引擎（`create_render_revision`→`render_paragraphs`，render.py仅读三键、MIN被忽略已核），而 `_enforce_hard_cap/_merge_shorts` 只活在 `formatter_v2.render_with_v2`（formatter_v2.py:190-204）内；`rg render_with_v2 src/ app/` 仅定义+自检+`__init__`导出，生产零调用。本机实证（同segments两路对比）：单450字无标点段→引擎`[450]`、wrapper`[200,200,50]`；引擎在多段累积同样可超200（`acc_len>=hard_max`只在下个边界前检查，150+150无标点即拼出300才断）。`check_rule_order hard_cap_v25/min_merge_v25`（207-297）测的是wrapper不是生产，属自证。改法（三选一，由planner/TM拍板，不自创架构）：① 生产侧收敛口径——文档+前端明确“200封顶/MIN合并仅段间生效，段内超长仍可能超200”，wrapper探针改名audit-only，QA加生产路复现例（450单段经`create_render_revision`断言现状）；② 把切分前移到段侧——入库前对超长segment按同款弱标点规则预切分（只动app/stage9，不碰stage3文件），再喂引擎；③ stage9自有render装配（新mechanics，需planner开STOP-EXPANSION例外，默认不选）。任选其一后，QA须补“生产路450单段/150+150无标点/3×ab碎渣”三例经真实`create_render_revision/derive`的断言。
- P1-1 重跑入口DB异常未接管，错data_root/坏库直接掉连接而非JSON：`_reapply_one`（2500-2520）`con=_open_rw`在`try`之外，`_open_rw`父目录缺失即`OperationalError unable to open database file`；表缺失时`SELECT`在`try`内但无`except`，`finally`关库后异常上抛；`_handle_reapply_post`单条（2763）与`all`批量列表推导（2748）均无`try`，`Handler.do_POST`亦无外层接管——本机实证空`data/`库调`_reapply_one`抛`no such table`直达调用方（HTTP层即掉线）。改法：`con=_open_rw`移入`try`并加`except (sqlite3.Error,OSError)`回`{"ok":False,"error":"状态库不可读…刷新/检查数据目录"}`；SELECT失败同口径；`all`批量改逐项`try`（单项异常记`{ok:False,error}`进results，不掀整批）；`_open_rw`缺父目录先`return`人话错而非直连抛。
- P1-2 用户词条无最小长度门，单字规则可血洗全文：`_validate_vocab_pair`（1099-1115）只拦空/超128/相等/撞基表，注释明示“比stage9形状门更松”。本机实证内存注册`("a","b")`对`"a cat and a dog banana"`→`"b cbt bnd b dog bbnbnb"`（7处替换）。用户手滑加`的→地/啊→呀/a→b`即全库污染，且自动进新转写+重跑。改法：`wrong`最小长度≥2（CJK≥2/拉丁建议≥3，二选一并写死），单字/纯标点/纯空格直接400拒收并给人话；2-3字短词加二次确认语（前端`confirm`复用delVocab口径）+回显`applied count`预览（调一次`apply_corrections`试算命中数，>50即警告）；大小写变体（`github` vs 基表`Github`）提示“疑似重复（仅大小写差异），仍要加吗”。
- P1-3 词库“先注册后落盘”+保存异常未接，500与状态分叉：`_handle_vocab_add`（1238-1242）`_register_user_rules`成功后`_save_vocab_entries`裸调，磁盘满/权限错即抛穿`do_POST`（500掉线），且内存已多一个`revision`而文件没有，重启即丢。改法：调序为先`_save_vocab_entries`（包`try/OSError`→`400/500 JSON“词库保存失败，未生效”`）再`_register_user_rules`；注册失败则删回文件或明确“文件已存、内存未注册，重启自愈”二选一并注释。

## P2 / P3 Backlog Findings

- P2-1 RENDER_ONLY重跑永不尝试入库：`_reapply_one`仅`prev_state==PUBLISHED and vault`（2596）走`initial_publish`，RENDER_ONLY即使本次给了vault也只落数据目录（2687-2697）。若为有意（防误入库），改法：前端重跑按钮对RENDER_ONLY注明“只出新稿不入库，去主页点重试/开始监听入库”，或后端对RENDER_ONLY+有vault追加一次`initial_publish`尝试；二选一并文档化。
- P2-2 注释史实对不上：formatter_v2.py:58-61写“Versus para-v2 {1.5,240,400}”，但树内无para-v2，stage3冻结实为`{1.5,180,400}`（render.py:63-66）。改法：删para-v2句，改“相对冻结para-v1 180→120”。
- P2-3 手改超500词库文件被静默截断：`_load_vocab_entries`（1080）`out[:500]`，revision按截断后算，与文件内容不一致。改法：超限文件load后记`truncated=True`并在GET回显“文件X条，仅前500生效，请删减”，或add/del时按原文长度拒写并提示。
- P2-4 内存词表只增不减：每次新内容一个`revision`键进`CORRECTION_RULES`（1132-1158），del不驱逐。改法：加注“revision键常驻内存，重启清；高频改词长期进程缓慢增长可接受”，或LRU上限（如200，超限拒reapply并提示重启）。
- P2-5 空输入报错类型与文档差一层：`render_with_v2`文档“无输出抛FormatterError”，实际空list由引擎先抛`RenderError`（已实证）。改法：入口加`if not segments: raise FormatterError`前置，或文档改“空输入由引擎RenderError拒收”。
- P2-6 CJK碎渣合并用ASCII空格：`_merge_shorts`（166/179）`pending+" "+para`，`ab ab ab`对英文对，中文 crumbs 会夹半角空格。改法：joiner按是否含CJK选`""`/`" "`，或文档注明“合并空格为英文习惯，中文可接受”。
- P2-7 弱引导 terms 在无mlx环境静默丢失：`_transcribe_audio`（1398-1447）stage7/8缺`mlx_whisper`即回退stage1直调（terms丢弃），`_user_prompt_terms`（1179-1190）20×128最长2560字prompt长度亦未钳。改法：回退分支记receipt `prompt_terms_dropped=True`，terms总长钳（如≤300字）并注释。
- P3-1 `esc()`（index.html:277）未转单引号：现vocab行/删除键均为双引号属性+`&<>"`转义，无XSS（已核），V2.2 P2-4延续，拼单引号属性前再补即可。
- P3-2 `all=true`串行逐项derive，大库耗时无进度：改法：results逐项回`render_revision_id/raw_unchanged`已有足够排障，后续加`summary{total/ok/skipped_user_edited/failed}`已齐；进度条以后再说。

PASS确认（不打回）：para-v2.5四参`{1.5,120,200,40}`+`FORMATTER_VERSION`只进render profile五字段（93-104），`RULE_ORDER`四序冻结且六探针全过（含X=200/MIN=40 wrapper探针）；`_engine_params`剥MIN与“引擎忽略多余键”已核对（render.py读三键+MIN改hash已实证hash变化）；user revision `s9-corr-v2-user-<sha8>`空回落基线、增删改查/幂等/损坏fail-open/原子tmp+rename全实跑过；重跑走`derive_on_correction_change`同一Case4入口、`whisper!=0`拦截+Raw前后sha256比对+`BLOCKED_OUTPUT_CONFLICT→skipped_user_edited`+present-canonical委托`publish_or_block`（publish.py:181-186）No-Clobber链完整；`src/stage9`无`run_asr/openai/llm/rewrite`命中、`app/server.py`无asr入口import（AST+rg双核）；`py_compile`四文件过。

证据备注：`py_compile` OK；`formatter check_rule_order all_pass True`；`engine[450] vs wrapper[200,200,50]`；`a→b`血洗例；vocab增/覆盖/撞基表/同值/空/超长/删/删缺失/损坏回空/非list回空/注册幂等/prompt去重截20全实跑；重跑空id/坏JSON/缺run_id/空all/缺表抛错全实跑。

## 复核修订（2026-09-11 V2.5补修复核）

- Task: 复核V2.5补修（P0-1生产走v2.5后处理不断链、P1-1 DB接管、P1-2单字门、P1-3先存后注册；对照本文件打回项）
- Reviewer: code-reviewer（本窗口subagent，按真源override主用 codex/gpt-5.6-terra 通道）
- Result: PASS（P0-1 CLOSED、P1-1 CLOSED、P1-2核心CLOSED余2项降P2、P1-3 CLOSED；只改本文件，未碰业务代码）
- P0-1 CLOSED：生产两入口均经 `_apply_v25_postpass`（server.py:1441-1503）用同一 `render_with_v2` 重算覆写、冻结derive先mint不断链。实证：单450无标点引擎`[450]`→wrapper`[200,200,50]`；150+150累积引擎`[301]`→wrapper`[200,101]`；3×ab碎渣→`['ab ab ab']`；`check_rule_order all_pass True`；`_apply_v25_postpass`首跑`{fixed:True,paras:3,max_len:200}`、次跑`{already_ok:True}`、缺norm/空segments均`{fixed:False}`fail-open不炸worker；新转写调用位2002-2019与重跑调用位3061-3078均try包+receipt（`V25_POSTPASS`/`v25_postpass`），`py_compile`四文件过。`split_segments_for_engine/postprocess_paragraphs`（formatter_v2.py:190-248）已导出但生产未直调（经`render_with_v2`重算等效），可接受。
- P1-1 CLOSED：`_open_rw`（2904-2935）缺父目录/缺库抛人话`FileNotFoundError/OSError`；`_reapply_one`（2965-3223）`_open_rw`入try→`{ok:False}`、SELECT包`except (sqlite3.Error,OSError)`人话、外层再包`except (sqlite3.Error,OSError)`；实证错root与缺表均回JSON不抛（`状态库不可读…no such table: processing_runs`）；`_handle_reapply_post`（3226-3285）坏JSON400、缺run_id400、空all200空summary、`all`逐项try（`sqlite3.Error,OSError`→人话+`Exception`→重跑失败）不掀整批，单项外层500接管；`Handler.do_POST`（3327-3369）外层try→500JSON（`服务开小差`）不断连接。
- P1-2 核心CLOSED：`_validate_vocab_pair`（1343-1377）单字`a→b`/`的→地`拒收、纯标点`...→x`拒收、纯空格按空拒收，2字放行；`_handle_vocab_add`（1529-1615）新加单字/纯标点均400，覆盖单字仍400（1559-1561二次门），短词2-3字放行但回`preview{needs_confirm:True,warnings}`+大小写变体提示（`github`疑似重复），前端（index.html:858-869）`len<2`前拦+`len<=3 confirm`复用delVocab口径+warnings回显。实证：`add a→b/的→地/...→x`均400，`ab→cd`200带预警，`github`变体提示，`overwrite a→new`仍400。
- P1-3 CLOSED：`_handle_vocab_add`先`_save_vocab_entries`（1591）后`_register_user_rules`（1597），源码序已核`save<reg`；`OSError→500“词库保存失败，未生效”`内存未动，`ValueError→400`并回滚文件到`entries_before`（1599-1604）。实证：mock磁盘满500且内存未污染，mock注册撞基表400且文件`before==after`；`_handle_vocab_del`（1618-1642）`OSError→500`。
- P2跟进（不卡过）：①覆盖纯标点绕过——legacy文件预置`...→old`时`overwrite ...→new`回200被覆写（新加已400），因第二段只重检`len<2`/基表未重检纯标点；改法：第二段补与`_validate`同款纯标点/空格门，或`if err is not None and wrong_s in existing and err含单字/标点→仍400`（仅重复覆盖的“已在词库”文案放行）。②短词命中数未试算——现2-3字统一通用警告（`命中超50处请及时删除`），未调`apply_corrections`试算`applied count`按>50分级；改法：add成功前对`wrong`调一次内存试算回`preview{applied_count}`，>50才强警告。③覆写后DB `final_hash`分叉——`render_revisions.final_hash`为mint时引擎稿哈希，`_apply_v25_postpass`覆写md后文件sha与库内值分叉（链不断但可审计性降）；改法二选一：生产改预切`split_segments_for_engine`再喂引擎保hash一致，或覆写后更新DB `final_hash`+manifest备注。④P2-2未修：formatter_v2.py:58-61仍留`Versus para-v2 {1.5,240,400}`史实句（树内无para-v2），下轮顺手按原改法删改。
