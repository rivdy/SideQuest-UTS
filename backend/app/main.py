"""Local RAG and draft RDKit screening. No organization authentication yet."""

from collections.abc import Awaitable, Callable
from typing import Literal

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.chemistry.api import router as chemistry_router
from app.rag.api import router as rag_router

app = FastAPI(title="BAYLab AI API", version="0.1.0")
app.include_router(rag_router)
app.include_router(chemistry_router)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["baylab-api"] = "baylab-api"
    stage: Literal["local-rag"] = "local-rag"


@app.middleware("http")
async def security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    if request.url.path.startswith("/api/") and request.method == "POST":
        try:
            size = int(request.headers.get("content-length", "-1"))
        except ValueError:
            size = -1
        limit = 17 * 1024 * 1024 if request.url.path.startswith("/api/rag") else 32 * 1024
        if size < 0 or size > limit:
            return JSONResponse(
                {"detail": "Content-Length diperlukan dan harus di bawah batas ukuran endpoint."},
                status_code=413,
            )
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health", response_model=HealthResponse, tags=["operations"])
def health() -> HealthResponse:
    """Liveness only: this does not certify database or Redis readiness."""
    return HealthResponse()
