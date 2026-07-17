"""Risoluzione dei percorsi delle risorse (sviluppo e PyInstaller)."""

import sys
from pathlib import Path


def resources_dir() -> Path:
    """Cartella resources, valida sia in sviluppo sia nell'exe PyInstaller."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        return base / "visualizzatore" / "resources"
    return Path(__file__).resolve().parent.parent / "resources"


def xsl_path(name: str) -> Path:
    return resources_dir() / "xsl" / name


def icon_path(name: str) -> Path:
    return resources_dir() / "icons" / name
