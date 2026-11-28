"""Rule-based draft formulation: sourced lines, 100% total, rejected vulnerable aroma materials."""

import pytest
from conftest import sign_in
from fastapi.testclient import TestClient

from app.formulation.draft import DraftInput, build_draft
from app.formulation.library import materials, reference_dir
from app.main import app
from app.rag.api import recent

pytestmark = pytest.mark.skipif(
    not (reference_dir() / "01_bahan_master.csv").exists(), reason="local dataset not present"
)


@pytest.fixture
def client():
    recent.clear()
    client = TestClient(app, base_url="http://127.0.0.1")
    sign_in(client)
    return client


def by_role(draft, role):
    return [line for line in draft["ingredients"] if line["role"] == role]


def test_library_has_structures_so_pubchem_is_not_needed():
    items = materials()
    assert len(items) >= 50
    fragrance = [m for m in items if m["role"] == "fragrance"]
    assert fragrance and sum(bool(m["smiles"]) for m in fragrance) == len(fragrance)


def test_citrus_draft_uses_plan_levels_and_rejects_vulnerable_citrus_notes():
    draft = build_draft(DraftInput(aroma=["Citrus"], intensity="sedang", h2o2_active_pct=3.5))
    assert abs(sum(line["percent"] for line in draft["ingredients"]) - 100) < 1e-6
    assert by_role(draft, "active")[0]["percent"] == 7.0
    assert abs(sum(line["percent"] for line in by_role(draft, "fragrance")) - 0.4) < 1e-6
    names = {line["name"] for line in by_role(draft, "fragrance")}
    assert "Tetrahydromyrcenol" in names and "d-Limonene" not in names
    rejected = {r["name"] for r in draft["rejected"]}
    assert {"d-Limonene", "Citral"} <= rejected
    assert all(line["source"] for line in draft["ingredients"])
    assert draft["status"] == "draft" and "Bukan model bahasa" in draft["method"]


def test_chosen_vulnerable_perfume_is_kept_but_flagged():
    draft = build_draft(DraftInput(perfume_ids=["limonene"], intensity="kuat"))
    assert by_role(draft, "fragrance")[0]["name"] == "d-Limonene"
    assert by_role(draft, "solubilizer")[0]["percent"] == pytest.approx(2.0)
    assert any("d-Limonene" in c for c in draft["checks"])


def test_api_validates_input(client):
    assert client.get("/api/formulation/library").status_code == 200
    ok = client.post("/api/formulation/draft", json={"aroma": ["Fresh"], "intensity": "ringan"})
    assert ok.status_code == 200
    assert client.post("/api/formulation/draft", json={"aroma": ["Smoky"]}).status_code == 422
    assert (
        client.post("/api/formulation/draft", json={"perfume_ids": ["unknown"]}).status_code == 422
    )


def test_alternative_keeps_base_and_swaps_only_fragrance():
    from app.formulation.draft import AlternativeInput, alternative

    original = [
        {"name": "Hidrogen peroksida 50%", "role": "active", "percent": 6, "smiles": "OO"},
        {"name": "AE 7EO", "role": "solubilizer", "percent": 2},
        {
            "name": "d-Limonene",
            "role": "fragrance",
            "percent": 0.3,
            "smiles": "CC1=CC[C@@H](CC1)C(=C)C",
        },
        {"name": "Citral", "role": "fragrance", "percent": 0.1, "smiles": "CC(=CCC/C(=C/C=O)/C)C"},
        {"name": "Air", "role": "water", "percent": 91.6},
    ]
    result = alternative(AlternativeInput(ingredients=original, aroma=["Citrus"]))
    lines = result["ingredients"]
    assert abs(sum(line["percent"] for line in lines) - 100) < 1e-6
    assert [line["percent"] for line in lines[:2]] == [6, 2]
    fragrance = [line for line in lines if line["role"] == "fragrance"]
    assert abs(sum(line["percent"] for line in fragrance) - 0.4) < 1e-6
    assert {"d-Limonene", "Citral"}.isdisjoint({line["name"] for line in fragrance})
    assert {r["name"] for r in result["removed"]} == {"d-Limonene", "Citral"}
    assert all(r["groups"] for r in result["removed"])


def test_text_alternative_matches_prototype_floral_case(client):
    body = {
        "components": [
            {"name": "Hydrogen peroxide", "pct": 3},
            {"name": "Benzalkonium chloride", "pct": 0.1},
            {"name": "d-Limonene", "pct": 0.5},
            {"name": "Air", "pct": 96.4},
        ],
        "target": "Floral",
    }
    r = client.post("/api/formulation/alternative-text", json=body)
    assert r.status_code == 200, r.text
    d = r.json()
    names = [c["name"] for c in d["alternative"]]
    assert names[0] == "Hydrogen peroxide" and "d-Limonene" not in names
    fragrance = [c for c in d["alternative"] if c["source"] == "rekomendasi aroma"]
    assert len(fragrance) == 5 and abs(sum(c["pct"] for c in fragrance) - 0.5) < 1e-6
    assert abs(sum(c["pct"] for c in d["alternative"]) - 100) < 1e-6
    assert d["removed_fragrance"][0]["risk"] == "Tinggi"
    assert any("surfaktan" in w for w in d["warnings"])
    assert all(c["risk"] == "Rendah" for c in d["fragrance_candidates"])
    medium = client.post(
        "/api/formulation/alternative-text",
        json={**body, "target": "segar", "include_medium_risk": True},
    ).json()
    assert {c["risk"] for c in medium["fragrance_candidates"]} <= {"Rendah", "Sedang"}
    assert "Sedang" in {c["risk"] for c in medium["fragrance_candidates"]}
