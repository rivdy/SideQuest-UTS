"""Interim benchmark: same folds for every approach, rule baseline from the real engine."""

import csv
from pathlib import Path

from app.evaluation.benchmark import benchmark_detection, benchmark_stability, rule_scores


def test_rule_baseline_flags_risky_groups():
    assert list(rule_scores(["CC(C)=CCCC(C)=CC=O", "CCCCCCO", "Oc1ccccc1"])) == [0.0, 1.0, 0.0]


def write_training(path: Path) -> None:
    stable = [
        "CCCCCCO",
        "CCCCCCCO",
        "CCCCO",
        "CCCCCCCCO",
        "CC(C)CCO",
        "CCC(C)CO",
        "CCCC(C)O",
        "CCCCCC(C)O",
        "CC(C)(C)CO",
        "CCOCCO",
    ]
    unstable = [
        "CCC=CCCO",
        "CC=CC=O",
        "C=CCCC=C",
        "CC=CCCC=O",
        "C=CCO",
        "CC=CCO",
        "C=CC=CC",
        "O=CCCC=C",
        "CC(C)=CCO",
        "C=CCCCO",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["smiles_kanonik", "label_stabil_oksidan", "boleh_evaluasi", "grup_split"])
        writer.writerows(
            [[s, "1", "ya", s] for s in stable] + [[s, "0", "ya", s] for s in unstable]
        )


def test_benchmark_reports_every_approach_against_the_target(tmp_path):
    training = tmp_path / "latih.csv"
    write_training(training)
    report = benchmark_stability(training, seeds=2, folds=2)
    assert set(report["hasil"]) == {
        "mayoritas",
        "aturan_gugus_saja",
        "logistic_regression",
        "random_forest",
    }
    assert report["data"]["baris"] == 20
    assert report["target_roc_auc"] == 0.8
    # The toy labels follow the C=C/aldehyde rule exactly, so the rule baseline is perfect.
    assert report["hasil"]["aturan_gugus_saja"]["roc_auc"]["rerata"] == 1.0


def test_detection_benchmark_compares_with_master_counts(tmp_path):
    master = tmp_path / "master.csv"
    with master.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            ["nama", "smiles", "R01_alkena_CC", "R02_aldehida", "R03_fenol", "R08_peroksida"]
        )
        writer.writerow(["Citral", "CC(C)=CCCC(C)=CC=O", "2", "1", "0", "0"])
        writer.writerow(["Salah", "CCCCCC", "1", "0", "0", "0"])
    report = benchmark_detection(master)
    assert report["bahan_diperiksa"] == 2
    assert report["kesesuaian_per_gugus"]["alkena"] == 0.5
    assert report["perbedaan"][0]["bahan"] == "Salah"
