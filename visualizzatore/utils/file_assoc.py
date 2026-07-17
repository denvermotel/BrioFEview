"""Registrazione delle associazioni file (.xml / .p7m) in HKCU.

Scrive solo sotto HKEY_CURRENT_USER\\Software\\Classes: nessun privilegio
amministrativo richiesto. Due livelli per estensione:
- "Apri con": l'app compare nel menu contestuale "Apri con" (OpenWithProgids)
- predefinita: l'app diventa il programma di default per l'estensione
  (nota: se l'utente ha già scelto un default da Esplora File, Windows
  mantiene la sua scelta in UserChoice, che ha priorità).
"""

from __future__ import annotations

import ctypes
import sys

try:
    import winreg
except ImportError:  # non-Windows: le associazioni non sono disponibili
    winreg = None

from .. import PROG_ID, APP_NAME

_EXTENSIONS = (".xml", ".p7m")

AVAILABLE = winreg is not None


def _exe_command() -> str:
    if getattr(sys, "frozen", False):
        exe = sys.executable
        return f'"{exe}" "%1"'
    # in sviluppo: lancia il modulo con l'interprete corrente
    return f'"{sys.executable}" -m visualizzatore "%1"'


def _icon_ref() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}",0'
    return ""


def register_progid() -> None:
    """Crea/aggiorna il ProgID dell'applicazione."""
    if not AVAILABLE:
        return
    base = rf"Software\Classes\{PROG_ID}"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base) as k:
        winreg.SetValue(k, "", winreg.REG_SZ, "Fattura elettronica XML - BrioFEview")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\shell\open\command") as k:
        winreg.SetValue(k, "", winreg.REG_SZ, _exe_command())
    icon = _icon_ref()
    if icon:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\DefaultIcon") as k:
            winreg.SetValue(k, "", winreg.REG_SZ, icon)
    # nome leggibile nel menu "Apri con"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\Application") as k:
        winreg.SetValueEx(k, "ApplicationName", 0, winreg.REG_SZ, APP_NAME)


def set_open_with(ext: str, enabled: bool) -> None:
    """Aggiunge/rimuove l'app dal menu 'Apri con' per l'estensione."""
    if not AVAILABLE:
        return
    assert ext in _EXTENSIONS
    key_path = rf"Software\Classes\{ext}\OpenWithProgids"
    if enabled:
        register_progid()
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as k:
            winreg.SetValueEx(k, PROG_ID, 0, winreg.REG_NONE, b"")
    else:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                                winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, PROG_ID)
        except FileNotFoundError:
            pass
    _notify_shell()


def set_default(ext: str, enabled: bool) -> None:
    """Imposta/rimuove l'app come predefinita per l'estensione."""
    if not AVAILABLE:
        return
    assert ext in _EXTENSIONS
    key_path = rf"Software\Classes\{ext}"
    if enabled:
        register_progid()
        set_open_with(ext, True)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as k:
            winreg.SetValue(k, "", winreg.REG_SZ, PROG_ID)
    else:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                                winreg.KEY_ALL_ACCESS) as k:
                current, _ = winreg.QueryValueEx(k, "")
                if current == PROG_ID:
                    winreg.DeleteValue(k, "")
        except FileNotFoundError:
            pass
    _notify_shell()


def get_status(ext: str) -> tuple[bool, bool]:
    """Ritorna (in_apri_con, predefinita) per l'estensione."""
    open_with = False
    default = False
    if not AVAILABLE:
        return open_with, default
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            rf"Software\Classes\{ext}\OpenWithProgids") as k:
            winreg.QueryValueEx(k, PROG_ID)
            open_with = True
    except FileNotFoundError:
        pass
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            rf"Software\Classes\{ext}") as k:
            current, _ = winreg.QueryValueEx(k, "")
            default = current == PROG_ID
    except FileNotFoundError:
        pass
    return open_with, default


def _notify_shell() -> None:
    """Informa Esplora File che le associazioni sono cambiate."""
    if not AVAILABLE:
        return
    SHCNE_ASSOCCHANGED = 0x08000000
    SHCNF_IDLIST = 0x0
    try:
        ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, None, None)
    except Exception:
        pass
