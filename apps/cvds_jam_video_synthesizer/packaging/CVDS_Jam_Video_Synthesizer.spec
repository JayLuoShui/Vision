# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

root = Path.cwd()
app_dir = root / "apps" / "cvds_jam_video_synthesizer"
datas = []
if (app_dir / "docs").exists():
    datas.append((str(app_dir / "docs"), "docs"))
if (root / "VERSION.txt").exists():
    datas.append((str(root / "VERSION.txt"), "."))
if (root / "runtime" / "ffmpeg.exe").exists():
    datas.append((str(root / "runtime" / "ffmpeg.exe"), "runtime"))

a = Analysis(
    [str(root / "apps" / "cvds_jam_video_synthesizer_app.py")],
    pathex=[str(root), str(root / "apps")],
    binaries=[],
    datas=datas,
    hiddenimports=[],
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
    name="CVDS_Jam_Video_Synthesizer",
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
    name="CVDS_Jam_Video_Synthesizer",
)
