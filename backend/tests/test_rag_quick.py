"""Quick RAG mode: instant verbatim excerpts, never the language model."""

from pathlib import Path

import pytest
from conftest import sign_in
from fastapi.testclient import TestClient

from app.main import app
from app.rag import api, service
from app.rag.service import excerpts

TEXT = (
    "Dokumen ini membahas formula disinfektan. "
    "Retensi H₂O₂ minimal 90 persen pada 54 °C selama 14 hari menjadi kriteria proposal. "
    "Aroma berfungsi sebagai penanda bahwa ruangan sudah disemprot. "
    "Bagian ini tidak terkait dengan pertanyaan."
)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("BAYLAB_RAG_DB", str(tmp_path / "quick.sqlite3"))
    api.get_store.cache_clear()
    api.recent.clear()
    client = TestClient(app, base_url="http://127.0.0.1")
    sign_in(client)
    response = client.post(
        "/api/rag/documents",
        data={"title": "Proposal uji", "source_ref": "TEST-QUICK", "authorized": "true"},
        files={"file": ("sample.txt", TEXT.encode(), "text/plain")},
    )
    assert response.status_code == 201
    return client


def test_quick_mode_answers_without_the_model(client, monkeypatch):
    def must_not_run(*args, **kwargs):
        raise AssertionError("mode cepat tidak boleh memanggil model")

    monkeypatch.setattr(service.LocalModelClient, "post", must_not_run)
    body = client.post(
        "/api/rag/ask", json={"question": "Berapa retensi H2O2 pada 54 °C?", "mode": "cepat"}
    ).json()
    assert body["mode"] == "extractive"
    assert body["claims"] == []
    top = body["excerpts"][0]
    assert top["quote"].startswith("Retensi H₂O₂ minimal 90 persen")
    assert top["source_ref"] == "TEST-QUICK"
    # Every excerpt is a verbatim piece of the indexed text.
    assert all(e["quote"] in " ".join(TEXT.split()) for e in body["excerpts"])


def test_quick_mode_without_matching_source(client):
    body = client.post(
        "/api/rag/ask", json={"question": "Jelaskan astronomi quasar", "mode": "cepat"}
    ).json()
    assert body["mode"] == "no_evidence"
    assert body["excerpts"] == []


def test_unknown_mode_is_rejected(client):
    response = client.post("/api/rag/ask", json={"question": "retensi", "mode": "cloud"})
    assert response.status_code == 422


def test_long_sentences_are_cut_at_a_word_and_flagged():
    long_sentence = "retensi " + "kata " * 200 + "akhir."
    source = {"id": "s1", "title": "T", "page": 1, "source_ref": "R", "text": long_sentence}
    chosen = excerpts("retensi", [source], max_chars=60)
    assert chosen[0]["truncated"] is True
    assert len(chosen[0]["quote"]) <= 60
    assert long_sentence.startswith(chosen[0]["quote"])
