import io
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.main import app
from app.rag import api, service
from app.rag.api import extract
from app.rag.service import ModelAnswer, validate_claims
from app.rag.store import Store, chunks


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("BAYLAB_RAG_DB", str(tmp_path / "test.sqlite3"))
    api.get_store.cache_clear()
    api.recent.clear()
    return TestClient(app, base_url="http://127.0.0.1")


def upload(
    client: TestClient,
    text: str = "Target retensi merupakan asumsi proposal, bukan hasil eksperimen.",
) -> httpx.Response:
    return client.post(
        "/api/rag/documents",
        data={"title": "Proposal uji", "source_ref": "TEST-001", "authorized": "true"},
        files={"file": ("sample.txt", text.encode(), "text/plain")},
    )


def test_ingestion_dedup_and_persistence(client: TestClient) -> None:
    first = upload(client)
    assert first.status_code == 201
    assert upload(client).json()["duplicate"] is True
    assert len(api.get_store().documents()) == 1
    reopened = Store(api.get_store().path)
    assert reopened.search("retensi", [])[0]["page"] == 1


def test_filtered_retrieval_and_delete(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite3")
    first = store.add(
        "A", "A", ["Retensi adalah parameter contoh pada proyek A, bukan data nyata."]
    )
    second = store.add(
        "B", "B", ["Retensi adalah parameter contoh pada proyek B, bukan data nyata."]
    )
    assert {r["document_id"] for r in store.search("retensi", [first["id"]])} == {first["id"]}
    assert store.delete(first["id"])
    assert {r["document_id"] for r in store.search("retensi", [])} == {second["id"]}
    assert store.search('" OR * NOT <script>', []) == []


def test_page_provenance(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite3")
    store.add(
        "Example",
        "EXAMPLE",
        [
            "Halaman pertama membahas alur kerja penelitian.",
            "Halaman kedua menjelaskan karakteristik retensi ilustratif.",
        ],
    )
    assert store.search("retensi", [])[0]["page"] == 2


def test_unknown_question_does_not_call_model(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    upload(client)

    def fail(*args: object, **kwargs: object) -> None:
        pytest.fail("Model must not be called without evidence")

    monkeypatch.setattr(service.LocalModelClient, "post", fail)
    result = client.post("/api/rag/ask", json={"question": "Jelaskan astronomi quasar"})
    assert result.json()["mode"] == "no_evidence"
    assert result.json()["sources"] == []


def test_model_offline_returns_evidence(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    upload(client)

    def offline(*args: object, **kwargs: object) -> None:
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(service.LocalModelClient, "post", offline)
    response = client.post("/api/rag/ask", json={"question": "Apa target retensi?"}).json()
    assert response["mode"] == "retrieval_only"
    assert response["claims"] == []
    assert response["sources"][0]["source_ref"] == "TEST-001"


def test_generated_answer_uses_real_citations(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    upload(client)
    source = api.get_store().search("retensi", [])[0]

    def generated(*args: object, **kwargs: object) -> httpx.Response:
        payload = kwargs["json"]
        assert payload["stream"] is False
        assert "untrusted_sources" in payload["messages"][1]["content"]
        result = ModelAnswer(
            claims=[
                {
                    "text": "Target bukan hasil eksperimen.",
                    "citations": [{"source_id": source["id"], "quote": source["text"]}],
                }
            ]
        )
        return httpx.Response(
            200,
            json={"message": {"content": result.model_dump_json()}},
            request=httpx.Request("POST", "http://127.0.0.1:11434/api/chat"),
        )

    monkeypatch.setattr(service.LocalModelClient, "post", generated)
    response = client.post("/api/rag/ask", json={"question": "Apa target retensi?"}).json()
    assert response["mode"] == "generated"
    assert response["claims"][0]["citations"][0]["source_id"] == source["id"]


@pytest.mark.parametrize(
    "source_id,quote",
    [
        ("invented", "Kutipan yang tidak tersedia dalam dokumen."),
        ("real", "Kutipan yang tidak tersedia dalam dokumen."),
    ],
)
def test_fabricated_citations_rejected(source_id: str, quote: str) -> None:
    answer = ModelAnswer(
        claims=[{"text": "Claim", "citations": [{"source_id": source_id, "quote": quote}]}]
    )
    assert (
        validate_claims(answer, [{"id": "real", "text": "Sumber berisi konteks yang berbeda."}])
        == []
    )


def test_exact_quotes_required() -> None:
    answer = ModelAnswer(
        claims=[
            {
                "text": "Parafrase",
                "citations": [
                    {
                        "source_id": "real",
                        "quote": "Data contoh tidak boleh menjadi bukti eksperimen.",
                    }
                ],
            }
        ]
    )
    assert (
        len(
            validate_claims(
                answer,
                [{"id": "real", "text": "Data contoh tidak boleh menjadi bukti eksperimen."}],
            )
        )
        == 1
    )


@pytest.mark.parametrize(
    "name,content",
    [
        ("unsafe.html", b"<script>alert(1)</script>"),
        ("fake.pdf", b"not a PDF"),
        ("binary.txt", b"abc\x00def"),
    ],
)
def test_invalid_files_rejected(name: str, content: bytes) -> None:
    with pytest.raises(ValueError):
        extract(name, content)


def test_large_file_rejected() -> None:
    with pytest.raises(ValueError):
        extract("large.txt", b"x" * (api.MAX_FILE + 1))


def test_blank_pdf_needs_ocr(tmp_path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    stream = io.BytesIO()
    writer.write(stream)
    pages = extract("blank.pdf", stream.getvalue())
    with pytest.raises(ValueError):
        Store(tmp_path / "db.sqlite3").add("Blank", "TEST", pages)


def test_permission_and_origin(client: TestClient) -> None:
    result = client.post(
        "/api/rag/documents",
        data={"title": "X", "source_ref": "X", "authorized": "false"},
        files={"file": ("sample.txt", b"Some legitimate text in a document.")},
    )
    assert result.status_code == 422
    result = client.post(
        "/api/rag/ask",
        json={"question": "Target retensi"},
        headers={"Origin": "https://evil.example"},
    )
    assert result.status_code == 403


def test_query_validation_and_unknown_document(client: TestClient) -> None:
    assert client.post("/api/rag/ask", json={"question": " "}).status_code == 422
    assert (
        client.post("/api/rag/ask", json={"question": "test", "provider": "cloud"}).status_code
        == 422
    )
    assert (
        client.post(
            "/api/rag/ask", json={"question": "test", "document_ids": ["a" * 24]}
        ).status_code
        == 422
    )


def test_chunks_overlap_without_missing_words() -> None:
    result = chunks(" ".join(f"word{i}" for i in range(650)))
    assert "word255" in result[0] and "word255" in result[1]
    assert "word649" in result[-1]


def test_cpu_generation_budget_and_source_scope(monkeypatch):
    sources = [
        {
            "id": f"source-{i}",
            "title": "Test",
            "page": 1,
            "text": "A sufficiently long source passage for testing.",
        }
        for i in range(5)
    ]

    def generated(*args, **kwargs):
        import json

        payload = kwargs["json"]
        context = json.loads(payload["messages"][1]["content"])["untrusted_sources"]
        assert [s["source_id"] for s in context] == ["source-0", "source-1"]
        assert payload["options"]["num_ctx"] == 4096
        assert payload["options"]["num_predict"] == 600
        assert payload["think"] is False
        return httpx.Response(
            200,
            request=httpx.Request("POST", "http://127.0.0.1:11434/api/chat"),
            json={
                "message": {
                    "content": json.dumps(
                        {
                            "claims": [
                                {
                                    "text": "Unseen source must not be cited.",
                                    "citations": [
                                        {"source_id": "source-4", "quote": sources[4]["text"]}
                                    ],
                                }
                            ]
                        }
                    )
                }
            },
        )

    monkeypatch.setattr(service.LocalModelClient, "post", generated)
    result = service.answer("Test source selection", sources)
    assert result["mode"] == "no_supported_answer"
    assert result["claims"] == []
    assert len(result["sources"]) == 5
