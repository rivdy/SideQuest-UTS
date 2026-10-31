from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_contract() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok", "service": "baylab-api", "stage": "scaffolding"
    }
    assert response.headers["cache-control"] == "no-store"


def test_security_headers_on_errors() -> None:
    response = client.get("/unknown")
    assert response.status_code == 404
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_health_is_read_only() -> None:
    assert client.post("/health", json={"status": "changed"}).status_code == 405
    assert client.get("/health").json()["status"] == "ok"


def test_no_wildcard_cors() -> None:
    response = client.get("/health", headers={"Origin": "https://untrusted.example"})
    assert "access-control-allow-origin" not in response.headers


def test_openapi_response_schema() -> None:
    schema = client.get("/openapi.json").json()
    assert schema["paths"]["/health"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("/HealthResponse")
