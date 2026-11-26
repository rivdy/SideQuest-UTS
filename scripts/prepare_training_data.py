"""Check BAYLab_dataset_final and write training-ready tables without touching raw files.

Run from the backend folder:
    python ../scripts/prepare_training_data.py
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.datasets.baylab_final import prepare  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument(
    "--source", type=Path, default=ROOT / "data" / "Dataset" / "BAYLab_dataset_final"
)
parser.add_argument("--out", type=Path, default=None)
args = parser.parse_args()
out = args.out or args.source / "siap_latih"
report = prepare(args.source, out)
print(json.dumps({k: v for k, v in report.items() if not k.startswith("sha256")}, indent=1))
print(f"\nHasil ditulis ke: {out}")
