
# PRODUCT BACKLOG

| Item | Task | Priority | Stage P0 Blocking? | Source | Status |
|---|---|---:|---|---|---|
| U-1 | §5 B档Peak誊写：3411.8→改为3429.7（或注明chunk轮另计） | P2 | 否 | STAGE0-CODE-REVIEW P2-1 / QA P2-1 | OPEN |
| U-2 | §4 T09-C3 Peak誊写：3344.6→改为3346.3（差1.7MB，疑抄T09-C4错行） | P2 | 否 | QA P2-4 | OPEN |
| U-3 | tokenizer分表计数补独立artifact（360/244/336/940tok输出JSON落results/） | P2 | 否 | CODE P2-2 / QA P2-2 PARTIAL | OPEN |
| U-4 | 报告加一句/tmp→results/路径映射说明＋清T08-B-ch900.wav（41MB残留） | P2 | 否 | CODE P2-3 / QA P2-3 | OPEN |
| U-5 | 补测缺口（素材到位后脚本重跑）：真30/60min单文件＋B全网格剩4格＋C WordON | P2 | 否（降级GO后补） | REPORT §10-D/§13 + QA §8 | OPEN |
| U-6 | ov2单次+6%复测确认（Stage1用overlap=2s后复测一次） | P3 | 否 | CODE P3-1 / QA §7 | OPEN |
| U-7 | D6确认正式RTF红线（报告Q4“<0.2为优”系自设，计划书无数字红线） | P3 | 否 | CODE P3-2 | OPEN |

> Product / Visual 问题是否立即修，由 Task Manager 判定是否阻塞 P0（P0 定义见 PLAN.template.md Stage P0 节）。

## 产品验收结论：PASS（报告收，Gate=NOGO待D6一句话降级转GO）

- 被验：`docs/qa/TECHNICAL_BENCHMARK_REPORT.md`＋`docs/review/STAGE0-CODE-REVIEW.md`（PASS）＋`docs/qa/STAGE0-QA-REPORT.md`（PASS）。
- 用户只关心三句话：能不能进Stage1——能，选选项一降级转GO；缺什么——真30/60min单文件＋上面U-1~U-5；补多久——笔误/清理/artifact<15min人工，补测脚本重跑<30min机器时间（等素材的人时间另计）。
- 打回条件三条均未触发：无跳项、无含糊默认值、无只喊通过（18轮全数据＋2项诚实FAIL）。

## 1. Gate 13问逐项（对照PLAN附录A，无跳项）

| Gate（附录A） | 报告§12 | 用户可读结论 |
|---|---|---|
| 1 MLX可运行 | 1 PASS | 19轮全OK，中文检出 |
| 2 revision锁定 | 2 PASS | repo+revision+路径+1.5G大小齐全 |
| 3 依赖冻结可复现 | 3 PASS | freeze 41行，无latest |
| 4a 5min RTF | 4 PASS | 0.1311，远优于实时 |
| 4b 30min RTF | 5 FAIL（覆盖缺口） | 无真30min单文件，21.7min代理0.0785已记 |
| 4c 60min无crash | 6 FAIL（覆盖缺口，严格口径） | 无真60min单文件；21.7min通过＋66min/6文件累计零异常 |
| 5 Peak预算内 | 7 PASS | 最坏3429.7MB<24GB（<15%） |
| 6 Load可接受 | 8 PASS | 0.7–1.5s冷启可接受 |
| 7 Word差＋默认 | 9 PASS | +39–46%，默认OFF |
| 8 VAD结论误删=0 | 10 PASS | 保守阈值方向，零过滤零误删 |
| 9 Pipe/Temp默认稳定侧 | 11 PASS | 默认Temp（可恢复性），哈希逐字节一致 |
| 10 Chunk数据＋推荐 | 12 PASS | 部分网格＋推荐10min/2s，缺口已声明 |
| 11 Prompt真实Capacity | 13 PASS | 223tok实测，350假设证伪，装配顺序修正 |
| 12 Blocking清零/有FINDING | 14 PASS | NONE，无悬空阻断 |

## 2. 输出物清单（对照附录C 13节，齐全）

- 环境§1✓／版本冻结§2✓／revision§2✓／视频信息＋7场景矩阵§3✓／原始结果18轮§4✓／汇总§5✓／RTF分析§6✓／内存分析§7✓／Word对比§8.1✓／Pipe-Temp对比§8.2✓／VAD对比§8.3✓／Chunk建议§8.4✓／Prompt建议§8.5✓／异常A-E§10✓／Blocking NONE§11✓／推荐配置§9✓／PASS-FAIL§12✓／GO-NOGO§13✓。无“只输出测试通过”。

## 3. 推荐配置可直接指导Stage1：是

- §9八行可直接粘贴为Stage1 Profile输入：model+revision／temp-wav 16k mono／word默认OFF（ON成本×1.4–1.5）／nst 0.6／VAD thr 0.3–0.5 advisory／chunk 10min overlap 2s／prompt预算200tok＋Global→Topic→Creator顺序／worker=1。只出值未回写架构，合规。

## 4. NOGO判据诚实合理＋两条路齐全：是

- NOGO仅因Q5/Q6数据集时长缺口，技术基线全绿；未拿拼接冒充长稳（R3合规），缺口§10-D/§12/§13三处一致声明，QA§8确认无掩盖。
- 选项一（建议）：接受降级，以21.7min最长单文件＋66min累计零异常为据转GO，拿到真素材后补测。选项二：补测后再GO，脚本可直接重跑。

## 5. D6拍板点（一句话）

> D6请定：接受“21.7min＋66min累计零异常”降级证据转GO进Stage1（后补真30/60min），还是补测后再GO？建议选前者。

## 差哪清单（用户版：缺什么、补多久）

- 数字笔误2处（U-1/U-2）：结论不受影响，改两行即好，<5min。
- tokenizer独立artifact缺（U-3）：refs半侧QA已文件系统验证闭环，只剩tokenizer计数JSON后补，不卡Gate。
- 路径一句话＋wav清理（U-4）：neat-freak顺手，<5min。
- 覆盖缺口（U-5）：真30/60min单文件（等人给素材）＋B全网格剩4格＋C WordON；脚本不变重跑，机器时间<30min（18轮已跑总量约15min量级为据）。
- 观察2项（U-6/U-7）：Stage1复测＋D6确认RTF红线，不阻进Stage1。
