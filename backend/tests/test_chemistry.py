import httpx
import pytest
from conftest import sign_in
from fastapi.testclient import TestClient

from app.chemistry.engine import screen
from app.chemistry.pubchem import PubChemClient
from app.main import app
from app.rag.api import recent


@pytest.fixture
def client():
    recent.clear()
    client = TestClient(app, base_url="http://127.0.0.1")
    sign_in(client)
    return client


def ids(result):
    return {m.rule.id for m in result.matches}


def test_actual_structure_changes_features():
    assert ids(screen("CCO")) == {"DRAFT-ALCOHOL"}
    assert ids(screen("CC=O")) == {"DRAFT-ALDEHYDE"}
    assert ids(screen("CC(=O)OC")) == {"DRAFT-ESTER"}
    assert ids(screen("Oc1ccccc1")) == {"DRAFT-PHENOL"}
    assert ids(screen("OO")) == {"DRAFT-PEROXIDE"}
    assert ids(screen("C=CC")) == {"DRAFT-ALKENE"}


def test_aromatic_bonds_not_reported_as_alkenes():
    result = screen("c1ccccc1")
    assert result.matches == []
    assert result.risk_status == "not_assessed"
    assert result.validated_rule_count == 0


def test_multiple_matches_and_reproducibility():
    result = screen("C=CC=C")
    assert result.matches[0].count == 2
    assert result.matches[0].atom_matches == [[0, 1], [2, 3]]
    assert result.canonical_smiles == screen("C=CC=C").canonical_smiles
    assert result.depiction.startswith("data:image/svg+xml;base64,")
    assert result.ruleset_version == "literature-draft-2"


@pytest.mark.parametrize(
    "value", ["", "not-smiles", "CCO name", "C(C)(C)(C)(C)C", "CC.O", "*CC", "C" * 201]
)
def test_rejects_unsupported_structure(value):
    with pytest.raises(ValueError):
        screen(value)


def test_api_schema_and_no_client_validation_override(client):
    response = client.post("/api/chemistry/screen", json={"smiles": "CCO"})
    assert response.status_code == 200
    assert response.json()["molecular_formula"] == "C2H6O"
    assert response.json()["matches"][0]["rule"]["status"] == "draft"
    assert (
        client.post(
            "/api/chemistry/screen", json={"smiles": "CCO", "status": "validated"}
        ).status_code
        == 422
    )
    assert client.post("/api/chemistry/screen", json={"smiles": "C" * 33000}).status_code == 413
    assert (
        client.post(
            "/api/chemistry/screen", json={"smiles": "CCO"}, headers={"Origin": "https://evil.test"}
        ).status_code
        == 403
    )
    assert client.get("/api/chemistry/rules").json()["validated_rules"] == 0


def test_pubchem_provenance_and_fixed_host(client, monkeypatch):
    def respond(self, method, url, **kwargs):
        assert url.startswith("https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/")
        assert kwargs["data"] == {"name": "ethanol"}
        return httpx.Response(
            200,
            request=httpx.Request(method, url),
            json={
                "PropertyTable": {
                    "Properties": [
                        {
                            "CID": 702,
                            "Title": "Ethanol",
                            "MolecularFormula": "C2H6O",
                            "SMILES": "CCO",
                        }
                    ]
                }
            },
        )

    monkeypatch.setattr(PubChemClient, "request", respond)
    response = client.post(
        "/api/chemistry/pubchem", json={"query": "ethanol", "consent_external_lookup": True}
    )
    assert response.status_code == 200
    assert response.json()["source_url"] == "https://pubchem.ncbi.nlm.nih.gov/compound/702"
    assert response.json()["retrieved_at"]
    assert client.post("/api/chemistry/pubchem", json={"query": "ethanol"}).status_code == 422
    assert (
        client.post(
            "/api/chemistry/pubchem",
            json={"query": "../../", "namespace": "cid", "consent_external_lookup": True},
        ).status_code
        == 422
    )


@pytest.mark.parametrize("status, expected", [(404, 404), (429, 503), (503, 503), (500, 502)])
def test_pubchem_errors_do_not_become_fake_results(client, monkeypatch, status, expected):
    monkeypatch.setattr(
        PubChemClient,
        "request",
        lambda self, method, url, **kw: httpx.Response(status, request=httpx.Request(method, url)),
    )
    response = client.post(
        "/api/chemistry/pubchem",
        json={"query": "702", "namespace": "cid", "consent_external_lookup": True},
    )
    assert response.status_code == expected
    assert "smiles" not in response.json()


def test_pubchem_timeout(client, monkeypatch):
    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("timeout")

    monkeypatch.setattr(PubChemClient, "request", timeout)
    assert (
        client.post(
            "/api/chemistry/pubchem",
            json={"query": "702", "namespace": "cid", "consent_external_lookup": True},
        ).status_code
        == 504
    )
