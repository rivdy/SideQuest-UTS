"""Explicit external lookup, fixed NIH endpoint, no silent cached substitute."""

from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import BaseModel, Field


class PubChemClient(httpx.Client):
    """Independent transport seam for tests."""


class PubChemResult(BaseModel):
    cid: int = Field(gt=0)
    title: str
    smiles: str
    molecular_formula: str
    source_url: str
    retrieved_at: str
    identity_note: str = "Konfirmasi identitas/isomer dengan SDS pemasok sebelum digunakan."


class LookupFailure(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


def lookup(query: str, namespace: str) -> PubChemResult:
    # Name is sent as POST form data, never interpolated into an arbitrary URL.
    root = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/"
    props = "/property/Title,MolecularFormula,IsomericSMILES/JSON"
    if namespace == "cid":
        if not query.isascii() or not query.isdigit() or not 0 < int(query) < 10**12:
            raise LookupFailure("CID harus berupa bilangan bulat positif.", 422)
        url, data = root + "cid/" + str(int(query)) + props, None
    else:
        url, data = root + "name" + props, {"name": query}
    try:
        with PubChemClient(timeout=15, trust_env=False, follow_redirects=False) as client:
            response = client.request("POST" if data else "GET", url, data=data)
        if response.status_code == 404:
            raise LookupFailure("Senyawa tidak ditemukan di PubChem.", 404)
        if response.status_code in {429, 503}:
            raise LookupFailure("PubChem sedang membatasi permintaan. Coba lagi nanti.", 503)
        response.raise_for_status()
        payload: Any = response.json()
        rows = payload["PropertyTable"]["Properties"]
        if len(rows) != 1:
            raise LookupFailure("Identitas ambigu. Gunakan CID yang sesuai SDS pemasok.", 409)
        row = rows[0]
        smiles = row.get("SMILES") or row.get("IsomericSMILES")
        if not isinstance(smiles, str) or not 1 <= len(smiles) <= 2000:
            raise LookupFailure("PubChem tidak menyediakan SMILES yang didukung.")
        return PubChemResult(
            cid=int(row["CID"]),
            title=row.get("Title", query),
            smiles=smiles,
            molecular_formula=row["MolecularFormula"],
            source_url="https://pubchem.ncbi.nlm.nih.gov/compound/" + str(int(row["CID"])),
            retrieved_at=datetime.now(UTC).isoformat(),
        )
    except httpx.TimeoutException as exc:
        raise LookupFailure("PubChem tidak merespons dalam batas waktu.", 504) from exc
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        raise LookupFailure("Respons PubChem tidak dapat diproses. Coba lagi nanti.") from exc
