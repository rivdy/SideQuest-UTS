"""Local-only document ingestion and RAG HTTP endpoints."""

import io
import os
import time
from collections import defaultdict, deque
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlparse

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from pypdf import PdfReader
from starlette.concurrency import run_in_threadpool

from app.workspace.auth import current_org

from .service import answer, model_status
from .store import Store

router = APIRouter(prefix="/api/rag", tags=["local-rag"])
MAX_FILE = 16 * 1024 * 1024
recent: dict[str, deque[float]] = defaultdict(deque)


@lru_cache
def _store_for(path: str) -> Store:
    return Store(Path(path))


def get_store() -> Store:
    default = Path(__file__).resolve().parents[2] / "data" / "rag.sqlite3"
    path = Path(os.getenv("BAYLAB_RAG_DB", str(default)))
    org = current_org.get()
    if org != "lkpi":
        path = path.with_name(path.stem + "." + org + path.suffix)
    return _store_for(str(path))


get_store.cache_clear = _store_for.cache_clear


def guard(request: Request, category: str, limit: int) -> None:
    host = request.url.hostname
    origin = request.headers.get("origin")
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise HTTPException(403, "RAG ini hanya untuk penggunaan localhost.")
    if origin and urlparse(origin).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise HTTPException(403, "Origin tidak diizinkan.")
    now = time.monotonic()
    bucket = recent[current_org.get() + ":" + category]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(429, "Terlalu banyak permintaan. Coba lagi satu menit lagi.")
    bucket.append(now)


def extract(filename: str, content: bytes) -> list[str]:
    extension = Path(filename).suffix.lower()
    if len(content) > MAX_FILE:
        raise ValueError("Ukuran maksimum 16 MB.")
    if extension == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise ValueError("Signature PDF tidak valid.")
        try:
            reader = PdfReader(io.BytesIO(content))
            if reader.is_encrypted or len(reader.pages) > 80:
                raise ValueError("PDF harus tanpa password dan maksimal 80 halaman.")
            pages = []
            length = 0
            for page in reader.pages:
                text = page.extract_text() or ""
                length += len(text)
                if length > 300_000:
                    raise ValueError("Teks dokumen melebihi 300.000 karakter.")
                pages.append(text)
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("PDF tidak dapat dibaca.") from exc
    elif extension in {".txt", ".md"}:
        try:
            pages = [content.decode("utf-8-sig")]
        except UnicodeDecodeError as exc:
            raise ValueError("Gunakan teks UTF-8.") from exc
        if "\x00" in pages[0]:
            raise ValueError("Berkas biner tidak diizinkan.")
    else:
        raise ValueError("Hanya PDF, TXT, atau Markdown yang didukung.")
    if sum(map(len, pages)) > 300_000:
        raise ValueError("Teks dokumen melebihi 300.000 karakter.")
    return pages


class Query(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=3, max_length=1600)
    document_ids: list[Annotated[str, Field(pattern=r"^[a-f0-9]{24}$")]] = Field(
        default_factory=list, max_length=20
    )


@router.get("/status")
def status(request: Request) -> dict[str, Any]:
    guard(request, "read", 120)
    return {
        "retrieval": "SQLite FTS5 / BM25",
        "local_only": True,
        "documents": len(get_store().documents()),
        "generation": model_status(),
    }


@router.get("/documents")
def documents(request: Request) -> list[dict[str, Any]]:
    guard(request, "read", 120)
    return get_store().documents()


@router.post("/documents", status_code=201)
async def upload(
    request: Request,
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form(min_length=1, max_length=180)],
    source_ref: Annotated[str, Form(min_length=1, max_length=240)],
    authorized: Annotated[bool, Form()],
) -> dict[str, Any]:
    guard(request, "upload", 10)
    if not authorized:
        raise HTTPException(422, "Konfirmasi hak penggunaan teks diperlukan.")
    if not title.strip() or not source_ref.strip():
        raise HTTPException(422, "Judul dan identitas sumber wajib diisi.")
    try:
        content = await file.read(MAX_FILE + 1)
        pages = await run_in_threadpool(extract, file.filename or "", content)
        return await run_in_threadpool(get_store().add, title.strip(), source_ref.strip(), pages)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        await file.close()


@router.delete("/documents/{document_id}")
def delete(document_id: str, request: Request) -> dict[str, bool]:
    guard(request, "delete", 20)
    if not get_store().delete(document_id):
        raise HTTPException(404, "Dokumen tidak ditemukan.")
    return {"deleted": True}


@router.post("/ask")
def ask(query: Query, request: Request) -> dict[str, Any]:
    guard(request, "ask", 20)
    store = get_store()
    existing = {document["id"] for document in store.documents()}
    if set(query.document_ids) - existing:
        raise HTTPException(422, "Dokumen pilihan tidak tersedia. Muat ulang daftar sumber.")
    sources = store.search(query.question, query.document_ids)
    return answer(query.question, sources)
