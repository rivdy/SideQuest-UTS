"""Deterministic draft formulation from the team's experiment plan and the ingredient master.

Every line carries its source. The draft is a starting point for the formulator; it is not a
stability prediction and the oxidation rules are drafts that a chemist has not validated.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.chemistry.engine import screen

from .library import materials

PLAN = "RENCANA_EKSPERIMEN_LKPI Bagian B"
WATCHED = {"DRAFT-ALKENE", "DRAFT-ALDEHYDE", "DRAFT-PHENOL"}
# Fragrance load per intensity = low / centre / high level of DoE factor D.
LOAD = {"ringan": 0.2, "sedang": 0.4, "kuat": 0.6}
# UI aroma preference -> words used in the `peran` column of the ingredient master.
KEYWORDS = {
    "Citrus": ("citrus", "lemon", "lime", "jeruk"),
    "Fresh": ("fresh", "segar"),
    "Floral": ("floral", "melati", "lavender"),
    "Woody": ("woody", "musk", "nilam", "pine"),
    "Fruity": ("fruity", "apel"),
    "Herbal": ("pine", "segar", "sereh"),
    "Musky": ("musk",),
    "Sweet": ("manis", "almond"),
}
Aroma = Literal["Citrus", "Fresh", "Floral", "Woody", "Fruity", "Herbal", "Musky", "Sweet"]


class DraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    aroma: list[Aroma] = Field(default_factory=list, max_length=8)
    intensity: Literal["ringan", "sedang", "kuat"] = "sedang"
    h2o2_active_pct: float = Field(default=3.5, gt=0, le=10)
    h2o2_stock_pct: float = Field(default=50, ge=10, le=70)
    perfume_ids: list[str] = Field(default_factory=list, max_length=10)
    max_components: int = Field(default=5, ge=1, le=8)


def _watched(smiles: str) -> list[str]:
    try:
        return [m.rule.name for m in screen(smiles).matches if m.rule.id in WATCHED]
    except ValueError:
        return ["struktur tidak terbaca"]


def _line(name, role, percent, source, item=None) -> dict:
    return {
        "name": name,
        "role": role,
        "percent": round(percent, 4),
        "smiles": (item or {}).get("smiles", ""),
        "cas": (item or {}).get("cas", ""),
        "library_id": (item or {}).get("id", ""),
        "source": source,
    }


def _fmt(value: float) -> str:
    return f"{value:g}".replace(".", ",")


def pick_aroma(lib: dict, aroma: list[str], limit: int) -> tuple[list, list]:
    """Library fragrance materials matching the preferences, without C=C, aldehyde or phenol."""
    scored, rejected = [], []
    for item in lib.values():
        if item["role"] != "fragrance" or not item["smiles"]:
            continue
        text = (item["description"] + " " + item["name"]).lower()
        hits = [a for a in aroma if any(k in text for k in KEYWORDS[a])]
        if not hits:
            continue
        groups = _watched(item["smiles"])
        if groups:
            rejected.append(
                {
                    "name": item["name"],
                    "smiles": item["smiles"],
                    "reason": "Ada " + ", ".join(groups),
                }
            )
        else:
            scored.append((-len(hits), item["eu_allergen_label"] == "ya", item["name"], item, hits))
    scored.sort(key=lambda s: s[:3])
    return [(s[3], "cocok dengan " + ", ".join(s[4])) for s in scored[:limit]], rejected


def build_draft(payload: DraftInput) -> dict:
    lib = {m["id"]: m for m in materials()}
    checks, notes = [], []
    load = LOAD[payload.intensity] if (payload.aroma or payload.perfume_ids) else 0.0

    chosen, rejected = [], []
    if payload.perfume_ids:
        unknown = [i for i in payload.perfume_ids if i not in lib]
        if unknown:
            raise ValueError("Bahan parfum tidak ada di library: " + ", ".join(unknown))
        for pid in payload.perfume_ids:
            item, groups = lib[pid], _watched(lib[pid]["smiles"])
            chosen.append((item, "dipilih formulator"))
            if groups:
                checks.append(
                    f"{item['name']} punya gugus yang perlu diawasi: {', '.join(groups)}."
                )
    elif payload.aroma:
        chosen, rejected = pick_aroma(lib, payload.aroma, payload.max_components)
        if not chosen:
            notes.append(
                "Tidak ada bahan aroma di library yang cocok tanpa gugus C=C, aldehida, "
                "atau fenol. "
                "Pilih preferensi lain atau tambahkan bahan ke library."
            )
            load = 0.0

    stock, active = _fmt(payload.h2o2_stock_pct), _fmt(payload.h2o2_active_pct)
    lines = [
        _line(
            f"Hydrogen peroxide {stock}% (aktif {active}%)",
            "active",
            payload.h2o2_active_pct / payload.h2o2_stock_pct * 100,
            f"Target formulator; {PLAN} faktor A 3,0-4,0%; contoh PKRT 3-10% "
            "(Kepdirjen Farmalkes 776/2022)",
            lib.get("h2o2"),
        ),
        _line(
            "HEDP 60% (aktif 0,125%)",
            "stabilizer",
            0.125 / 0.6,  # % of a 60% stock that gives 0.125% active HEDP
            f"{PLAN} titik tengah faktor C (HEDP aktif 0,05-0,2%); kadar stok 60% sesuaikan CoA",
            lib.get("hedp"),
        ),
        _line(
            "Alcohol ethoxylate C12-14 7EO",
            "solubilizer",
            max(2.0, 3 * load),
            f"{PLAN}: surfaktan 7EO 2%, rasio surfaktan : parfum minimal 3 : 1",
            lib.get("laureth7"),
        ),
        _line(
            "Asam sitrat",
            "other",
            0.2,
            "Perkiraan awal; atur dengan pH meter sampai pH 3,75 (titik tengah faktor B). "
            "Kadar belum ada sumber",
            lib.get("sitrat"),
        ),
        _line(
            "Trisodium sitrat",
            "other",
            0.1,
            "Pasangan buffer sitrat; kadar belum ada sumber, sesuaikan saat atur pH",
            lib.get("na_sitrat"),
        ),
    ]
    if chosen:
        share = load / len(chosen)
        for item, why in chosen:
            lines.append(
                _line(
                    item["name"],
                    "fragrance",
                    share,
                    f"Library bahan BAYLab ({why}); muatan parfum {_fmt(load)}% = {PLAN} faktor D; "
                    "porsi dibagi rata, atur setelah uji panel",
                    item,
                )
            )
            limit = item["ifra_10a_max_pct"].replace(",", ".")
            if limit.replace(".", "", 1).isdigit() and share > float(limit):
                checks.append(
                    f"{item['name']} melebihi batas IFRA 10A di dataset "
                    f"({item['ifra_10a_max_pct']}%)."
                )
            if item["eu_allergen_label"] == "ya":
                checks.append(
                    f"{item['name']} termasuk alergen berlabel (dataset); cantumkan di label."
                )
    water = 100 - sum(line["percent"] for line in lines)
    lines.append(
        _line("Air demineralisasi (ad 100)", "water", water, "Sisa hingga 100%", lib.get("air"))
    )
    if not 3 <= payload.h2o2_active_pct <= 10:
        checks.append("Kadar H2O2 aktif di luar contoh PKRT 3-10% (Kepdirjen Farmalkes 776/2022).")
    return {
        "ingredients": lines,
        "rejected": rejected,
        "checks": checks,
        "notes": notes,
        "target_ph": 3.75,
        "status": "draft",
        "method": (
            "Aturan tetap: basis dari titik tengah rencana DoE, bahan aroma dari library BAYLab "
            "tanpa gugus C=C, aldehida, atau fenol (RDKit, aturan draf). Bukan model bahasa."
        ),
        "scope": (
            "Draf awal untuk formulator; belum divalidasi kimiawan dan bukan prediksi stabilitas."
        ),
    }


class AltIngredient(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    role: Literal["active", "fragrance", "solubilizer", "stabilizer", "solvent", "water", "other"]
    percent: float = Field(ge=0, le=100)
    smiles: str = Field(default="", max_length=2000)


class AlternativeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ingredients: list[AltIngredient] = Field(min_length=1, max_length=30)
    aroma: list[Aroma] = Field(min_length=1, max_length=8)
    max_components: int = Field(default=5, ge=1, le=8)


def alternative(payload: AlternativeInput) -> dict:
    """Keep the disinfectant base, replace only the fragrance, rebalance water to 100%."""
    lib = {m["id"]: m for m in materials()}
    base = [i for i in payload.ingredients if i.role not in ("fragrance", "water")]
    removed = [i for i in payload.ingredients if i.role == "fragrance"]
    load = round(sum(i.percent for i in removed), 6)
    checks = []
    if not load:
        load = LOAD["sedang"]
        checks.append(
            f"Formula asal tanpa parfum; dipakai muatan {_fmt(load)}% "
            f"({PLAN} faktor D, titik tengah)."
        )
    chosen, rejected = pick_aroma(lib, payload.aroma, payload.max_components)
    removed_out = [
        {"name": i.name, "percent": i.percent, "groups": _watched(i.smiles) if i.smiles else []}
        for i in removed
    ]
    lines = [
        _line(i.name, i.role, i.percent, "Dipertahankan dari formula asal", {"smiles": i.smiles})
        for i in base
    ]
    if chosen:
        share = load / len(chosen)
        for item, why in chosen:
            lines.append(
                _line(
                    item["name"],
                    "fragrance",
                    share,
                    f"Library bahan BAYLab ({why}); muatan parfum sama dengan formula asal, "
                    "dibagi rata",
                    item,
                )
            )
            if item["eu_allergen_label"] == "ya":
                checks.append(
                    f"{item['name']} termasuk alergen berlabel (dataset); cantumkan di label."
                )
    else:
        checks.append("Tidak ada bahan aroma di library yang cocok tanpa gugus rentan.")
    solubilizer = sum(i.percent for i in base if i.role == "solubilizer")
    if chosen and solubilizer < 3 * load:
        checks.append(
            f"Rasio solubilizer : parfum {_fmt(round(solubilizer / load, 2))} : 1, di bawah "
            f"minimal 3 : 1 di {PLAN}; uji kejernihan."
        )
    water = round(100 - sum(line["percent"] for line in lines), 6)
    if water < 0:
        raise ValueError("Total komponen melebihi 100% b/b.")
    lines.append(
        _line("Air demineralisasi (ad 100)", "water", water, "Penyeimbang", lib.get("air"))
    )
    return {
        "ingredients": lines,
        "removed": removed_out,
        "rejected": rejected,
        "checks": checks,
        "status": "draft",
        "method": "Basis disinfektan dipertahankan; hanya parfum diganti dengan bahan library "
        "tanpa gugus C=C, aldehida, atau fenol (RDKit, aturan draf). Bukan model bahasa.",
        "scope": "Draf; stabilitas H2O2, aroma, dan efikasi wajib dibuktikan lewat uji lab.",
    }
