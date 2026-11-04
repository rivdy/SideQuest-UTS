"""Authenticate local checks without logging credentials."""

import json
import os
from pathlib import Path


def authenticate(client, base_url):
    default = (
        Path(__file__).resolve().parents[1] / "backend/data/initial-admin-lkpi.json"
    )
    path = Path(os.environ.get("BAYLAB_CREDENTIALS_FILE", str(default)))
    credentials = json.loads(path.read_text(encoding="utf-8"))
    response = client.post(base_url + "/api/auth/login", json=credentials)
    response.raise_for_status()
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
