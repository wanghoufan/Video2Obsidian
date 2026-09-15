"""S2-T06: Single Instance + Startup Ordering subset + Root gate.

Implements STAGE2-PLAN S2-T06 only:
  - fcntl.flock LOCK_EX|LOCK_NB on <data_root>/data/.lock (§64). A second
    instance raises SecondInstanceError and the CLI exits 3 without touching
    the DB or writing anything (P0-7).
  - Startup subset in §62 order: Static Preflight -> Acquire Lock ->
    Open SQLite -> Volume Preflight -> Recovery Bootstrap. Later-stage
    background starters are absent by construction (this module defines no
    such entry points; the S2-T06 self-check asserts it structurally).
  - Root gate reuses stage1.probe_volume read-only (§61/§3.14): a non-local
    Input or Data root yields BLOCKED_UNSUPPORTED_ROOT_FOR_V1 (Case 11,
    CLI exit 2).
  - Static Preflight touches only config/path facts: no DB open, no repair,
    no job creation, no background activity (§63).

STOP EXPANSION: no transcription-engine invocations (count == 0), no
Stage3+ writes, no real filesystem listening.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stage1 import probe_volume  # noqa: E402  (read-only reuse, S2加法约束)

from stage2 import store  # noqa: E402

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_BLOCKED_ROOT = 2
EXIT_SECOND_INSTANCE = 3

BLOCK_CODE = "BLOCKED_UNSUPPORTED_ROOT_FOR_V1"

# FDs for locks held by this process: {abspath(data_root): file object}.
_FDS: dict[str, object] = {}


class SecondInstanceError(RuntimeError):
    """Raised when another instance already holds the data-root lock."""


class RootBlocked(RuntimeError):
    """Raised when a root is not a local filesystem (Case 11)."""

    def __init__(self, message: str, verdicts: dict):
        super().__init__(message)
        self.verdicts = verdicts


def check_static_preflight(data_root: str, input_root: str | None = None) -> dict:
    """Config/path checks only (§63). Never opens the DB, repairs, or starts
    anything: pure os.path facts + abspath normalization."""
    data_abs = os.path.abspath(data_root)
    input_abs = os.path.abspath(input_root) if input_root else data_abs
    problems = []
    if not os.path.isabs(data_abs):
        problems.append("data_root not absolute: %r" % (data_root,))
    if not os.path.isabs(input_abs):
        problems.append("input_root not absolute: %r" % (input_root,))
    verdict = "PASS" if not problems else "FAIL"
    return {
        "stage": "Static Preflight",
        "verdict": verdict,
        "problems": problems,
        "data_root": data_abs,
        "input_root": input_abs,
        "db_touched": False,
    }


def acquire(data_root: str) -> None:
    """Acquire the Single Instance lock (non-blocking). Idempotent."""
    key = os.path.abspath(data_root)
    if key in _FDS:
        return
    data_dir = os.path.join(key, "data")
    os.makedirs(data_dir, exist_ok=True)
    fh = open(os.path.join(key, store.LOCK_RELPATH), "a+b")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError):
        fh.close()
        raise SecondInstanceError("second instance: lock held for %r" % (key,))
    fh.write(("pid=%d\n" % (os.getpid(),)).encode("utf-8"))
    fh.flush()
    _FDS[key] = fh
    store.mark_held(key)


def release(data_root: str) -> None:
    key = os.path.abspath(data_root)
    fh = _FDS.pop(key, None)
    if fh is None:
        store.mark_released(key)
        return
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)  # type: ignore[attr-defined]
    finally:
        fh.close()  # type: ignore[attr-defined]
        store.mark_released(key)


def holds_lock(data_root: str) -> bool:
    return os.path.abspath(data_root) in _FDS


def gate_roots(input_root: str, data_root: str) -> dict:
    """Volume Preflight via stage1.probe_volume (read-only).

    Either side non-ALLOW -> RootBlocked(BLOCKED_UNSUPPORTED_ROOT_FOR_V1).
    """
    verdicts = {
        "input": probe_volume(input_root),
        "data": probe_volume(data_root),
    }
    blocked = {k: v for k, v in verdicts.items() if v.get("verdict") != "ALLOW"}
    if blocked:
        raise RootBlocked(
            "unsupported root for V1: %r" % (blocked,), verdicts,
        )
    return verdicts


def recovery_bootstrap(data_root: str) -> dict:
    """Post-lock bootstrap: integrity + schema presence + Stage2 gates.

    Read-only w.r.t. business semantics: verifies the central DB, never
    repairs artifacts, never creates jobs, never starts background work.
    """
    store.require_lock(data_root)
    con = store.open_db(data_root)
    try:
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        counts = store.table_counts(con)
        stage3 = store.assert_stage3_tables_empty(con)
        run_hist = store.assert_no_transcription_states(con)
    finally:
        con.close()
    if str(integrity).lower() != "ok":
        raise RuntimeError("central DB integrity_check failed: %r" % (integrity,))
    return {
        "stage": "Recovery Bootstrap",
        "integrity": "ok",
        "table_counts": counts,
        "stage3_empty": stage3,
        "run_status_histogram": run_hist,
    }


def startup(data_root: str, input_root: str | None = None) -> dict:
    """Run the §62 five-step subset in order. Returns a report dict."""
    pre = check_static_preflight(data_root, input_root)
    if pre["verdict"] != "PASS":
        raise ValueError("static preflight FAIL: %r" % (pre["problems"],))
    data_abs = pre["data_root"]
    input_abs = pre["input_root"]
    try:
        acquire(data_abs)
    except SecondInstanceError:
        raise
    db_path = store.init_db(data_abs)  # Open SQLite (creates skeleton once)
    verdicts = gate_roots(input_abs, data_abs)  # Volume Preflight (post-lock)
    boot = recovery_bootstrap(data_abs)  # Recovery Bootstrap (post-lock)
    return {
        "order": [
            "Static Preflight",
            "Acquire Single Instance Lock",
            "Open SQLite",
            "Volume Preflight",
            "Recovery Bootstrap",
        ],
        "static_preflight": pre,
        "lock": store.lock_path(data_abs),
        "db": db_path,
        "volumes": verdicts,
        "bootstrap": boot,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S2-T06 single-instance startup subset")
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--input-root", default=None)
    args = parser.parse_args(argv)
    try:
        pre = check_static_preflight(args.data_root, args.input_root)
        if pre["verdict"] != "PASS":
            print("FAIL %r" % (pre["problems"],), file=sys.stderr)
            return EXIT_FAIL
        report = startup(args.data_root, args.input_root)
    except SecondInstanceError as exc:
        print("SECOND_INSTANCE %s" % (exc,), file=sys.stderr)
        return EXIT_SECOND_INSTANCE
    except RootBlocked as exc:
        print("BLOCK %s %s" % (BLOCK_CODE, exc), file=sys.stderr)
        return EXIT_BLOCKED_ROOT
    except (ValueError, RuntimeError, OSError) as exc:
        print("FAIL %s" % (exc,), file=sys.stderr)
        return EXIT_FAIL
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
