"""Dialog di esportazione/stampa batch di una cartella di fatture."""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, Slot
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
)

from .. import APP_NAME
from ..core import invoice, transform
from ..core.pdf_export import HtmlToPdfRenderer, PdfJob, merge_pdfs, print_pdf, A4_LAYOUT


class BatchDialog(QDialog):
    """Esporta in PDF (singoli o file unico) o stampa più fatture."""

    def __init__(self, files: list[Path], fmt: str, settings: QSettings, parent=None):
        super().__init__(parent)
        self.files = files
        self.settings = settings
        self.renderer: HtmlToPdfRenderer | None = None
        self._tempdir: tempfile.TemporaryDirectory | None = None
        self._jobs_meta: list[tuple[Path, str]] = []
        self._mode = ""

        self.setWindowTitle("Esporta / stampa cartella")
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>{len(files)} fatture selezionate</b>"))

        # --- operazione
        op_box = QGroupBox("Operazione")
        op_lay = QVBoxLayout(op_box)
        self.rb_singoli = QRadioButton("Salva PDF singoli (un file per fattura)")
        self.rb_unico = QRadioButton("Salva PDF unico (con segnalibri)")
        self.rb_stampa = QRadioButton("Stampa tutte le fatture")
        self.rb_singoli.setChecked(True)
        for rb in (self.rb_singoli, self.rb_unico, self.rb_stampa):
            op_lay.addWidget(rb)
            rb.toggled.connect(self._update_visibility)
        layout.addWidget(op_box)

        # --- opzioni
        opt_box = QGroupBox("Opzioni")
        form = QFormLayout(opt_box)

        self.combo_fmt = QComboBox()
        for key, label in transform.FORMAT_LABELS.items():
            self.combo_fmt.addItem(label, key)
        idx = self.combo_fmt.findData(fmt)
        self.combo_fmt.setCurrentIndex(max(0, idx))
        form.addRow("Formato di stampa:", self.combo_fmt)

        self.combo_naming = QComboBox()
        self.combo_naming.addItem("Nome del file di origine (ordine alfabetico)", "origine")
        self.combo_naming.addItem("Cedente + numero + data (ordine per data)", "metadati")
        naming = settings.value("naming_pdf", "origine")
        idx = self.combo_naming.findData(naming)
        self.combo_naming.setCurrentIndex(max(0, idx))
        form.addRow("Nome dei PDF:", self.combo_naming)

        dest_lay = QHBoxLayout()
        self.edit_dest = QLineEdit(str(files[0].parent / "PDF"))
        btn_dest = QPushButton("Sfoglia…")
        btn_dest.clicked.connect(self._pick_dest)
        dest_lay.addWidget(self.edit_dest)
        dest_lay.addWidget(btn_dest)
        self.dest_label = QLabel("Cartella di destinazione:")
        form.addRow(self.dest_label, dest_lay)

        layout.addWidget(opt_box)

        # --- avanzamento
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(120)
        self.log.setVisible(False)
        layout.addWidget(self.log)

        self.buttons = QDialogButtonBox()
        self.btn_start = self.buttons.addButton(
            "Avvia", QDialogButtonBox.ButtonRole.AcceptRole)
        self.btn_close = self.buttons.addButton(QDialogButtonBox.StandardButton.Close)
        self.btn_start.clicked.connect(self._start)
        self.btn_close.clicked.connect(self.reject)
        layout.addWidget(self.buttons)

        self._update_visibility()

    # ------------------------------------------------------------------

    def _update_visibility(self) -> None:
        printing = self.rb_stampa.isChecked()
        self.edit_dest.setEnabled(not printing)
        self.dest_label.setEnabled(not printing)

    def _pick_dest(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Cartella di destinazione", self.edit_dest.text())
        if folder:
            self.edit_dest.setText(folder)

    def _append_log(self, text: str) -> None:
        self.log.setVisible(True)
        self.log.append(text)

    # ------------------------------------------------------------- avvio

    @Slot()
    def _start(self) -> None:
        fmt = self.combo_fmt.currentData()
        naming = self.combo_naming.currentData()
        self.settings.setValue("naming_pdf", naming)

        if self.rb_stampa.isChecked():
            self._mode = "stampa"
        elif self.rb_unico.isChecked():
            self._mode = "unico"
        else:
            self._mode = "singoli"

        # 1. carica e trasforma tutte le fatture
        loaded: list[tuple[invoice.Invoice, str]] = []
        errors: list[str] = []
        for f in self.files:
            try:
                inv = invoice.load(f)
                html, _ = transform.to_html(inv, fmt)
                loaded.append((inv, html))
            except (invoice.InvoiceError, transform.TransformError) as exc:
                errors.append(f"{f.name}: {exc}")
        for e in errors:
            self._append_log(f"⚠ {e}")
        if not loaded:
            QMessageBox.warning(self, APP_NAME, "Nessuna fattura leggibile.")
            return

        # 2. ordina
        if naming == "metadati":
            loaded.sort(key=lambda t: (t[0].data or "9999", t[0].cedente.lower()))
        else:
            loaded.sort(key=lambda t: t[0].path.name.lower())

        # 3. destinazione dei PDF
        if self._mode == "singoli":
            out_dir = Path(self.edit_dest.text())
        else:
            self._tempdir = tempfile.TemporaryDirectory(prefix="fatture_pdf_")
            out_dir = Path(self._tempdir.name)

        jobs: list[PdfJob] = []
        self._jobs_meta = []
        used_names: set[str] = set()
        for i, (inv, html) in enumerate(loaded):
            name = inv.suggested_pdf_name(naming)
            if name.lower() in used_names:
                name = f"{Path(name).stem}_{i + 1}.pdf"
            used_names.add(name.lower())
            title = (f"{inv.cedente} n.{inv.numero} del {inv.data}".strip()
                     if inv.cedente or inv.numero else inv.path.name)
            jobs.append(PdfJob(html=html, output=out_dir / name, title=title))
            self._jobs_meta.append((out_dir / name, title))

        # 4. avvia il rendering
        self.btn_start.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setMaximum(len(jobs))
        self.progress.setValue(0)
        self.renderer = HtmlToPdfRenderer(self)
        self.renderer.progress.connect(self._on_progress)
        self.renderer.finished.connect(self._on_rendered)
        self.renderer.start(jobs)

    @Slot(int, int, str)
    def _on_progress(self, done: int, total: int, _title: str) -> None:
        self.progress.setValue(done)

    @Slot(list, list)
    def _on_rendered(self, done: list, errors: list) -> None:
        for e in errors:
            self._append_log(f"⚠ {e}")
        done_set = {Path(p) for p in done}
        parts = [(p, t) for p, t in self._jobs_meta if p in done_set]

        try:
            if self._mode == "singoli":
                self._append_log(f"✔ {len(parts)} PDF salvati in "
                                 f"{Path(self.edit_dest.text())}")
            elif self._mode == "unico":
                self._finish_unico(parts)
            else:
                self._finish_stampa(parts)
        finally:
            if self._tempdir and self._mode != "stampa":
                self._tempdir.cleanup()
                self._tempdir = None
            self.btn_start.setEnabled(True)

    def _finish_unico(self, parts: list[tuple[Path, str]]) -> None:
        if not parts:
            self._append_log("⚠ Nessun PDF generato.")
            return
        suggested = str(Path(self.edit_dest.text()).parent / "Fatture.pdf")
        out, _ = QFileDialog.getSaveFileName(
            self, "Salva PDF unico", suggested, "Documento PDF (*.pdf)")
        if not out:
            self._append_log("Operazione annullata.")
            return
        try:
            merge_pdfs(parts, Path(out))
            self._append_log(f"✔ PDF unico salvato: {out} "
                             f"({len(parts)} fatture, con segnalibri)")
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, f"Errore nell'unione dei PDF:\n{exc}")

    def _finish_stampa(self, parts: list[tuple[Path, str]]) -> None:
        if not parts:
            self._append_log("⚠ Nessuna fattura da stampare.")
            return
        try:
            merged = Path(self._tempdir.name) / "_stampa_unica.pdf"
            merge_pdfs(parts, merged)

            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setPageLayout(A4_LAYOUT)
            dialog = QPrintDialog(printer, self)
            dialog.setWindowTitle(f"Stampa {len(parts)} fatture")
            if dialog.exec() != QPrintDialog.DialogCode.Accepted:
                self._append_log("Stampa annullata.")
                return
            self.progress.setMaximum(0)  # indeterminata durante la stampa
            print_pdf(merged, printer)
            self.progress.setMaximum(1)
            self.progress.setValue(1)
            self._append_log(f"✔ Inviate alla stampante {len(parts)} fatture.")
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, f"Errore di stampa:\n{exc}")
        finally:
            if self._tempdir:
                self._tempdir.cleanup()
                self._tempdir = None
