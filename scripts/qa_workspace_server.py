"""Disposable local browser QA server; never seeds the real organization database."""

import json
import os
import secrets
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
qa = root / "qa"
qa.mkdir(exist_ok=True)
private = Path(tempfile.mkdtemp(prefix="workspace-browser-", dir=qa))
os.environ["BAYLAB_DB"] = str(private / "workspace.sqlite3")
os.environ["BAYLAB_DATA_DIR"] = str(private)
os.environ["BAYLAB_RAG_DB"] = str(private / "rag.sqlite3")
os.environ["BAYLAB_ALLOWED_ORIGINS"] = "http://127.0.0.1:8101"

from fastapi.staticfiles import StaticFiles  # noqa: E402
from app.main import app  # noqa: E402
from app.workspace.auth import hasher  # noqa: E402
from app.workspace.db import Organization, User, database  # noqa: E402

password = secrets.token_urlsafe(24)
with database() as db:
    db.add(Organization(id="qa", name="QA - isolated test organization"))
    db.flush()
    db.add(
        User(
            org_id="qa",
            email="qa@example.test",
            name="QA Administrator",
            role="admin",
            password_hash=hasher.hash(password),
        )
    )
(qa / "browser-login.json").write_text(
    json.dumps(
        {"organization": "qa", "email": "qa@example.test", "password": password}
    ),
    encoding="utf-8",
)
app.mount(
    "/",
    StaticFiles(directory=str(root / "frontend" / "public"), html=True),
    name="qa-static",
)
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8101)
