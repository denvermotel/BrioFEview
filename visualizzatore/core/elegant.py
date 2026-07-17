"""Formato di visualizzazione "Elegante": rappresentazione di cortesia,
propria dell'app, costruita in HTML dai dati della fattura.

Non sostituisce la fattura elettronica originale né i formati ufficiali
(ministeriale / AssoSoftware): è una resa pulita, in linea con il tema
dell'app, per lettura, stampa ed export PDF. Gestisce fattura ordinaria
e semplificata.
"""

from __future__ import annotations

from html import escape

from lxml import etree

from .invoice import Invoice, SEMPLIFICATA

# --------------------------------------------------------- tabelle codici

TIPO_DOCUMENTO = {
    "TD01": "Fattura", "TD02": "Acconto / anticipo su fattura",
    "TD03": "Acconto / anticipo su parcella", "TD04": "Nota di credito",
    "TD05": "Nota di debito", "TD06": "Parcella",
    "TD07": "Fattura semplificata", "TD08": "Nota di credito semplificata",
    "TD09": "Nota di debito semplificata",
    "TD16": "Integrazione reverse charge interno",
    "TD17": "Integrazione / autofattura acquisti dall'estero",
    "TD18": "Integrazione acquisto beni intracomunitari",
    "TD19": "Integrazione / autofattura ex art. 17 c.2",
    "TD20": "Autofattura per regolarizzazione", "TD21": "Autofattura per splafonamento",
    "TD22": "Estrazione beni da deposito IVA",
    "TD23": "Estrazione beni da deposito IVA con versamento",
    "TD24": "Fattura differita", "TD25": "Fattura differita art. 21 c.4",
    "TD26": "Cessione di beni ammortizzabili", "TD27": "Fattura per autoconsumo",
}

MODALITA_PAGAMENTO = {
    "MP01": "Contanti", "MP02": "Assegno", "MP03": "Assegno circolare",
    "MP04": "Contanti presso Tesoreria", "MP05": "Bonifico",
    "MP06": "Vaglia cambiario", "MP07": "Bollettino bancario",
    "MP08": "Carta di pagamento", "MP09": "RID", "MP10": "RID utenze",
    "MP11": "RID veloce", "MP12": "RIBA", "MP13": "MAV", "MP14": "Quietanza erario",
    "MP15": "Giroconto su conti speciali", "MP16": "Domiciliazione bancaria",
    "MP17": "Domiciliazione postale", "MP18": "Bollettino c/c postale",
    "MP19": "SEPA Direct Debit", "MP20": "SEPA Direct Debit CORE",
    "MP21": "SEPA Direct Debit B2B", "MP22": "Trattenuta su somme già riscosse",
    "MP23": "PagoPA",
}

REGIME_FISCALE = {
    "RF01": "Ordinario", "RF02": "Contribuenti minimi",
    "RF04": "Agricoltura e attività connesse", "RF05": "Vendita sali e tabacchi",
    "RF06": "Commercio fiammiferi", "RF07": "Editoria",
    "RF08": "Gestione servizi telefonia", "RF09": "Rivendita documenti di trasporto",
    "RF10": "Intrattenimenti e giochi", "RF11": "Agenzie viaggi e turismo",
    "RF12": "Agriturismo", "RF13": "Vendite a domicilio",
    "RF14": "Rivendita beni usati e oggetti d'arte", "RF15": "Agenzie vendite all'asta",
    "RF16": "IVA per cassa P.A.", "RF17": "IVA per cassa",
    "RF18": "Altro", "RF19": "Regime forfettario",
}

CONDIZIONI_PAGAMENTO = {
    "TP01": "Pagamento a rate", "TP02": "Pagamento completo", "TP03": "Anticipo",
}

ESIGIBILITA = {
    "I": "esigibilità immediata", "D": "esigibilità differita",
    "S": "scissione dei pagamenti (split payment)",
}

NATURA = {
    "N1": "Escluse ex art. 15", "N2": "Non soggette",
    "N2.1": "Non soggette ad IVA artt. 7-7septies", "N2.2": "Non soggette - altri casi",
    "N3": "Non imponibili", "N3.1": "Non imponibili - esportazioni",
    "N3.2": "Non imponibili - cessioni intracomunitarie",
    "N3.3": "Non imponibili - cessioni verso San Marino",
    "N3.4": "Non imponibili - operazioni assimilate",
    "N3.5": "Non imponibili - dichiarazioni d'intento",
    "N3.6": "Non imponibili - altre operazioni",
    "N4": "Esenti", "N5": "Regime del margine / IVA non esposta",
    "N6": "Inversione contabile (reverse charge)",
    "N6.1": "Reverse charge - rottami", "N6.2": "Reverse charge - oro e argento",
    "N6.3": "Reverse charge - subappalto edilizia", "N6.4": "Reverse charge - fabbricati",
    "N6.5": "Reverse charge - telefoni cellulari", "N6.6": "Reverse charge - elettronica",
    "N6.7": "Reverse charge - prestazioni edili", "N6.8": "Reverse charge - energia",
    "N6.9": "Reverse charge - altri casi", "N7": "IVA assolta in altro Stato UE",
}


# ---------------------------------------------------------------- helpers

def _ln(name: str) -> str:
    return f"*[local-name()='{name}']"


def _first(node, *chain):
    """Primo elemento seguendo una catena di figli per local-name."""
    cur = node
    for name in chain:
        if cur is None:
            return None
        res = cur.xpath(f"./{_ln(name)}")
        cur = res[0] if res else None
    return cur


def _deep(node, name: str):
    if node is None:
        return None
    res = node.xpath(f".//{_ln(name)}")
    return res[0] if res else None


def _t(node, *chain) -> str:
    el = _first(node, *chain)
    return (el.text or "").strip() if el is not None and el.text else ""


def _td(node, name: str) -> str:
    el = _deep(node, name)
    return (el.text or "").strip() if el is not None and el.text else ""


def _money(s: str) -> str:
    try:
        v = float(s)
    except (TypeError, ValueError):
        return escape(s or "")
    txt = f"{v:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return txt


def _dec(s: str) -> str:
    if not s:
        return ""
    try:
        float(s)
    except ValueError:
        return escape(s)
    return s.replace(".", ",")


def _date(s: str) -> str:
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return f"{s[8:10]}/{s[5:7]}/{s[0:4]}"
    return escape(s)


def _addr(sede) -> str:
    if sede is None:
        return ""
    ind = _t(sede, "Indirizzo")
    civ = _t(sede, "NumeroCivico")
    l1 = ind + (f", {civ}" if civ else "")
    cap = _t(sede, "CAP")
    com = _t(sede, "Comune")
    prov = _t(sede, "Provincia")
    l2 = " ".join(filter(None, [cap, com, f"({prov})" if prov else ""]))
    naz = _t(sede, "Nazione")
    return "<br>".join(escape(x) for x in filter(None, [l1, l2, naz]))


def _party(node) -> str:
    """Card HTML con anagrafica di cedente o cessionario."""
    if node is None:
        return "<div class='muted'>-</div>"
    den = _td(node, "Denominazione")
    if not den:
        den = " ".join(filter(None, [_td(node, "Nome"), _td(node, "Cognome")]))
    idf = _deep(node, "IdFiscaleIVA")
    piva = ""
    if idf is not None:
        piva = _t(idf, "IdPaese") + _t(idf, "IdCodice")
    cf = _td(node, "CodiceFiscale")
    sede = _deep(node, "Sede")

    rows = []
    if den:
        rows.append(f"<div class='pname'>{escape(den)}</div>")
    if piva:
        rows.append(f"<div class='pline'><span class='k'>P. IVA</span> {escape(piva)}</div>")
    if cf and cf != piva.replace('IT', ''):
        rows.append(f"<div class='pline'><span class='k'>Cod. Fisc.</span> {escape(cf)}</div>")
    addr = _addr(sede)
    if addr:
        rows.append(f"<div class='paddr'>{addr}</div>")
    reg = _td(node, "RegimeFiscale")
    if reg:
        label = REGIME_FISCALE.get(reg, "")
        rows.append(f"<div class='pline muted'>{escape(reg)}"
                    f"{' · ' + escape(label) if label else ''}</div>")
    return "".join(rows) or "<div class='muted'>-</div>"


def _aliquota_cell(aliquota: str, natura: str) -> str:
    if aliquota:
        try:
            v = float(aliquota)
            if v > 0:
                return f"{_dec(aliquota)}%"
        except ValueError:
            pass
    if natura:
        label = NATURA.get(natura, "")
        title = f" title=\"{escape(label)}\"" if label else ""
        return f"<span class='nat'{title}>{escape(natura)}</span>"
    if aliquota:
        return f"{_dec(aliquota)}%"
    return "-"


# ------------------------------------------------------------- rendering

def _render_ordinaria(root) -> str:
    ced = _deep(root, "CedentePrestatore")
    cess = _deep(root, "CessionarioCommittente")
    gen = _deep(root, "DatiGeneraliDocumento")

    tipo = _t(gen, "TipoDocumento")
    tipo_lbl = TIPO_DOCUMENTO.get(tipo, "Documento")
    numero = _t(gen, "Numero")
    data = _t(gen, "Data")
    divisa = _t(gen, "Divisa") or "EUR"
    causale = _t(gen, "Causale")

    # righe di dettaglio
    body_rows = []
    for l in root.xpath(f".//{_ln('DettaglioLinee')}"):
        n = _t(l, "NumeroLinea")
        desc = escape(_t(l, "Descrizione")).replace("\n", "<br>")
        sconti = l.xpath(f"./{_ln('ScontoMaggiorazione')}")
        notes = []
        for sc in sconti:
            tipo_sc = _t(sc, "Tipo")
            perc = _t(sc, "Percentuale")
            imp = _t(sc, "Importo")
            seg = "Sconto" if tipo_sc == "SC" else "Maggiorazione"
            if perc:
                notes.append(f"{seg} {_dec(perc)}%")
            elif imp:
                notes.append(f"{seg} € {_money(imp)}")
        if notes:
            desc += f"<div class='lnote'>{escape(' · '.join(notes))}</div>"
        qta = _dec(_t(l, "Quantita"))
        um = escape(_t(l, "UnitaMisura"))
        qta_um = " ".join(filter(None, [qta, um])) or "-"
        pu = _t(l, "PrezzoUnitario")
        pt = _t(l, "PrezzoTotale")
        aliquota = _t(l, "AliquotaIVA")
        natura = _t(l, "Natura")
        body_rows.append(
            f"<tr><td class='c'>{escape(n)}</td>"
            f"<td>{desc or '-'}</td>"
            f"<td class='r'>{qta_um}</td>"
            f"<td class='r'>{('€ ' + _money(pu)) if pu else '-'}</td>"
            f"<td class='c'>{_aliquota_cell(aliquota, natura)}</td>"
            f"<td class='r strong'>{('€ ' + _money(pt)) if pt else '-'}</td></tr>"
        )
    lines_table = (
        "<table class='lines'><thead><tr>"
        "<th class='c'>#</th><th>Descrizione</th><th class='r'>Q.tà</th>"
        "<th class='r'>Prezzo unit.</th><th class='c'>IVA</th>"
        "<th class='r'>Totale</th></tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody></table>"
    )

    # riepiloghi IVA
    rie_rows = []
    tot_imp = tot_iva = 0.0
    for r in root.xpath(f".//{_ln('DatiRiepilogo')}"):
        aliquota = _t(r, "AliquotaIVA")
        natura = _t(r, "Natura")
        imp = _t(r, "ImponibileImporto")
        iva = _t(r, "Imposta")
        esig = _t(r, "EsigibilitaIVA")
        rif = _t(r, "RiferimentoNormativo")
        try:
            tot_imp += float(imp)
        except ValueError:
            pass
        try:
            tot_iva += float(iva)
        except ValueError:
            pass
        esig_lbl = ESIGIBILITA.get(esig, "")
        extra = escape(rif) if rif else (escape(esig_lbl) if esig_lbl else "")
        rie_rows.append(
            f"<tr><td class='c'>{_aliquota_cell(aliquota, natura)}</td>"
            f"<td class='r'>€ {_money(imp)}</td>"
            f"<td class='r'>€ {_money(iva)}</td>"
            f"<td class='muted small'>{extra}</td></tr>"
        )
    rie_table = (
        "<table class='sum'><thead><tr>"
        "<th class='c'>Aliquota / Natura</th><th class='r'>Imponibile</th>"
        "<th class='r'>Imposta</th><th>Riferimento / esigibilità</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rie_rows)}</tbody></table>"
    )

    tot_doc = _t(gen, "ImportoTotaleDocumento")
    if not tot_doc:
        tot_doc = f"{tot_imp + tot_iva:.2f}"

    # pagamenti
    pay_rows = []
    for p in root.xpath(f".//{_ln('DettaglioPagamento')}"):
        mod = _t(p, "ModalitaPagamento")
        mod_lbl = MODALITA_PAGAMENTO.get(mod, mod)
        scad = _t(p, "DataScadenzaPagamento")
        iban = _t(p, "IBAN")
        importo = _t(p, "ImportoPagamento")
        dett = " · ".join(filter(None, [
            f"scad. {_date(scad)}" if scad else "",
            f"IBAN {escape(iban)}" if iban else "",
        ]))
        pay_rows.append(
            f"<tr><td>{escape(mod_lbl)}</td>"
            f"<td class='muted small'>{dett}</td>"
            f"<td class='r strong'>{('€ ' + _money(importo)) if importo else ''}</td></tr>"
        )
    cond = _td(root, "CondizioniPagamento")
    cond_lbl = CONDIZIONI_PAGAMENTO.get(cond, "")
    pay_block = ""
    if pay_rows:
        head = (f"<div class='sec-sub'>{escape(cond_lbl)}</div>" if cond_lbl else "")
        pay_block = (
            "<h2>Pagamento</h2>" + head +
            f"<table class='pay'><tbody>{''.join(pay_rows)}</tbody></table>"
        )

    totals = (
        "<table class='totals'><tbody>"
        f"<tr><td>Totale imponibile</td><td class='r'>€ {_money(f'{tot_imp:.2f}')}</td></tr>"
        f"<tr><td>Totale imposta</td><td class='r'>€ {_money(f'{tot_iva:.2f}')}</td></tr>"
        f"<tr class='grand'><td>Totale documento</td>"
        f"<td class='r'>€ {_money(tot_doc)}</td></tr>"
        "</tbody></table>"
    )

    return _document(
        tipo_lbl=tipo_lbl, numero=numero, data=data, divisa=divisa,
        ced_html=_party(ced), cess_html=_party(cess),
        causale=causale,
        lines_table=lines_table, rie_table=rie_table,
        totals=totals, pay_block=pay_block,
    )


def _render_semplificata(root) -> str:
    ced = _deep(root, "CedentePrestatore")
    cess = _deep(root, "CessionarioCommittente")
    gen = _deep(root, "DatiGenerali")

    tipo = _t(gen, "TipoDocumento")
    tipo_lbl = TIPO_DOCUMENTO.get(tipo, "Fattura semplificata")
    numero = _t(gen, "Numero")
    data = _t(gen, "Data")

    body_rows = []
    tot_imp = tot_iva = 0.0
    rie_rows = []
    for bs in root.xpath(f".//{_ln('DatiBeniServizi')}"):
        desc = escape(_t(bs, "Descrizione")).replace("\n", "<br>")
        importo = _t(bs, "Importo")
        aliquota = _t(bs, "Aliquota") or _td(bs, "Aliquota")
        natura = _t(bs, "Natura") or _td(bs, "Natura")
        iva = _td(bs, "Imposta")
        body_rows.append(
            f"<tr><td>{desc or '-'}</td>"
            f"<td class='c'>{_aliquota_cell(aliquota, natura)}</td>"
            f"<td class='r strong'>{('€ ' + _money(importo)) if importo else '-'}</td></tr>"
        )
        try:
            tot_imp += float(importo)
        except ValueError:
            pass
        try:
            tot_iva += float(iva)
        except ValueError:
            pass
        if importo or iva:
            rie_rows.append(
                f"<tr><td class='c'>{_aliquota_cell(aliquota, natura)}</td>"
                f"<td class='r'>€ {_money(importo)}</td>"
                f"<td class='r'>€ {_money(iva) if iva else '0,00'}</td></tr>"
            )

    lines_table = (
        "<table class='lines'><thead><tr>"
        "<th>Descrizione</th><th class='c'>IVA</th><th class='r'>Importo</th>"
        "</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody></table>"
    )
    rie_table = (
        "<table class='sum'><thead><tr>"
        "<th class='c'>Aliquota / Natura</th><th class='r'>Importo</th>"
        "<th class='r'>di cui imposta</th></tr></thead>"
        f"<tbody>{''.join(rie_rows)}</tbody></table>"
    )
    # nella semplificata l'Importo è già comprensivo dell'IVA
    totals = (
        "<table class='totals'><tbody>"
        f"<tr class='grand'><td>Totale documento</td>"
        f"<td class='r'>€ {_money(f'{tot_imp:.2f}')}</td></tr>"
        "</tbody></table>"
    )
    return _document(
        tipo_lbl=tipo_lbl, numero=numero, data=data, divisa="EUR",
        ced_html=_party(ced), cess_html=_party(cess), causale="",
        lines_table=lines_table, rie_table=rie_table,
        totals=totals, pay_block="",
    )


def _document(*, tipo_lbl, numero, data, divisa, ced_html, cess_html,
              causale, lines_table, rie_table, totals, pay_block) -> str:
    meta = " · ".join(filter(None, [
        f"n. {escape(numero)}" if numero else "",
        _date(data) if data else "",
        escape(divisa) if divisa and divisa != "EUR" else "",
    ]))
    causale_block = (
        f"<div class='causale'><span class='k'>Causale</span> {escape(causale)}</div>"
        if causale else ""
    )
    return f"""<!DOCTYPE html><html lang="it"><head><meta charset="utf-8">
<style>{_CSS}</style></head><body><div class="sheet">
  <header class="head">
    <div class="doc-kind">{escape(tipo_lbl)}</div>
    <div class="doc-meta">{meta}</div>
  </header>

  <table class="parties"><tr>
    <td class="party"><div class="sec-sub">Cedente / prestatore</div>{ced_html}</td>
    <td class="party"><div class="sec-sub">Cessionario / committente</div>{cess_html}</td>
  </tr></table>
  {causale_block}

  <h2>Dettaglio</h2>
  {lines_table}

  <h2>Riepilogo IVA</h2>
  {rie_table}

  {totals}

  {pay_block}

  <footer class="foot">
    Rappresentazione di cortesia generata con BrioFEview.
    Non sostituisce la fattura elettronica originale.
  </footer>
</div></body></html>"""


_CSS = """
* { box-sizing: border-box; }
body {
  margin: 0; padding: 28px 20px;
  background: #EEEBE2;
  font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  color: #2A2825; font-size: 13px; line-height: 1.5;
}
.sheet {
  max-width: 820px; margin: 0 auto; background: #FFFFFF;
  border: 1px solid #E6E3DA; border-radius: 14px;
  padding: 40px 44px 32px; box-shadow: 0 8px 30px rgba(60,50,40,0.08);
}
.head {
  display: flex; align-items: baseline; justify-content: space-between;
  border-bottom: 2px solid #0E9C8C; padding-bottom: 14px; margin-bottom: 6px;
}
.doc-kind { font-size: 22px; font-weight: 700; letter-spacing: .01em; color: #1F1E1D; }
.doc-meta { font-size: 14px; color: #78746C; }
h2 {
  font-size: 11px; text-transform: uppercase; letter-spacing: .1em;
  color: #0E9C8C; font-weight: 700; margin: 30px 0 10px;
}
.sec-sub {
  font-size: 10px; text-transform: uppercase; letter-spacing: .09em;
  color: #A29C90; font-weight: 700; margin-bottom: 8px;
}
.parties { width: 100%; border-collapse: separate; border-spacing: 14px 0; margin-top: 24px; }
.parties .party {
  width: 50%; vertical-align: top;
  background: #FAF9F5; border: 1px solid #EAE7DE; border-radius: 10px; padding: 16px 18px;
}
.pname { font-size: 15px; font-weight: 700; color: #1F1E1D; margin-bottom: 6px; }
.pline { font-size: 12.5px; margin: 2px 0; }
.paddr { font-size: 12.5px; color: #55524C; margin-top: 8px; }
.k { display: inline-block; min-width: 62px; color: #A29C90; font-size: 11px;
     text-transform: uppercase; letter-spacing: .04em; }
.causale { margin-top: 16px; font-size: 13px; }
.muted { color: #A29C90; }
.small { font-size: 11.5px; }

table.lines, table.sum, table.pay, table.totals {
  width: 100%; border-collapse: collapse; margin-top: 4px;
}
table.lines th, table.sum th {
  text-align: left; font-size: 10.5px; text-transform: uppercase; letter-spacing: .05em;
  color: #8A857B; font-weight: 700; padding: 8px 10px;
  border-bottom: 1.5px solid #E6E3DA; background: #FAF9F5;
}
table.lines td, table.sum td, table.pay td {
  padding: 10px; border-bottom: 1px solid #EFEDE5; vertical-align: top; font-size: 12.5px;
}
table.lines tbody tr:last-child td, table.sum tbody tr:last-child td { border-bottom: none; }
.r { text-align: right; white-space: nowrap; }
.c { text-align: center; }
.strong { font-weight: 700; color: #1F1E1D; }
.lnote { font-size: 11px; color: #A29C90; margin-top: 3px; }
.nat { font-weight: 600; color: #9A6A3A; }

table.totals { width: 300px; margin-left: auto; margin-top: 18px; }
table.totals td { padding: 6px 10px; font-size: 13px; }
table.totals tr.grand td {
  border-top: 2px solid #0E9C8C; padding-top: 12px;
  font-size: 17px; font-weight: 700; color: #0E9C8C;
}
table.pay td { border-bottom: 1px solid #EFEDE5; }

.foot {
  margin-top: 34px; padding-top: 14px; border-top: 1px solid #EFEDE5;
  font-size: 10.5px; color: #B0AB9F; line-height: 1.5;
}

@media print {
  body { background: #FFFFFF; padding: 0; }
  .sheet { border: none; border-radius: 0; box-shadow: none; max-width: none;
           padding: 8px 4px; }
}
"""


def render(invoice: Invoice) -> str:
    """HTML del formato Elegante per la fattura (ordinaria o semplificata)."""
    root = invoice.tree.getroot()
    if invoice.kind == SEMPLIFICATA:
        return _render_semplificata(root)
    return _render_ordinaria(root)
