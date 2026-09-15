# CODE REVIEW

- Task: **DEVELOP-P1-5「词库与候选易用性修整」**（Plan `docs/pm/PRODUCT_PLAN.md:222`，S 级非 blocking；Plan 明写「不做不阻断失败恢复，**不得升 P0**」）。`CHANGE_REQUEST=B`，留 Phase2 DEVELOP。范围＝Plan 原文六项（限分组标签／trim／空态／筛选计数／组头点击／全选初态）＋ V1.3 处置表归 P1-5 的 6 条（`PRODUCT_PLAN.md:248-256`：`CANDIDATE-UI2 P3-3／P3-4`、`VOCAB-FOLD P3-1／P3-2／P3-3／P3-4`）；共 **12 行、6 个不同修法（两组 1:1 重叠）**。
- Commit: **未提交**（工作树，基线 `HEAD=e340396`）。`git diff --numstat` 实测＝`app/index.html 26/5`、`tests/selftest_p1_2_contract.py 48/0`、`tests/selftest_p1_2_frontend.py 139/2`（**3 files，+213/−7**），与派单书逐字一致；`git diff --check` → **rc=0**。
  - **`app/server.py` 本链 0 改动（独立复算）**：`sha256 = 36d78124802d21d07fdb7673b09832943cac5a0a572dbc3f078063c42b70b21f`，与派单书给的期望值**逐字一致**；`git status --porcelain` 只有上述 3 个 `M`（无 `app/server.py`）。
- Reviewer: code-reviewer（`opencode/muse-spark-1.3-contributor-free`，本窗口 subagent 独立复核，与 builder 非同一审查上下文；先读 CODE_REVIEW.template 与同目录既有报告体例再动手）
- Result: **PASS（无 P0／P1 阻断；P3×6）**。12 项**全做、无越界、无顺手重构**；builder 6 条自陈**6 条全部接受**；重点咬的 **B／C／D** 三条裁定见 §三（C 用**真 Chrome 真实 DOM** 实测、D 裁定既有口径正确、B 判 P3 信息回退但**不返工**）。

> 复核口径：只读业务代码＋独立跑自测＋自写探针＋真浏览器（headless Chrome，真实 DOM 事件）取证；**未改业务代码**（**8 次**反向证伪均为「改回旧形态→取证→还原」，每次以**全量 sha256** 校验还原一致）；未起 8765、未请求线上服务；用户真实视频目录与 Obsidian 库零写；本次只新增本报告一个文件。
> 自写探针（全部落 `/tmp`，未入仓）：`/tmp/p15_probe.py`（独立抽真源码＋最小桩，12 项判定）、`/tmp/p15_mutate.py`（6 条反向证伪）、`/tmp/p15_dom.html`＋`/tmp/p15_dom2.html`（真 Chrome DOM 事件实验）。凡调 handler 的用例首行均断言 `data_root` 在系统 tmp 下。

---

## 一、我自己跑过的命令与退出码（实跑证据，非转述）

| # | 命令 | 实测输出 | rc |
|---|---|---|---|
| 1 | `python3 tests/selftest_p1_2_contract.py` | `SELFTEST ALL PASS（482 项断言）` | **0** |
| 2 | `python3 tests/selftest_p1_2_frontend.py` | `FRONT ALL PASS` ＋ `FRONT SELFTEST PASS`（`grep -c '^PASS'` = **154**） | **0** |
| 3 | `python3 tests/selftest_v26_presets.py` | `SELFTEST ALL PASS`（`grep -c '^PASS'` = **58**） | **0** |
| 4 | `git diff --check` | 无输出 | **0** |
| 5 | `shasum -a 256 app/server.py` | `36d78124802d21d07fdb7673b09832943cac5a0a572dbc3f078063c42b70b21f`（＝派单书期望值） | **0** |
| 6 | `python3 /tmp/p15_probe.py`（我方独立探针） | 12 项判定全过（11 PASS ＋ 1 CONFIRM，含 A1「候选/手加行内已不可区分」的**复现证据**、A4 Σ组头==匹配数、XSS 仍走 `esc()`） | **0** |
| 7 | `python3 /tmp/p15_mutate.py`（6 条反向证伪） | 6/6「改回旧形态即 rc=1」，6/6「还原后全量 sha256 一致」 | **0** |
| 8 | 真 Chrome 无头 DOM 事件实验（`p15_dom2.html`） | 见 §三-C（折叠三路全可用；旧形态同为不折叠） | **0** |
| 9 | 独立数据层核三铁律（预置 3 域 369 条） | 短错词 0／「正词含错词」0／重错词 0；`VOCAB_MAX_ENTRIES=500` 在位 | **0** |

**还原校验（全部证伪跑完后）**：`app/index.html 8221155b0ab61589fa9c3c82a8da883bfde314f829f0936caab102901e379514`、`tests/selftest_p1_2_contract.py 03719d454ed0ef9de717abe38ccae90b20463b971fd4631e0a331dcf4a6227fa`、`tests/selftest_p1_2_frontend.py e6c359bf0d5e34a7a8df91862672972b38250c8e269da3de06448cff3df9f578`，与动手前逐字一致；`git status --short` 仍只有那 3 个 `M`。

---

## 二、范围逐项判定（12 行，全部落 `app/index.html`，后端 0 改动）

| # | Range 项（来源） | 判定 | 关键证据（工作树行号） |
|---|---|---|---|
| 1 | 限分组标签（Plan 六项之①） | **真闭环** | 行内标签改 `vocabGroupLabels[group]`：`index.html:1515`（旧形态为 `esc(e.source\|\|"user")`）；`data-vocdel="'+esc(e.wrong)+'"` 与 `esc(e.wrong/right)` **一字未动** |
| 2 | `VOCAB-FOLD P3-1` 来源标签不一 | **闭环**（口径见 §三-B，1×P3） | 同上；探针实测真实 markup 里 `candidate`／`finance`／`whatever` **0 命中**，行内标签 ⊆ {预置-编程,预置-币圈,预置-金融,我自己加的} |
| 3 | trim（Plan 六项之②） | **真闭环** | `vocabGroupFor`：`index.html:1482` 末尾追加 `.trim()`（只此一处判据；注释 `:1479-1481` 明写「不碰落盘内容」） |
| 4 | `VOCAB-FOLD P3-2` 未 trim | **真闭环** | 同 `:1482`；探针：`  programming  →预置-编程`、`Crypto→预置-币圈`、` preset:finance →预置-金融`（改前全落「我自己加的」——M2 证伪已咬住） |
| 5 | 空态（Plan 六项之③） | **真闭环** | `index.html:1503-1506` 早返回单句；判据是 `!loadedVocabEntries.length`（**整库**为空），**不是**过滤命中数 → 「过滤零命中仍按组显示」口径未变（探针实测 4 组 ×「暂无匹配词条」） |
| 6 | `VOCAB-FOLD P3-3` 空库重复文案 | **真闭环** | 同 `:1503-1506`；M3 证伪已咬住 |
| 7 | 筛选计数（Plan 六项之④） | **真闭环** | `matched` 累加 `index.html:1491`（在过滤 `return` **之后**，计数＝命中数）；summary `:1500-1501` 追加 `· 匹配 N 条`（仅 `filter` 非空时） |
| 8 | `VOCAB-FOLD P3-4` 总数/过滤数不清 | **闭环**（同口径已验，见 §三-F） | 同 `:1500-1501`；探针：未过滤 `已导入词库（N条）` 且 **Σ组头==N**；过滤中 `（N条）· 匹配 M 条` 且 **Σ组头==M**；零命中 `匹配 0 条` 且 Σ组头==0 |
| 9 | 组头点击（Plan 六项之⑤） | **真闭环** | `index.html:1601` 组头 `<label class="candGroupHead" onclick="event.stopPropagation()">`；真 Chrome 实测勾选仍生效、不再折叠（§三-C） |
| 10 | `CANDIDATE-UI2 P3-3` 组头勾选兼折叠 | **闭环** | 同 `:1601`；折叠保留三角标（17px）＋组头行空白（612px）＋键盘三路 |
| 11 | 全选初态（Plan 六项之⑥） | **真闭环** | `index.html:1612` 由 `all.checked=false` 改为 `syncCandidateSelectAll()`（`syncCandidateSelectAll` 本体 `:1620-1622` **未改**）；M6／M8 两条证伪均咬住 |
| 12 | `CANDIDATE-UI2 P3-4` 全选初态不同步 | **闭环**（口径裁定见 §三-D） | 同 `:1612`；探针真跑 markup＋真函数：高中已勾、无 low → 全选**勾**；含默认不勾的 low → 全选**不勾**（＝真状态） |

**越界检查（H）**：diff 只有 **4 个 hunk**，全部落在 `index.html:1475-1615`（词库列表渲染 + 候选渲染两块）；无 CSS 改动、无 DOM 结构改动、无其他函数被碰。除 6 个修法外只多了一个局部变量 `matched` 与注释；**无顺手重构**词库/候选大逻辑。三份测试文件的新增也全部是 P1-5 专属断言块（契约 `part13_p15_vocab_display`／前端 `S11a~S11g`）。

---

## 三、重点咬的 A~J 逐项裁定

### A｜词库三铁律有没有被破 —— **没有；但三铁律里两条本来就没有机械保证（既有缺口，非本批）**

- **落盘链路一字未动（三重证据）**：① `app/server.py` sha256 与基线逐字一致（后端本链 0 改动）；② 逐行核过 `_save_vocab_entries:3004-3015`（`json.dump([{"wrong": e["wrong"], "right": e["right"], "source": str(e.get("source") or "user")}...])` 原子写 tmp+rename）、`_load_vocab_entries:2976-3001`（只 `strip()`、**不改大小写**）、`_validate_vocab_pair:3019-3053`（`wrong<2` 拒收／`wrong==right` 拒收／纯标点拒收／撞基表拒收）；③ 本批前端改的只是**展示**：`data-vocdel` 仍带 `esc(e.wrong)` 原样串，我方探针实测 `data-vocdel=" 空格错词 "`（**含前后空格原样**）→ 删除请求输入与改前逐字相同（后端收到后自行 `strip`，`_handle_vocab_del:3966`）。
- **`trim` 不会改「正确文本含 wrong」判据或落盘**：`.trim()` 只进 `vocabGroupFor` 的 `source` 判据（`:1482`），既不参与 `wrong/right` 比较，也不参与 `_user_rules_revision:3056-3067`（只哈希 `sorted((wrong,right))`）。契约新增 `13a/13b/13c`（`selftest_p1_2_contract.py:2034-2078`）在后端侧把这条边界钉死：13a 保存**逐字落盘不 trim**、13b 读取**只 strip 不改大小写**、13c 候选导入落 `source="candidate"`。
- **三铁律现状（我方独立实测，非转述）**：
  - 「wrong ≥ 2 字」——**代码在位**（`_validate_vocab_pair:3038`、`_handle_vocab_add:3895`、`_read_vocab_preset:4019`）；预置 3 域 369 条实测 0 条违规。
  - 「上限 500」——**代码在位**（`VOCAB_MAX_ENTRIES=500`，载入截断 `:3000` + 新增满额 400 `:3903`）。
  - 「正确文本含 wrong 即删条」——**全仓代码里没有这个判据**（`grep` 仅命中 HANDOFF 的治理文字与本批注释）；预置数据层实测 **0 条**「正词含错词」。
  - 「长 wrong 排前」——**运行时无机械保证**：`apply_corrections`（`src/stage3/normalize.py:145-160`）按**表序**逐条替换，而表序＝`base + 用户对子（追加序）`（`_register_user_rules:3087`）；base 表只有 3 条且**非长度降序**，三域预置文件也**不是长度降序**（实测 `False/False/False`）。
- **裁定**：本批**没有破**任何一条；上述两条属**治理文案 vs 代码/数据的既有缺口**（本链 `server.py` 零改动，不可能是本批引入），记 **P3-5**，是否补排序/补断言交 TM 处置（改排序会动已固化的替换语义，建议仅补文档口径而非改行为）。
- **`selftest_v26_presets.py` 58 项是不是「只是跑过」**：**不是**——它真断言了「错词≥2字（逐域）」「错词<2字读取层丢弃」「同域去重」「错词≠正词」「真实预置零撞基表」「二次导入幂等/revision 不变」等。但**未覆盖**「上限 500」与「长 wrong 排前／正确文本含 wrong 即删条」→ 结论：**三铁律只覆盖了 1 条半**（如实记账，非缺陷）。

### B｜A1「限分组标签」是不是信息丢失 —— **符合 Plan 字面口径（不返工）；但相对 P3-1 原意确实丢了一维信息，判 P3**

- **改前**：候选导入条目（`source="candidate"`，`server.py:3467`）行内显示「来源：candidate」，而它落在组「我自己加的」→ 这就是 P3-1 说的「组名与行内来源不一致」。
- **改后（`index.html:1515`）**：行内标签恒等于组标签。**证据（我方探针真实 markup）**：同一份数据里 `{source:"candidate"}` 与 `{source:"user"}` 两条**都渲染成「（来源：我自己加的）」**，出现 2 次；`candidate`／`finance`／`whatever` 字符串在整块 HTML 里 **0 命中**。→ **「候选导入」与「我手加」在行内已不可区分**。
- **裁定依据**：① Plan `:222` 字面就写「**限分组标签**」，builder 的读法与 DEV_BASELINE 一致；② 用户此前那次投诉的是「**显示不一致**」（同一词条组名与行内标签互相打脸），本改动**消除**了不一致，方向正确、**不构成该投诉的回退**；③ 但 P3-1 原文给的**两个**建议（「user 组标签改为『我自己加的/候选导入』」**或**「行内 candidate 显示为『候选导入』」）**都保留了区分**，第三方选项「抹平」不在其中 → 判 **P3 可用信息回退**（不是 P1/P2：`source` 对功能**零影响**——我方逐处穷举 `server.py` 的 `source` 用途：仅 `_load/_save` 透传、`_active_vocab_entries:3137-3139` 的**预置域开关**（`candidate`/`user` 永不是域名的值）、`_user_rules_revision` 不取它；预置域名为 `programming/crypto/finance`，与 `user`/`candidate` 无撞车；即**不影响删条、落盘顺序、revision、active 过滤、提示词**）。
- **建议（backlog，改动一行级）**：user 组标签写成「我自己加的（含候选导入）」或对 `source==="candidate"` 加来源副标（如「我自己加的 · 候选导入」）——纯展示，不返工本链。**若 TM 认为「候选导入」这个维度对用户筛查 AI 误判很重要，可升为 P2 并派一次 A 级小改**（我的建议是**不必**：候选清单本身仍在页面上，且 source 无功能语义）。

### C｜A5 组头点击是否破坏折叠或可访问性 —— **PASS（真 Chrome 真实 DOM 实测；折叠三路全保留）**

用真 Chrome 无头跑「与 `index.html:1601` 同形 markup」的真实 DOM 事件实验（`/tmp/p15_dom2.html`，结果原样如下）：

| 用例 | 动作 | 实测 | 判定 |
|---|---|---|---|
| N2／N2b | 新形态**直接点勾选框** | `details.open = true`（不折叠）／勾选态翻转为 `false` | **勾选只勾选、不再顺手折叠** ✓ |
| N3 | 新形态点组名文字（label 盒） | `open = true`（不折叠） | ✓ |
| N5 | 新形态**点 summary 本体**（组头行空白/三角标区） | `open` true→false | **折叠仍可用** ✓ |
| N6 | summary 可聚焦 | `document.activeElement === summary` = **true** | **键盘 Space/Enter 走原生激活，仍可折叠** ✓ |
| N7／N8 | 几何 | label `display:inline`；label 宽 **101px** / summary 宽 **740px** → **剩余可点宽 612px**；summary 左边界到 label 左边界 **17px**（三角标区） | 折叠可点区域**没有**退化成「只剩小三角」 ✓ |
| N4／N1 | **对照：改前形态**（label 无 `stopPropagation`） | 点 label 文字 `open = true`；**直接点勾选框 `open = true`** | **P3-3 描述的「顺手折叠」在本机 Chrome 复现不出** |

- **裁定 PASS**：① 折叠**没有**被破坏——三角标区（17px）、组头行的空白区（612px）、键盘三路都还在，「整行只有小三角能点」的退化**不成立**；② 勾选功能完好（N2b 勾选态确实翻转，说明 `stopPropagation` 只拦冒泡、**不 preventDefault**，label→checkbox 的转发照常）；③ **事实澄清（非缺陷）**：在本机 Chrome（真实 DOM）里，**改前形态点勾选框本来也不会折叠**，所以这条改动在本浏览器属**防御性保留**（对会冒泡折叠的浏览器/版本有效），**既无副作用也无本项目可观测收益**。记 **P3-1**：真机需实点一次确认（并入 QA 真机目检）。

### D｜A6「全选初态」口径裁定 —— **builder 的口径正确；建议拒绝「高中都勾就显示全选」的替代口径**

- **原始 `CANDIDATE-UI2 P3-4` 原文**：「有候选加载后 `all.checked=false` 而高中默认已勾，全选显示未选。**建议加载后调一次 `syncCandidateSelectAll()`**」——**原评审给的修法就是 builder 做的这一步**，一字不差。
- **此前 QA 报告口径**（`docs/qa/RERUN-PROGRESS-QA-REPORT.md:67` U1／`:76` U10，真机 AX 证据）：真机记录的状态是「high/medium 勾选、low 未勾、**`全选` 未勾**」，且 U10 明确「`全选` → **4 条全勾（含折叠的 low 组）**，再点 → 全不勾」→ **既有实现语义就是「全选 ＝ 全部候选都勾」**，与 `syncCandidateSelectAll:1621`（`cs.every(...)`）同源。
- **裁定**：**builder 口径正确**（全选＝全部候选；存在默认不勾的 low 时全选就是不勾，这是**真状态**，不是「硬写 false」）。Plan 处置表给 P3-4 的目标是「**选择范围可信／页面所见与提交不一致**」——替代口径（高中都勾就显示全选）会制造「全选框已勾、low 却没选」的**新的**页面≠实际，**恰是 P3-4 要修的病**，应拒绝；builder 自陈「不改 `syncCandidateSelectAll` 本身、按最小改动」**予以接受**。
- **会不会误导用户**：**不会**。`applyVocabCandidates:1886` 的提交集合取自**逐条** `candidateCheckboxes().filter(c=>c.checked)`，**与全选框无关**；全选框对逐条/组头是**双向回写**（`:1948`）。用户看到「全选未勾」＝「确实没全选」，想全选就点它。三级（全选／组头／逐条）状态自洽。

### E｜A3 空态是否把「过滤零命中」也吞了 —— **没有吞；但空态文案的方向写错了一处（P3，本批新增文案）**

- **判据是整库不是过滤结果**：`:1503` `if(!loadedVocabEntries.length)`。我方探针：库非空 + 过滤零命中 → 仍渲染 **4 个 `vocabGroup` ＋ 4 句「暂无匹配词条」**（口径与 `VOCAB-FOLD` 原文一致）；真空库 → 单句、无组块、无「暂无匹配词条」。**PASS。**
- **空库＋有过滤串时 summary 显示什么**：`已导入词库（0条）· 匹配 0 条`。**不自相矛盾**（总数 0、命中 0，与空态单句一致），但空库时「· 匹配 0 条」纯属噪声（P3-2，一行条件即可省）。
- **P3-3（本批新增文案的**事实错误**）**：`index.html:1504` 写「跑一次 AI 审查生成候选，**或在上方手动添加**」——实测 DOM 顺序：`<details id="vocabListDetails">`（`:263`，内含 summary/filter/vocabList）之后才是手动添加行 `#vocWrong/#vocRight/#btnVocAdd`（`:268-271`）→ 手动添加在**下方**，不在上方。用户读完会往上看。**建议同批改成「或在下方手动添加」**（纯文案一行；本项非阻断，但属本批新增、修起来零风险，倾向 TM 判本批顺手修）。

### F｜A4 筛选计数与组头是否同口径 —— **PASS（Σ组头 == 匹配数，已实测）**

- summary ＝ `已导入词库（N条）`（N＝`loadedVocabEntries.length`，总数）＋ 过滤时 `· 匹配 M 条`（M＝`matched`）；组头 ＝ `items.length`（**过滤后**该组条数）。
- **实测对账（我方探针，真实函数真跑）**：未过滤 → N=5、**Σ组头=5**、summary 无「匹配」；过滤「错词」命中全部 → `（5条）· 匹配 5 条`、Σ组头=5；过滤「绝不命中」→ `（5条）· 匹配 0 条`、**Σ组头=0**。三档全部自洽、`Σ组头 ≡ M`。
- 双口径误读已消除（P3-4 的目标达成）：总数与命中数**分开明写**，不再让「（303条）」被读成「这次会应用 303 条」。残留观感（P3，不必修）：过滤中「N 条」与组头之和仍不等（一个总数、一个命中数），但旁有 `· 匹配 M 条` 兜住。

### G｜前序语义无回退 —— **PASS（后端零改动 + 前端 diff 只落 4 hunk）**

- **后端侧（P0-1/P0-2/P0-3 的 FR-13/FR-14/FR-17、P1-2 契约、P1-3 五桶 `STATE_BUCKET`/`_state_bucket` fail-closed、P1-4 脱敏白名单 `FAIL_DIGEST_FIELDS`/唯一出口 `digestEntry`、D-12、No-Clobber）**：`app/server.py` **`git diff --numstat` 0 行**、sha256 与基线逐字一致 → **逐字未动，不存在回退可能**（契约 482 项全 PASS 亦复证）。
- **前端侧**：diff 只有 `index.html` 的 4 个 hunk，行区间 **1475-1615**，全部落在 `vocabGroupFor` / `renderVocabList` / `loadVocabCandidates` 三个函数内；P1-3 的 `vocabApplyPct`／`setCandidateControls`／`batchLockHint`、P1-4 的 `digestEntry`／`FAIL_DIGEST_FIELDS`／`diagCache`、P0-3 的 `#recoverBox`／`say` 截断／长面板 **0 命中**于本 diff；既有前端断言 S1~S10（139 条）全绿。
- **主题默认浅色**：`index.html:2` ＝ `<html lang="zh-CN" data-theme="light">`，**未动**（实测）。
- **FR-9「现有功能不回退」**：监听/停止/目录浏览/路径记忆/单条重试/清空预览/笔记预览/访达打开/词库/候选应用/错词重跑/浅色主题——本 diff 未触及对应函数或 DOM id；轮询与批量链路由 S1~S8j2 断言守。

### H｜范围 —— **12 项全做、无越界、无顺手重构**

见 §二 12 行表（全部真闭环）与「越界检查」。**「B 批 6 条」未被含糊过去**：`CANDIDATE-UI2 P3-3/P3-4`、`VOCAB-FOLD P3-1/P3-2/P3-3/P3-4` 各有一条可指认的实现行号与一条可咬住的断言（§四）。唯一超出「6 个修法」的新增是局部变量 `matched` 与注释（注释体量远大于代码，属体例选择，不构成越界）。

### I｜自测「有牙」—— **抽检 8 条：6 条有牙、1 条无牙（P3）、1 条为 markup 级断言（P3）**

| 变异 | 内容 | rc | 咬住它的断言 | 判定 |
|---|---|---|---|---|
| M2 | 去掉 `vocabGroupFor` 的 `.trim()` | **1** | `S11a 分组判定去前后空格`（实测返回 `"user"` 而非 `"programming"`）＋`S11a preset 前缀带空格同组`＋`S11b` | **有牙（行为级）** |
| M6 | `syncCandidateSelectAll()` 改回 `all.checked=false;` | **1** | `S11g 全选初态＝真状态` | **有牙（行为级）** |
| M8 | 整条 `syncCandidateSelectAll();` 调用**删掉** | **1** | `S11g 全选初态＝真状态` | **有牙** |
| M4 | 行内标签改回 `esc(e.source\|\|"user")` | **1** | `S11b 行内来源标签恒为四组标签之一` | **有牙** |
| M3 | 删掉空库早返回 | **1** | `S11e 空库只留一句人话` | **有牙** |
| M5 | 组头去掉 `onclick="event.stopPropagation()"` | **1** | `S11f 三个组头都掐断冒泡` | 有牙（但见下） |
| M7 | 删掉 `· 匹配 N 条` | **1** | `S11d 过滤中 summary 同时报总数与匹配数` | **有牙** |
| **M9** | 删掉 `syncCandidateSelectAll` 里的**组头回写**那行 | **0（未咬住）** | — | **无牙 → P3-4** |

- **不是自我实现（M2／M6 单独判断）**：M2 的断言**调用真源码抽出的 `vocabGroupFor`** 并比对其**返回值**（`FAIL ... << "user"`），是真行为；M6／M8 走真 `loadVocabCandidates` → 真 `syncCandidateSelectAll`，读的是真函数写出的 `candidateSelectAll.checked`。两者都**不是**「比对源码字符串」。
- **P3-4（无牙，1 条）**：`S11g 组头初态同样按真勾选算` 是**假信心**——桩的 `candListStub.querySelectorAll`（`tests/selftest_p1_2_frontend.py:1215-1234`）**每次从 innerHTML 重新正则解析**，`syncCandidateSelectAll` 对 `g.checked` 的写回落在一次性临时对象上；断言读到的其实是 **markup 里的默认 `checked` 属性**。因此 M9（删组头回写）**rc=0 未咬住**。属**既有函数**（P1-2 期就有，本批未改）+ 本批新增的弱断言，**非阻断**，建议桩改成「元素对象持久化」或在断言前重新取同一对象。
- **P3-3（markup 级断言）**：`S11f` 断言的是渲染出的 HTML 里三个组头都带该属性（内联 `onclick` 属性在位＝浏览器必执行，属可接受的等价证据），但**验不到折叠行为**；结合 §三-C 的实测（本机 Chrome 改前也不折叠），建议把「点一次确认」交 QA 真机目检，不要靠 S11f 推断行为。

### J｜数据安全 —— **PASS**

- **契约新增 `part13_p15_vocab_display`**（`tests/selftest_p1_2_contract.py:2035`）：第 2 行即 `assert_tmp(root, "part13_p15_vocab_display")`（`:2048`，**首行时序正确**），root 由 `make_data_root` 建于系统 tmp（`p12_P15_*`），`finally: shutil.rmtree` 清理；调用的 `_save/_load_vocab_entries`、`_handle_vocab_candidates_get`、`_run_vocab_candidates_apply` **全部只落该 tmp**（`vocab-user.json`/`vocab-candidates.json` 均在 root 下），未传 `ob_vault_root`（P1-三1 语义：缺键不回写）。
- **前端新增 S11**：全程 node 桩 + `FETCH_QUEUE` 假响应（`data_root: "/tmp/p12-s11"`），**不发真请求**；harness 只写 `tempfile.mkdtemp(prefix="p12_front_")` 下的 JS 并在 `finally` rmtree。
- 全仓测试新代码**零**真实路径/真实视频目录/Obsidian 库引用；未起 8765；未写 `data/state.db`。我方探针同样只落 `/tmp`。

---

## 四、反向证伪与 sha256（抽检清单）

- 动手前基线：`app/index.html 8221155b…e379514`、`tests/selftest_p1_2_contract.py 03719d45…a6227fa`、`tests/selftest_p1_2_frontend.py e6c359bf…3df9f578`、`app/server.py 36d78124…c42b70b21f`。
- 8 次变异全部**先改坏→跑→要求 rc=1→还原→比对全量 sha256**；`M2`／`M6`／`M8` 三条按要求单独定位到**具体断言名**（见 §三-I 表）；`M9` 未咬住已如实记录。
- 每次还原后 `sha256` 与基线**逐字一致**，`git status --porcelain` 全程只有那 3 个 `M`。

---

## 五、P3 Backlog（非阻断，写明归属）

- **P3-1（本批，A5）**：组头 `stopPropagation` 在本机 Chrome 属**防御性保留**（改前形态实测也不折叠）——真机实点一次确认折叠路径（并入 QA 真机目检）。
- **P3-2（本批，A4/E）**：空库时 summary 仍带 `· 匹配 0 条`；建议空库时不显示「匹配」分句。
- **P3-3（本批，A3）**：`index.html:1504` 空态文案「在**上方**手动添加」方向写错（添加行 `:268-271` 在**下方**）——**建议本批顺手改一行**。
- **P3-4（既有+本批弱断言，I）**：`S11g 组头初态同样按真勾选算` 无牙（桩每次重解析 markup）；建议桩改为元素对象持久化。
- **P3-5（既有，A）**：三铁律中「长 wrong 排前」「正确文本含 wrong 即删条」在代码/数据里**无机械保证**（本链 `server.py` 零改动，非本批引入）；`selftest_v26_presets.py` 58 项未覆盖「上限 500」与这两条。
- **P3-6（本批，B）**：行内来源标签抹平后「候选导入 vs 手加」不可区分（§三-B；Plan 字面支持，**不返工**；若用户要区分再加来源副标）。
- **P3-7（既有，E）**：`renderVocabList` 的「空」不区分「尚未加载／加载失败」与「真空」（`loadVocab:1533` 失败静默 `.catch(function(){})`、且 `oninput=renderVocabList`（`:2028`）在数据到位前即可触发）→ 后端 5xx 时用户可能在筛选框一输入就被告知「词库还没有词条」。改前形态同样是「空」，属既有缺口，建议**分别给「加载中／读取失败」文案**（P3，不返工）。

---

## 六、未覆盖项（如实标注，不推断为通过）

- **真机 UI 未目检**：8765 无监听、本窗口未起服务；S11 系列为「抽真源码 + node 桩」，**真浏览器点击/折叠**我改用 headless Chrome 同形 markup 实验替代（§三-C），但**与真页面真数据的端到端点击未跑**（交 QA 真机）。
- **词库 303 条真实规模下的空态/筛选/分组观感未目检**（只跑合成数据）。
- **「长 wrong 排前」若补齐，需评估是否改变既有替换结果**——本报告只判定「无机械保证」，**未做影响面实测**（不属本批范围）。
- 未跑：真实 whisper、真实 Obsidian 库、F 端到端应用候选（沿用既有报告的已知缺口）。

---

# 复核二（code-reviewer，2026-09-15）：P3-3＋P3-4 返工复核

- 复核范围：**只**复核本批新写文案事实错误（上节 **P3-3**）与本批新增断言假信心（上节 **P3-4**）的返工；上一节正文一字未动，本节为追加。
- Reviewer：code-reviewer（`opencode/muse-spark-1.3-contributor-free`，本窗口 subagent，与 builder 非同一审查上下文）。
- **Result：PASS（无 P0／无 P1；P3-3 已闭、P3-4 已闭）**。放行去 QA。
- 口径：只读业务代码＋独立跑三套自测＋自写探针（重建法／断言集合比对／桩 vs 真 Chrome DOM 等价）＋**4 条自己动手的反向证伪**；**未改业务代码**（每次变异均「改坏→取证→从 `/tmp` 备份拷回→比对全量 sha256」）；未起 8765、未请求线上服务、未碰用户真实目录与 Obsidian 库；本次只追加本文件。

## 复核二·一｜实跑命令与 rc（实测，非转述）

| # | 命令 | 实测输出 | rc |
|---|---|---|---|
| 1 | `python3 tests/selftest_p1_2_contract.py` | `SELFTEST ALL PASS（482 项断言）` | **0** |
| 2 | `python3 tests/selftest_p1_2_frontend.py` | `FRONT SELFTEST PASS`；`grep -c '^PASS'`＝**157**、`^FAIL`＝0 | **0** |
| 3 | `python3 tests/selftest_v26_presets.py` | `SELFTEST ALL PASS`（58） | **0** |
| 4 | `git diff --check` | 无输出 | **0** |
| 5 | `shasum -a 256 app/server.py` | `36d78124802d21d07fdb7673b09832943cac5a0a572dbc3f078063c42b70b21f`（＝派单书期望值，逐字一致） | **0** |
| 6 | `git diff --numstat` | `app/index.html 29/5`、`tests/selftest_p1_2_contract.py 48/0`、`tests/selftest_p1_2_frontend.py 182/2`（3 files） | **0** |
| 7 | `git status --porcelain` | 只有 3 个 `M` ＋ 本报告 `??`（无 `app/server.py`、无 `docs/`／`src/` 改动） | **0** |
| 8 | `/tmp/p15rev2_asserts.py`（断言集合机器比对） | 无删除／无改名／同名调用文本 0 变化／顺序子序列校验 True | **0** |
| 9 | `/tmp/p15rev2_realdom.py`（桩 vs 真 Chrome DOM 等价） | 12/12 条目一致（正常源码与 M9 形态各 6） | **0** |
| 10 | `/tmp/p15rev2_mutate.py`（3 条反向证伪＋还原） | M9 rc=1、P3-3 回退 rc=1、关持久影子 rc=1；3/3 还原后 sha256 与基线逐字一致 | **0** |

**本回复核基线 sha256**（动手前自分自算，全部已还原）：`app/index.html b412ba99fae801a15d3225755f9da73e469625b3483ba19fa83ce29d02cb92ed`、`tests/selftest_p1_2_frontend.py 49e0b336a81cd9b53adefb46c1b8ea0669bb67dff964a49a370ac5f4b9160cb4`、`tests/selftest_p1_2_contract.py 03719d454ed0ef9de717abe38ccae90b20463b971fd4631e0a331dcf4a6227fa`（**与上一节点录的契约基线逐字相同 → 本批契约文件内容零改动**）、`app/server.py 36d78124…c42b70b21f`。备份：`/tmp/p15rev2_bak/{index.html,frontend.py}`（拷回即还原，**全程未用 `git checkout`**，工作树是本批未提交交付）。

## 复核二·二｜返工净增量核算（重建法，不靠 builder 自报）

`app/index.html` 的返工只有一处可指认改动（P3-3）。把新增的 3 行注释与改写的 1 行文案**反向撤销**后重建「返工前」文件，再用 `git diff --no-index --numstat` 量：

| 对比 | 结果 |
|---|---|
| 重建文件（＝返工前） vs `HEAD:e340396` | **26/5**（与上一节 `git diff --numstat` 记录**逐字相同**，证明重建无偏） |
| 当前文件 vs `HEAD:e340396` | **29/5**（＝派单书累计值） |
| 当前文件 vs 重建文件（＝本次返工净增量） | **+4/−1** |

→ builder 自报 `index.html +4/−1` **精确成立**；`frontend +47/−4`（净 +43）与上一节 139 → 现 182 **净额一致**（返工是「替换 4 行 round-1 新增行 + 新增 47 行」，对 HEAD 的累计删除数仍是 2，故只看 numstat 无法独立量出内部 −4，属**证据边界**而非不一致）；`contract 0` 成立（sha256 与上一节基线逐字相同）。**无记账偏差。**

## 复核二·三｜P3-3 判定：**真闭环**

- **改法在位**：`app/index.html:1507` 空态文案现为「词库还没有词条：跑一次 AI 审查生成候选，**或手动添加词条**。」；理由注释在 `:1503-1505`（明写「不写方位词／添加行在列表之后／方位词会随 P1-6 布局漂移」）。整块早返回 `:1506-1509` 未动别处。
- **不依赖方位、与事实不矛盾（三项独立核对）**：① 文案中**已无任何方位词**（「上方／下方／左侧」0 命中）；② 两个动作都真实存在——添加行 `#vocWrong`/`#vocRight`/`#btnVocAdd` 在 `:268-271`，「跑一次 AI 审查」是全页既有措辞（`:1590`／`:1592`／`:1594`／`:1893` 四处同款）；③ 注释里引用的行号 `:268-271`、`:263-267` **实测准确**（无新的「注释写错」类事实错误）。
- **断言是整条比对，不是子串**：`:1309-1311` `ck("S11e 空库空态文案整条一致…", vempty === '<div class="hint">词库还没有词条：跑一次 AI 审查生成候选，或手动添加词条。</div>', vempty)`——`===` 全串相等，方位词回来即红。
- **我的反向证伪 ②**：把文案改回「或在上方手动添加。」→ 前端 rc=**1**，唯一失败项 `FAIL S11e 空库空态文案整条一致… << "<div class=\"hint\">词库还没有词条：跑一次 AI 审查生成候选，或在上方手动添加。</div>"` → 还原后 `b412ba99…` 逐字一致。
- **有没有顺手改别的文案**：没有——重建法证明本次 `index.html` 只动了这 1 行文案＋3 行注释；全批 diff 里「返工」标记也只出现在 `index.html:1503-1505` 与前端 4 处断言注释。
- **裁定：P3-3 已闭**（且比上一节建议的「改成下方」更稳：不写方位，日后 P1-6 挪动不会二次变成事实错误）。

## 复核二·四｜P3-4 判定：**真闭环**（桩在真实 DOM 语义上等价；M9 我自己复现咬住）

### 1）桩的持久化影子是否等价于真实 DOM —— **等价（node 桩 vs 真 Chrome 真实 DOM 12/12 一致）**

探针 `/tmp/p15rev2_realdom.py`：真源码一律从 `index.html`／自测文件**抽取**（不手抄），两套环境（node 桩；headless Chrome 真实 DOM）跑**同一串**动作，逐项比对（`candListStub` 桩本体也是从 `tests/selftest_p1_2_frontend.py:1221-1249` 抽真文本，验的就是它本身）：

| 动作 | node 桩 | 真 Chrome DOM | 判定 |
|---|---|---|---|
| 夹具 A 初态组头 | `high:true,medium:true,low:false` `all=true` | 同左 | 一致 |
| 夹具 A 取消一个已勾项后 | `high:false,medium:true,low:false` `all=false` | 同左 | 一致 |
| 夹具 B 初态（medium 0 条） | `high:true,medium:false,low:false` | 同左 | 一致 |
| **重写 `innerHTML` 后（不调 sync）** | `high:true,medium:true,low:false` `item0=true` | 同左 | 一致 |
| M9 形态（删组头回写）下同上 4 项 | `medium` 停在 `true` | `medium` 停在 `true` | 一致 |

- **「改 property → 再 query 拿回同一元素」成立**：桩按 `i:<index>`／`g:<level>` 记住首解对象，此后 `querySelectorAll` 返回**同一批对象**；真 DOM 同样如此（`g.checked` 写回可被再次 query 读到）→ 12/12 一致。
- **「重写 `innerHTML` 才作废重建」成立**：桩 `innerHTML` setter 里 `reg = {}`（`:1245-1247`），真 DOM 重写即销毁子节点——两者在「重写后不调 sync 应回到 markup 默认」这一档**逐字一致**（`item0=true`）。这正回答了「桩永远不重建会不会让本该重建的场景变绿」：**不会**，桩与真 DOM 在重建档同值；而且该档结果与上一档（取消后的 `false`）不同，说明它不是恒真断言。
- **反向验桩（我自己的第 3 条证伪）**：把 `if(!reg[key]) reg[key] = mk(...)` 改成每次新建（＝关掉持久影子）→ rc=**1**，在 `S11g 取消已勾项…` 处 `citems0[0].onchange is not a function` 抛错（`harness.js:2245`）。含义：新断言**读的是桩里那份真状态**，光源码正确、桩不持久也一样红 → **不是自我实现，也不是恒真**。（代价是该失败形态为异常中断而非干净 FAIL，记 P3-新1，不阻断。）

### 2）新断言是否真与 markup 默认相反 —— **相反（实测三方对账）**

真源码渲染出的真实 markup（探针落盘）：夹具 A 组头 markup `high=checked, medium=checked, low=未勾`；夹具 B 组头 markup `high=checked, **medium=checked**（0 条也一样勾）, low=未勾`。

- `S11g 空组组头按 0 条算`（`:1375-1380`）期望 `high:true,**medium:false**,low:false`：真值 `medium=false`（`items.length>0&&…`）**与 markup 默认相反** → 只有真跑过组头回写才过。
- `S11g 取消已勾项后组头与全选跟着取消`（`:1351-1357`）期望 `high:false,medium:true,low:false` 且 `all=false`：真值 `high=false` **与 markup 默认相反**（行为级：改 property＋调真源码 `:1616` 绑的 onchange）。
- 反面对照：保留的 `S11g 组头初态同样按真勾选算`（现 `:1338-1343`）期望 `high:true,medium:true,low:false` **＝夹具 A 的 markup 默认**（真 Chrome 实测 `dom.A.init` 与 markup 默认逐字相同）→ 单靠它仍咬不住 M9，builder 的自陈属实。

### 3）我自己复现 M9（本轮核心验收）—— **rc=1，咬住两条新断言**

删掉 `app/index.html:1625` 的组头回写语句（从真源码切出，274 字符整行）→

```
FRONT FAIL 2: S11g 取消已勾项后组头与全选跟着取消（组头回写被删即 rc=1）
              | S11g 空组组头按 0 条算（真值 false，不是 markup 默认的 checked）
FAIL S11g 取消已勾项后组头与全选跟着取消  << [false,["high:true","medium:true","low:false"]]
FAIL S11g 空组组头按 0 条算            << ["high:true","medium:true","low:false"]
```

还原后 `index.html` sha256 ＝ `b412ba99…` 逐字一致。**上节 M9「rc=0 未咬住」的缺口已由本轮补上**（并与真 Chrome 的 `domM9.B.init = high:true,medium:true,low:false` 互相印证：删回写后组头停在 markup 默认）。

### 4）**裁定：保留 `:1338`（原 `:1330`）那条——接受，不要求补**

理由三条：① 它的期望值（`high:true,medium:true,low:false`）是**该夹具的真值**，不是编造值，属「正确的冗余断言」而非假信心；② 上节判它的问题实质是「它是**唯一**守卫且不能单独咬 M9」，该缺口已由两条与 markup 默认相反的新断言补上，且**我实测咬住**（见上）；③ 它仍有独立价值：守 `全选初态＝真状态` 那条路径的组头侧同源（配合 `:1336` 的 `all=true`，M6／M8 改回硬写 `false` 时仍红）。**非必须的改进（记 P3-新3，backlog）**：把该断言挪到夹具 B 之后或用空组夹具，让它自身也具判别力。

### 5）另外核了 builder 那句「`S11f` 有牙、属结构级欠覆盖而非假信心」—— **成立**

- **有牙**：删掉 `index.html:1604` 的 `onclick="event.stopPropagation()"` → 前端 rc=**1**，唯一失败项 `FAIL S11f 三个组头都掐断冒泡 << ["<label class=\"candGroupHead\" >", …]`（我的第 4 条证伪；与上节 M5 结论一致，且证明返工没有把这条断言弄钝）。
- **属结构级欠覆盖**：它断言的是渲染出的 markup 里内联属性在位（浏览器必执行，属可接受等价证据），验不到折叠/勾选**行为**——与我上节 P3-1／P3-3 的记录一致（本机 Chrome 改前形态实测也不折叠），**交 QA 真机实点一次**。
- **不是假信心**：其命题（三个组头都掐断冒泡）被 markup 蕴含，为真；与「期望值＝markup 默认」那类假信心不同源。**采纳 builder 口径。**

## 复核二·五｜「只加不减」机器比对（脚本，非目测）

`/tmp/p15rev2_asserts.py`（`git show HEAD:tests/selftest_p1_2_frontend.py` vs 工作树，抽取全部 `ck("名",…)` 平衡括号调用文本）：

- **HEAD 命名断言 139 → 现 157**（`ck(` 计数 140→158，含 1 处 `function ck(` 定义）；上一节 154（＝139＋round-1 新增 15 条 S11）→ 现 **157**（＝15＋本轮 3 条）——**154→157，与 builder 自陈逐字一致**。
- **被删 0 条、改名 0 条、同名调用文本变化 0 条、HEAD 顺序在现文件仍是子序列**（True）。
- **物理删除行仅 2 行**，且都是「原地改写」型：`"effectiveDataRoot", "lastLongText"]`（DECLS 行）与 `await s8(); await s9(); await s10();`（接上 `s11()`），**内容未被移除**。
- **本轮 3 条新增名的落地与自陈完全一致**：`S11e 空库空态文案整条一致`（`:1309`）／`S11g 取消已勾项后组头与全选跟着取消`（`:1351`）／`S11g 空组组头按 0 条算`（`:1375`）。
- **上一节引用过的 S11 断言名逐条仍在**（用上一节正文的引用做前缀比对：`S11a 分组判定去前后空格`／`S11a preset 前缀带空格同组`／`S11b 行内来源标签恒为四组标签之一`／`S11d 过滤中 summary…`／`S11e 空库只留一句人话`／`S11f 三个组头都掐断冒泡`／`S11g 全选初态＝真状态`／`S11g 组头初态同样按真勾选算` 全部命中，无改名）。
- **证据边界（如实标注）**：返工前的前端文件**无快照**（未提交、无备份），故「round-1 那 15 条的调用文本与现在逐字相同」只能由「名字全在＋总数 15→18 恰为 +3＋顺序未变」间接支持，**不能逐字比对**；对 HEAD 已有断言则已逐字比对，0 变化。

## 复核二·六｜越界／红线／数据安全（逐项实测）

- **只碰两个文件**：`git status --porcelain` 仅 `M app/index.html`／`M tests/selftest_p1_2_frontend.py`／`M tests/selftest_p1_2_contract.py`（契约 sha256 与上一节逐字相同 → **本批未动**）＋本报告自身 `??`；`docs/`、`src/` 零改动；`app/server.py` 零改动（sha256 复算＝期望值）。
- **主题浅色**：`index.html:2` ＝ `<html lang="zh-CN" data-theme="light">`，未动；本批 diff 内 `data-theme` 0 命中。
- **前端 diff 对前序语义零接触**：`_strip_paths`／`digestEntry`／`FAIL_DIGEST_FIELDS`／`vocabApplyPct`／`recoverBox`／`STATE_BUCKET` 等关键字在 `index.html` 的 diff 里 **0 命中**；返工只落在 `1503-1507`（P3-3）与测试文件内。**重建法**进一步证明本批 `index.html` 自 round-1 以来只动了 P3-3 那一处 → P0／P1-2／P1-3／P1-4 已收口语义**逐字未动**。
- **词库三铁律**：落盘链路（`server.py`）零改动；前端 `data-vocdel` 仍带原样错词（`S11c` 通过，实测 `data-vocdel=" 带空格错词 "` 含前后空格）；trim 仍只进 `vocabGroupFor` 判据（`:1482`），返工未触碰。
- **No-Clobber／D-12（`_strip_paths`）／上限 500**：全在后端，本链 `server.py` 零改动 → 不可被本批触碰。
- **数据安全**：契约 `part13_p15_vocab_display` 第 2 行仍是 `assert_tmp(root, "part13_p15_vocab_display")`（`:2048`，紧跟 `make_data_root`，时序正确；文件字节未变）；S11 区段**只用外置假响应**（`FETCH_QUEUE`，`data_root: "/tmp/p12-s11"`）＋合成数据，`/Users/`、`/Volumes/`、真实用户名、`http://`、`8765`、`realpath` **0 命中**，不发真请求、不落真实目录。我方探针同样只落 `/tmp`。

## 复核二·七｜上一节 7×P3 现状逐条

| # | 上节条目 | 现状 | 证据 |
|---|---|---|---|
| P3-1 | 组头 `stopPropagation` 属本机 Chrome 防御性保留；真机需实点确认 | **仍开**（未变，非本轮范围） | `index.html:1604` 未动；`S11f` 仍为 markup 级断言（本轮复验有牙 rc=1）；折叠行为交 QA 真机 |
| P3-2 | 空库时 summary 仍带「· 匹配 0 条」 | **仍开**（未修） | `index.html:1501` 判据仅 `filter` 非空；空库＋有过滤串 → 「已导入词库（0条）· 匹配 0 条」 |
| **P3-3** | 空态文案「在上方手动添加」是事实错误 | **已闭** | `:1507` 改「或手动添加词条」；`:1309-1311` 整条比对；我证伪 rc=1（见·三） |
| **P3-4** | `S11g 组头初态…` 无牙（桩每次重解析＝假信心） | **已闭** | 桩改持久影子 `:1221-1249`；我复现 M9 rc=1 咬住两条新断言；桩 vs 真 DOM 12/12 一致（见·四） |
| P3-5 | 三铁律中「长 wrong 排前」「正词含 wrong 即删条」无机械保证（既有） | **仍开**（既有，非本批） | `app/server.py` 本链零改动（sha256 逐字一致）；`selftest_v26_presets.py` 58 项覆盖面未变 |
| P3-6 | 行内来源标签抹平后「候选导入 vs 手加」不可区分（Plan 字面支持，不返工） | **仍开**（裁定不变） | `index.html:1518` 未动（重建法证明本批只动 P3-3 处） |
| P3-7 | 空态不区分「尚未加载／加载失败」与「真空」（既有） | **仍开**（既有） | `:1506` 判据仍只看 `loadedVocabEntries.length` |

**新增（本节记，非阻断，进 backlog）**

- **P3-新1（测试体例）**：持久影子被关掉时，`S11g 取消已勾项…` 以 `TypeError` 中断而非干净 FAIL（`harness.js:2245`）——rc 仍为 1，**不削弱闸门**；建议在 `citems0[0].onchange()` 前先判 `typeof === "function"`（可选）。
- **P3-新2（覆盖）**：`el("vocabList")` 桩的 `querySelectorAll` 恒返回 `[]`（`tests/selftest_p1_2_frontend.py:100`），词库删除按钮的**点击链**在桩里不可达（只验了 `data-vocdel` 字符串，`S11c`）→ 交 QA 真机点一次删除。另：桩按 `i:<index>` 去重，而真实后端 `index` 由 `enumerate` **全局唯一**（`app/server.py:3353`）→ 生产数据下等价，畸形候选（同 index 跨组）下不等价（低风险，未实测畸形数据）。
- **P3-新3（可选改进）**：把保留的 `S11g 组头初态同样按真勾选算`（`:1338`）挪到夹具 B 之后或改用空组夹具，使其自身也具判别力（见·四-4；不返工）。

## 复核二·八｜未覆盖项（如实标注，不推断为通过）

- **真机 UI 仍未目检**：8765 无监听、本窗口未起服务；本轮新增的等价性证据是「node 桩 vs headless Chrome 真实 DOM 同形实验」，**与真页面真数据的端到端点击未跑**（交 QA 真机：点组头勾选不折叠／取消勾选后组头与全选跟随／词库删除按钮／空态文案）。
- 词库 303 条真实规模下的空态与分组观感未目检（只跑合成数据）。
- round-1 那 15 条 S11 断言文本无快照可比（见·五 证据边界）。
- 未跑：真实 whisper、真实 Obsidian 库、端到端应用候选（沿用上节已知缺口）。

## 复核二·九｜结论

**PASS（无 P0／无 P1 阻断；Plan `:222` 明写本项不得升 P0，本节亦未升）。** 上节的 2×P3（P3-3 文案事实错误、P3-4 断言假信心）**均已真闭环**并经我独立证伪复现（P3-3 rc=1、M9 rc=1 且咬住两条新断言、桩与真实 DOM 12/12 等价）；「只加不减」机器比对通过；越界、红线、数据安全三项全过；4 条反向证伪**全部还原，全量 sha256 与基线逐字一致**，工作树仍只有那 3 个 `M`。余下 5×P3 与新增 3×P3 均为非阻断，进 backlog。**放行去 QA。**
