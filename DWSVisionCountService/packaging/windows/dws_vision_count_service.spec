# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules


project_root = Path(os.environ["DWS_SERVICE_PROJECT_ROOT"]).resolve()
icon_path = Path(os.environ.get("DWS_SERVICE_ICON", ""))

datas = []
binaries = []
hiddenimports = []

for package in ["torch", "torchvision", "ultralytics", "openvino", "cv2"]:
    hiddenimports += collect_submodules(package)
    collected = collect_all(package)
    datas += collected[0]
    binaries += collected[1]
    hiddenimports += collected[2]

native_bin = project_root / "native" / "turbojpeg_decoder" / "bin"
for name in [
    "dws_turbojpeg_decoder.dll",
    "turbojpeg.dll",
    "LICENSE-libjpeg-turbo.md",
]:
    datas.append((str(native_bin / name), "native/turbojpeg_decoder/bin"))

assets_dir = project_root / "app" / "assets"
for name in ["app_icon.png", "app_icon.ico"]:
    datas.append((str(assets_dir / name), "app/assets"))

a = Analysis(
    [str(project_root / "app" / "windows_app.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["fastapi", "uvicorn", "pytest"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DWSVisionCountService",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path) if icon_path.is_file() else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="DWSVisionCountService",
)
