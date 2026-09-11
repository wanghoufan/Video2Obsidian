"""Stage11: LaunchAgent + Full Reliability + Fault Injection (V1.8 S69).

Additive-only: read-only reuse of stage1/stage2/stage5/stage10 public
entry points. This package never amends src/stage1-10, never touches
real LaunchAgents dirs, never performs a true reboot or power test,
and never starts a transcription engine (whisper increment is 0 on
every path; each public result carries asr_calls/whisper_calls = 0).

Contents:
  launch_plist.py  S11-T01 plist build/write/validate + test-dir drill
  agent_boot.py    S11-T02 cold boot via stage5 startup (11-step order)
  reliability.py   S11-T03 crash-matrix helpers (snapshot/relaunch/checks)
  fault_suite.py   S11-T04 full fault registry + runner
"""
