"""S4-T01: output volume capability probe + Output gate.

Implements STAGE4-PLAN S4-T01 only (V1.8 ``# 54`` / ``# 55`` + ``# 3.14``)::

    probe_volume(path) -> nine measured fields
    gate_output_root(path) -> probe dict, or raises a BLOCK error

``probe_volume`` measures, never invents:

* ``filesystem_type`` — macOS ``stat -f %T`` of the covering dir,
  ``"unknown"`` when the probe cannot run (still non-empty).
* ``volume_id`` — ``str(os.stat(dir).st_dev)`` of the covering dir.
* ``local_or_remote`` — read-only reuse of ``stage1.probe_volume``
  (``"local"`` / ``"remote"`` / ``"unknown"``).
* ``case_sensitive`` — two probe names differing only in case either
  coexist (True) or collide with ``EEXIST`` (False).
* ``supports_atomic_rename`` — a same-dir ``os.rename`` round trip
  carrying exact bytes.
* ``supports_exclusive_rename`` — behavioural probe: rename a probe
  file onto a second probe file holding different bytes; when the
  target ends up holding the source bytes the rename *replaces*,
  so exclusive rename is NOT supported (False). POSIX ``rename``
  replaces by definition, so macOS/APFS honestly reports False.
* ``supports_exclusive_create`` — ``O_CREAT | O_EXCL`` creates once,
  then fails with ``EEXIST`` on retry.
* ``supports_hardlink`` — ``os.link`` round trip in the same dir.
* ``supports_advisory_lock`` — ``fcntl.flock(LOCK_EX | LOCK_NB)``.

``gate_output_root`` is the ``# 55`` + ``# 3.14`` door every publish
entry point must pass *before* any byte is staged:

* iCloud / network / remote markers (``# 3.14``) raise
  :class:`BlockedUnsupportedRoot`
  (``BLOCKED_UNSUPPORTED_ROOT_FOR_V1``).
* no reliable atomic no-cover primitive — neither exclusive rename
  nor ``O_CREAT | O_EXCL`` — raises
  :class:`BlockedUnsupportedOutputFilesystem`
  (``BLOCKED_UNSUPPORTED_OUTPUT_FILESYSTEM``).

There is no second door and no other way to stage bytes: the publish
path offers a single mechanism (fsync'd same-dir tmp + atomic
``link(2)`` commit, see ``publish_commit``), and that mechanism is the
only writer. Every success dict carries ``whisper_calls == 0``.
"""

from __future__ import annotations

import errno
import fcntl
import os
import subprocess
import uuid

# Path markers that always mean a non-local root (# 3.14, same set the
# Stage1 ingest gate uses; read here for the Output side).
REMOTE_PATH_MARKERS = (
    "Mobile Documents",
    "com~apple~CloudDocs",
    "iCloud Drive",
)

BLOCK_CODE_FILESYSTEM = "BLOCKED_UNSUPPORTED_OUTPUT_FILESYSTEM"
BLOCK_CODE_ROOT = "BLOCKED_UNSUPPORTED_ROOT_FOR_V1"

PROBE_FIELDS = (
    "filesystem_type",
    "volume_id",
    "local_or_remote",
    "case_sensitive",
    "supports_atomic_rename",
    "supports_exclusive_rename",
    "supports_exclusive_create",
    "supports_hardlink",
    "supports_advisory_lock",
)


class BlockedUnsupportedOutputFilesystem(RuntimeError):
    """# 55: the volume cannot do atomic no-cover publishes."""

    def __init__(self, message: str, probe: dict):
        super().__init__(message)
        self.probe = probe
        self.code = BLOCK_CODE_FILESYSTEM


class BlockedUnsupportedRoot(RuntimeError):
    """# 3.14: iCloud / network / remote output roots are out for V1."""

    def __init__(self, message: str, probe: dict):
        super().__init__(message)
        self.probe = probe
        self.code = BLOCK_CODE_ROOT


def _covering_dir(path: str) -> str:
    """Nearest existing dir: the path itself, its parent, or above."""
    candidate = os.path.abspath(path)
    if os.path.isfile(candidate):
        candidate = os.path.dirname(candidate)
    while not os.path.isdir(candidate):
        parent = os.path.dirname(candidate)
        if parent == candidate:
            raise OSError("no existing ancestor dir for %r" % (path,))
        candidate = parent
    return candidate


def _probe_name(tag: str) -> str:
    return ".s4probe_%s_%s" % (tag, uuid.uuid4().hex[:8])


def _filesystem_type(covering_dir: str) -> str:
    try:
        out = subprocess.run(
            ["stat", "-f", "%T", covering_dir],
            capture_output=True, text=True, timeout=10,
        )
        fstype = (out.stdout or "").strip()
        if out.returncode == 0 and fstype:
            return fstype
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


def _local_or_remote(covering_dir: str) -> str:
    from stage1 import probe_volume as _s1_probe  # noqa: PLC0415 (read-only)

    try:
        verdict = _s1_probe(covering_dir)
    except (OSError, ValueError, RuntimeError):
        return "unknown"
    kind = verdict.get("local_or_remote")
    return kind if kind in ("local", "remote") else "unknown"


def _case_sensitive(covering_dir: str) -> bool:
    lower = os.path.join(covering_dir, _probe_name("case"))
    upper = lower + "X"
    lower2 = lower + "x"
    try:
        fd = os.open(lower2, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        try:
            fd2 = os.open(upper, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except OSError as exc:
            if exc.errno == errno.EEXIST:
                return False
            raise
        os.close(fd2)
        os.unlink(upper)
        return True
    except OSError:
        return False
    finally:
        for candidate in (lower, lower2, upper):
            try:
                os.unlink(candidate)
            except OSError:
                pass


def _atomic_rename(covering_dir: str) -> bool:
    src = os.path.join(covering_dir, _probe_name("ren_src"))
    dst = os.path.join(covering_dir, _probe_name("ren_dst"))
    try:
        with open(src, "wb") as fh:
            fh.write(b"s4-rename-probe")
            fh.flush()
            os.fsync(fh.fileno())
        os.rename(src, dst)
        with open(dst, "rb") as fh:
            return fh.read() == b"s4-rename-probe"
    except OSError:
        return False
    finally:
        for candidate in (src, dst):
            try:
                os.unlink(candidate)
            except OSError:
                pass


def _exclusive_rename(covering_dir: str) -> bool:
    """True only when rename refuses to dislodge an existing target."""
    src = os.path.join(covering_dir, _probe_name("xren_src"))
    dst = os.path.join(covering_dir, _probe_name("xren_dst"))
    try:
        with open(src, "wb") as fh:
            fh.write(b"s4-xren-src")
        with open(dst, "wb") as fh:
            fh.write(b"s4-xren-dst")
        try:
            os.rename(src, dst)
        except OSError as exc:
            if exc.errno == errno.EEXIST:
                return True
            return False
        with open(dst, "rb") as fh:
            replaced = fh.read() == b"s4-xren-src"
        return not replaced
    except OSError:
        return False
    finally:
        for candidate in (src, dst):
            try:
                os.unlink(candidate)
            except OSError:
                pass


def _exclusive_create(covering_dir: str) -> bool:
    target = os.path.join(covering_dir, _probe_name("xcre"))
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        try:
            fd2 = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except OSError as exc:
            return exc.errno == errno.EEXIST
        os.close(fd2)
        return False
    except OSError:
        return False
    finally:
        try:
            os.unlink(target)
        except OSError:
            pass


def _hardlink(covering_dir: str) -> bool:
    src = os.path.join(covering_dir, _probe_name("hl_src"))
    dst = os.path.join(covering_dir, _probe_name("hl_dst"))
    try:
        with open(src, "wb") as fh:
            fh.write(b"s4-hardlink-probe")
        os.link(src, dst)
        with open(dst, "rb") as fh:
            return fh.read() == b"s4-hardlink-probe"
    except OSError:
        return False
    finally:
        for candidate in (src, dst):
            try:
                os.unlink(candidate)
            except OSError:
                pass


def _advisory_lock(covering_dir: str) -> bool:
    target = os.path.join(covering_dir, _probe_name("lock"))
    try:
        with open(target, "wb") as fh:
            fh.write(b"s4-lock-probe")
        fh = open(target, "r+b")
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            return True
        except (BlockingIOError, OSError):
            return False
        finally:
            fh.close()
    except OSError:
        return False
    finally:
        try:
            os.unlink(target)
        except OSError:
            pass


def probe_volume(path: str) -> dict:
    """Measure the # 54 nine fields for the volume holding ``path``."""
    covering = _covering_dir(path)
    st = os.stat(covering)
    probe = {
        "path": os.path.abspath(path),
        "covering_dir": covering,
        "filesystem_type": _filesystem_type(covering),
        "volume_id": str(st.st_dev),
        "local_or_remote": _local_or_remote(covering),
        "case_sensitive": _case_sensitive(covering),
        "supports_atomic_rename": _atomic_rename(covering),
        "supports_exclusive_rename": _exclusive_rename(covering),
        "supports_exclusive_create": _exclusive_create(covering),
        "supports_hardlink": _hardlink(covering),
        "supports_advisory_lock": _advisory_lock(covering),
        "whisper_calls": 0,
    }
    return probe


def gate_output_root(path: str) -> dict:
    """Pass the # 55 + # 3.14 door, or raise the matching BLOCK error.

    Must run before any publish byte is staged; every publish entry
    point in this package calls it first.
    """
    probe = probe_volume(path)
    abspath = os.path.abspath(path)
    if (
        probe.get("local_or_remote") != "local"
        or any(marker in abspath for marker in REMOTE_PATH_MARKERS)
    ):
        raise BlockedUnsupportedRoot(
            "%s: output root %r is not a local V1 volume "
            "(local_or_remote=%r)" % (
                BLOCK_CODE_ROOT, abspath, probe.get("local_or_remote"),
            ),
            probe,
        )
    if not (
        probe.get("supports_exclusive_rename")
        or probe.get("supports_exclusive_create")
    ):
        raise BlockedUnsupportedOutputFilesystem(
            "%s: volume holding %r offers no reliable atomic "
            "no-cover primitive" % (BLOCK_CODE_FILESYSTEM, abspath),
            probe,
        )
    return probe
