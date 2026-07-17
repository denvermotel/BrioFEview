"""Dialog impostazioni: formato predefinito, naming batch, associazioni file."""

from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QVBoxLayout,
)

from .. import APP_NAME
from ..core import transform
from ..utils import file_assoc


class SettingsDialog(QDialog):
    def __init__(self, settings: QSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Impostazioni")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)

        # --- visualizzazione
        vis_box = QGroupBox("Visualizzazione")
        form = QFormLayout(vis_box)
        self.combo_fmt = QComboBox()
        for key, label in transform.FORMAT_LABELS.items():
            self.combo_fmt.addItem(label, key)
        idx = self.combo_fmt.findData(settings.value("formato", transform.MINISTERIALE))
        self.combo_fmt.setCurrentIndex(max(0, idx))
        form.addRow("Formato predefinito:", self.combo_fmt)

        self.combo_naming = QComboBox()
        self.combo_naming.addItem("Nome del file di origine", "origine")
        self.combo_naming.addItem("Cedente + numero + data", "metadati")
        idx = self.combo_naming.findData(settings.value("naming_pdf", "origine"))
        self.combo_naming.setCurrentIndex(max(0, idx))
        form.addRow("Nome PDF predefinito:", self.combo_naming)
        layout.addWidget(vis_box)

        # --- associazioni file (solo Windows)
        self.checks: dict[tuple[str, str], QCheckBox] = {}
        if file_assoc.AVAILABLE:
            self._build_assoc_box(layout)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_assoc_box(self, layout: QVBoxLayout) -> None:
        assoc_box = QGroupBox("Associazioni file di Windows (utente corrente)")
        assoc_lay = QVBoxLayout(assoc_box)
        assoc_lay.addWidget(QLabel(
            "«Apri con»: l'app compare nel menu contestuale.\n"
            "«Predefinita»: doppio clic sul file apre direttamente l'app."))

        for ext in (".xml", ".p7m"):
            open_with, default = file_assoc.get_status(ext)
            cb_ow = QCheckBox(f"Mostra in «Apri con» per i file {ext}")
            cb_ow.setChecked(open_with)
            cb_def = QCheckBox(f"App predefinita per i file {ext}")
            cb_def.setChecked(default)
            assoc_lay.addWidget(cb_ow)
            assoc_lay.addWidget(cb_def)
            self.checks[(ext, "open_with")] = cb_ow
            self.checks[(ext, "default")] = cb_def

        note = QLabel(
            "Nota: se Windows ha già un programma predefinito scelto manualmente, "
            "la scelta dell'utente in Esplora File ha la precedenza.")
        note.setWordWrap(True)
        note.setStyleSheet("color: gray; font-size: 11px;")
        assoc_lay.addWidget(note)
        layout.addWidget(assoc_box)

    def _save(self) -> None:
        self.settings.setValue("formato", self.combo_fmt.currentData())
        self.settings.setValue("naming_pdf", self.combo_naming.currentData())

        try:
            if not self.checks:
                self.accept()
                return
            for ext in (".xml", ".p7m"):
                open_with_now, default_now = file_assoc.get_status(ext)
                want_ow = self.checks[(ext, "open_with")].isChecked()
                want_def = self.checks[(ext, "default")].isChecked()
                if want_def and not want_ow:
                    # predefinita implica "Apri con"
                    want_ow = True
                    self.checks[(ext, "open_with")].setChecked(True)
                if want_def != default_now:
                    file_assoc.set_default(ext, want_def)
                if want_ow != open_with_now:
                    file_assoc.set_open_with(ext, want_ow)
        except OSError as exc:
            QMessageBox.warning(self, APP_NAME,
                                f"Impossibile aggiornare il registro di Windows:\n{exc}")
        self.accept()
