"""S11-T01: LaunchAgent plist build / write / validate + test-dir drill.

Implements STAGE11-PLAN S11-T01 only (V1.8 S69 + S72 LaunchAgent gate):

  build_plist(...)  -> plist dict with test-domain Label, absolute
                      ProgramArguments, WorkingDirectory, RunAtLoad,
                      KeepAlive, ThrottleInterval, log paths under
                      <data_root>/logs/.
  write_plist(...)  -> path-prefix gate (plist stays inside the given
                      test agent dir; real dirs are refused) + plistlib
                      write.
  validate_plist(..)-> plutil -lint pass + read-back checks (absolute
                      paths, Label/RunAtLoad/KeepAlive present).
  load/unload helpers exercise launchctl only against the test plist
  and unload immediately so no resident entry is left behind.

Hard gates (TM decided):
  - Real dirs ~/Library/LaunchAgents and /Library/LaunchAgents are
    never written, loaded, or listed for mutation. Any path touching
    them is refused.
  - The persist-boot path is never invoked by this module (no such
    call exists here by construction; the self-check scans this
    package for it structurally).
  - Zero transcription: every result carries asr_calls == 0 and
    whisper_calls == 0. Zero central-DB writes from this module.

Windows（本批改造）：launchd/LaunchAgents 在 Windows 11 上不存在。
模块**照常可 import**（plistlib 是标准库），但所有入口在非 macOS 上返回
``{"skipped": True, ...}`` 并附人话说明，**不抛异常、不假装自启成功**。
MVP 不做开机自启（方案 §2「启动／自启」行）。

Additive-only: stdlib only + read-only path facts. No stage1-10 file
is amended; no new table or column is created here.
"""

from __future__ import annotations

import os
import plistlib
import subprocess

import platform_win  # noqa: E402  (Windows/POSIX 平台适配单点)

LABEL_PREFIX = "com.video2obsidian.test."
THROTTLE_DEFAULT = 10

LAUNCHD_SUPPORTED = not platform_win.is_windows()
SKIP_REASON = (
    "Windows 11 没有 launchd / LaunchAgents，开机自启在 Windows 端不可用；"
    "MVP 不做自启（方案 §2「启动／自启」行）。"
    "看状态请用：python -m stage12.status_cli status --data-root <data_root>"
)


def skipped(platform: str | None = None) -> dict:
    """Windows 上的优雅跳过：显式说明 + 零副作用，不抛异常。"""
    return {
        "skipped": True,
        "platform": platform_win.current_platform(platform),
        "reason": SKIP_REASON,
        "asr_calls": 0,
        "whisper_calls": 0,
    }

_REAL_AGENT_DIRS = (
    os.path.abspath(os.path.expanduser("~/Library/LaunchAgents")),
    os.path.abspath("/Library/LaunchAgents"),
)


def _abs(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))


def _inside(root_abs: str, cand_abs: str) -> bool:
    try:
        return os.path.commonpath([root_abs, cand_abs]) == root_abs
    except (ValueError, OSError):
        return False


def _refuse_real_dir(cand_abs: str) -> None:
    for real in _REAL_AGENT_DIRS:
        if cand_abs == real or _inside(real, cand_abs):
            raise ValueError(
                "refused: path touches a real LaunchAgents dir: %r" % (cand_abs,)
            )


def snapshot_real_agents() -> dict:
    """List real LaunchAgents dirs (read-only listing for zero-touch proof)."""
    out: dict = {}
    for real in _REAL_AGENT_DIRS:
        try:
            names = sorted(os.listdir(real))
        except FileNotFoundError:
            names = []
        except OSError as exc:
            names = ["<unreadable: %s>" % (exc,)]
        out[real] = names
    return out


def build_plist(
    label: str,
    abs_binary: str,
    data_root: str,
    test_agent_dir: str,
    input_root: str | None = None,
    asr_profile_hash: str = "test-profile-v1",
    throttle_interval: int = THROTTLE_DEFAULT,
) -> dict:
    """Assemble the plist dict. All paths recorded are absolute."""
    if not LAUNCHD_SUPPORTED:
        return skipped()
    if not label or not label.startswith(LABEL_PREFIX):
        raise ValueError(
            "label must start with %r (got %r)" % (LABEL_PREFIX, label)
        )
    binary_abs = _abs(abs_binary)
    if not os.path.isabs(binary_abs):
        raise ValueError("binary path must be absolute: %r" % (abs_binary,))
    data_abs = _abs(data_root)
    agent_abs = _abs(test_agent_dir)
    if not os.path.isabs(data_abs) or not os.path.isabs(agent_abs):
        raise ValueError("data_root and test_agent_dir must be absolute")
    _refuse_real_dir(agent_abs)
    _refuse_real_dir(data_abs)
    logs_abs = os.path.join(data_abs, "logs")
    args: list[str] = [binary_abs]
    args += ["--data-root", data_abs]
    if input_root is not None:
        args += ["--input-root", _abs(input_root)]
    args += ["--asr-profile-hash", asr_profile_hash]
    # Path-valued flags hold absolute paths; the profile hash is an
    # opaque identity string (never a path, never executed).
    skip_next = False
    for idx, item in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if item.startswith("--"):
            if item == "--asr-profile-hash":
                skip_next = True
            continue
        if not os.path.isabs(item):
            raise ValueError("ProgramArguments must be absolute: %r" % (item,))
    plist: dict = {
        "Label": label,
        "ProgramArguments": args,
        "WorkingDirectory": data_abs,
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": int(throttle_interval),
        "StandardOutPath": os.path.join(logs_abs, "stdout.log"),
        "StandardErrorPath": os.path.join(logs_abs, "stderr.log"),
    }
    return plist


def plist_path_for(test_agent_dir: str, label: str) -> str:
    agent_abs = _abs(test_agent_dir)
    _refuse_real_dir(agent_abs)
    if not label.startswith(LABEL_PREFIX):
        raise ValueError("label must start with %r" % (LABEL_PREFIX,))
    return os.path.join(agent_abs, label + ".plist")


def write_plist(plist: dict, test_agent_dir: str, label: str) -> dict:
    """Write the plist inside the test agent dir (prefix gate held)."""
    if not LAUNCHD_SUPPORTED:
        return skipped()
    agent_abs = _abs(test_agent_dir)
    _refuse_real_dir(agent_abs)
    dest = plist_path_for(agent_abs, label)
    if not _inside(agent_abs, _abs(dest)):
        raise ValueError("refused: plist dest escapes test agent dir")
    data_abs = _abs(str(plist.get("WorkingDirectory", "")))
    _refuse_real_dir(data_abs)
    os.makedirs(agent_abs, exist_ok=True)
    os.makedirs(os.path.join(data_abs, "logs"), exist_ok=True)
    with open(dest, "wb") as fh:
        plistlib.dump(plist, fh)
        fh.flush()
        os.fsync(fh.fileno())
    return {
        "plist_path": dest,
        "label": label,
        "asr_calls": 0,
        "whisper_calls": 0,
    }


def validate_plist(
    plist_path: str,
    expect_label: str | None = None,
    expect_binary: str | None = None,
    expect_data_root: str | None = None,
) -> dict:
    """plutil -lint + read-back absolute-path and field checks."""
    if not LAUNCHD_SUPPORTED:
        return skipped()
    path_abs = _abs(plist_path)
    _refuse_real_dir(path_abs)
    proc = subprocess.run(
        ["plutil", "-lint", path_abs],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
    )
    lint_ok = proc.returncode == 0
    lint_out = (proc.stdout or "") + (proc.stderr or "")
    with open(path_abs, "rb") as fh:
        payload = plistlib.load(fh)
    problems: list[str] = []
    if not lint_ok:
        problems.append("plutil -lint failed: %s" % (lint_out.strip(),))
    label = payload.get("Label")
    if not isinstance(label, str) or not label.startswith(LABEL_PREFIX):
        problems.append("Label missing or not in test domain: %r" % (label,))
    if expect_label is not None and label != expect_label:
        problems.append("Label drift: %r != %r" % (label, expect_label))
    for key in ("RunAtLoad", "KeepAlive"):
        if payload.get(key) is not True:
            problems.append("%s must be true" % (key,))
    prog = payload.get("ProgramArguments")
    if not isinstance(prog, list) or not prog:
        problems.append("ProgramArguments missing or empty")
    else:
        skip_next = False
        for item in prog:
            if skip_next:
                skip_next = False
                continue
            if isinstance(item, str) and item.startswith("--"):
                if item == "--asr-profile-hash":
                    skip_next = True
                continue
            if not isinstance(item, str) or not os.path.isabs(item):
                problems.append("ProgramArguments not absolute: %r" % (item,))
    if expect_binary is not None and isinstance(prog, list) and prog:
        if os.path.abspath(prog[0]) != os.path.abspath(expect_binary):
            problems.append("binary drift: %r" % (prog[0],))
    work = payload.get("WorkingDirectory")
    if not isinstance(work, str) or not os.path.isabs(work):
        problems.append("WorkingDirectory must be absolute: %r" % (work,))
    if expect_data_root is not None and work != os.path.abspath(expect_data_root):
        problems.append("WorkingDirectory drift: %r" % (work,))
    for key in ("StandardOutPath", "StandardErrorPath"):
        val = payload.get(key)
        if not isinstance(val, str) or not os.path.isabs(val):
            problems.append("%s must be absolute: %r" % (key, val))
        elif isinstance(work, str) and os.path.isabs(work):
            if not _inside(work, val):
                problems.append("%s escapes data_root logs dir" % (key,))
    verdict = "PASS" if not problems else "FAIL"
    return {
        "verdict": verdict,
        "problems": problems,
        "label": label,
        "plist_path": path_abs,
        "lint_ok": lint_ok,
        "asr_calls": 0,
        "whisper_calls": 0,
    }


def _label_for_plist(plist_path: str) -> str:
    with open(_abs(plist_path), "rb") as fh:
        payload = plistlib.load(fh)
    label = payload.get("Label")
    if not isinstance(label, str) or not label:
        raise ValueError("plist has no Label: %r" % (plist_path,))
    return label


def load_test_plist(plist_path: str, test_agent_dir: str) -> dict:
    """launchctl load the test plist (test dir only)."""
    if not LAUNCHD_SUPPORTED:
        return skipped()
    path_abs = _abs(plist_path)
    agent_abs = _abs(test_agent_dir)
    _refuse_real_dir(path_abs)
    _refuse_real_dir(agent_abs)
    if not _inside(agent_abs, path_abs):
        raise ValueError("refused: plist outside test agent dir")
    label = _label_for_plist(path_abs)
    proc = subprocess.run(
        ["launchctl", "load", path_abs],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
    )
    listed = _list_has_label(label)
    return {
        "label": label,
        "load_returncode": proc.returncode,
        "load_stdout": proc.stdout,
        "load_stderr": proc.stderr,
        "list_visible": listed,
        "asr_calls": 0,
        "whisper_calls": 0,
    }


def unload_test_plist(plist_path: str, test_agent_dir: str) -> dict:
    """launchctl unload the test plist; no resident entry may remain."""
    if not LAUNCHD_SUPPORTED:
        return skipped()
    path_abs = _abs(plist_path)
    agent_abs = _abs(test_agent_dir)
    _refuse_real_dir(path_abs)
    _refuse_real_dir(agent_abs)
    if not _inside(agent_abs, path_abs):
        raise ValueError("refused: plist outside test agent dir")
    label = _label_for_plist(path_abs)
    proc = subprocess.run(
        ["launchctl", "unload", path_abs],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
    )
    listed = _list_has_label(label)
    return {
        "label": label,
        "unload_returncode": proc.returncode,
        "unload_stdout": proc.stdout,
        "unload_stderr": proc.stderr,
        "list_visible": listed,
        "residue": listed,
        "asr_calls": 0,
        "whisper_calls": 0,
    }


def _list_has_label(label: str) -> bool:
    try:
        proc = subprocess.run(
            ["launchctl", "list"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if proc.returncode != 0:
        return False
    for line in (proc.stdout or "").splitlines():
        if label in line:
            return True
    return False
