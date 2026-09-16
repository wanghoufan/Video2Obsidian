"""Windows 11 平台适配单点（Stage 1 启动链 + Stage 2 文件安全）。

本模块是 Windows 语义的**唯一入口**：锁、占用探测、卷探针、长路径、data
root、reveal 命令、UTF-8、进程终止全部从这里出。业务模块不再直接 import
``fcntl`` / ``msvcrt`` / ``ctypes.windll`` / ``winreg``，改调这里的函数，
平台分支只在这一处判。

判定与可测性约定（本机是 macOS，不能真跑 Windows 行为）：
  - 平台判定走 ``is_windows(platform=None)``，实参为空时**现场读
    ``sys.platform``**（不是 import 期快照），测试 monkeypatch ``sys.platform``
    即可进 Windows 分支。
  - Windows 能力（``ctypes.windll`` / ``winreg`` / ``msvcrt``）全部**惰性状
    态取用**，测试可注入假模块：``platform_win.ctypes``、
    ``platform_win._WINREG``，或 ``sys.modules["msvcrt"]``。
  - 能力缺失一律 :class:`PlatformCapabilityMissing`（人话 + 交由调用方
    BLOCK），**绝不静默当作「不支持但没关系」放行**。

不做的（红线）：
  - 不改注册表、不申请 UAC、不加 Defender 排除、不杀占用端口的进程。
"""

from __future__ import annotations

import ntpath
import os
import posixpath
import subprocess
import sys
import tempfile

try:  # POSIX 分支才用得到；Windows 上没有这个模块
    import fcntl
except ImportError:  # pragma: no cover - Windows 真机
    fcntl = None  # type: ignore[assignment]

try:  # 只有 Windows 提供；测试可替换 platform_win.ctypes 注入假实现
    import ctypes
except ImportError:  # pragma: no cover
    ctypes = None  # type: ignore[assignment]

try:  # 只有 Windows 提供；测试可替换 platform_win._WINREG 注入假实现
    import winreg as _winreg_mod
except Exception:  # pragma: no cover - 非 Windows / 受限环境
    _winreg_mod = None

_WINREG = None  # 测试注入点：设成假 winreg 模块即可在 macOS 跑注册表分支

# ---- 常量 ---------------------------------------------------------------
MAX_PATH = 260                 # Win32 MAX_PATH（含结尾 NUL）
USABLE_PATH_LIMIT = MAX_PATH - 1  # 实际可用 259
LONG_PATH_BLOCK_CODE = "BLOCKED_PATH_TOO_LONG_FOR_WINDOWS"
LONG_PATH_REG_KEY = r"SYSTEM\CurrentControlSet\Control\FileSystem"
LONG_PATH_REG_VALUE = "LongPathsEnabled"

DATA_ROOT_PARENT = "Video2Obsidian"
DATA_ROOT_LEAF = "data"

ENCODING = "utf-8"

# GetDriveTypeW 返回值
_DRIVE_FIXED = 3
_DRIVE_REMOTE = 4
_DRIVE_CDROM = 5
_DRIVE_RAMDISK = 6

INVALID_HANDLE_VALUE = -1  # CreateFileW 失败时（按 int 比较）


class PlatformCapabilityMissing(RuntimeError):
    """Windows 能力不可用：调用方必须 BLOCK 并给人话，不许静默放行。"""


class DataRootUnavailable(RuntimeError):
    """Windows 上拿不到 LOCALAPPDATA：不回落、不猜目录，直接报错给人类。"""


# ---- 平台判定 -----------------------------------------------------------
def current_platform(platform: str | None = None) -> str:
    """平台字符串；实参为空时现场读 ``sys.platform``（可被测试 monkeypatch）。"""
    return str(sys.platform if platform is None else platform)


def is_windows(platform: str | None = None) -> bool:
    p = current_platform(platform).lower()
    return p.startswith("win") or p in ("nt", "cygwin", "msys")


def _ops(platform: str | None = None):
    """Windows 语义一律走 ntpath（macOS 上也能拿到 Windows 路径语义）。"""
    return ntpath if is_windows(platform) else posixpath


# ---- 路径 ---------------------------------------------------------------
def normcase(path: str, platform: str | None = None) -> str:
    """大小写不敏感 + 分隔符归一（Windows 用小写字面量比较用）。"""
    op = _ops(platform)
    return op.normcase(op.normpath(str(path)))


def abspath(path: str, platform: str | None = None) -> str:
    """按平台语义取绝对路径（Windows 用 ntpath，POSIX 用 posixpath）。

    生产上与 ``os.path.abspath`` 完全等价（Windows 上 ``os.path`` 就是
    ntpath）；单独封装是为了让 Windows 分支在 macOS 上也能被桩测试。
    """
    return _ops(platform).abspath(str(path))


def same_path(a: str, b: str, platform: str | None = None) -> bool:
    return normcase(a, platform) == normcase(b, platform)


def is_unc(path: str, platform: str | None = None) -> bool:
    p = _ops(platform).normpath(str(path))
    return p.startswith("\\\\")


def is_within(parent: str, child: str, platform: str | None = None) -> bool:
    """normcase + commonpath 判定包含关系（方案 §2「路径」行）。

    已知限制（P2-2，fail-closed，已记，Windows 真机须复验）：``parent`` 为
    **UNC 共享根本身**（``\\\\server\\share``，再无下一级）时返回 False ——
    ntpath 把它拆成 drive=``\\\\server\\share`` + 空剩余，再与带剩余的子路径
    commonpath 会因「绝对路径/相对路径混用」抛 ValueError，本函数按规矩落到
    False。方向是**不放行**（宁可判「不在目录内」也不误判在），且 UNC 根目录
    在入口已被 :func:`validate_root` 拦成 ``BLOCKED_UNC_ROOT``。
    """
    op = _ops(platform)
    p = normcase(parent, platform)
    c = normcase(child, platform)
    if p == c:
        return True
    try:
        return op.commonpath([p, c]) == p
    except (ValueError, OSError):
        return False


def to_extended_path(path: str, platform: str | None = None) -> str:
    """给 >259 的绝对路径加 ``\\\\?\\`` 前缀（仅 Win32 边界用，不改写业务路径）。

    UNC 走 ``\\\\?\\UNC\\``；非 Windows 平台原样返回。
    """
    if not is_windows(platform):
        return str(path)
    p = ntpath.normpath(str(path).replace("/", "\\"))
    if p.startswith("\\\\?\\"):
        return p
    if p.startswith("\\\\"):
        return "\\\\?\\UNC\\" + p[2:]
    return "\\\\?\\" + p


# ---- 长路径 -------------------------------------------------------------
def long_paths_enabled(platform: str | None = None) -> bool | None:
    """只读探测「Win32 长路径」策略。

    返回 True/False；**读不到就返回 None**（视作未开 → BLOCK，给人话指引）。
    只读注册表，绝不写入、绝不申请管理员权限。
    """
    if not is_windows(platform):
        return None
    reg = _WINREG if _WINREG is not None else _winreg_mod
    if reg is None:
        return None
    try:
        with reg.OpenKey(reg.HKEY_LOCAL_MACHINE, LONG_PATH_REG_KEY) as key:
            value, _ = reg.QueryValueEx(key, LONG_PATH_REG_VALUE)
    except Exception:
        return None
    try:
        return int(value) == 1
    except (TypeError, ValueError):
        return None


def check_path_length(path: str, platform: str | None = None,
                      policy: bool | None = None) -> dict:
    """259/260/261 边界判定。未开长路径策略 + 超长 → BLOCK（不自动改注册表）。"""
    length = len(str(path))
    guidance = (
        "Windows 默认路径上限为 259 个字符（MAX_PATH 260 含结尾 NUL）。"
        "本程序不会自动修改注册表、不会申请管理员权限。"
        "要解除限制请自行开启「启用 Win32 长路径」：组策略 计算机配置→管理模板"
        "→系统→文件系统，或注册表 HKLM\\%s\\%s = 1（需管理员权限，改完重启）。"
        % (LONG_PATH_REG_KEY, LONG_PATH_REG_VALUE)
    )
    out = {
        "path": str(path),
        "length": length,
        "limit": USABLE_PATH_LIMIT,
        "platform": current_platform(platform),
    }
    if not is_windows(platform):
        out.update(verdict="ALLOW", code=None, long_paths_enabled=None,
                   message="非 Windows 平台，不做 259 长度限制", guidance="")
        return out
    enabled = long_paths_enabled(platform) if policy is None else bool(policy)
    if length <= USABLE_PATH_LIMIT:
        out.update(verdict="ALLOW", code=None, long_paths_enabled=enabled,
                   message="", guidance="")
        return out
    if enabled is True:
        out.update(
            verdict="ALLOW_EXTENDED", code=None, long_paths_enabled=True,
            message=("路径 %d 字符超过 259，但已开启 Win32 长路径策略；"
                     "Win32 调用需自行使用 \\\\?\\ 前缀，且 Explorer/ffmpeg/"
                     "Obsidian 需分别真机验证" % (length,)),
            guidance="",
        )
        return out
    out.update(
        verdict="BLOCK", code=LONG_PATH_BLOCK_CODE, long_paths_enabled=enabled,
        message=("路径 %d 字符超过 Windows 上限 259（%s）：本程序已停止，"
                 "未创建/未改动任何文件"
                 % (length, LONG_PATH_BLOCK_CODE)),
        guidance=guidance,
    )
    return out


def too_long_reason(path, what: str = "路径",
                    platform: str | None = None) -> str | None:
    """写入/读取某路径前的长路径闸：超限回人话 reason，否则 None。"""
    if not path:
        return None
    verdict = check_path_length(path, platform=platform)
    if verdict["verdict"] != "BLOCK":
        return None
    tail = ("。" + verdict["guidance"]) if verdict.get("guidance") else ""
    return ("%s太长（%d 字符，超过 Windows 上限 %d）：已拦下，未写入任何文件"
            "（请把文件或目录搬到更短的路径下再重试）%s"
            % (("%s " % (what,)) if what else "", verdict["length"],
               verdict["limit"], tail))


def validate_root(path: str, label: str = "路径",
                  platform: str | None = None) -> dict:
    """目录（data root / input root / vault root）**接受前**的体检。

    三件事，任一条不满足即 BLOCK（不猜测、不静默回落、不写注册表）：
      ① 必须绝对路径；② Windows 上 UNC 网络共享根一律 BLOCK（网络盘 V1 不
      支持，与 Stage1/Stage4 的 remote BLOCK 同口径）；③ 长路径 >259 且未
      开 Win32 长路径策略 → BLOCK + 人话指引。
    """
    out = {
        "ok": True, "verdict": "ALLOW", "code": None, "message": "",
        "guidance": "", "path": str(path), "label": label,
        "length": len(str(path)), "platform": current_platform(platform),
    }
    if not _ops(platform).isabs(str(path)):
        out.update(ok=False, verdict="BLOCK",
                   code="BLOCKED_PATH_NOT_ABSOLUTE",
                   message="%s须为绝对路径，请点浏览重选" % (label,))
        return out
    if is_windows(platform) and is_unc(path, platform):
        out.update(ok=False, verdict="BLOCK", code="BLOCKED_UNC_ROOT",
                   message=("%s是 UNC 网络共享路径：Windows 端按网络盘拦下，"
                            "请改用本机盘符下的目录" % (label,)))
        return out
    verdict = check_path_length(path, platform=platform)
    out["length"] = verdict["length"]
    if verdict["verdict"] == "BLOCK":
        out.update(ok=False, verdict="BLOCK", code=verdict["code"],
                   message=("%s太长（%d 字符，超过 Windows 上限 %d）：已拦下，"
                            "未写入任何文件" % (label, verdict["length"],
                                              verdict["limit"])),
                   guidance=verdict["guidance"])
        return out
    if verdict["verdict"] == "ALLOW_EXTENDED":
        out.update(verdict="ALLOW_EXTENDED", message=verdict["message"])
    return out


# ---- data root ----------------------------------------------------------
def default_data_root(environ: dict | None = None,
                      platform: str | None = None) -> str:
    """正式 data root。Windows：``%LOCALAPPDATA%\\Video2Obsidian\\data``。

    找不到 ``LOCALAPPDATA`` → :class:`DataRootUnavailable`（人话，不静默回落
    到 CWD/临时目录）。非 Windows 维持既有 macOS 口径（临时目录下的控制台
    数据目录）。
    """
    env = os.environ if environ is None else environ
    if is_windows(platform):
        base = str(env.get("LOCALAPPDATA") or "").strip()
        if not base:
            raise DataRootUnavailable(
                "找不到环境变量 LOCALAPPDATA，Windows 上无法确定正式数据目录"
                "（应为 %%LOCALAPPDATA%%\\%s\\%s）。"
                "请确认以普通用户身份登录并重新启动：本程序不会猜测目录、"
                "也不会改用临时目录代替正式数据目录。"
                % (DATA_ROOT_PARENT, DATA_ROOT_LEAF)
            )
        return ntpath.join(base, DATA_ROOT_PARENT, DATA_ROOT_LEAF)
    return posixpath.join(tempfile.gettempdir(), "v2o-console-data")


# ---- 资源管理器定位 -----------------------------------------------------
def build_reveal_argv(path: str, platform: str | None = None) -> dict:
    """构造「在文件管理器中定位」的**参数数组**（不拼 shell 字符串）。

    Windows：``explorer.exe /select,<path>``。已知坑：路径含逗号或双引号时
    Explorer 会把它当分隔符/引号截断，此时**降级为打开所在文件夹**并如实
    说明（mode=open-folder），不假装定位成功。
    """
    op = _ops(platform)
    target = op.normpath(str(path))
    if is_windows(platform):
        if "," in target or '"' in target:
            folder = op.dirname(target) or target
            return {
                "argv": ["explorer.exe", folder],
                "mode": "open-folder",
                "note": "路径含逗号或双引号，Explorer /select, 会截断，"
                        "改为打开所在文件夹（未定位到文件本身）",
                "path": target,
            }
        return {"argv": ["explorer.exe", "/select," + target],
                "mode": "select", "note": "", "path": target}
    if current_platform(platform) == "darwin":
        return {"argv": ["open", "-R", target], "mode": "select",
                "note": "", "path": target}
    return {"argv": ["xdg-open", op.dirname(target) or target],
            "mode": "open-folder",
            "note": "非 macOS/Windows：只能打开所在文件夹", "path": target}


# ---- 文件占用 / 锁 ------------------------------------------------------
def _win_file_busy(path: str) -> bool:
    """CreateFileW 共享模式探测：share=0 打不开即被占用（Windows 语义）。"""
    if ctypes is None:
        raise PlatformCapabilityMissing(
            "CreateFileW 占用探测需要 Windows 的 ctypes.windll；"
            "当前环境不可用，无法判定占用（调用方必须 BLOCK，不许当作未占用）"
        )
    kernel32 = getattr(ctypes, "windll", None)
    if kernel32 is None:
        raise PlatformCapabilityMissing(
            "ctypes.windll 不可用：不在 Windows 上，无法做 CreateFileW "
            "占用探测（调用方必须 BLOCK，不许当作未占用）"
        )
    kernel32 = kernel32.kernel32
    generic_read = 0x80000000
    open_existing = 3
    file_attribute_normal = 0x80
    handle = kernel32.CreateFileW(
        str(path), generic_read, 0, None, open_existing,
        file_attribute_normal, None,
    )
    try:
        if int(handle) == INVALID_HANDLE_VALUE:
            return True
    except (TypeError, ValueError):  # pragma: no cover - 句柄类型异常
        return True
    try:
        kernel32.CloseHandle(handle)
    except Exception:  # pragma: no cover - 关闭失败不影响判定
        pass
    return False


def _posix_file_busy(path: str) -> bool:
    if fcntl is None:
        raise PlatformCapabilityMissing(
            "POSIX 占用探测需要 fcntl.flock；当前环境不可用"
        )
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return True
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
    return False


def file_is_busy(path: str, platform: str | None = None,
                 probe=None) -> bool:
    """文件是否被别的写方占着（占用即视作「仍在写」，不投递）。

    ``probe`` 供测试注入；为空时按平台分派：Windows 走 CreateFileW，
    POSIX 走 flock。能力缺失抛 :class:`PlatformCapabilityMissing`。
    """
    if probe is not None:
        return bool(probe(path))
    if is_windows(platform):
        return _win_file_busy(path)
    return _posix_file_busy(path)


def lock_first_byte(fh, platform: str | None = None) -> None:
    """单实例锁：Windows 用 msvcrt 非阻塞 1-byte 锁（句柄必须一直持有）。"""
    if is_windows(platform):
        try:
            import msvcrt  # 惰性：便于测试注入 sys.modules["msvcrt"]
        except ImportError as exc:
            raise PlatformCapabilityMissing(
                "Windows 单实例锁需要标准库 msvcrt；当前环境不可用，"
                "无法保证单实例（调用方必须 BLOCK）"
            ) from exc
        fh.seek(0)
        msvcrt.locking(fh.fileno(), getattr(msvcrt, "LK_NBLCK", 2), 1)
        return
    if fcntl is None:
        raise PlatformCapabilityMissing(
            "POSIX 单实例锁需要 fcntl.flock；当前环境不可用"
        )
    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def unlock_first_byte(fh, platform: str | None = None) -> None:
    if is_windows(platform):
        try:
            import msvcrt
        except ImportError:
            return
        try:
            fh.seek(0)
            msvcrt.locking(fh.fileno(), getattr(msvcrt, "LK_UNLCK", 0), 1)
        except OSError:
            pass
        return
    if fcntl is None:
        return
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass


# ---- 卷探针 -------------------------------------------------------------
def _win_drive_root(path: str) -> str:
    p = str(path).replace("/", "\\")
    if p.startswith("\\\\?\\UNC\\"):
        rest = p[len("\\\\?\\UNC\\"):].split("\\")
        return "\\\\" + "\\".join(rest[:2])
    if p.startswith("\\\\"):
        parts = p[2:].split("\\")
        return "\\\\" + "\\".join(parts[:2])
    if p.startswith("\\\\?\\"):
        p = p[4:]
    if len(p) >= 2 and p[1] == ":" and p[0].isalpha():
        return p[:2] + "\\"
    return ""


def volume_info(path: str, platform: str | None = None) -> dict:
    """Windows 卷探针：NTFS 判定 + 盘符类型 + 可用空间。

    UNC（\\\\server\\share）一律判 remote（网络盘 BLOCK）。能力不可用抛
    :class:`PlatformCapabilityMissing`，不返回「unknown 但放行」。
    """
    if not is_windows(platform):
        return {"platform": current_platform(platform),
                "supported": False,
                "reason": "非 Windows：沿用既有 macOS 卷探针（stat -f / mount）"}
    if ctypes is None or getattr(ctypes, "windll", None) is None:
        raise PlatformCapabilityMissing(
            "Windows 卷探针需要 ctypes.windll（GetVolumeInformationW / "
            "GetDriveTypeW / GetDiskFreeSpaceExW）；当前环境不可用，"
            "无法判定卷类型（调用方必须 BLOCK）"
        )
    root = _win_drive_root(path)
    info = {
        "path": str(path),
        "drive_root": root,
        "platform": current_platform(platform),
        "supported": True,
        "filesystem_type": "unknown",
        "drive_type": None,
        "local_or_remote": "unknown",
        "free_bytes": None,
        "reason": "",
    }
    if root.startswith("\\\\"):
        info.update(filesystem_type="unknown", local_or_remote="remote",
                    reason="UNC 网络路径（%s）：Windows 端按网络盘 BLOCK" % (root,))
        return info
    if not root:
        info.update(local_or_remote="unknown",
                    reason="无法确定盘符根（%r）：BLOCK" % (str(path),))
        return info
    kernel32 = ctypes.windll.kernel32
    drive_type = int(kernel32.GetDriveTypeW(root))
    info["drive_type"] = drive_type
    if drive_type in (_DRIVE_FIXED, _DRIVE_RAMDISK):
        info["local_or_remote"] = "local"
    elif drive_type in (_DRIVE_REMOTE, _DRIVE_CDROM):
        info["local_or_remote"] = "remote"
    else:
        info["local_or_remote"] = "unknown"
    buf = ctypes.create_unicode_buffer(64)
    try:
        ok = kernel32.GetVolumeInformationW(
            root, None, 0, None, None, None, buf, len(buf)
        )
        if ok:
            info["filesystem_type"] = (buf.value or "unknown").upper()
    except Exception:
        info["filesystem_type"] = "unknown"
    try:
        free = ctypes.c_ulonglong(0)
        total = ctypes.c_ulonglong(0)
        total_free = ctypes.c_ulonglong(0)
        ok = kernel32.GetDiskFreeSpaceExW(
            root, ctypes.byref(free), ctypes.byref(total),
            ctypes.byref(total_free),
        )
        if ok:
            info["free_bytes"] = int(free.value)
    except Exception:
        info["free_bytes"] = None
    info["reason"] = "GetVolumeInformationW/GetDriveTypeW/GetDiskFreeSpaceExW"
    return info


def is_ntfs(path: str, platform: str | None = None) -> bool:
    info = volume_info(path, platform)
    return str(info.get("filesystem_type", "")).upper() == "NTFS"


# ---- UTF-8 --------------------------------------------------------------
def read_text(path: str) -> str:
    with open(path, "r", encoding=ENCODING, errors="replace") as fh:
        return fh.read()


def write_text(path: str, text: str, fsync: bool = True) -> None:
    with open(path, "w", encoding=ENCODING, errors="strict") as fh:
        fh.write(text)
        fh.flush()
        if fsync:
            os.fsync(fh.fileno())


def decode_output(data) -> str:
    """subprocess 输出统一按 UTF-8 + replace 解码（不改系统 code page）。"""
    if data is None:
        return ""
    if isinstance(data, bytes):
        return data.decode(ENCODING, errors="replace")
    return str(data)


def run_argv(argv: list, timeout: float = 10.0) -> subprocess.CompletedProcess:
    """子进程一律传数组（不拼字符串、不经 shell），显式 UTF-8。"""
    return subprocess.run(
        list(argv), capture_output=True, text=True,
        encoding=ENCODING, errors="replace", timeout=timeout,
    )


# ---- ffmpeg（Windows：随包绝对路径优先）---------------------------------
FFMPEG_ENV = "V2O_FFMPEG"
FFMPEG_DIR_PARTS = ("third_party", "ffmpeg", "bin")


def bundle_root() -> str:
    """随包第三方目录的根（``<repo>/third_party``；本文件在 ``<repo>/src``）。"""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        *FFMPEG_DIR_PARTS,
    )


def ffmpeg_resolve(environ: dict | None = None,
                   platform: str | None = None) -> dict:
    """定位 ffmpeg 可执行文件，返回 ``{exe, kind, bundled}``。

    顺序：① ``V2O_FFMPEG`` 指定的绝对路径；② 随包 ``third_party/ffmpeg/bin``
    （Windows 为 ``ffmpeg.exe``，这是交付形态）；③ PATH 里的 ``ffmpeg``（兜底，
    只有前两档都没有时才用，Windows 真机应走前两档）。
    """
    env = os.environ if environ is None else environ
    op = _ops(platform)
    override = str(env.get(FFMPEG_ENV) or "").strip()
    if override:
        if not op.isabs(override):
            raise PlatformCapabilityMissing(
                "环境变量 %s 必须给出 ffmpeg 的绝对路径（不许用相对路径或"
                "只写命令名），否则无法确定用的是哪一个 ffmpeg" % (FFMPEG_ENV,)
            )
        if not os.path.isfile(override):
            raise PlatformCapabilityMissing(
                "环境变量 %s 指向的 ffmpeg 不存在：请在开始监听前把它改成"
                "真实存在的文件路径" % (FFMPEG_ENV,)
            )
        return {"exe": override, "kind": "env", "bundled": False}
    name = "ffmpeg.exe" if is_windows(platform) else "ffmpeg"
    bundled = os.path.join(bundle_root(), name)
    if os.path.isfile(bundled):
        return {"exe": bundled, "kind": "bundled", "bundled": True}
    if is_windows(platform):
        # 交付形态没有随包 ffmpeg 时仍允许 PATH 兜底，但如实记 kind=path，
        # 便于 README/诊断指出「没在用随包那个」。
        return {"exe": name, "kind": "path", "bundled": False}
    return {"exe": name, "kind": "path", "bundled": False}


def ffmpeg_executable(environ: dict | None = None,
                      platform: str | None = None) -> str:
    """ffmpeg 可执行文件路径（数组首项，绝不拼 shell 字符串）。"""
    return ffmpeg_resolve(environ, platform)["exe"]


def ffmpeg_argv(args, environ: dict | None = None,
                platform: str | None = None) -> list:
    """拼 ffmpeg 参数数组：exe + 参数，不用 shell、不用 POSIX 特有写法。"""
    return [ffmpeg_executable(environ, platform)] + [str(a) for a in args]


def run_ffmpeg(args, timeout: float = 600.0, environ: dict | None = None,
               platform: str | None = None) -> subprocess.CompletedProcess:
    """跑一次 ffmpeg：UTF-8 输出、数组传参、超时交给调用方定。"""
    return subprocess.run(
        ffmpeg_argv(args, environ, platform), capture_output=True, text=True,
        encoding=ENCODING, errors="replace", timeout=timeout,
    )


# ---- 进程 ---------------------------------------------------------------
def kill_child(proc, timeout: float = 10.0,
               platform: str | None = None) -> dict:
    """终止子进程：Windows 走 TerminateProcess，不依赖 POSIX signal/负 rc。"""
    if is_windows(platform):
        try:
            proc.kill()
            killed = True
        except Exception as exc:
            return {"killed": False, "returncode": proc.returncode,
                    "killed_by": "TerminateProcess", "error": str(exc),
                    "hard_killed": False}
        try:
            proc.wait(timeout=timeout)
        except Exception:
            pass
        rc = proc.returncode
        return {"killed": killed, "returncode": rc,
                "killed_by": "TerminateProcess",
                "hard_killed": rc is not None}
    import signal

    sig = getattr(signal, "SIGKILL", None)
    if sig is None:
        raise PlatformCapabilityMissing(
            "POSIX SIGKILL 不可用：无法做 kill -9 等价验证"
        )
    try:
        os.kill(proc.pid, sig)
        killed = True
    except ProcessLookupError:
        killed = False
    except Exception as exc:
        return {"killed": False, "returncode": proc.returncode,
                "killed_by": "SIGKILL", "error": str(exc),
                "hard_killed": False}
    try:
        proc.wait(timeout=timeout)
    except Exception:
        pass
    rc = proc.returncode
    return {"killed": killed, "returncode": rc, "killed_by": "SIGKILL",
            "hard_killed": rc is not None and rc == -sig}


def terminate_then_kill(proc, timeout: float = 10.0,
                        platform: str | None = None) -> dict:
    """优雅退出：terminate → wait → kill → wait（不假设负 rc）。"""
    info = {"terminated": False, "killed": False, "waited": False,
            "returncode": None,
            "semantics": "TerminateProcess" if is_windows(platform)
                         else "POSIX signal"}
    try:
        proc.terminate()
        info["terminated"] = True
    except Exception as exc:
        info["error"] = str(exc)
    try:
        proc.wait(timeout=timeout)
        info["waited"] = True
    except Exception:
        try:
            proc.kill()
            info["killed"] = True
        except Exception:
            pass
        try:
            proc.wait(timeout=timeout)
            info["waited"] = True
        except Exception:
            pass
    info["returncode"] = proc.returncode
    return info
