# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules


project_root = Path(os.environ.get("CVDS_PROJECT_ROOT", Path.cwd())).resolve()
app_root = project_root / "apps" / "cvds_annotation_tool_v2_3"
package_name = os.environ.get("CVDS_ANNOTATION_PACKAGE_NAME", "CVDS_Annotation_Tool_v2.3")
include_ai = os.environ.get("CVDS_ANNOTATION_INCLUDE_AI", "0") == "1"

datas = []
binaries = []
hiddenimports = []
excludes = []

for data_path in ["VERSION.txt", "CHANGELOG.md"]:
    source = project_root / data_path
    if source.exists():
        datas.append((str(source), "."))

docs_dir = project_root / "docs"
if docs_dir.exists():
    datas.append((str(docs_dir), "docs"))

if include_ai:
    for package in ["torch", "torchvision", "ultralytics"]:
        hiddenimports += collect_submodules(package)
        collected = collect_all(package)
        datas += collected[0]
        binaries += collected[1]
        hiddenimports += collected[2]
else:
    excludes += ["torch", "torchvision", "ultralytics"]


a = Analysis(
    [str(project_root / "apps" / "cvds_annotation_tool_v2_3.py")],
    pathex=[str(project_root), str(app_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=package_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=package_name,
)
