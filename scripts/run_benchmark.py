"""Interim benchmark of BAYLab AI on existing data. Run from the project root:
python scripts/run_benchmark.py
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.evaluation.benchmark import benchmark_detection, benchmark_stability  # noqa: E402

DATASET = ROOT / "data" / "Dataset" / "BAYLab_dataset_final"
report = {
    "dijalankan_pada": datetime.now(UTC).isoformat(timespec="seconds"),
    "prediksi_stabilitas_bahan": benchmark_stability(
        DATASET / "siap_latih" / "bahan_oksidan_siap_latih.csv"
    ),
    "deteksi_gugus": benchmark_detection(DATASET / "1_referensi" / "01_bahan_master.csv"),
}
out = ROOT / "data" / "validasi"
out.mkdir(parents=True, exist_ok=True)
path = out / "benchmark_sementara.json"
path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=1))
print(f"\nDitulis ke: {path}")
