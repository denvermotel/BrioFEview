"""Caricamento fatture elettroniche: XML puro o .p7m firmato.

Rileva il tipo di fattura (ordinaria / semplificata) dal root element ed
estrae i metadati essenziali (cedente, numero, data) usati per il naming
dei PDF in modalità batch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

from . import p7m


class InvoiceError(Exception):
    """Il file non è una fattura elettronica leggibile."""


ORDINARIA = "ordinaria"
SEMPLIFICATA = "semplificata"

# Namespace noti dei tracciati FatturaPA / Fattura B2B
_KNOWN_NS = {
    "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2",
    "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.0",
    "http://www.fatturapa.gov.it/sdi/fatturapa/v1.1",
    "http://www.fatturapa.gov.it/sdi/fatturapa/v1.0",
}


@dataclass
class Invoice:
    path: Path
    xml_bytes: bytes
    tree: etree._ElementTree
    kind: str  # ORDINARIA | SEMPLIFICATA
    signed: bool
    cedente: str = ""
    numero: str = ""
    data: str = ""  # ISO yyyy-mm-dd
    warnings: list[str] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        return self.path.name

    def suggested_pdf_name(self, mode: str) -> str:
        """Nome PDF suggerito: mode = 'origine' | 'metadati'."""
        if mode == "metadati" and (self.cedente or self.numero):
            parts = []
            if self.cedente:
                parts.append(self.cedente)
            if self.numero:
                parts.append(f"n.{self.numero}")
            if self.data:
                parts.append(f"del {self.data}")
            name = " - ".join(parts)
            name = re.sub(r'[\\/:*?"<>|]', "_", name).strip()
            return name[:150] + ".pdf"
        stem = self.path.name
        for suffix in (".p7m", ".P7M"):
            if stem.endswith(suffix):
                stem = stem[: -len(suffix)]
        return Path(stem).stem + ".pdf"


def _local_name(el: etree._Element) -> str:
    return etree.QName(el).localname


def _find_text(root: etree._Element, xpath: str) -> str:
    res = root.xpath(xpath)
    if res and res[0].text:
        return res[0].text.strip()
    return ""


def _extract_metadata(inv: Invoice) -> None:
    root = inv.tree.getroot()
    # XPath insensibili al namespace (local-name) per coprire tutte le versioni
    ana = "//*[local-name()='CedentePrestatore']"
    inv.cedente = (
        _find_text(root, f"{ana}//*[local-name()='Denominazione']")
        or " ".join(
            filter(None, [
                _find_text(root, f"{ana}//*[local-name()='Nome']"),
                _find_text(root, f"{ana}//*[local-name()='Cognome']"),
            ])
        )
    )
    gen = "//*[local-name()='DatiGeneraliDocumento']"
    if inv.kind == SEMPLIFICATA:
        gen = "//*[local-name()='DatiGenerali']"
    inv.numero = _find_text(root, f"{gen}/*[local-name()='Numero']")
    inv.data = _find_text(root, f"{gen}/*[local-name()='Data']")[:10]


def _strip_leading_junk(data: bytes) -> bytes:
    """Rimuove BOM/spazi prima della dichiarazione XML."""
    data = data.lstrip(b"\xef\xbb\xbf\xff\xfe\x00 \t\r\n")
    idx = data.find(b"<")
    return data[idx:] if idx > 0 else data


def load(path: str | Path) -> Invoice:
    """Carica una fattura da file .xml o .xml.p7m."""
    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise InvoiceError(f"Impossibile leggere il file: {exc}") from exc

    signed = False
    if path.suffix.lower() == ".p7m":
        try:
            xml_bytes = p7m.extract_xml(raw)
            signed = True
        except p7m.P7MError as exc:
            raise InvoiceError(str(exc)) from exc
    else:
        xml_bytes = raw
        # Alcuni gestionali salvano p7m con estensione .xml: riconoscilo
        if not raw.lstrip()[:1] == b"<":
            try:
                xml_bytes = p7m.extract_xml(raw)
                signed = True
            except p7m.P7MError:
                xml_bytes = raw  # tenta comunque il parse XML

    xml_bytes = _strip_leading_junk(xml_bytes)

    try:
        parser = etree.XMLParser(recover=False, resolve_entities=False, no_network=True)
        tree = etree.ElementTree(etree.fromstring(xml_bytes, parser=parser))
    except etree.XMLSyntaxError as exc:
        raise InvoiceError(f"XML non valido: {exc}") from exc

    root = tree.getroot()
    local = _local_name(root)
    ns = etree.QName(root).namespace or ""

    if local == "FatturaElettronicaSemplificata":
        kind = SEMPLIFICATA
    elif local == "FatturaElettronica":
        kind = ORDINARIA
    else:
        raise InvoiceError(
            f"Il file non è una fattura elettronica (elemento radice: {local})."
        )

    inv = Invoice(path=path, xml_bytes=xml_bytes, tree=tree, kind=kind, signed=signed)
    if ns and ns not in _KNOWN_NS:
        inv.warnings.append(f"Namespace non riconosciuto: {ns}")
    _extract_metadata(inv)
    return inv


def scan_folder(folder: str | Path) -> list[Path]:
    """Elenca i file fattura (xml / p7m) in una cartella, non ricorsivo."""
    folder = Path(folder)
    out: list[Path] = []
    for p in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
        if p.is_file() and p.suffix.lower() in (".xml", ".p7m"):
            out.append(p)
    return out
