"""S5-T03: Reconcile Third —补漏対账 over FS/DB state.

Implements STAGE5-PLAN S5-T03 only:
  - ``initial_reconcile`` (startup chain) and ``periodic_reconcile``
    (repeatable补漏) share one semantic: enumerate the synthetic input
    root's live video files, deliver each through the ``discover`` entry
    (missed files are thereby补回), then converge the AUTO run of every
    delivered source through ``runs.reconcile_source``:
      - FAILED_RETRYABLE -> same run_id, retry_count+1, no new run;
      - NO_SPEECH_DETECTED -> the same terminal row back, nothing new;
      - QUEUED -> returned unchanged.
  - Files still inside the Stable gate (WAITING, no source yet) are left
    alone for a later round; swallowed deliveries (None) are skipped.
  - Reconciliation never advances execution itself: the only run mutation
    it can produce is the retry_count+1 defined above.
  - ``PeriodicReconciler`` (P1-1 fix) is the host that actually calls
    ``periodic_reconcile`` on an interval (30–60s) for as long as the app is
    listening: FS events that watchdog coalesces or drops can no longer
    strand a finished file. Its scanning口径 is exactly
    ``initial_reconcile``'s, so it adds no new persistence semantic;
    idempotency (no duplicate task / no re-transcription) rests on
    ``discover`` + ``get_or_create_auto_run`` as before.
  - 与 watcher 投递门的差异（如实记）：周期扫描不做「静默窗 + 多轮采样」判定，
    所以它**可能**扫到一个此刻仍在写的文件（P1-FIX-1 的同类窗口）。真正的
    兜底是 app 侧发布门（``app/server.py``：源快照不一致就不转写/不发布），
    这里不重复判定以免周期遍变慢。

Additive-only: imports ``stage2`` + ``stage5.watcher`` read-only; never
touches ``src/stage1-4`` files.
"""

from __future__ import annotations

import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stage2 import runs as _runs  # noqa: E402
from stage2.candidate import discover as _default_deliver  # noqa: E402

from stage5.watcher import canonical, iter_video_files  # noqa: E402

# Default补漏 period: long enough to be free, short enough that a dropped FS
# event surfaces within one human "did it pick it up?" beat.
RECONCILE_INTERVAL_S = 45.0

# stop() join 上界：超时即如实返回 False（P2-2），不再谎报已停。
STOP_TIMEOUT_S = 10.0


def _snapshot(path: str):
    """(size, mtime_ns) 或 None（取不到＝文件已不在）。"""
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (int(st.st_size), int(st.st_mtime_ns))


def _reconcile_once(
    input_root: str,
    data_root: str,
    asr_profile_hash: str,
    on_deliver,
    reason: str,
    skip_unchanged: dict | None = None,
) -> list:
    """One pass. ``skip_unchanged``（仅周期路用）＝ path -> (snapshot, source_id)：
    身份没变的文件本遍**不投递**（不读文件、不再做全文件哈希、不新增候选行），
    只用记忆里的 source 做一次 run 收敛；变了/新出现的才走完整投递。
    """
    if not asr_profile_hash:
        raise ValueError("asr_profile_hash must be a non-empty frozen hash string")
    input_abs = canonical(input_root)
    data_abs = os.path.abspath(data_root)
    if not os.path.isdir(input_abs):
        raise ValueError("input_root is not a directory: %r" % (input_abs,))
    items: list[dict] = []
    for full in iter_video_files(input_abs, data_abs):
        snap = _snapshot(full)
        remembered = skip_unchanged.get(full) if skip_unchanged is not None else None
        if (skip_unchanged is not None and remembered is not None
                and snap is not None and remembered[0] == snap):
            # P2-1：路径与身份都没变 → 只收敛 run（同一份对账语义），不重投。
            run = None
            converge_error = None
            try:
                run = _converge(remembered[1], asr_profile_hash, data_abs, reason)
            except Exception as exc:
                converge_error = "run-converge: %r" % (exc,)
            items.append(
                {"path": full, "delivered": None,
                 "deliver_error": converge_error, "run": run, "skipped": True}
            )
            continue
        try:
            delivered = on_deliver(full, data_abs, asr_profile_hash)
            deliver_error = None
        except Exception as exc:
            items.append(
                {"path": full, "delivered": None,
                 "deliver_error": repr(exc), "run": None, "skipped": False}
            )
            continue
        run = None
        source_id = None
        if isinstance(delivered, dict):
            source_id = delivered.get("source_id")
        if source_id:
            try:
                run = _converge(source_id, asr_profile_hash, data_abs, reason)
            except Exception as exc:
                items.append(
                    {"path": full, "delivered": delivered,
                     "deliver_error": "run-converge: %r" % (exc,), "run": None,
                     "skipped": False}
                )
                continue
        if skip_unchanged is not None:
            skip_unchanged[full] = (snap, source_id)
        items.append(
            {"path": full, "delivered": delivered,
             "deliver_error": deliver_error, "run": run, "skipped": False}
        )
    return items


def _converge(source_id, asr_profile_hash: str, data_abs: str, reason: str):
    """Converge one source's AUTO run (None source_id → nothing to do)."""
    if not source_id:
        return None
    return _runs.reconcile_source(source_id, asr_profile_hash, data_abs, reason)


def initial_reconcile(
    input_root: str,
    data_root: str,
    asr_profile_hash: str,
    on_deliver=None,
) -> list:
    """One reconciliation pass for the startup chain (see module docstring)."""
    return _reconcile_once(
        input_root, data_root, asr_profile_hash,
        on_deliver or _default_deliver, "initial-reconciliation",
    )


def periodic_reconcile(
    input_root: str,
    data_root: str,
    asr_profile_hash: str,
    on_deliver=None,
    skip_unchanged: dict | None = None,
) -> list:
    """Repeatable补漏 pass with identical semantics (see module docstring).

    ``skip_unchanged`` is the periodic-only cost shortcut (P2-1, see
    ``_reconcile_once``); ``initial_reconcile`` never passes it.
    """
    return _reconcile_once(
        input_root, data_root, asr_profile_hash,
        on_deliver or _default_deliver, "periodic-reconciliation",
        skip_unchanged=skip_unchanged,
    )


class PeriodicReconciler:
    """Background host that runs ``periodic_reconcile`` every ``interval_s``.

    The pass keeps ``initial_reconcile``'s semantics (same enumeration, same
    ``discover`` delivery, same run convergence), with one cost fix (P2-1):
    a file whose ``(size, mtime_ns)`` is unchanged since the previous pass is
    **not delivered again** — it would re-read/hash the whole file and add a
    candidate row every 45s forever. Such a path only converges its recorded
    run. A changed/new path still goes through the full delivery path.
    A failing pass is recorded (``last_error``) and never kills the thread —
    losing the backstop silently is exactly the failure this fixes.
    """

    def __init__(
        self,
        input_root: str,
        data_root: str,
        asr_profile_hash: str,
        interval_s: float = RECONCILE_INTERVAL_S,
        on_deliver=None,
    ):
        if not asr_profile_hash:
            raise ValueError("asr_profile_hash must be a non-empty frozen hash string")
        if interval_s <= 0:
            raise ValueError("interval_s must be > 0 (got %r)" % (interval_s,))
        self.input_root = canonical(input_root)
        self.data_root = os.path.abspath(data_root)
        self.asr_profile_hash = asr_profile_hash
        self.interval_s = float(interval_s)
        self.stop_timeout_s = STOP_TIMEOUT_S
        self._deliver = on_deliver or _default_deliver
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._started = False
        self._thread: threading.Thread | None = None
        self._passes = 0
        self._last_error: str | None = None
        self._last_items: list = []
        # path -> (snapshot, source_id)：上一遍已投递且身份未变的路径
        self._seen: dict[str, tuple] = {}

    def start(self) -> "PeriodicReconciler":
        with self._lock:
            if self._started:
                return self
            self._started = True
        self._thread = threading.Thread(
            target=self._loop, name="s5-periodic-reconcile", daemon=True
        )
        self._thread.start()
        return self

    def _loop(self) -> None:
        while not self._stop.wait(self.interval_s):
            self.run_once()

    def run_once(self) -> list:
        """One补漏 pass; errors are swallowed into ``last_error``."""
        try:
            items = periodic_reconcile(
                self.input_root, self.data_root, self.asr_profile_hash,
                self._deliver, skip_unchanged=self._seen,
            )
            error = None
            self._prune_seen()
        except Exception as exc:  # keep the backstop alive
            items, error = [], repr(exc)
        with self._lock:
            self._passes += 1
            self._last_error = error
            if error is None:
                self._last_items = items
        return items

    def _prune_seen(self) -> None:
        """丢掉已不在目录里的路径，避免 _seen 长跑后无界增长。"""
        gone = [p for p in self._seen if not os.path.exists(p)]
        for path in gone:
            self._seen.pop(path, None)

    def stop(self) -> bool:
        """Idempotent stop; return True 仅当线程真的收掉了（P2-2：不谎报）。"""
        self._stop.set()
        thread = self._thread
        if thread is None:
            return True
        if thread is threading.current_thread():
            return False
        thread.join(timeout=self.stop_timeout_s)
        return not thread.is_alive()

    def is_running(self) -> bool:
        """真实运行态（P2-2）：线程活着才算在跑，不看标志位。"""
        thread = self._thread
        return bool(thread is not None and thread.is_alive())

    def passes(self) -> int:
        with self._lock:
            return self._passes

    def last_error(self) -> str | None:
        with self._lock:
            return self._last_error

    def last_items(self) -> list:
        with self._lock:
            return list(self._last_items)
