"""Esportazione PDF e stampa.

- HtmlToPdfRenderer: converte HTML in PDF con una QWebEnginePage offscreen,
  elaborando una coda in modo sequenziale (l'API di Chromium è asincrona).
- merge_pdfs: unisce più PDF in un unico file con un segnalibro per fattura.
- print_pdf: stampa un PDF su una QPrinter renderizzando le pagine con QtPdf.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QMarginsF, QObject, QSize, Qt, Signal
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QImage
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWebEngineCore import QWebEnginePage

from pypdf import PdfReader, PdfWriter

A4_LAYOUT = QPageLayout(
    QPageSize(QPageSize.PageSizeId.A4),
    QPageLayout.Orientation.Portrait,
    QMarginsF(10, 10, 10, 10),
    QPageLayout.Unit.Millimeter,
)


@dataclass
class PdfJob:
    html: str
    output: Path
    title: str = ""


class HtmlToPdfRenderer(QObject):
    """Rende una coda di documenti HTML in PDF, uno alla volta.

    Segnali:
      progress(indice_completato, totale, titolo)
      finished(lista_pdf_prodotti, lista_errori)
    """

    progress = Signal(int, int, str)
    finished = Signal(list, list)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._page = QWebEnginePage(self)
        self._page.loadFinished.connect(self._on_load_finished)
        self._page.pdfPrintingFinished.connect(self._on_pdf_finished)
        self._jobs: list[PdfJob] = []
        self._index = 0
        self._done: list[Path] = []
        self._errors: list[str] = []
        self._running = False
        self._cancelled = False

    def start(self, jobs: list[PdfJob]) -> None:
        if self._running:
            raise RuntimeError("Renderer già in esecuzione")
        self._jobs = jobs
        self._index = 0
        self._done = []
        self._errors = []
        self._running = True
        self._cancelled = False
        self._next()

    def cancel(self) -> None:
        self._cancelled = True

    def _next(self) -> None:
        if self._cancelled or self._index >= len(self._jobs):
            self._running = False
            self.finished.emit(self._done, self._errors)
            return
        job = self._jobs[self._index]
        self._page.setHtml(job.html)

    def _current(self) -> PdfJob:
        return self._jobs[self._index]

    def _on_load_finished(self, ok: bool) -> None:
        if not self._running:
            return
        job = self._current()
        if not ok:
            self._errors.append(f"{job.title or job.output.name}: rendering HTML fallito")
            self._advance()
            return
        job.output.parent.mkdir(parents=True, exist_ok=True)
        self._page.printToPdf(str(job.output), A4_LAYOUT)

    def _on_pdf_finished(self, file_path: str, ok: bool) -> None:
        if not self._running:
            return
        job = self._current()
        if ok:
            self._done.append(job.output)
        else:
            self._errors.append(f"{job.title or job.output.name}: scrittura PDF fallita")
        self._advance()

    def _advance(self) -> None:
        self._index += 1
        self.progress.emit(self._index, len(self._jobs), self._current_title())
        self._next()

    def _current_title(self) -> str:
        if self._index < len(self._jobs):
            return self._jobs[self._index].title
        return ""


def merge_pdfs(parts: list[tuple[Path, str]], output: Path) -> None:
    """Unisce i PDF in un unico file, con un segnalibro per ogni fattura.

    parts: lista di (path_pdf, titolo_segnalibro), nell'ordine desiderato.
    """
    writer = PdfWriter()
    page_index = 0
    for path, title in parts:
        reader = PdfReader(str(path))
        writer.append(reader)
        writer.add_outline_item(title or path.stem, page_index)
        page_index += len(reader.pages)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "wb") as fh:
        writer.write(fh)


def print_pdf(pdf_path: Path, printer: QPrinter,
              progress_cb: Callable[[int, int], None] | None = None) -> None:
    """Stampa un PDF renderizzando ogni pagina come immagine ad alta risoluzione."""
    doc = QPdfDocument()
    doc.load(str(pdf_path))
    if doc.status() != QPdfDocument.Status.Ready:
        raise RuntimeError(f"PDF non leggibile: {pdf_path}")

    painter = QPainter()
    if not painter.begin(printer):
        raise RuntimeError("Impossibile inizializzare la stampante.")
    try:
        page_count = doc.pageCount()
        for i in range(page_count):
            if i > 0:
                printer.newPage()
            page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
            points = doc.pagePointSize(i)
            # scala mantenendo le proporzioni della pagina PDF
            scale = min(page_rect.width() / points.width(),
                        page_rect.height() / points.height())
            size = QSize(int(points.width() * scale), int(points.height() * scale))
            image = doc.render(i, size)
            if image.isNull():
                continue
            image = image.convertToFormat(QImage.Format.Format_RGB32)
            painter.drawImage(0, 0, image)
            if progress_cb:
                progress_cb(i + 1, page_count)
    finally:
        painter.end()
        doc.close()
