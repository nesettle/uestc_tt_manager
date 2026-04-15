# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules


desktop_dir = Path(SPEC).resolve().parent
project_root = desktop_dir.parent
browser_dir = desktop_dir / "build_assets" / "ms-playwright"

qt_datas = collect_data_files("qtpy")

datas = [
    (str(project_root / "app" / "templates"), "app/templates"),
    (str(project_root / "app" / "static"), "app/static"),
    (str(project_root / "vendor"), "vendor"),
]
if browser_dir.exists():
    datas.append((str(browser_dir), "ms-playwright"))
datas += collect_data_files("webview")
datas += qt_datas

hiddenimports = collect_submodules("webview") + [
    "app.main",
    "app.runtime",
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "playwright.sync_api",
    "qtpy",
    "qtpy.QtCore",
    "qtpy.QtGui",
    "qtpy.QtWidgets",
    "qtpy.QtNetwork",
    "qtpy.QtWebChannel",
    "qtpy.QtWebEngineCore",
    "qtpy.QtWebEngineWidgets",
    "webview.platforms.qt",
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtNetwork",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "shiboken6",
]

a = Analysis(
    [str(desktop_dir / "app_host.py")],
    pathex=[str(project_root), str(desktop_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="UESTC_TT_Manager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="UESTC_TT_Manager",
)
