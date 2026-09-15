"""S12-T02: stdlib status command + optional text menu.

Implements STAGE12-PLAN S12-T02 only:

  status [--data-root R] [--format json|text] [--limit N]
    json prints the S12-T01 snapshot object as-is;
    text prints the same data as three readable blocks
    (counts by state / recent runs / error count).
    Exit 0 on success; exit 2 plus a structured object on stderr
    when the central DB is missing or unreadable.
  menu [--data-root R] [--limit N] (also reachable via --menu)
    stdlib input() loop with exactly three choices:
    show status / refresh / quit. No control entries of any kind.

Stdlib only (argparse / json / sys). Additive-only: read-only reuse
of status_snapshot.collect; never amends src/stage1-11; never writes
the central DB.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from stage12.status_snapshot import collect  # noqa: E402

EXIT_OK = 0
EXIT_DB_ERROR = 2


def render_text(snapshot: dict) -> str:
    """Human-readable three-block view of a success snapshot object."""
    counts = snapshot.get("counts_by_state", {}) or {}
    recent = snapshot.get("recent_runs", []) or []
    out = ["state counts:"]
    for table in sorted(counts):
        out.append("  %s:" % (table,))
        states = counts.get(table) or {}
        if not states:
            out.append("    (empty)")
        for state in sorted(states, key=lambda v: str(v)):
            out.append("    %s: %d" % (state, states[state]))
    out.append("recent runs (%d):" % (len(recent),))
    if not recent:
        out.append("  (empty)")
    for row in recent:
        out.append(
            "  %s %s %s %s"
            % (
                row.get("run_id"),
                row.get("source_id"),
                row.get("status"),
                row.get("updated_at"),
            )
        )
    out.append("error count: %d" % (int(snapshot.get("error_count", 0)),))
    out.append("collected_at: %s" % (snapshot.get("collected_at"),))
    return "\n".join(out)


def _emit_failure(snapshot: dict) -> int:
    sys.stderr.write(
        json.dumps(
            {
                "ok": False,
                "code": snapshot.get("code", "DB_UNREADABLE"),
                "message": snapshot.get("message", ""),
                "collected_at": snapshot.get("collected_at"),
            },
            ensure_ascii=False,
        )
        + "\n"
    )
    sys.stderr.flush()
    return EXIT_DB_ERROR


def run_status(data_root: str, format: str = "json", limit: int = 5) -> int:
    """One-shot status path shared by CLI entry and tests."""
    snapshot = collect(os.path.abspath(data_root), limit)
    if not snapshot.get("ok"):
        return _emit_failure(snapshot)
    if format == "text":
        sys.stdout.write(render_text(snapshot) + "\n")
    else:
        sys.stdout.write(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")
    sys.stdout.flush()
    return EXIT_OK


def run_menu(data_root: str, limit: int = 5, _input=input, _print=print) -> int:
    """Stdlib text menu: show status / refresh / quit (read-only)."""
    data_abs = os.path.abspath(data_root)
    while True:
        _print("menu: [1] show status  [2] refresh  [3] quit")
        try:
            raw = _input("choice (1/2/3): ")
        except (EOFError, KeyboardInterrupt):
            _print("")
            return EXIT_OK
        choice = (raw or "").strip().lower()
        if choice in ("1", "show", "2", "refresh"):
            snapshot = collect(data_abs, limit)
            if not snapshot.get("ok"):
                _print(
                    "db error %s: %s"
                    % (snapshot.get("code"), snapshot.get("message"))
                )
            else:
                _print(render_text(snapshot))
        elif choice in ("3", "quit", "q"):
            return EXIT_OK
        else:
            _print("unknown choice; use 1/2/3")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="stage12-status",
        description="Read-only 懒得笔记 status display (counts by state,"
        " recent runs, error count).",
    )
    ap.add_argument(
        "command",
        nargs="?",
        default="status",
        choices=("status", "menu"),
        help="status prints one snapshot; menu opens the text menu",
    )
    ap.add_argument(
        "--data-root",
        default=".",
        help="central data root holding data/state.db",
    )
    ap.add_argument(
        "--format",
        default="json",
        choices=("json", "text"),
        help="output shape for the status command",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=5,
        help="recent-run row cap",
    )
    ap.add_argument(
        "--menu",
        action="store_true",
        help="open the text menu (same as the menu command)",
    )
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    if args.menu or args.command == "menu":
        return run_menu(args.data_root, args.limit)
    return run_status(args.data_root, args.format, args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
