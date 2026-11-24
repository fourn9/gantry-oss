"""Installed-wheel smoke on an actual x64 Windows host without commercial CAD."""
import json
from pathlib import Path
import platform
import subprocess
import sys
import winreg

import comtypes
import pythoncom


def main():
    assert sys.platform == "win32" and platform.machine().upper() in {"AMD64", "X86_64"}
    cli = Path(sys.executable).with_name("gantry-native.exe")
    catalog = json.loads(subprocess.check_output([cli, "catalog"]))
    host = json.loads(subprocess.check_output([cli, "doctor"]))
    assert host["platform"] == "Windows"
    products = {r["id"]: r for r in host["products"]}
    assert set(products) == {r["id"] for r in catalog}
    assert all(not r["runtime_verified"] for r in products.values())
    assert products["capital"]["status"] == products["zuken-e3"]["status"] == "blocked_sdk"
    pythoncom.CoInitialize()
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "CLSID") as key:
            assert winreg.QueryInfoKey(key)[0] > 0
    finally:
        pythoncom.CoUninitialize()
    print(json.dumps({"platform": host["platform"], "machine": host["machine"],
                      "products": {p: r["status"] for p, r in products.items()},
                      "licensed_editor_executed": False}, indent=2))


if __name__ == "__main__":
    main()
