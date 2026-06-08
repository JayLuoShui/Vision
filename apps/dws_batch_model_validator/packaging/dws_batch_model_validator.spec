# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules


project_root = Path(os.environ.get("DWS_VALIDATOR_PROJECT_ROOT", Path.cwd())).resolve()
src_root = project_root / "src"
icon_path = src_root / "dws_validator_gui" / "resources" / "app.ico"

datas = []
binaries = []
hiddenimports = []

for package in ["dws_validator", "dws_validator_gui", "torch", "torchvision", "ultralytics", "openvino", "cv2"]:
    hiddenimports += collect_submodules(package)

for package in ["torch", "torchvision", "ultralytics", "openvino", "cv2"]:
    collected = collect_all(package)
    datas += collected[0]
    binaries += collected[1]
    hiddenimports += collected[2]

for relative in ["configs", "docs", "README.md", "VERSION.txt"]:
    path = project_root / relative
    if path.exists():
        datas.append((str(path), relative if path.is_dir() else "."))

if (project_root / "models").exists():
    datas.append((str(project_root / "models"), "models"))

a = Analysis(
    [str(project_root / "run_gui.py")],
    pathex=[str(project_root), str(src_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DWSBatchModelValidator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path) if icon_path.exists() else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="DWSBatchModelValidator",
)
