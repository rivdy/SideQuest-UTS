"""Read-only access to the BAYLab ingredient master and aroma profile tables (local dataset)."""

import csv
import os
from functools import lru_cache
from pathlib import Path

ROLE = {
    "aktif": "active",
    "stabilizer": "stabilizer",
    "buffer": "other",
    "surfaktan": "solubilizer",
    "pelarut": "solvent",
    "parfum": "fragrance",
}


def reference_dir() -> Path:
    default = (
        Path(__file__).resolve().parents[3]
        / "data"
        / "Dataset"
        / "BAYLab_dataset_final"
        / "1_referensi"
    )
    return Path(os.getenv("BAYLAB_REFERENCE_DIR", str(default)))


def _rows(name: str) -> list[dict]:
    path = reference_dir() / name
    if not path.exists():
        raise FileNotFoundError(f"Dataset lokal {name} belum tersedia.")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


@lru_cache(maxsize=2)
def _materials(stamp: float) -> tuple[dict, ...]:
    items = []
    for r in _rows("01_bahan_master.csv"):
        role = "water" if r["id"] == "air" else ROLE.get(r["kelas"], "other")
        items.append(
            {
                "id": r["id"],
                "name": r["nama"],
                "cas": r["cas"],
                "role": role,
                "description": r["peran"],
                "smiles": r["smiles"],
                "structure_source": r["sumber_struktur"] or "belum ada sumber",
                "oxidation_risk_draft": r["risiko_oksidasi_draf"],
                "ifra_10a_max_pct": r["ifra_10A_maks_pct"],
                "eu_allergen_label": r["label_alergen_eu"],
                "limits": r["batas_dan_bahaya"],
            }
        )
    return tuple(items)


@lru_cache(maxsize=2)
def _master(stamp: float) -> tuple[dict, ...]:
    return tuple(_rows("01_bahan_master.csv"))


def master_rows() -> tuple[dict, ...]:
    """Raw ingredient master rows (all columns), for rules that need regulatory fields."""
    path = reference_dir() / "01_bahan_master.csv"
    return _master(path.stat().st_mtime if path.exists() else 0.0)


def materials() -> tuple[dict, ...]:
    path = reference_dir() / "01_bahan_master.csv"
    return _materials(path.stat().st_mtime if path.exists() else 0.0)


def aroma_profiles() -> list[dict]:
    return [
        {
            "profile": r["profil_aroma"],
            "example_products": r["contoh_produk_indonesia"],
            "typical_components": [c.strip() for c in r["komponen_khas"].split(";") if c.strip()],
            "source": r["link_bukti"] or "belum ada sumber",
            "h2o2_fit_draft": r["kecocokan_basis_H2O2_draf"],
        }
        for r in _rows("02_parfum_populer_indonesia.csv")
    ]
