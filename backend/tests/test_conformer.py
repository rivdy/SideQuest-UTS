"""3D structure endpoint: deterministic display geometry, bounded input, no property claims."""

import pytest
from conftest import sign_in
from fastapi.testclient import TestClient

from app.chemistry.conformer import conformer
from app.main import app
from app.rag.api import recent


@pytest.fixture
def client():
    recent.clear()
    client = TestClient(app, base_url="http://127.0.0.1")
    sign_in(client)
    return client


def test_limonene_geometry_is_complete_and_repeatable():
    first, second = conformer("CC1=CC[C@@H](CC1)C(=C)C"), conformer("CC1=CC[C@@H](CC1)C(=C)C")
    elements = [a.element for a in first.atoms]
    assert elements.count("C") == 10 and elements.count("H") == 16
    assert len(first.bonds) == 26
    assert sorted(b.order for b in first.bonds)[-2:] == [2.0, 2.0]
    assert first.atoms == second.atoms
    assert abs(sum(a.x for a in first.atoms)) < 1e-6
    assert "bukan prediksi" in first.note


def test_endpoint_rejects_unreadable_structure(client):
    ok = client.post("/api/chemistry/conformer", json={"smiles": "OO"})
    assert ok.status_code == 200 and len(ok.json()["atoms"]) == 4
    bad = client.post("/api/chemistry/conformer", json={"smiles": "C1CC"})
    assert bad.status_code == 422


def test_endpoint_requires_session():
    anonymous = TestClient(app, base_url="http://127.0.0.1")
    assert anonymous.post("/api/chemistry/conformer", json={"smiles": "O"}).status_code == 401
