"""S5-T04: full startup assembly (11 ordered steps) + delivery workers.

Implements STAGE5-PLAN S5-T04 only:
  - ``run_startup`` reuses ``stage2.instance.startup`` for the first five
    steps (lock + DB shape stay Stage2's; no second lock file, no changed
    lock semantic — a second instance still surfaces SecondInstanceError,
    which this module never swallows), then continues:
    Start Watcher -> Confirm Watcher Ready -> Startup Scan
    -> Initial Reconciliation -> Start Workers -> RUNNING.
    The returned ``order`` array holds all 11 step names verbatim; any
    inversion or skip is a FAIL by plan.
  - The same "Start Workers" step also starts the periodic reconciliation
    host (P1-1 fix): a 30–60s补漏扫描 so a dropped/coalesced FS event can no
    longer strand a finished file. It shares ``initial_reconcile``'s口径.
  - ``DeliveryWorkers`` are delivery-only: bounded queue-fed threads whose
    only DB entry is the ``discover`` call per submitted path. They hold no
    other capability by construction (this module's only DB entries are
    ``discover`` and the ``reconcile_*`` calls inside ``reconcile.py``).
  - ``shutdown`` stops the periodic reconciler, then workers, then the
    watcher; it is idempotent.
  - A Ready timeout never leaves a half start: the watcher is stopped and a
    RuntimeError is raised instead of reporting RUNNING.

Additive-only: imports ``stage2`` + ``stage5.*`` read-only; never touches
``src/stage1-4`` files.
"""

from __future__ import annotations

import os
import queue
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stage2 import instance as _instance  # noqa: E402
from stage2.candidate import discover as _default_deliver  # noqa: E402

from stage5.reconcile import PeriodicReconciler, initial_reconcile  # noqa: E402
from stage5.scan import startup_scan  # noqa: E402
from stage5.watcher import Watcher, canonical, start_watch  # noqa: E402

STARTUP_ORDER = [
    "Static Preflight",
    "Acquire Single Instance Lock",
    "Open SQLite",
    "Volume Preflight",
    "Recovery Bootstrap",
    "Start Watcher",
    "Confirm Watcher Ready",
    "Startup Scan",
    "Initial Reconciliation",
    "Start Workers",
    "RUNNING",
]


class DeliveryWorkers:
    """Bounded queue-fed threads; each item is delivered via ``discover``."""

    def __init__(
        self,
        data_root: str,
        asr_profile_hash: str,
        on_deliver=None,
        count: int = 2,
    ):
        if count < 1 or count > 8:
            raise ValueError("worker count must be 1..8 (got %r)" % (count,))
        if not asr_profile_hash:
            raise ValueError("asr_profile_hash must be a non-empty frozen hash string")
        self.data_root = os.path.abspath(data_root)
        self.asr_profile_hash = asr_profile_hash
        self._deliver = on_deliver or _default_deliver
        self._count = count
        self._queue: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._started = False
        self._threads: list[threading.Thread] = []
        self._lock = threading.Lock()
        self._results: list[dict] = []

    def start(self) -> "DeliveryWorkers":
        with self._lock:
            if self._started:
                return self
            self._started = True
        for idx in range(self._count):
            thread = threading.Thread(
                target=self._loop, name="s5-delivery-%d" % idx, daemon=True
            )
            thread.start()
            self._threads.append(thread)
        return self

    def submit(self, path: str) -> None:
        if self._stop.is_set():
            raise RuntimeError("delivery workers are stopped; submit refused")
        self._queue.put(canonical(path))

    def pending(self) -> int:
        return self._queue.qsize()

    def results(self) -> list:
        with self._lock:
            return list(self._results)

    def _loop(self) -> None:
        while True:
            if self._stop.is_set() and self._queue.empty():
                return
            try:
                path = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                result = self._deliver(path, self.data_root, self.asr_profile_hash)
                record = {"path": path, "result": result,
                          "error": None, "at": time.time()}
            except Exception as exc:
                record = {"path": path, "result": None,
                          "error": repr(exc), "at": time.time()}
            with self._lock:
                self._results.append(record)
            self._queue.task_done()

    def stop(self) -> bool:
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=10)
        return True

    def stopped(self) -> bool:
        return self._stop.is_set()


def _fail_closed(
    watcher: Watcher | None,
    workers: DeliveryWorkers | None,
    reconciler: "PeriodicReconciler | None" = None,
) -> None:
    if reconciler is not None:
        try:
            reconciler.stop()
        except Exception:
            pass
    if workers is not None:
        try:
            workers.stop()
        except Exception:
            pass
    if watcher is not None:
        try:
            watcher.stop()
        except Exception:
            pass


def run_startup(
    data_root: str,
    input_root: str,
    asr_profile_hash: str,
    ready_timeout: float = 20.0,
    worker_count: int = 2,
) -> dict:
    """Run the full 11-step startup; return the RUNNING handle dict."""
    data_abs = os.path.abspath(data_root)
    input_abs = canonical(input_root)
    # Steps 1-5 (Stage2 owned; SecondInstanceError / RootBlocked propagate).
    first = _instance.startup(data_abs, input_abs)
    order = list(first["order"])
    watcher: Watcher | None = None
    workers: DeliveryWorkers | None = None
    reconciler: PeriodicReconciler | None = None
    try:
        # Step 6.
        watcher = start_watch(input_abs, data_abs, asr_profile_hash)
        order.append("Start Watcher")
        # Step 7.
        if not watcher.wait_ready(timeout=ready_timeout):
            raise RuntimeError(
                "watcher not Ready within %.1fs; refusing half start" % ready_timeout
            )
        order.append("Confirm Watcher Ready")
        # Step 8.
        scan_out = startup_scan(input_abs, data_abs, asr_profile_hash,
                                watcher=watcher)
        if any(item["error"] is not None for item in scan_out):
            raise RuntimeError(
                "startup scan delivery errors: %r"
                % ([i for i in scan_out if i["error"] is not None],)
            )
        order.append("Startup Scan")
        # Step 9.
        rec_out = initial_reconcile(input_abs, data_abs, asr_profile_hash)
        if any(
            item["deliver_error"] is not None for item in rec_out
        ):
            raise RuntimeError(
                "initial reconciliation errors: %r"
                % ([i for i in rec_out if i["deliver_error"] is not None],)
            )
        order.append("Initial Reconciliation")
        # Step 10.
        workers = DeliveryWorkers(data_abs, asr_profile_hash,
                                  count=worker_count).start()
        # 同一段内起周期兜底对账（P1-1）：FS 事件被合并/丢弃时靠它补回，
        # 扫描口径与 initial_reconcile 完全一致（幂等由 discover 保证）。
        reconciler = PeriodicReconciler(input_abs, data_abs,
                                        asr_profile_hash).start()
        order.append("Start Workers")
        # Step 11.
        order.append("RUNNING")
        if order != STARTUP_ORDER:
            raise AssertionError("startup order drift: %r" % (order,))
    except Exception:
        _fail_closed(watcher, workers, reconciler)
        raise
    return {
        "order": order,
        "running": True,
        "watcher": watcher,
        "workers": workers,
        "reconciler": reconciler,
        "scan": scan_out,
        "initial_reconciliation": rec_out,
        "instance": first,
        "data_root": data_abs,
        "input_root": input_abs,
    }


def shutdown(handle: dict | None) -> dict:
    """Stop reconciler, workers then the watcher. Idempotent; tolerates partial handles."""
    workers_stopped = True
    watcher_stopped = True
    reconciler_stopped = True
    if handle:
        reconciler = handle.get("reconciler")
        if reconciler is not None:
            try:
                reconciler.stop()
            except Exception:
                reconciler_stopped = False
        workers = handle.get("workers")
        if workers is not None:
            try:
                workers.stop()
            except Exception:
                workers_stopped = False
        watcher = handle.get("watcher")
        if watcher is not None:
            try:
                watcher.stop()
            except Exception:
                watcher_stopped = False
    return {
        "running": False,
        "workers_stopped": workers_stopped,
        "watcher_stopped": watcher_stopped,
        "reconciler_stopped": reconciler_stopped,
    }
