# USER_MODEL_OVERRIDE｜一句话切模型

| 角色 | 模型（精确ID，照抄执行） | 执行通道 | 调用方式 |
|---|---|---|---|
| task-manager | 开窗口时定 | 本窗口 | 本窗口subagent直派，按开窗口时模型执行 |
| supervisor | opencode-go/muse-spark-1.3-contributor | 本窗口 | 本窗口subagent直派 |
| builder | opencode-go/deepseek-v4.1-flash | 本窗口 | 本窗口subagent直派 |
| planner | codex/gpt-5.6-sol | codex | 派工基础设施走codex直调；CLI用短名`gpt-5.6-sol`：`codex exec -m "gpt-5.6-sol" --skip-git-repo-check "任务" </dev/null`；表内记全ID，禁本窗口代做 |
| code-reviewer | opencode/muse-spark-1.3-contributor-free | 本窗口 | 本窗口subagent直派 |
| qa | codex/gpt-5.6-luna | codex | 派工基础设施走codex直调；CLI用短名`gpt-5.6-luna`：`codex exec -m "gpt-5.6-luna" --skip-git-repo-check "任务" </dev/null`；表内记全ID，禁本窗口代做 |
| product-reviewer | codex/gpt-5.6-luna | codex | 派工基础设施走codex直调；CLI用短名`gpt-5.6-luna`：`codex exec -m "gpt-5.6-luna" --skip-git-repo-check "任务" </dev/null`；表内记全ID，禁本窗口代做 |
| experience-recorder | opencode/muse-spark-1.3-contributor-free | 本窗口 | 本窗口subagent直派 |
| neat-freak | opencode/muse-spark-1.3-contributor-free | 本窗口 | 本窗口subagent直派 |
| senior-expert | codex/gpt-5.6-sol | codex | 派工基础设施走codex直调；CLI用短名`gpt-5.6-sol`：`codex exec -m "gpt-5.6-sol" --skip-git-repo-check "任务" </dev/null`；表内记全ID，只接升级任务，禁本窗口代做 |
