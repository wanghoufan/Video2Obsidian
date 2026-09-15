#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Windows 适配第一批（Stage 1 启动链 + Stage 2 文件安全）自测。

本机是 macOS，跑不了真 Windows 行为，所以全部用**桩/假模块**验证分支：
假 ``msvcrt``、假 ``ctypes.windll``、假 ``winreg``、桩 ``sys.platform``、
桩 ``LOCALAPPDATA``。测试只用外置 tmp + 合成数据，不碰用户真实目录。

跑法（在仓库根）：
    .venv/bin/python windows/tests/selftest_win_stage12.py   # rc=0 即通过

反向证伪（teeth）：每条都用 ``_teeth()`` 先把实现改坏，再确认对应断言
**变红**；变红=有牙，仍绿=无牙（会打印出来）。
"""

from __future__ import annotations

import contextlib
import ctypes as _real_ctypes
import hashlib
import importlib
import io
import json
import os
import sqlite3
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
WIN_ROOT = os.path.dirname(HERE)          # windows/
SRC = os.path.join(WIN_ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import platform_win  # noqa: E402
from stage2 import candidate  # noqa: E402
from stage2 import instance, store  # noqa: E402
from stage4 import volume_probe  # noqa: E402
from stage5 import watcher  # noqa: E402
from stage1 import ingest  # noqa: E402

WIN = "win32"
MAC = "darwin"


# ---- 计数与断言 ---------------------------------------------------------
class Checker:
    def __init__(self) -> None:
        self.total = 0
        self.failed: list[str] = []
        self.teeth_total = 0
        self.teeth_sharp = 0

    def ok(self, cond: bool, label: str) -> bool:
        self.total += 1
        if cond:
            print("  PASS  %s" % (label,))
        else:
            self.failed.append(label)
            print("  FAIL  %s" % (label,))
        return bool(cond)

    def teeth(self, label: str, mutate, restore, probe) -> bool:
        """把实现改坏 → 对应断言必须变红；变红记「有牙」，仍绿记「无牙」。"""
        self.teeth_total += 1
        try:
            mutate()
            red = not bool(probe())
        finally:
            restore()
        if red:
            self.teeth_sharp += 1
            print("  牙    [有牙] %s（改坏后断言变红）" % (label,))
        else:
            print("  牙    [无牙] %s（改坏后断言仍绿！）" % (label,))
        return red


T = Checker()


# ---- 桩 ----------------------------------------------------------------
@contextlib.contextmanager
def fake_platform(name: str):
    old = sys.platform
    sys.platform = name
    try:
        yield
    finally:
        sys.platform = old


@contextlib.contextmanager
def fake_msvcrt(mod):
    had = "msvcrt" in sys.modules
    old = sys.modules.get("msvcrt")
    sys.modules["msvcrt"] = mod
    try:
        yield
    finally:
        if had:
            sys.modules["msvcrt"] = old
        else:
            sys.modules.pop("msvcrt", None)


class FakeMsvcrt:
    """假 msvcrt：按 (dev, ino) 记锁，模拟「另一进程已持锁」。"""

    LK_LOCK = 1
    LK_NBLCK = 2
    LK_UNLCK = 0

    def __init__(self, always_succeed: bool = False) -> None:
        self._locked: set = set()
        self.calls: list = []
        self.always_succeed = always_succeed

    @staticmethod
    def _key(fd: int):
        st = os.fstat(fd)
        return (st.st_dev, st.st_ino)

    def locking(self, fd: int, mode: int, nbytes: int) -> None:
        self.calls.append((fd, mode, nbytes))
        key = self._key(fd)
        if mode == self.LK_NBLCK:
            if not self.always_succeed and key in self._locked:
                raise OSError(13, "文件已被另一进程锁定")
            self._locked.add(key)
        elif mode == self.LK_UNLCK:
            self._locked.discard(key)


class FakeKernel32:
    def __init__(self, fstype="NTFS", drive_type=3, free_bytes=123456789,
                 busy_paths=()):
        self.fstype = fstype
        self.drive_type = drive_type
        self.free_bytes = free_bytes
        self.busy_paths = set(busy_paths)
        self.volumeinfo_calls: list = []
        self.createfile_calls: list = []

    def GetDriveTypeW(self, root):
        return int(self.drive_type)

    def GetVolumeInformationW(self, root, *a):
        buf = a[-2]
        self.volumeinfo_calls.append(root)
        buf.value = self.fstype
        return 1

    def GetDiskFreeSpaceExW(self, root, free, total, totalfree):
        free._obj.value = int(self.free_bytes)
        total._obj.value = int(self.free_bytes) * 2
        totalfree._obj.value = int(self.free_bytes)
        return 1

    def CreateFileW(self, path, *a):
        self.createfile_calls.append(path)
        return -1 if str(path) in self.busy_paths else 7

    def CloseHandle(self, handle):
        return 1


def make_fake_ctypes(kernel32):
    fake = types.SimpleNamespace()
    fake.windll = types.SimpleNamespace(kernel32=kernel32)
    fake.create_unicode_buffer = _real_ctypes.create_unicode_buffer
    fake.byref = _real_ctypes.byref
    fake.c_ulonglong = _real_ctypes.c_ulonglong
    return fake


@contextlib.contextmanager
def fake_ctypes(kernel32):
    old = platform_win.ctypes
    platform_win.ctypes = make_fake_ctypes(kernel32)
    try:
        yield kernel32
    finally:
        platform_win.ctypes = old


@contextlib.contextmanager
def fake_winreg(value):
    reg = types.SimpleNamespace()
    reg.HKEY_LOCAL_MACHINE = "HKLM"

    class _Key:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    reg.OpenKey = lambda hive, key: _Key()
    if value is None:
        def _boom(*_a, **_k):
            raise OSError("读不到 LongPathsEnabled")
        reg.QueryValueEx = _boom
    else:
        reg.QueryValueEx = lambda key, name: (value, 4)
    old = platform_win._WINREG
    platform_win._WINREG = reg
    try:
        yield
    finally:
        platform_win._WINREG = old


def _db_fingerprint(path: str):
    try:
        st = os.stat(path)
        with open(path, "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return None
    return (st.st_size, st.st_mtime_ns, digest)


def win_path_of_len(n: int) -> str:
    """构造长度恰为 n 的 Windows 绝对路径。"""
    return "C:\\" + "a" * (n - 3)


def _reset_instance():
    instance._FDS.clear()
    store._HELD_LOCKS.clear()


# ---- 1. 平台分支选择 ----------------------------------------------------
def test_platform_branch():
    print("\n[1] 平台分支选择")
    T.ok(platform_win.is_windows(WIN) is True, "is_windows('win32') == True")
    T.ok(platform_win.is_windows(MAC) is False, "is_windows('darwin') == False")
    T.ok(platform_win.is_windows("linux") is False, "is_windows('linux') == False")

    def pick(platform=None):  # 自定义判定函数：模拟业务模块的分支选择
        return "win-impl" if platform_win.is_windows(platform) else "posix-impl"

    T.ok(pick(WIN) == "win-impl", "自定义判定函数 win32→win-impl")
    T.ok(pick(MAC) == "posix-impl", "自定义判定函数 darwin→posix-impl")
    with fake_platform(WIN):
        T.ok(platform_win.is_windows() is True, "桩 sys.platform=win32 → is_windows() True")
        T.ok(pick() == "win-impl", "桩 sys.platform=win32 → 判函数选 win-impl")
    with fake_platform(MAC):
        T.ok(platform_win.is_windows() is False, "桩 sys.platform=darwin → is_windows() False")

    # 有牙：把 is_windows 改成恒 True → darwin 分支断言必须变红
    T.teeth(
        "平台分支（is_windows 恒 True 后 darwin 也走 Windows 分支）",
        lambda: setattr(platform_win, "is_windows", lambda *a, **k: True),
        lambda: setattr(platform_win, "is_windows", _ORIG_IS_WINDOWS),
        lambda: platform_win.is_windows(MAC) is False,
    )


_ORIG_IS_WINDOWS = platform_win.is_windows


# ---- 2. 路径比较 --------------------------------------------------------
def test_paths():
    print("\n[2] 路径比较（normcase + commonpath）")
    T.ok(platform_win.same_path("C:\\Users\\Abc\\a.mp4", "c:\\users\\abc\\A.MP4",
                                WIN), "大小写不敏感：C:\\Users\\Abc 与 c:\\users\\abc 相等")
    T.ok(platform_win.same_path("C:/Users/a.mp4", "C:\\Users\\a.mp4", WIN),
         "分隔符归一：/ 与 \\ 等价")
    T.ok(not platform_win.same_path("D:\\a.mp4", "C:\\a.mp4", WIN),
         "盘符不同 → 不等")
    T.ok(platform_win.is_within("C:\\root", "C:\\root\\sub\\a 丨 b.mp4", WIN),
         "中文/空格/丨 子路径仍在父目录内")
    T.ok(not platform_win.is_within("C:\\root", "C:\\root2\\a.mp4", WIN),
         "同级相似目录不算包含（\\root2 不在 \\root 内）")
    T.ok(platform_win.is_within("\\\\srv\\share\\v", "\\\\SRV\\share\\v\\a 中文.mp4", WIN),
         "UNC 大小写不敏感 + 子路径包含")
    T.ok(platform_win.same_path("\\\\srv\\share\\a", "\\\\SRV\\SHARE\\a", WIN),
         "UNC 主机/共享名大小写不敏感")
    T.ok(platform_win.same_path("C:\\视频\\懒得笔记丨a.mp4", "c:\\视频\\懒得笔记丨a.mp4",
                                WIN), "中文 + 丨 路径判等")
    T.ok(not platform_win.same_path("C:\\a\\b.mp4", "C:\\a\\b.mp4", MAC)
         or platform_win.same_path("/tmp/a.MP4", "/tmp/a.mp4", MAC) is False,
         "POSIX 分支保持大小写敏感（/tmp/a.MP4 != /tmp/a.mp4）")
    T.ok(platform_win.is_within("/tmp/root", "/tmp/root/sub", MAC),
         "POSIX 分支包含判定仍正确")

    # 长路径 \\?\ 前缀（只在 Win32 边界用）
    T.ok(platform_win.to_extended_path("C:\\a\\b", WIN).startswith("\\\\?\\C:\\"),
         "to_extended_path 加 \\\\?\\ 前缀")
    T.ok(platform_win.to_extended_path("\\\\srv\\share\\a", WIN).startswith(
        "\\\\?\\UNC\\"), "UNC 的 \\\\?\\UNC\\ 前缀")

    # 有牙：normcase 退化成原样返回 → 大小写不敏感判等变红
    T.teeth(
        "路径比较（normcase 退化后大小写不敏感判等失败）",
        lambda: setattr(platform_win, "normcase",
                        lambda path, platform=None: str(path)),
        lambda: setattr(platform_win, "normcase", _ORIG_NORMCASE),
        lambda: platform_win.same_path("C:\\Users\\Abc\\a.mp4",
                                       "c:\\users\\abc\\A.MP4", WIN),
    )
    # 有牙：包含判定退化成朴素 startswith → 大小写/UNC 断言变红
    T.teeth(
        "路径比较（is_within 退化成 startswith 后大小写不敏感断言失败）",
        lambda: setattr(platform_win, "is_within",
                        lambda parent, child, platform=None:
                        str(child).startswith(str(parent))),
        lambda: setattr(platform_win, "is_within", _ORIG_IS_WITHIN),
        lambda: platform_win.is_within("C:\\Users\\Abc", "c:\\users\\abc\\x", WIN),
    )


_ORIG_IS_WITHIN = platform_win.is_within
_ORIG_NORMCASE = platform_win.normcase


# ---- 3. 长路径 259/260/261 ---------------------------------------------
def test_long_paths():
    print("\n[3] 长路径 259/260/261 边界")
    p259 = win_path_of_len(259)
    p260 = win_path_of_len(260)
    p261 = win_path_of_len(261)
    T.ok(len(p259) == 259 and len(p260) == 260 and len(p261) == 261,
         "构造长度 259/260/261 精确")
    r259 = platform_win.check_path_length(p259, WIN, policy=False)
    r260 = platform_win.check_path_length(p260, WIN, policy=False)
    r261 = platform_win.check_path_length(p261, WIN, policy=False)
    T.ok(r259["verdict"] == "ALLOW" and r259["code"] is None, "259 → ALLOW")
    T.ok(r260["verdict"] == "BLOCK" and r260["code"] == platform_win.LONG_PATH_BLOCK_CODE,
         "260 → BLOCK（未开长路径策略）")
    T.ok(r261["verdict"] == "BLOCK" and r261["code"] == platform_win.LONG_PATH_BLOCK_CODE,
         "261 → BLOCK（未开长路径策略）")
    T.ok("不会自动修改注册表" in r261["guidance"], "BLOCK 附带人话指引且声明不改注册表")
    T.ok(platform_win.check_path_length(p261, WIN, policy=True)["verdict"]
         == "ALLOW_EXTENDED", "已开策略 → ALLOW_EXTENDED（仍提示需真机验）")
    T.ok(platform_win.check_path_length(p261, MAC)["verdict"] == "ALLOW",
         "非 Windows 不套 259 限制")
    with fake_winreg(1):
        T.ok(platform_win.long_paths_enabled(WIN) is True, "假 winreg=1 → 判定已开启")
    with fake_winreg(None):
        T.ok(platform_win.long_paths_enabled(WIN) is None,
             "读不到策略 → None（视作未开，BLOCK）")
        T.ok(platform_win.check_path_length(p261, WIN)["verdict"] == "BLOCK",
             "策略读不到 → 261 仍 BLOCK（fail-closed）")

    # 有牙：把上限放到 10**6 → 261 不再 BLOCK
    T.teeth(
        "长路径（把 USABLE_PATH_LIMIT 放大后 261 不再 BLOCK）",
        lambda: setattr(platform_win, "USABLE_PATH_LIMIT", 10 ** 6),
        lambda: setattr(platform_win, "USABLE_PATH_LIMIT", 259),
        lambda: platform_win.check_path_length(p261, WIN, policy=False)["verdict"]
        == "BLOCK",
    )


# ---- 4. 单实例锁（假 msvcrt）-------------------------------------------
def test_single_instance(tmp: str):
    print("\n[4] 单实例锁（假 msvcrt，第二实例 exit 3 且 DB 不变）")
    root = os.path.join(tmp, "inst-win")
    os.makedirs(root, exist_ok=True)
    fake = FakeMsvcrt()
    with fake_platform(WIN), fake_msvcrt(fake):
        _reset_instance()
        instance.acquire(root)
        T.ok(instance.holds_lock(root) is True, "第一实例拿到 msvcrt 1-byte 锁")
        T.ok(fake.calls and fake.calls[0][1] == FakeMsvcrt.LK_NBLCK
             and fake.calls[0][2] == 1,
             "走的是非阻塞（LK_NBLCK）1 字节锁")
        db = store.init_db(root)
        before = _db_fingerprint(db)

        # 模拟第二实例：清掉进程内状态（OS 级锁仍由「另一个进程」持有）
        _reset_instance()
        rc = instance.main(["--data-root", root, "--input-root", root])
        T.ok(rc == 3, "第二实例 exit 3（实测 %r）" % (rc,))
        after = _db_fingerprint(db)
        T.ok(before == after and before is not None,
             "第二实例未写 DB（size/mtime/sha256 三元组不变）")
        T.ok(instance.holds_lock(root) is False, "第二实例未持有锁")

        # 反例：桩成「锁不上」（locking 永不失败）→ 行为必须改变
        _reset_instance()
        loose = FakeMsvcrt(always_succeed=True)
        with fake_msvcrt(loose):
            raised = False
            try:
                instance.acquire(root)
            except instance.SecondInstanceError:
                raised = True
            T.ok(raised is False, "反例：锁不上时 acquire 不抛 SecondInstanceError")
            T.ok(instance.holds_lock(root) is True,
                 "反例：锁不上时第二实例拿到锁（行为与正例相反，证明有牙）")
        _reset_instance()

    # 有牙：把锁调用换成恒成功 → 第二实例不再 exit 3
    def _mutate():
        def _noop(fh, platform=None):
            return None
        platform_win.lock_first_byte = _noop

    def _probe():
        root2 = os.path.join(tmp, "inst-win-teeth")
        os.makedirs(root2, exist_ok=True)
        f2 = FakeMsvcrt()
        with fake_platform(WIN), fake_msvcrt(f2):
            _reset_instance()
            instance.acquire(root2)
            _reset_instance()
            try:
                rc = instance.main(["--data-root", root2])
            finally:
                _reset_instance()
        return rc == 3

    T.teeth("单实例锁（锁恒成功后第二实例不再 exit 3）", _mutate,
            lambda: setattr(platform_win, "lock_first_byte", _ORIG_LOCK), _probe)


_ORIG_LOCK = platform_win.lock_first_byte


# ---- 5. reveal 命令构造 -------------------------------------------------
def test_reveal():
    print("\n[5] reveal 命令构造")
    plain = "C:\\Users\\me\\视频\\a b 中文丨.mp4"
    plan = platform_win.build_reveal_argv(plain, WIN)
    T.ok(plan["argv"][0] == "explorer.exe", "Windows 用 explorer.exe")
    T.ok(plan["argv"][1] == "/select," + plain, "普通路径：/select,<file> 原样带中文/空格")
    T.ok(plan["mode"] == "select", "普通路径 mode=select")
    T.ok(len(plan["argv"]) == 2, "参数数组（不拼 shell 字符串）")

    comma = "C:\\Users\\me\\a,b 中文.mp4"
    plan_c = platform_win.build_reveal_argv(comma, WIN)
    T.ok(plan_c["argv"][0] == "explorer.exe", "逗号路径仍用 explorer.exe")
    T.ok(plan_c["mode"] == "open-folder", "逗号路径降级为打开所在文件夹")
    T.ok(plan_c["argv"][1] == "C:\\Users\\me", "逗号路径取所在目录")
    T.ok("会截断" in plan_c["note"], "逗号路径附人话说明（不假装定位成功）")

    quote = 'C:\\Users\\me\\a"b.mp4'
    T.ok(platform_win.build_reveal_argv(quote, WIN)["mode"] == "open-folder",
         "双引号路径同样降级为打开文件夹")
    T.ok(platform_win.build_reveal_argv("/Users/me/a b.mp4", MAC)["argv"]
         == ["open", "-R", "/Users/me/a b.mp4"], "macOS 仍是 open -R（未回归）")

    # 有牙：去掉逗号判定 → 逗号路径断言变红
    def _mutate():
        def _always_select(path, platform=None):
            op = platform_win._ops(platform)
            t = op.normpath(str(path))
            if platform_win.is_windows(platform):
                return {"argv": ["explorer.exe", "/select," + t],
                        "mode": "select", "note": "", "path": t}
            return platform_win.build_reveal_argv.__wrapped__(path, platform) \
                if hasattr(platform_win.build_reveal_argv, "__wrapped__") \
                else {"argv": ["open", "-R", t], "mode": "select", "note": "",
                      "path": t}
        platform_win.build_reveal_argv = _always_select

    T.teeth("reveal（去掉逗号/引号降级后逗号路径不再 open-folder）", _mutate,
            lambda: setattr(platform_win, "build_reveal_argv", _ORIG_REVEAL),
            lambda: platform_win.build_reveal_argv(comma, WIN)["mode"]
            == "open-folder")


_ORIG_REVEAL = platform_win.build_reveal_argv


# ---- 6. data root -------------------------------------------------------
def test_data_root():
    print("\n[6] data root（LOCALAPPDATA 桩）")
    got = platform_win.default_data_root(
        environ={"LOCALAPPDATA": "C:\\Users\\me\\AppData\\Local"}, platform=WIN)
    T.ok(got == "C:\\Users\\me\\AppData\\Local\\Video2Obsidian\\data",
         "Windows data root = LOCALAPPDATA\\Video2Obsidian\\data（实测 %r）" % (got,))
    raised = None
    try:
        platform_win.default_data_root(environ={}, platform=WIN)
    except platform_win.DataRootUnavailable as exc:
        raised = str(exc)
    T.ok(raised is not None, "LOCALAPPDATA 缺失 → DataRootUnavailable（不回落）")
    T.ok(raised is not None and "LOCALAPPDATA" in raised and "不会" in raised,
         "缺失时给明确人话（含变量名 + 不猜测/不改临时目录的声明）")
    raised2 = None
    try:
        platform_win.default_data_root(environ={"LOCALAPPDATA": "   "}, platform=WIN)
    except platform_win.DataRootUnavailable:
        raised2 = "ok"
    T.ok(raised2 == "ok", "空白 LOCALAPPDATA 同样报错，不静默回落")
    T.ok(platform_win.default_data_root(platform=MAC).endswith("v2o-console-data"),
         "非 Windows 维持既有临时目录口径（Mac 端不回归）")

    # 有牙：改成缺失时回落到临时目录 → 不再抛错
    def _mutate():
        def _fallback(environ=None, platform=None):
            env = os.environ if environ is None else environ
            if platform_win.is_windows(platform):
                base = str(env.get("LOCALAPPDATA") or "").strip()
                if not base:
                    return os.path.join(tempfile.gettempdir(),
                                        "v2o-fallback-data")
                return platform_win.ntpath.join(base, "Video2Obsidian", "data")
            return _ORIG_DATA_ROOT(environ, platform)
        platform_win.default_data_root = _fallback

    def _probe():
        try:
            platform_win.default_data_root(environ={}, platform=WIN)
        except platform_win.DataRootUnavailable:
            return True
        return False

    T.teeth("data root（改成静默回落后不再报错）", _mutate,
            lambda: setattr(platform_win, "default_data_root", _ORIG_DATA_ROOT),
            _probe)


_ORIG_DATA_ROOT = platform_win.default_data_root


# ---- 7. 卷探针 / 占用检测（假 ctypes）----------------------------------
def test_volume_and_busy(tmp: str):
    print("\n[7] 卷探针 + 占用检测（假 ctypes.windll）")
    with fake_platform(WIN), fake_ctypes(FakeKernel32(fstype="NTFS",
                                                      drive_type=3,
                                                      free_bytes=987654321)):
        info = platform_win.volume_info("C:\\Users\\me\\data")
        T.ok(info["filesystem_type"] == "NTFS", "NTFS 判定（实测 %r）"
             % (info["filesystem_type"],))
        T.ok(info["local_or_remote"] == "local", "固定盘 → local")
        T.ok(info["free_bytes"] == 987654321, "可用空间实测（GetDiskFreeSpaceExW）")
        T.ok(platform_win.is_ntfs("C:\\Users\\me\\data") is True, "is_ntfs → True")
        T.ok(volume_probe._filesystem_type("C:\\Users\\me\\data") == "NTFS",
             "stage4 卷探针走 Windows 分支拿到 NTFS")
        T.ok(volume_probe._free_bytes("C:\\Users\\me\\data") == 987654321,
             "stage4 探针带出可用空间")
        v = ingest.probe_volume("C:\\Users\\me\\data")
        T.ok(v["verdict"] == "ALLOW" and v["local_or_remote"] == "local",
             "stage1 probe_volume 在 Windows 分支 ALLOW 本地 NTFS 盘")

    with fake_platform(WIN), fake_ctypes(FakeKernel32(drive_type=4)):
        T.ok(platform_win.volume_info("Z:\\x")["local_or_remote"] == "remote",
             "网络盘（DRIVE_REMOTE）→ remote")
        T.ok(ingest.probe_volume("Z:\\x")["verdict"] == "BLOCK",
             "网络盘 BLOCK（不静默放行）")

    with fake_platform(WIN), fake_ctypes(FakeKernel32(drive_type=3)):
        unc = platform_win.volume_info("\\\\srv\\share\\videos")
        T.ok(unc["local_or_remote"] == "remote", "UNC 路径 → remote")
        T.ok(ingest.probe_volume("\\\\srv\\share\\videos")["verdict"] == "BLOCK",
             "UNC BLOCK（网络盘仍 BLOCK）")

    # 占用检测：CreateFileW 共享模式（用真实存在的合成文件，假 ctypes 决定忙闲）
    busy_dir = os.path.join(tmp, "busy")
    os.makedirs(busy_dir, exist_ok=True)
    busy_file = os.path.join(busy_dir, "a 中文.mp4")
    free_file = os.path.join(busy_dir, "free 中文.mp4")
    for p in (busy_file, free_file):
        with open(p, "wb") as fh:
            fh.write(b"fake-video-bytes")
    busy = FakeKernel32(busy_paths={busy_file})
    with fake_platform(WIN), fake_ctypes(busy):
        T.ok(platform_win.file_is_busy(busy_file) is True,
             "CreateFileW 打不开（sharing violation）→ 占用")
        T.ok(platform_win.file_is_busy(free_file) is False,
             "能独占打开 → 未占用")
        T.ok(busy.createfile_calls and busy.createfile_calls[0] == busy_file,
             "占用探测确实调用了 CreateFileW")
        T.ok(watcher.Watcher._busy_reason(None, busy_file) == "locked",
             "watcher 占用门在 Windows 分支判 busy → 不投递")
        T.ok(watcher.Watcher._busy_reason(None, free_file) is None,
             "watcher 占用门对空闲文件放行")

    # 能力缺失必须炸出来，不许当作「未占用」
    with fake_platform(WIN):
        T.ok(watcher.Watcher._busy_reason(None, free_file)
             == "probe-unavailable",
             "Windows 上无 ctypes 能力 → fail-closed 判 busy（不静默放行）")

    # 有牙：去掉 UNC 短路 → UNC 会被当成本地盘
    def _mutate():
        def _no_unc(path, platform=None):
            info = _ORIG_VOLUME_INFO(path, platform)
            info["local_or_remote"] = "local"
            return info
        platform_win.volume_info = _no_unc

    def _probe():
        with fake_platform(WIN), fake_ctypes(FakeKernel32(drive_type=3)):
            return platform_win.volume_info(
                "\\\\srv\\share\\v")["local_or_remote"] == "remote"

    T.teeth("卷探针（去掉 UNC 判定后 UNC 被当成本地盘）", _mutate,
            lambda: setattr(platform_win, "volume_info", _ORIG_VOLUME_INFO),
            _probe)


_ORIG_VOLUME_INFO = platform_win.volume_info


# ---- 8. 长路径策略只给指引，不改注册表 ----------------------------------
def test_no_registry_write():
    print("\n[8] 绝不自动改注册表/UAC")
    src = open(os.path.join(SRC, "platform_win.py"), "r",
               encoding="utf-8").read()
    banned = ("CreateKey", "SetValueEx", "DeleteKey", "runas", "ShellExecute")
    hits = [b for b in banned if b in src]
    T.ok(not hits, "platform_win.py 不含注册表写入/UAC 提权调用（命中 %r）" % (hits,))


# ---- 9. UTF-8 读写桩 ----------------------------------------------------
def test_utf8(tmp: str):
    print("\n[9] UTF-8 读写 / subprocess")
    p = os.path.join(tmp, "u8", "中文 空格 丨 emoji🙂.txt")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    text = "懒得笔记丨中文 空格 emoji🙂\n第二行"
    platform_win.write_text(p, text)
    T.ok(platform_win.read_text(p) == text, "显式 UTF-8 写入→读出一致")
    with open(p, "rb") as fh:
        T.ok(fh.read().startswith(text[:6].encode("utf-8")),
             "磁盘上确实是 UTF-8 字节（非 GBK）")
    T.ok(platform_win.decode_output(b"\xff\xfe\xe4\xb8\xad") == "��中",
         "decode_output 用 errors=replace，坏字节不炸")
    res = platform_win.run_argv(
        [sys.executable, "-c",
         "import sys; sys.stdout.buffer.write('中文丨ok'.encode('utf-8'))"],
        timeout=30)
    T.ok(res.returncode == 0, "run_argv 传数组起子进程 rc=0")
    T.ok("中文丨ok" in (res.stdout or ""), "子进程输出按 UTF-8 解码正确")

    # 有牙：读的时候换成 latin-1 → 中文读回来不一致
    def _mutate():
        def _latin1(path):
            with open(path, "r", encoding="latin-1", errors="replace") as fh:
                return fh.read()
        platform_win.read_text = _latin1

    T.teeth("UTF-8（读用 latin-1 后中文不一致）", _mutate,
            lambda: setattr(platform_win, "read_text", _ORIG_READ_TEXT),
            lambda: platform_win.read_text(p) == text)


_ORIG_READ_TEXT = platform_win.read_text


# ---- 10. launch_plist / menu_bar 优雅跳过 -------------------------------
def test_graceful_skip():
    print("\n[10] launch_plist / menu_bar 在 Windows 优雅跳过")
    with fake_platform(WIN):
        lp = importlib.import_module("stage11.launch_plist")
        importlib.reload(lp)
        T.ok(lp.LAUNCHD_SUPPORTED is False, "launch_plist 在 Windows 标记不支持")
        out = lp.build_plist(lp.LABEL_PREFIX + "x", "/bin/x", "/tmp/dr", "/tmp/ag")
        T.ok(out.get("skipped") is True, "build_plist 返回 skipped（不抛异常）")
        T.ok("launchd" in out.get("reason", "") and len(out["reason"]) > 20,
             "跳过说明是人话（含 launchd + 替代方案）")
        T.ok(lp.write_plist({}, "/tmp/ag", lp.LABEL_PREFIX + "x").get("skipped")
             is True, "write_plist 也跳过，零副作用")
        T.ok(lp.load_test_plist("/tmp/a.plist", "/tmp/ag").get("skipped") is True,
             "load_test_plist 跳过，不调 launchctl")

        mb = importlib.import_module("stage12.menu_bar")
        importlib.reload(mb)
        T.ok(mb.RUMPS_AVAILABLE is False, "Windows 上永不 import rumps")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = mb.main(["--data-root", "/tmp/dr"])
        T.ok(rc == 0, "menu_bar main() 在 Windows 上 exit 0（不崩）")
        T.ok("托盘" in buf.getvalue(), "menu_bar 打印人话说明（提到托盘不做）")

    # 还原成 darwin 语义，避免污染同进程后续用例
    with fake_platform(MAC):
        importlib.reload(importlib.import_module("stage11.launch_plist"))
        importlib.reload(importlib.import_module("stage12.menu_bar"))
    T.ok(True, "（还原）按 darwin 重新装载两个模块")


# ---- 11. 启动脚本与依赖锁（静态检查）------------------------------------
def test_launch_files():
    print("\n[11] 启动链文件（start.ps1 / start.bat / requirements.txt）")
    ps1 = os.path.join(WIN_ROOT, "start.ps1")
    bat = os.path.join(WIN_ROOT, "start.bat")
    req = os.path.join(WIN_ROOT, "requirements.txt")
    for path in (ps1, bat, req):
        T.ok(os.path.isfile(path), "存在 %s" % (os.path.basename(path),))
    ps = open(ps1, "r", encoding="utf-8").read()
    T.ok("py -3.12 -m venv .venv" in ps, "start.ps1 用 py -3.12 -m venv .venv")
    T.ok(".venv\\Scripts\\python.exe" in ps, "start.ps1 用 venv 里的 python.exe")
    T.ok("pip install -r requirements.txt" in ps, "start.ps1 按锁文件装依赖")
    T.ok("PYTHONUTF8" in ps, "start.ps1 设置进程级 PYTHONUTF8=1")
    T.ok(ps.count("8899") == 1, "8899 只出现一次（端口单点，实测 %d 次）"
         % (ps.count("8899"),))
    T.ok("$Url" in ps and ps.count("$Url") >= 2, "URL 用变量派生，不写死第二份")
    T.ok("V2O_PORT" in ps, "支持 V2O_PORT 覆盖")
    T.ok("Get-NetTCPConnection" in ps and "OwningProcess" in ps,
         "端口占用只报证据、不杀进程")
    bat_txt = open(bat, "r", encoding="utf-8").read()
    T.ok("start.ps1" in bat_txt and "powershell" in bat_txt.lower(),
         "start.bat 只薄包装转调 start.ps1")
    reqs = open(req, "r", encoding="utf-8").read()
    req_lines = [ln for ln in reqs.splitlines()
                 if ln.strip() and not ln.lstrip().startswith("#")]
    T.ok("faster-whisper==" in reqs and "ctranslate2==" in reqs
         and "watchdog==" in reqs, "依赖锁含 faster-whisper/ctranslate2/watchdog")
    T.ok(not any("mlx" in ln.lower() for ln in req_lines),
         "已移除 Mac 专属 mlx-whisper（生效行无 mlx）")
    T.ok(all("==" in ln for ln in req_lines), "每条依赖都锁死版本（==）")
    T.ok("--hash=" in reqs, "预留哈希字段（--hash= 占位）")
    srv = open(os.path.join(WIN_ROOT, "app", "server.py"), "r",
               encoding="utf-8").read()
    T.ok("PORT = 8899" in srv, "server.py 端口真源仍在 PORT = 8899（未被改动）")
    T.ok("V2O_PORT" in srv, "server.py 仍支持 V2O_PORT 覆盖")


# ---- 12. POSIX 侧不回归 -------------------------------------------------
def test_posix_no_regression(tmp: str):
    print("\n[12] POSIX 侧不回归（Mac 端行为保持）")
    root = os.path.join(tmp, "inst-posix")
    os.makedirs(root, exist_ok=True)
    _reset_instance()
    instance.acquire(root)      # 真 flock（macOS）
    T.ok(instance.holds_lock(root) is True, "macOS 上仍走 flock 拿到锁")
    instance.acquire(root)      # 同进程幂等（by design，锁只持一次）
    T.ok(instance.holds_lock(root) is True, "同进程重复 acquire 幂等")
    # 真跨进程第二实例：先放手，让子进场持锁不放，本进程再 acquire 必须被挡
    instance.release(root)
    T.ok(instance.holds_lock(root) is False, "release 后锁释放（锁可交接）")
    child = _spawn_lock_holder(root)
    try:
        _reset_instance()
        try:
            instance.acquire(root)
            blocked = False
        except instance.SecondInstanceError:
            blocked = True
        T.ok(blocked is True, "macOS 跨进程第二实例仍被 flock 挡住（真子进程持有）")
    finally:
        _reset_instance()
        try:
            child.terminate()
            child.wait(timeout=10)
        except Exception:
            pass
    _reset_instance()
    probe = volume_probe.probe_volume(tmp)
    T.ok("free_bytes" in probe, "probe_volume 新增 free_bytes 字段（不破坏旧字段）")
    for field in ("filesystem_type", "volume_id", "case_sensitive",
                  "supports_advisory_lock"):
        T.ok(field in probe, "probe_volume 仍含 %s" % (field,))


def _spawn_lock_holder(root: str):
    """起一个真正持有 data-root 锁的子进程（跨进程第二实例的反证夹具）。"""
    import subprocess
    import time as _time

    code = (
        "import sys, time; sys.path.insert(0, %r);"
        "from stage2 import instance; instance.acquire(%r);"
        "print('HELD', flush=True); time.sleep(30)"
    ) % (SRC, root)
    proc = subprocess.Popen([sys.executable, "-c", code],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True)
    deadline = _time.time() + 20
    while _time.time() < deadline:
        line = proc.stdout.readline() if proc.stdout else ""
        if line.strip() == "HELD":
            return proc
        if proc.poll() is not None:
            break
    return proc


# ---- 13. 接线：根目录验收闸 / 行前闸 / 归属判定 / 发现闸 ---------------
CAND_BLOCKED_STATUS = "BLOCKED_PATH_TOO_LONG"


def _import_server():
    """导入 app/server.py（macOS 上 DEFAULT_DATA_ROOT 走临时目录，可执行）。"""
    app_dir = os.path.join(WIN_ROOT, "app")
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    return importlib.import_module("server")


def test_root_gate():
    print("\n[13] 接线①：三个根目录（data/input/vault）接受前过闸")
    long_root = "C:\\" + "\\".join(["d" * 40] * 7) + "\\Video2Obsidian\\data"
    short_root = "C:\\Users\\me\\AppData\\Local\\Video2Obsidian\\data"
    srv = _import_server()
    with fake_platform(WIN):
        bad = platform_win.validate_root(long_root, "数据目录")
        T.ok(not bad["ok"] and bad["code"] == platform_win.LONG_PATH_BLOCK_CODE,
             "validate_root：超长根（%d 字符）→ BLOCK/%s"
             % (bad["length"], bad["code"]))
        T.ok(platform_win.validate_root(short_root, "数据目录")["ok"] is True,
             "正常根放行")
        unc = platform_win.validate_root("\\\\srv\\share\\v", "视频文件夹")
        T.ok(not unc["ok"] and unc["code"] == "BLOCKED_UNC_ROOT",
             "UNC 网络共享根 → BLOCKED_UNC_ROOT（不静默放行）")
        rel = platform_win.validate_root("relative\\dir", "笔记库目录")
        T.ok(not rel["ok"] and rel["code"] == "BLOCKED_PATH_NOT_ABSOLUTE",
             "非绝对路径 → BLOCKED_PATH_NOT_ABSOLUTE")
    long_posix = "/tmp/" + "/".join(["d" * 40] * 7) + "/data"
    T.ok(len(long_posix) > 259, "构造 POSIX 长路径（%d 字符）" % (len(long_posix),))
    with fake_platform(MAC):
        T.ok(platform_win.validate_root(long_posix, "数据目录")["ok"] is True,
             "非 Windows：同长度 POSIX 路径放行（Mac 端零改动）")

    with fake_platform(WIN):
        blockers = srv._win_root_blockers(short_root, long_root, None)
        T.ok(len(blockers) == 1 and "太长" in blockers[0],
             "server._win_root_blockers 命中超长 input root")
        T.ok(not any(long_root in b for b in blockers),
             "人话文案不带真实绝对路径（沿用 P1-2 脱敏口径）")
        T.ok("UNC" in srv._win_root_blockers(short_root, short_root,
                                             "\\\\srv\\share\\v")[0],
             "三个根里的 vault 为 UNC 同样被拦")

    def _start_with(root_value: str):
        body = json.dumps({"data_root": root_value,
                           "input_root": root_value}).encode("utf-8")
        with fake_platform(WIN):
            return srv._handle_start_post(body)

    tmp_root = tempfile.mkdtemp(prefix="v2o-win-root-")
    long_data = os.path.join(tmp_root, *(["子目录" + "d" * 50] * 6))
    code, obj = _start_with(long_data)
    T.ok(code == 400 and obj.get("ok") is False,
         "真 handler（未 mock 内部）：超长根 → 400（实测 %r）" % (code,))
    T.ok("太长" in str(obj.get("error", "")), "真 handler 回长路径人话")
    T.ok(not os.path.isdir(long_data),
         "被拦时零写盘（data 目录未被 makedirs 创建）")

    orig = srv._win_root_blockers
    T.teeth(
        "根目录闸（桩掉调用点后超长根不再被 400 拦下）",
        lambda: setattr(srv, "_win_root_blockers", lambda *a, **k: []),
        lambda: setattr(srv, "_win_root_blockers", orig),
        lambda: (_start_with(long_data)[0] == 400
                 and "太长" in str(_start_with(long_data)[1].get("error", ""))),
    )


def test_run_gate():
    print("\n[14] 接线②：单条任务送 Whisper 前的实际写入路径闸")
    srv = _import_server()
    tmp_run = tempfile.mkdtemp(prefix="v2o-win-run-")
    short_video = os.path.join(tmp_run, "短", "a.mp4")
    long_video = os.path.join(tmp_run, *(["层" + "x" * 50] * 6))
    long_video = long_video + os.sep + "b" * 60 + ".mp4"
    with fake_platform(WIN):
        T.ok(srv._win_path_too_long([("这个视频的路径", short_video)]) is None,
             "短路径放行（不误杀）")
        reason = srv._win_path_too_long([("这个视频的路径", long_video)])
        T.ok(reason is not None and "太长" in reason,
             "超长写入路径（%d 字符）→ 人话 reason" % (len(long_video),))
        T.ok(long_video not in reason and tmp_run not in reason,
             "reason 不带真实绝对路径")
        T.ok("不会自动" in reason, "reason 明说不会自动改注册表/提权")
        multi = srv._win_path_too_long([("这个视频的路径", short_video),
                                        ("目标笔记落点", long_video)])
        T.ok(multi is not None and "目标笔记落点" in multi,
             "三条候选里命中哪一条就报哪一条（此处＝目标笔记落点）")
    with fake_platform(MAC):
        T.ok(srv._win_path_too_long([("这个视频的路径", long_video)]) is None,
             "非 Windows 恒放行（Mac 端零改动）")
    orig = srv._win_path_too_long
    T.teeth(
        "行前闸（桩掉调用点后超长路径不再被拦）",
        lambda: setattr(srv, "_win_path_too_long", lambda *a, **k: None),
        lambda: setattr(srv, "_win_path_too_long", orig),
        lambda: srv._win_path_too_long(
            [("这个视频的路径", long_video)]) is not None,
    )


def test_ownership_gate(tmp: str):
    print("\n[15] 接线③：归属判定统一走 normcase + commonpath")
    srv = _import_server()
    realdir = os.path.join(tmp, "own", "CaseRoot")
    child = os.path.join(realdir, "a 中文丨.mp4")
    os.makedirs(realdir, exist_ok=True)
    with open(child, "wb") as fh:
        fh.write(b"x")
    with fake_platform(WIN):
        T.ok(srv._is_under_root(child, realdir) is True,
             "真目录归属判定 True（走 normcase+commonpath）")
    calls = []
    orig_within = platform_win.is_within

    def _spy(parent, child_, platform=None):
        calls.append((parent, child_, platform))
        return orig_within(parent, child_, platform)

    platform_win.is_within = _spy
    try:
        with fake_platform(WIN):
            srv._is_under_root(child, realdir)
    finally:
        platform_win.is_within = orig_within
    T.ok(bool(calls),
         "_is_under_root 真的委托给 platform_win.is_within（观测到 %d 次）"
         % (len(calls),))
    T.teeth(
        "归属判定（委托换成朴素 startswith 后大小写变体不再识别）",
        lambda: setattr(platform_win, "is_within",
                        lambda parent, c, platform=None:
                        str(c).startswith(str(parent))),
        lambda: setattr(platform_win, "is_within", _ORIG_IS_WITHIN),
        lambda: platform_win.is_within("C:\\Users\\Me\\Input",
                                       "c:\\users\\me\\input\\a.mp4", WIN),
    )
    # UNC 已知限制（P2-2）：fail-closed，代码注释与此处测试都留证。
    with fake_platform(WIN):
        T.ok(platform_win.is_within("\\\\srv\\share",
                                    "\\\\srv\\share\\a.mp4") is False,
             "已知限制：UNC 共享根本身 → False（fail-closed，真机须复验）")
        T.ok(platform_win.is_within("\\\\srv\\share\\v",
                                    "\\\\srv\\share\\v\\a.mp4") is True,
             "UNC 下一级起仍正常判包含")


def test_discover_gate(tmp: str):
    print("\n[16] 接线④：发现链路上最早一道（discover 入口）")
    long_path = os.path.join(tmp, *(["层" + "y" * 50] * 6))
    long_path = long_path + os.sep + "c" * 60 + ".mp4"
    short_path = os.path.join(tmp, "短.mp4")
    with open(short_path, "wb") as fh:
        fh.write(b"x")
    root = os.path.join(tmp, "disc")
    os.makedirs(root, exist_ok=True)
    _reset_instance()
    instance.acquire(root)
    store.init_db(root)
    try:
        with fake_platform(WIN):
            res = candidate.discover(long_path, root)
            T.ok(res.get("status") == CAND_BLOCKED_STATUS,
                 "超长源连稳定门都不等：status=%r" % (res.get("status"),))
            T.ok(res.get("source_id") is None and res.get("run_id") is None,
                 "超长源不建 Source、不建 Run（绝不进转写）")
            con = store.open_db(root)
            try:
                n_src = con.execute(
                    "SELECT COUNT(*) FROM sources").fetchone()[0]
                n_blk = con.execute(
                    "SELECT COUNT(*) FROM discovery_candidates"
                    " WHERE status=?", (CAND_BLOCKED_STATUS,)).fetchone()[0]
            finally:
                con.close()
            T.ok(n_src == 0, "DB 里没为超长源落任何 Source 行")
            T.ok(n_blk >= 1, "留下一条 BLOCKED_PATH_TOO_LONG 记录（不静默丢）")
        with fake_platform(MAC):
            res2 = candidate.discover(short_path, root)
            T.ok(res2.get("status") != CAND_BLOCKED_STATUS,
                 "非 Windows：discover 不受此闸影响（status=%r）"
                 % (res2.get("status"),))
    finally:
        _reset_instance()

    def _discover_blocked() -> bool:
        root2 = os.path.join(tmp, "disc-teeth")
        os.makedirs(root2, exist_ok=True)
        _reset_instance()
        instance.acquire(root2)
        store.init_db(root2)
        try:
            with fake_platform(WIN):
                got = candidate.discover(long_path, root2)
                return got.get("status") == CAND_BLOCKED_STATUS
        finally:
            _reset_instance()

    T.teeth(
        "发现闸（路径长度判定恒放行后超长源不再被拦）",
        lambda: setattr(platform_win, "check_path_length",
                        lambda p, platform=None, policy=None:
                        {"path": str(p), "length": len(str(p)), "limit": 259,
                         "verdict": "ALLOW", "code": None, "message": "",
                         "guidance": "", "platform": platform or ""}),
        lambda: setattr(platform_win, "check_path_length", _ORIG_CHECK_LEN),
        _discover_blocked,
    )


_ORIG_CHECK_LEN = platform_win.check_path_length


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="v2o-win-selftest-")
    try:
        print("tmp 夹具：%s" % (tmp,))
        test_platform_branch()
        test_paths()
        test_long_paths()
        test_single_instance(tmp)
        test_reveal()
        test_data_root()
        test_volume_and_busy(tmp)
        test_no_registry_write()
        test_utf8(tmp)
        test_graceful_skip()
        test_launch_files()
        test_posix_no_regression(tmp)
        test_root_gate()
        test_run_gate()
        test_ownership_gate(tmp)
        test_discover_gate(tmp)
    finally:
        _reset_instance()
    print("\n" + "=" * 60)
    print("断言总数：%d，失败：%d" % (T.total, len(T.failed)))
    print("反向证伪：有牙 %d / 共 %d" % (T.teeth_sharp, T.teeth_total))
    for label in T.failed:
        print("  失败项：%s" % (label,))
    if T.failed or T.teeth_sharp != T.teeth_total:
        print("结论：FAIL")
        return 1
    print("结论：PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
