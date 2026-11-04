"""Actual regression training with grouped holdout and explicit target boundaries."""

import csv
import hashlib
import json
import math
import os
import threading
import time
from functools import lru_cache
from pathlib import Path

import numpy as np
from fastapi import APIRouter, HTTPException, Request
from rdkit import Chem, rdBase
from rdkit.Chem import Descriptors, rdMolDescriptors
from rdkit.Chem.Scaffolds import MurckoScaffold
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit

from .api import records, save_record
from .auth import require_editor
from .db import data_dir, new_id
from .schemas import TrainInput

router = APIRouter(prefix="/api/workspace/model", tags=["model-evaluation"])
training_lock = threading.Lock()
FEATURES = [
    "MolWt",
    "MolLogP",
    "HBD",
    "HBA",
    "TPSA",
    "Rings",
    "RotatableBonds",
    "HeavyAtoms",
    "FractionCSP3",
]
LAB_FEATURES = [
    "initial_h2o2",
    "ph",
    "temperature_c",
    "duration_days",
    "fragrance_pct",
    "solubilizer_pct",
    "stabilizer_pct",
]


def solubility_path() -> Path:
    return Path(
        os.getenv(
            "BAYLAB_SOLUBILITY_FILE",
            str(Path(__file__).resolve().parents[3] / "data" / "aqueous solubility dataset.csv"),
        )
    )


@lru_cache(maxsize=3)
def solubility_data(path: str, modified: int) -> dict:
    file = Path(path)
    rows, excluded = [], 0
    with file.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"smiles", "measured log solubility in mols per litre"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError(
                "CSV tidak memiliki kolom SMILES dan kelarutan terukur yang diperlukan."
            )
        for index, row in enumerate(reader):
            if index >= 10000:
                raise ValueError("Batas dataset lokal 10.000 baris.")
            try:
                smiles = row["smiles"].strip()
                if len(smiles) > 2000:
                    raise ValueError("SMILES too long")
                with rdBase.BlockLogs():
                    mol = Chem.MolFromSmiles(smiles)
                if mol is None or mol.GetNumAtoms() > 200 or len(Chem.GetMolFrags(mol)) != 1:
                    raise ValueError("Unsupported molecule")
                canonical = Chem.MolToSmiles(mol)
                y = float(row["measured log solubility in mols per litre"])
                x = [
                    Descriptors.MolWt(mol),
                    Descriptors.MolLogP(mol),
                    rdMolDescriptors.CalcNumHBD(mol),
                    rdMolDescriptors.CalcNumHBA(mol),
                    rdMolDescriptors.CalcTPSA(mol),
                    rdMolDescriptors.CalcNumRings(mol),
                    rdMolDescriptors.CalcNumRotatableBonds(mol),
                    mol.GetNumHeavyAtoms(),
                    rdMolDescriptors.CalcFractionCSP3(mol),
                ]
                if not all(math.isfinite(v) for v in [y, *x]):
                    raise ValueError("Non-finite measurement")
                scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=mol)
                rows.append(
                    {
                        "x": x,
                        "y": y,
                        "group": scaffold or canonical,
                        "label": row.get("Compound ID", str(index)),
                        "identity": canonical,
                    }
                )
            except (ValueError, TypeError, KeyError):
                excluded += 1
    return {
        "rows": rows,
        "excluded": excluded,
        "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
        "filename": file.name,
    }


def dataset(org: str, target: str, protocol: str = "") -> dict:
    if target == "solubility":
        path = solubility_path()
        if not path.is_file():
            raise ValueError("Dataset kelarutan lokal belum tersedia.")
        data = solubility_data(str(path), path.stat().st_mtime_ns)
        return {
            **data,
            "features": FEATURES,
            "unit": "log10(mol/L)",
            "origin": "external_measured_column",
            "grouping": "Bemis-Murcko scaffold; acyclic: canonical SMILES",
            "scope": "Kelarutan senyawa dalam air; bukan stabilitas atau kelarutan formula H2O2.",
            "provenance": "CSV pengguna, kolom terukur; belum diaudit terhadap data asli.",
        }
    all_rows = records(org, "experiment")
    rows = []
    for row in all_rows:
        if (
            row["data_origin"] != "real"
            or not row["confirmed_actual"]
            or row["protocol"] != protocol
        ):
            continue
        fractions = row["composition_features"]
        x = [row[k] for k in LAB_FEATURES[:4]] + [
            fractions[k] for k in ["fragrance", "solubilizer", "stabilizer"]
        ]
        rows.append(
            {
                "x": x,
                "y": row["retention_pct"],
                "group": row["composition_hash"],
                "label": row["batch_id"],
                "identity": row["id"],
            }
        )
    return {
        "rows": rows,
        "excluded": len(all_rows) - len(rows),
        "sha256": hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest(),
        "filename": "organization laboratory observations",
        "features": LAB_FEATURES,
        "unit": "% retensi H2O2",
        "origin": "user_attested_lab",
        "grouping": "composition fingerprint",
        "scope": "Evaluasi retensi H2O2 pada protokol terpilih; bukan prediksi efikasi mikroba.",
        "provenance": "Pengukuran berlabel nyata dari pengguna; belum verifikasi independen.",
    }


def readiness(data: dict) -> dict:
    rows = data["rows"]
    groups = len({r["group"] for r in rows})
    enough = len(rows) >= 12 and groups >= 4 and len({r["y"] for r in rows}) >= 2
    return {
        "eligible_rows": len(rows),
        "groups": groups,
        "excluded_rows": data["excluded"],
        "can_train": enough,
        "minimum_rows": 12,
        "minimum_groups": 4,
        "message": "Siap evaluasi teknis; belum model tervalidasi."
        if enough
        else "Butuh minimal 12 pengukuran, 4 kelompok independen, dan variasi nilai target.",
        "scope": data["scope"],
        "unit": data["unit"],
    }


def train(data: dict, algorithm: str, directory: Path) -> dict:
    if not readiness(data)["can_train"]:
        raise ValueError(readiness(data)["message"])
    from importlib.metadata import version

    rows = data["rows"]
    x = np.asarray([r["x"] for r in rows], dtype=float)
    y = np.asarray([r["y"] for r in rows], dtype=float)
    groups = np.asarray([r["group"] for r in rows])
    train_ids, test_ids = next(
        GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42).split(x, y, groups)
    )
    if len(test_ids) < 2 or len(train_ids) < 6 or len(set(y[train_ids])) < 2:
        raise ValueError(
            "Pembagian kelompok menghasilkan data latih/uji terlalu kecil atau target konstan."
        )
    if algorithm == "catboost":
        from catboost import CatBoostRegressor

        model = CatBoostRegressor(
            iterations=160,
            depth=4,
            learning_rate=0.05,
            loss_function="RMSE",
            random_seed=42,
            thread_count=2,
            verbose=False,
            allow_writing_files=False,
        )
    else:
        from xgboost import XGBRegressor

        model = XGBRegressor(
            n_estimators=160,
            max_depth=4,
            learning_rate=0.05,
            objective="reg:squarederror",
            random_state=42,
            n_jobs=2,
            tree_method="hist",
        )
    model.fit(x[train_ids], y[train_ids])
    predictions = model.predict(x[test_ids])
    baseline = np.full(len(test_ids), y[train_ids].mean())
    if not np.isfinite(predictions).all():
        raise ValueError("Model menghasilkan nilai non-finite.")
    directory.mkdir(parents=True, exist_ok=True)
    artifact = directory / ("model.cbm" if algorithm == "catboost" else "model.json")
    model.save_model(str(artifact))
    score = float(r2_score(y[test_ids], predictions)) if np.ptp(y[test_ids]) > 0 else None
    train_groups, test_groups = set(groups[train_ids]), set(groups[test_ids])
    assert not train_groups.intersection(test_groups)
    return {
        "algorithm": algorithm,
        "library_version": version(algorithm),
        "status": "evaluation_only",
        "unit": data["unit"],
        "scope": data["scope"],
        "origin": data["origin"],
        "provenance": data["provenance"],
        "dataset_sha256": data["sha256"],
        "features": data["features"],
        "grouping": data["grouping"],
        "rows": len(rows),
        "excluded": data["excluded"],
        "train_rows": len(train_ids),
        "test_rows": len(test_ids),
        "train_groups": len(train_groups),
        "test_groups": len(test_groups),
        "group_overlap": 0,
        "metrics": {
            "mae": float(mean_absolute_error(y[test_ids], predictions)),
            "rmse": float(math.sqrt(mean_squared_error(y[test_ids], predictions))),
            "r2": score,
            "baseline_mae": float(mean_absolute_error(y[test_ids], baseline)),
        },
        "points": [
            {"label": rows[int(i)]["label"], "actual": float(y[i]), "predicted": float(p)}
            for i, p in zip(test_ids, predictions, strict=True)
        ],
        "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "seed": 42,
        "warning": "Grouped holdout; belum validasi eksternal; dilatih pada subset latih.",
    }


@router.get("/status")
def status(request: Request, target: str = "solubility", protocol: str = "") -> dict:
    if target not in {"solubility", "h2o2_retention"}:
        raise HTTPException(422, "Target tidak dikenal.")
    try:
        return readiness(dataset(request.state.user["org_id"], target, protocol))
    except ValueError as exc:
        return {"can_train": False, "eligible_rows": 0, "groups": 0, "message": str(exc)}


@router.get("/runs")
def runs(request: Request) -> list[dict]:
    return records(request.state.user["org_id"], "model_run")


@router.post("/train", status_code=201)
def train_model(payload: TrainInput, request: Request) -> dict:
    actor = require_editor(request)
    if not training_lock.acquire(blocking=False):
        raise HTTPException(409, "Pelatihan lain masih berjalan. Tunggu hingga selesai.")
    started = time.monotonic()
    try:
        data = dataset(actor["org_id"], payload.target, payload.protocol)
        run_id = new_id()
        result = train(data, payload.algorithm, data_dir() / "models" / actor["org_id"] / run_id)
        result.update(
            {
                "target": payload.target,
                "protocol": payload.protocol,
                "artifact_key": run_id,
                "duration_seconds": round(time.monotonic() - started, 2),
            }
        )
        return save_record(actor, "model_run", result)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        training_lock.release()
