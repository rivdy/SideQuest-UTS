"""Free-text "formula alternatif beraroma": keep the disinfectant base, swap only the fragrance.

Ported from the earlier BAYLab prototype (app/aroma/recommend.py) onto the current ingredient
master. Fragrance choice uses the draft oxidation-risk column of the master table plus the
descriptor words in `peran`; doses are split equally and capped by the dataset's IFRA 10A value.
No LLM is involved, and the output is a draft that a chemist has not validated.
"""

from pydantic import BaseModel, ConfigDict, Field

from .draft import PLAN, _watched
from .library import ROLE, master_rows

RISK_SCORE = {"Rendah": 1.0, "Sedang": 0.5, "Tinggi": 0.0}
WATER = {"air", "water", "aqua", "aquadest", "akuades", "air murni", "air demineralisasi"}
# Scent words people type (Indonesian/English) -> descriptor words used in `peran`.
FAMILIES: dict[str, set[str]] = {
    "citrus": {"citrus", "jeruk", "lemon", "lime", "segar", "fresh", "orange"},
    "lemon": {"lemon", "citrus", "jeruk"},
    "segar": {"segar", "fresh", "citrus"},
    "fresh": {"fresh", "segar", "citrus"},
    "floral": {"floral", "bunga", "melati", "jasmine", "mawar", "rose", "lavender"},
    "melati": {"melati", "jasmine", "floral"},
    "lavender": {"lavender", "floral"},
    "pine": {"pine", "pinus", "cemara"},
    "woody": {"woody", "kayu", "nilam", "patchouli"},
    "nilam": {"nilam", "patchouli", "woody"},
    "sereh": {"sereh", "citronella", "lemongrass"},
    "spicy": {"spicy", "rempah", "cengkeh"},
    "musk": {"musk", "lembut"},
    "manis": {"manis", "sweet", "vanilla"},
    "fruity": {"fruity", "buah", "apel", "apple"},
    "apel": {"apel", "apple", "fruity"},
    "green": {"green", "hijau", "daun"},
}
RULE_COLUMNS = {
    "R01_alkena_CC": "C=C (alkena)",
    "R02_aldehida": "aldehida",
    "R03_fenol": "fenol",
    "R05_amina_tersier": "amina tersier",
    "R06_tioeter": "tioeter",
    "R07_CH_alilik": "C-H alilik",
}


class TextComponent(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    pct: float = Field(ge=0, le=100)


class TextAlternativeInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    components: list[TextComponent] = Field(min_length=1, max_length=30)
    target: str = Field(min_length=2, max_length=160)
    include_medium_risk: bool = False
    max_items: int = Field(default=5, ge=1, le=8)


def _terms(text: str) -> set[str]:
    out: set[str] = set()
    for word in text.lower().replace("/", " ").replace("-", " ").replace(",", " ").split():
        out.add(word)
        out |= FAMILIES.get(word, set())
    return out


def _is_water(name: str) -> bool:
    key = name.strip().lower()
    return key in WATER or key.startswith(("air ", "water ", "aqua ", "aquadest ", "akuades "))


def _number(value: str) -> float | None:
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def _find(name: str) -> dict | None:
    key = name.strip().lower()
    rows = master_rows()
    for row in rows:
        if key in {row["id"].lower(), row["nama"].lower(), row["cas"].lower()}:
            return row
    for row in rows:
        if key and key in row["nama"].lower():
            return row
    return None


def recommend(target: str, total_pct: float, max_items: int, include_medium: bool) -> dict:
    wanted = _terms(target)
    if not wanted:
        raise ValueError("Target aroma kosong.")
    allowed = {"Rendah", "Sedang"} if include_medium else {"Rendah"}
    candidates, excluded = [], []
    for row in master_rows():
        if not row["peran"].lower().startswith("parfum"):
            continue
        descriptor = row["peran"].lower().removeprefix("parfum").strip(" /")
        overlap = _terms(descriptor) & wanted
        if not overlap:
            continue
        rules = [label for col, label in RULE_COLUMNS.items() if row.get(col) == "1"]
        risk = row["risiko_oksidasi_draf"]
        if risk not in allowed:
            excluded.append({"name": row["nama"], "risk": risk, "triggered_rules": rules})
            continue
        match = round(len(overlap) / len(_terms(descriptor)), 2)
        candidates.append(
            {
                "id": row["id"],
                "name": row["nama"],
                "cas": row["cas"],
                "smiles": row["smiles"],
                "descriptor": descriptor,
                "risk": risk,
                "triggered_rules": rules,
                "aroma_match": match,
                "score": round(0.6 * match + 0.4 * RISK_SCORE.get(risk, 0.0), 2),
                "ifra_10a_max_pct": _number(row["ifra_10A_maks_pct"]),
                "sources": [s for s in (row["sumber_struktur"], row["sumber_regulasi"]) if s],
                "reason": "Cocok: " + ", ".join(sorted(overlap)) + "; risiko oksidasi draf " + risk,
            }
        )
    candidates.sort(key=lambda c: (-c["score"], c["name"]))
    picked, blend = candidates[:max_items], []
    if picked:
        share = round(total_pct / len(picked), 4)
        for c in picked:
            cap = c["ifra_10a_max_pct"]
            dose = share if cap is None else min(share, cap)
            blend.append({**c, "pct": dose, "capped_by_ifra": dose < share})
    return {"candidates": candidates, "blend": blend, "excluded": excluded}


def text_alternative(payload: TextAlternativeInput) -> dict:
    base, removed, warnings = [], [], []
    perfume_pct = surfactant_pct = 0.0
    for comp in payload.components:
        if _is_water(comp.name):
            continue
        row = _find(comp.name)
        if row and row["peran"].lower().startswith("parfum"):
            perfume_pct += comp.pct
            removed.append(
                {
                    "name": row["nama"],
                    "pct": comp.pct,
                    "risk": row["risiko_oksidasi_draf"],
                    "groups": _watched(row["smiles"]) if row["smiles"] else [],
                }
            )
            continue
        if not row:
            warnings.append(f"{comp.name} tidak ada di Library Bahan; risikonya belum diketahui.")
        elif row["kelas"] == "surfaktan" or "solubilizer" in row["peran"].lower():
            surfactant_pct += comp.pct
        base.append(
            {
                "name": row["nama"] if row else comp.name,
                "cas": row["cas"] if row else "",
                "role": row["peran"] if row else "tidak dikenal",
                "role_key": ROLE.get(row["kelas"], "other") if row else "other",
                "smiles": row["smiles"] if row else "",
                "pct": comp.pct,
                "source": "formula asal",
            }
        )
    if not perfume_pct:
        perfume_pct = 0.4
        warnings.append(f"Formula asal tanpa parfum; dipakai muatan 0,4% ({PLAN} faktor D).")
    rec = recommend(payload.target, perfume_pct, payload.max_items, payload.include_medium_risk)
    fragrance = [
        {
            "name": b["name"],
            "cas": b["cas"],
            "role": "parfum (pengganti)",
            "role_key": "fragrance",
            "smiles": b["smiles"],
            "pct": b["pct"],
            "source": "rekomendasi aroma",
            "capped_by_ifra": b["capped_by_ifra"],
        }
        for b in rec["blend"]
    ]
    if not fragrance:
        warnings.append("Tidak ada bahan aroma yang cocok dan berisiko rendah untuk target ini.")
    elif surfactant_pct == 0:
        warnings.append(
            "Formula belum punya surfaktan / solubilizer parfum. Rencana eksperimen memakai AE 7EO "
            "dengan rasio surfaktan : parfum minimal 3 : 1; tentukan dosisnya lewat uji kejernihan."
        )
    elif surfactant_pct < 3 * perfume_pct:
        warnings.append(
            f"Rasio surfaktan : parfum di bawah 3 : 1 ({PLAN}); uji kejernihan sebelum dipakai."
        )
    if any(f["capped_by_ifra"] for f in fragrance):
        warnings.append("Sebagian dosis dibatasi nilai IFRA 10A di dataset; total parfum turun.")
    water = round(100 - sum(c["pct"] for c in base + fragrance), 4)
    if water < 0:
        raise ValueError("Total komponen melebihi 100% b/b.")
    alt = [
        *base,
        *fragrance,
        {
            "name": "Air murni",
            "cas": "7732-18-5",
            "role": "pelarut",
            "role_key": "water",
            "smiles": "O",
            "pct": water,
            "source": "penyeimbang",
        },
    ]
    return {
        "target": payload.target,
        "status": "draft",
        "alternative": alt,
        "removed_fragrance": removed,
        "fragrance_candidates": rec["candidates"],
        "excluded_fragrance": rec["excluded"],
        "warnings": warnings,
        "note": "Formula alternatif draf: zat aktif dan basis disinfektan dipertahankan sesuai "
        "formula asal; hanya parfum yang diganti. Risiko memakai kolom risiko oksidasi draf di "
        "Library Bahan. Efikasi antimikroba, stabilitas H2O2, dan aroma wajib dibuktikan lewat "
        "uji lab dan ditinjau ahli kimia.",
    }
