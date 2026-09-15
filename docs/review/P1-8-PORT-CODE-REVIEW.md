# CODE REVIEW

- Task: **DEVELOP-P1-8「默认端口去硬编码：8765 → 8899」首轮代码复核**
- Commit: 工作树未提交，基线 `HEAD=f611824867568d7d23f2e0a7ca6e6c7427b8a0af`
- Reviewer: code-reviewer（`opencode/muse-spark-1.3-contributor-free`，本窗口 subagent 直派；独立 Session）
- Result: **PASS 带 P2×2 / P3×4**（无 P0/P1；业务代码零回归，主钉值断言有牙；两条 P2 属"守备牙口"缺口，非现网缺陷）
- 取证目录（全部系统 tmp，非仓内）：`/tmp/p18rev/`（备份 10 文件 + sha256、`ast_diff2.py`、`brand_probe.py`、`port_probe.py`、`start_probe.sh`、`falsify.py`）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

---

## 〇、结论一句话

`app/server.py:55-68` 的端口真源改造**只动了端口这一件事**（AST 函数级差异 **0/170**，顶层语句多重集差集**恰好**＝旧 `PORT = 8765` 一条）；`app/index.html` 与 `src/` **零改动**；三套自测 **513/167/58 rc=0** 与 builder 自报逐个吻合；默认端口钉值断言**有牙**（改回 8765 → contract rc=1）。品牌守卫**不是整行豁免**（同行真违规仍咬住），但 builder 顺手加的 `V2OApp` 子串豁免是**本轮新引入的放宽**（P2-2）。start.sh 端口/URL **无任何自动牙口**（P2-1）。

---

## 一、复核范围与方法（实跑命令 + rc 表）

### 1.1 交付实体核对（`git diff --stat`）

| 项 | 卡面 | 实测 | 判定 |
|---|---|---|---|
| 文件数 | 8 文件 | **8 文件**（`git diff --stat`） | 一致 |
| 增删行 | 约 +39/−20 | **+50/−21**（`git diff --numstat` 合计） | **不符**（见 P3-4） |
| 清单外改动 | 无 | `git status --porcelain` 仅 8×`M` ＋ `?? .codebuddy/`（会话产物，前序既有） | 一致 |

逐文件 numstat：`README.en.md 3/3`、`README.md 3/3`、`app/server.py 14/1`、`app/start.sh 8/5`、`docs/troubleshooting.md 2/2`、`docs/usage.md 2/2`、`tests/selftest_p1_2_contract.py 13/3`、`tests/selftest_p1_2_frontend.py 5/2`。

### 1.2 实跑命令与 rc 表

| # | 命令 | rc | 关键输出 |
|---|---|---|---|
| R1 | `python3 /tmp/p18rev/ast_diff2.py` | 0 | 函数数 HEAD=170 / WT=170；**同名函数体变了 0 个**；新增/删除函数 0 个 |
| R2 | 顶层语句多重集比对（`ast` + sha256） | 0 | only-HEAD **1 条**＝`PORT = 8765`(:55)；only-WT **4 条**＝`PORT = 8899`(:56)、`_env_port = …`(:57)、`if _env_port:`(:58-67)、`del _env_port`(:68) |
| R3 | `git status --porcelain -- app/index.html src/` | 0 | **空**（零改动） |
| R4 | `sh -n app/start.sh` | **0** | 语法通过 |
| R5 | `python3 /tmp/p18rev/port_probe.py`（15 个 V2O_PORT 取值） | 0 | **15/15 符合预期**，见 §二.3 |
| R6 | `bash /tmp/p18rev/start_probe.sh`（A–E 五用例真起服务） | 0 | A 默认→8899 HTTP200；B `V2O_PORT=8903`→8903 HTTP200；C 空串→8899；D `abc`→start.sh rc=1 人话；E 纯空格→8899 但打印坏 URL |
| R7 | `python3 tests/selftest_p1_2_contract.py` | **0** | `SELFTEST ALL PASS（513 项断言）`，`^PASS` 行 = **513** |
| R8 | `python3 tests/selftest_p1_2_frontend.py` | **0** | `FRONT SELFTEST PASS`，`^PASS` 行 = **167** |
| R9 | `python3 tests/selftest_v26_presets.py` | **0** | `SELFTEST ALL PASS`，`^PASS` 行 = **58** |
| R10 | `python3 /tmp/p18rev/brand_probe.py`（9 个合成用例） | 1 | 6 符合 / 3 不符（不符即抓到的洞），见 §二.2 |
| R11 | `python3 /tmp/p18rev/falsify.py`（5 条反向证伪） | 0 | 有牙 2 条（F1、F4）＋无牙 3 条（F2/F2b/F3 对照），全部 sha256 还原一致 |
| R12 | `grep -rn "8765" <8 文件>` | 1 | **零命中**（见 §二.7） |
| R13 | `lsof -nP -iTCP:8765/8899/8903/8904 -sTCP:LISTEN` | 0 | 探针前后 8765 恒为 **PID 6586**；8899/8903/8904 收尾全空 |

---

## 二、逐项裁定

### 1. 范围严查（机器比对，非目测）——**PASS**

- **`app/server.py`**：`ast` 逐函数（含嵌套）算 sha256，**170 vs 170，函数体差异 0**；顶层非 def 语句用多重集差集，只有 `PORT = 8765`(HEAD:55) 被移除、4 条新语句（`:56/:57/:58-67/:68`）加入。**照此，起服务语义 `server = ThreadingHTTPServer((HOST, PORT), Handler)`（`app/server.py:6381`）、`_handle_status`、恢复/词库/诊断/发布/browse/start/stop 等全部函数逐字未动**（行号因插入 13 行整体下移，非内容改动）。
- **`PORT` 仅两处使用**：真源定义 `app/server.py:56` 与 serve 点 `:6381`（引擎侧 `81 行`外无其它硬编码 4 位端口）。
- **`app/index.html` 零改动 / `src/` 零改动**：`git status --porcelain -- app/index.html src/` 输出为空。（说明：本卡卡面提到"`app/index.html` 的改动"，实际**无任何改动**，我按实测记账。）
- **无重复真源**：全仓 `.py/.sh/.html/.js` 内 `PORT=` 赋值点仅 `app/server.py:56` 与 `app/start.sh:8`（同一默认值的两处落点，见 P2-1）。

### 2. 品牌守卫豁免是否被放宽出洞——**裁定：核心洞不存在；但新增 1 个窄洞（P2-2）+ 1 个前缀过宽（P3-3）**

被检代码 `tests/selftest_p1_2_frontend.py:1443-1446`（守卫），HEAD 原版为 `assert "V2O" not in <start.sh 全文>`。

我用 `/tmp/p18rev/brand_probe.py` **直接 import 真测试文件并调用其 `brand_checks()`**（不手抄守卫代码），9 例结果：

| 用例 | 塞进 `app/start.sh` 的内容 | HEAD 版守卫 | 现守卫 | 期望 | 判定 |
|---|---|---|---|---|---|
| B1 | `echo "V2O 本机控制台"` | 咬住 | **咬住** | 咬住 | OK |
| B2 | `V2O_FOO=1`（非 V2O_PORT 的新标识） | 咬住 | **咬住** | 咬住 | OK（**未被误豁免**） |
| B3 | `echo "V2O 本机控制台 $V2O_PORT"`（同行混放） | 咬住 | **咬住** | 咬住 | OK（**不是整行豁免**） |
| B4 | `# 端口见 V2O_PORT 说明`（注释） | 咬住 | 放行 | 放行 | OK（正当豁免） |
| B5 | `echo "V2OApp 本机控制台"` | 咬住 | **放行** | 咬住 | **P2-2** |
| B6 | `V2O_PORT_EXTRA=1` | 咬住 | **放行** | 咬住 | **P3-3** |
| B7 | `echo "V2O-Console"` | 咬住 | **咬住** | 咬住 | OK |
| B8 | `echo "V2OApplication 控制台"` | 咬住 | **放行** | 咬住 | **P2-2** |
| B9 | 不动 start.sh（基线） | 放行 | 放行 | 放行 | OK |

三问三答（照卡面要求）：

1. **①裸品牌 / V2O-xxx / 裸 `V2O ` 是否仍 FAIL** → **是**。B1/B2/B3/B7 全部咬住，守卫**没有**被放宽成"含 V2O 即豁免"。
2. **②豁免粒度是否过宽（整行豁免顺手放过同行其它违规）** → **不是整行豁免**。`l.replace("V2O_PORT","")` 只摘掉那一个精确 token，同行其它 `V2O` 仍在（B3 咬住，`:1445` 定位为行内替换而非行跳过）。**但 `V2OApp` 这一档是多做的豁免**（B5/B8），且 HEAD 版没有它 → **本链新引入的放宽**（F3 差分实证：把守卫改成"整行含 V2O_PORT 即跳过"→ 同一用例转红为放行，证明该洞真实存在且我的探针有分辨力；而 builder 的实现没有这类整行洞）。
3. **③任意含 `V2O` 子串的新标识是否被误豁免** → **会，两档**：`V2OApp…`（B5/B8，P2-2）与 `V2O_PORT…`（B6，P3-3）。**修法**（`tests/selftest_p1_2_frontend.py:1445` 起）：

```python
import re
# 只豁免「精确 token V2O_PORT」；start.sh 内不存在 V2OApp 类名，不需要该档豁免
sh_left = [l.strip() for l in sh.splitlines() if "V2O" in re.sub(r"V2O_PORT\b", "", l)]
```

`\b` 保证 `V2O_PORT_EXTRA` 仍被咬住（`_` 是词字符，`\b` 不成立），同时保留 `V2O_PORT` 的正当豁免。

### 3. 端口真源独立复算——**PASS（15/15），无"裸崩/坑"**

`/tmp/p18rev/port_probe.py` 子进程实跑 `import app/server.py`（`os.environ` 逐例隔离）：

| V2O_PORT | 实测 | 期望 | 判定 |
|---|---|---|---|
| 未设 | `PORT=8899` | 8899 | OK |
| `8901` | `PORT=8901` | 8901 | OK |
| `""`（空串） | `PORT=8899` | 8899 | OK |
| `"   "`（纯空格） | `PORT=8899` | 8899 | OK（`.strip()`，`app/server.py:57`） |
| `"abc"` | rc **2** ＋人话 | rc2 | OK |
| `"0"` | rc **2**（`超出 1-65535 范围：0`） | rc2 | OK（**0 未被当合法端口**） |
| `"-1"` | rc **2** | rc2 | OK |
| `"70000"` | rc **2** | rc2 | OK |
| `"8899.5"` | rc **2**（`必须是 1-65535 的整数`） | rc2 | OK |
| `65535` / `1` | 65535 / 1 | 同 | OK |
| `" 8899 "` / `"+8901"` / `"8899\n"` | 8899 / 8901 / 8899 | 同 | OK（`int()` 容错，无害） |
| `"0x22c3"` | rc **2** | rc2 | OK |

- 人话报错两条分别落在 `app/server.py:62-64`（非整数）与 `:65-67`（越界），均 `raise SystemExit(2)`，`start.sh` 侧转成 `rc=1` ＋「启动失败，查看上方报错。」（R6/D 实测）。
- 无裸崩、无静默钳制。**范围下界 1 与实测 bind 能力不符** → P3-2（见下）。

### 4. start.sh 联动——**PASS（真起服务两组均通），但牙口缺失记 P2-1**

- `sh -n app/start.sh` **rc=0**（R4）。
- `set -eu` 下无未定义变量风险：`PORT="${V2O_PORT:-8899}"`（`app/start.sh:8`）用 `:-` 兜底，V2O_PORT 未设/为空均得值；`$PORT` 首次使用（`:30/:37/:39/:41`）晚于定义。`V2O_PORT="$PORT" "$PY" app/server.py &`（`:30`）为**透传**，非导出污染。
- **真起服务**（本窗口可 bind；`open`/`xdg-open` 用 `/tmp` no-op 遮掉以免弹浏览器）：
  - 默认 → 监听 `127.0.0.1:8899`，`curl` **HTTP 200**，日志「已起 http://127.0.0.1:8899/」；
  - `V2O_PORT=8903` → 监听 `127.0.0.1:8903`，`curl` **HTTP 200**；
  - `V2O_PORT=`（空串）→ 回落 8899，`curl` HTTP 200；
  - `V2O_PORT=abc` → `start.sh` **rc=1**，输出 `V2O_PORT 必须是 1-65535 的整数，当前为 'abc'…` ＋「启动失败」；
  - **两份服务均已停**，`8899/8903/8904` 收尾 `lsof` 全空；**8765 全程未 bind、PID 6586 前后一致**。
- **首个用例失败后我修正了探针的清理顺序**（首版 C 用例与 A 同端口互撞），结论以修正后 R6 为准。

### 5. 三套自测独立复跑——**PASS，数字与 builder 自报逐个吻合**

| 套件 | 卡面/builder 自报 | 我实测 | rc |
|---|---|---|---|
| `tests/selftest_p1_2_contract.py` | 513 | **513**（`^PASS` 行 513，汇总行「513 项断言」） | 0 |
| `tests/selftest_p1_2_frontend.py` | 167 | **167**（`^PASS` 行 167；无汇总数字行） | 0 |
| `tests/selftest_v26_presets.py` | 58 | **58**（`^PASS` 行 58；无汇总数字行） | 0 |

新增两条断言**确实执行且通过**：`contract` 输出 `:268` `PASS 8 端口不是 8899（不碰线上服务）`、`:269` `PASS 8 未设 V2O_PORT 时默认端口＝8899（真源，防回退）`。注：`:951` 那条因走临时端口（`ThreadingHTTPServer(("127.0.0.1",0))`）几乎恒真，实为"不碰线上"护栏，**真钉值在同块 `:960-961`**（`tests/selftest_p1_2_contract.py:952-961`）。

### 6. 反向证伪——**5 条实跑，2 条有牙 / 3 条无牙（如实记账）**

| 编号 | 改坏内容 | 跑什么 | rc | 牙口 | 还原 sha256 |
|---|---|---|---|---|---|
| **F1** | `app/server.py:56` `PORT = 8899` → `8765` | contract / frontend / v26 | **1** / 0 / 0 | **有牙** | 一致 |
| **F2** | `app/start.sh:39` `open "http://127.0.0.1:$PORT/"` → `8765` | contract / frontend / v26 | 0 / 0 / 0 | **无牙** | 一致 |
| **F2b** | `app/start.sh:8` `PORT="${V2O_PORT:-8899}"` → `PORT=8904` | contract / frontend / v26 | 0 / 0 / 0 | **无牙** | 一致 |
| **F3** | 守卫改「整行含 V2O_PORT 即跳过」＋同行塞真违规 | `brand_checks()` | 0（放行） | 对照：证明该洞真实存在，且 **builder 的实现无此洞** | 一致 |
| **F3b** | 只塞同行真违规，守卫不动 | `brand_checks()` / frontend | **1** / 1 | **有牙** | 一致 |
| **F4** | `app/server.py:65-67` 删掉 1-65535 范围校验 | 探针 `V2O_PORT=0` | 0（`PORT= 0`） | 对照：证明范围校验是唯一拦住 `0` 的闸门（有牙反向证据） | 一致 |

- F1 失败原文：`FAIL 8 未设 V2O_PORT 时默认端口＝8899（真源，防回退）  << 8765` ＋ `SELFTEST FAIL 1/513`。
- **还原方式**：全程只从 `/tmp/p18rev/<path>` 备份 `cp` 回写，**未使用 `git checkout`**；10 个受检文件（含 `app/index.html`、`tests/selftest_v26_presets.py`）终态 sha256 与备份**逐字一致**（见 §四）。

### 7. 文档一致性——**PASS（8 文件内），清单外 2 处残留记 P3-5**

- 8 文件内 `grep -rn "8765"` → **零命中**（R12）。
- `8899` 落点与卡面完全一致：`README.md:40/:73/:81`、`README.en.md:40/:73/:81`、`docs/usage.md:17/:20`、`docs/troubleshooting.md:22/:25`、`app/server.py:55-56/:63`、`app/start.sh:2/:7/:8`。
- **无"固定 vs 可覆盖"并存**：8 文件内"固定"命中 6 处，全部与端口无关（数据目录措辞、契约字段措辞）；端口措辞统一为「默认 …；如需换端口，用环境变量 `V2O_PORT` 覆盖」。
- **中英对称**：`README.md:73` 与 `README.en.md:73`、`usage.md:20` 与 README 中文同义同数字；`troubleshooting.md:25` 独有"冲突时换端口"的建议，与另两处不矛盾。
- 无 87xx 其它残留数字（`grep -rnE "87[0-9]{2}"` 8 文件零命中）。
- **清单外残留（角色禁改，交 TM 收口）**：`docs/handoff/HANDOFF.md:73`「`PORT` 硬编码 8765」、`:46` 教用户「用 `PORT=xxxx` 覆盖」（**该变量名现不生效**，真值是 `V2O_PORT`）；`docs/pm/PRODUCT_PLAN.md:11`「仅监听 `127.0.0.1:8765`」（`docs/pm/` 属 planner 域，我禁改）。详见 P3-5。

### 8. 红线核查——**全部 PASS**

| 红线 | 取证 | 结论 |
|---|---|---|
| 未碰 secrets | `git diff \| grep -inE "api[_-]?key\|secret\|token\|password\|sk-\|bearer"` → 空 | PASS |
| 未改封存物 | 仓内无 `V1.10/V2.0` 目录；`git status --porcelain` 无相关命中 | PASS |
| 测试只用外置 tmp＋合成数据 | `contract` part8 走 `ThreadingHTTPServer(("127.0.0.1", 0))` 临时端口；新增块（`:952-961`）**只动 `os.environ`＋重载模块，无任何文件写**；三套自测跑完 `git status` 仍只有 8×`M`＋`?? .codebuddy/` | PASS |
| 用户真实视频目录 / Obsidian 库零写 | 我的探针只起本项目 `app/server.py`（`DEFAULT_DATA_ROOT`＝系统 tmp `/tmp/v2o-console-data`）；未访问 `Downloads/需转录视频` 与 ob 库 | PASS |
| 外部 8765 进程零扰动 | `lsof` 前后同一 **PID 6586**；全程未 bind 8765、未 kill 非自起 PID（清理只对 `8899/8903/8904` 上自起 PID） | PASS |
| 未碰 `008林粒粒AI编程/` | `git status --porcelain -- "008林粒粒AI编程/"` → 空 | PASS |

---

## 三、P0 / P1 Findings

- **无。** 业务代码零回归（AST 函数级差异 0/170），主钉值断言有牙，端口解析边界无裸崩/无静默错收。

---

## 四、P2 / P3 Backlog Findings

### P2-1（牙口缺口，**本卡最严重**）：start.sh 的端口/URL 无任何自动断言，默认值两处复制有漂移风险

- 证据：F2、F2b 两条改坏（`open` 硬编码 8765；`PORT` 不再读环境变量）**三套自测全部 rc=0**；`grep -rn "start.sh\|V2O_PORT" tests/` 显示除品牌守卫外**没有任何测试读 start.sh 的端口**。
- 风险：`8899` 现落在两处（真源 `app/server.py:56` 与 `app/start.sh:8`）。若日后只改 server.py 默认值，`./app/start.sh` 仍发 `V2O_PORT=8899` → **start.sh 起 8899、裸 `python3 app/server.py` 起新默认值**，两入口静默分叉；而 `contract:960` 只钉 server.py，咬不住 start.sh。
- 修法（二选一，推荐 ①，改动最小）：
  ① 在 `tests/selftest_p1_2_frontend.py::brand_checks()` 或 `contract` part8 补一条静态一致性断言：
  ```python
  import re
  sh   = open(os.path.join(root, "start.sh"), encoding="utf-8").read()
  srv  = open(os.path.join(root, "server.py"), encoding="utf-8").read()
  a = re.search(r"^PORT = (\d+)$", srv, re.M)
  b = re.search(r'^PORT="\$\{V2O_PORT:-(\d+)\}"$', sh, re.M)
  assert a and b and a.group(1) == b.group(1), "start.sh 与 server.py 默认端口漂移"
  assert "$PORT" in sh and not re.search(r"127\.0\.0\.1:\d{4}", sh), "start.sh 出现硬编码端口"
  ```
  ② 让 start.sh 不写默认值（`V2O_PORT` 未设时完全不传该变量），默认只留 `app/server.py:56` 一处；代价是 start.sh 打 URL 前需读一次真源（`"$PY" -c "import importlib.util…print(m.PORT)"`），比 ① 重。

### P2-2（本轮新引入的守卫放宽）：`V2OApp` 子串豁免使含 `V2O` 的品牌文案可整行溜过

- 位置：`tests/selftest_p1_2_frontend.py:1445` 的 `and "V2OApp" not in l`。
- 证据：B5（`echo "V2OApp 本机控制台"`）与 B8（`echo "V2OApplication 控制台"`）**现守卫放行**；用 HEAD 版守卫（`git show HEAD:…` 逐字取回）对同一内容跑 → **咬住**。即 HEAD 对 start.sh 是"全文零 V2O"，本链把它放宽了两档。
- 判断：`V2OApp` 豁免是从 `menu_bar.py`（`:1448`）检查照抄过来的，**start.sh 内根本不存在 `V2OApp` 类名**，这一档属多余的自我放宽；后果仅限"守卫守备力"，无现网影响，故 P2 而非 P1。
- 修法：见 §二.2 的 `re.sub(r"V2O_PORT\b", "", l)` 一行替换（去掉 `V2OApp` 档）。

### P3-1：start.sh 纯空格 `V2O_PORT` 会打印/打开坏 URL

- 位置：`app/start.sh:8/:37/:39/:41`。
- 证据（R6 用例 E）：`V2O_PORT=' ' ./app/start.sh` → 实际监听 **8899**（server 侧 `.strip()` 兜住），但日志原文为 `已起 http://127.0.0.1: /`，且 `open` 会去开这个坏 URL。`${V2O_PORT:-8899}` 只把**空串**当未设，不管纯空格/前后空格。
- 修法：`PORT="$(printf '%s' "${V2O_PORT:-8899}" | tr -d '[:space:]')"; [ -n "$PORT" ] || PORT=8899`（或在 `:8` 后加一行 trim）。

### P3-2：范围消息自称 1-65535，但 1-1023 会在 bind 抛裸 traceback

- 位置：`app/server.py:65-67`。
- 证据（实跑）：`V2O_PORT=100 python3 app/server.py` → 解析通过，随后 `PermissionError` 裸 traceback（`app/server.py:6381` → `socketserver.server_bind`）；本机 `uid=501`（非特权）。
- 修法：把下界改 `1024`，或把 `ThreadingHTTPServer((HOST, PORT), Handler)` 包 `try/except OSError` 输出人话（含"端口被占用/需特权端口"两类分流）。

### P3-3：`V2O_PORT` 前缀延伸标识被豁免（`.replace` 的前缀语义）

- 位置：`tests/selftest_p1_2_frontend.py:1445`。
- 证据：B6 `V2O_PORT_EXTRA=1` → 放行。属技术标识而非用户可见文案，影响面极小；随 P2-2 的 `\b` 修法一并收口。

### P3-4：卡面计数与实测不符（以实测为准）

- 卡面「约 +39/−20」，实测 `git diff --numstat` 合计 **+50/−21**（8 文件）。**以实测为准**（沿用 P1-6 链 P3-2「numstat 口径差」先例，不改报告正文之外的口径）。

### P3-5：清单外 docs 仍写 8765 / 旧覆盖变量名（角色禁改，交 TM）

- `docs/handoff/HANDOFF.md:73`「`PORT` 硬编码 8765」、`:46`「用 `PORT=xxxx` 覆盖起服务」——**`PORT` 这个变量名在 HEAD 与工作树的 server.py 里都从未被读取**（`git show HEAD:app/server.py` 内 `environ["PORT"]` 零命中），即该行原本就不可执行；本卡把真覆盖变量定为 `V2O_PORT`，建议 TM 收口时把 HANDOFF 服务节改写为 `V2O_PORT=xxxx`。
- `docs/pm/PRODUCT_PLAN.md:11`「仅监听 `127.0.0.1:8765`」——`docs/pm/` 属 planner 域，且为 Phase1 快照，我未改。
- 以上**不计入本卡 8 文件范围**（卡面已声明"清单外历史 docs 命中不算"）。

---

## 五、未覆盖项（如实标注，不可推断为通过）

1. **真机浏览器目检**：`start.sh` 的 `open`/`xdg-open`（`:38-42`）被 `/tmp/p18rev/fakebin` no-op 遮掉，未验浏览器是否真打开 `http://127.0.0.1:8899/`；本卡交付面为端口＋文案，UI 目检按 HANDOFF 归真机流程。
2. **Windows / 其他 OS**：`app/start.sh` 是 POSIX sh，本卡未验 Windows 侧启动入口（仓内无对应脚本）。
3. **8899 被占用时的行为**：本窗口 8899 实测空闲，未测 `EADDRINUSE` 下 start.sh 的提示质量（由 P3-2 的 try/except 修法一并覆盖）。
4. **`docs/pm/` 与 HANDOFF 的 8765 残留**：角色禁改，已在 P3-5 记账，未落地修改。
5. **未跑 qa 视角的完整端到端旅程**（真实 whisper／真机 UI／长视频），归属 P1-1 与 QA 卡，本卡不重复。
6. **`PORT` 语义面**：本卡只验「端口取值与监听」，未验监听地址 `HOST`（`:54` `127.0.0.1` 未动，逐字与 HEAD 相同）。

---

## 六、裁定汇总

| 维度 | 判定 |
|---|---|
| DEV_BASELINE 一致（`PRODUCT_PLAN_V1.3`，改动面＝卡面 8 文件） | PASS |
| Requirement 覆盖（默认 8899＋单真源＋start.sh 联动＋文档换数字＋断言改写） | PASS |
| DoD 达成（三套 513/167/58 rc0；真起服务 8899/8903 双 HTTP200） | PASS |
| Diff 越界（`app/index.html`、`src/`、`docs/pm/`、HANDOFF 零改） | PASS |
| 回归影响（AST 函数级 0/170；起服务语义 `:6381` 逐字未动） | PASS |
| P0-P2 分级 | 无 P0/P1；P2×2、P3×5 |
| 可回滚性 | 8 文件纯文本、无 schema/数据迁移，`git diff` 可原样回退；`V2O_PORT` 未设即旧行为 |
| **结论** | **PASS 带 P2×2 / P3×5，不阻塞下一环（qa）**；建议 P2-1、P2-2 在收口前顺手补（各约 1-3 行） |

**给 builder 的最小返修单（若 supervisor 要求合并返修）**：① `tests/selftest_p1_2_frontend.py:1445` 改 `re.sub(r"V2O_PORT\b", "", l)` 并删去 `V2OApp` 档；② 补一条 start.sh↔server.py 默认端口一致＋start.sh 无硬编码端口的静态断言。

---

# 返工复核（第二轮，code-reviewer 续首轮报告；**以上首轮正文一字未改**）

- Task: **DEVELOP-P1-8 返工复核**（针对首轮 P2-1／P2-2／P3-3 的返修）
- Commit: 工作树未提交，基线 `HEAD=f611824867568d7d23f2e0a7ca6e6c7427b8a0af`（与首轮同）
- Reviewer: code-reviewer（`opencode/muse-spark-1.3-contributor-free`，本窗口 subagent 直派，独立 Session）
- Result: **PASS**（首轮 P2×2 与 P3-3 全部关闭，证伪 6/6 有牙；业务代码零改动；无清单外夹带）
- 本轮取证目录：`/tmp/p18rev2/`（备份 10 文件＋sha256、`falsify2.py`、`brand_probe2.py`、`REPORT.before`）

## 一、修复真实性核实（不信自报，逐行读码）

### 1. P2-1：start.sh 牙口 4 条 —— **真实存在，粒度正确**

`tests/selftest_p1_2_contract.py:962-975`（实读行号，含 `:973` 的注释行过滤）：

| # | 行 | 断言（原文摘要） | 作用 |
|---|---|---|---|
| 1 | `:962-964` | `sh_defaults = re.findall(r"V2O_PORT:-(\d+)", sh_src)`；`len(...) == 1` | 端口默认值**恰一处** |
| 2 | `:965-967` | `sh_defaults == [str(fresh.PORT)]` | start.sh 默认值 **＝ server.py 真源默认值**（跨文件同步，双向） |
| 3 | `:968-970` | `sh_bare = sorted(set(re.findall(r"(?<!\d)(\d{4,5})(?!\d)", sh_src)))`；`sh_bare == sh_defaults` | 除该默认值外**无裸 4-5 位端口数字** |
| 4 | `:971-975` | 非注释行不得命中 `127\.0\.0\.1:\d` | URL 全走 `$PORT`，无硬编码 |

- 依赖前置齐全：`import re` 在 `tests/selftest_p1_2_contract.py:18`（**HEAD 既有**，非本轮新增）；`ROOT` 变量在同文件既有；`:952-961` 的 `fresh`（隔离 `V2O_PORT` 后重载）被 `:967` 复用，故 check 2 比的是**默认路径**而非环境值 —— 正确。
- **双向性成立**（我补的关键一问）：check 2 不依赖哪一侧被改，任一侧单独漂移即挂（见证伪 G1/G4）。

### 2. P2-2：撤销 `V2OApp` 豁免 —— **真实撤销，粒度收回到令牌级**

`tests/selftest_p1_2_frontend.py:1448-1450`：
```python
sh_left = [l.strip() for l in sh.splitlines()
           if "V2O" in re.sub(r"\bV2O_PORT\b", "", l)]
assert not sh_left, "start.sh 可见文案 V2O 残留（仅豁免 V2O_PORT 令牌）: %s" % sh_left
```
- 旧档 `and "V2OApp" not in l` **已删除**（对比首轮 `:1445`）；docstring `:1438-1439` 同步改写，明确"仅按令牌豁免 `V2O_PORT`（V2OApp 等子串不再放行）"。
- `import re` 在 `:13`，位置正确（`:1449` 使用）。
- 注：`menu_bar.py` / `status_cli.py` 两处检查仍保留 `"V2OApp" not in l`（`:1451-1455`）—— **这是对的**，那两个文件里 `V2OApp` 是真实类名（技术标识），豁免正当；`src/` 本轮零改动，我未要求动它。

### 3. P3-3：`\bV2O_PORT\b` 令牌边界 —— **真实生效**

`tests/selftest_p1_2_frontend.py:1449` 的 `\b…\b` 使 `V2O_PORT_EXTRA`、`V2O_PORTX`、`XV2O_PORT` **不再**被误豁免（`_`/`X` 是词字符，边界不成立）。我用独立探针逐例实证（下节 C3/C4/C9）。

## 二、实跑三套自测（我自己的 Session）

| 套件 | builder 自报 | 我实测 | rc | 备注 |
|---|---|---|---|---|
| `tests/selftest_p1_2_contract.py` | 517 | **517**（`SELFTEST ALL PASS（517 项断言）`，`^PASS` 行 517） | **0** | 新增 4 条已执行：输出 `:270-273` 四行 PASS |
| `tests/selftest_p1_2_frontend.py` | 167 | **167**（`^PASS` 行 167） | **0** | — |
| `tests/selftest_v26_presets.py` | 58 | **58**（`^PASS` 行 58） | **0** | — |

数字与 builder 自报**逐个吻合**。首轮 `:268-269` 两条钉子仍在位并通过。

## 三、我自己重做的反向证伪（6 条，逐条 /tmp 还原）

| 编号 | 改坏内容 | 跑什么 | rc | 咬住的断言（原文） | 判定 |
|---|---|---|---|---|---|
| **G1** | `start.sh:8` `V2O_PORT:-8899` → `:-8888`（server.py 不动） | contract | **1** | `FAIL 8 start.sh 默认值＝server.py 默认端口…<< ['8888']` ＋ `FAIL …无裸端口数字…<< ['8888','8899']` | **有牙**（P2-1 关） |
| **G2** | 塞 `echo "V2OApp 本机控制台"` | brand_checks / frontend | **1** / **1** | `start.sh 可见文案 V2O 残留（仅豁免 V2O_PORT 令牌）` | **有牙**（P2-2 关） |
| **G3** | 塞 `V2O_PORT_EXTRA=1` | brand_checks / frontend | **1** / **1** | 同上 | **有牙**（P3-3 关） |
| **G4（我补）** | **只改** `app/server.py:56` `PORT = 8899` → `8888`（start.sh 不动） | contract / frontend / v26 | **1** / 0 / 0 | `FAIL 8 未设 V2O_PORT 时默认端口＝8899…<< 8888` ＋ `FAIL 8 start.sh 默认值＝server.py 默认端口…<< ['8899']` | **有牙（双向成立）**——反方向同样被咬住，无需修法 |
| **G5** | `start.sh:39` `open …:$PORT/` → 硬编码 `127.0.0.1:8765`（＝首轮 F2 无牙项） | contract | **1** | `FAIL …无裸端口数字…<< ['8765','8899']` ＋ `FAIL …URL 全走 $PORT…<< ['  open "http://127.0.0.1:8765/"']` | **有牙**（首轮 P2-1 的具体缺口已补） |
| **G6** | 负控尝试：server.py＋start.sh＋注释同步改 8888 | contract | 1 | 只挂首轮钉子（`:960` 硬钉 `== 8899`）与我的替换不全 | **非缺陷**：见下「说明」 |

- 6 条全部从 `/tmp/p18rev2/` 备份 `cp` 还原，**未使用 `git checkout`**；每例后校验 7 文件 sha256，**全量逐字一致**（末次总校验 `逐字一致：yes`）。
- **G6 说明**（如实记，不计为缺陷）：`:960` 的 `== 8899` 是**有意钉死当前默认值**（改默认端口本应是一次需要动断言的显式动作），因此"把默认值改掉"必然挂这条钉值——这是设计意图，不是误报。真正需要防的"合法改动被无辜挂掉"已由现状 `rc=0` 本身证明（当前状态 517 全过）。
- 补充粒度探针（`/tmp/p18rev2/brand_probe2.py`，直接 import 真测试调 `brand_checks()`）**9/9 符合预期**：C2 `V2OApp` 咬住、C3 `V2O_PORT_EXTRA` 咬住、C4 `XV2O_PORT` 咬住、C8 同行混放咬住、C9 `V2O_PORTX` 咬住；C5「唯一 V2O 出现＝`$V2O_PORT`」与 C7「注释提 `V2O_PORT`」正确放行 —— 豁免**恰好只剩令牌级**，无过宽也无过严。

## 四、重建法核净增量（对账）

| 项 | 实测 | 判定 |
|---|---|---|
| `git diff --name-only` | **8 文件**（`README.md`/`README.en.md`/`app/server.py`/`app/start.sh`/`docs/troubleshooting.md`/`docs/usage.md`/`tests/selftest_p1_2_contract.py`/`tests/selftest_p1_2_frontend.py`） | 与卡面一致，**无清单外夹带** |
| `git diff --numstat` | 合计 **+69/−22**（首轮 +50/−21；返工净增 **+19/−1**，全部落在 2 个测试文件） | builder 自报「4 条牙口＋守卫改写」与实测相符 |
| 逐文件 | contract **27/3**（首轮 13/3，+14/0）、frontend **10/3**（首轮 5/2，+5/−1），其余 6 文件 numstat 与首轮**完全相同** | 一致 |
| **业务代码零改动** | `app/server.py`、`app/start.sh` sha256 与**首轮备份**（`/tmp/p18rev/`）**逐字相同** | **business 未被二次触碰** |
| `app/index.html`、`src/` | `git status --porcelain -- app/index.html src/` → **空** | 零改动 |
| 业务代码 AST | HEAD vs 工作树：函数 170/170，**同名函数体变了 0** | 零回归 |
| 计数口径 | 首轮已记 P3-4（卡面「约 +39/−20」vs 实测）；本轮实测 **+69/−22**，仍以实测为准 | 沿用 |

- 未触碰封存物（仓内无 `V1.10/V2.0` 目录）；`docs/pm/`、`docs/handoff/HANDOFF.md`、`008林粒粒AI编程/` 零改动。

## 五、红线核查（本轮）

| 红线 | 取证 | 结论 |
|---|---|---|
| 8765 外部进程零扰动 | `lsof -nP -iTCP:8765 -sTCP:LISTEN` → **PID 6586**，与本轮/首轮基线同一；**本轮未起任何服务**（未 bind 8765，未 kill，未请求） | PASS |
| 测试只用外置 tmp＋合成数据 | 本轮只跑三套自测（`contract` 走 `ThreadingHTTPServer(("127.0.0.1",0))` 临时端口）＋改坏/还原；跑完 `git status` 仍只有 8×`M`＋2 个 `??` | PASS |
| 未碰 secrets | 新 diff 段 secrets 正则唯一命中为中文注释「只按 token 边界精确摘除」的 `token` 字样（误报），无任何密钥 | PASS |
| 我自己的写盘范围 | 仅 `docs/review/P1-8-PORT-CODE-REVIEW.md` 追加本节 ＋ `/tmp/p18rev2/*` | PASS |
| 端口残留 | `lsof` 8899/8903/8904/8888 → **全空** | PASS |

## 六、返工复核裁定

| 项 | 首轮裁定 | 本轮核验 | 结果 |
|---|---|---|---|
| P2-1（start.sh 零牙口＋默认值两处漂移） | P2 | `:962-975` 4 条牙口，G1/G4/G5 三条证伪全咬住，跨文件**双向**同步成立 | **CLOSED** |
| P2-2（`V2OApp` 子串豁免＝本轮引入的放宽） | P2 | `:1448-1450` 撤销该档改令牌级，G2 咬住；探针 9/9 | **CLOSED** |
| P3-3（`V2O_PORT_EXTRA` 前缀过宽） | P3 | `\b…\b` 生效，G3 咬住，C4/C9 同咬 | **CLOSED** |
| P3-1（纯空格 `V2O_PORT` → 坏 URL） | P3 | 未在本轮返修范围，**残留** | 残留 P3 |
| P3-2（1-1023 解析通过、bind 抛裸 traceback） | P3 | 未在本轮返修范围，**残留** | 残留 P3 |
| P3-4（numstat 口径差） | P3 | 沿用，以实测为准（本轮 +69/−22） | 残留 P3 |
| P3-5（HANDOFF/PRODUCT_PLAN 的 8765 与 `PORT=` 旧变量名） | P3 | 未改（角色禁改，交 TM 收口） | 残留 P3 |
| **P3-6（本轮新增）** | — | 见下 | 新增 P3 |

**新增 P3-6：`:968-970`「无裸端口数字」检查偏宽，会打无辜的 4-5 位数**
- 证据（实跑）：`echo '# 见 issue 1234（与端口无关）' >> app/start.sh` → `FAIL 8 start.sh 除该默认值外无裸端口数字…<< ['1234','8899']`，contract **rc=1**（改动已 `/tmp` 还原，sha256 一致）。
- 原因：`re.findall(r"(?<!\d)(\d{4,5})(?!\d)", sh_src)` 作用在**整份文本**（含注释），凡是 4-5 位数字都必须恰等于端口默认值 —— 将来在 start.sh 注释里写年份/期号/版本号都会误挂；`:971-975` 的第 4 条只过滤了**整行注释**，行尾内联注释仍按代码判。
- 影响：无现网缺陷，属"过严的静态 lint"，会诱发后续有人为了过测而削弱它。
- 修法（建议，随下一轮或 backlog）：把检查限定到**与端口相关的行**，例如先取 `sh_code`（`:973` 已有该列表）再判数字，并只对含 `V2O_PORT:-`／`127.0.0.1` 的行做数字约束：
```python
sh_code = [l for l in sh_src.splitlines() if l.strip() and not l.strip().startswith("#")]
port_lines = [l for l in sh_code if "V2O_PORT:-" in l or "127.0.0.1" in l]
bad_nums = [n for l in port_lines for n in re.findall(r"(?<!\d)(\d{4,5})(?!\d)", l)
            if n != sh_defaults[0]] if sh_defaults else []
check("8 start.sh 端口相关行无额外裸端口数字", not bad_nums, bad_nums)
```

### 最终裁定：**PASS**

- 首轮两条 P2 与 P3-3 **全部关闭**且牙口经我独立复现（6 条证伪 6 条有牙，含我自补的「只改 server.py 一侧」双向用例）；三套自测 **517/167/58 rc=0**；业务代码本轮**零改动**（sha256 与首轮逐字同）；净增量 +19/−1 全在 2 个测试文件，**无清单外夹带**。
- 残留 P3×5：P3-1（start.sh 纯空格 URL）、P3-2（特权端口裸 traceback）、P3-4（numstat 口径）、P3-5（HANDOFF/PRODUCT_PLAN 旧 8765 与 `PORT=` 变量名，交 TM）、**P3-6（本轮新增：无裸端口数字检查偏宽）**。均不阻塞下一环（qa）。
- 仍未覆盖（承首轮，不因返工改变）：真机浏览器目检、Windows 侧入口、8899 被占用时的 start.sh 提示质量、qa 视角的完整端到端旅程。
