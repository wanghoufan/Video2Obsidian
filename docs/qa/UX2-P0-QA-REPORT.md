# BUGS｜UX2-P0 运行期复验（2026-09-11）

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| UX2-P0-1 67合成规模（总数67/可见67/limit20截断明示/失败行可点重试） | P0 | 否（业务逻辑PASS） | /tmp合成67（16失败+51成功）直调_S.handle_status，limit=200与20 | PASS | 运行期复验通过 | 独立脚本40断言全PASS EXIT=0；总数67可见67失败16截断True明示 |
| UX2-P0-2 清空代价与只清失败（dry_run代价行/只清失败成功不动/全清代价明示） | P0 | 否（业务逻辑PASS） | 同一合成库直调_handle_clear_post：dry_run→only_failed→full | PASS | 运行期复验通过 | dry_run将删DB67条+jobs67个+约134分钟；只清16留51；全清归零；源视频全程未动 |
| UX2-SELFTEST-HARNESS builder合成脚本未持锁 | P1 | 否（返工闭环） | python3 /tmp/ux2_selftest.py | CLOSED | 返工闭环已验 | 复跑SELFTEST ALL PASS EXIT=0；业务零改，只改脚本夹具 |

## Fix Attempt Fingerprint

- Task ID: UX2-P0-QA-2026-09-11
- Root Cause Hypothesis: builder自检脚本夹具缺`stage2.instance.acquire(data_root)`，`init_db`按P0-1锁门必抛`LockNotHeldError`；业务码`_handle_status/_handle_clear_post/_clear_plan/_est_retranscribe_minutes`本身无辜（QA持锁独立复验全过）。
- Approach: 只用外置/tmp+合成数据，直调函数（禁碰8765服务、用户真实目录与OB库）；先`python3 -m py_compile app/server.py`，再跑builder脚本看exit码，另写/tmp/ux2_qa_independent.py独立验证（持锁+67合成+坏例只看exit码）。
- Files Changed: 无（QA不改业务代码；只写本报告）。
- Verification:
  - `python3 -m py_compile app/server.py` → EXIT=0 PASS。
  - `python3 /tmp/ux2_selftest.py` → EXIT=1 FAIL，`stage2.store.LockNotHeldError: Stage2 DB write without Single Instance lock`（build_fixture:41→init_db:261→require_lock:93）。
  - QA独立脚本`/tmp/ux2_qa_independent.py` → ALL PASS EXIT=0（40断言）：est67=134/est16=32/est0=0；limit200时total67/shown67/done51/failed16/truncatedFalse/limit200；limit20时shown20/truncatedTrue/total67；dry_run preview db67/jobs67/succ51/fail16/only_failed16条+message含“将删DB 67条+jobs 67个”+重试提示+dry后库仍67；only_failed清16留51（runs/sources51/51、jobs51、kept_success51、undo非空）；全清归零；源视频67个两次均未动；坏例空体/缺input/坏JSON均400（只记exit码）。
  - 前端静态核对（app/index.html）：937行`limit=200`必带；442-471行列表头“共N（成功/失败/排队）当前显示M”+截断行“仅显示前M个”；488/512-513行失败行`data-retry`逐行重试；1136-1165行清空先dry_run代价行（DB N条+jobs M个+约X分钟+只清失败/全部清空二选一）。
- Failure Reason: builder脚本夹具未按`src/stage2/instance.py:79 acquire`持锁即`init_db`，与业务无关的harness bug；期望SELFTEST ALL PASS EXIT=0未达成。
- Difference From Previous Attempt: 首轮运行期复验；此前无UX2-P0 QA报告。
- Reverify 2026-09-11（返工闭环）: builder只改脚本（build_fixture加acquire、用后release+rmtree，业务零改）；QA独立重跑`python3 -m py_compile app/server.py`→EXIT=0，`python3 /tmp/ux2_selftest.py`→SELFTEST ALL PASS EXIT=0（31断言全PASS，源视频67未动）；UX2-SELFTEST-HARNESS转CLOSED。

## 未闭环（打回项）

- 无（UX2-SELFTEST-HARNESS已CLOSED；UX2-P0-1/P0-2均为PASS）。
