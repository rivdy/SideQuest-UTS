"""Composition screening: per-component detection, no risk verdict, bounded input."""

import pytest
from conftest import sign_in
from fastapi.testclient import TestClient

from app.main import app
from app.rag.api import recent

URL = "/api/chemistry/screen-batch"


@pytest.fixture
def client():
    recent.clear()
    client = TestClient(app, base_url="http://127.0.0.1")
    sign_in(client)
    return client


def test_each_component_is_screened_and_invalid_ones_are_reported(client):
    response = client.post(
        URL,
        json={
            "items": [
                {"label": "Citral", "smiles": "CC(=CCC/C(=C/C=O)/C)C"},
                {"label": "Dimetol", "smiles": "CC(C)CCCC(C)(C)O"},
                {"label": "Rusak", "smiles": "C1CC"},
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    citral, dimetol, broken = body["items"]
    assert {m["id"] for m in citral["matches"]} == {"DRAFT-ALKENE", "DRAFT-ALDEHYDE"}
    assert {m["id"] for m in dimetol["matches"]} == {"DRAFT-ALCOHOL"}
    assert broken["ok"] is False and broken["error"]
    assert body["components_with_match"]["DRAFT-ALDEHYDE"] == 1
    assert body["risk_status"] == "not_assessed"


def test_batch_size_and_extra_fields_are_limited(client):
    item = {"label": "x", "smiles": "CCO"}
    assert client.post(URL, json={"items": []}).status_code == 422
    assert client.post(URL, json={"items": [item] * 31}).status_code == 422
    assert client.post(URL, json={"items": [item | {"risk": "low"}]}).status_code == 422


def test_batch_endpoint_rejects_foreign_origin(client):
    response = client.post(
        URL,
        json={"items": [{"label": "x", "smiles": "CCO"}]},
        headers={"Origin": "https://evil.test"},
    )
    assert response.status_code == 403
