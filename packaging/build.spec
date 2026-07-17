# -*- mode: python ; coding: utf-8 -*-
# Build: pyinstaller packaging/build.spec  (eseguire dalla root dev/)

from pathlib import Path

ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "visualizzatore" / "__main__.py")],
    pathex=[str(ROOT)],
    datas=[
        (str(ROOT / "visualizzatore" / "resources" / "xsl"), "visualizzatore/resources/xsl"),
        (str(ROOT / "visualizzatore" / "resources" / "icons"), "visualizzatore/resources/icons"),
        (str(ROOT / "visualizzatore" / "resources" / "style.qss"), "visualizzatore/resources"),
    ],
    hiddenimports=[
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineCore",
        "PySide6.QtPrintSupport",
        "PySide6.QtPdf",
        "PySide6.QtSvg",
    ],
    excludes=["tkinter", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.Qt3DCore"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="BrioFEview",
    icon=str(ROOT / "visualizzatore" / "resources" / "icons" / "app.ico"),
    console=False,
    upx=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="BrioFEview",
    upx=False,
)
