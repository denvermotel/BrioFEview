"""Finestra principale del visualizzatore."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QSettings, QSize, Qt, Slot
from PySide6.QtGui import QAction, QActionGroup, QIcon, QKeySequence
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSplitter,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, APP_VERSION, GITHUB_URL, ORG_NAME
from ..core import invoice, transform
from ..core.pdf_export import A4_LAYOUT
from ..utils.resources import icon_path
from .batch_dialog import BatchDialog
from .icons import make_icon
from .settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings(ORG_NAME, APP_NAME)
        self.current_invoice: invoice.Invoice | None = None
        self.current_folder: Path | None = None
        self.fmt = self.settings.value("formato", transform.ELEGANTE)
        if self.fmt not in transform.FORMAT_LABELS:
            self.fmt = transform.ELEGANTE
        # vista corrente: un formato di stampa oppure il codice XML
        self.view_mode = self.fmt

        self.setWindowTitle(APP_NAME)
        self.resize(1100, 800)
        ico = icon_path("app.ico")
        if ico.exists():
            self.setWindowIcon(QIcon(str(ico)))

        self._build_ui()
        self.setAcceptDrops(True)
        self._show_welcome()

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        self.web = QWebEngineView()
        # QWebEngineView intercetta i drop con un widget interno creato in
        # seguito: filtriamo gli eventi suoi e dei suoi figli (anche futuri)
        # per far arrivare i file trascinati alla finestra principale.
        self.web.installEventFilter(self)
        for child in self.web.findChildren(QWidget):
            child.installEventFilter(self)
        self._build_zoom_overlay()

        # barra laterale: intestazione con pulsante di chiusura + elenco fatture
        self.file_list = QListWidget()
        self.file_list.currentItemChanged.connect(self._on_list_selection)

        self.sidebar = QWidget()
        self.sidebar.setMaximumWidth(340)
        side_lay = QVBoxLayout(self.sidebar)
        side_lay.setContentsMargins(0, 0, 0, 0)
        side_lay.setSpacing(0)
        header = QWidget()
        header.setObjectName("sidebarHeader")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(12, 6, 6, 6)
        title = QLabel("FATTURE NELLA CARTELLA")
        title.setObjectName("sidebarTitle")
        btn_close = QToolButton()
        btn_close.setText("✕")  # ✕
        btn_close.setObjectName("sidebarClose")
        btn_close.setToolTip("Chiudi l'elenco della cartella")
        btn_close.clicked.connect(self.close_folder)
        h_lay.addWidget(title)
        h_lay.addStretch(1)
        h_lay.addWidget(btn_close)
        side_lay.addWidget(header)
        side_lay.addWidget(self.file_list)
        self.sidebar.hide()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.sidebar)
        splitter.addWidget(self.web)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        tb = QToolBar("Principale")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        tb.setIconSize(QSize(18, 18))
        self.addToolBar(tb)

        self.act_open = QAction(make_icon("open-file"), "Apri fattura", self)
        self.act_open.setShortcut(QKeySequence.StandardKey.Open)
        self.act_open.triggered.connect(self.open_file_dialog)
        tb.addAction(self.act_open)

        self.act_open_folder = QAction(make_icon("open-folder"), "Apri cartella", self)
        self.act_open_folder.setShortcut("Ctrl+Shift+O")
        self.act_open_folder.triggered.connect(self.open_folder_dialog)
        tb.addAction(self.act_open_folder)

        tb.addSeparator()

        # selettore vista raggruppato in un menu a tendina (occupa poco spazio
        # anche a finestra ridotta): formati di stampa + codice XML
        self.view_button = QToolButton(self)
        self.view_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.view_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        view_menu = QMenu(self.view_button)
        view_group = QActionGroup(self)
        view_group.setExclusive(True)
        self.fmt_actions: dict[str, QAction] = {}
        for key, label in transform.VIEW_LABELS.items():
            act = QAction(label, self, checkable=True)
            act.setChecked(key == self.view_mode)
            act.triggered.connect(lambda _=False, k=key: self.set_view(k))
            view_group.addAction(act)
            view_menu.addAction(act)
            self.fmt_actions[key] = act
        self.view_button.setMenu(view_menu)
        tb.addWidget(self.view_button)
        self._update_view_button()

        tb.addSeparator()

        self.act_print = QAction(make_icon("print"), "Stampa", self)
        self.act_print.setShortcut(QKeySequence.StandardKey.Print)
        self.act_print.triggered.connect(self.print_current)
        self.act_print.setEnabled(False)
        tb.addAction(self.act_print)

        self.act_pdf = QAction(make_icon("save-pdf"), "Salva PDF", self)
        self.act_pdf.setShortcut("Ctrl+S")
        self.act_pdf.triggered.connect(self.save_pdf)
        self.act_pdf.setEnabled(False)
        tb.addAction(self.act_pdf)

        self.act_batch = QAction(make_icon("export"), "Esporta cartella", self)
        self.act_batch.triggered.connect(self.open_batch_dialog)
        self.act_batch.setVisible(False)  # solo con la barra laterale aperta
        tb.addAction(self.act_batch)

        tb.addSeparator()

        act_settings = QAction(make_icon("settings"), "Impostazioni", self)
        act_settings.triggered.connect(self.open_settings)
        tb.addAction(act_settings)

        self.statusBar().showMessage("Pronto")

    def _update_view_button(self) -> None:
        """Aggiorna l'etichetta del pulsante vista con la vista corrente."""
        label = transform.VIEW_LABELS.get(self.view_mode, "")
        self.view_button.setText(f"  Vista: {label}  ")

    # --------------------------------------------------------------- zoom

    def _build_zoom_overlay(self) -> None:
        """Controllo zoom in overlay, in basso a destra sulla fattura.
        Non incide su stampa/PDF: agisce solo sullo zoom di visualizzazione."""
        self._zoom = 1.0
        self.zoom_overlay = QFrame(self.web)
        self.zoom_overlay.setObjectName("zoomOverlay")
        lay = QHBoxLayout(self.zoom_overlay)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(1)
        btn_out = QToolButton()
        btn_out.setObjectName("zoomBtn")
        btn_out.setText("−")  # −
        btn_out.setToolTip("Riduci (Ctrl+rotella)")
        self.zoom_label = QToolButton()
        self.zoom_label.setObjectName("zoomLabel")
        self.zoom_label.setText("100%")
        self.zoom_label.setToolTip("Ripristina zoom 100%")
        btn_in = QToolButton()
        btn_in.setObjectName("zoomBtn")
        btn_in.setText("+")
        btn_in.setToolTip("Ingrandisci (Ctrl+rotella)")
        btn_out.clicked.connect(lambda: self._apply_zoom(self._zoom - 0.1))
        btn_in.clicked.connect(lambda: self._apply_zoom(self._zoom + 0.1))
        self.zoom_label.clicked.connect(lambda: self._apply_zoom(1.0))
        for wdg in (btn_out, self.zoom_label, btn_in):
            lay.addWidget(wdg)
        self.zoom_overlay.hide()

    def _apply_zoom(self, factor: float) -> None:
        factor = max(0.3, min(3.0, round(factor, 2)))
        self._zoom = factor
        self.web.setZoomFactor(factor)
        self.zoom_label.setText(f"{round(factor * 100)}%")
        self._position_zoom_overlay()

    def _position_zoom_overlay(self) -> None:
        if not getattr(self, "zoom_overlay", None):
            return
        self.zoom_overlay.adjustSize()
        margin = 16
        x = self.web.width() - self.zoom_overlay.width() - margin
        y = self.web.height() - self.zoom_overlay.height() - margin
        self.zoom_overlay.move(max(0, x), max(0, y))
        self.zoom_overlay.raise_()

    def _show_welcome(self) -> None:
        logo_b64 = ""
        logo_file = icon_path("logo.png")
        if logo_file.exists():
            import base64
            logo_b64 = base64.b64encode(logo_file.read_bytes()).decode("ascii")
        mark = (f'<img class="mark" src="data:image/png;base64,{logo_b64}">'
               if logo_b64 else '<div class="mark mark-fallback">€</div>')

        self.web.setHtml(f"""
        <!DOCTYPE html><html lang="it"><head><meta charset="utf-8"><style>
          html,body {{ height:100%; margin:0; }}
          body {{
            font-family:"Segoe UI","Helvetica Neue",sans-serif;
            background:#F5F4EE; color:#2A2825;
            display:flex; align-items:center; justify-content:center;
          }}
          .card {{ text-align:center; max-width:460px; padding:0 24px; }}
          .mark-wrap {{
            width:150px; height:150px; margin:0 auto 16px;
            display:flex; align-items:center; justify-content:center;
            border-radius:32px;
            background:radial-gradient(circle at 50% 42%, rgba(255,255,255,.95), rgba(255,255,255,0) 68%);
          }}
          .mark {{
            width:104px; height:auto; display:block;
            filter:drop-shadow(0 12px 20px rgba(11,122,110,.22))
                   drop-shadow(0 2px 5px rgba(31,30,29,.16));
          }}
          .mark-fallback {{
            width:64px; height:64px; border-radius:16px; line-height:64px;
            background:#0E9C8C; color:#fff; font-size:30px; font-weight:700;
            box-shadow:0 6px 20px rgba(14,156,140,.28);
          }}
          h1 {{ font-size:22px; font-weight:600; margin:0 0 10px; color:#1F1E1D; }}
          p {{ font-size:14px; line-height:1.6; color:#78746C; margin:0 0 8px; }}
          .hint {{ color:#A29C90; }}
          .ver {{ margin-top:26px; font-size:12px; color:#B0AB9F;
                  letter-spacing:.02em; }}
          .repo {{ margin-top:4px; font-size:11.5px; color:#7FB3AB; }}
        </style></head><body>
          <div class="card">
            <div class="mark-wrap">{mark}</div>
            <h1>{APP_NAME}</h1>
            <p>Apri una fattura elettronica <b>.xml</b> o <b>.p7m</b>,
               oppure un'intera cartella.</p>
            <p class="hint">Puoi anche trascinare i file in questa finestra.</p>
            <div class="ver">Versione {APP_VERSION} · {ORG_NAME}</div>
            <div class="repo">{GITHUB_URL}</div>
          </div>
        </body></html>""")

    # ------------------------------------------------------ apertura file

    @Slot()
    def open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Apri fattura elettronica",
            self.settings.value("ultima_cartella", ""),
            "Fatture elettroniche (*.xml *.p7m);;Tutti i file (*.*)")
        if path:
            self.settings.setValue("ultima_cartella", str(Path(path).parent))
            self.load_file(Path(path))

    @Slot()
    def open_folder_dialog(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Apri cartella di fatture",
            self.settings.value("ultima_cartella", ""))
        if folder:
            self.settings.setValue("ultima_cartella", folder)
            self.load_folder(Path(folder))

    def load_file(self, path: Path) -> None:
        try:
            inv = invoice.load(path)
        except invoice.InvoiceError as exc:
            QMessageBox.warning(self, APP_NAME,
                                f"Impossibile aprire «{path.name}»:\n\n{exc}")
            return
        self.current_invoice = inv
        self._render()

    def load_folder(self, folder: Path) -> None:
        files = invoice.scan_folder(folder)
        if not files:
            QMessageBox.information(
                self, APP_NAME,
                f"Nessun file .xml o .p7m trovato in «{folder}».")
            return
        self.current_folder = folder
        self.file_list.clear()
        for f in files:
            item = QListWidgetItem(f.name)
            item.setData(Qt.ItemDataRole.UserRole, str(f))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.file_list.addItem(item)
        self.sidebar.show()
        self.act_batch.setVisible(True)
        self.file_list.setCurrentRow(0)
        self.statusBar().showMessage(
            f"Cartella: {folder} - {len(files)} file")

    @Slot()
    def close_folder(self) -> None:
        """Chiude la barra laterale con l'elenco della cartella."""
        self.sidebar.hide()
        self.act_batch.setVisible(False)
        self.current_folder = None

    @Slot()
    def _on_list_selection(self, current: QListWidgetItem | None,
                           _prev: QListWidgetItem | None = None) -> None:
        if current:
            self.load_file(Path(current.data(Qt.ItemDataRole.UserRole)))

    # -------------------------------------------------------- rendering

    def set_view(self, view: str) -> None:
        self.view_mode = view
        if view in transform.FORMAT_LABELS:
            self.fmt = view
            self.settings.setValue("formato", view)
        self._update_view_button()
        if self.current_invoice:
            self._render()

    def _render(self) -> None:
        inv = self.current_invoice
        assert inv is not None
        warn = None
        try:
            if self.view_mode == transform.XML_VIEW:
                html = transform.source_html(inv)
            else:
                html, warn = transform.to_html(inv, self.view_mode)
        except transform.TransformError as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
            return
        self.web.setHtml(html)
        self.web.setZoomFactor(self._zoom)  # mantiene lo zoom scelto
        self.zoom_overlay.show()
        self._position_zoom_overlay()
        self.act_print.setEnabled(True)
        self.act_pdf.setEnabled(True)
        self.setWindowTitle(f"{inv.display_name} - {APP_NAME}")

        parts = [inv.display_name,
                 "fattura semplificata" if inv.kind == invoice.SEMPLIFICATA
                 else "fattura ordinaria"]
        if inv.signed:
            parts.append("firmata (p7m)")
        if inv.cedente:
            parts.append(inv.cedente)
        msg = " - ".join(parts)
        if warn:
            msg += f"   {warn}"
        self.statusBar().showMessage(msg)

    # ----------------------------------------------------- stampa e PDF

    @Slot()
    def print_current(self) -> None:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageLayout(A4_LAYOUT)
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("Stampa fattura")
        if dialog.exec() != QPrintDialog.DialogCode.Accepted:
            return
        self.statusBar().showMessage("Stampa in corso...")
        self.web.print_(printer) if hasattr(self.web, "print_") else self.web.print(printer)
        self._printer_ref = printer  # evita il garbage collect durante la stampa asincrona
        self.web.printFinished.connect(self._on_print_finished)

    @Slot(bool)
    def _on_print_finished(self, ok: bool) -> None:
        try:
            self.web.printFinished.disconnect(self._on_print_finished)
        except RuntimeError:
            pass
        self.statusBar().showMessage(
            "Stampa inviata." if ok else "Stampa non riuscita.", 5000)

    @Slot()
    def save_pdf(self) -> None:
        inv = self.current_invoice
        if not inv:
            return
        naming = self.settings.value("naming_pdf", "origine")
        suggested = str(Path(self.settings.value("ultima_cartella_pdf",
                                                 str(inv.path.parent)))
                        / inv.suggested_pdf_name(naming))
        path, _ = QFileDialog.getSaveFileName(
            self, "Salva PDF", suggested, "Documento PDF (*.pdf)")
        if not path:
            return
        self.settings.setValue("ultima_cartella_pdf", str(Path(path).parent))
        self.statusBar().showMessage("Creazione PDF...")
        self.web.page().pdfPrintingFinished.connect(self._on_pdf_saved)
        self.web.page().printToPdf(path, A4_LAYOUT)

    @Slot(str, bool)
    def _on_pdf_saved(self, file_path: str, ok: bool) -> None:
        try:
            self.web.page().pdfPrintingFinished.disconnect(self._on_pdf_saved)
        except RuntimeError:
            pass
        if ok:
            self.statusBar().showMessage(f"PDF salvato: {file_path}", 8000)
        else:
            QMessageBox.warning(self, APP_NAME,
                                f"Impossibile salvare il PDF:\n{file_path}")

    # ------------------------------------------------------------- batch

    @Slot()
    def open_batch_dialog(self) -> None:
        if not self.current_folder:
            return
        selected = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(Path(item.data(Qt.ItemDataRole.UserRole)))
        if not selected:
            QMessageBox.information(self, APP_NAME,
                                    "Nessuna fattura selezionata nell'elenco.")
            return
        dlg = BatchDialog(selected, self.fmt, self.settings, self)
        dlg.exec()

    @Slot()
    def open_settings(self) -> None:
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec():
            fmt = self.settings.value("formato", transform.MINISTERIALE)
            if fmt != self.fmt and fmt in self.fmt_actions:
                self.fmt_actions[fmt].setChecked(True)
                self.set_view(fmt)

    # ------------------------------------------------------- drag & drop

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Gestisce drop, zoom con Ctrl+rotella e riposizionamento overlay
        sul QWebEngineView (e sui suoi widget interni)."""
        t = event.type()
        if t == QEvent.Type.ChildAdded:
            child = event.child()
            if isinstance(child, QWidget):
                child.installEventFilter(self)
        elif t == QEvent.Type.Resize and obj is self.web:
            self._position_zoom_overlay()
        elif t == QEvent.Type.Wheel:
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                step = 0.1 if event.angleDelta().y() > 0 else -0.1
                self._apply_zoom(self._zoom + step)
                return True
        elif t in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
                return True
        elif t == QEvent.Type.Drop:
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
                self._handle_dropped_urls(event.mimeData().urls())
                return True
        return super().eventFilter(obj, event)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        self._handle_dropped_urls(event.mimeData().urls())

    def _handle_dropped_urls(self, urls) -> None:
        for url in urls:
            path = Path(url.toLocalFile())
            if path.is_dir():
                self.load_folder(path)
                return
            if path.suffix.lower() in (".xml", ".p7m"):
                self.load_file(path)
                return
        QMessageBox.information(self, APP_NAME,
                                "Trascina un file .xml/.p7m o una cartella.")
