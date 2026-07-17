"""Icone lineari monocromatiche per la toolbar.

Icone in stile Feather (MIT): path SVG resi al volo con QSvgRenderer, così
ereditano il colore del tema senza dipendere da file o plugin immagine.
"""

from __future__ import annotations

import tempfile
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer

# viewBox 0 0 24 24, tracciato "stroke" (Feather-style)
_PATHS = {
    "open-file": (
        '<path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>'
        '<polyline points="13 2 13 9 20 9"/>'
    ),
    "open-folder": (
        '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 '
        '2 0 0 1 2 2z"/>'
    ),
    "print": (
        '<polyline points="6 9 6 2 18 2 18 9"/>'
        '<path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 '
        '0 0 1-2 2h-2"/>'
        '<rect x="6" y="14" width="12" height="8" rx="1"/>'
    ),
    "save-pdf": (
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
        '<polyline points="7 10 12 15 17 10"/>'
        '<line x1="12" y1="15" x2="12" y2="3"/>'
    ),
    "export": (
        '<polygon points="12 2 2 7 12 12 22 7 12 2"/>'
        '<polyline points="2 17 12 22 22 17"/>'
        '<polyline points="2 12 12 17 22 12"/>'
    ),
    "settings": (
        '<line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/>'
        '<line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/>'
        '<line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/>'
        '<line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/>'
        '<line x1="17" y1="16" x2="23" y2="16"/>'
    ),
}


def _svg_bytes(name: str, color: str) -> QByteArray:
    inner = _PATHS[name]
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="1.8" stroke-linecap="round" '
        f'stroke-linejoin="round">{inner}</svg>'
    )
    return QByteArray(svg.encode("utf-8"))


@lru_cache(maxsize=None)
def make_icon(name: str, color: str = "#3A3833") -> QIcon:
    renderer = QSvgRenderer(_svg_bytes(name, color))
    pm = QPixmap(48, 48)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    renderer.render(painter)
    painter.end()
    return QIcon(pm)


# --------------------------------------- indicatori check/radio (per il QSS)

_BORDER = "#C6C2B6"
_ACCENT = "#0E9C8C"
_WHITE = "#FFFFFF"
_S = 36  # risoluzione sorgente (mostrata poi a ~18px)


def _new_canvas() -> tuple[QPixmap, QPainter]:
    pm = QPixmap(_S, _S)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    return pm, p


def _check_off() -> QPixmap:
    pm, p = _new_canvas()
    p.setBrush(QColor(_WHITE))
    p.setPen(QPen(QColor(_BORDER), 2.4))
    p.drawRoundedRect(QRectF(3, 3, _S - 6, _S - 6), 7, 7)
    p.end()
    return pm


def _check_on() -> QPixmap:
    pm, p = _new_canvas()
    p.setBrush(QColor(_ACCENT))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(3, 3, _S - 6, _S - 6), 7, 7)
    path = QPainterPath(QPointF(10, 18.5))
    path.lineTo(16, 24.5)
    path.lineTo(26.5, 12.5)
    p.setPen(QPen(QColor(_WHITE), 3.6, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.drawPath(path)
    p.end()
    return pm


def _radio_off() -> QPixmap:
    pm, p = _new_canvas()
    p.setBrush(QColor(_WHITE))
    p.setPen(QPen(QColor(_BORDER), 2.4))
    p.drawEllipse(QRectF(3, 3, _S - 6, _S - 6))
    p.end()
    return pm


def _radio_on() -> QPixmap:
    pm, p = _new_canvas()
    p.setBrush(QColor(_WHITE))
    p.setPen(QPen(QColor(_ACCENT), 2.4))
    p.drawEllipse(QRectF(3, 3, _S - 6, _S - 6))
    p.setBrush(QColor(_ACCENT))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QRectF(11, 11, _S - 22, _S - 22))
    p.end()
    return pm


def ensure_indicator_images() -> Path:
    """Genera i PNG degli indicatori check/radio in una cache temporanea e
    ne restituisce la cartella (percorso da iniettare nel QSS come @ICONS@).
    Richiede una QApplication già attiva."""
    out = Path(tempfile.gettempdir()) / "stg_fattura_ui"
    out.mkdir(parents=True, exist_ok=True)
    images = {
        "check_off.png": _check_off, "check_on.png": _check_on,
        "radio_off.png": _radio_off, "radio_on.png": _radio_on,
    }
    for name, fn in images.items():
        fn().save(str(out / name))
    return out
