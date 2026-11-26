"""Quality control and training-ready export for the BAYLab_dataset_final folder.

The raw files are never modified. Every rule here is a data-consistency check
(missing structure, duplicate structure, label that contradicts its own recorded
basis, unit harmonisation). No rule changes a chemical label: rows that look
wrong are excluded and flagged for review by the designated chemist.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rdkit import Chem, rdBase
from rdkit.Chem import Descriptors, rdMolDescriptors
from rdkit.Chem.Scaffolds import MurckoScaffold

INGREDIENT_FILE = "3_data_training/10_bahan_stabilitas_oksidan_berlabel.csv"
PATENT_FILE = "3_data_training/06_formulasi_paten_berlabel.csv"
SYNTHETIC_FILE = "3_data_training/07_formulasi_sintetis_ilustratif.csv"
LAB_TEMPLATE_FILE = "4_lab_LKPI/09_template_data_lab_LKPI.csv"
LAB_RUN_FILES = ("4_lab_LKPI/11_doe_A_skrining_bahan.csv", "4_lab_LKPI/12_doe_B_formulasi.csv")

CONFIDENCE_RANK = {"kuat": 3, "sedang": 2, "lemah": 1}
TRUSTED_CONFIDENCE = {"kuat", "sedang"}
# Same descriptor set and order as app.workspace.ml.FEATURES.
DESCRIPTOR_NAMES = [
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
RATING = re.compile(r"\b(good|fair|moderate|poor|unstable)\b", re.IGNORECASE)
PATENT_ID = re.compile(r"US\s?(\d[\d,]*)")
LAB_RESULT_RANGES: dict[str, tuple[float, float]] = {
    "retensi_h2o2_pct": (0.0, 110.0),
    "h2o2_akhir_pct": (0.0, 60.0),
    "ph_akhir": (0.0, 14.0),
    "skor_aroma_panel_0_5": (0.0, 5.0),
    "skor_intensitas_aroma_0_5": (0.0, 5.0),
}

Row = dict[str, str]


@dataclass
class TableResult:
    """One prepared table plus the counts that explain it."""

    fieldnames: list[str]
    rows: list[Row]
    summary: dict[str, Any] = field(default_factory=dict)


def read_csv(path: Path) -> tuple[list[str], list[Row]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = [{k: (v or "").strip() for k, v in row.items()} for row in reader]
        return list(reader.fieldnames or []), rows


def write_csv(path: Path, fieldnames: list[str], rows: list[Row]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig keeps Excel on Windows from corrupting subscripts and decimals.
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def name_needs_check(name: str) -> bool:
    """Detect names that were cut at a comma during scraping, e.g. '2' or '(E'."""
    if not name or name.count("(") != name.count(")"):
        return True
    return bool(re.fullmatch(r"[\d\s]+", name) or re.search(r"[-\s]\d+$", name))


def label_contradicts_basis(basis: str, label: str) -> bool:
    """True when every rating written in the basis points the other way."""
    ratings = {m.lower() for m in RATING.findall(basis)}
    if not ratings:
        return False
    if label == "1":
        return ratings <= {"poor", "unstable"}
    if label == "0":
        return ratings <= {"good"}
    return False


def descriptor_vector(mol: Chem.Mol) -> list[float]:
    return [
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


def prepare_ingredients(fieldnames: list[str], raw: list[Row]) -> TableResult:
    """File 10: ingredient-level oxidant stability (binary, proxy label)."""
    rows: list[Row] = []
    flags: list[list[str]] = []
    canon_of: list[str] = []
    for source in raw:
        row = dict(source)
        notes: list[str] = []
        canonical = ""
        smiles = row.get("smiles", "")
        if row.get("label_stabil_oksidan") not in {"0", "1"}:
            notes.append("label_tidak_valid")
        if row.get("keyakinan_label") not in CONFIDENCE_RANK:
            notes.append("keyakinan_tidak_valid")
        if not smiles:
            notes.append("smiles_kosong")
        else:
            with rdBase.BlockLogs():
                mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                notes.append("smiles_tidak_valid")
            elif len(Chem.GetMolFrags(mol)) != 1:
                notes.append("campuran_multi_fragmen_perlu_struktur_representatif")
            else:
                canonical = Chem.MolToSmiles(mol)
                vector = descriptor_vector(mol)
                if not all(math.isfinite(v) for v in vector):
                    notes.append("deskriptor_tidak_finite")
                    canonical = ""
                else:
                    row.update(
                        {n: f"{v:.6g}" for n, v in zip(DESCRIPTOR_NAMES, vector, strict=True)}
                    )
                    scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=mol)
                    row["grup_split"] = scaffold or canonical
        if label_contradicts_basis(row.get("dasar_label", ""), row.get("label_stabil_oksidan", "")):
            notes.append("label_bertentangan_dengan_dasar_label_perlu_review_kimiawan")
        row["smiles_kanonik"] = canonical
        rows.append(row)
        flags.append(notes)
        canon_of.append(canonical if not notes else "")

    # Duplicate structures leak between train and test; keep one row per structure.
    by_structure: dict[str, list[int]] = defaultdict(list)
    for index, canonical in enumerate(canon_of):
        if canonical:
            by_structure[canonical].append(index)
    for members in by_structure.values():
        if len(members) == 1:
            continue
        best = max(CONFIDENCE_RANK[rows[i]["keyakinan_label"]] for i in members)
        top = [i for i in members if CONFIDENCE_RANK[rows[i]["keyakinan_label"]] == best]
        if len({rows[i]["label_stabil_oksidan"] for i in top}) > 1:
            for i in members:
                flags[i].append("duplikat_struktur_label_bertentangan")
            continue
        keep = top[0]
        for i in members:
            if i != keep:
                same = rows[i]["label_stabil_oksidan"] == rows[keep]["label_stabil_oksidan"]
                flags[i].append(
                    "duplikat_struktur" if same else "duplikat_struktur_label_lebih_lemah_berbeda"
                )
                rows[i]["duplikat_dari_cas"] = rows[keep]["cas"]

    counts: dict[str, int] = defaultdict(int)
    for row, notes in zip(rows, flags, strict=True):
        trainable = not notes
        name_flag = name_needs_check(row.get("nama", ""))
        row["nama_perlu_cek"] = "ya" if name_flag else "tidak"
        row["boleh_latih"] = "ya" if trainable else "tidak"
        row["boleh_evaluasi"] = (
            "ya" if trainable and row["keyakinan_label"] in TRUSTED_CONFIDENCE else "tidak"
        )
        row["catatan_qc"] = ";".join(notes)
        for note in notes:
            counts[note] += 1
        counts["nama_perlu_cek"] += name_flag
        row.setdefault("duplikat_dari_cas", "")
        row.setdefault("grup_split", "")
        for name in DESCRIPTOR_NAMES:
            row.setdefault(name, "")

    train = [r for r in rows if r["boleh_latih"] == "ya"]
    evaluation = [r for r in train if r["boleh_evaluasi"] == "ya"]

    def labels(subset: list[Row]) -> dict[str, int]:
        result = {"0": 0, "1": 0}
        for r in subset:
            result[r["label_stabil_oksidan"]] += 1
        return result

    weak = [r for r in train if r["keyakinan_label"] == "lemah"]
    out_fields = [
        *fieldnames,
        "smiles_kanonik",
        "grup_split",
        *DESCRIPTOR_NAMES,
        "boleh_latih",
        "boleh_evaluasi",
        "nama_perlu_cek",
        "duplikat_dari_cas",
        "catatan_qc",
    ]
    return TableResult(
        out_fields,
        rows,
        {
            "baris_mentah": len(raw),
            "baris_boleh_latih": len(train),
            "baris_boleh_evaluasi_kuat_sedang": len(evaluation),
            "label_boleh_latih": labels(train),
            "label_boleh_evaluasi": labels(evaluation),
            "label_lemah_boleh_latih": labels(weak),
            "grup_scaffold_boleh_evaluasi": len({r["grup_split"] for r in evaluation}),
            "alasan_eksklusi": dict(sorted(counts.items())),
        },
    )


def prepare_patents(fieldnames: list[str], raw: list[Row]) -> TableResult:
    """File 06: formulation-level stability extracted from four patents."""
    rows: list[Row] = []
    for source in raw:
        row = dict(source)
        notes: list[str] = []
        match = PATENT_ID.search(row.get("sumber", ""))
        row["grup_split"] = "US" + match.group(1).replace(",", "") if match else row["sumber"]
        hours = row.get("durasi_jam", "")
        row["durasi_hari"] = f"{float(hours) / 24:.4g}" if hours else ""
        if not row.get("dipakai_training", "").startswith("ya"):
            notes.append("ditandai_tidak_dipakai_training_di_sumber")
        if row.get("label_stabil") not in {"0", "1", "0.0", "1.0"}:
            notes.append("label_kosong")
        else:
            row["label_stabil"] = row["label_stabil"][0]
        for column, flag in [
            ("ph_awal", "ph_tidak_dilaporkan"),
            ("suhu_c", "suhu_tidak_dilaporkan"),
            ("durasi_jam", "durasi_tidak_dilaporkan"),
        ]:
            if not row.get(column):
                row["peringatan_qc"] = ";".join(filter(None, [row.get("peringatan_qc"), flag]))
        if row.get("metrik", "").lower().startswith("diprediksi"):
            row["peringatan_qc"] = ";".join(
                filter(None, [row.get("peringatan_qc"), "label_dari_klaim_prediksi_paten"])
            )
        row.setdefault("peringatan_qc", "")
        row["boleh_latih"] = "tidak" if notes else "ya"
        row["catatan_qc"] = ";".join(notes)
        rows.append(row)

    train = [r for r in rows if r["boleh_latih"] == "ya"]
    per_patent: dict[str, dict[str, int]] = defaultdict(lambda: {"0": 0, "1": 0})
    for r in train:
        per_patent[r["grup_split"]][r["label_stabil"]] += 1
    single_class = sorted(p for p, c in per_patent.items() if min(c.values()) == 0)
    out_fields = [
        *fieldnames,
        "grup_split",
        "durasi_hari",
        "boleh_latih",
        "catatan_qc",
        "peringatan_qc",
    ]
    return TableResult(
        out_fields,
        rows,
        {
            "baris_mentah": len(raw),
            "baris_boleh_latih": len(train),
            "label_per_paten": {k: dict(v) for k, v in sorted(per_patent.items())},
            "paten_satu_kelas": single_class,
            "label_terpaut_sumber": len(single_class) >= len(per_patent) - 1,
            "peringatan": sum(1 for r in train if r["peringatan_qc"]),
        },
    )


def _number(value: str) -> float | None:
    try:
        number = float(value.replace(",", "."))
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def prepare_lab(
    template_fields: list[str], runs: dict[str, tuple[list[str], list[Row]]]
) -> TableResult:
    """Files 11/12: LKPI run sheets. Only measured, labelled rows are trainable."""
    extra = ["sumber_file", "bagian", "ulangan", "kode_vial"]
    rows: list[Row] = []
    summary: dict[str, Any] = {"file": {}, "kolom_hilang": {}}
    for name, (fields, raw) in runs.items():
        missing = [c for c in template_fields if c not in fields]
        if missing:
            summary["kolom_hilang"][name] = missing
        filled = 0
        for source in raw:
            if not (source.get("retensi_h2o2_pct") or source.get("label_stabil")):
                continue
            filled += 1
            row = {c: source.get(c, "") for c in [*template_fields, *extra]}
            row["sumber_file"] = name
            notes: list[str] = []
            if row.get("data_origin") != "lab_LKPI":
                notes.append("data_origin_bukan_lab_LKPI")
            if row.get("label_stabil") not in {"0", "1"}:
                notes.append("label_stabil_kosong_atau_bukan_0_1")
            for column, (low, high) in LAB_RESULT_RANGES.items():
                if row.get(column):
                    value = _number(row[column])
                    if value is None or not low <= value <= high:
                        notes.append(f"{column}_di_luar_rentang_{low:g}_{high:g}")
            if not row.get("retensi_h2o2_pct"):
                notes.append("retensi_h2o2_pct_kosong")
            row["boleh_latih"] = "tidak" if notes else "ya"
            row["catatan_qc"] = ";".join(notes)
            rows.append(row)
        summary["file"][name] = {"baris_run_sheet": len(raw), "baris_berisi_hasil": filled}
    summary["baris_boleh_latih"] = sum(r["boleh_latih"] == "ya" for r in rows)
    return TableResult([*template_fields, *extra, "boleh_latih", "catatan_qc"], rows, summary)


def check_synthetic(raw: list[Row]) -> dict[str, Any]:
    leaked = [
        r.get("formula_id", "")
        for r in raw
        if r.get("data_origin") != "sintetis" or r.get("dipakai_training", "").startswith("ya")
    ]
    return {"baris": len(raw), "dikecualikan_seluruhnya": True, "baris_mencurigakan": leaked}


def prepare(source: Path, out: Path) -> dict[str, Any]:
    """Run every check and write the training-ready tables and report into ``out``."""
    inputs = [INGREDIENT_FILE, PATENT_FILE, SYNTHETIC_FILE, LAB_TEMPLATE_FILE, *LAB_RUN_FILES]
    for name in inputs:
        if not (source / name).is_file():
            raise FileNotFoundError(f"File dataset tidak ditemukan: {source / name}")

    ingredients = prepare_ingredients(*read_csv(source / INGREDIENT_FILE))
    patents = prepare_patents(*read_csv(source / PATENT_FILE))
    synthetic = check_synthetic(read_csv(source / SYNTHETIC_FILE)[1])
    template_fields, _ = read_csv(source / LAB_TEMPLATE_FILE)
    lab = prepare_lab(template_fields, {Path(n).name: read_csv(source / n) for n in LAB_RUN_FILES})

    outputs = {
        "bahan_oksidan_siap_latih.csv": ingredients,
        "formulasi_paten_siap_latih.csv": patents,
        "lab_LKPI_siap_latih.csv": lab,
    }
    for filename, table in outputs.items():
        write_csv(out / filename, table.fieldnames, table.rows)

    report = {
        "versi_aturan_qc": 1,
        "sha256_input": {name: sha256(source / name) for name in inputs},
        "bahan_oksidan": ingredients.summary,
        "formulasi_paten": patents.summary,
        "formulasi_sintetis_07": synthetic,
        "lab_LKPI": lab.summary,
        "sha256_output": {name: sha256(out / name) for name in outputs},
    }
    (out / "laporan_qc.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return report
