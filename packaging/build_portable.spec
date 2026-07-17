# -*- mode: python ; coding: utf-8 -*-
# Build portable a file singolo:
#   python -m PyInstaller packaging/build_portable.spec --noconfirm
# (eseguire dalla root dev/). Produce dist/BrioFEview_Portable.exe:
# un unico eseguibile senza installazione, che si autoestrae in una
# cartella temporanea a ogni avvio (primo avvio più lento dei successivi).

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
    a.binaries,
    a.datas,
    name="BrioFEview_Portable",
    icon=str(ROOT / "visualizzatore" / "resources" / "icons" / "app.ico"),
    console=False,
    upx=False,
)
