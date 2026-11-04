import time

import pytest
from conftest import PASSWORD, sign_in
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.workspace.auth import COOKIE, digest
from app.workspace.db import LoginSession, User, database
from app.workspace.ml import train
from app.workspace.ranking import rank_candidates
from app.workspace.schemas import CRITERIA, Assessment, Weights


def client(org="lkpi", role="admin", email="test@example.test"):
    result = TestClient(app, base_url="http://127.0.0.1")
    sign_in(result, org, role, email)
    return result


def create_form(c, name="Candidate", origin="real", fraction=1):
    r = c.post(
        "/api/workspace/formulations",
        json={
            "name": name,
            "data_origin": origin,
            "ingredients": [
                {"name": "Fragrance", "role": "fragrance", "percent": fraction},
                {"name": "Water", "role": "water", "percent": 100 - fraction},
            ],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def trial(form, origin="real", batch="B01"):
    return {
        "formulation_id": form["id"],
        "batch_id": batch,
        "protocol": "LAB-TEST",
        "source_ref": "Isolated test fixture",
        "measured_on": "2026-11-04",
        "initial_h2o2": 3,
        "final_h2o2": 2.7,
        "ph": 4,
        "temperature_c": 30,
        "duration_days": 14,
        "homogeneous": False,
        "data_origin": origin,
        "confirmed_actual": origin == "real",
    }


def test_private_endpoints_require_session():
    c = TestClient(app, base_url="http://127.0.0.1")
    for path in [
        "/api/workspace/formulations",
        "/api/rag/documents",
        "/api/chemistry/rules",
        "/api/auth/session",
    ]:
        assert c.get(path).status_code == 401
    assert c.post("/api/workspace/rank", json={}).status_code == 401


def test_cookie_csrf_hash_and_logout():
    c = TestClient(app, base_url="http://127.0.0.1")
    login = sign_in(c)
    cookie = login.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie
    assert "password" not in login.text
    with database() as db:
        user = db.scalar(select(User))
        assert user.password_hash.startswith("$argon2id$")
        assert PASSWORD not in user.password_hash
        assert db.get(LoginSession, digest(c.cookies[COOKIE]))
    assert c.post("/api/auth/logout", json={}, headers={"X-CSRF-Token": "wrong"}).status_code == 403
    assert c.post("/api/auth/logout", json={}).status_code == 200
    assert c.get("/api/auth/session").status_code == 401


def test_expired_session_and_cookie_security(monkeypatch):
    monkeypatch.setenv("BAYLAB_SECURE_COOKIES", "true")
    c = TestClient(app, base_url="https://127.0.0.1")
    response = sign_in(c)
    assert "Secure" in response.headers["set-cookie"]
    with database() as db:
        session = db.get(LoginSession, digest(c.cookies[COOKIE]))
        session.expires = time.time() - 1
    assert c.get("/api/auth/session").status_code == 401


def test_role_and_tenant_isolation():
    admin, other = client(), client("other")
    viewer = client(role="viewer", email="reader@example.test")
    form = create_form(admin)
    assert other.get("/api/workspace/formulations").json() == []
    assert (
        other.put(
            "/api/workspace/formulations/" + form["id"] + "/assessment",
            json={"comparison_protocol": "LAB"},
        ).status_code
        == 404
    )
    assert (
        viewer.post(
            "/api/workspace/formulations",
            json={
                "name": "Candidate",
                "ingredients": [{"name": "Water", "role": "water", "percent": 100}],
            },
        ).status_code
        == 403
    )
    assert viewer.get("/api/auth/users").status_code == 403
    assert (
        viewer.post(
            "/api/workspace/model/train", json={"target": "solubility", "algorithm": "catboost"}
        ).status_code
        == 403
    )
    assert (
        admin.post(
            "/api/auth/users",
            json={
                "organization": "other",
                "email": "new@example.test",
                "name": "New User",
                "role": "admin",
                "password": PASSWORD,
            },
        ).status_code
        == 403
    )


def test_rag_organization_isolation():
    a, b = client(), client("other")
    upload = a.post(
        "/api/rag/documents",
        data={"title": "Private test", "source_ref": "PRIVATE", "authorized": "true"},
        files={
            "file": ("p.txt", b"Private original document for tenant isolation test.", "text/plain")
        },
    )
    assert upload.status_code == 201
    doc = upload.json()["id"]
    assert b.get("/api/rag/documents").json() == []
    assert b.delete("/api/rag/documents/" + doc).status_code == 404
    assert (
        b.post(
            "/api/rag/ask", json={"question": "private document", "document_ids": [doc]}
        ).status_code
        == 422
    )


def test_password_change_revokes_sessions_and_field_tampering():
    c = client()
    assert (
        c.post(
            "/api/auth/login",
            json={
                "organization": "lkpi",
                "email": "test@example.test",
                "password": PASSWORD,
                "role": "admin",
            },
        ).status_code
        == 422
    )
    assert (
        c.post(
            "/api/auth/password",
            json={"old_password": PASSWORD, "new_password": "A-new-long-test-password"},
        ).status_code
        == 200
    )
    assert c.get("/api/auth/session").status_code == 401


def test_login_rate_limit_and_origin():
    c = TestClient(app, base_url="http://127.0.0.1")
    data = {"organization": "lkpi", "email": "unknown@example.test", "password": "wrong"}
    assert (
        c.post("/api/auth/login", json=data, headers={"Origin": "https://evil.test"}).status_code
        == 403
    )
    for _ in range(10):
        assert c.post("/api/auth/login", json=data).status_code == 401
    assert c.post("/api/auth/login", json=data).status_code == 429


def assessment(score):
    return Assessment(
        comparison_protocol="SAME-RUBRIC",
        **{
            k: {
                "score": score,
                "source_ref": "TEST source",
                "rationale": "Normalized test criterion",
            }
            for k in CRITERIA
        },
    ).model_dump()


def test_ranking_recomputes_and_abstains():
    rows = [
        {"id": "a", "name": "A", "data_origin": "real", "assessment": assessment(40)},
        {"id": "b", "name": "B", "data_origin": "real", "assessment": assessment(60)},
    ]
    result = rank_candidates(rows, Weights(), "SAME-RUBRIC")
    assert result["ranked"][0]["id"] == "b" and result["ranked"][0]["score"] == 60
    rows[0]["assessment"]["aroma"]["score"] = 100
    result = rank_candidates(
        rows,
        Weights(oxidation=0, solubility=0, compatibility=0, temperature=0, aroma=100),
        "SAME-RUBRIC",
    )
    assert result["ranked"][0]["id"] == "a"
    rows[0]["assessment"]["aroma"] = None
    result = rank_candidates(rows, Weights(), "SAME-RUBRIC")
    assert result["incomplete"][0]["missing"] == ["aroma"]
    assert rank_candidates(rows, Weights(), "OTHER")["ranked"] == []


def test_formulation_and_experiment_validation():
    c = client()
    assert (
        c.post(
            "/api/workspace/formulations",
            json={
                "name": "Bad sum",
                "ingredients": [{"name": "Water", "role": "water", "percent": 90}],
            },
        ).status_code
        == 422
    )
    f = create_form(c)
    data = trial(f)
    data["confirmed_actual"] = False
    assert c.post("/api/workspace/experiments", json=data).status_code == 422
    data["confirmed_actual"] = True
    r = c.post("/api/workspace/experiments", json=data)
    assert r.status_code == 201 and r.json()["retention_pct"] == 90
    assert c.post("/api/workspace/experiments", json=data).status_code == 409
    assert client("other").delete("/api/workspace/experiments/" + r.json()["id"]).status_code == 404
    assert c.delete("/api/workspace/experiments/" + r.json()["id"]).status_code == 200
    assert c.get("/api/workspace/experiments").json() == []


def test_synthetic_trials_are_not_trainable():
    c = client()
    f = create_form(c, origin="synthetic")
    assert c.post("/api/workspace/experiments", json=trial(f)).status_code == 422
    assert (
        c.post("/api/workspace/experiments", json=trial(f, origin="synthetic")).status_code == 201
    )
    status = c.get("/api/workspace/model/status?target=h2o2_retention&protocol=LAB-TEST").json()
    assert status["eligible_rows"] == 0 and not status["can_train"]
    assert (
        c.post(
            "/api/workspace/model/train",
            json={"algorithm": "catboost", "target": "h2o2_retention", "protocol": "LAB-TEST"},
        ).status_code
        == 422
    )


@pytest.mark.parametrize("algorithm", ["catboost", "xgboost"])
def test_real_training_code_uses_disjoint_groups_and_saves_model(algorithm, tmp_path):
    # Generated fixtures test the pipeline only, never inserted into application data.
    rows = [
        {
            "x": [i, j],
            "y": i * 2 + j,
            "group": str(i),
            "label": str((i, j)),
            "identity": str((i, j)),
        }
        for i in range(8)
        for j in range(4)
    ]
    data = {
        "rows": rows,
        "excluded": 0,
        "unit": "test",
        "origin": "test fixture",
        "scope": "test only",
        "provenance": "test",
        "sha256": "fixture",
        "features": ["a", "b"],
        "grouping": "fixture group",
    }
    report = train(data, algorithm, tmp_path / algorithm)
    assert report["group_overlap"] == 0
    assert report["train_rows"] + report["test_rows"] == 32
    assert report["status"] == "evaluation_only"
    assert len(report["points"]) == report["test_rows"]
    assert report["metrics"]["rmse"] >= 0
    assert list((tmp_path / algorithm).iterdir())
