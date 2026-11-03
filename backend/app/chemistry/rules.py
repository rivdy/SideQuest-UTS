"""Versioned structural patterns, deliberately separate from LKPI R-01 through R-12."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from .evidence import BY_ID, Evidence


class DraftRule(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    smarts: str
    status: Literal["draft"] = "draft"
    version: str = "2"
    evidence: tuple[Evidence, ...] = ()
    chemical_evidence: str = "belum ada sumber"
    scope: str = "Deteksi substruktur saja; belum menetapkan risiko reaksi atau kompatibilitas."


RULESET_VERSION = "literature-draft-2"
RULES = (
    DraftRule(
        id="DRAFT-ALKENE",
        name="Ikatan karbon rangkap nonaromatik",
        smarts="[C]=[C]",
        evidence=(BY_ID["DOI:10.1039/C8RE00094H"], BY_ID["DOI:10.1002/ffj.3210"]),
        chemical_evidence="Literatur kontekstual limonene; bukan prediksi untuk setiap alkena.",
    ),
    DraftRule(
        id="DRAFT-ALDEHYDE",
        name="Aldehida",
        smarts="[CX3H1](=O)[#6]",
        evidence=(BY_ID["DOI:10.1039/C5RA02234G"],),
        chemical_evidence="Abstrak oksidasi berkatalis; penerapan pada formula belum dinilai.",
    ),
    DraftRule(
        id="DRAFT-ALCOHOL",
        name="Alkohol",
        smarts="[OX2H][CX4]",
        evidence=(BY_ID["DOI:10.1039/C8RE00085A"],),
        chemical_evidence="Studi alkohol primer berkatalis; bukan aturan untuk seluruh alkohol.",
    ),
    DraftRule(
        id="DRAFT-PHENOL",
        name="Fenol",
        smarts="[OX2H][c]",
        evidence=(BY_ID["DOI:10.1039/C9RA02021G"],),
        chemical_evidence="Studi fenol berkatalis; bukan bukti untuk seluruh fenol parfum.",
    ),
    DraftRule(id="DRAFT-ESTER", name="Ester", smarts="[CX3](=O)[OX2][#6]"),
    DraftRule(id="DRAFT-PEROXIDE", name="Ikatan peroksida", smarts="[OX2][OX2]"),
)
