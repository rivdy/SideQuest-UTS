"""Score BAYLab components against the chemist's reference cases (TKT 4 evidence).

First run creates an empty template and default criteria:
    python scripts/run_reference_validation.py --init
Commit the criteria file before the chemist's cases are scored, then run:
    python scripts/run_reference_validation.py
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.evaluation.reference_cases import (  # noqa: E402
    run,
    write_default_criteria,
    write_template,
)

DATA = ROOT / "data"
parser = argparse.ArgumentParser()
parser.add_argument("--init", action="store_true", help="buat template kasus dan kriteria")
parser.add_argument("--cases", type=Path, default=DATA / "validasi" / "kasus_acuan.csv")
parser.add_argument("--criteria", type=Path, default=ROOT / "validasi" / "kriteria_lulus.json")
parser.add_argument(
    "--training",
    type=Path,
    default=DATA
    / "Dataset"
    / "BAYLab_dataset_final"
    / "siap_latih"
    / "bahan_oksidan_siap_latih.csv",
)
parser.add_argument("--out", type=Path, default=DATA / "validasi")
args = parser.parse_args()

if args.init:
    if args.cases.exists():
        print(f"Tidak ditimpa, sudah ada: {args.cases}")
    else:
        write_template(args.cases)
        print(f"Template kasus acuan: {args.cases}")
    if args.criteria.exists():
        print(f"Tidak ditimpa, sudah ada: {args.criteria}")
    else:
        write_default_criteria(args.criteria)
        print(f"Kriteria lulus: {args.criteria} (commit file ini sebelum menjalankan uji)")
    raise SystemExit(0)

report = run(args.cases, args.criteria, args.training, args.out)
print(
    json.dumps(
        {k: report[k] for k in ("kasus_dipakai", "pemeriksaan_kriteria", "lulus_semua_kriteria")},
        ensure_ascii=False,
        indent=1,
    )
)
print(f"\nLaporan lengkap ditulis ke: {args.out}")
