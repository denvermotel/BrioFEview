"""Genera l'icona dell'app (multi-risoluzione .ico) a partire dal logo
ufficiale in resources/icons/logo.png (scalato con Qt)."""

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

ICONS_DIR = Path(__file__).parent.parent / "visualizzatore" / "resources" / "icons"
LOGO = ICONS_DIR / "logo.png"


def scaled(src: QImage, size: int) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    scaled_src = src.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)
    from PySide6.QtGui import QPainter
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    x = (size - scaled_src.width()) // 2
    y = (size - scaled_src.height()) // 2
    p.drawImage(x, y, scaled_src)
    p.end()
    return img


def main() -> None:
    QApplication(sys.argv)
    if not LOGO.exists():
        raise SystemExit(f"Logo non trovato: {LOGO}")
    src = QImage(str(LOGO))
    if src.isNull():
        raise SystemExit(f"Logo non leggibile: {LOGO}")

    images = [scaled(src, s) for s in (256, 64, 48, 32, 16)]

    entries, blobs = [], []
    offset = 6 + 16 * len(images)
    for img in images:
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QBuffer.OpenModeFlag.WriteOnly)
        img.save(buf, "PNG")
        blob = bytes(ba)
        s = img.width()
        b = s if s < 256 else 0
        entries.append(struct.pack("<BBBBHHII", b, b, 0, 0, 1, 32, len(blob), offset))
        blobs.append(blob)
        offset += len(blob)
    with open(ICONS_DIR / "app.ico", "wb") as fh:
        fh.write(struct.pack("<HHH", 0, 1, len(images)))
        for e in entries:
            fh.write(e)
        for b in blobs:
            fh.write(b)
    print(f"Icona creata in {ICONS_DIR} a partire da {LOGO.name}")


if __name__ == "__main__":
    main()
