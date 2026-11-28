"""Endpoints for the formulation page: local ingredient library and rule-based drafts."""

from fastapi import APIRouter, HTTPException, Request

from app.rag.api import guard

from .draft import AlternativeInput, DraftInput, alternative, build_draft
from .library import aroma_profiles, materials
from .text_alternative import TextAlternativeInput, text_alternative

router = APIRouter(prefix="/api/formulation", tags=["formulation"])


@router.get("/library")
def library(request: Request) -> dict:
    guard(request, "formulation-read", 120)
    try:
        return {"materials": list(materials()), "aroma_profiles": aroma_profiles()}
    except FileNotFoundError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post("/draft")
def draft(payload: DraftInput, request: Request) -> dict:
    guard(request, "formulation-draft", 60)
    try:
        return build_draft(payload)
    except FileNotFoundError as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/alternative")
def alternative_formula(payload: AlternativeInput, request: Request) -> dict:
    guard(request, "formulation-draft", 60)
    try:
        return alternative(payload)
    except FileNotFoundError as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/alternative-text")
def alternative_from_text(payload: TextAlternativeInput, request: Request) -> dict:
    guard(request, "formulation-draft", 60)
    try:
        return text_alternative(payload)
    except FileNotFoundError as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
