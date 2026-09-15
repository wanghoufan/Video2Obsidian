"""Stage12: Menu Bar optional read-only status display (V1.8 S69).

Additive-only: read-only reuse of stage2 path helpers; never amends
src/stage1-11; never writes the central DB.

Contents:
  status_snapshot.py  S12-T01 read-only aggregate over state.db
  status_cli.py       S12-T02 stdlib status command + text menu
  menu_bar.py         S12-T03 optional display (try-import)
"""
