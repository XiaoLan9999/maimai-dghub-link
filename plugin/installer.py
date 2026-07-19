"""Safe installer for the bundled MaiDGBridge MelonLoader mod."""

import ctypes
import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime


DLL_NAME = "MaiDGBridge.dll"
INI_NAME = "MaiDGBridge.ini"
MARKER_NAME = "MaiDGBridge.dghub.json"
BACKUP_DIR_NAME = "MaiDGBridge.backups"


def _result(
    state,
    detail,
    hint="",
    package="",
    path_state="pending",
    path_detail="尚未找到游戏目录",
    detected=False,
    installed=False,
    restart_required=False,
    game_running=False,
    backup="",
):
    return {
        "state": state,
        "detail": detail,
        "hint": hint,
        "package": package,
        "path_state": path_state,
        "path_detail": path_detail,
        "detected": detected,
        "installed": installed,
        "restart_required": restart_required,
        "game_running": game_running,
        "backup": backup,
    }


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _same_path(left, right):
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(
        os.path.abspath(right)
    )


def resolve_package_path(value):
    if value is None:
        return None
    raw = str(value).strip().strip('"').strip("'")
    if not raw:
        return None
    raw = os.path.expanduser(os.path.expandvars(raw))
    candidate = os.path.abspath(raw)
    if os.path.isfile(candidate) and os.path.basename(candidate).lower() == "sinmai.exe":
        candidate = os.path.dirname(candidate)

    for path in (candidate, os.path.join(candidate, "Package")):
        if os.path.isfile(os.path.join(path, "Sinmai.exe")):
            return os.path.normpath(path)
    return None


def _iter_process_images_windows():
    from ctypes import wintypes

    class ProcessEntry32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    invalid_handle = ctypes.c_void_p(-1).value
    if snapshot == invalid_handle:
        return

    try:
        entry = ProcessEntry32W()
        entry.dwSize = ctypes.sizeof(entry)
        has_entry = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while has_entry:
            if entry.szExeFile.lower() == "sinmai.exe":
                process = kernel32.OpenProcess(0x1000, False, entry.th32ProcessID)
                if process:
                    try:
                        size = wintypes.DWORD(32768)
                        buffer = ctypes.create_unicode_buffer(size.value)
                        if kernel32.QueryFullProcessImageNameW(
                            process, 0, buffer, ctypes.byref(size)
                        ):
                            yield buffer.value
                    finally:
                        kernel32.CloseHandle(process)
            has_entry = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)


def find_running_game_packages():
    if os.name != "nt":
        return []
    found = []
    try:
        images = _iter_process_images_windows()
        for image in images:
            package = resolve_package_path(image)
            if package and not any(_same_path(package, item) for item in found):
                found.append(package)
    except Exception:
        return []
    return found


def _load_payload(plugin_root):
    payload_dir = os.path.join(plugin_root, "payload")
    descriptor_path = os.path.join(payload_dir, "bridge.json")
    dll_path = os.path.join(payload_dir, DLL_NAME)
    ini_path = os.path.join(payload_dir, INI_NAME)
    with open(descriptor_path, encoding="utf-8-sig") as source:
        descriptor = json.load(source)
    expected_hash = str(descriptor.get("sha256", "")).lower()
    actual_hash = _sha256(dll_path)
    if len(expected_hash) != 64 or actual_hash != expected_hash:
        raise ValueError("内置桥接 DLL 校验失败")
    if not os.path.isfile(ini_path):
        raise FileNotFoundError(ini_path)
    return descriptor, dll_path, ini_path, actual_hash


def _atomic_copy(source, destination):
    directory = os.path.dirname(destination)
    os.makedirs(directory, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".maidgbridge-", dir=directory)
    os.close(handle)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _new_backup_dir(package):
    root = os.path.join(package, BACKUP_DIR_NAME)
    os.makedirs(root, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = os.path.join(root, timestamp)
    suffix = 1
    while os.path.exists(candidate):
        candidate = os.path.join(root, "{0}-{1}".format(timestamp, suffix))
        suffix += 1
    os.makedirs(candidate)
    return candidate


def _backup_existing(package, dll_destination, ini_destination):
    existing = [path for path in (dll_destination, ini_destination) if os.path.isfile(path)]
    marker = os.path.join(package, MARKER_NAME)
    if os.path.isfile(marker):
        existing.append(marker)
    if not existing:
        return ""

    backup = _new_backup_dir(package)
    for path in existing:
        if _same_path(path, dll_destination):
            target = os.path.join(backup, "Mods", DLL_NAME)
            os.makedirs(os.path.dirname(target), exist_ok=True)
        else:
            target = os.path.join(backup, os.path.basename(path))
        shutil.copy2(path, target)
    return backup


def _write_marker(package, descriptor, dll_hash, backup):
    marker = {
        "plugin": "maimai_link",
        "plugin_version": str(descriptor.get("plugin_version", "")),
        "bridge_version": str(descriptor.get("bridge_version", "")),
        "dll_sha256": dll_hash,
        "backup": backup,
        "installed_at": datetime.now().isoformat(timespec="seconds"),
    }
    destination = os.path.join(package, MARKER_NAME)
    data = json.dumps(marker, ensure_ascii=False, indent=2).encode("utf-8")
    handle, temporary = tempfile.mkstemp(prefix=".maidgbridge-marker-", dir=package)
    try:
        with os.fdopen(handle, "wb") as output:
            output.write(data)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def ensure_bridge_installed(
    plugin_root,
    configured_path="",
    auto_detect=True,
    auto_install=True,
    running_packages=None,
):
    configured = str(configured_path or "").strip()
    detected = False
    package = resolve_package_path(configured)
    if configured and package is None:
        return _result(
            "fail",
            "游戏目录无效，未安装桥接",
            "请选择包含 Sinmai.exe 的 Package 目录，或它的上一级目录",
            path_state="fail",
            path_detail="配置的目录中未找到 Sinmai.exe",
        )

    if running_packages is None:
        running_packages = find_running_game_packages()
    else:
        running_packages = [
            item for item in (resolve_package_path(path) for path in running_packages) if item
        ]

    if package is None and auto_detect:
        if len(running_packages) == 1:
            package = running_packages[0]
            detected = True
        elif len(running_packages) > 1:
            return _result(
                "warn",
                "检测到多个正在运行的游戏，未自动安装",
                "请在插件配置中填写要使用的 Package 目录",
                path_state="warn",
                path_detail="检测到多个 Sinmai.exe",
            )

    if package is None:
        return _result(
            "pending",
            "等待确定游戏目录",
            "启动一次游戏即可自动识别，或在插件配置中填写 Package 目录",
        )

    package_running = any(_same_path(package, item) for item in running_packages)
    path_detail = "已识别：" + package
    try:
        descriptor, payload_dll, payload_ini, payload_hash = _load_payload(plugin_root)
    except Exception as exc:
        return _result(
            "fail",
            "插件内置桥接文件不可用：" + str(exc),
            "请重新导入官方插件 ZIP",
            package=package,
            path_state="ok",
            path_detail=path_detail,
            detected=detected,
            game_running=package_running,
        )

    dll_destination = os.path.join(package, "Mods", DLL_NAME)
    ini_destination = os.path.join(package, INI_NAME)
    destination_hash = _sha256(dll_destination) if os.path.isfile(dll_destination) else ""

    if destination_hash == payload_hash:
        if not os.path.isfile(ini_destination) and auto_install:
            try:
                _atomic_copy(payload_ini, ini_destination)
            except OSError as exc:
                return _result(
                    "fail",
                    "DLL 已安装，但配置文件写入失败：" + str(exc),
                    "确认目录可写，必要时以管理员身份运行 DGHub",
                    package=package,
                    path_state="ok",
                    path_detail=path_detail,
                    detected=detected,
                    installed=True,
                    game_running=package_running,
                )
        return _result(
            "ok",
            "MaiDGBridge {0} 已安装".format(descriptor.get("bridge_version", "")),
            package=package,
            path_state="ok",
            path_detail=path_detail,
            detected=detected,
            installed=True,
            game_running=package_running,
        )

    if not auto_install:
        return _result(
            "idle",
            "自动安装已关闭",
            "开启自动安装后会备份旧文件并安装内置桥接",
            package=package,
            path_state="ok",
            path_detail=path_detail,
            detected=detected,
            game_running=package_running,
        )

    if destination_hash and package_running:
        return _result(
            "warn",
            "检测到旧版桥接；游戏运行中，暂缓更新",
            "关闭游戏后插件会自动完成更新并备份旧文件",
            package=package,
            path_state="ok",
            path_detail=path_detail,
            detected=detected,
            game_running=True,
        )

    backup = ""
    try:
        backup = _backup_existing(package, dll_destination, ini_destination)
        _atomic_copy(payload_dll, dll_destination)
        if not os.path.isfile(ini_destination):
            _atomic_copy(payload_ini, ini_destination)
        _write_marker(package, descriptor, payload_hash, backup)
    except OSError as exc:
        return _result(
            "fail",
            "桥接安装失败：" + str(exc),
            "确认游戏目录可写，必要时以管理员身份运行 DGHub",
            package=package,
            path_state="ok",
            path_detail=path_detail,
            detected=detected,
            game_running=package_running,
            backup=backup,
        )

    if package_running:
        return _result(
            "warn",
            "桥接已安装，需要重启游戏后生效",
            "退出并重新启动一次游戏；之后无需重复安装",
            package=package,
            path_state="ok",
            path_detail=path_detail,
            detected=detected,
            installed=True,
            restart_required=True,
            game_running=True,
            backup=backup,
        )

    return _result(
        "ok",
        "桥接已安装，可以启动游戏",
        package=package,
        path_state="ok",
        path_detail=path_detail,
        detected=detected,
        installed=True,
        backup=backup,
    )
