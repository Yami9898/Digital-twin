# -*- mode: python ; coding: utf-8 -*-
"""
Fichier spec PyInstaller — ETO Digital Twin
Génère un .app macOS autonome dans dist/
"""

import os
from pathlib import Path

ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "data"),   "data"),
        (str(ROOT / "config"), "config"),
    ],
    hiddenimports=[
        # PySide6
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtCharts",
        "PySide6.QtOpenGL",
        "PySide6.QtOpenGLWidgets",
        # scipy / numpy internaux
        "scipy.special._cython_special",
        "scipy._lib.messagestream",
        "scipy.integrate",
        "scipy.optimize",
        "scipy.linalg",
        # matplotlib backend Qt
        "matplotlib.backends.backend_qtagg",
        "matplotlib.backends.backend_qt5agg",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "PyQt5",
        "PyQt6",
        "wx",
        "gtk",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ETO Digital Twin",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ROOT / "assets" / "icon.icns"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ETO Digital Twin",
)

app = BUNDLE(
    coll,
    name="ETO Digital Twin.app",
    icon=str(ROOT / "assets" / "icon.icns"),
    bundle_identifier="com.eto.digital-twin",
    info_plist={
        "CFBundleDisplayName": "ETO Digital Twin",
        "CFBundleName":        "ETO Digital Twin",
        "CFBundleVersion":     "1.0.0",
        "CFBundleShortVersionString": "1.0",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
        "LSMinimumSystemVersion": "12.0",
    },
)
