
# BUGS

## 测试结论

qa 回来了：**PASS，0 个缺陷**。

- 测试对象：自动轮询词汇区刷新隔离、手动刷新全量重载、任务进度轮询。
- 测试方式：`load_server()` 直测合成 tmp 词库；对 `app/index.html` 使用 DOM 桩式逻辑断言，未启动浏览器。
- 数据边界：仅使用外置 `mktemp` tmp 目录与合成词库；未触碰 `src`、用户真实目录、Obsidian 库。
- 结果：11 项检查 11 PASS、0 FAIL。

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| — | — | 否 | — | 无 | POLL-FIX 轻量复测 | 本轮未发现缺陷 |

## 已验证通过

- `load_server()` 直测外置 tmp 合成词库 GET 成功，返回词库数据正确。
- 自动轮询 `refresh(true)` 不调用 `loadVocab()`、`loadPresets()`、`loadVocabCandidates()` 三个词汇加载函数。
- 自动轮询逻辑不触碰词汇折叠、候选勾选、过滤输入等 DOM 状态，词汇区的折叠/勾选/过滤状态可保持。
- 手动按钮仍调用 `refresh(false)`，手动刷新继续全量重载三块词汇区。
- 任务进度轮询仍请求 `/api/status`，并调用 `renderTape()`、`renderRuns()`。
- 监听状态轮询仍请求 `/api/start` 并调用 `renderLock()`。
- `Promise.all([p1,p2])` 完成后恢复刷新按钮状态，轮询本身未被小修破坏。
- `setInterval(function(){refresh(true);},5000);` 仍存在。
- 增加词与删除词成功路径仍保留 `loadVocab()` 重载。

## 未执行 / 限制

- 未启动浏览器，未验证真实 DOM 交互、折叠状态在运行时跨轮询的视觉表现；本轮采用 DOM 桩式逻辑断言。

## Fix Attempt Fingerprint

- Task ID: poll-fix-qa-2026-09-13
- Root Cause Hypothesis: 本轮为轮询刷新隔离小修复测，无新增缺陷假设。
- Approach: `load_server()` 直测 handler；tmp 合成词库；静态提取 `refresh(autoPoll)` 进行自动/手动分支与进度链断言。
- Files Changed: 仅新增本报告。
- Verification: 11 项 PASS、0 FAIL。
- Failure Reason: 无。
- Difference From Previous Attempt: 聚焦确认自动轮询不再触发词汇区三块加载，同时保留手动刷新及增删词后的词汇重载。
