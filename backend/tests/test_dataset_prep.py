"""Dataset QC rules: exclusions are explicit and labels are never rewritten."""

import csv
import hashlib
from pathlib import Path

import pytest

from app.datasets.baylab_final import (
    DESCRIPTOR_NAMES,
    INGREDIENT_FILE,
    LAB_RUN_FILES,
    LAB_TEMPLATE_FILE,
    PATENT_FILE,
    SYNTHETIC_FILE,
    label_contradicts_basis,
    name_needs_check,
    prepare,
    prepare_ingredients,
    prepare_lab,
    prepare_patents,
)

ING_FIELDS = [
    "nama",
    "cas",
    "smiles",
    "label_stabil_oksidan",
    "keyakinan_label",
    "dasar_label",
    "sumber_url",
]


def ing(nama, cas, smiles, label, conf, basis="tercantum stabil di: bleach"):
    return dict(zip(ING_FIELDS, [nama, cas, smiles, label, conf, basis, "u"], strict=True))


@pytest.mark.parametrize(
    ("name", "flag"),
    [
        ("2", True),
        ("(E", True),
        ("methyl 2", True),
        ("tricyclo(5.2.1.02", True),
        ("2-methyl-4-phenyl-1", True),
        ("linalool", False),
        ("2-acetyl pyrrole", False),
        ("adoxal (Givaudan)", False),
    ],
)
def test_truncated_names_are_flagged(name, flag):
    assert name_needs_check(name) is flag


@pytest.mark.parametrize(
    ("basis", "label", "conflict"),
    [
        ("tercantum stabil di: bleach (poor)", "1", True),
        ("tercantum stabil di: bleach: poor", "1", True),
        ("hypochlorite bleach: poor; perborate powder detergent: good", "1", False),
        ("tercantum stabil di: bleach", "1", False),
        ("hanya hipoklorit: liquid bleach: poor", "0", False),
        ("bleach: good; detergent perborate: good", "0", True),
    ],
)
def test_label_basis_contradiction(basis, label, conflict):
    assert label_contradicts_basis(basis, label) is conflict


def test_ingredient_rules_exclude_without_rewriting_labels():
    raw = [
        ing("linalool", "78-70-6", "CC(C)=CCCC(C)(O)C=C", "0", "sedang", "liquid bleach: poor"),
        ing("no structure", "1-00-0", "", "1", "kuat"),
        ing("mixture", "2-00-0", "CCO.CCCO", "1", "sedang"),
        ing("poor but stable", "3-00-0", "CCCCCCO", "1", "sedang", "bleach (poor)"),
        ing("dup weak", "4-00-0", "OCCCCCCC", "1", "lemah"),
        ing("dup strong", "5-00-0", "CCCCCCCO", "1", "kuat"),
        ing("conflict a", "6-00-0", "c1ccccc1C", "1", "sedang"),
        ing("conflict b", "7-00-0", "Cc1ccccc1", "0", "sedang"),
        ing("weak only", "8-00-0", "CC(=O)OCC", "0", "lemah", "tidak tercantum (8 media)"),
    ]
    result = prepare_ingredients(ING_FIELDS, raw)
    rows = {r["cas"]: r for r in result.rows}

    assert [r["label_stabil_oksidan"] for r in result.rows] == [
        r["label_stabil_oksidan"] for r in raw
    ]
    assert rows["78-70-6"]["boleh_latih"] == rows["78-70-6"]["boleh_evaluasi"] == "ya"
    assert rows["78-70-6"]["grup_split"] == rows["78-70-6"]["smiles_kanonik"]
    assert all(rows["78-70-6"][n] for n in DESCRIPTOR_NAMES)
    assert "smiles_kosong" in rows["1-00-0"]["catatan_qc"]
    assert "multi_fragmen" in rows["2-00-0"]["catatan_qc"]
    assert "perlu_review_kimiawan" in rows["3-00-0"]["catatan_qc"]
    # The stronger duplicate survives; the weaker one points to it.
    assert rows["5-00-0"]["boleh_latih"] == "ya"
    assert rows["4-00-0"]["boleh_latih"] == "tidak"
    assert rows["4-00-0"]["duplikat_dari_cas"] == "5-00-0"
    # Equal-confidence duplicates that disagree are both removed.
    assert rows["6-00-0"]["boleh_latih"] == rows["7-00-0"]["boleh_latih"] == "tidak"
    # Weak labels may train but never evaluate.
    assert rows["8-00-0"]["boleh_latih"] == "ya" and rows["8-00-0"]["boleh_evaluasi"] == "tidak"
    assert result.summary["baris_boleh_latih"] == 3
    assert result.summary["baris_boleh_evaluasi_kuat_sedang"] == 2


PAT_FIELDS = ["formula_id", "dipakai_training", "sumber", "ph_awal", "suhu_c", "durasi_jam"]
PAT_FIELDS += ["metrik", "label_stabil"]


def test_patent_rows_get_patent_groups_and_day_units():
    raw = [
        dict(zip(PAT_FIELDS, r, strict=True))
        for r in [
            ["P1", "ya", "US 8802613 B2 (X)", "9.5", "97", "16", "% sisa", "0"],
            ["P2", "ya", "US 9149550 B2", "5", "45", "1344", "diprediksi stabil", "1"],
            ["P3", "tidak (label kosong)", "US 9149550 B2", "5", "", "", "x", ""],
        ]
    ]
    result = prepare_patents(PAT_FIELDS, raw)
    p1, p2, p3 = result.rows
    assert p1["grup_split"] == "US8802613" and p1["durasi_hari"] == "0.6667"
    assert p2["durasi_hari"] == "56" and "label_dari_klaim_prediksi_paten" in p2["peringatan_qc"]
    assert p3["boleh_latih"] == "tidak" and "label_kosong" in p3["catatan_qc"]
    assert result.summary["label_terpaut_sumber"] is True


LAB_FIELDS = ["formula_id", "retensi_h2o2_pct", "ph_akhir", "label_stabil", "data_origin"]


def test_only_measured_lab_rows_become_trainable():
    sheet = [
        {"formula_id": "A-1", "data_origin": "lab_LKPI"},
        {
            "formula_id": "A-2",
            "retensi_h2o2_pct": "92.5",
            "label_stabil": "1",
            "data_origin": "lab_LKPI",
        },
        {
            "formula_id": "A-3",
            "retensi_h2o2_pct": "180",
            "label_stabil": "1",
            "data_origin": "lab_LKPI",
        },
        {
            "formula_id": "A-4",
            "retensi_h2o2_pct": "50",
            "label_stabil": "0",
            "data_origin": "sintetis",
        },
    ]
    result = prepare_lab(LAB_FIELDS, {"11.csv": (LAB_FIELDS, sheet)})
    status = {r["formula_id"]: r["boleh_latih"] for r in result.rows}
    assert status == {"A-2": "ya", "A-3": "tidak", "A-4": "tidak"}
    assert result.summary["file"]["11.csv"] == {"baris_run_sheet": 4, "baris_berisi_hasil": 3}


def test_aroma_intensity_outside_panel_scale_is_rejected():
    fields = [*LAB_FIELDS, "skor_intensitas_aroma_0_5"]
    base = {"retensi_h2o2_pct": "95", "label_stabil": "1", "data_origin": "lab_LKPI"}
    sheet = [
        {"formula_id": "A-1", "skor_intensitas_aroma_0_5": "4", **base},
        {"formula_id": "A-2", "skor_intensitas_aroma_0_5": "7", **base},
    ]
    rows = {r["formula_id"]: r for r in prepare_lab(fields, {"11.csv": (fields, sheet)}).rows}
    assert rows["A-1"]["boleh_latih"] == "ya"
    assert rows["A-2"]["boleh_latih"] == "tidak"
    assert "skor_intensitas_aroma_0_5_di_luar_rentang" in rows["A-2"]["catatan_qc"]


def write(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_prepare_writes_outputs_and_leaves_raw_files_untouched(tmp_path):
    src = tmp_path / "src"
    write(src / INGREDIENT_FILE, ING_FIELDS, [ing("linalool", "78-70-6", "CCO", "1", "kuat")])
    write(src / PATENT_FILE, PAT_FIELDS, [dict.fromkeys(PAT_FIELDS, "") | {"sumber": "US 1"}])
    write(
        src / SYNTHETIC_FILE,
        ["formula_id", "data_origin", "dipakai_training"],
        [{"formula_id": "S", "data_origin": "sintetis", "dipakai_training": "tidak"}],
    )
    write(src / LAB_TEMPLATE_FILE, LAB_FIELDS, [])
    for name in LAB_RUN_FILES:
        write(src / name, LAB_FIELDS, [{"formula_id": "A", "data_origin": "lab_LKPI"}])
    before = {p: hashlib.sha256(p.read_bytes()).digest() for p in src.rglob("*.csv")}

    report = prepare(src, tmp_path / "out")

    assert before == {p: hashlib.sha256(p.read_bytes()).digest() for p in src.rglob("*.csv")}
    assert report["bahan_oksidan"]["baris_boleh_latih"] == 1
    assert report["formulasi_sintetis_07"]["baris_mencurigakan"] == []
    assert report["lab_LKPI"]["baris_boleh_latih"] == 0
    assert (tmp_path / "out" / "laporan_qc.json").is_file()
    assert (
        (tmp_path / "out" / "bahan_oksidan_siap_latih.csv").read_bytes().startswith(b"\xef\xbb\xbf")
    )


def test_prepare_refuses_incomplete_dataset(tmp_path):
    with pytest.raises(FileNotFoundError):
        prepare(tmp_path, tmp_path / "out")
