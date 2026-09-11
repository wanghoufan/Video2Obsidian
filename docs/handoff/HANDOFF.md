# HANDOFF｜开发暂停（2026-09-11）：V1.8全链+控制台V2.5收口，待续项3件

- Captured at（YYYY-MM-DD HH:MM）：2026-09-11 13:40
- Stage ID（本阶段叫什么）：开发暂停。V1.8 Stage0-12全CLOSED + 控制台PACKAGING-APP/V2/V2.1/V2.2/V2.3/V2.4/V2.5全PASS（supervisor终检PASS）+ 真机67单跑完（成功51/失败16）+ neat-freak收尾 done
- 剩 P0（没完的才列，多一条都不行）：
  - 无（全链PASS；未决全非阻塞，见下一步）
- 当前 Task（正干到哪）（累计打回 n/2，supervisor每次打回时TM同步更新）：暂停前状态——V2.5补修supervisor终检PASS 0/2；账本30行exit 0（rework=1计7行，均为code/qa打回口径，supervisor累计0/2，从未升级，senior从未启用）；服务venv跑在8765（V2.5新码，监听中）；git有未提交修改（V2.5代码+评审文档，无commit指令不碰）；neat三段已记（对齐全齐/残留只计数/未决非阻塞）
- 执行链/Session：本窗口subagent链（普通摘要续链）；builder同阶段续session规则生效中（用户定：同阶段续链不重启，换阶段才视情况重启）；模型真源=模板包USER_MODEL_OVERRIDE.md（主备制，项目本地表已作废只留声明）；实际执行主备：builder主用codebuddy无执行能力→备用本窗口subagent（已记账）；调用行/回执按真源:28执行
- 未闭环评审意见：无P0/P1；P2 backlog（V2.5余P2×4等，各报告内）
- docs 落盘清单：docs/pm STAGE0-12 PLAN 13份；src/stage1-12 + app/；docs/review（STAGE 13+FINAL 1+PACKAGING 6+UX 2）；docs/qa（STAGE 13+FINAL回归1+基准1+PACKAGING 6+UX-FIX 1）；docs/model 30行；README+截图已推GitHub（wanghoufan/Video2Obsidian，main到874aaf4；V2.5之后改动未推）
- 下一步（Next Single Action，按序）：
  1. 查失败16原因并修（真机67单中16失败，原因随重启丢内存，需重跑复现定位；行上重试按钮可用）。
  2. 任务列表“进行中置顶+完成自动跟随+状态筛选”（用户已定下单做）。
  3. V2.5之后改动commit+push（等用户指令，含分支名）。
- 人要拍什么板：无（开工后按上序直推；P0/P1直接修不问）。
- 收尾记一笔（neat-freak 2026-09-11）：对齐全齐（PLAN 13/src 12+app/review+qa成套/账本30行exit 0/作废声明与真源一致）；残留只计数（/tmp 452项、v2o-* 96项、$TMPDIR 6.2G，未删）；未决非阻塞（P2×4、U系列延续）；改了HANDOFF L15/L21两处，其余零改。
- 注意事项及规矩（本项目专用）：
  - 读盘顺序：AGENTS→角色卡→真源override表（模板包路径）→本HANDOFF→经验一句话→任务目标最后。
  - 派工贴调用行+收工贴回执（真源:28）；主备切换记HANDOFF+账本；主备均超限停派找人。
  - builder主用codebuddy本窗口无执行能力→自动切备用并记账（用户已知）。
  - 同阶段builder续session（task_id续接），不反复重启；换阶段才视情况重启。
  - 不可跳code-reviewer+qa+supervisor；小修跳planner/product须记一句原因；结论只落review/qa报告，HANDOFF只记状态。
  - 不push（commit需用户明确指令含分支名）；不碰secrets；测试只用外置目录+合成+stub，用户真实目录与ob库禁写（只读浏览例外）；坏例看exit码。
  - 服务：venv版python跑app/server.py，固定8765；监听状态重启丢失，路径localStorage回填。

## 恢复读盘（全体系唯一顺序，别乱）

1. AGENTS；2. 角色卡；3. 真源 `USER_MODEL_OVERRIDE.md`（模板包）；4. 本 HANDOFF；5. 根 `经验一句话.md`；6. 任务目标放最后。
冲突才扩大读。
