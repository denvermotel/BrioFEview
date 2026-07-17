"""Entry point: python -m visualizzatore [file]"""

import sys
from pathlib import Path


def _light_palette():
    """Palette chiara forzata: impedisce che la modalità scura di Windows
    filtri negli elementi nativi non coperti dal QSS (menu contestuali,
    popup delle tendine, indicatori checkbox, barre di scorrimento)."""
    from PySide6.QtGui import QColor, QPalette

    C = QColor
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, C("#F5F4EE"))
    pal.setColor(QPalette.ColorRole.WindowText, C("#2A2825"))
    pal.setColor(QPalette.ColorRole.Base, C("#FFFFFF"))
    pal.setColor(QPalette.ColorRole.AlternateBase, C("#FAF9F5"))
    pal.setColor(QPalette.ColorRole.ToolTipBase, C("#2A2825"))
    pal.setColor(QPalette.ColorRole.ToolTipText, C("#F5F4EE"))
    pal.setColor(QPalette.ColorRole.Text, C("#2A2825"))
    pal.setColor(QPalette.ColorRole.Button, C("#F5F4EE"))
    pal.setColor(QPalette.ColorRole.ButtonText, C("#2A2825"))
    pal.setColor(QPalette.ColorRole.PlaceholderText, C("#A29C90"))
    pal.setColor(QPalette.ColorRole.Highlight, C("#0E9C8C"))
    pal.setColor(QPalette.ColorRole.HighlightedText, C("#FFFFFF"))
    pal.setColor(QPalette.ColorRole.Link, C("#0E9C8C"))
    disabled = QPalette.ColorGroup.Disabled
    pal.setColor(disabled, QPalette.ColorRole.Text, C("#A8A49B"))
    pal.setColor(disabled, QPalette.ColorRole.ButtonText, C("#A8A49B"))
    pal.setColor(disabled, QPalette.ColorRole.WindowText, C("#A8A49B"))
    return pal


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from visualizzatore import APP_NAME, ORG_NAME
    from visualizzatore.ui.icons import ensure_indicator_images
    from visualizzatore.ui.main_window import MainWindow
    from visualizzatore.utils.resources import resources_dir

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setStyle("Fusion")
    app.setPalette(_light_palette())
    qss = resources_dir() / "style.qss"
    if qss.exists():
        icons_dir = ensure_indicator_images().as_posix()
        css = qss.read_text(encoding="utf-8").replace("@ICONS@", icons_dir)
        app.setStyleSheet(css)

    window = MainWindow()
    window.show()

    # file o cartella passati da riga di comando / doppio clic
    for arg in sys.argv[1:]:
        p = Path(arg)
        if p.is_dir():
            window.load_folder(p)
            break
        if p.is_file():
            window.load_file(p)
            break

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
