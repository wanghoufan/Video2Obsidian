"""S5-T01: Watch First — watchdog Observer real listen + Ready gate.

Implements STAGE5-PLAN S5-T01 only (V1.8 Stage 5, Watch First):
  - ``start_watch`` runs a real watchdog ``Observer`` (recursive) over the
    synthetic input root. Created / moved / modified events are debounced
    and then only *delivered* — the single delivery entry is
    ``stage2.candidate.discover`` (Stable gate + provisional UNIQUE + Case 13
    semantics stay inside ``discover``; this module adds no dedup of its own
    beyond a short post-write debounce window).
  - This module never writes business tables directly and never opens the DB
    itself: every DB effect flows through ``discover`` (which asserts the
    Single Instance lock). No lock of its own is created here.
  - ``wait_ready`` is the Watch First gate: scan must not start before it
    returns True (``scan.startup_scan`` enforces this structurally).
  - ``stop`` is idempotent and joins the Observer thread.

Additive-only: imports ``stage2`` read-only; never touches ``src/stage1-4``
files and never invokes any later-stage execution.
"""

from __future__ import annotations

import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stage2 import store  # noqa: E402  (read-only reuse, S5 additive rule)
from stage2.candidate import discover as _default_deliver  # noqa: E402

from watchdog.events import FileSystemEventHandler  # noqa: E402
from watchdog.observers import Observer  # noqa: E402

# Video suffix allowlist (case-insensitive). Non-listed suffixes are ignored.
VIDEO_SUFFIXES = frozenset({".mp4", ".mov", ".mkv", ".m4v", ".avi", ".webm"})


def canonical(path: str) -> str:
    """Canonical file identity inside Stage5: abspath + symlink resolution.

    Watchdog reports FS-resolved paths (e.g. /private/tmp for /tmp on
    macOS) while ``os.walk`` keeps the given root's spelling; without one
    spelling the three routes would mint different provisional keys for one
    file. The data root is never canonicalized here (Stage2 keys it by
    abspath); only input-root file paths go through this.
    """
    return os.path.realpath(os.path.abspath(path))

# Post-write debounce window: collapse created/modified bursts for one path.
# Repeat delivery stays legal (At Least Once); this only calms storms.
DEBOUNCE_S = 0.25


class WatcherNotReadyError(RuntimeError):
    """Raised when Scan is attempted before the Watcher is Ready."""


def is_video_path(path: str) -> bool:
    """Case-insensitive suffix check against VIDEO_SUFFIXES."""
    return os.path.splitext(path)[1].lower() in VIDEO_SUFFIXES


def iter_video_files(input_root: str, data_root: str | None = None) -> list:
    """Recursively enumerate video files under input_root, sorted.

    Skips anything nested under <data_root>/data when data_root is given,
    so a nested layout can never pick up central-DB side files.
    No dedup of its own: every matching file is listed every time.
    """
    root_abs = canonical(input_root)
    skip_prefix = None
    if data_root is not None:
        skip_prefix = canonical(
            os.path.join(os.path.abspath(data_root), "data")
        ) + os.sep
    out: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(root_abs):
        for name in filenames:
            full = os.path.join(dirpath, name)
            if skip_prefix is not None and canonical(full).startswith(
                skip_prefix
            ):
                continue
            if is_video_path(full):
                out.append(canonical(full))
    out.sort()
    return out


# Registry of started watchers by abspath input root (for the Scan gate).
_REGISTRY: dict[str, "Watcher"] = {}
_REGISTRY_LOCK = threading.Lock()


def find_ready(input_root: str) -> "Watcher | None":
    """Return the registered Ready watcher for input_root, if any."""
    with _REGISTRY_LOCK:
        watcher = _REGISTRY.get(canonical(input_root))
    if watcher is not None and watcher.is_ready():
        return watcher
    return None


class _Handler(FileSystemEventHandler):
    def __init__(self, watcher: "Watcher"):
        super().__init__()
        self._watcher = watcher

    def on_created(self, event):  # noqa: N802
        self._watcher._on_fs_event(event.src_path, getattr(event, "is_directory", False))

    def on_modified(self, event):  # noqa: N802
        self._watcher._on_fs_event(event.src_path, getattr(event, "is_directory", False))

    def on_moved(self, event):  # noqa: N802
        dest = getattr(event, "dest_path", None) or event.src_path
        self._watcher._on_fs_event(dest, getattr(event, "is_directory", False))


class Watcher:
    """A started watchdog watch over one synthetic input root."""

    def __init__(
        self,
        input_root: str,
        data_root: str,
        asr_profile_hash: str,
        on_deliver=None,
        debounce_s: float = DEBOUNCE_S,
    ):
        self.input_root = canonical(input_root)
        self.data_root = os.path.abspath(data_root)
        self.asr_profile_hash = asr_profile_hash
        self._deliver = on_deliver or _default_deliver
        self._debounce_s = debounce_s
        self._observer = Observer()
        self._ready = threading.Event()
        self._stopped = False
        self._lock = threading.Lock()
        self._last_seen: dict[str, float] = {}
        self._deliveries: list[dict] = []
        self._handler = _Handler(self)

    # -- lifecycle ------------------------------------------------------
    def start(self) -> "Watcher":
        self._observer.schedule(self._handler, self.input_root, recursive=True)
        self._observer.start()
        self._ready.set()
        with _REGISTRY_LOCK:
            _REGISTRY[self.input_root] = self
        return self

    def wait_ready(self, timeout: float = 20.0) -> bool:
        """Block until the Observer signals Ready (True) or timeout (False)."""
        return self._ready.wait(timeout=timeout)

    def is_ready(self) -> bool:
        return self._ready.is_set() and not self._stopped

    def stop(self) -> bool:
        """Idempotent stop: halt the Observer and join its thread."""
        with self._lock:
            if self._stopped:
                return True
            self._stopped = True
        with _REGISTRY_LOCK:
            if _REGISTRY.get(self.input_root) is self:
                _REGISTRY.pop(self.input_root, None)
        try:
            self._observer.stop()
        except Exception:
            pass
        try:
            self._observer.join(timeout=10)
        except Exception:
            pass
        return True

    # -- delivery -------------------------------------------------------
    def deliver(self, path: str) -> dict:
        """Deliver one path via the discover entry; record the outcome."""
        path_abs = canonical(path)
        result = self._deliver(path_abs, self.data_root, self.asr_profile_hash)
        record = {"path": path_abs, "result": result, "error": None, "at": time.time()}
        with self._lock:
            self._deliveries.append(record)
        return result

    def _on_fs_event(self, path: str, is_directory: bool) -> None:
        if is_directory:
            return
        path_abs = canonical(path)
        if not is_video_path(path_abs):
            return
        now = time.time()
        with self._lock:
            last = self._last_seen.get(path_abs, 0.0)
            if now - last < self._debounce_s:
                return
            self._last_seen[path_abs] = now
        try:
            self.deliver(path_abs)
        except Exception as exc:  # never kill the Observer thread
            with self._lock:
                self._deliveries.append(
                    {"path": path_abs, "result": None,
                     "error": repr(exc), "at": time.time()}
                )

    # -- inspection (for tests / startup chain) --------------------------
    def deliveries(self) -> list:
        with self._lock:
            return list(self._deliveries)

    def wait_for_path(self, path: str, timeout: float = 20.0) -> dict | None:
        """Poll recorded deliveries for path; return the record or None."""
        want = canonical(path)
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                for record in self._deliveries:
                    if record["path"] == want and record["error"] is None:
                        return record
            time.sleep(0.1)
        return None

    def delivery_count(self) -> int:
        with self._lock:
            return len(self._deliveries)


def start_watch(
    input_root: str,
    data_root: str,
    asr_profile_hash: str,
    on_deliver=None,
    debounce_s: float = DEBOUNCE_S,
) -> Watcher:
    """Start a real watchdog watch. Requires the instance lock held.

    Delivery flows through ``discover`` (which asserts the lock); this
    function creates no lock of its own.
    """
    if not store.is_held(os.path.abspath(data_root)):
        raise store.LockNotHeldError(
            "start_watch requires the Single Instance lock held for %r"
            % (os.path.abspath(data_root),)
        )
    if not asr_profile_hash:
        raise ValueError("asr_profile_hash must be a non-empty frozen hash string")
    watcher = Watcher(input_root, data_root, asr_profile_hash, on_deliver, debounce_s)
    return watcher.start()
