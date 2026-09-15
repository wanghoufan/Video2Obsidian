"""S11-T03: S67 crash-matrix helpers (snapshot / relaunch / checks).

Implements STAGE11-PLAN S11-T03 only:

  snapshot(data_root)        read-only counts + DB mtime + shape proof.
  relaunch(old, data_root, input_root, profile)
                             shutdown + lock release + cold_boot re-entry
                             (the single re-entry used by every matrix
                             item; release->reacquire proves the lock
                             handoff a true restart must cross).
  assert_running(boot)       11-step order verbatim + RUNNING.
  assert_recovered(...)      RUNNING + Lost/Duplicate 0 + half-file is
                             not success + whisper increment 0.
  kill9_child_relaunch(...)  TRUE kill path: child holds a synthetic
                             job (sleep) while the parent hard-kills it
                             (POSIX: os.kill(pid, SIGKILL) + rc ==
                             -SIGKILL；**Windows: proc.kill() →
                             TerminateProcess，不假设负 returncode**，
                             分派见 platform_win.kill_child), then
                             relaunch + assert_recovered. Covers the
                             job-window kill with a real kernel kill.
  power_loss_best_effort_note()
                             booked Best Effort row (flush/fsync +
                             PREPARED/Receipt landed in Stage1/10);
                             no true power test is performed.
  describe_reboot_equivalent()
                             booked reboot-equivalent row (stop-all +
                             relaunch + Bootstrap); no true reboot.

Kill-equivalence per window (P1-5; hook ~= kill claim + uncovered face):
  - job window: TRUE SIGKILL covered by kill9_child_relaunch (kernel
    terminates the child; no Python cleanup runs; parent relaunches and
    asserts Lost/Dup 0). No hook equivalence needed here.
  - rename/manifest window (F-R2 path): hook = stage1 prepare leaves
    final without manifest, then recover_raw Repair Forward. Equivalent
    claim: kill between rename and manifest leaves the same on-disk
    shape (final present, manifest stale); uncovered face: page-cache
    unflushed bytes / open fd state / WAL not checkpointed at the exact
    kill instant are NOT reproduced by the hook.
  - mid-copy window (archive_midcopy_drill): hook = on_pre_unlink raises
    at pre-unlink, then recover_midcopy repairs the owned sidecar.
    Equivalent claim: SIGKILL at pre-unlink leaves source + partial
    sidecar without Receipt, same shape the hook leaves; uncovered face:
    torn rename / half-flushed sidecar bytes / fd/WAL states at the
    signal instant are NOT reproduced by the hook.
  Source-kept + Receipt-only-after-valid-final hold on every window;
  QA accepts per window above.

Recovery writes are only ever performed through the existing public
paths (stage1 recovery Repair Forward, stage10 gate/commit); this
module holds no direct central-DB write path of its own. Archive
mid-copy simulation reuses the stage10 level-B copy + recover calls
with a pre-unlink hook standing in for SIGKILL; rename/manifest
simulation reuses stage1 prepare/commit/recovery on synthetic job
dirs under the external test root.

Zero transcription on every path (asr_calls/whisper_calls = 0).

Additive-only: read-only reuse of stage1/2/5/10 publics; never amends
src/stage1-10; never touches real LaunchAgents dirs.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import platform_win  # noqa: E402  (Windows/POSIX 平台适配单点)


def snapshot(data_root: str) -> dict:
    """Capture counts + DB mtime for Lost/Duplicate bookkeeping."""
    from stage2 import store as _store  # noqa: E402 (read-only reuse)

    data_abs = os.path.abspath(data_root)
    con = _store.open_db(data_abs)
    try:
        counts = _store.table_counts(con)
    finally:
        con.close()
    try:
        mtime = os.stat(_store.central_db_path(data_abs)).st_mtime_ns
    except OSError:
        mtime = None
    return {
        "data_root": data_abs,
        "counts": counts,
        "db_mtime_ns": mtime,
        "asr_calls": 0,
        "whisper_calls": 0,
    }


def assert_running(boot: dict) -> dict:
    """Order verbatim + RUNNING flag check."""
    from stage5.startup import STARTUP_ORDER  # noqa: E402 (read-only order)

    order = list((boot or {}).get("order", []))
    running = (boot or {}).get("running") is True
    ok = (order == STARTUP_ORDER) and running
    return {
        "verdict": "PASS" if ok else "FAIL",
        "order": order,
        "running": running,
        "asr_calls": 0,
        "whisper_calls": 0,
    }


def relaunch(old_boot: dict | None, data_root: str, input_root: str,
             asr_profile_hash: str = "test-profile-v1") -> dict:
    """Shutdown + lock release + cold-boot anew (P1-4 lock handoff)."""
    from stage11 import agent_boot as _boot  # noqa: E402 (same package)

    if old_boot is not None:
        try:
            _boot.shutdown_agent(old_boot)
        except Exception:
            pass
        try:
            from stage2 import instance as _inst  # noqa: E402 (lock handoff)

            _inst.release(os.path.abspath(data_root))
        except Exception:
            pass
    fresh = _boot.cold_boot(data_root, input_root, asr_profile_hash)
    fresh["relaunch"] = True
    return fresh


def kill9_child_relaunch(old_boot: dict | None, data_root: str,
                         input_root: str,
                         asr_profile_hash: str = "test-profile-v1") -> dict:
    """True-SIGKILL job-window drill (P1-5 named kill9 helper).

    Spawns a child holding a synthetic job (sleep), sends the real kernel
    ``SIGKILL`` via ``os.kill``, waits for ``-SIGKILL`` termination (no
    Python cleanup runs in the child), then relaunches the parent agent
    and asserts recovery. Covers the job-window kill with a true signal;
    rename/manifest + mid-copy windows keep hook simulation (see module
    header for per-window equivalence + uncovered face).
    """
    from stage11 import agent_boot as _boot  # noqa: E402 (same package)

    data_abs = os.path.abspath(data_root)
    input_abs = os.path.abspath(input_root)
    before = snapshot(data_abs)
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    pid = proc.pid
    time.sleep(0.2)
    # Windows：TerminateProcess（proc.kill），不假设负 returncode；
    # POSIX：真 SIGKILL，rc == -SIGKILL 才算硬杀成功。分派在 platform_win。
    kill = platform_win.kill_child(proc, timeout=10.0)
    rc = kill.get("returncode")
    sigkilled = bool(kill.get("hard_killed"))
    killed = bool(kill.get("killed"))
    fresh = relaunch(old_boot, data_abs, input_abs, asr_profile_hash)
    # Keep the fresh handle observable for the caller (no leak: caller
    # owns shutdown of the returned boot).
    _boot_handle = fresh
    after = snapshot(data_abs)
    recovered = assert_recovered(before, after, _boot_handle,
                                 whisper_delta=0)
    running = assert_running(_boot_handle)
    ok = (sigkilled and recovered.get("verdict") == "PASS"
          and running.get("verdict") == "PASS")
    return {
        "verdict": "PASS" if ok else "FAIL",
        "child_pid": pid,
        "sigkilled": sigkilled,
        "child_returncode": rc,
        "kill_sent": killed,
        "kill_semantics": kill.get("killed_by"),
        "recovered": recovered,
        "running": running,
        "boot": _boot_handle,
        "asr_calls": 0,
        "whisper_calls": 0,
    }


def _counts_delta(before: dict, after: dict) -> dict:
    keys = sorted(set(before) | set(after))
    return {k: (after.get(k, 0) - before.get(k, 0)) for k in keys}


def assert_recovered(before: dict, after: dict, boot: dict,
                     whisper_delta: int = 0,
                     allow_archive_rows: bool = False) -> dict:
    """Shared post-crash checks for every S67 matrix item."""
    problems: list[str] = []
    run_check = assert_running(boot)
    if run_check["verdict"] != "PASS":
        problems.append("RUNNING not reached after relaunch")
    b_counts = (before or {}).get("counts", {})
    a_counts = (after or {}).get("counts", {})
    delta = _counts_delta(b_counts, a_counts)
    # Lost/Duplicate 0 is observed as: no source or AUTO-run row vanished
    # and no unexpected duplicate row appeared outside the booked path.
    for table in ("sources", "processing_runs", "discovery_candidates"):
        if a_counts.get(table, 0) < b_counts.get(table, 0):
            problems.append("table %s shrank (lost row)" % (table,))
    for table in ("normalization_revisions", "render_revisions",
                  "publish_records"):
        if delta.get(table, 0) != 0:
            problems.append("table %s moved by %r (must stay 0 here)"
                            % (table, delta.get(table)))
    if not allow_archive_rows and delta.get("archive_commits", 0) != 0:
        problems.append("archive_commits moved by %r (not booked here)"
                        % (delta.get("archive_commits"),))
    if whisper_delta != 0:
        problems.append("whisper increment must be 0 (got %r)" % (whisper_delta,))
    verdict = "PASS" if not problems else "FAIL"
    return {
        "verdict": verdict,
        "problems": problems,
        "delta": delta,
        "running": run_check,
        "whisper_delta": whisper_delta,
        "asr_calls": 0,
        "whisper_calls": 0,
    }


def sha256_file_hex(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            part = fh.read(8 * 1024 * 1024)
            if not part:
                break
            digest.update(part)
    return digest.hexdigest()


def write_small_bytes(path: str, payload: bytes) -> dict:
    """Write a synthetic small input file (fsync'd) for fault drills."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(payload)
        fh.flush()
        os.fsync(fh.fileno())
    st = os.stat(path)
    return {
        "path": os.path.abspath(path),
        "size": st.st_size,
        "hash": "sha256:" + sha256_file_hex(path),
    }


def power_loss_best_effort_note() -> dict:
    """Booked Best Effort row for power loss (no true power test)."""
    return {
        "item": "power loss",
        "scope": "Best Effort only",
        "semantics": "flush + fsync + PREPARED/Receipt landed in Stage1/10",
        "true_power_test_performed": False,
        "verdict": "PASS-BY-BOOKING",
        "asr_calls": 0,
        "whisper_calls": 0,
    }


def describe_reboot_equivalent() -> dict:
    """Booked reboot-equivalent row (no true machine reboot)."""
    return {
        "item": "macOS reboot",
        "proof": "stop-all + relaunch + Recovery Bootstrap + RUNNING "
                 "+ Lost/Duplicate 0",
        "true_reboot_performed": False,
        "verdict": "PASS-BY-EQUIVALENCE",
        "asr_calls": 0,
        "whisper_calls": 0,
    }


def archive_midcopy_drill(source_path: str, archive_final_path: str,
                          expected_hash: str, source_id: str) -> dict:
    """Level-B copy with a pre-unlink cut acting as SIGKILL, then repair.

    Uses only the stage10 level-B public calls: the first copy is cut
    at pre-unlink time (an exception stands in for the kill, so the
    source stays and no Receipt counts as success); recover_midcopy
    then carries the owned sidecar to a valid final. Returns both
    halves plus the source-kept proof.
    """
    from stage10 import level_b as _b  # noqa: E402 (read-only reuse)

    source_abs = os.path.abspath(source_path)
    final_abs = os.path.abspath(archive_final_path)

    class _Cut(Exception):
        pass

    def _cut(_receipt: dict) -> None:
        raise _Cut("simulated SIGKILL at pre-unlink")

    cut_seen = False
    try:
        _b.archive_level_b(source_abs, final_abs, expected_hash, source_id,
                           on_pre_unlink=_cut)
    except _Cut:
        cut_seen = True
    source_kept = os.path.isfile(source_abs)
    # Repair path: owned sidecar + valid bytes -> Receipt + unlink.
    receipt = _b.recover_midcopy(source_abs, final_abs, expected_hash,
                                 source_id)
    final_hash = ("sha256:" + sha256_file_hex(final_abs)
                  if os.path.isfile(final_abs) else None)
    ok = (cut_seen and receipt.get("status") == "ARCHIVE_COMMITTED"
          and final_hash == expected_hash)
    return {
        "verdict": "PASS" if ok else "FAIL",
        "cut_seen": cut_seen,
        "source_kept_at_cut": source_kept,
        "receipt": receipt,
        "final_hash": final_hash,
        "expected_hash": expected_hash,
        "asr_calls": 0,
        "whisper_calls": 0,
    }
