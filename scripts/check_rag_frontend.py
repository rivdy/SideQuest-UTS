"""Exercise local Ollama through the frontend rewrite, not only backend HTTP."""

import json
import time
from pathlib import Path

import httpx
from local_session import authenticate

with httpx.Client(timeout=195, trust_env=False) as client:
    authenticate(client, "http://127.0.0.1:3000")
    root = "http://127.0.0.1:3000/api/rag"
    response = client.get(root + "/documents")
    response.raise_for_status()
    doc = next(d for d in response.json() if d["source_ref"] == "EVONIK-H2O2-STABILITY")
    started = time.monotonic()
    response = client.post(
        root + "/ask",
        json={
            "question": "Faktor apa yang memengaruhi stabilitas H2O2 menurut catatan Evonik "
            "dan apa batas penerapannya?",
            "document_ids": [doc["id"]],
        },
    )
    response.raise_for_status()
    result = response.json()
    elapsed = round(time.monotonic() - started, 1)
    assert result["mode"] == "generated" and result["claims"], result["mode"]
    sources = {source["id"]: source for source in result["sources"]}
    assert sources and all(
        s["source_ref"] == "EVONIK-H2O2-STABILITY" for s in sources.values()
    )
    for claim in result["claims"]:
        for citation in claim["citations"]:
            assert citation["source_id"] in sources
            assert " ".join(citation["quote"].split()) in " ".join(
                sources[citation["source_id"]]["text"].split()
            )
    unknown = client.post(
        root + "/ask", json={"question": "quasarxyz astronomiunknown"}
    )
    unknown.raise_for_status()
    assert unknown.json()["mode"] == "no_evidence"
    report = {
        "passed": True,
        "model": "qwen3:4b",
        "via": "frontend:3000",
        "mode": result["mode"],
        "elapsed_seconds": elapsed,
        "source_filter_passed": True,
        "unknown_question_abstained": True,
    }
    target = Path("qa/ollama-local-integration.json")
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    print(json.dumps(result["claims"], ensure_ascii=True))
