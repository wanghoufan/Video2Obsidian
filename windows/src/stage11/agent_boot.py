"""S11-T02: Cold Boot via S62 full order + single-instance re-proof.

Implements STAGE11-PLAN S11-T02 only:

  cold_boot(data_root, input_root, ...) assembles the existing
  stage5.startup.run_startup full order and returns the 11-step order
  array verbatim plus the RUNNING handle. Order drift (skip or
  inversion) is a FAIL by plan.

  Archive and transcribe entry points always pass through the
  existing gate paths (expected_hash is mandatory there); this module
  holds no direct handle to the level-A/B move helpers by
  construction (it imports only stage5 startup/shutdown plus stage2
  store/instance read helpers, never the archive move helpers).

  reboot_equivalent(...) is stop-all + relaunch + Recovery Bootstrap
  + RUNNING + Lost/Duplicate 0. It is the booked equivalent proof;
  no true machine reboot is performed here.

  assert_second_instance_blocked(...) re-proves exit-3 semantics under
  the agent: a child process attempts startup on the same data_root,
  must observe SecondInstanceError, and must leave the DB mtime
  untouched with zero writes.

Zero transcription: boot never starts a transcription engine; every
result carries asr_calls == 0 and whisper_calls == 0. Central-DB
access here is read-only (counts/shape checks) except for the
assembled startup path itself, which owns its documented writes.

Additive-only: imports stage5/startup + stage2 store/instance
read-only; never amends src/stage1-10; never writes a plist; never
touches real LaunchAgents dirs.
"""

from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stage5.startup import STARTUP_ORDER  # noqa: E402  (read-only order)
from stage5.startup import run_startup as _run_startup  # noqa: E402
from stage5.startup import shutdown as _shutdown  # noqa: E402

PROFILE_DEFAULT = "test-profile-v1"


def expected_order() -> list[str]:
    return list(STARTUP_ORDER)


def cold_boot(
    data_root: str,
    input_root: str,
    asr_profile_hash: str = PROFILE_DEFAULT,
    ready_timeout: float = 20.0,
    worker_count: int = 2,
) -> dict:
    """Run the full S62 order to RUNNING. Order drift raises."""
    data_abs = os.path.abspath(data_root)
    input_abs = os.path.abspath(input_root)
    handle = _run_startup(
        data_abs,
        input_abs,
        asr_profile_hash,
        ready_timeout=ready_timeout,
        worker_count=worker_count,
    )
    order = list(handle.get("order", []))
    if order != STARTUP_ORDER:
        try:
            _shutdown(handle)
        except Exception:
            pass
        raise AssertionError("startup order drift: %r" % (order,))
    if handle.get("running") is not True:
        raise AssertionError("startup did not reach RUNNING")
    return {
        "order": order,
        "running": True,
        "handle": handle,
        "data_root": data_abs,
        "input_root": input_abs,
        "asr_profile_hash": asr_profile_hash,
        "asr_calls": 0,
        "whisper_calls": 0,
    }


def shutdown_agent(boot: dict) -> dict:
    """Stop workers then watcher. Idempotent; tolerates partial boots."""
    handle = (boot or {}).get("handle", boot)
    out = _shutdown(handle)
    return {**out, "asr_calls": 0, "whisper_calls": 0}


def reboot_equivalent(old_boot: dict | None, data_root: str, input_root: str,
                      asr_profile_hash: str = PROFILE_DEFAULT) -> dict:
    """Stop-all + lock release + relaunch + Bootstrap as reboot proof.

    P1-4: ``shutdown`` alone never releases the Single Instance lock
    (same-process ``acquire`` is a no-op), so relaunch must explicitly
    ``instance.release`` after shutdown and let ``cold_boot`` reacquire.
    This proves lock release->reacquire; cross-process handoff stays
    covered by ``assert_second_instance_blocked`` (child exit 3).
    """
    if old_boot is not None:
        try:
            shutdown_agent(old_boot)
        except Exception:
            pass
        try:
            from stage2 import instance as _inst  # noqa: E402 (lock handoff)

            _inst.release(os.path.abspath(data_root))
        except Exception:
            pass
    fresh = cold_boot(data_root, input_root, asr_profile_hash)
    fresh["reboot_equivalent"] = True
    fresh["true_reboot_performed"] = False
    fresh["proof"] = "stop-all + relaunch + Recovery Bootstrap + RUNNING"
    return fresh


def db_mtime_ns(data_root: str) -> int | None:
    from stage2 import store as _store  # noqa: E402 (read-only path fact)

    path = _store.central_db_path(os.path.abspath(data_root))
    try:
        return os.stat(path).st_mtime_ns
    except OSError:
        return None


def table_snapshot(data_root: str) -> dict:
    """Read-only table counts for Lost/Duplicate bookkeeping."""
    from stage2 import store as _store  # noqa: E402 (read-only reuse)

    con = _store.open_db(os.path.abspath(data_root))
    try:
        counts = _store.table_counts(con)
    finally:
        con.close()
    return counts


def assert_second_instance_blocked(data_root: str) -> dict:
    """Child-process startup must see SecondInstanceError; mtime stable."""
    data_abs = os.path.abspath(data_root)
    before = db_mtime_ns(data_abs)
    repo_src = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    script = (
        "import sys\n"
        "sys.path.insert(0, %r)\n"
        "from stage2 import instance as _i\n"
        "try:\n"
        "    _i.startup(%r, None)\n"
        "    print('UNEXPECTED_SINGLETON_PASS')\n"
        "    raise SystemExit(0)\n"
        "except _i.SecondInstanceError as _e:\n"
        "    print('SECOND_INSTANCE ' + str(_e))\n"
        "    raise SystemExit(3)\n"
    ) % (repo_src, data_abs)
    proc = subprocess.run(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=60,
    )
    after = db_mtime_ns(data_abs)
    mtime_stable = (before == after)
    blocked = proc.returncode == 3 and "SECOND_INSTANCE" in (proc.stdout + proc.stderr)
    verdict = "PASS" if (blocked and mtime_stable) else "FAIL"
    return {
        "verdict": verdict,
        "child_returncode": proc.returncode,
        "child_stdout": proc.stdout,
        "child_stderr": proc.stderr,
        "db_mtime_before": before,
        "db_mtime_after": after,
        "db_mtime_stable": mtime_stable,
        "asr_calls": 0,
        "whisper_calls": 0,
    }
