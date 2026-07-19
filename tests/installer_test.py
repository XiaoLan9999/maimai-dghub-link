import hashlib
import json
import pathlib
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugin"))

from installer import ensure_bridge_installed  # noqa: E402


def write_payload(plugin, version, content):
    payload = plugin / "payload"
    payload.mkdir(parents=True, exist_ok=True)
    dll = payload / "MaiDGBridge.dll"
    dll.write_bytes(content)
    (payload / "MaiDGBridge.ini").write_text(
        "Enabled=true\nPort=8891\nPublishIntervalMs=250\n", encoding="utf-8"
    )
    descriptor = {
        "plugin_version": version,
        "bridge_version": version,
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    (payload / "bridge.json").write_text(
        json.dumps(descriptor), encoding="utf-8"
    )


def main():
    with tempfile.TemporaryDirectory() as temporary:
        root = pathlib.Path(temporary)
        plugin = root / "plugin"
        package = root / "game" / "Package"
        (package / "Mods").mkdir(parents=True)
        (package / "MelonLoader").mkdir()
        (package / "Sinmai.exe").write_bytes(b"test executable")

        write_payload(plugin, "1.2.0", b"bridge version 1")
        first = ensure_bridge_installed(
            str(plugin), str(package), auto_detect=False, running_packages=[]
        )
        assert first["state"] == "ok", first
        assert first["installed"], first
        assert (package / "Mods" / "MaiDGBridge.dll").read_bytes() == b"bridge version 1"
        assert (package / "MaiDGBridge.ini").is_file()
        assert (package / "MaiDGBridge.dghub.json").is_file()

        second = ensure_bridge_installed(
            str(plugin), str(package.parent), auto_detect=False, running_packages=[]
        )
        assert second["state"] == "ok", second
        assert not second["backup"], second

        write_payload(plugin, "1.2.1", b"bridge version 2")
        deferred = ensure_bridge_installed(
            str(plugin),
            str(package / "Sinmai.exe"),
            auto_detect=False,
            running_packages=[str(package)],
        )
        assert deferred["state"] == "warn", deferred
        assert not deferred["installed"], deferred
        assert (package / "Mods" / "MaiDGBridge.dll").read_bytes() == b"bridge version 1"

        upgraded = ensure_bridge_installed(
            str(plugin), str(package), auto_detect=False, running_packages=[]
        )
        assert upgraded["state"] == "ok", upgraded
        assert pathlib.Path(upgraded["backup"]).is_dir(), upgraded
        assert (package / "Mods" / "MaiDGBridge.dll").read_bytes() == b"bridge version 2"
        assert (
            pathlib.Path(upgraded["backup"]) / "Mods" / "MaiDGBridge.dll"
        ).read_bytes() == b"bridge version 1"

        invalid = ensure_bridge_installed(
            str(plugin), str(root / "missing"), auto_detect=False, running_packages=[]
        )
        assert invalid["state"] == "fail", invalid

    print("installer ok: detect, install, idempotence, running-game deferral, backup, upgrade")


if __name__ == "__main__":
    main()
