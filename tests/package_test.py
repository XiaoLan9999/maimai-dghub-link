import hashlib
import json
import pathlib
import sys
import zipfile


REQUIRED = {
    "manifest.json",
    "main.py",
    "installer.py",
    "vrchat_osc.py",
    "SOURCE.md",
    "LICENSE",
    "payload/bridge.json",
    "payload/MaiDGBridge.dll",
    "payload/MaiDGBridge.ini",
}


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: package_test.py <plugin.zip>")
    archive = pathlib.Path(sys.argv[1])
    with zipfile.ZipFile(archive) as bundle:
        names = {name.replace("\\", "/") for name in bundle.namelist()}
        assert REQUIRED <= names, sorted(REQUIRED - names)
        assert all(not name.startswith("/") and ".." not in name.split("/") for name in names)

        def read(name):
            actual = next(item for item in bundle.namelist() if item.replace("\\", "/") == name)
            return bundle.read(actual)

        manifest = json.loads(read("manifest.json").decode("utf-8-sig"))
        descriptor = json.loads(read("payload/bridge.json").decode("utf-8-sig"))
        dll_hash = hashlib.sha256(read("payload/MaiDGBridge.dll")).hexdigest()

    assert manifest["id"] == "maimai_link", manifest
    assert manifest["version"] == descriptor["plugin_version"], descriptor
    assert descriptor["bridge_version"] == manifest["version"], descriptor
    assert descriptor["sha256"] == dll_hash, descriptor
    assert manifest["author"] == "XiaoLan9999", manifest
    osc_fields = {
        field["key"]: field
        for section in manifest["config_schema"]
        for field in section["fields"]
        if field["key"].startswith("osc_")
    }
    assert osc_fields["osc_enabled"]["default"] is False, osc_fields
    assert osc_fields["osc_port"]["default"] == "9000", osc_fields
    assert archive.stat().st_size < 20 * 1024 * 1024
    print(
        "package ok: {0} {1} files, {2} bytes, sha256={3}".format(
            manifest["version"], len(names), archive.stat().st_size, dll_hash
        )
    )


if __name__ == "__main__":
    main()
