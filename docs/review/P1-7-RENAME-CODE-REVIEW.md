# CODE REVIEW

- Task: DEVELOP-P1-7 产品改名「懒得笔记」（页面 title/h1/流程标识/磁带标识/Notification/两 README 标题+首句括注；DEV_BASELINE=PRODUCT_PLAN_V1.3，Plan:119/:224）
- Commit: 工作树未提交（HEAD=7bc8cec + dirty；diff 3 文件 9+/9−：app/index.html、README.md、README.en.md）
- Reviewer: code-reviewer（独立取证，不采信 builder 自报）
- Result: 过（PASS，无 P0/P1；遗留 1×P2 + 4×P3 观察项）

## 硬门逐项（任一命中即 FAIL，本轮全过）

- **申报外改动**：`git diff --stat` 仅 3 文件（README.en.md 4±、README.md 4±、app/index.html 10±＝5+/5−），合计 9+/9−，与 builder 自报精确一致。`git status --short` 仅此 3 个 M，无未跟踪文件。tests/ 零改动（`git diff --name-only -- tests/ | wc -l` = 0），不存在为过测改断言。app/server.py 零 diff（`git diff --stat app/server.py` 输出为空）。
- **语义性改动**：逐 hunk 审毕，全部为字符串字面量替换（`<title>`、`.tape::before` content、`<h1>` 文本、`new Notification(...)` 第一参、两 README 标题与首句）。标签结构、属性、class、CSS、JS 逻辑零触碰。`<span class="v2o">` span 结构保留（index.html:179）。

## 禁改清单逐项（自己 grep 取证，非 builder 报告转抄）

| 禁改项 | 证据 | 判定 |
|---|---|---|
| `v2o-input-root`/`v2o-vault-root`/`v2o-data-root` | index.html:326 三键原样 | 未动 |
| `v2o-theme`/`v2o-theme-migrated` | index.html:352/:357/:359/:360/:364 原样 | 未动 |
| `v2o-console-data` | server.py:53（零 diff）；README.md:99、README.en.md:99 原样 | 未动 |
| app/server.py | `git diff --stat app/server.py` 空 | 零 diff |
| 主题默认浅色 | index.html:2 `data-theme="light"`、:17 `:root[data-theme="light"]`、:364 兜底 `\|\|"light"` 原样 | 未动 |
| `.v2o` class 与 :27 CSS | index.html:27 `header.top h1 .v2o{color:var(--orange)}`、:179 `class="v2o"` 原样 | 未动 |
| 日志前缀 `v2o-console:` | server.py:6051（零 diff）；contract 自测日志实证仍输出 `v2o-console: "GET / HTTP/1.1" 200 -` | 未动 |
| 版本串 `V2OConsole/1.1` | server.py:6048（零 diff） | 未动 |
| GitHub 仓库名 | `git remote -v` = `…/Video2Obsidian.git`，remote/仓库名不在文件 diff 内 | 未动 |

## 要求点逐项证据（TM 盘点 5 处可见 + README 4 处）

| 应改处 | 证据（当前行号） | 判定 |
|---|---|---|
| index.html :6 title | `:6 <title>懒得笔记 · 本地视频自动转文字</title>` | PASS |
| index.html :38 磁带 | `:38 content:"懒得笔记 · 本机磁带"` | PASS |
| index.html :179 h1 | `:179 <h1><span class="v2o">懒得笔记</span> 本地视频自动转文字</h1>` | PASS |
| index.html :1060/:1064 Notification | 两处 `new Notification("懒得笔记",{body:t})` | PASS |
| README.md:1 | `# 懒得笔记｜本地视频自动转写入库工具` | PASS |
| README.md:11 首句括注 | `懒得笔记（Video2Obsidian）是一个在本机运行的小工具。` | PASS |
| README.en.md:1 | `# 懒得笔记 (Video2Obsidian) — Turn Local Videos into Obsidian Notes` | PASS |
| README.en.md:11 首句括注 | `懒得笔记 (Video2Obsidian) watches a video folder…` | PASS |

hunk 头行号（@@ -3/+3、-35/+35、-176/+176、-1057/+1057）与盘点行号 6/38/179/1060/1064 逐处对上。

## 自测实跑（三套，rc 真贴）

- `python3 tests/selftest_p1_2_contract.py` → rc=0，`SELFTEST ALL PASS（482 项断言）`（含 PASS 8 主题默认浅色未回退）
- `python3 tests/selftest_p1_2_frontend.py` → rc=0，`FRONT SELFTEST PASS`
- `python3 tests/selftest_v26_presets.py` → rc=0，`SELFTEST ALL PASS`

## 残留扫描（全仓，逐处判定）

`grep -rni 'V2O|V20'`（app/ src/ tests/ README*，剔除 v2o- 键/`.v2o` class）后逐处判定：

| 位置 | 内容 | 判定 |
|---|---|---|
| app/server.py:2/:6048/:6192 | docstring/版本串/启动打印含 V2O | 豁免（server.py 禁改零 diff；:6192 终端打印记 P3-2 观察） |
| app/start.sh:2/:26 | 注释与 echo「V2O 本机控制台」 | P3-3 观察（终端可见，不在本轮盘点） |
| src/stage12/menu_bar.py:47/:48/:88/:92/:118/:139/:160 | 菜单栏显示 `V2O`/`V2O S:%d R:%d E:%d`/`V2O unavailable` | P2-1（用户可见品牌面，超出本轮 DoD 盘点，建议下轮统一或书面豁免） |
| tests/selftest_p1_2_contract.py:54、selftest_v26_presets.py:32 | tmp 目录名 `v2o_server_p12`/`v2o_server` | 豁免（目录名类，DoD 明示保持不变） |
| app/index.html:38「本机磁带」 | 「懒得笔记 · 本机磁带」 | 豁免（盘点指定的最终文案，非残留） |

页面可见面（index.html + 两 README）无任何应改未改的 V2O/本机控制台残留。

## 变异证伪抽检（有牙检查，实证）

1. 动手前 `cp -p app/index.html /tmp/p1-7_review_bak/index.html`，双 sha256 一致：`954d54d09118f045d0268b891e4469d6df4352b8bad94232a127649130c3a6b0`（未用 git checkout）。
2. 变异：`<title>` 改回 `V2O · 本机控制台`。
3. 实跑：frontend rc=0（FRONT SELFTEST PASS）、contract rc=0（482 项 ALL PASS）——**变异未被捕获**。
4. 还原后 sha256 复验与备份一致（同上哈希），`git diff --stat` 回到 3 文件 9+/9−，工作树零损。
5. 结论：三套自测对品牌文案**无断言牙**（grep 证实 tests/ 内无 title/h1/品牌断言），记 P3-1。本轮靠人工 grep 兜底成立，建议后续补一条「页面 title/h1 含『懒得笔记』、无裸 V2O 可见文案」的自测断言防回退。

## DoD 五项兼容边界判定

| 边界 | 判定 |
|---|---|
| ① GitHub 仓库名不变 | PASS（remote=Video2Obsidian，README 保留括注） |
| ② v2o-* 键不变 | PASS（5 键逐处原样，见禁改清单表） |
| ③ 日志前缀不变 | PASS（server.py 零 diff + contract 实测日志输出） |
| ④ 数据目录名不变 | PASS（server.py:53 + 两 README:99 原样） |
| ⑤ 页面 title/h1/流程标识/README 改名 | PASS（要求点表 8/8） |

## P0 / P1 Findings

- 无。

## P2 / P3 Backlog Findings

- **P2-1** 菜单栏品牌残留：`src/stage12/menu_bar.py` 七处可见 `V2O`（:47/:48/:92/:118/:139 等）未随改名。不在本轮 DoD 盘点内故不拦，但属用户可见品牌面，建议下轮统一改名或书面豁免。
- **P3-1** 自测无品牌文案断言牙：变异证伪实证（title 改回 V2O 三套自测全 PASS）。建议补防回退断言。
- **P3-2** `app/server.py:6192` 启动打印「V2O 本机控制台」终端可见；server.py 禁改属任务约束，记观察待后续任务处理。
- **P3-3** `app/start.sh:2/:26` 注释/echo「V2O 本机控制台」终端可见，不在盘点内，记观察。
- **P3-4** `app/server.py:6048` `server_version = "V2OConsole/1.1"` 为版本标识符，保持不变是正确的兼容决策（改了反而破坏可识别性），书面豁免记录。

## 复核结论

P1-7 改名任务 **PASS**：申报 3 文件 9+/9− 精确一致、纯文案零语义混入、禁改清单 9 项全未动、要求点 8/8 改到位、三套自测 rc=0 且 tests/ 零改动、变异证伪已做并如实记录（无牙为既有事实非本次引入）、五项兼容边界全 PASS。可进 QA/supervisor 链。

---

# 返工复核二（2026-09-15）

- Task: DEVELOP-P1-7 返工复核（Change B：P2-1 menu_bar 可见文案＋P3-1 断言牙＋P3-3 start.sh＋追加 status_cli:124）
- HEAD 仍为 7bc8cec，工作树 dirty；Reviewer 独立取证，不采信 builder 自报
- Result: **PASS**（无 P0/P1；无新增 findings，上轮 P3-2/P3-4 维持不动）

## 净增量重建（逐文件对上，无申报外改动）

`git diff --stat`＝7 文件 34+/16−，与申报精确一致：

| 文件 | diff | 判定 |
|---|---|---|
| app/index.html | 10±（5+/5−） | 上轮 PASS 交付，本轮**零触碰**（sha256 `954d54d09118f045d0268b891e4469d6df4352b8bad94232a127649130c3a6b0` 与上轮记录哈希逐字相同） |
| README.md / README.en.md | 4±/4± | 上轮 PASS 交付，本轮零触碰 |
| src/stage12/menu_bar.py | 8±（4+/4−） | 本轮①派，见下 |
| app/start.sh | 4±（2+/2−） | 本轮①派（:2/:26） |
| src/stage12/status_cli.py | 2±（1+/1−） | 本轮②派（仅 :124） |
| tests/selftest_p1_2_frontend.py | +18（brand_checks） | 本轮①派断言牙 |

`git status --short` 除 7 个 M 外仅 `?? docs/review/P1-7-RENAME-CODE-REVIEW.md`（本报告自身），无未跟踪代码文件。

## menu_bar.py 七处逐处判定

| 行 | 内容 | 判定 |
|---|---|---|
| :47 | `return "懒得笔记 unavailable"` | 改，正确（title 可见） |
| :48 | `return "懒得笔记 S:%d R:%d E:%d"` | 改，正确（title 可见） |
| :92 | `super().__init__("懒得笔记")` | 改，正确（菜单栏应用名可见） |
| :139 | `description="Optional read-only 懒得笔记 menu-bar display."` | 改，正确（--help 可见） |
| :88 | `class V2OApp(_rumps.App):` | 留，正确（类名技术标识） |
| :118 | `class V2OApp:` | 留，正确（降级占位类名） |
| :160 | `app = V2OApp(args.data_root, args.limit)` | 留，正确（类引用） |

grep 该文件可见文案 V2O 零残留（仅剩 V2OApp 类名 3 处）。

## status_cli.py / start.sh

- status_cli.py：仅 :124 `description="Read-only 懒得笔记 status display…"` 一处改；`prog="stage12-status"`（:123）及函数名等技术标识未动。全文件 V2O 零残留。
- start.sh：:2 注释与 :26 echo 改「懒得笔记 本机控制台」，`set -eu`/ROOT/端口 8765 逻辑零触碰。

## 禁改清单（本轮全量重核，grep 取证）

| 禁改项 | 证据 | 判定 |
|---|---|---|
| v2o-input/vault/data-root | index.html:326 原样 | 未动 |
| v2o-theme / v2o-theme-migrated | index.html:352/:357/:359/:360/:364 原样 | 未动 |
| v2o-console-data | server.py:53（`git diff app/server.py`＝0 行） | 未动 |
| 主题默认浅色 | index.html:2 `data-theme="light"`、:17、:370 兜底 `\|\|"light"` 原样 | 未动 |
| `.v2o` class 与 :27 CSS | index.html:179 `class="v2o"` 原样 | 未动 |
| 日志前缀 `v2o-console:` | server.py:6051（零 diff） | 未动 |
| 版本串 `V2OConsole/1.1` | server.py:6048（零 diff） | 未动 |

## 断言牙（brand_checks，frontend 自测 :1393-1410）

六处钉点：title、h1、磁带 content、start.sh 无 V2O、menu_bar.py 可见文案无 V2O（V2OApp 豁免）、status_cli.py 同口径。豁免逻辑正确（技术标识不入列）。tests/ 改动仅为追加 brand_checks 函数与 main() 两行调用，既有断言零触碰（diff 仅 +18/-0）。

## 变异证伪（两条，独立实跑，/tmp 备份还原，未用 git checkout）

1. 动手前 `cp -p` menu_bar.py/status_cli.py → `/tmp/p1-7_review2_bak/`，双 sha256 一致（`3067d4ea…`/`533b2b05…`）。
2. **变异一** menu_bar.py:47 回滚 `"V2O unavailable"` → frontend **rc=1**，断言精确咬住：`menu_bar.py 可见文案 V2O 残留（非 V2OApp 类名）: ['return "V2O unavailable"']`。还原后 sha256 与备份一致。
3. **变异二** status_cli.py:124 回滚 `"Read-only V2O status display"` → frontend **rc=1**，断言精确咬住：`status_cli.py 可见文案 V2O 残留…: ['description="Read-only V2O status display…"]`。还原后 sha256 `533b2b05…` 与备份一致，复跑 frontend rc=0，`git diff --stat` 复位 7 文件 34+/16−，工作树零损。

上轮 P3-1（无断言牙）就此关闭：变异即挂，防回退牙已生效。

## 三套自测实跑（rc 真贴）

- `python3 tests/selftest_p1_2_frontend.py` → rc=0，`BRAND SELFTEST PASS` ＋ `FRONT SELFTEST PASS`
- `python3 tests/selftest_p1_2_contract.py` → rc=0（482 项）
- `python3 tests/selftest_v26_presets.py` → rc=0

## DoD 六项判定

| 项 | 判定 |
|---|---|
| ① GitHub 仓库名不变 | PASS（remote=Video2Obsidian，未触碰） |
| ② v2o-* 键不变 | PASS（见禁改清单） |
| ③ 日志前缀不变 | PASS（server.py 零 diff） |
| ④ 数据目录名不变 | PASS（server.py:53 零 diff） |
| ⑤ 页面 title/h1/流程标识/README 改名 | PASS（上轮 8/8，本轮零触碰零回退） |
| ⑥ 菜单栏/CLI/start.sh 可见名称扩展项 | PASS（menu_bar 4 改 3 留正确、status_cli:124、start.sh:2/:26，可见面 V2O 零残留，且有断言牙防回退） |

## P0 / P1 Findings

- 无。

## P2 / P3 Backlog Findings

- 上轮 P2-1（menu_bar）、P3-1（无断言牙）、P3-3（start.sh）本轮全部关闭。
- P3-2（server.py:6192 启动打印）与 P3-4（V2OConsole/1.1 版本串豁免）维持不动，结论照旧。
- 无新增 findings。

## 复核结论

P1-7 返工（Change B）**PASS**：净增量 7 文件 34+/16− 与申报精确一致、上轮已 PASS 文件（index.html/两 README）sha256 零触碰、menu_bar 4 改 3 留逐处判定正确、status_cli/start.sh 精确单点、禁改清单 7 项全原样、brand_checks 六处断言牙经两条变异实证 rc=1（/tmp 还原零损）、三套自测 rc=0、DoD 六项全 PASS。可进 QA/supervisor 链。

---

> 勘误注记（2026-09-15，加注人 neat-freak）：复核二中「主题兜底」引用行号 `:370` 系笔误，实际为 `:364`（supervisor 复检发现）。仅行号更正，复核结论不变。
