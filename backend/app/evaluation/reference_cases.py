"""Score BAYLab components against reference cases written by the designated chemist.

The reference answers come only from the chemist's file; nothing here invents them.
Two components are checked:

* functional-group detection (RDKit + draft SMARTS) against the groups the chemist names;
* the oxidant-stability model against the chemist's stable/unstable judgement, with every
  reference structure removed from the training data first to avoid leakage.

Pass criteria are read from a separate file whose hash is written into the report, so a
reviewer can confirm the thresholds were fixed before the run.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from rdkit import Chem, DataStructs, rdBase
from rdkit.Chem import rdFingerprintGenerator
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import balanced_accuracy_score, roc_auc_score

from app.chemistry.engine import screen
from app.datasets.baylab_final import descriptor_vector

# Chemist-facing group names mapped to the draft rule ids of the screening engine.
GROUP_TO_RULE = {
    "alkena": "DRAFT-ALKENE",
    "aldehida": "DRAFT-ALDEHYDE",
    "alkohol": "DRAFT-ALCOHOL",
    "fenol": "DRAFT-PHENOL",
    "ester": "DRAFT-ESTER",
    "peroksida": "DRAFT-PEROXIDE",
}
RULE_TO_GROUP = {rule: group for group, rule in GROUP_TO_RULE.items()}
NONE_WORDS = {"tidak_ada", "tidak ada", "-", "none"}
TEMPLATE_FIELDS = [
    "case_id",
    "nama",
    "cas",
    "smiles",
    "gugus_menurut_kimiawan",
    "stabil_menurut_kimiawan",
    "alasan_kimiawan",
    "sumber",
    "divalidasi_oleh",
    "tanggal_validasi",
    "catatan",
]
EXAMPLE_PREFIX = "CONTOH"


@dataclass(frozen=True)
class Criteria:
    """Thresholds fixed by the team before the run."""

    min_kasus_tervalidasi: int = 20
    min_kesesuaian_gugus: float = 0.90
    min_kasus_berlabel_stabilitas: int = 10
    min_akurasi_seimbang_stabilitas: float = 0.70
    ambang_probabilitas_stabil: float = 0.5


@dataclass(frozen=True)
class ReferenceCase:
    case_id: str
    nama: str
    smiles: str
    groups: frozenset[str]
    stable: int | None
    validated_by: str


@dataclass
class Skipped:
    case_id: str
    reason: str


@dataclass
class CaseResult:
    case_id: str
    nama: str
    gugus_kimiawan: list[str]
    gugus_sistem: list[str]
    gugus_sesuai: bool
    stabil_kimiawan: int | None = None
    prob_stabil_model: float | None = None
    stabil_model: int | None = None
    kemiripan_maks_data_latih: float | None = None
    catatan: list[str] = field(default_factory=list)


def write_template(path: Path) -> None:
    """Empty template with one example row that the runner always ignores."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=TEMPLATE_FIELDS)
        writer.writeheader()
        writer.writerow(
            {
                "case_id": f"{EXAMPLE_PREFIX}-1",
                "nama": "Linalool",
                "cas": "78-70-6",
                "smiles": "CC(C)=CCCC(C)(O)C=C",
                "gugus_menurut_kimiawan": "alkena;alkohol",
                "stabil_menurut_kimiawan": "",
                "alasan_kimiawan": "",
                "sumber": "",
                "divalidasi_oleh": "",
                "tanggal_validasi": "",
                "catatan": "Contoh cara mengisi. Baris berawalan CONTOH selalu diabaikan.",
            }
        )


def write_default_criteria(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(Criteria()), indent=1), encoding="utf-8")


def load_criteria(path: Path) -> Criteria:
    data = json.loads(path.read_text(encoding="utf-8"))
    unknown = set(data) - set(Criteria.__dataclass_fields__)
    if unknown:
        raise ValueError(f"Kunci kriteria tidak dikenal: {sorted(unknown)}")
    return Criteria(**data)


def _parse_groups(text: str) -> frozenset[str]:
    cleaned = text.strip().lower()
    if cleaned in NONE_WORDS:
        return frozenset()
    groups = frozenset(
        part.strip() for part in cleaned.replace(",", ";").split(";") if part.strip()
    )
    unknown = groups - set(GROUP_TO_RULE)
    if unknown:
        raise ValueError(f"gugus tidak dikenal: {sorted(unknown)}")
    return groups


def load_cases(path: Path) -> tuple[list[ReferenceCase], list[Skipped]]:
    """Read the chemist's file. Only rows with a named validator count."""
    cases: list[ReferenceCase] = []
    skipped: list[Skipped] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = set(TEMPLATE_FIELDS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Kolom kasus acuan hilang: {sorted(missing)}")
        for raw in reader:
            row = {k: (v or "").strip() for k, v in raw.items()}
            case_id = row["case_id"]
            if not case_id or case_id.upper().startswith(EXAMPLE_PREFIX):
                continue
            if case_id in seen:
                skipped.append(Skipped(case_id, "case_id ganda"))
                continue
            seen.add(case_id)
            if not row["divalidasi_oleh"]:
                skipped.append(Skipped(case_id, "belum divalidasi kimiawan"))
                continue
            if not row["smiles"]:
                skipped.append(Skipped(case_id, "SMILES kosong"))
                continue
            if not row["gugus_menurut_kimiawan"]:
                skipped.append(Skipped(case_id, "gugus_menurut_kimiawan kosong"))
                continue
            try:
                groups = _parse_groups(row["gugus_menurut_kimiawan"])
            except ValueError as exc:
                skipped.append(Skipped(case_id, str(exc)))
                continue
            stable_text = row["stabil_menurut_kimiawan"]
            if stable_text not in {"", "0", "1"}:
                skipped.append(Skipped(case_id, "stabil_menurut_kimiawan harus 0, 1, atau kosong"))
                continue
            cases.append(
                ReferenceCase(
                    case_id=case_id,
                    nama=row["nama"],
                    smiles=row["smiles"],
                    groups=groups,
                    stable=int(stable_text) if stable_text else None,
                    validated_by=row["divalidasi_oleh"],
                )
            )
    return cases, skipped


def detect_groups(smiles: str) -> frozenset[str]:
    """Groups found by the production screening engine (raises on invalid SMILES)."""
    result = screen(smiles)
    return frozenset(RULE_TO_GROUP[m.rule.id] for m in result.matches if m.rule.id in RULE_TO_GROUP)


def _canonical(smiles: str) -> str | None:
    with rdBase.BlockLogs():
        mol = Chem.MolFromSmiles(smiles)
    return Chem.MolToSmiles(mol) if mol is not None else None


_MORGAN = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)


def _fingerprint(smiles: str):
    with rdBase.BlockLogs():
        mol = Chem.MolFromSmiles(smiles)
    return _MORGAN.GetFingerprint(mol)


@dataclass
class StabilityModel:
    model: RandomForestClassifier
    training_smiles: list[str]
    excluded_for_leakage: int


def train_stability_model(training_csv: Path, exclude_smiles: list[str]) -> StabilityModel:
    """Random forest on the trusted rows of the prepared oxidant table, minus reference cases."""
    excluded = {c for c in (_canonical(s) for s in exclude_smiles) if c}
    features, labels, kept = [], [], []
    removed = 0
    with training_csv.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row.get("boleh_evaluasi") != "ya" or row.get("label_stabil_oksidan") not in {
                "0",
                "1",
            }:
                continue
            canonical = row.get("smiles_kanonik") or ""
            if not canonical:
                continue
            if canonical in excluded:
                removed += 1
                continue
            with rdBase.BlockLogs():
                mol = Chem.MolFromSmiles(canonical)
            if mol is None:
                continue
            features.append(descriptor_vector(mol))
            labels.append(int(row["label_stabil_oksidan"]))
            kept.append(canonical)
    if len(set(labels)) < 2:
        raise ValueError("Data latih stabilitas harus memuat label 0 dan 1.")
    model = RandomForestClassifier(
        n_estimators=400, min_samples_leaf=2, class_weight="balanced", random_state=42
    )
    model.fit(np.asarray(features, dtype=float), np.asarray(labels))
    return StabilityModel(model, kept, removed)


def _max_similarity(smiles: str, training: list) -> float:
    return max(DataStructs.BulkTanimotoSimilarity(_fingerprint(smiles), training), default=0.0)


def evaluate(
    cases: list[ReferenceCase], criteria: Criteria, stability: StabilityModel | None
) -> dict[str, Any]:
    results: list[CaseResult] = []
    group_hits: dict[str, dict[str, int]] = {g: {"tp": 0, "fp": 0, "fn": 0} for g in GROUP_TO_RULE}
    training_fps = (
        [_fingerprint(s) for s in stability.training_smiles] if stability is not None else []
    )
    y_true, y_prob = [], []
    for case in cases:
        try:
            found = detect_groups(case.smiles)
        except ValueError as exc:
            results.append(
                CaseResult(
                    case.case_id,
                    case.nama,
                    sorted(case.groups),
                    [],
                    False,
                    catatan=[f"SMILES ditolak sistem: {exc}"],
                )
            )
            continue
        for group in GROUP_TO_RULE:
            if group in found and group in case.groups:
                group_hits[group]["tp"] += 1
            elif group in found:
                group_hits[group]["fp"] += 1
            elif group in case.groups:
                group_hits[group]["fn"] += 1
        result = CaseResult(
            case.case_id, case.nama, sorted(case.groups), sorted(found), found == case.groups
        )
        if case.stable is not None and stability is not None:
            with rdBase.BlockLogs():
                mol = Chem.MolFromSmiles(case.smiles)
            prob = float(stability.model.predict_proba([descriptor_vector(mol)])[0][1])
            result.stabil_kimiawan = case.stable
            result.prob_stabil_model = round(prob, 3)
            result.stabil_model = int(prob >= criteria.ambang_probabilitas_stabil)
            result.kemiripan_maks_data_latih = round(_max_similarity(case.smiles, training_fps), 3)
            if result.kemiripan_maks_data_latih < 0.3:
                result.catatan.append("di luar pengalaman model (kemiripan < 0,3)")
            y_true.append(case.stable)
            y_prob.append(prob)
        results.append(result)

    group_agreement = sum(r.gugus_sesuai for r in results) / len(results) if results else 0.0
    per_group = {}
    for group, counts in group_hits.items():
        tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
        per_group[group] = {
            **counts,
            "presisi": round(tp / (tp + fp), 3) if tp + fp else None,
            "recall": round(tp / (tp + fn), 3) if tp + fn else None,
        }
    stability_metrics: dict[str, Any] = {"kasus_berlabel": len(y_true)}
    if y_true:
        y_pred = [int(p >= criteria.ambang_probabilitas_stabil) for p in y_prob]
        stability_metrics["akurasi"] = round(
            sum(int(a == b) for a, b in zip(y_true, y_pred, strict=True)) / len(y_true), 3
        )
        stability_metrics["akurasi_seimbang"] = (
            round(float(balanced_accuracy_score(y_true, y_pred)), 3)
            if len(set(y_true)) == 2
            else None
        )
        stability_metrics["roc_auc"] = (
            round(float(roc_auc_score(y_true, y_prob)), 3) if len(set(y_true)) == 2 else None
        )
    checks = _checks(len(cases), group_agreement, stability_metrics, criteria)
    return {
        "hasil_per_kasus": [asdict(r) for r in results],
        "deteksi_gugus": {
            "kesesuaian_himpunan_gugus": round(group_agreement, 3),
            "per_gugus": per_group,
        },
        "prediksi_stabilitas": stability_metrics,
        "pemeriksaan_kriteria": checks,
        "lulus_semua_kriteria": all(c["lulus"] for c in checks),
    }


def _checks(
    n_cases: int, group_agreement: float, stability: dict[str, Any], criteria: Criteria
) -> list[dict[str, Any]]:
    balanced = stability.get("akurasi_seimbang")
    rows = [
        ("Jumlah kasus tervalidasi", n_cases, criteria.min_kasus_tervalidasi),
        ("Kesesuaian deteksi gugus", round(group_agreement, 3), criteria.min_kesesuaian_gugus),
        (
            "Jumlah kasus berlabel stabilitas",
            stability["kasus_berlabel"],
            criteria.min_kasus_berlabel_stabilitas,
        ),
        (
            "Akurasi seimbang prediksi stabilitas",
            balanced,
            criteria.min_akurasi_seimbang_stabilitas,
        ),
    ]
    return [
        {
            "kriteria": name,
            "nilai": value,
            "ambang_minimum": threshold,
            "lulus": value is not None
            and not (isinstance(value, float) and math.isnan(value))
            and value >= threshold,
        }
        for name, value, threshold in rows
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(cases_path: Path, criteria_path: Path, training_csv: Path, out_dir: Path) -> dict[str, Any]:
    cases, skipped = load_cases(cases_path)
    criteria = load_criteria(criteria_path)
    labelled = [c.smiles for c in cases if c.stable is not None]
    stability = train_stability_model(training_csv, [c.smiles for c in cases]) if labelled else None
    report = {
        "dijalankan_pada": datetime.now(UTC).isoformat(timespec="seconds"),
        "sha256_kasus_acuan": _sha256(cases_path),
        "sha256_kriteria": _sha256(criteria_path),
        "sha256_data_latih": _sha256(training_csv),
        "kriteria": asdict(criteria),
        "kasus_dipakai": len(cases),
        "kasus_dilewati": [asdict(s) for s in skipped],
        "data_latih_stabilitas": (
            {
                "baris": len(stability.training_smiles),
                "dikeluarkan_karena_sama_dengan_kasus_acuan": stability.excluded_for_leakage,
            }
            if stability
            else None
        ),
        **evaluate(cases, criteria, stability),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = report["dijalankan_pada"].replace(":", "").replace("-", "")[:15]
    (out_dir / f"laporan_validasi_{stamp}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (out_dir / f"laporan_validasi_{stamp}.md").write_text(to_markdown(report), encoding="utf-8")
    return report


def to_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Laporan validasi komponen BAYLab AI terhadap kasus acuan kimiawan",
        "",
        f"Dijalankan: {report['dijalankan_pada']}. Kasus dipakai: {report['kasus_dipakai']}, "
        f"dilewati: {len(report['kasus_dilewati'])}.",
        "",
        "Hash file (untuk membuktikan kriteria tidak diubah setelah uji):",
        f"- kasus acuan: `{report['sha256_kasus_acuan']}`",
        f"- kriteria: `{report['sha256_kriteria']}`",
        f"- data latih: `{report['sha256_data_latih']}`",
        "",
        "## Kriteria lulus",
        "",
        "| Kriteria | Nilai | Minimum | Lulus |",
        "| --- | --- | --- | --- |",
    ]
    for check in report["pemeriksaan_kriteria"]:
        value = "belum dapat dihitung" if check["nilai"] is None else check["nilai"]
        lines.append(
            f"| {check['kriteria']} | {value} | {check['ambang_minimum']} | "
            f"{'ya' if check['lulus'] else 'tidak'} |"
        )
    verdict = (
        "Semua kriteria yang ditetapkan tim terpenuhi."
        if report["lulus_semua_kriteria"]
        else "Belum semua kriteria terpenuhi."
    )
    lines += [
        "",
        verdict + " Hasil ini adalah validasi komponen perangkat lunak terhadap penilaian "
        "kimiawan, bukan bukti stabilitas formula atau efikasi antimikroba.",
        "",
        "## Hasil per kasus",
        "",
        "| Kasus | Nama | Gugus kimiawan | Gugus sistem | Sesuai | Stabil (kimiawan) | "
        "Prob. stabil model | Kemiripan data latih |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in report["hasil_per_kasus"]:
        lines.append(
            f"| {r['case_id']} | {r['nama']} | {', '.join(r['gugus_kimiawan']) or '-'} | "
            f"{', '.join(r['gugus_sistem']) or '-'} | {'ya' if r['gugus_sesuai'] else 'tidak'} | "
            f"{'' if r['stabil_kimiawan'] is None else r['stabil_kimiawan']} | "
            f"{'' if r['prob_stabil_model'] is None else r['prob_stabil_model']} | "
            f"{'' if r['kemiripan_maks_data_latih'] is None else r['kemiripan_maks_data_latih']} |"
        )
    if report["kasus_dilewati"]:
        lines += ["", "## Kasus dilewati", ""]
        lines += [f"- {s['case_id']}: {s['reason']}" for s in report["kasus_dilewati"]]
    return "\n".join(lines) + "\n"
