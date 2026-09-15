"""S12-T03: optional menu-bar display over the S12-T01 snapshot.

Implements STAGE12-PLAN S12-T03 only:

  Top-level try-import keeps this module importable with or without
  the optional rumps package (RUMPS_AVAILABLE flag).
  With rumps: the title line shows the same three numbers as
  collect() (row totals for sources / processing_runs plus
  error_count) and the drop-down holds the same data as read-only
  text rows. The only actions are Refresh (read the snapshot again)
  and Quit (leave the menu).
  Without rumps: main() prints the stdlib CLI path and exits 0;
  this module fetches nothing and alters nothing.

Windows（本批改造）：rumps 是 macOS 托盘库，**Windows 端永不 import 它**
（import 期即短路，不会崩）。MVP 不做托盘（方案 §2「启动／自启」行 +
§7①），main() 在 Windows 上打印人话说明并 exit 0，不假装托盘可用。

Stdlib + optional rumps only. Additive-only: read-only reuse of
status_snapshot.collect; never amends src/stage1-11; never writes
the central DB.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import platform_win  # noqa: E402  (Windows/POSIX 平台适配单点)

# Windows 端永久不 import rumps（它是 macOS 托盘库），import 期即短路。
IS_WINDOWS = platform_win.is_windows()
MENU_BAR_SKIP_REASON = (
    "Windows 端 MVP 不做托盘图标（rumps 是 macOS 专用库，方案 §2「启动／自启」"
    "行 + §7①）。请用浏览器控制台或下面的 CLI 看状态。"
)

if IS_WINDOWS:
    _rumps = None
    RUMPS_AVAILABLE = False
else:
    try:
        import rumps as _rumps

        RUMPS_AVAILABLE = True
    except ImportError:
        _rumps = None
        RUMPS_AVAILABLE = False

from stage12.status_snapshot import collect  # noqa: E402


def _table_total(snapshot: dict, table: str) -> int:
    counts = (snapshot or {}).get("counts_by_state", {}) or {}
    states = counts.get(table, {}) or {}
    return int(sum(states.values()))


def build_title(snapshot: dict) -> str:
    """Title line derived from the same numbers collect() returns."""
    if not (snapshot or {}).get("ok"):
        return "懒得笔记 unavailable"
    return "懒得笔记 S:%d R:%d E:%d" % (
        _table_total(snapshot, "sources"),
        _table_total(snapshot, "processing_runs"),
        int((snapshot or {}).get("error_count", 0)),
    )


def build_lines(snapshot: dict) -> list:
    """Drop-down rows: the same three blocks as read-only text."""
    if not (snapshot or {}).get("ok"):
        return ["state unavailable: %s" % ((snapshot or {}).get("code", "UNKNOWN"),)]
    lines = ["state counts:"]
    counts = snapshot.get("counts_by_state", {}) or {}
    for table in sorted(counts):
        lines.append("  %s:" % (table,))
        states = counts.get(table) or {}
        if not states:
            lines.append("    (empty)")
        for state in sorted(states, key=lambda v: str(v)):
            lines.append("    %s: %d" % (state, states[state]))
    recent = snapshot.get("recent_runs", []) or []
    lines.append("recent runs (%d):" % (len(recent),))
    if not recent:
        lines.append("  (empty)")
    for row in recent:
        lines.append(
            "  %s %s %s %s"
            % (
                (row or {}).get("run_id"),
                (row or {}).get("source_id"),
                (row or {}).get("status"),
                (row or {}).get("updated_at"),
            )
        )
    lines.append("error count: %d" % (int(snapshot.get("error_count", 0)),))
    return lines


if RUMPS_AVAILABLE:

    class V2OApp(_rumps.App):
        """Menu-bar app with exactly two actions: Refresh and Quit."""

        def __init__(self, data_root: str, limit: int = 5) -> None:
            super().__init__("懒得笔记")
            self._data_root = os.path.abspath(data_root)
            self._limit = limit
            self._snapshot = collect(self._data_root, self._limit)
            self._rebuild()

        def _rebuild(self) -> None:
            self._snapshot = self._snapshot or {}
            self.title = build_title(self._snapshot)
            rows = [
                _rumps.MenuItem(line, callback=None)
                for line in build_lines(self._snapshot)
            ]
            rows.append(_rumps.MenuItem("Refresh", callback=self._on_refresh))
            rows.append(_rumps.MenuItem("Quit", callback=self._on_quit))
            self.menu = rows

        def _on_refresh(self, _sender) -> None:
            self._snapshot = collect(self._data_root, self._limit)
            self._rebuild()

        def _on_quit(self, _sender) -> None:
            _rumps.quit_application()

else:

    class V2OApp:
        """Placeholder used only when the optional package is absent."""

        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError(
                "optional menu-bar package is absent;"
                " use the stdlib CLI status command instead"
            )

        def run(self) -> None:
            raise RuntimeError(
                "optional menu-bar package is absent;"
                " use the stdlib CLI status command instead"
            )


def main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="stage12-menu-bar",
        description="Optional read-only 懒得笔记 menu-bar display.",
    )
    ap.add_argument(
        "--data-root",
        default=".",
        help="central data root holding data/state.db",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=5,
        help="recent-run row cap",
    )
    args = ap.parse_args(list(argv) if argv is not None else None)
    if IS_WINDOWS:
        print(MENU_BAR_SKIP_REASON)
        print(
            "  python -m stage12.status_cli status --data-root %s --limit %d"
            % (os.path.abspath(args.data_root), args.limit)
        )
        return 0
    if not RUMPS_AVAILABLE:
        print("menu bar is unavailable here; stdlib CLI path:")
        print(
            "  python -m stage12.status_cli status --data-root %s --limit %d"
            % (os.path.abspath(args.data_root), args.limit)
        )
        return 0
    app = V2OApp(args.data_root, args.limit)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
