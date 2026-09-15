"""S5-T01: Watch First — watchdog Observer real listen + Ready gate.

Implements STAGE5-PLAN S5-T01 only (V1.8 Stage 5, Watch First):
  - ``start_watch`` runs a real watchdog ``Observer`` (recursive) over the
    synthetic input root. Created / moved / modified events are debounced
    and then only *delivered* — the single delivery entry is
    ``stage2.candidate.discover`` (Stable gate + provisional UNIQUE + Case 13
    semantics stay inside ``discover``; this module adds no dedup of its own
    beyond the delivery-timing rule below).
  - Delivery timing (P1-1 fix, hardened by P1-FIX-1): an FS event never
    delivers by itself. It only (re-)arms a *trailing* quiet window for its
    path; the path is delivered only after ALL of these hold:
      ① the quiet window expired with no newer event for that path
         (``DEBOUNCE_S``),
      ② ``STABLE_ROUNDS`` size/mtime samples taken ``STABLE_PROBE_S`` apart
         are all identical (a single-sample "looks frozen" is not enough),
      ③ the file's mtime is at least ``DEBOUNCE_S + (STABLE_ROUNDS-1) *
         STABLE_PROBE_S`` old (a just-written file is never "finished"), and
      ④ the file is not held by another writer (``BUSY_CHECK``: POSIX 用
         独占 ``flock`` 探测，**Windows 用 CreateFileW 共享模式探测**，
         见 ``platform_win.file_is_busy``) — a busy file is treated as
         still being written.
    The verdict is then re-checked once more right before the delivery call
    (TOCTOU) and the delivery is dropped/re-armed if anything moved.
    Known limit (honest): a writer that pauses longer than the whole gate
    (~7s with the shipped defaults) is indistinguishable from a finished one
    by FS metadata alone; that case is caught later by the app-side
    "source snapshot changed → do not transcribe/publish" guard
    (``app/server.py``), and its root fix (supersede the stale run) is a
    Change-B item.
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

import platform_win  # noqa: E402  (Windows/POSIX 平台适配单点)

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

# ---- 投递门参数（P1-FIX-1：生产者的停顿绝不能被当成「写完」）-------------
# 取值理由：文件「写没写完」无法从 FS 元数据直接看出来，只能四道门串起来把
# 常见停顿挡在门外，再用「处理前复核 + 半截不发布」兜住剩下的小概率窗口：
#   - DEBOUNCE_S=3.0：最后一次事件后再静默 3s 才可能投递（同路径事件推后计时）。
#     实测本机 cp 462MB 仅 0.2s、分块 fsync 慢写 4.5s 全程最大间隙 <0.5s，
#     3s 静默窗足以覆盖常见的「分块写 + 偶发停顿」，又不会让用户等太久。
#   - STABLE_PROBE_S=2.0：相邻两次采样的间隔；2s 内还在变的文件一律判「仍在写」。
#   - STABLE_ROUNDS=3：必须连续 3 次采样（=2 个采样窗）都一致才算「写完」；
#     单次采样相等（旧版 0.5s 双采样）在同长停顿下会误判，故不再单窗定稿。
#   - BUSY_CHECK=True：投递前试占独占锁，被别的写方占着即「仍在写」，不投递。
#     注意：只有持锁写入的写方探得到；cp/浏览器下载多数不持锁，那种情况靠前
#     三条 + 处理前复核兜（见模块 docstring 的「known limit」）。
# 尾延迟 ≈ DEBOUNCE_S + (STABLE_ROUNDS-1)×STABLE_PROBE_S = 7s（换来不投半截）。
DEBOUNCE_S = 3.0
STABLE_PROBE_S = 2.0
STABLE_ROUNDS = 3
BUSY_CHECK = True

# Flusher poll tick: how often expired quiet windows are turned into deliveries.
FLUSH_TICK_S = 0.1


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
        stable_s: float = STABLE_PROBE_S,
        rounds: int = STABLE_ROUNDS,
        busy_check: bool = BUSY_CHECK,
    ):
        if rounds < 1:
            raise ValueError("rounds must be >= 1 (got %r)" % (rounds,))
        self.input_root = canonical(input_root)
        self.data_root = os.path.abspath(data_root)
        self.asr_profile_hash = asr_profile_hash
        self._deliver = on_deliver or _default_deliver
        self._debounce_s = debounce_s
        self._stable_s = stable_s
        self._rounds = int(rounds)
        self._busy_check = bool(busy_check)
        # ③ 最小文件年龄：刚写过的文件不许投递（见模块 docstring）
        self._min_age_s = float(debounce_s) + (self._rounds - 1) * float(stable_s)
        self._observer = Observer()
        self._ready = threading.Event()
        self._stopped = False
        self._lock = threading.Lock()
        # path -> earliest delivery time (trailing quiet window deadline)
        self._pending: dict[str, float] = {}
        self._flush_stop = threading.Event()
        self._flush_thread: threading.Thread | None = None
        self._deliveries: list[dict] = []
        self._handler = _Handler(self)

    # -- lifecycle ------------------------------------------------------
    def start(self) -> "Watcher":
        self._ensure_flusher()
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
        """Idempotent stop; returns真实结果（flusher 未在 10s 内收掉即 False）。"""
        self._flush_stop.set()
        with self._lock:
            already = self._stopped
            self._stopped = True
            self._pending.clear()
        with _REGISTRY_LOCK:
            if _REGISTRY.get(self.input_root) is self:
                _REGISTRY.pop(self.input_root, None)
        thread = self._flush_thread
        joined = True
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=10)
            joined = not thread.is_alive()
        if already:
            return joined
        try:
            self._observer.stop()
        except Exception:
            pass
        try:
            self._observer.join(timeout=10)
        except Exception:
            pass
        return joined

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
        """Arm (or re-arm) the trailing quiet window for one path.

        Nothing is delivered here: the path lands in ``_pending`` and a
        dedicated flusher thread delivers it once every gate in the module
        docstring holds. Same-path events inside the window only push the
        deadline out (trailing debounce).
        """
        if is_directory:
            return
        path_abs = canonical(path)
        if not is_video_path(path_abs):
            return
        if self._stopped:
            return
        self._ensure_flusher()
        with self._lock:
            self._pending[path_abs] = time.time() + self._debounce_s

    # -- trailing-debounce flusher --------------------------------------
    def _ensure_flusher(self) -> None:
        with self._lock:
            if self._stopped:
                return
            thread = self._flush_thread
            if thread is not None and thread.is_alive():
                return
            # 线程可重建（P3-1）：重建时给一个干净的停机信号，避免「生而即死」。
            self._flush_stop = threading.Event()
            self._flush_thread = threading.Thread(
                target=self._flush_loop, name="s5-deliver-debounce", daemon=True
            )
            self._flush_thread.start()

    def _flush_loop(self) -> None:
        while not self._flush_stop.wait(FLUSH_TICK_S):
            now = time.time()
            with self._lock:
                due = [p for p, at in self._pending.items() if now >= at]
            if not due:
                continue
            if self._flush_batch(due):
                return      # 期间收到停机信号：不再投递（P3-2）

    def _flush_batch(self, due: list) -> bool:
        """裁决一批到期路径并按判定投递；返回 True＝收到停机信号。

        P2-3：整批共享同一次采样节奏（N 轮采样只等 (N-1)×stable_s，不再每个
        文件各等一个窗），批量落盘时不会出现「最后一个文件多等几十秒」。
        """
        verdicts = self._verdicts(due)
        now = time.time()
        for path, (verdict, snap) in zip(due, verdicts):
            if self._flush_stop.is_set() or self._stopped:
                return True
            with self._lock:
                deadline = self._pending.get(path)
            if deadline is None:
                continue                    # 停机清理过
            if now < deadline:
                continue                    # 期间又有新事件（deadline 已推后）
            if verdict == "gone":
                self._forget(path)          # 消失：丢 pending，不投递
                continue
            if verdict != "stable":
                self._rearm(path)           # 仍在变/太新/被占用 → 回到等待态
                continue
            if self._changed_since(path, snap):
                self._rearm(path)           # TOCTOU：裁决后又变了 → 回到等待态
                continue
            self._forget(path)
            self._deliver_safe(path)
        return False

    def _verdicts(self, paths: list) -> list:
        """一批路径的稳定判定：[(verdict, snapshot), ...]。

        verdict ∈ stable（可投）｜unstable（还在变/采样被打断）｜gone（消失）｜
        too-new（刚写过，未过最小年龄）｜busy（被别的写方占着）。
        """
        columns = [self._sample_once(paths)]
        for _ in range(max(0, self._rounds - 1)):
            if self._flush_stop.wait(self._stable_s):
                break                       # 停机：本轮一律不判「可投」
            columns.append(self._sample_once(paths))
        now = time.time()
        out = []
        for idx, path in enumerate(paths):
            cols = [column[idx] for column in columns]
            if any(col is None for col in cols):
                out.append(("gone", None))
                continue
            if len(cols) < self._rounds or len(set(cols)) != 1:
                out.append(("unstable", cols[0]))
                continue
            snap = cols[0]
            if now - snap[1] / 1e9 < self._min_age_s:
                out.append(("too-new", snap))
                continue
            if self._busy_check and self._busy_reason(path) is not None:
                out.append(("busy", snap))
                continue
            out.append(("stable", snap))
        return out

    @staticmethod
    def _sample_once(paths: list) -> list:
        """每条路径一次 stat → [(size, mtime_ns) | None, ...]（一批共享一轮）。"""
        out = []
        for path in paths:
            try:
                st = os.stat(path)
            except OSError:
                out.append(None)
            else:
                out.append((int(st.st_size), int(st.st_mtime_ns)))
        return out

    def _busy_reason(self, path: str) -> str | None:
        """占用检测：试占独占锁；被别的写方占着 → 视作仍在写（P1-FIX-1）。

        说明：只有**持锁写入**的写方（本项目工具、部分下载器）探得到；`cp`／
        浏览器下载多数不持锁，那种情况靠静默窗 + 多轮采样 + 处理前复核兜。
        打不开（权限等）不算「占用」，交给正常路径处理。
        """
        try:
            fd = os.open(path, os.O_RDONLY)
        except OSError:
            return None
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            if platform_win.file_is_busy(path):
                return "locked"
        except platform_win.PlatformCapabilityMissing:
            # fail-closed：占用探测不可用时不许当作「未占用」，判 busy 不投递。
            return "probe-unavailable"
        return None

    def _changed_since(self, path: str, snap) -> bool:
        """TOCTOU：裁决用的快照与此刻不一致（含消失）→ 不得投递。"""
        if snap is None:
            return True
        try:
            st = os.stat(path)
        except OSError:
            return True
        return (int(st.st_size), int(st.st_mtime_ns)) != snap

    def stability(self, path: str) -> str:
        """单路径判定入口（测试/排查用；投递走 ``_flush_batch``）。"""
        return self._verdicts([canonical(path)])[0][0]

    def _forget(self, path: str) -> None:
        with self._lock:
            self._pending.pop(path, None)

    def _rearm(self, path: str) -> None:
        with self._lock:
            self._pending[path] = time.time() + self._debounce_s

    def _deliver_safe(self, path_abs: str) -> None:
        try:
            self.deliver(path_abs)
        except Exception as exc:  # never kill the delivery thread
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
    stable_s: float = STABLE_PROBE_S,
    rounds: int = STABLE_ROUNDS,
    busy_check: bool = BUSY_CHECK,
) -> Watcher:
    """Start a real watchdog watch. Requires the instance lock held.

    Delivery flows through ``discover`` (which asserts the lock); this
    function creates no lock of its own. ``stable_s``/``rounds``/``busy_check``
    default to the shipped投递门 (pinned by tests); production callers pass
    nothing and get the pinned defaults.
    """
    if not store.is_held(os.path.abspath(data_root)):
        raise store.LockNotHeldError(
            "start_watch requires the Single Instance lock held for %r"
            % (os.path.abspath(data_root),)
        )
    if not asr_profile_hash:
        raise ValueError("asr_profile_hash must be a non-empty frozen hash string")
    watcher = Watcher(input_root, data_root, asr_profile_hash, on_deliver,
                      debounce_s, stable_s, rounds, busy_check)
    return watcher.start()
