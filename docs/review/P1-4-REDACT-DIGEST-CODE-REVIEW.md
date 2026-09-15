# CODE REVIEW

- Task: **DEVELOP-P1-4「脱敏摘要复制（HD-2=A）」**（Plan `docs/pm/PRODUCT_PLAN.md:221`，S 级非 blocking；需求原文 `FR-3` 在 `:49`，`HD-2=A` 在 `:262`）。`CHANGE_REQUEST=B`，留 Phase2 DEVELOP。**TM 已记跳步原因**（由 Plan 既有 FR-3／HD-2 直接定义，属局部功能落地，跳 planner／product-reviewer，仍走 code-reviewer＋qa＋supervisor）——我方核过 Plan 原文确实已逐条写死摘要允许字段（FR-3 那 7 类），**跳步理由成立**。
- Commit: **未提交**（全在工作树）。`git diff --stat` 实测＝`app/index.html 217`、`app/server.py 3`、`tests/selftest_p1_2_contract.py 99`、`tests/selftest_p1_2_frontend.py 257`（合计 559/17）——与派单书**逐字一致**。`git rev-parse HEAD` = `fa6ba1b77c85e7dd401ae2e6de4897d31dcadf55`（＝派单书基线，无偏差）。`git diff --check` → rc=0。后端**只加 3 行**（`server.py:1630-1632`：注释 2 行＋`source_dir_tail` 1 行），与 builder 自陈一致。
- Reviewer: code-reviewer（`opencode/muse-spark-1.3-contributor-free`，本窗口 subagent 独立复核，与 builder 非同一审查上下文；先读 `CODE_REVIEW.template.md` 与同目录 P1-3 报告体例再动手）
- Result: **PASS（无 P0/P1 阻断；P2×2 ＋ P3×8）**。DoD 5 条 **5/5 真闭环**；A~I **9 项中 7 项合意、2 项部分成立并已降级为 P2／P3**；builder 10 条自陈 **10 条全接受**（其中 #1／#2／#5 要求补测或补口径，非返工）。

> 复核口径：只读业务代码＋独立跑自测＋自写探针；**未改业务代码**（33 次反向证伪尝试均为「改坏→取证→还原」，每次以全量 sha256 校验还原一致；其中 **27 条为活性变异**计入证据，另 6 条因分支在夹具下不可达/构造失败而剔除、不作证据，自纠说明见 H 节）；未起 8765、未请求线上服务；用户真实视频目录与 Obsidian 库**零写**（唯一触碰是 `_diag_alternate_paths` 的**只读**遍历，且仅发生在我方自建探针里，仓内自测不触发——见 F）；**本次只新增本报告一个文件**。
> 自写探针（全部落 `/tmp`，未入仓）：`/tmp/p14rev/race.js`（前端诊断缓存跨目录串味）、`/tmp/p14rev/diffeq.js`（前后端脱敏口径逐例差分）、`/tmp/p14rev/alt_probe.py`／`alt_probe2.py`（真 16 条分支与替代路径脱敏覆盖度）。凡调 handler 的探针首行均断言 `data_root` 在系统 tmp 下。

---

## 一、我自己跑过的命令与退出码（实跑证据，非转述）

| # | 命令 | 实测输出 | rc |
|---|---|---|---|
| 1 | `python3 tests/selftest_p1_2_contract.py` | `SELFTEST ALL PASS（466 项断言）` | **0** |
| 2 | `python3 tests/selftest_p1_2_frontend.py` | `FRONT ALL PASS` ＋ `FRONT SELFTEST PASS` | **0** |
| 3 | `python3 tests/selftest_v26_presets.py` | `SELFTEST ALL PASS` | **0** |
| 4 | `git diff --check` | 无输出 | **0** |
| 5 | `node /tmp/p14rev/race.js`（独立探针：诊断缓存跨目录） | 7 项，第 ④⑤⑥ 项**实测串目录**（见 P2-1） | 0（按预期暴露问题） |
| 6 | `python3 /tmp/p14rev/diffeq.js`（前后端脱敏口径差分 30 例） | `redactPathField` 22 处差、`redactPathTail` 16 处差、`redactCopyField` **2 处差** | 0 |
| 7 | `python3 /tmp/p14rev/alt_probe2.py`（真 16 条分支探针） | 真分支下替代路径**已脱敏**；变异后**全套自测仍 rc=0** | 0 |
| 8 | 反向证伪（去重后**活性变异 27 条**：前端 12／后端 15） | 见第七节：**23 条咬住（rc=1）**、**4 条咬不住**（前端 3 条同根因 → P3；后端 1 条 `alternate_path_redacted` → P2-2）。另 6 条惰性变异/构造失败已剔除、不作证据 | — |

断言计数：`grep -c '^PASS'` → contract **466**、frontend **127**、presets **58**，与派单书给的数字**逐个一致**。

还原校验（全部证伪跑完后立即复算全量 sha256，与动手前记录**逐字一致**）：

```
app/index.html                  a57fe493dd7dfe09a261b4eafada0af76bfaf99998ccdeda5311f4c05c55b869
app/server.py                   36d78124802d21d07fdb7673b09832943cac5a0a572dbc3f078063c42b70b21f
tests/selftest_p1_2_contract.py 759481bd6596e297b5bb6bd6bcb572b8bfce40dc39c5ae9164eab8861ff13fde
tests/selftest_p1_2_frontend.py fdaf4093739729833f63fe6649517b6eb73509472e3a2b9837b661627d7b3001
```

`git status --porcelain` 仍只有那 4 个 `M`；`git diff --stat` 仍为 `559 insertions(+), 17 deletions(-)`。

---

## 二、DoD 5 条逐条判定（各给证据行号）

| # | DoD | 判定 | 关键证据（工作树行号） |
|---|---|---|---|
| 1 | 一键复制**只含允许字段**（脱敏 source label／目录尾段／错误码／类别／置信度／缺失证据／建议） | **真闭环** | 白名单唯一入口 `FAIL_DIGEST_FIELDS:1249`（恰为 FR-3 那 7 类，逐字对得上）→ 唯一构造函数 `digestEntry:1281-1284`（`FAIL_DIGEST_FIELDS.forEach` 取键，**只可能带这 7 个键**）→ 唯一渲染 `failDigestText:1344-1355`（正文只用 `f.label/tail/code/category/confidence/missing/next`）。唯一 HTTP 出口 `copyAllFailedReasons:1406-1417` → `copyText:1070`。**穷举旁路＝0**：全文件 `copyText(` 调用点 4 处（`:674`／`:768`／`:788` 是既有「复制输出路径／复制笔记路径」，`:1414` 是本次摘要），`grep JSON.stringify` 19 处**无一处**出现在 P1-4 新增块内；`failDigestText` 之外没有第二个拼装摘要串的函数（新增块 `1237-1428` 逐行读完）。 |
| 2 | **绝不包含**真实绝对路径／转写正文／笔记正文／密钥／请求体 | **真闭环（生产行为实测正确）**，但测试覆盖有洞 → P2-2 | 后端：路径字段全部过 `_diag_redact_path`（`server.py:1633/1636`，`1428-1433`）＋新增 `source_dir_tail` 走既有 `_dir_tail`（`:1632`→`:1044`）；`reason`／`next_action` 是硬编码人话常量（`_diag_action:1552-1577` 逐分支读完，**从不回 `row.reason`／异常原文**）。前端三层兜底 `redactPathField:1253`／`redactPathTail:1260`／`redactCopyField:1267` 全部落位。**正文/密钥/请求体结构上进不来**：摘要只读诊断项 7 键＋降级路只读 `failPartsForRun().next`（`：474-482`，`verdict` 的 `→` 后半句），**从不读** `detailsByRun[].verdict` 前半句、笔记正文、`/api/*` 请求体。真机形态实测：我在真 16 条那条分支下打印诊断全包，`/Users/`、`/var/folders/`、真实替代路径**均 0 命中**（探针 7）。 |
| 3 | 页面可看逐条本地证据 | **真闭环（两入口）** | ① 详情内联块 `index.html:736`（`.evbox`＋`#diagEvidence`，CSS `:89-91`）＋ `renderDiagEvidence:1394-1403`，接线 `:757`；② 全量面板 `showFailEvidence:1421-1427`＋表头按钮 `:609`（绑定 `:613`），正文 `evidenceLinesFor:1359-1383`／`failEvidenceText:1385-1389`。**降级时如实说明**（`:1381`：「诊断不可用（未配置绝对数据目录／库缺失或读不出）……不编造」）。 |
| 4 | 不弹成功 toast 洪水 | **真闭环** | 只传短句 `shortOk:"已复制 "+list.length+" 条脱敏摘要"`（`:1414`，实测 ≤40 字、无换行）；`copyText:1070-1096` 的 `done()` 只 `say(shortOk)+toast(shortOk)`，长文仅落 `lastLongText`＋点亮 `btnViewLong`（`:1077-1080`，**不自动开面板**）；`say()` 120 字截断仍在（`:1038` `.slice(0,120)`）。反向证伪②（`shortOk` 换成整篇正文）→ **rc=1，4 条断言咬住**。 |
| 5 | 不提供完整绝对路径导出、不新增导出按钮 | **真闭环** | 契约 `11g` 扫 `导出全路径/导出完整路径/导出绝对路径/复制完整路径/复制全路径`（`selftest_p1_2_contract.py:1851-1852,1933`）**0 命中**；我另**穷举 diff 内全部新增按钮**：只新增「查看本地证据（逐条）」`index.html:609` 一个，无导出/复制全路径类入口；旧入口文案同步改为「复制脱敏摘要」（`:608`）。 |

---

## 三、A~I 逐项裁定

### A｜脱敏是「真同口径」还是「第二套」→ **部分成立：三对里两对为「近似」，一对有实质口径差（但方向安全）；无一处在「前端比后端更宽松以致漏出路径」的活跃通道上**

我做了**逐例差分**（30 例语料：绝对／相对／`/` 根／`///`／Windows 风格／UNC／多级父目录／超长／`..` 归一化／尾斜杠／中文含空格／自由文本嵌路径／枚举值），不是抽查：

| 对 | 差异处数 | 差异与方向 | 裁定 |
|---|---|---|---|
| `redactPathField:1253` ↔ `_diag_redact_path:1428` | 22/30 | ①**非 `/` 开头字符串**：前端**原样返回**，后端回 `…/`＋末 3 段（如 `打不开 /Users/zzy/My Data/vault/x.md` → 前端原样、后端 `…/My Data/vault/x.md`）；②前端**不做 `normpath`**（builder 自陈 #3 属实），`/Users/zzy/a/..` → 前端 `…/zzy/a/..`、后端 `…/Users/zzy` | **方向①是「前端更宽松」**，但**不在活跃通道上**：该 helper 只被喂后端已产出的值（`source_label`=basename／枚举／常量），唯一例外是 `raw_error_code`——而 `processing_runs` **DDL 里根本没有这一列**（`src/stage2/store.py:151`，测试 docstring `selftest_p1_2_contract.py:87` 亦已言明），恒为 `UNKNOWN`，故**当前不可达**。方向②两侧披露量相当（都只留 3 段）。→ **P3-3**（补 `normpath`／把 `code`/`missing` 改走 `redactCopyField`，仅作纵深） |
| `redactPathTail:1260` ↔ `_dir_tail:1044` | 16/30 | 同一类：非 `/` 开头原样透传；`""`／`"/"`／`"///"`／尾斜杠**三例与后端一致**（逐例核过） | **可接受**：调用点只喂后端 `_dir_tail` 产物（`…/xxx` 形态）或列表侧同源字段，均以 `…/` 开头。→ **P3-3**（同条） |
| `redactCopyField:1267` ↔ `_strip_paths:354`（＋`_err_text` 空白归一） | **2/30** | **唯一实质差**：前端 `REDACT_STOP_CHARS:1250` **缺 ASCII `(` `)`**（后端 `_PATH_STOP_CHARS:349-351` 有）。实测：`路径(/Users/a/b/c)打不开` → 前端 `路径(…`（**多抹到行尾**）、后端 `路径(…)打不开` | **方向是「前端更严」＝不会漏路径**（缺收尾字符只会延长吞掉区段）。代价是降级路「建议」字段**多丢人话尾句**（`文件找不到了：x.mp4→检查 … (可能是移动了) 是否还在` → 只留 `…检查 …`）。→ **P3-4**（补 `()` 两个字符即可完全同口径） |

**结论**：不构成「第二套口径各写一遍」的失控（三对均指向同一设计意图，且 builder 在注释 `:1239-1246` 逐对标注了溯源），但**「逐字等价」不成立**，其中一处（ASCII 括号）是实打实的口径差。**没有任何一处构成「前端兜底比后端更宽松从而导致真路径漏出」的活跃通道**——唯一的宽松方向（非 `/` 开头透传）落在 `raw_error_code` 上，而该字段在当前 schema 下恒为 `UNKNOWN`。

### B｜「只含允许字段」是否真被强制 → **是。白名单是唯一出口，无旁路**

对新增块 `index.html:1237-1428` 做了**穷举**（不是抽查）：

- 唯一构造：`digestEntry:1281-1284`，`FAIL_DIGEST_FIELDS.forEach` 决定键集 → 返回值**不可能**含第 8 个键（反向证伪⑥「白名单加第 8 键 `reason`」→ **rc=1**，`10d 白名单恰好是 FR-3 那 7 类字段` 咬住）。
- 唯一渲染：`failDigestText:1344-1355`——逐行读完，正文只出现 `f.*` 七个变量＋字面量标题＋`rows.length`。
- 唯一出口：`copyAllFailedReasons:1406-1417` → `copyText(body, …)`。全文件 `copyText(` 共 4 个调用点，另 3 处是**既有**的「复制输出路径」按钮（`:674`／`:768`／`:788`，diff 未触碰）。
- **没有**「把整条 item 塞进面板文案再被复制」的旁路：面板正文 `failEvidenceText` 的每一项都经 `evidenceLinesFor` 逐字段取值（路径类过 `redactPathField`／自由文本过 `redactCopyField`），且面板只能由用户**主动**点「查看本地证据（逐条）」打开（`:1421`），复制行为**不自动开面板**（`:1077-1080`，10a 断言 `!REC.cls["longPanel"]` 咬住）。
- diff 内无 `JSON.stringify(item)` 类拼装（19 处 `JSON.stringify` 全在既有请求体行，逐处核过）。

### C｜按钮文案与产物是否一致（同类历史缺陷）→ **一致，不构成同类缺陷；仅剩一处「结构性保证」与「文案断言」的精度差 → P3-5**

| 位置 | 文案（逐字） | 产物（逐字） | 判定 |
|---|---|---|---|
| 按钮 label `:608` | `复制脱敏摘要` | 首行 `失败诊断摘要（脱敏；共 N 条）` | **对得上** |
| 按钮 title `:608` | 「只含脱敏来源/目录尾段/错误码/类别/置信度/缺失证据/建议；不含真实绝对路径、正文、密钥、请求体」 | 白名单 7 键＝来源 label／目录尾段／错误码／类别／置信度／缺失证据／建议，**逐项同名同序** | **对得上** |
| 面板按钮 `:609` | 「在页面上逐条展开本地证据（脱敏路径、身份匹配、产物、冲突、provenance）」 | 面板正文含 原登记路径/替代路径/身份匹配/持久态/展示态/provenance/恢复资格/whisper/产物/证据来源/证据冲突（**超集**） | **对得上（承诺是子集）** |
| 长文面板标题 `:1415` | `失败诊断摘要（脱敏，共 N 条）` | 同 `body` | **对得上** |
| 复制成功短句 `:1414` | `已复制 N 条脱敏摘要` | 复制出去的就是该摘要 | **对得上** |
| 旧版「说明：…重新转写全部失败…」footer | **已整段删除**（builder #4） | — | **删除是正确的**：它属于白名单外的第 8 类内容，留着就违反 DoD1；每条已有「建议」字段承担下一步指引 |

**唯一精度差（P3-5）**：title 承诺「不含密钥、请求体」，实现上密钥是**结构性保证**（摘要从不读请求体/正文）而非**文本扫描保证**——若哪天有值把 token 形态的字串塞进 `next`（降级路唯一自由文本口），不会被拦；builder #2 已如实自陈「无 token 形态探测（刻意不造正则以免误伤中文）」。**判 P3，不改文案也接受**（当前无任何真实 token 能进入该字段），但建议在 title 里把「密钥、请求体」的口径写实（如「不读取请求体与正文」）。

### D｜脱敏的证据强度（断言是否有牙）→ **整体有牙，但存在一处「结构性无牙」：替代路径脱敏零断言，且真 16 条那条分支在自测里不可达 → P2-2**

- **合成数据里真放了真实形态绝对路径**：
  - 前端 `selftest_p1_2_frontend.py:881` `REAL_USER_PATH = "/Users/zzymima0000/需转录视频/第七周/样例视频.mp4"`，在 `10b`（`:995`）作为 `source_label`／`next_action`／`source_dir_tail` 三路喂进去，**输入侧确实含 `/Users/` 与整条真路径**，非空跑。断言 `t2.indexOf("/Users/") < 0 && t2.indexOf(REAL_USER_PATH) < 0` **非空断言**（反向证伪①恒等 → rc=1）。
  - 契约侧夹具走 tmp（`/var/folders/…/p12_A_*`），`SENSITIVE:601` 含 `/var/folders/` 且 `scan_leak` 额外传 `[root, TMP_ROOT]`，**牙在 tmp 形态上**（反向证伪①②④ → rc=1）。
- **「弱子串扫描」不够，但有整条比对兜底**：`hasAnyAbsPath:926` 只扫 6 个前缀（`/Users/ /Volumes/ /private/ /var/ /tmp/ /home/`）。我做了**方向性证伪⑤**：把 `redactPathField` 从「末 3 段」放宽成「末 4 段」（＝泄漏一层父目录、账号名 `zzymima0000` 出现在摘要里，但**不含** `/Users/`）——结果：**弱子串断言 PASS**，而 `10b 打码后仍留可用信息`＋`10b 来源 label 按 _diag_redact_path 同口径` 两条**整条比对**断言 FAIL → **rc=1**。即：**弱断言无牙，但整条比对把这一档接住了**（契约侧同理，`11e` 钉死 `…/需转录视频/第七周/样例.mp4` 逐字）。
- **咬不住的一处（P2-2，本项最重要的发现）**：`alternate_path_redacted`（**替代路径＝用户把文件搬到哪儿，本功能里最敏感的一字段**）**没有任何断言**。根因是夹具结构性限制：共享夹具 `add_run:86-99` 把 `content_identity` 硬编码成 `"x"*40`（`:97`），而 `_diag_identity:1447-1463` 要求 `sha256(候选)==content_identity` 才回 `MATCH`，`_diagnosis_item:1587-1590` 又**只在 MATCH 时**才把 `alternate` 填上（MISMATCH 只有 identity 不留路径）。后果：**契约夹具永远到不了 `action_category=SOURCE_LOCATION_REVIEW`／`identity_match=MATCH`／`confidence=HIGH`／`alternate_path_redacted≠UNKNOWN`**——也就是**真 16 条那条唯一分支**。我用自建夹具（把 `content_identity` 改成真 sha256、源文件搬到 `_alt/葫芦军师/`）**证实**：真分支下 `alternate_path_redacted='…/_alt/葫芦军师/run-missing.mp4'`（**生产行为正确**）；而把该行改成不回脱敏（`alternate` 直接返回）后，**全套自测仍 rc=0／466 PASS**，同时在真分支夹具下**明文泄漏成真**。→ **生产代码是对的，缺的是断言与夹具**。（前端同一字段同理：fixture `p14Item:882-890` 喂的是**已打码**的 `…/…` 值，我把 `index.html:1367` 的 `redactPathField` 拿掉 → frontend **rc=0**，同样咬不住。）
- 其余字段**逐条有牙**（我做了活性变异，全部 rc=1）：`recorded_path_redacted` 明文→5 条断言咬住；`source_dir_tail` 塞真实目录→4 条；`source_dir_tail` 另造「末 2 段」第二套口径→`11d 与列表同源`**精确咬住**；`missing_evidence` 塞真路径→`6g`＋`6 脱敏`；`confidence` 塞真路径→`11f 枚举`；`next_action` 塞真路径→`6g`＋`6 脱敏`；`action_category` 塞真路径→4 条；`reason` 塞真路径→`6g`＋`6 脱敏`；`_strip_paths` 放宽（遇空格即停）→3 条。

### E｜降级路径 → **真闭环**（脱敏同口径、缺失写「未提供」不写空、不误连别目录），两处小瑕疵记 P3

- **触发与走向**：`digestDataRoot:1288-1292` 取「框优先→`effectiveDataRoot`」，**无值或非绝对路径一律返回 `""`** → `loadDiag:1297-1300` 直接 `Promise.resolve(null)`（**不发请求**，不误连别目录；反向证伪⑧「`digestDataRoot` 恒空」→ rc=1，11 条断言咬住）→ `diagItemFor:1321` 回 `null` → `failDigestFields:1326-1342` 走降级分支。
- **缺失字段不写空**：`NO_EVIDENCE="未提供（诊断不可用）":1251` 用在 `code/category/confidence/missing` 四格（`:1340`），实测输出 `错误码：未提供（诊断不可用）`（10d 断言咬住；反向证伪⑦改成空串 → **rc=1**）。**不存在「诊断不可用但字段留空导致读者误判」**。
- **降级路同样脱敏**：唯一自由文本 `建议` 先过 `redactCopyField` 再按 say() 同一 120 字上限截断（`:1337-1341`）；10d 用例把真路径塞进 `verdict` 后半句，实测输出 `检查 …，补回后点重试`（**路径已抹、人话保留**），且 `10d 原因/正文/token 不进摘要` 断言咬住（`正文MARKER`／`TOKEN-ABC` 0 命中）。
- **接口 404／网络错**：`mark(null)` 落 `byRun={}`（`:1310-1317`）＝「已查过但不可用」，**不反复闪「加载中」、不每 5 秒重扫盘**；`.catch` 也走 `mark(null)`，不抛异常到页面。
- **两处小瑕疵**：① 降级提示把原因写成「未配置绝对数据目录／库缺失或读不出」（`:1381`），但**网络错／404／5xx** 也走同一句，**枚举不完备**（P3-6）；② `digestDataRoot` 非法时不查诊断 → 用户看到的是「未提供（诊断不可用）」而**不是空手**，这点正确；但 `diagCache.byRun` 在该情形**恒为 null**，每次重画都重写一次占位（`:1397`），虽因微任务在手绘前完成而无可见闪烁，语义上「已查过」的哨兵未置位（P3-7）。

### F｜数据安全 → **合规**

- 新增用例**只有一个调 handler 的用例组** `part11_p14_digest:1855`，**首行即** `root = build_root_a(server)` → `assert_tmp(root, "part11_p14_digest")`（`:1866-1867`，在**任何 handler 调用之前**）；夹具构造 `make_data_root:113-118` 自身也首行 `assert_tmp`。**逐条核过**：该用例组内所有 handler 调用（`_handle_failure_diagnosis:1866`／`_handle_status:1883`）都在断言之后。
- **全 tmp ＋ 合成数据**：`tempfile.mkdtemp(prefix="p12_%s_")`，`finally: shutil.rmtree`；DDL 复用 `src/stage2` 真 DDL，视频是 `b"fake-media-…"` 假字节，无任何真实视频。
- **未碰用户真实目录／Obsidian 库**：实测 `build_root_a` 的 4 个 spec 均 `with_src` 默认 True → `recorded_path_redacted` 对应文件**存在** → `_diag_alternate_paths`（唯一会遍历 `~/Downloads` 的函数）**在本用例组内零调用**（代码判据 `server.py:1584` 只在 `not recorded_exists` 时调用）。前端测试是 node 桩（`DRIVER` 内假 `fetch`/DOM），`REAL_USER_PATH` 只是**字符串常量**，磁盘上无任何读写。→ **本批自测对用户真实目录是零读零写**（我自己的探针才触发了只读遍历，用完即删）。
- 新增行密钥扫描（`git diff` 新增行 × 8 种密钥形态）→ **0 命中**。

### G｜前序成果无回退 → **无回退**

| 前序成果 | 证据 | 判定 |
|---|---|---|
| 主题默认浅色 | `index.html:2` = `<html lang="zh-CN" data-theme="light">`（未动） | **保留** |
| `say()` 120 字截断 | `:1038` `.slice(0,120)` 在位（本批未改） | **保留** |
| 长文面板四退出 | `openLongPanel:1039-1044`／`closeLongPanel:1045-1048` 未改；新增面板**复用**之（10c 断言 `longPanel`＋`btnLongClose` 在位），未新造浮层 | **保留** |
| D-12 口径未被放宽 | `git diff app/server.py` = **仅 3 行新增**，`_strip_paths:354-374`／`_err_text:377-393` 字节未变；反向证伪「放宽 `_strip_paths`」→ rc=1（`9b` 两条＋`11e` 各咬住） | **保留** |
| No-Clobber | 本批**未动任何发布/写盘逻辑**（server 仅新增一个只读派生字段） | **保留** |
| 词库三铁律 | `tests/selftest_v26_presets.py` **58/58 rc=0** | **保留** |
| P1-3 五桶同源／锁定提示／无目标不画 100% | `STATE_BUCKET:1770`／`_state_bucket:1796` 未动；`renderProgress:832`／`vocabApplyLockText:1654` 未动（diff hunk 落在 `88/560/604/607/728/748/1228/1241/1843/2028`＋ server `1629`，**无一处触及 P1-3 函数体**） | **保留** |

### H｜自测「有牙」→ **有牙（活性变异 23/27），但 builder 报的那 4 条我无法复核其产物；已用 27 条自建活性证伪替代取证**

- builder 报的 F1a／F1b／F2／F3 四条反向证伪**未随工作树落盘**（无报告、无脚本、无 sha256 台账可查），**无法复核**；我按要求**自建并独立复跑**（前端 12／后端 15 条活性变异），**23 条咬住 rc=1**、**4 条咬不住**（前端 3 条同根因＝夹具喂已打码值 → P3；后端 1 条＝`alternate_path_redacted` → P2-2）。另 6 条变异因分支在夹具下不可达（惰性）或构造失败，**已剔除、不作证据**。全部 33 次尝试跑完均立即复算 sha256 与基线**逐字一致**（见第一节还原校验块）。
- 基线哈希我已**全量算存**（派单书只给了前 16 位，已补齐 64 位并写进本报告）。
- **两次「惰性变异」自纠（记一笔，避免后人误读）**：我最初两条变异（`missing_evidence` 走「未对齐」分支、`next_action` 走 `UNKNOWN` 兜底分支）在夹具下**根本不会命中**，rc=0 是**假绿**；我复算后改成命中分支重跑，两条均 rc=1。**这正是「断言有牙」必须做活性校验的最好例子**，也提示 P2-2 那两条咬不住**同样要排除「惰性」**——我用真分支夹具单独确认过变异版**确实泄漏明文**（不是惰性），故 P2-2 成立。

### I｜范围外改动 → **逐条列出，全部接受，其中 1 条记 P3**

| # | 范围外改动 | 位置 | 裁定 |
|---|---|---|---|
| I-1 | 新增按钮「查看本地证据（逐条）」 | `index.html:609,613` | **接受**：DoD3 明文要求「页面可看逐条本地证据」，且 Plan FR-3 首句即「页面可看逐条本地证据」，属**需求内**（DoD3 与 FR-3 都点名，非越界） |
| I-2 | 详情区新增内联证据块 `#diagEvidence` | `:736,757`＋CSS `:89-91` | **接受**：同上，比 DoD3 要求的「可看」多给一个就近入口；只在「失败／入库受阻」两个详情分支挂（builder #7 自陈属实，`:717` 分支内） |
| I-3 | 手动刷新时 `dropDiagCache()` | `:2028` | **接受（但有附带缺陷 → 见 P2-1）**：语义是「手动刷新＝要看最新证据」，合理；**但该重置与迟到响应交互有 bug**（P2-1） |
| I-4 | 旧复制函数整体替换、`V2O 失败原因清单` 字样随之消失 | 删除行 `-lines=["V2O 失败原因清单（共 …"]` 等 | **接受**：白名单化**必然**要求删掉旧标题/旧 footer（第 8 类内容）。但 **P1-7 的只读盘点会因此过期一处**（HANDOFF 记「`index.html` 可见 4 处待改」）→ **P3-8**，请 TM/neat 收尾时把 P1-7 清单与现状对齐（当前 `grep 'V2O'` 只剩 `:6` title、`:38` tape::before、`:179` h1、`:1060/:1064` Notification 五处） |
| I-5 | 注释改写（`:563-564` 表头用途说明） | `:563-564` | **接受**：与行为同步的注释更新 |
| I-6 | 未动 P1-7 范围、未动主题/三铁律/D-12 | — | **接受**（builder #10 自陈属实，G 节已逐条验证） |

---

## 四、P0 / P1 Findings

- **无 P0、无 P1 阻断。**

## 五、P2 / P3 Backlog Findings

### P2-1（非阻断，**建议同批修**）｜诊断缓存重置与迟到响应竞态 → 会把**别的数据目录**的诊断当成当前目录的

- 位置：`app/index.html:1295`（`dropDiagCache`）＋`:1297-1319`（`loadDiag` 的 `mark` 闭包）＋`:2028`（手动刷新调用 `dropDiagCache`）。
- 机制：`mark()` 把响应写进**模块级 `diagCache`（写时取新值）**，而 `diagCache.root` 已在重置后换成新目录。于是**旧目录的响应会落到新目录的缓存里**，且 `loadDiag():1303`（`if(diagCache.byRun&&diagCache.root===root)return …`）**认为它有效**，直接回给调用方，不再发请求。
- 独立复现（`/tmp/p14rev/race.js`，抽真源码＋桩，**未改业务代码**）：① 目录 A 诊断请求在飞 → ② 用户把数据目录改成 B 并点「刷新」（触发 `:2028`）→ ③ 放行 A 的迟到响应 → 实测：`diagCache.root='/rootB'` 而 `diagItemFor('run-1').source_label='A-ITEM'`，摘要正文里出现 **A 目录的数据**，且 `loadDiag()` 之后再取**直接回 A、不发新请求**；直到 B 自己的响应到达才自愈。
- 影响面：**只读、无写盘、无跨目录执行**；但摘要/页面证据会呈现**非当前目录**的诊断（若两个目录存在同名 `run_id`，用户会把 A 目录的证据当 B 目录的复制出去协作排错——正好打在 FR-3「携带 16 条诊断证据协作排错」的用途上）。窗口宽度＝该次诊断请求耗时（builder #1 自陈最坏 N×2s，真 16 条场景可长达数十秒），**不是微秒级竞态**。
- 与既有约定冲突：`:1288-1292` 注释自陈的设计意图是「宁可不给诊断，也不去诊断别的目录」，P1-2 整条链的主题亦是「防串任务/串目录」。
- 返工要求（小、自包含，只改 `index.html`）：`mark()` 落地前先核当前 `diagCache.root` 是否仍等于本次请求发起的 root（不等则丢弃，不写），或在 `loadDiag` 里把 root 与 promise 一起捕获、`.then` 内比对后再赋值。并补一条前端断言：**换目录＋迟到响应 → 不得回旧目录数据**（现有 S10 无此反例）。

### P2-2（非阻断，测试债）｜替代路径脱敏**零断言**，且真 16 条那条分支在自测里**不可达**

- 位置：夹具 `tests/selftest_p1_2_contract.py:86-99`（`content_identity` 硬编码 `"x"*40`，`:97`）＋实现 `app/server.py:1447-1463`（`_diag_identity`）／`:1587-1590`（仅 MATCH 才填 `alternate`）／`:1636`（`alternate_path_redacted`）；前端同字段 `app/index.html:1367`＋夹具 `tests/selftest_p1_2_frontend.py:882-890`（喂的是**已打码**值）。
- 证据：把 `"alternate_path_redacted": _diag_redact_path(alternate) if alternate else "UNKNOWN"` 改成 `alternate`（不回脱敏）→ **全套自测 rc=0／466 PASS**；我自建真分支夹具确认变异版**确实输出明文绝对路径**（非惰性）。前端同位置去掉 `redactPathField` → frontend **rc=0**。
- 连带：`SOURCE_LOCATION_REVIEW`／`identity_match=MATCH`／`confidence=HIGH` 三档在契约夹具里**均不可达**，故 `11f 置信度取值属 {HIGH, UNVERIFIED}` 实际只验过 `UNVERIFIED`，`11c` 的 `/Users/` needle 在契约侧**从未被 `/Users/` 形态的值触发**（牙只在 `/var/folders/` 上）。
- 返工要求（补断言＋补夹具，不动业务逻辑）：① 让 `add_run` 可传 `content_identity`（或允许 spec 指定），加一条「源文件不在原位＋替代位置身份匹配」的夹具；② 断言该分支下 `action_category=SOURCE_LOCATION_REVIEW`、`identity_match=MATCH`、`confidence=HIGH`、`alternate_path_redacted` 以 `…/` 开头且**不等于**真实替代路径；③ 前端 `p14Item` 增加一档喂**未打码** `recorded_path_redacted`／`alternate_path_redacted`，断言页面证据仍零真路径。

### P3（不拦收口，记 backlog，写明归属）

| # | 内容 | 位置 | 归属 |
|---|---|---|---|
| P3-1 | 诊断耗时未实测：预算 `_DIAG_SCAN_TIME_BUDGET_S=2.0`／`_DIAG_SCAN_MAX_DIRS=2000` 是**逐行**预算（`server.py:1466-1467`，用在 `:1510-1524`，且只在 `recorded_exists=False` 时才扫，`:1584`），真 16 条最坏 ≈16×2s；前端**无超时/无取消**、无跨行记忆化；且 `say()` 3 秒自动清（`:1038`）会让长等待「看起来像卡死」——与用户追加反馈三同族观感。**要求 QA 在真 16 条（或等量合成缺源行）上实测一次墙钟**，并考虑服务端加总预算或保活提示 | `index.html:1406-1417`（复制待诊断完才落）、`:1035-1038`；`server.py:1466-1524` | QA 取证＋TM 判同批/backlog（builder #1 已如实自陈） |
| P3-2 | `raw_error_code` 恒为 `UNKNOWN`（`processing_runs` 无该列，`src/stage2/store.py:151`）→ 摘要「错误码」一栏**结构性无信息**。如实未编造（符合 FR-1），但摘要可用性受限；若日后新增该列，前端 `redactPathField` 对**句中嵌路径**不生效（见 A 表方向①） | `server.py:1649`；`index.html:1332` | TM（是否补列属 Change B／Plan 范畴，**本批不得自行加列**） |
| P3-3 | `redactPathField`／`redactPathTail` **未做 `normpath`**、且非 `/` 开头原样透传（与后端 `_diag_redact_path`／`_dir_tail` 不同口径）。当前无活跃漏出通道 | `index.html:1253-1265`；`server.py:1428-1433,1044-1055` | 本链 backlog（builder #3 已自陈） |
| P3-4 | `REDACT_STOP_CHARS:1250` 缺 ASCII `(` `)`（后端 `_PATH_STOP_CHARS:350-351` 有）→ 降级「建议」多丢人话尾句 | `index.html:1250` | 本链 backlog（补两个字符即完全同口径） |
| P3-5 | 按钮 title 承诺「不含密钥、请求体」，实现是结构性保证而非文本扫描保证（降级路 `next` 无 token 探测） | `index.html:608`；`server.py` 无 token 形态判定 | 本链 backlog（builder #2 已自陈，刻意不造正则以免误伤中文） |
| P3-6 | 降级提示把原因写成「未配置绝对数据目录／库缺失或读不出」，**枚举不完备**（404／网络错／5xx 同句） | `index.html:1381` | 本链 backlog |
| P3-7 | `digestDataRoot` 非法/无值时 `diagCache.byRun` 恒 null →「已查过」哨兵未置位，每次重画重写占位（无可见闪烁，仅语义不整） | `index.html:1288-1292,1397` | 本链 backlog |
| P3-8 | P1-7 只读盘点过期：旧摘要标题 `V2O 失败原因清单` 已随白名单化删除，HANDOFF 记的「index.html 可见 4 处待改」需与现状（title/tape::before/h1/两处 Notification＝5 处）对齐 | `index.html:6,38,179,1060,1064` | TM／neat 收尾对齐 |

---

## 六、builder 10 条自陈逐条裁定

| # | 自陈 | 裁定 | 理由／补测要求 |
|---|---|---|---|
| 1 | 诊断耗时未实测（逐行 2s 预算／无前端超时取消／无跨行记忆化） | **接受（如实）＋补测要求** | 代码逐行核过：预算确为逐行（`server.py:1466-1467` 用在 `:1523`），只在缺源时触发（`:1584`）。**但影响面被低估**：真 16 条全部缺源 → 每次复制/开面板都可能 ≈16×2s，且 P1-4 是**第一个 UI 消费者**（此前无调用点）。→ **P3-1**，要求 QA 实测墙钟 |
| 2 | 降级「建议」是唯一自由文本入口，已过 `_strip_paths`＋120 字截断，无 token 形态探测 | **接受** | 实测确认（`index.html:1337-1341`；10d 用例把真路径塞进该字段 → 输出 `检查 …，补回后点重试`）。**刻意不造正则**的判断我认同（中文语料误伤风险 > 收益），但 title 文案口径要跟着变 → **P3-5** |
| 3 | `redactPathField` 未做 `..` 归一化 | **接受（确认属实）** | 30 例差分实测：`/Users/zzy/a/..` → 前端 `…/zzy/a/..`、后端 `…/Users/zzy`；披露量相当，**方向不构成漏出**（`..` 只会减少有效段）。→ **P3-3** |
| 4 | 复制首行是文档标题（非数据字段），旧版「说明：…」footer 整段删掉 | **接受，且是必须的** | footer 属白名单外第 8 类内容，保留即违反 DoD1；每条「建议」字段已承担指引。**首行标题不计入数据字段**的判断我认同（前端断言 `onlyWhitelistedLines:912` 即按「第 0 行是标题」口径写） |
| 5 | 旧版原因/下一步原文不再进摘要（页面详情仍可见） | **接受** | 与 FR-3 逐字一致（只允许那 7 类）；页面侧仍在 `:730-734`（详情 failbox「原因／下一步」），**未丢用户可见信息**。另注：摘要含 `next` 不含 `reason`，比旧版**严格更窄**（旧版两者都进） |
| 6 | `raw_error_code` 阶段恒为 `UNKNOWN`（表无该列，如实写未编造） | **接受（验证属实）** | `src/stage2/store.py:151` 的 DDL 确无该列；测试 docstring `selftest_p1_2_contract.py:87` 亦已言明。如实写 `UNKNOWN` 正合 FR-1「未获得的值必须写 UNKNOWN」。→ 连带 **P3-2** |
| 7 | 证据块只挂「失败/入库受阻」两个详情分支 | **接受** | 代码属实（`index.html:717` 分支内 `:736`）。覆盖缺口由**全量面板**（`:609`／`:1421`）补齐，DoD3 已满足；这一点也解释了为什么内联块是「就近入口」而非唯一入口 |
| 8 | 真机 UI 未目检、窄屏未专项验 | **接受（如实，法上与红线一致）** | 8765 当前无监听，本窗口禁点真机主题开关。**要求交 QA 真机目检**：失败任务详情展开后内联证据块渲染、点「查看本地证据（逐条）」面板四退出（关闭按钮/Esc/遮罩/焦点返回）、窄屏 `min(70vh,560px)` 内滚（`:174` CSS）、以及**真实 16 条量级的等待观感**（对应 P3-1） |
| 9 | 顺带减少一处用户可见 `V2O` 文案但 P1-7 范围未动 | **接受（属必然连带）** | 该字样在旧复制函数体内，白名单化必然删除；P1-7 范围（title/h1/流程标识/README）**确未动**（G 节已验证）。但 P1-7 盘点会因此过期 → **P3-8** |
| 10 | 未动主题/三铁律/D-12 | **接受（独立复核属实）** | G 节逐条验证：`data-theme="light"` 在位、presets 58/58、`server.py` 仅 3 行新增且 `_strip_paths:354-374` 字节未变 |

---

## 七、反向证伪汇总（活性变异 27 条：前端 12／后端 15；全部为「改坏→跑→取证→还原」）

**前端（`app/index.html`，12 条活性）**

| 变异 | rc | 咬住它的断言 |
|---|---|---|
| ① `redactPathField` 恒等 | **1** | `10b 真实绝对路径不进摘要`／`10b 打码后仍留可用信息`／`10b 来源 label 同口径` |
| ② `shortOk` 换成整篇正文 | **1** | `10a 成功提示是一句短话`／`10a toast 同样是短句`／`10a 长文不得进状态行`／`10d 降级路提示仍是短句` |
| ③ `redactCopyField` 恒等 | **1** | `10b ×3`／`10d 降级建议已脱敏`／`10d 页面证据如实说明降级`（共 5） |
| ④ `redactPathTail` 恒等 | **1** | `10b ×3`（含 `10b 目录尾段按 _dir_tail 同口径`） |
| ⑤ `redactPathField` 末 4 段（弱泄漏，无 `/Users/`） | **1** | **弱子串断言 PASS，整条比对断言 FAIL** ← D 的关键取证 |
| ⑥ 白名单加第 8 键 | **1** | `10d 白名单恰好是 FR-3 那 7 类字段` |
| ⑦ `NO_EVIDENCE` 改空串 | **1** | `10d 缺失字段写「未提供」`／`10e 降级摘要不含路径` |
| ⑧ `digestDataRoot` 恒空 | **1** | 11 条（含 `10a 只调一次诊断`／`10b ×3`／`10c ×4`） |
| ⑨ 页面证据 `alternate` 行去掉兜底脱敏 | **0** | ← **咬不住（P2-2）** |
| ⑩ 页面证据 `recorded` 行去掉兜底脱敏 | **0** | ← 咬不住（P3，夹具喂已打码值） |
| ⑪ 页面证据 `evidence_sources` 去掉兜底 | **0** | ← 咬不住（P3，同上） |
| ⑫ 摘要 `label` 去掉 `redactPathField` 兜底 | **1** | `10b ×3`（摘要字段这一路**有牙**，与 ⑨⑩ 形成对照） |

**后端（`app/server.py`，15 条活性）**

| 变异 | rc | 咬住它的断言 |
|---|---|---|
| `_diag_redact_path` 恒等 | **1** | `6c`／`6g`／`9c ×2`／`6 脱敏（P1-4）` |
| `_dir_tail` 回真实目录 | **1** | `6g`／`6 脱敏`／`11d 打码形态`／`11e _dir_tail 只留末段` |
| `source_dir_tail` 另造第二套（末 2 段） | **1** | **`11d 与列表 source_dir_tail 逐条一致`（精确同源）** |
| `source_dir_tail` 直接塞真实目录 | **1** | `6g`／`6 脱敏`／`11d ×2` |
| `_strip_paths` 放宽（遇空格即停） | **1** | `9b ×2`／`11e 含空格路径整段抹掉` |
| `recorded_path_redacted` 明文 | **1** | `6g ×2`／`6 脱敏`／`11c ×2` |
| `source_label` 回完整登记路径 | **1** | `6g`／`6 脱敏`／`11c 无字段等于真实登记路径` |
| `missing_evidence` 塞真路径（活性变异） | **1** | `6g`／`6 脱敏` |
| `next_action`（RETRANSCRIBE 分支）塞真路径 | **1** | `6g`／`6 脱敏` |
| `action_category` 塞真路径 | **1** | `3b 诊断覆盖多类`／`6g`／`6 脱敏`／`11f 类别属枚举` |
| `confidence` 塞真路径 | **1** | `6g`／`6 脱敏`／`11f 置信度属 {HIGH,UNVERIFIED}` |
| `reason` 字段塞真路径 | **1** | `6g`／`6 脱敏` |
| 删掉 `source_dir_tail` 字段 | **1** | `11d`（KeyError → 非零退出，**契约字段缺失即挂**） |
| **`alternate_path_redacted` 明文** | **0** | ← **咬不住（P2-2，已排除惰性：真分支夹具下变异版确实输出明文）** |

> **另 6 条已剔除、不作证据（自纠留痕）**：`missing_evidence` 改「未对齐」分支、`next_action` 改 `UNKNOWN` 兜底分支（×2）、`action_category` 改 `_diag_action` 第二元（×2）、以及一条 Python 侧格式化把真值写进文件导致的 `NameError`——前几类**在现有夹具下根本不会命中**（rc=0 属**假绿**），最后一条是构造失败。**这正说明「反向证伪必须做活性校验」**：我最初据此误判过 2 条「咬不住」，复算分支可达性后纠正。P2-2 那条已用真分支夹具单独确认**变异确实泄漏明文**，故成立。

---

## 八、未覆盖项（如实列出，不可推断为通过）

1. **真机 UI 未目检**：8765 无监听；内联证据块真实渲染、面板四退出、窄屏内滚、以及「失败任务详情展开」链路的真实数据闭环均**未实点**（builder #8 同）。→ 交 qa。
2. **真实 16 条未跑**：真实 `data_root`／真实 DB／真实缺失源文件下的诊断耗时与摘要内容**未测**（P3-1 的核心未知量）。本报告所有"生产行为正确"的结论均来自 **合成夹具＋自建探针**。
3. **真 16 条分支的端到端**：我用自建夹具确认了后端该分支的字段脱敏正确，但**仓内自测到不了该分支**（P2-2）；该分支在前端的表现（`p14Item` 夹具是手写形态，非后端真实回包）**未做前后端联合验证**。
4. **并发/多标签**：`diagCache` 是模块级单例，多标签各自独立；本批未验多标签同时切目录（P2-1 的另一变体）。
5. **未测浏览器剪贴板失败分支**：`copyText:1085-1092` 的 `fallback()`（`execCommand`）与 `fail()` 路径只有既有 P1-3 覆盖，本批未新增断言（既有断言仍在，故不判回退）。
6. **CDN/渲染层**：未在真实浏览器引擎下验证 `hasAnyAbsPath` 之外的显示层转义（`ev` 走 `textContent`，无 XSS 面；未做浏览器实测）。
7. **builder 报的 F1a/F1b/F2/F3 四条反向证伪产物**：工作树内无脚本/无记录，**无法复核**；已用我方 27 条活性自建证伪替代（见 H／七）。

---

## 九、结论

**PASS（无 P0/P1）**。DoD 5 条 **5/5 真闭环**；A~I 中 **C／D 两项部分成立**已按 P2／P3 落账；builder **10 条自陈全部接受**（#1／#2／#8 附补测要求）。**"脱敏不是第二套"总体成立**（三对 helper 指向同一设计并逐对标注溯源），但"逐字等价"不成立（ASCII 括号缺失一处）；**"白名单是唯一出口"成立**（穷举无旁路）；**"文案与产物一致"成立**（同类历史缺陷未复现）。

两项 P2 **不拦收口**，建议 **P2-1 同批修**（改法自包含、只动 `index.html` 一个函数），**P2-2 与 P3 记 backlog**（前者可在本链顺手补夹具＋断言）。8 条 P3 归属已逐条写明。**未改业务代码、未 commit、未 push**；本次只新增本报告一个文件。

> 请在复核后再放行 QA；QA 请重点接：**P3-1 真 16 条量级耗时实测**、**P2-1 换目录＋迟到响应反例**、以及 builder #8 要求的**真机目检（内联证据块／面板四退出／窄屏内滚）**。

---
---

# 复核二（2026-09-15）｜只复核 P2-1／P2-2 两条的返工

- Task: 同上 `DEVELOP-P1-4`。本轮**只**复核 P2-1（诊断缓存跨目录串味）与 P2-2（替代路径脱敏测试无牙）的返工；上一节（复核一）正文一字未动，本节为追加。
- Commit: **仍未提交**。`git rev-parse HEAD` = `fa6ba1b77c85e7dd401ae2e6de4897d31dcadf55`（＝派单书基线，无偏差）。`git diff --stat` 实测＝`app/index.html 226`、`app/server.py 3`、`tests/selftest_p1_2_contract.py 204`、`tests/selftest_p1_2_frontend.py 359`（`4 files changed, 767 insertions(+), 25 deletions(-)`）——与派单书**逐字一致**。`git diff --check` → **rc=0**。
- Reviewer: code-reviewer（`opencode/muse-spark-1.3-contributor-free`，本窗口 subagent 独立复核；未改业务代码、未 commit/push）
- Result: **PASS（无 P0／无 P1，放行 QA）**。P2-1 **真闭环**、P2-2 **真闭环**；本次返工**无越界**、前序成果**零回退**；新记 **5×P3**（其中 2× 为「测试覆盖缺口」、3× 为记账/提示），复核一 8 条 P3 **全部仍开**、第七节 3 条「咬不住」**2 条已闭 1 条仍开**。

> 本轮口径：只读业务代码 ＋ 独立跑自测 ＋ 自写探针（`/tmp/p14rev2/`，未入仓）；**未改业务代码**（11 次「改坏→取证→还原」，每次以**全量 sha256** 校验还原一致，**11/11 逐字一致**）；未起 8765；用户真实目录**零写**（part12 触发的是**只读**扫描，见第七节 P3-新4）；**本次只追加本报告正文**，未新建文件。

## 一、实跑命令、退出码与断言数

| # | 命令 | 实测输出 | rc |
|---|---|---|---|
| 1 | `python3 tests/selftest_p1_2_contract.py` | `SELFTEST ALL PASS（479 项断言）` | **0** |
| 2 | `python3 tests/selftest_p1_2_frontend.py` | `FRONT ALL PASS` ＋ `FRONT SELFTEST PASS` | **0** |
| 3 | `python3 tests/selftest_v26_presets.py` | `SELFTEST ALL PASS` | **0** |
| 4 | `git diff --check` | 无输出 | **0** |

断言计数（`grep -c '^PASS'`）：contract **479**、frontend **139**、presets **58**——与派单书给的 `479／139／58` **逐个一致**。
耗时（自测）：contract `real 1.48s`、frontend `real 0.27s`（用于核 P3-新4）。

**sha256（四文件，全量）**：

```
app/index.html                  31e1ea5bad1bd951bfd8029bbacd12cab8ff214dca73449c98398fa4b863313f
app/server.py                   36d78124802d21d07fdb7673b09832943cac5a0a572dbc3f078063c42b70b21f
tests/selftest_p1_2_contract.py 2bf4dddd457144204f48b4d1c5da705719ba241034e3ef40e9f6200dbe0c5bca
tests/selftest_p1_2_frontend.py 122917973ff2256f78978dd2ee2f6df38b26b84138e415fecdb6b01e478cd403
```

- `index.html 31e1ea5b…313f` ＝ builder 报的 `31e1ea5b…313f` **逐字相符**；与复核一记的 `a57fe493…b869` 不同 → 本轮确实改过 `index.html`。
- `server.py 36d78124…b21f` ＝ builder 报的 `36d78124…b21f`，且**与复核一第一节记的后端基线逐字相同 → 后端本轮 0 改动**（独立复核成立）。

## 二、抽检反向证伪（11 条：改坏→跑→记 rc→字节级还原→比对全量 sha256）

抽检含派单书指定的 builder ②③ 两条 ＋ 我自抽的 9 条；`11/11` 还原后 sha256 与基线逐字一致。

| # | 变异 | rc | 咬住它的断言 |
|---|---|---|---|
| **FA-1（＝builder ②）** | `server.py:1636` `alternate_path_redacted` 不脱敏（回 `alternate`） | **1** | `11i 替代路径已脱敏`／`11i 不等于真实替代路径`／`11i 响应里不存在真实替代路径明文`／`6 脱敏 11i 替代路径分支…`（**4 条**，与 builder 报「contract 4 FAIL」逐字相符） |
| **FA-2（＝builder ③）** | 前端替代路径行去掉 `redactPathField`（`:1378`） | **1** | `10g`×3（**3 条**，与 builder 报「frontend 3 FAIL」逐字相符） |
| **FA-4′（＝builder ①）** | `mark()` 退回**真旧形态**（`box.*`→`diagCache.*` ＋ 去守卫） | **1** | `10f 迟到响应不得落到新目录的缓存`／`10f 不得改写快照 id`／`10f 摘要正文里零 A 目录数据`／`10f2 迟到响应同样不串目录`（**4 条**，与 builder 报「frontend 4 FAIL」逐字相符） |
| FA-3（自抽） | `_diag_redact_path` 由末 3 段放宽到**末 4 段**（弱泄漏、不含 `/var/`） | **1** | `11e _diag_redact_path 只留 basename＋两级父目录标签` |
| FA-5（自抽） | 守卫只留 root 检查（删 `diagCache!==box\|\|` 这半） | **0** | ← **无牙**（见 P3-新1） |
| FA-6（自抽） | 前端 `redactPathField` 末 3 段→末 4 段 | **1** | `10b 打码后仍留可用信息`／`10b 来源 label 同口径`／`10g`×2（**4 条**） |
| FA-7（自抽） | 前端 `redactCopyField` 恒等 | **1** | `10b`×3／`10d 降级建议已脱敏`／`10d 页面证据如实说明降级`（**5 条**） |
| FA-8（自抽） | 后端 `source_dir_tail` 直接回真实目录 | **1** | `6g`／`6 脱敏`／`11d`×2／`6 脱敏 11i…`（**5 条**） |
| ⑩（复核一咬不住项） | 页面证据 **recorded** 行去兜底脱敏 | **1** | `10g 未打码的原登记路径同样被脱敏`／`10g 该情形页面证据里零真实绝对路径`／`10g 逐条面板里…` → **已闭** |
| ⑪（复核一咬不住项） | 页面证据 **evidence_sources** 行去兜底 | **0** | ← **仍咬不住**（P3-新2） |
| ⑫（自抽新项） | 页面证据 **evidence_conflicts** 行去兜底 | **0** | ← **仍咬不住**（P3-新2，同根因） |
| ⑬（对照） | 摘要 `label` 去兜底 | **1** | `10b`×3（与复核一一致，证明探针活性） |

**两条自纠留痕（避免后人误读）**：

1. 我第一版 FA-4 **只删了守卫、没把 `box.*` 改回 `diagCache.*`** → rc=0。这是**非变异**（写入仍落在被瞬间换掉的局部 `box` 上，行为等价，rc=0 属**正确**），**不是覆盖洞**。改成真旧形态后 rc=1／4 条咬住。
2. 我的第一条还原脚本把「补丁后文本」误当「原文」写回，造成 `index.html` 漂 1 行（多一个空行）。**sha256 当场抓出**（`ee33ee84…8941` ≠ 基线），我按四步反向替换＋删掉多出的空行复原，最终回到 `31e1ea5b…313f` 逐字一致。**教训**：(a) 还原必须**字节级**（先存 `rb`，还原写 `wb`）；(b) 「把某行删成空串」的变异会在原地留一个空行，反向插回时须一并处理——本轮其余 10 条已改用字节级备份/还原，全部一次到位。

## 三、P2-1（诊断缓存跨目录串味）→ **真闭环**

**① 守卫是否覆盖所有落地路径 → 是，且 `mark()` 是唯一数据写点。**
全文件 `diagCache` 共 11 处（`grep -n` 逐处核过）：写入只有 **3 个整块替换点**——`:1294` 初始化、`:1295 dropDiagCache()`、`:1307 diagCache=box`；对 `byRun/snap/at` 的写入**只有 `mark()` 内的 `box.*` 三处**（`:1319/:1320/:1322`）。`box` 只有被 `:1307` 装进 `diagCache` 后才有读者，而 `mark()` 落地前先过 `:1314 if(diagCache!==box||String(diagCache.root||"")!==root)return null;`。→ **box 外不存在第二个写点，落地路径唯一且被守卫覆盖**。（`:1314` 第二个分句在 `diagCache===box` 时恒成立，属冗余守卫，无害。）
另有独立读取点 `:1396 diagCache.snap`、`:1406 diagCache.byRun`——只读，不构成旁路。

**② 丢弃后是否真能重新发起 → 是，不被 `pending` 卡住。**
自写探针 `/tmp/p14rev2/race2.js`（抽真源码，桩自写）4 个场景，与「旧形态对照」（内存内改回 `mark` 写模块级、不落盘）对照：

| 场景 | 真形态（工作树） | 旧形态对照 |
|---|---|---|
| 1 换目录＋刷新＋迟到响应 | 请求数 2；迟到后仍 `B-ITEM`；snap `diag-B`；root `/rootB`；**串味 false** | 迟到后变 `A-ITEM`；snap 被 `diag-A` 覆盖；**串味 true** |
| 2 只换目录＋迟到响应 | `B-ITEM`；**串味 false** | **串味 true** |
| 3 **A→B→A** | 回 A 时**新发第 3 个请求**（`issued=1`）；终值 `A2-ITEM`／snap `diag-A2`；**未被 A1 覆盖** | 终值被 A1 覆盖 |
| 4 **同目录刷新＋迟到** | 终值 `FRESH-ITEM`／snap `diag-FRESH`；**未被旧响应覆盖** | 被 `STALE-ITEM` 覆盖 |

对照列 4/4 全串味 → **探针活性得到证明**（不是空跑）。场景 3 独立证实「丢弃后必然重新发起、不吃旧 `pending`」；场景 4 证实 `diagCache!==box` 那半确实在起作用（也正因仓内无对应反例 → P3-新1）。

**③ `null` 返回值对 3 个调用点 → 真无副作用。**
`:1407 renderDiagEvidence`／`:1419 copyAllFailedReasons`／`:1434 showFailEvidence` **三处都忽略回调参数**，只重读 `diagItemFor()`／`failedRuns()`。被丢弃时 `box.byRun` 未被写 → 走降级口径（`:1389` 写「诊断不可用…不编造」）；不写缓存、不动 `snap`、不改列表；**不可能出现别的目录的数据**。最坏只是「该次降级」，且下一次调用按 ② 必然重新发起。

**④ 多标签／`reload` → 不是本次新引入的问题（属结构性不存在，非未测）。**
`diagCache` 是**普通模块级 `var`**，`loadDiag`／`mark` 全程不读不写 `localStorage`／`sessionStorage`／`BroadcastChannel`（逐行核过）。多标签各自独立 realm、`reload` 直接重建 realm，**不存在跨标签/跨刷新的共享状态通道**。同一 realm 内快速切目录已由 `10f`（＋刷新）／`10f2`（不刷新）＋我的场景 1-3 覆盖。

## 四、P2-2（替代路径脱敏无牙）→ **真闭环**

**① 新分支是否真跑到（不是被 dot 掉的）→ 是，双证据。**
仓内 `11h` 的 4 条**可达性自断言**（`recorded_path_exists is False`、`identity_match == "MATCH"`、`alternate_path_checked is True`、类别＝`SOURCE_LOCATION_REVIEW`＋置信度 `HIGH`）逐条 PASS；我另写独立探针 `/tmp/p14rev2/alt_branch_probe.py`（导入仓内夹具＋直调 handler，首行 `assert_tmp`，用完即删）复核同一分支：

```
[ALT]   recorded_path_exists=False  alternate_path_checked=True  identity_match=MATCH
        action_category=SOURCE_LOCATION_REVIEW  confidence=HIGH
        alternate_path_redacted='…/p12_ALT_x6gmvdii/_alt/run-alt.mp4'  末段数=3  真实明文在整包=False
[NOALT] recorded_path_exists=False  alternate_path_checked=True  identity_match=UNKNOWN
        alternate_path_redacted=UNKNOWN  category=RETRYABLE_TRANSCRIPTION  confidence=UNVERIFIED
```

**② 断言是整条比对还是弱子串 → 关键处有「逐字/整段」比对，`11i` 本身偏弱但被 `11e` 兜住。**
`11i` 自身是 `startswith("…/")`＋`!= 真实路径`＋弱扫描（这一档确实扛不住「末 4 段」）；但 `11e` 对**同一 helper** `_diag_redact_path` 做了**逐字断言**（`== "…/需转录视频/第七周/样例.mp4"`）——我实测 FA-3（helper 末 3 段→末 4 段）→ **rc=1，正是 `11e` 咬住**。前端同理：`10b 来源 label 同口径`／`10g` 用的是**整段期望串**，FA-6（前端末 4 段）→ rc=1／4 条咬住。→ **「末 4 段」型泄漏在本次返工后已被接住**（复核一 D 节担心的那一档已闭环）。
**③ `11i2` 能否真证明「不编造」→ 能。**
`11i2` 的对照行与 ALT 行走的是**同一条分支**（我的探针确认 NOALT 也是 `recorded_path_exists=False` ＋ `alternate_path_checked=True`），在「同分支、无替代位置命中」下断言 `identity_match != "MATCH"` 且 `alternate_path_redacted == "UNKNOWN"`，且类别/置信度回落到 `RETRYABLE_TRANSCRIPTION`／`UNVERIFIED`（**非** ALT 专属值）→ 证明该字段是**判出来的**，不是常量或编造。

**④ 夹具改动有没有放松既有断言 → 只加不减，无放松（逐行核）。**
- `add_run`：只新增两个**可选**参数，默认值与原写死值**逐字等价**（`content_identity or ("x"*40)`；`truth = identity_from or src_path`，而 `size/mtime` 原来就是取自 `src_path`）。既有调用点全靠默认值，行为不变。
- `make_data_root`：只新增 `alt_dir` 分支；`alt_dir` 缺省 `None` → `identity_from=content_identity=None` → 与旧行为**逐字等价**。
- **diff 内无一行 `check(` 被删**；断言总数 `466`（复核一）＋`13`（`11h`×6＋`11i`×6＋`11i2`×1）＝**479**，与实跑逐字吻合。前端 diff 内**亦无一行 `ck(` 被删**；`127`＋`10f`×6＋`10f2`×2＋`10g`×4＝**139**，吻合。
- 前端新增的 `DECLS`／`extract_decl` 是**照抄真源码**取常量（`FAIL_DIGEST_FIELDS` 等改名即 `AssertionError`），比手写复现更严，不是放松。

## 五、越界与回归（逐项零接触核验）

| 项 | 证据 | 判定 |
|---|---|---|
| 本次返工只碰那 4 个文件 | `git status --porcelain` 仍只有 4 个 `M`＋本报告 `??`；`docs/`、`src/`、`AGENTS.md` 均无改动 | **合规** |
| 主题默认浅色 | `index.html:2` = `<html lang="zh-CN" data-theme="light">`（未动） | **零回退** |
| 词库三铁律 | `tests/selftest_v26_presets.py` **58/58 rc=0**；`app/presets/vocab/*` 未在改动清单 | **零回退** |
| No-Clobber | 本轮**未动任何发布/写盘逻辑**（`server.py` 本轮 0 改动，且与复核一基线同 sha） | **零回退** |
| D-12 | `_strip_paths:354`／`_err_text` 字节未变——**铁证＝`server.py` sha256 与复核一基线逐字相同** | **零回退** |
| P1-3 已收口语义（五桶同源／锁定提示／无目标不画 100%／ELAPSED 等） | `git diff` 的 hunk 全集＝`88／560／604／607／728／748／1228-1440／1843`（`-U0` 实测）。**`renderProgress:832`、`vocabApplyPct:1627`、`vocabApplyLockText:1663`、`#batchLockHint:239/1553` 均不落在任何 hunk 内** → 整个 P1-4 交付（两轮）**一行未碰**；后端 `STATE_BUCKET:1770`／`_state_bucket` 因 `server.py` 0 改动亦未碰 | **零回退** |
| 行号漂移 | 本轮 `index.html` 净 +9，故插入点之后的行号整体 +9（`dropDiagCache` 调用 `2028→2037`、`vocabApplyLockText 1654→1663`）；插入点之前不变（`renderProgress 832`、`REDACT_STOP_CHARS 1250`、`V2O` 五处） | 记一笔（P3-8 相关） |

## 六、复核一 8 条 P3 现状（逐条）

| # | 内容 | 现状 | 证据 |
|---|---|---|---|
| P3-1 | 诊断耗时未实测（逐行 2s 预算／前端无超时取消） | **仍开** | 本轮未碰（`_DIAG_SCAN_TIME_BUDGET_S:1466` 未变）；仍属交 QA 的取证项 |
| P3-2 | `raw_error_code` 恒 `UNKNOWN`（表无该列） | **仍开** | `server.py` 0 改动 |
| P3-3 | `redactPathField`／`redactPathTail` 未 `normpath`、非 `/` 开头原样透传 | **仍开** | 两函数体逐字未动（builder 自陈「一行没碰」属实） |
| P3-4 | `REDACT_STOP_CHARS:1250` 缺 ASCII `(` `)` | **仍开** | `:1250` 现为 `"'\`，。；：、！？（）《》【】[]{}<>|*?\t\n\r"`——仍只有全角 `（）`，**无 ASCII 括号**（如实） |
| P3-5 | 按钮 title 承诺「不含密钥、请求体」实为结构性保证 | **仍开** | `:608` title 逐字未变 |
| P3-6 | 降级提示把 404/网络错写成「未配置绝对数据目录／库缺失或读不出」 | **仍开** | 同句现 `:1389`（行号 +8） |
| P3-7 | `digestDataRoot` 无值/非法时「已查过」哨兵未置位 | **仍开（性质未变）** | `:1299` 早返回分支未改。**补核**：box 化后 `root` 非法时 `diagCache` 不被重置，仍会命中「同目录」的旧缓存；因列表与诊断同为**同一目录**的数据，**不构成跨目录串味**，维持 P3 |
| P3-8 | P1-7 只读盘点过期（HANDOFF 记「`index.html` 可见 4 处待改」） | **仍开＋已变** | `grep -n V2O` 现为 **5 处**：`:6` title、`:38` tape::before、`:179` h1、`:1060`／`:1064` Notification → 与复核一一致，HANDOFF 的「4 处」仍过期；builder 自陈「行号会因 `+9` 再漂」**属实**（`dropDiagCache:2028→2037`） |
| 第七节 ⑨（页面证据 `alternate` 行去兜底 → 曾 rc=0） | **已闭** | FA-2 rc=1（`10g`×3） |
| 第七节 ⑩（页面证据 `recorded` 行去兜底 → 曾 rc=0） | **已闭** | 抽检 rc=1（`10g`×3）——builder 自陈「⑩ recorded 行兜底已顺手有牙」**核实属实** |
| 第七节 ⑪（页面证据 `evidence_sources` 行去兜底 → 曾 rc=0） | **仍开** | 抽检 rc=0 → 记 P3-新2 |

## 七、本次新增 backlog（全部非阻断）

| # | 内容 | 位置 | 归属／说明 |
|---|---|---|---|
| P3-新1 | **守卫 `diagCache!==box` 这半无专项断言**：FA-5（只留 root 检查）→ **rc=0**（咬不住）。缺的反例是「**同一目录**手动刷新＋刷新前那条请求迟到」——我的探针场景 4 证实该情形**真会被旧响应覆盖**（故这半守卫有价值），但仓内 `10f`/`10f2` 都**换了目录**，root 检查即可通过，故接不住。**当前代码行为正确**，纯测试覆盖缺口（后果＝同目录旧快照短暂覆盖，非跨目录泄漏，**不阻断**） | `index.html:1314`；`tests/selftest_p1_2_frontend.py` S10 | 本链 backlog（建议加一条同目录刷新反例，1 个用例即可） |
| P3-新2 | **`evidence_sources`／`evidence_conflicts` 两行兜底脱敏无牙**：抽检 ⑪／⑫ → **rc=0**。根因同复核一 ⑨⑩（`10g` 只给 `recorded`／`alternate` 喂了真路径，这两个数组喂的是无路径常量）。**零当前风险**：后端 `conflicts` 是两条硬编码中文句（`server.py:1609/1622`）、`evidence_sources` 是硬编码列表（`server.py:1648`），结构上不含路径 → 纯测试债 | `index.html:1381-1382`；夹具 `selftest_p1_2_frontend.py:907 p14Item` | 本链 backlog（把 `10g` 夹具扩一个含真路径的 `evidence_sources` 即可） |
| P3-新3 | `11i` 对 `alternate_path_redacted` **无「整条精确值」断言**（`startswith("…/")`＋`!= 真实值`＋弱扫描）。当前精度实际由 `11e` 对**同一 helper** 的逐字断言兜住（FA-3 已证）；但若日后有人让该字段**绕过** `_diag_redact_path` 而用别的写法，`11i` 可能接不住 | `tests/selftest_p1_2_contract.py` `part12_p14_alt_branch` | 本链 backlog（建议钉成 `"…/" + 末 3 段` 精确串；非必要） |
| P3-新4 | **part12 让自动化自测首次真实触发只读全盘扫描**：ALT/NOALT 都是 `recorded_exists=False` → `_diagnosis_item:1584` 调 `_diag_alternate_paths:1487`，其 roots 含 `~/Downloads`＋`/Volumes`（＋tmp 数据目录）。**合法**（项目规矩「只读浏览例外」；有界 `2.0s`/`2000` 目录、`/Volumes` 只顶层、fail-closed 零写、`finally rmtree` 清 tmp），但也意味着**自测耗时开始依赖用户真实目录规模**。实测 contract `real 1.48s`（含 2 行触发的扫描），当前无影响；若用户 `~/Downloads` 很大，最坏每行 +2s | `app/server.py:1487-1527`；`tests/selftest_p1_2_contract.py:1972` | 记一笔，交 QA 侧知悉（无需返工） |
| P3-新5 | **记账口径**：builder 自报增量「`index.html +15/−6`、contract `+98/−7`、frontend `+102/−2`」——contract 的 `98+7=105` 与实测 stat 增量（`99→204`）**对得上**；但 `index.html` 的 `15+6=21` 与实测增量（`217→226＝+9`）**对不上**（frontend 的 `102+2=104` vs 实测 `257→359＝+102` 亦差 2）。复核一时未另存返工前快照，我**无法逐字复现该拆分**。实质无碍：4 文件范围、`server.py` 与复核一基线同 sha、hunk 全集不含 P1-4 块外任何区域——三条独立证据支持「只改 `loadDiag` ＋两个测试文件」 | — | 记账纠偏；下次返工**先把前一版另存 `/tmp`**，把增量做成可复算的差分 |

## 八、数据安全

- **调 handler 的用例首行断言**：`part11_p14_digest:1884` → `make_data_root`（`:126` 自带 `assert_tmp`）→ `assert_tmp(root, "part11_p14_digest")` `:1891`；`part12_p14_alt_branch:1972` → `assert_tmp(root, "part12_p14_alt_branch")` `:1981`；其子用例 `noroot` 亦在**任何 handler 调用之前** `assert_tmp(noroot, …)` `:2018`。逐条核过：**断言先于 handler 调用**。
- **全程外置 tmp ＋ 合成数据**：`tempfile.mkdtemp(prefix="p12_%s_")`，`finally: shutil.rmtree`；视频是 `b"fake-media-…"` 假字节，DDL 复用 `src/stage2` 真 DDL。**无任何真实视频/真实库参与断言。**
- **零写**：ALT 分支只多写 tmp 内的 `_alt/` 合成文件；`_diag_alternate_paths` 是 `os.walk` **只读**遍历，无写盘路径（见 P3-新4）。
- **自测对用户真实目录是「只读」**（part12 触发的扫描），自动化**禁写**红线未破；`~/Downloads` 与 Obsidian 库**零写**。
- 新增行密钥扫描（`git diff` 新增行 × 8 种密钥形态）→ **0 命中**。

## 九、结论

**PASS（无 P0／无 P1，放行 QA）。**

- **P2-1 真闭环**：`mark()` 是唯一数据写点且守卫覆盖全部落地路径；丢弃后必然重新发起（不被 `pending` 占位）——我的探针在**旧形态对照 4/4 串味 vs 真形态 4/4 干净**之间取到了活性证据，并额外覆盖了仓内没测的 A→B→A 与同目录刷新两种情形；`null` 返回对 3 个调用点无副作用；多标签／`reload` 属结构性不存在而非本次新引入。
- **P2-2 真闭环**：真 16 条那条分支已被 `11h` 可达性自断言＋我的独立探针双重确认**真跑到**；`alternate_path_redacted` 精确 3 段且真实明文不在整包；`11i2` 对照（同分支、无替代命中 → `UNKNOWN`＋类别回落）确能证明**不编造**；夹具**只加不减**，断言总数 `466+13=479`／`127+12=139` 逐字吻合，**无既有断言被放松**。
- **越界／回退**：只碰那 4 个文件；`docs/`、`src/`、主题浅色、词库三铁律、No-Clobber、D-12（`server.py` 与复核一基线**同 sha**）**零接触**；P1-3 收口语义经 hunk 全集核验**一行未碰**。
- **P3**：复核一 8 条**全部仍开**（P3-7 性质未变、P3-8 仍过期且行号再漂）；第七节 3 条「咬不住」**⑨⑩已闭、⑪仍开**；新记 **5×P3**（P3-新1／新2 为测试覆盖缺口，均**零当前风险**；新3／新4／新5 为提示与记账）。全部非阻断，记 backlog。
- **未改业务代码、未 commit、未 push**；除本节追加外未动任何文件。

> 放行条件已满足。**QA 建议重点接**：P3-1 真 16 条量级耗时实测、P3-新4 自测耗时对真实目录规模的敏感度、以及复核一第八节列的全部未覆盖项（真机 UI 目检／内联证据块／面板四退出／窄屏内滚）。
