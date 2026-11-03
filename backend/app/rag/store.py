"""Persistent lexical retrieval with page-level provenance."""

import hashlib
import re
import sqlite3
from pathlib import Path
from typing import Any

STOP = set(
    "apa apakah yang dan atau di ke dari dengan untuk ini itu pada dalam sebagai "
    "adalah saya kita mengapa bagaimana berapa "
    "the a an is of for to and in what how why bisa tentang jelaskan".split()
)


def normalize(text: str) -> str:
    return text.translate(str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789"))


def chunks(text: str, size: int = 300, overlap: int = 45) -> list[str]:
    words = text.split()
    return [" ".join(words[i : i + size]) for i in range(0, len(words), size - overlap)]


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, source_ref TEXT NOT NULL,
                    permission TEXT NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY, document_id TEXT NOT NULL,
                    page INTEGER NOT NULL, text TEXT NOT NULL
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(
                    chunk_id UNINDEXED, text, tokenize='unicode61'
                );
            """)

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def add(self, title: str, source_ref: str, pages: list[str]) -> dict[str, Any]:
        digest = hashlib.sha256((title + source_ref + "\n".join(pages)).encode()).hexdigest()[:24]
        records = [
            (number, part)
            for number, page in enumerate(pages, 1)
            for part in chunks(page)
            if len(part.strip()) >= 20
        ]
        if not records:
            raise ValueError(
                "Dokumen tidak memiliki teks yang bisa diindeks. PDF pindai perlu OCR."
            )
        with self.connect() as db:
            exists = db.execute("SELECT id FROM documents WHERE id=?", (digest,)).fetchone()
            if exists:
                return {"id": digest, "title": title, "chunks": len(records), "duplicate": True}
            count = db.execute("SELECT count(*) FROM documents").fetchone()[0]
            if count >= 100:
                raise ValueError("Batas indeks lokal 100 dokumen tercapai.")
            db.execute(
                "INSERT INTO documents(id,title,source_ref,permission) VALUES(?,?,?,?)",
                (digest, title, source_ref, "user-authorized-local-index"),
            )
            for index, (page, text) in enumerate(records):
                chunk_id = f"{digest}-{index}"
                db.execute("INSERT INTO chunks VALUES(?,?,?,?)", (chunk_id, digest, page, text))
                db.execute("INSERT INTO search VALUES(?,?)", (chunk_id, normalize(text)))
        return {"id": digest, "title": title, "chunks": len(records), "duplicate": False}

    def documents(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("""SELECT d.*, count(c.id) AS chunks FROM documents d
                LEFT JOIN chunks c ON c.document_id=d.id GROUP BY d.id ORDER BY d.created DESC""")
            return [dict(row) for row in rows]

    def delete(self, document_id: str) -> bool:
        with self.connect() as db:
            db.execute(
                "DELETE FROM search WHERE chunk_id IN (SELECT id FROM chunks WHERE document_id=?)",
                (document_id,),
            )
            db.execute("DELETE FROM chunks WHERE document_id=?", (document_id,))
            return db.execute("DELETE FROM documents WHERE id=?", (document_id,)).rowcount > 0

    def search(
        self, question: str, document_ids: list[str], limit: int = 5
    ) -> list[dict[str, Any]]:
        terms = list(
            dict.fromkeys(
                word
                for word in re.findall(r"\w+", normalize(question).lower())
                if word not in STOP and len(word) > 1
            )
        )[:24]
        if not terms:
            return []
        expression = " OR ".join('"' + term.replace('"', "") + '"' for term in terms)
        query = """SELECT c.id,c.document_id,c.page,c.text,d.title,d.source_ref,
                    bm25(search) AS rank FROM search
                    JOIN chunks c ON search.chunk_id=c.id
                    JOIN documents d ON d.id=c.document_id WHERE search MATCH ?"""
        parameters: list[Any] = [expression]
        if document_ids:
            query += " AND c.document_id IN (" + ",".join("?" for _ in document_ids) + ")"
            parameters.extend(document_ids)
        query += " ORDER BY rank, c.id LIMIT ?"
        parameters.append(limit)
        with self.connect() as db:
            return [
                {key: row[key] for key in row.keys() if key != "rank"}
                for row in db.execute(query, parameters)
            ]
