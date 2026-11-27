"""Interim benchmark on data already in hand, before the chemist's reference cases exist.

It answers "how far along is the model" by comparing, on the same scaffold-grouped folds:
a majority guess, the draft group rules alone, logistic regression and a random forest.
Labels are proxies (perborate and bleach media), so the result is a benchmark of the
pipeline, not evidence that any formula is stable.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import numpy as np
from rdkit import Chem, rdBase
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.datasets.baylab_final import descriptor_vector

from .reference_cases import detect_groups

RISKY_GROUPS = frozenset({"alkena", "aldehida", "fenol"})
TARGET_AUC = 0.80


def load_trusted(training_csv: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    features, labels, groups, smiles = [], [], [], []
    with training_csv.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row.get("boleh_evaluasi") != "ya":
                continue
            with rdBase.BlockLogs():
                mol = Chem.MolFromSmiles(row["smiles_kanonik"])
            if mol is None:
                continue
            features.append(descriptor_vector(mol))
            labels.append(int(row["label_stabil_oksidan"]))
            groups.append(row.get("grup_split") or row["smiles_kanonik"])
            smiles.append(row["smiles_kanonik"])
    return np.asarray(features, float), np.asarray(labels), np.asarray(groups), smiles


def rule_scores(smiles: list[str]) -> np.ndarray:
    """1 = predicted stable when the draft rules find no C=C, aldehyde or phenol."""
    return np.asarray([0.0 if detect_groups(s) & RISKY_GROUPS else 1.0 for s in smiles])


def _summary(values: list[float]) -> dict[str, float]:
    return {"rerata": round(float(np.mean(values)), 3), "sd": round(float(np.std(values)), 3)}


def benchmark_stability(training_csv: Path, seeds: int = 5, folds: int = 5) -> dict[str, Any]:
    x, y, groups, smiles = load_trusted(training_csv)
    if len(set(y)) < 2:
        raise ValueError("Data benchmark harus memuat label 0 dan 1.")
    rules = rule_scores(smiles)
    models = {
        "logistic_regression": lambda: make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced")
        ),
        "random_forest": lambda: RandomForestClassifier(
            n_estimators=400, min_samples_leaf=2, class_weight="balanced", random_state=42
        ),
    }
    scores: dict[str, dict[str, list[float]]] = {
        name: {"roc_auc": [], "akurasi_seimbang": [], "brier": []}
        for name in ["mayoritas", "aturan_gugus_saja", *models]
    }
    for seed in range(seeds):
        oof = {name: np.zeros(len(y)) for name in scores}
        for train, test in StratifiedGroupKFold(folds, shuffle=True, random_state=seed).split(
            x, y, groups
        ):
            oof["mayoritas"][test] = y[train].mean()
            oof["aturan_gugus_saja"][test] = rules[test]
            for name, make in models.items():
                oof[name][test] = make().fit(x[train], y[train]).predict_proba(x[test])[:, 1]
        for name, prob in oof.items():
            scores[name]["roc_auc"].append(roc_auc_score(y, prob))
            scores[name]["akurasi_seimbang"].append(balanced_accuracy_score(y, prob >= 0.5))
            scores[name]["brier"].append(brier_score_loss(y, prob))
    results = {
        name: {metric: _summary(values) for metric, values in metrics.items()}
        for name, metrics in scores.items()
    }
    best_auc = results["random_forest"]["roc_auc"]["rerata"]
    return {
        "data": {
            "baris": int(len(y)),
            "label_1_stabil": int(y.sum()),
            "label_0_tidak": int(len(y) - y.sum()),
            "grup_scaffold": int(len(set(groups))),
        },
        "skema_uji": f"StratifiedGroupKFold {folds} fold per scaffold, diulang {seeds} seed",
        "hasil": results,
        "target_roc_auc": TARGET_AUC,
        "posisi_menuju_target": round((best_auc - 0.5) / (TARGET_AUC - 0.5), 3),
    }


def benchmark_detection(master_csv: Path) -> dict[str, Any]:
    """Agreement between the screening engine and the group counts in the master table."""
    columns = {
        "alkena": "R01_alkena_CC",
        "aldehida": "R02_aldehida",
        "fenol": "R03_fenol",
        "peroksida": "R08_peroksida",
    }
    agree = {group: 0 for group in columns}
    disagreements: list[dict[str, str]] = []
    total = 0
    with master_csv.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if not row.get("smiles") or not row.get(columns["alkena"]):
                continue
            try:
                found = detect_groups(row["smiles"])
            except ValueError:
                continue
            total += 1
            for group, column in columns.items():
                expected = float(row[column]) > 0
                if expected == (group in found):
                    agree[group] += 1
                else:
                    disagreements.append(
                        {
                            "bahan": row["nama"],
                            "gugus": group,
                            "tabel_master": "ada" if expected else "tidak",
                            "sistem": "ada" if group in found else "tidak",
                        }
                    )
    return {
        "bahan_diperiksa": total,
        "kesesuaian_per_gugus": {
            g: round(n / total, 3) if total else None for g, n in agree.items()
        },
        "perbedaan": disagreements,
        "catatan": "Kedua sumber dihitung dengan RDKit tetapi pola SMARTS berbeda; ini uji "
        "konsistensi antarimplementasi, bukan validasi oleh kimiawan.",
    }
