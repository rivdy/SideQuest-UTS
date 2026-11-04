"""Isolate every test from the user's accounts, documents and models."""

from pathlib import Path

import pytest
from sqlalchemy import select

from app.rag.api import get_store
from app.workspace import auth
from app.workspace.db import Organization, User, database, engine

PASSWORD = "Only-for-isolated-tests-1937"


@pytest.fixture(autouse=True)
def isolated_workspace(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("BAYLAB_DB", str(tmp_path / "workspace.sqlite3"))
    monkeypatch.setenv("BAYLAB_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.setenv("BAYLAB_RAG_DB", str(tmp_path / "rag.sqlite3"))
    engine.cache_clear()
    get_store.cache_clear()
    token = auth.current_org.set("lkpi")
    yield
    if engine.cache_info().currsize:
        engine().dispose()
    engine.cache_clear()
    get_store.cache_clear()
    auth.current_org.reset(token)


def sign_in(client, org="lkpi", role="admin", email="test@example.test"):
    with database() as db:
        if not db.get(Organization, org):
            db.add(Organization(id=org, name="Test " + org))
            db.flush()
        user = db.scalar(select(User).where(User.org_id == org, User.email == email))
        if not user:
            db.add(
                User(
                    org_id=org,
                    email=email,
                    name="Test User",
                    role=role,
                    password_hash=auth.hasher.hash(PASSWORD),
                )
            )
    response = client.post(
        "/api/auth/login", json={"organization": org, "email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return response
