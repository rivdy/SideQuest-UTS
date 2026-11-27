"""Reference-case validation: chemist answers are read, never invented, and leakage is blocked."""

import csv
import json
from pathlib import Path

import pytest

from app.evaluation.reference_cases import (
    TEMPLATE_FIELDS,
    Criteria,
    detect_groups,
    load_cases,
    run,
    train_stability_model,
    write_default_criteria,
    write_template,
)


@pytest.mark.parametrize(
    ("smiles", "groups"),
    [
        ("CC(C)=CCCC(C)=CC=O", {"alkena", "aldehida"}),  # citral
        ("CC(C)=CCCC(C)(O)C=C", {"alkena", "alkohol"}),  # linalool
        ("Oc1ccccc1", {"fenol"}),
        ("CC(=O)OCC", {"ester"}),
        ("OO", {"peroksida"}),
        ("CCCCCC", set()),
    ],
)
def test_group_detection_uses_the_screening_engine(smiles, groups):
    assert detect_groups(smiles) == frozenset(groups)


def write_cases(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=TEMPLATE_FIELDS)
        writer.writeheader()
        writer.writerows([dict.fromkeys(TEMPLATE_FIELDS, "") | r for r in rows])


def test_only_chemist_validated_rows_are_scored(tmp_path):
    path = tmp_path / "kasus.csv"
    write_cases(
        path,
        [
            {
                "case_id": "CONTOH-1",
                "smiles": "CCO",
                "gugus_menurut_kimiawan": "alkohol",
                "divalidasi_oleh": "x",
            },
            {"case_id": "K1", "smiles": "CCO", "gugus_menurut_kimiawan": "alkohol"},
            {
                "case_id": "K2",
                "smiles": "CCO",
                "gugus_menurut_kimiawan": "alkohol",
                "divalidasi_oleh": "Pak Pugoh",
                "stabil_menurut_kimiawan": "1",
            },
            {
                "case_id": "K3",
                "smiles": "CCO",
                "gugus_menurut_kimiawan": "keton",
                "divalidasi_oleh": "Pak Pugoh",
            },
            {
                "case_id": "K4",
                "smiles": "CCO",
                "gugus_menurut_kimiawan": "tidak_ada",
                "divalidasi_oleh": "Pak Pugoh",
                "stabil_menurut_kimiawan": "ya",
            },
        ],
    )
    cases, skipped = load_cases(path)
    assert [c.case_id for c in cases] == ["K2"]
    assert cases[0].stable == 1
    reasons = {s.case_id: s.reason for s in skipped}
    assert reasons["K1"] == "belum divalidasi kimiawan"
    assert "keton" in reasons["K3"]
    assert "0, 1" in reasons["K4"]


def write_training(path: Path) -> None:
    rows = [
        ("CCCCCCO", "1"),
        ("CCCCCCCO", "1"),
        ("CCCCO", "1"),
        ("CCC=CCCO", "0"),
        ("CC=CC=O", "0"),
        ("C=CCCC=C", "0"),
        ("CCO", "1"),
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["smiles_kanonik", "label_stabil_oksidan", "boleh_evaluasi"])
        writer.writerows([[s, y, "ya"] for s, y in rows])


def test_reference_structures_are_removed_from_training(tmp_path):
    training = tmp_path / "latih.csv"
    write_training(training)
    model = train_stability_model(training, ["OCC"])  # same molecule as CCO
    assert model.excluded_for_leakage == 1
    assert "CCO" not in model.training_smiles


def test_run_writes_report_with_hashes_and_honest_verdict(tmp_path):
    cases = tmp_path / "kasus.csv"
    write_template(cases)
    with cases.open("a", encoding="utf-8-sig", newline="") as stream:
        csv.DictWriter(stream, fieldnames=TEMPLATE_FIELDS).writerow(
            dict.fromkeys(TEMPLATE_FIELDS, "")
            | {
                "case_id": "K1",
                "nama": "Citral",
                "smiles": "CC(C)=CCCC(C)=CC=O",
                "gugus_menurut_kimiawan": "alkena;aldehida",
                "stabil_menurut_kimiawan": "0",
                "divalidasi_oleh": "Pak Pugoh",
            }
        )
    criteria = tmp_path / "kriteria.json"
    write_default_criteria(criteria)
    training = tmp_path / "latih.csv"
    write_training(training)

    report = run(cases, criteria, training, tmp_path / "out")

    assert report["kasus_dipakai"] == 1
    assert report["deteksi_gugus"]["kesesuaian_himpunan_gugus"] == 1.0
    assert report["hasil_per_kasus"][0]["stabil_kimiawan"] == 0
    # One case cannot satisfy the default minimum of 20, so the verdict must be negative.
    assert report["lulus_semua_kriteria"] is False
    assert len(report["sha256_kriteria"]) == 64
    written = sorted(p.suffix for p in (tmp_path / "out").iterdir())
    assert written == [".json", ".md"]


def test_criteria_file_rejects_unknown_keys(tmp_path):
    from app.evaluation.reference_cases import load_criteria

    path = tmp_path / "k.json"
    path.write_text(json.dumps({"min_kasus_tervalidasi": 5, "bonus": 1}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_criteria(path)
    assert Criteria().min_kasus_tervalidasi == 20
