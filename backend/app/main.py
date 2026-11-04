"""Local organization workspace, structure screening and document RAG."""

import secrets
from collections.abc import Awaitable, Callable
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.chemistry.api import router as chemistry_router
from app.rag.api import router as rag_router
from app.workspace import auth
from app.workspace.api import router as workspace_router
from app.workspace.ml import router as model_router

app = FastAPI(title="BAYLab AI API", version="0.2.0")
for router in (auth.router, workspace_router, model_router, rag_router, chemistry_router):
    app.include_router(router)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["baylab-api"] = "baylab-api"
    stage: Literal["local-rag"] = "local-rag"


@app.middleware("http")
async def security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    token = None
    try:
        if request.url.path.startswith("/api/"):
            if not auth.permitted_origin(request):
                raise HTTPException(403, "Origin tidak diizinkan.")
            if request.method in {"POST", "PUT", "PATCH"}:
                try:
                    size = int(request.headers.get("content-length", "-1"))
                except ValueError:
                    size = -1
                limit = 17 * 1024 * 1024 if request.url.path.startswith("/api/rag") else 32 * 1024
                if size < 0 or size > limit:
                    raise HTTPException(
                        413, "Content-Length diperlukan dan melebihi batas endpoint."
                    )
            if request.url.path != "/api/auth/login":
                user, csrf = auth.identity(request)
                request.state.user, request.state.csrf = user, csrf
                token = auth.current_org.set(user["org_id"])
                if request.method not in {"GET", "HEAD", "OPTIONS"}:
                    supplied = request.headers.get("X-CSRF-Token", "")
                    if not secrets.compare_digest(csrf, supplied):
                        raise HTTPException(403, "Token CSRF tidak valid. Muat ulang halaman.")
                if request.url.path.startswith("/api/rag/documents") and request.method not in {
                    "GET",
                    "HEAD",
                }:
                    auth.require_editor(request)
        response = await call_next(request)
    except HTTPException as exc:
        response = JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    finally:
        if token is not None:
            auth.current_org.reset(token)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health", response_model=HealthResponse, tags=["operations"])
def health() -> HealthResponse:
    """Liveness only; not a claim about database or model readiness."""
    return HealthResponse()
