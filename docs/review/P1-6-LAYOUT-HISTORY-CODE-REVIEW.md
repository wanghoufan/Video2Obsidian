# CODE REVIEW｜DEVELOP-P1-6「布局与历史分页」

- Task: **DEVELOP-P1-6**（FR-10/HD-9=A 顶部横条、FR-11 两列栅格、FR-12/HD-6=A 完成分层与 cursor 历史、FR-15/HD-7=A 隐藏已完成、D-15 历史分页一致性）。
- Commit: **未提交**（工作树，基线 `HEAD=da0f572`）。`git diff --numstat` 实测＝`app/server.py 178/1`、`app/index.html 178/25`、`tests/selftest_p1_2_contract.py 254/0`、`tests/selftest_p1_2_frontend.py 135/3`（4 files，+745/−29）。TM 转述为 `index.html +184/−25、两自测 +253/+137`，与实测有小出入（记 P3-2，非代码缺陷）。
- Reviewer: code-reviewer（本窗口 subagent 独立复核，与 builder 非同一审查上下文；先读 AGENTS 治理节、`PRODUCT_PLAN.md:63-68/:144/:202/:266-269` 与同目录既有报告体例再动手）
- Result: **PASS（无 P0／P1 阻断；P3×5）**。builder 自报的改动范围经 **AST 逐函数机器比对**证实精确成立；keyset 翻页、并列决胜、孤儿可见、口径一致性全部用**独立夹具探针**复算；4 条反向证伪全部咬住且 sha256 还原一致。

> 复核口径：只读业务代码＋独立跑三套自测＋自写探针（`/tmp/p16_probe.py` 独立 8-run 夹具、`/tmp/p16_mutate*.py` 4 条变异）取证；**未改业务代码**（每次变异均「改坏→跑→从 `/tmp/p16_bak` 拷回→比对全量 sha256」，**全程未用 `git checkout`**）；未起 8765、未请求线上服务；用户真实视频目录与 Obsidian 库零写；本次只新增本报告一个文件。

---

## 一、我自己跑过的命令与退出码（实跑证据，非转述）

| # | 命令 | 实测输出 | rc |
|---|---|---|---|
| 1 | `python3 tests/selftest_p1_2_contract.py` | `SELFTEST ALL PASS（512 项断言）`，含 part14 全绿（14a~14k） | **0** |
| 2 | `python3 tests/selftest_p1_2_frontend.py` | `FRONT ALL PASS`＋`FRONT SELFTEST PASS`（`^PASS`=**167**、`^FAIL`=**0**），含 S12 与 L1-L5 | **0** |
| 3 | `python3 tests/selftest_v26_presets.py` | `SELFTEST ALL PASS`（58） | **0** |
| 4 | AST 逐函数比对 `HEAD:server.py` vs 工作树 | ADDED＝3 常量＋4 函数；REMOVED=[]；CHANGED=**仅 `_handle_status`** | 0 |
| 5 | `function` 级比对 `HEAD:index.html` vs 工作树 | ADDED＝10（sha256Hex/hideDone*/loadOlderCompleted/renderCompletedBar/segStateText/visibleCompletedRows 及 2 个内层）；CHANGED=**仅 refresh/renderRuns/renderTape** | 0 |
| 6 | `python3 /tmp/p16_probe.py`（独立 8-run 夹具） | **17/17 PASS**（keyset 翻页/并列决胜/回退/孤儿/口径一致/伪造实验） | 0 |
| 7 | `python3 /tmp/p16_mutate.py`（4 条变异＋自动还原） | 4/4 rc=1、4/4 还原后 sha256 与基线逐字一致 | 0 |
| 8 | 终态 `shasum -a 256`＋`git status --short` | 四文件与动手前逐字一致；仍只有 4 个 `M`＋`?? .codebuddy/` | 0 |

**基线 sha256（动手前自分自算，全部已还原）**：`app/server.py 9dbbed86…33c4eb`、`app/index.html 5ad402f6…19ad6`、`tests/selftest_p1_2_contract.py a540ac9e…945a8`、`tests/selftest_p1_2_frontend.py 8551df49…8ea4a5`。备份：`/tmp/p16_bak/`。

## 二、范围严查（复核重点 1）——**精确成立，无越界**

- **server.py（机器比对，非目测）**：全文件 AST 逐函数 sha256 比对，CHANGED **只有 `_handle_status`**（diff 唯一内容＝`:4414-4420` 追加 FR-12 块）；ADDED＝`COMPLETED_DEFAULT_LIMIT/COMPLETED_MAX_LIMIT/_CURSOR_SIG_PREFIX`＋`_completed_cursor_encode/_completed_cursor_decode/_completed_runs_view/_attach_completed_view`（`:2853-3016`）。REMOVED=0。
- **`_strip_paths`（D-12 唯一脱敏出口）逐字未动**（函数体 sha256 与 HEAD 一致）；`DONE_STATES`/`FAIL_STATES`/`_scoped_runs_summary`/`_dir_tail`/`_err_text`/`_open_ro`/`_scan_disk_states`/`_run_source_path_map`/`_is_under_root`/`_query_int`/`_attach_source_filenames`/`_filter_status_runs`/`collect` 全部 same；**恢复/词库/诊断/发布/browse/start/stop 等 handler 零触碰**（REMOVED=[]＋CHANGED 仅 1 项即证明）。
- **DONE_STATES 口径一致性**：`:103 DONE_STATES=("PUBLISHED","RENDER_ONLY")`；新视图 `:2937` 判据（磁盘终态∈DONE_STATES）与 `_scoped_runs_summary` 的 done 分桶（`:2813-2816`）逐字同构；范围过滤 `:2940-2942` 与 `:2807-2810` 逐字相同（孤儿可见）。**独立夹具实测 `summary.done == completed_total`（探针④；契约 14b 亦断言）**。

## 三、重点逐项裁定

### A｜cursor 安全与正确性 —— **PASS（P3-1 记一处）**

- **解码路径异常全捕获**：无 `.`→400（`:2878`）；签名不匹配→400（`hmac.compare_digest`，`:2883`）；base64/json 异常→400（`:2885-2892` try 包死）；缺排序键→400（`:2893`）。全部 ParamError 人话，`_handle_status:4419` 捕获回 400；非 ParamError 冒泡到 `do_GET:6239-6243` 500（`_err_text` 脱敏，不静默）。
- **keyset「严格小于」独立复算（我自己的 8-run 夹具，非复用测试桩）**：`after=[e for e in entries if (e["_eff"],e["run_id"]) < (cur_eff,rid)]`（`:2988`），与 DESC 排序（`:2957`）严格配套。探针②：limit=3 翻页＝**3/3/2、8 条无重复无遗漏、集合=全量**；5 个并列时间戳 run 内部 **run_id 降序**；缺 completed_at 行回退 updated_at 且 cursor 往返（f=""→cur_eff=u）与 `_eff` 同构，**不撕裂**。契约 14c/14d/14f/14g/14j（77 夹具、61 展开、20/20/20/1、并列对、幂等）全绿。
- **completed_limit**：`_query_int` 非整数→400 人话（`"completed_limit 须为整数"`）；越界 `max(1,min(limit,200))`（`:2972`）与既有 `limit` 口径（`:4375`）逐字同构。14e 实测 5 生效。
- **P3-1（本批新增）**：校验和＝**无密钥** sha256（`sha256("v2o-cursor:"+raw)[:12]`）。我的探针⑤实证：取合法 cursor 改 payload 后**自算校验和即可通过 decode**（伪造成功）；随手篡改（不改校验和）仍被拒。含义：防**意外**篡改/客户端 bug 有效，防**故意**伪造无效——影响面仅限分页窗口（不越 data_root 范围、无鉴权语义），判 P3 不阻断；若要收紧可改 HMAC＋既有 server_nonce（FR-5 同款思路），backlog。

### B｜完成行数据可信（复核重点 3）—— **PASS**

- **真源直读**：state/verdict/rendered_path/canonical_output_path 来自 `_scan_disk_states`（`jobs/*/manifest.json` 直读，`:2922`）；source_path 来自 `_run_source_path_map`（sources 表）；无内存缓存中介。
- **脱敏复用既有口径**：`source_dir_tail` 复用 `_dir_tail`（`:3010`），探针⑥实测与 `server._dir_tail(dirname)` 逐字一致且为 `…/` 打码形态。
- **无口径外泄漏**：page 行字段集与既有 `_attach_source_filenames:1083-1091` 往 recent_runs 写的**完全同构**（source_path/source_dir/source_dir_tail/source_filename）——全路径本就是 /api/status 既有响应字段（本地页面显示用，D-12 脱敏管的是错误文本出口，不在此列）；rendered_path/canonical_output_path 亦为既有详情/输出列已暴露字段（`:2109/:2171/:2193`）。**本批没有新引入任何脱敏口径外字段**。

### C｜前端正确性（复核重点 4）—— **PASS**

- **续接游标对齐不是假信心**：`refresh()` 每张新快照把 `completedNextCursor` 对齐到**当前首页尾**（index.html diff `:2199-2201`）。我独立推演了「展开后监听中新完成项挤出边界」场景：新项进首页→首页尾后移→展开从新尾接起→`visibleCompletedRows` 按 run_id 去重（extras 里的旧行兜住不丢）→**并集无缝无重**。反例也推演了：若不重置 cursor 才会产生重复拉取浪费（去重仍兜底）——即现设计是必要而非多余。契约 14d/14j 与前端 L3 断言守同一路径。
- **去重键 run_id**：DB 主键，唯一成立。
- **隐藏开关零删写**：`hideDoneGet/Set` 只走 `lsGet/lsSet`；渲染层 `runs.concat(hideOn?[]:completedRows)` 纯视图过滤（L3 断言钉死该串）；无任何 fetch/DELETE 关联。勾选状态在 renderRuns 里按存储回写 UI（`el("hideDoneChk").checked=hideDoneGet()`），不会漂。
- **localStorage 键隔离**：`v2o-hide-done-<sha256Hex(data_root)前8位>`；S12 有 hashlib 对账、已知向量（abc/空串/中文）、跨目录隔离、切回保留、可逆、**effectiveDataRoot 兜底**（输入框空时取生效目录）7 类行为级断言，全绿。前端自实现 SHA-256 属紧凑实现，S12 已钉 KAT 向量（含中文 UTF-8），够用。
- **手动刷新重置**：`refresh(false)` 里 `completedExtra=[];completedNextCursor=null;completedRootSeen=null`，展开视图不跨目录串味；换 data_root 时 renderRuns 按 `completedRootSeen!==dataRoot()+"|"+irNow` 再兜一层（含 input_root 维度）。

### D｜布局语义（复核重点 5）—— **PASS（静态＋变异双查）**

- **横条**：`.flowbar` 为 `main(display:block)` 下的普通 section，`display:flex;padding:6px 12px;margin:0 0 12px`——**无 position:sticky/fixed**（全文件 `position:fixed` 仅 .modal/#toasts/#longPanel 三处既有）；无收起控件（不可收起）；高度≈36px≤64px（FR-10）。变异 M4（加 sticky）被 `L1 不 sticky` 断言咬住（见 §四）。
- **栅格**：`.cols{grid-template-columns:minmax(0,1fr) 300px}`＋`section{...;min-width:0}`＋`@media(max-width:960px){.cols{grid-template-columns:1fr}}`；DOM 顺序＝横条→处理任务（表单/操作在前）→runs 表→completedBar→详情（L2 断言钉死顺序，主操作先于历史）。
- **P0-3 收口语义**：`#recoverBox` 整块与 HEAD **逐字一致**（我做了 900 字节区块比对＝True）；三按钮（btnRecTranscribe/btnRecReuse/btnRecPublish）在位且 `L4 P0-3 批量重跑入口唯一` 断言在位（全文唯一＋无第二挂点）。**FR-13 display_state/persisted_state/diagnosis_snapshot_id 计数与 HEAD 相同（各 1），且函数级比对证明零函数触碰**——fail-closed 块不可能被本批改动。
- **主题浅色**：`data-theme="light"` 未动（L5 断言＋我全 diff 无 data-theme 命中）。

### E｜测试质量（复核重点 6）—— **PASS（有牙，见 §四）**

- part14（contract `:2162` 起，14a~14k）断言覆盖 D-15 全句：77 夹具 recent_runs 全可达（14a）、completed_total=61 与 run_summary.done 一致（14a/14b）、首页顺序独立复算（14c）、**并列时间戳 run_id 决胜且夹具确含并列对**（14f）、展开 61 无重复遗漏＋页大小 20/20/20/1＋尾页含回退行（14d）、cursor 非 offset（14g）、篡改四态 400（14h）、input_root 范围（14i）、幂等（14j）、state 字段（14k）。`assert_tmp(root,"part14_p16_completed_cursor")` 在 `:2098` 紧跟建根，时序正确。
- S12（前端 `:1403-1421`）与 L1-L5（`:1452-1536`）见 §三-C/D。

## 四、反向证伪（复核重点 8，4 条文件变异＋1 条伪造探针）

| # | 变异 | rc | 咬住它的断言 | 还原 sha256 |
|---|---|---|---|---|
| M1 | server：签名校验短路（`if False and not hmac...`） | **1** | `14h 篡改签名（坏游标 400 人话）<< (200,'None')`（**行为级**：真 200/400 响应） | 一致 |
| M2 | server：keyset `<` 改 `<=` | **1** | `14d 展开全61无重复遗漏 << (64,61)`＋`14d 页大小 20/20/20/1 << [20,20,20,4]`＋`14g`（**行为级**） | 一致 |
| M3 | index：隐藏键改原始路径（`"v2o-hide-done-"+dr`） | **1** | `L3 隐藏键按 data_root 摘要分区`（layout_checks，assert 即 rc=1；行为级由 S12 hashlib 对账兜底） | 一致 |
| M4 | index：`.flowbar` 加 `position:sticky;top:0` | **1** | `L1 不 sticky（反向证伪：加回 sticky 即挂）`（layout_checks） | 一致 |
| 探针⑤ | （不改文件）自算校验和伪造 cursor | decode **接受** | —（即 P3-1 实证：校验和无密钥可伪造） | 不涉及 |

M3/M4 的咬住点是**源码级静态断言**（同 S11f 体例，可接受等价证据）；其行为级兜底分别由 S12（真跑 hideDoneKey 与 hashlib 对账）与真机目检承担。

## 五、P3 Backlog（非阻断）

- **P3-1（本批，A）**：cursor 校验和无密钥、可自算伪造（探针⑤实证）；防意外篡改已够，防伪造需 HMAC＋server_nonce。影响面仅分页窗口，backlog。
- **P3-2（记账）**：TM 转述 numstat（index 184/25、自测 253/137）与实测（178/25、254/0、135/3）有出入，server 178/1 一致；属转述/记账偏差，建议以本报告实测为准归档。
- **P3-3（本批观感）**：勾选「隐藏已完成」且列表全为完成项时，表体为空但仍显示表头（空态提示不出现）；`#completedBar` 有「已隐藏（取消勾选…即可恢复）」文案兜底，不致困惑。
- **P3-4（本批观感）**：展开后每轮 poll 会把 cursor 重置回首页尾，下一次「展开更早」会重拉一段已有行（去重兜底，无重复无遗漏），多一次请求开销；属对齐正确性的代价，可优化为「仅当首页尾变化才重置」。
- **P3-5（既有口径）**：排序键为 `completed_at/updated_at` **字符串比较**，依赖库内时间戳格式同源（同一段代码生成则成立）；若历史数据格式混排（不同时区表示）排序会漂。与既有 recent_runs 排序同口径，非本批引入。

## 六、未覆盖项（如实标注，不推断为通过）

- **真机 UI 未目检**：8765 无监听、本窗口未起服务；横条实际观感（~36px）、960px 断点单列、展开更早点击流、隐藏开关勾选流、完成行详情/输出列显示——交 QA 真机（布局类断言 L1-L5 为静态源码级，行为需真机确认）。
- 大数据量（数百完成项）下逐页展开的体感与 cursor 长链未压测（仅 77 夹具＋我 8-run 夹具）。
- 未跑：真实 whisper、真实 Obsidian 库（沿用既有报告已知缺口）。

## 七、结论

**PASS（无 P0／无 P1；P3×5 进 backlog）。** 范围严查（AST 机器比对）、keyset 独立复算（探针 17/17）、脱敏口径比对、P0-3/FR-13 零改动证明、三套自测实跑（512/167/58 全绿）、5 条证伪（4 咬住＋1 实证 P3-1）全部完成；4 次文件变异全部 sha256 还原一致，工作树仍只有 4 个 `M`。**放行去 QA（真机目检）。**

---

> 注记（2026-09-15，加注人 neat-freak）：针对 P3-2——TM 转述的 numstat 与实测有出入（index.html 实测 178/25 而非 184/25；自测文件实测 254/0、135/3）。口径说明：builder 自报为含空行/上下文的毛计数，reviewer 实测为精确 numstat，**以实测为准**。不影响复核结论。
