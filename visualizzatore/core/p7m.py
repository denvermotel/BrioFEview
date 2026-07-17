"""Estrazione del contenuto XML da file firmati CAdES (.p7m).

Non esegue verifica della firma: estrae soltanto il documento incapsulato
nella struttura CMS/PKCS#7 SignedData. Gestisce sia file DER binari sia
file codificati Base64 (entrambi circolano con estensione .p7m).
"""

import base64
import re

from asn1crypto import cms


class P7MError(Exception):
    """Il file .p7m non è leggibile o non contiene dati."""


def _try_base64_decode(data: bytes) -> bytes | None:
    """Decodifica Base64 se il contenuto sembra codificato, altrimenti None."""
    sample = data[:1024].strip()
    if not sample:
        return None
    # Un DER inizia con 0x30 (SEQUENCE); se già binario non è Base64
    if sample[:1] == b"\x30":
        return None
    if not re.fullmatch(rb"[A-Za-z0-9+/=\s\r\n-]+", sample):
        return None
    try:
        return base64.b64decode(re.sub(rb"\s+", b"", data), validate=True)
    except Exception:
        return None


def extract_xml(data: bytes) -> bytes:
    """Estrae il payload XML dai byte di un file .p7m.

    Solleva P7MError se la struttura CMS non è valida o è priva di contenuto.
    """
    decoded = _try_base64_decode(data)
    if decoded is not None:
        data = decoded

    try:
        content_info = cms.ContentInfo.load(data)
    except Exception as exc:
        raise P7MError(f"Struttura PKCS#7/CMS non valida: {exc}") from exc

    if content_info["content_type"].native != "signed_data":
        raise P7MError(
            f"Tipo CMS non gestito: {content_info['content_type'].native}"
        )

    encap = content_info["content"]["encap_content_info"]
    payload = encap["content"].native
    if payload is None:
        raise P7MError("Il file firmato non incapsula alcun contenuto (firma detached).")
    return payload


def extract_xml_from_file(path: str) -> bytes:
    with open(path, "rb") as fh:
        return extract_xml(fh.read())
