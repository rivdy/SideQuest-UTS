"""Read-only chemistry endpoints for the local prototype."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.rag.api import guard

from .engine import ScreeningResult, screen
from .evidence import SOURCES
from .pubchem import LookupFailure, PubChemResult, lookup
from .rules import RULES, RULESET_VERSION

router = APIRouter(prefix="/api/chemistry", tags=["chemistry-draft"])


class StructureInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    smiles: str = Field(min_length=1, max_length=2000)


class BatchItem(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    label: str = Field(min_length=1, max_length=120)
    smiles: str = Field(min_length=1, max_length=2000)


class BatchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[BatchItem] = Field(min_length=1, max_length=30)


class LookupInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    query: str = Field(min_length=1, max_length=160)
    namespace: Literal["name", "cid"] = "name"
    consent_external_lookup: Literal[True]


@router.get("/rules")
def rules(request: Request) -> dict:
    guard(request, "chemistry-read", 120)
    return {"version": RULESET_VERSION, "rules": RULES, "validated_rules": 0}


@router.post("/screen", response_model=ScreeningResult)
def screen_structure(payload: StructureInput, request: Request) -> ScreeningResult:
    guard(request, "chemistry-screen", 60)
    try:
        return screen(payload.smiles)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/screen-batch")
def screen_composition(payload: BatchInput, request: Request) -> dict:
    """Screen every component of a composition; one invalid component never hides the rest."""
    guard(request, "chemistry-screen", 60)
    items = []
    for item in payload.items:
        try:
            result = screen(item.smiles)
        except ValueError as exc:
            items.append({"label": item.label, "ok": False, "error": str(exc)})
            continue
        items.append(
            {
                "label": item.label,
                "ok": True,
                "canonical_smiles": result.canonical_smiles,
                "molecular_formula": result.molecular_formula,
                "matches": [
                    {"id": m.rule.id, "name": m.rule.name, "count": m.count} for m in result.matches
                ],
            }
        )
    with_match = {
        rule.id: sum(any(m["id"] == rule.id for m in i.get("matches", [])) for i in items)
        for rule in RULES
    }
    return {
        "ruleset_version": RULESET_VERSION,
        "items": items,
        "components_with_match": with_match,
        "risk_status": "not_assessed",
        "message": (
            "Deteksi substruktur per komponen dengan pola draft. Ini bukan skor risiko, "
            "dan tidak menilai kadar, pH, suhu, logam jejak, atau interaksi campuran."
        ),
    }


@router.post("/pubchem", response_model=PubChemResult)
def lookup_pubchem(payload: LookupInput, request: Request) -> PubChemResult:
    guard(request, "chemistry-pubchem", 20)
    try:
        return lookup(payload.query, payload.namespace)
    except LookupFailure as exc:
        raise HTTPException(exc.status, str(exc)) from exc


@router.get("/evidence")
def evidence_catalog(request: Request) -> dict:
    guard(request, "chemistry-read", 120)
    return {"version": RULESET_VERSION, "sources": SOURCES, "validated_rules": 0}
