"""Organization-scoped records and deterministic candidate comparison."""

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from .auth import require_editor
from .db import Record, audit, database
from .ranking import rank_candidates
from .schemas import Assessment, ExperimentInput, FormulationInput, RankInput

router = APIRouter(prefix="/api/workspace", tags=["workspace"])


def records(org: str, kind: str) -> list[dict]:
    with database() as db:
        rows = db.scalars(
            select(Record)
            .where(Record.org_id == org, Record.kind == kind, Record.archived.is_(False))
            .order_by(Record.created.desc())
        ).all()
        return [{"id": r.id, "created": r.created, **r.data} for r in rows]


def owned(db, org: str, record_id: str, kind: str) -> Record:
    row = db.scalar(
        select(Record).where(
            Record.id == record_id,
            Record.org_id == org,
            Record.kind == kind,
            Record.archived.is_(False),
        )
    )
    if row is None:
        raise HTTPException(404, "Data tidak ditemukan dalam organisasi ini.")
    return row


def save_record(actor: dict, kind: str, data: dict[str, Any]) -> dict:
    with database() as db:
        row = Record(org_id=actor["org_id"], kind=kind, data=data, created_by=actor["id"])
        db.add(row)
        db.flush()
        audit(db, actor["org_id"], actor["id"], "create_" + kind, row.id)
        return {"id": row.id, "created": row.created, **data}


@router.get("/overview")
def overview(request: Request) -> dict:
    org = request.state.user["org_id"]
    forms, trials, runs = (
        records(org, "formulation"),
        records(org, "experiment"),
        records(org, "model_run"),
    )
    return {
        "formulations": len(forms),
        "experiments": len(trials),
        "real_experiments": sum(e["data_origin"] == "real" for e in trials),
        "synthetic_experiments": sum(e["data_origin"] == "synthetic" for e in trials),
        "model_runs": len(runs),
    }


@router.get("/formulations")
def formulations(request: Request) -> list[dict]:
    return records(request.state.user["org_id"], "formulation")


@router.post("/formulations", status_code=201)
def create_formulation(payload: FormulationInput, request: Request) -> dict:
    actor = require_editor(request)
    return save_record(
        actor,
        "formulation",
        {**payload.model_dump(), "composition_hash": payload.fingerprint(), "assessment": None},
    )


@router.put("/formulations/{record_id}/assessment")
def assess(record_id: str, payload: Assessment, request: Request) -> dict:
    actor = require_editor(request)
    with database() as db:
        row = owned(db, actor["org_id"], record_id, "formulation")
        row.data = {**row.data, "assessment": payload.model_dump(), "assessed_at": time.time()}
        audit(db, actor["org_id"], actor["id"], "assess_formulation", row.id)
    return {"ok": True}


@router.post("/rank")
def rank(payload: RankInput, request: Request) -> dict:
    selected = []
    with database() as db:
        for record_id in payload.formulation_ids:
            row = owned(db, request.state.user["org_id"], record_id, "formulation")
            selected.append({"id": row.id, **row.data})
    origins = {c["data_origin"] for c in selected}
    if len(origins) != 1:
        raise HTTPException(
            422, "Bandingkan kandidat nyata dan kandidat ilustrasi secara terpisah."
        )
    return rank_candidates(selected, payload.weights, payload.comparison_protocol)


@router.get("/experiments")
def experiments(request: Request) -> list[dict]:
    return records(request.state.user["org_id"], "experiment")


@router.post("/experiments", status_code=201)
def create_experiment(payload: ExperimentInput, request: Request) -> dict:
    actor = require_editor(request)
    with database() as db:
        form = owned(db, actor["org_id"], payload.formulation_id, "formulation")
        if form.data["data_origin"] == "synthetic" and payload.data_origin == "real":
            raise HTTPException(
                422, "Formulasi ilustrasi tidak dapat menghasilkan catatan lab nyata."
            )
        duplicate = [
            x
            for x in records(actor["org_id"], "experiment")
            if x["formulation_id"] == payload.formulation_id
            and x["batch_id"] == payload.batch_id
            and x["protocol"] == payload.protocol
            and x["duration_days"] == payload.duration_days
        ]
        if duplicate:
            raise HTTPException(409, "Pengukuran batch/protokol/hari ini sudah tercatat.")
        totals = {
            role: sum(i["percent"] for i in form.data["ingredients"] if i["role"] == role)
            for role in ["fragrance", "solubilizer", "stabilizer"]
        }
        snapshot = {
            "formulation_name": form.data["name"],
            "composition_hash": form.data["composition_hash"],
            "composition_features": totals,
        }
    return save_record(
        actor,
        "experiment",
        {
            **payload.model_dump(),
            **snapshot,
            "retention_pct": round(payload.final_h2o2 / payload.initial_h2o2 * 100, 6),
        },
    )


@router.delete("/experiments/{record_id}")
def void_experiment(record_id: str, request: Request) -> dict:
    actor = require_editor(request)
    with database() as db:
        row = owned(db, actor["org_id"], record_id, "experiment")
        row.archived = True
        audit(db, actor["org_id"], actor["id"], "void_experiment", row.id)
    return {"ok": True, "message": "Catatan dibatalkan; audit dan model terdahulu tetap disimpan."}
