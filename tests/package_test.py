import hashlib
import json
import pathlib
import sys
import zipfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
VERSION_INFO = json.loads((ROOT / "bridge" / "version.json").read_text(encoding="utf-8"))


REQUIRED = {
    "manifest.json",
    "main.py",
    "installer.py",
    "SOURCE.md",
    "LICENSE",
    "payload/bridge.json",
    "payload/XiaoLanMaiBrdge.dll",
    "payload/XiaoLanMaiBrdge.ini",
}


def main():
    if len(sys.argv) not in (2, 3):
        raise SystemExit("usage: package_test.py <plugin.zip> [expected_id]")
    archive = pathlib.Path(sys.argv[1])
    expected_id = sys.argv[2] if len(sys.argv) == 3 else "maimai_link"
    with zipfile.ZipFile(archive) as bundle:
        names = {name.replace("\\", "/") for name in bundle.namelist()}
        required = set(REQUIRED)
        if expected_id == "maimai_vrchat_osc":
            required.add("sse.py")
        assert required <= names, sorted(required - names)
        assert all(not name.startswith("/") and ".." not in name.split("/") for name in names)

        def read(name):
            actual = next(item for item in bundle.namelist() if item.replace("\\", "/") == name)
            return bundle.read(actual)

        manifest = json.loads(read("manifest.json").decode("utf-8-sig"))
        descriptor = json.loads(read("payload/bridge.json").decode("utf-8-sig"))
        dll_hash = hashlib.sha256(read("payload/XiaoLanMaiBrdge.dll")).hexdigest()

    assert manifest["id"] == expected_id, manifest
    assert manifest["version"] == descriptor["plugin_version"], descriptor
    assert descriptor["bridge_version"] == VERSION_INFO["bridge_version"], descriptor
    assert descriptor["sha256"] == dll_hash, descriptor
    assert manifest["author"] == "XiaoLan9999", manifest
    all_fields = {
        field["key"]: field
        for section in manifest["config_schema"]
        for field in section["fields"]
    }
    assert not any(key.startswith("osc_") for key in all_fields), all_fields
    if expected_id == "maimai_vrchat_osc":
        assert "settle_enabled" not in all_fields, all_fields
        assert "miss_strength" not in all_fields, all_fields
    assert archive.stat().st_size < 20 * 1024 * 1024
    print(
        "package ok: {0} {1} {2} files, {3} bytes, sha256={4}".format(
            manifest["id"], manifest["version"], len(names), archive.stat().st_size, dll_hash
        )
    )


if __name__ == "__main__":
    main()
