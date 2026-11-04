"""Verify one real local-model response after its download finishes."""

import argparse
import json
import time
from pathlib import Path

import httpx
from local_session import authenticate

parser = argparse.ArgumentParser()
parser.add_argument("--wait", action="store_true")
args = parser.parse_args()
deadline = time.monotonic() + (3600 if args.wait else 0)
report_path = Path("qa/rag-live.json")
report_path.parent.mkdir(exist_ok=True)
with httpx.Client(timeout=200, trust_env=False) as client:
    authenticate(client, "http://127.0.0.1:8000")
    while True:
        status = client.get("http://127.0.0.1:8000/api/rag/status").json()
        if status["generation"]["ready"]:
            break
        if not args.wait or time.monotonic() >= deadline:
            report_path.write_text(
                json.dumps({"passed": False, "reason": "model_not_ready"})
            )
            raise SystemExit("Model is not ready; retrieval is available separately.")
        time.sleep(15)
    response = client.post(
        "http://127.0.0.1:8000/api/rag/ask",
        json={"question": "Apa tujuan pengembangan BAYLab AI dalam proposal?"},
    )
    response.raise_for_status()
    result = response.json()
    sources = {source["id"]: source["text"] for source in result["sources"]}
    passed = result["mode"] == "generated" and bool(result["claims"])
    for claim in result["claims"]:
        for citation in claim["citations"]:
            quote = " ".join(citation["quote"].split())
            source = " ".join(sources.get(citation["source_id"], "").split())
            passed = passed and quote in source
    report = {
        "passed": passed,
        "mode": result["mode"],
        "claims": len(result["claims"]),
        "sources": len(sources),
        "model": status["generation"]["model"],
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    if not passed:
        raise SystemExit(1)
