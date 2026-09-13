
# BUGS

## 测试结论

qa 回来了：**PASS，0 个缺陷**。

- 测试对象：已导入词库折叠、编程/币圈/金融/用户四组归类、分组计数、过滤、删除计数更新、空态文案。
- 测试方式：按 `tests/selftest_v26_presets.py` 的 `load_server()` 方式直接 import `app/server.py` 并调用词库 handler；前端不启动浏览器，仅静态走读。
- 数据边界：使用外置 `mktemp` tmp 目录与合成四组词库；未触碰 `src`、用户真实目录、Obsidian 库。
- 结果：8 项检查 8 PASS、0 FAIL。

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| — | — | 否 | — | 无 | VOCAB-FOLD 轻量复测 | 本轮未发现缺陷 |

## 已验证通过

- 合成词库通过 handler 返回 4 个来源组：`programming`、`crypto`、`finance`、`user`，总数正确。
- 删除一条词库项成功，handler 返回 count=3；删除后再次 GET 计数更新且目标词消失。
- UI 存在已导入词库折叠节点、summary 总数节点及四组标签映射。
- UI 走读确认总数使用 `loadedVocabEntries.length`，分组计数使用 `items.length`。
- 过滤逻辑支持空值显示全部，并按错词或正词命中筛选。
- 过滤无命中时显示“暂无匹配词条”。
- 删除按钮绑定 `delVocab`，删除成功后调用 `loadVocab()`，计数会重新加载。
- 空词库 API 返回 `200 + ok`、count=0、空 vocab，前端具备空态基础数据。

## 未执行 / 限制

- 未启动浏览器，未验证真实 DOM 点击、折叠动画或输入交互；仅完成代码走读与 handler 直测。

## Fix Attempt Fingerprint

- Task ID: vocab-fold-qa-2026-09-13
- Root Cause Hypothesis: 本轮为纯前端增量复测，无新增缺陷假设。
- Approach: `load_server()` 直测 `_handle_vocab_get` / `_handle_vocab_del`；tmp 合成四组来源词库；静态检查前端分组、计数、过滤、空态和删除刷新逻辑。
- Files Changed: 仅新增本报告。
- Verification: 8 项 PASS、0 FAIL。
- Failure Reason: 无。
- Difference From Previous Attempt: 新增已导入词库折叠、四组归类计数、过滤与删除后计数/空态复测。
