"""Trasformazioni XSLT fattura -> HTML.

Due formati di visualizzazione:
- ministeriale: foglio di stile AdE (ordinaria o semplificata, scelto in base
  al tipo di fattura)
- assosoftware: foglio di stile AssoSoftware (solo fattura ordinaria; per la
  semplificata si usa il ministeriale con avviso)
"""

from __future__ import annotations

from functools import lru_cache

from lxml import etree

from ..utils.resources import xsl_path
from .invoice import Invoice, SEMPLIFICATA

ELEGANTE = "elegante"
MINISTERIALE = "ministeriale"
ASSOSOFTWARE = "assosoftware"
XML_VIEW = "xml"

# formati di stampa (usati anche dal batch)
FORMAT_LABELS = {
    ELEGANTE: "Elegante",
    MINISTERIALE: "Ministeriale",
    ASSOSOFTWARE: "AssoSoftware",
}

# viste disponibili nella finestra principale
VIEW_LABELS = {**FORMAT_LABELS, XML_VIEW: "Codice XML"}

_XSL_FILES = {
    "ordinaria_min": "Foglio_di_stile_fattura_ordinaria_ver1.2.3.xsl",
    "semplificata_min": "Foglio_di_stile_VFSM10_v1.0.2.xsl",
    "assosoftware": "FoglioStileAssoSoftware.xsl",
}


class TransformError(Exception):
    pass


@lru_cache(maxsize=None)
def _stylesheet(key: str) -> etree.XSLT:
    path = xsl_path(_XSL_FILES[key])
    try:
        return etree.XSLT(etree.parse(str(path)))
    except (OSError, etree.LxmlError) as exc:
        raise TransformError(f"Foglio di stile non caricabile ({path.name}): {exc}") from exc


def to_html(invoice: Invoice, fmt: str) -> tuple[str, str | None]:
    """Trasforma la fattura in HTML.

    Ritorna (html, avviso). L'avviso è valorizzato se è stato applicato un
    fallback (es. semplificata richiesta in formato AssoSoftware).
    """
    warning = None
    if fmt == ELEGANTE:
        from .elegant import render
        return render(invoice), None
    if fmt == ASSOSOFTWARE and invoice.kind == SEMPLIFICATA:
        key = "semplificata_min"
        warning = (
            "Il foglio di stile AssoSoftware non supporta la fattura "
            "semplificata: visualizzazione in formato ministeriale."
        )
    elif fmt == ASSOSOFTWARE:
        key = "assosoftware"
    elif invoice.kind == SEMPLIFICATA:
        key = "semplificata_min"
    else:
        key = "ordinaria_min"

    xslt = _stylesheet(key)
    try:
        result = xslt(invoice.tree)
    except etree.XSLTApplyError as exc:
        raise TransformError(f"Errore nella trasformazione XSLT: {exc}") from exc

    html = str(result)
    if not html.strip():
        raise TransformError("La trasformazione ha prodotto un documento vuoto.")
    return html, warning


# ------------------------------------------------------- vista codice XML

import html as _html
import re as _re

_TAG_RE = _re.compile(r"(<[^>]*>)", _re.DOTALL)
# opera sul testo già passato da html.escape: le virgolette sono &quot;/&#x27;
_ATTR_RE = _re.compile(r"([\w:.-]+)(=)(&quot;.*?&quot;|&#x27;.*?&#x27;)")

_XML_CSS = """
body { margin: 0; background: #fdfdfd; }
pre { font: 12px/1.5 Consolas, 'Courier New', monospace; margin: 0;
      padding: 12px 16px; white-space: pre; counter-reset: line; }
pre span.ln { display: inline-block; width: 3.5em; color: #b0b0b0;
      text-align: right; padding-right: 1em; user-select: none; }
.tag  { color: #22548e; }
.attr { color: #8a5a00; }
.val  { color: #1e7a1e; }
.com  { color: #909090; font-style: italic; }
.decl { color: #7a3fa0; }
.txt  { color: #222; }
"""


def _colorize_tag(tag: str) -> str:
    esc = _html.escape(tag)
    if tag.startswith("<!--"):
        return f'<span class="com">{esc}</span>'
    if tag.startswith("<?") or tag.startswith("<!"):
        return f'<span class="decl">{esc}</span>'

    def attr_sub(m: _re.Match) -> str:
        return (f'<span class="attr">{m.group(1)}</span>{m.group(2)}'
                f'<span class="val">{m.group(3)}</span>')

    return f'<span class="tag">{_ATTR_RE.sub(attr_sub, esc)}</span>'


def source_html(invoice: Invoice) -> str:
    """Codice XML della fattura, riformattato ed evidenziato, come HTML."""
    # reindenta: riparsa senza i whitespace originali per un pretty print pulito
    parser = etree.XMLParser(remove_blank_text=True, resolve_entities=False,
                             no_network=True)
    try:
        tree = etree.fromstring(invoice.xml_bytes, parser=parser)
        pretty = etree.tostring(tree, pretty_print=True, encoding="unicode")
    except etree.XMLSyntaxError:
        pretty = invoice.xml_bytes.decode("utf-8", errors="replace")

    parts: list[str] = []
    for token in _TAG_RE.split(pretty):
        if not token:
            continue
        if token.startswith("<"):
            parts.append(_colorize_tag(token))
        else:
            parts.append(f'<span class="txt">{_html.escape(token)}</span>')
    body = "".join(parts)

    # numeri di riga
    lines = body.split("\n")
    numbered = "\n".join(
        f'<span class="ln">{i + 1}</span>{line}' for i, line in enumerate(lines)
    )
    return (f"<html><head><meta charset='utf-8'><style>{_XML_CSS}</style></head>"
            f"<body><pre>{numbered}</pre></body></html>")
