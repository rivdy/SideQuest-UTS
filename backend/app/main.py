"""BAYLab service foundation. No chemistry or authentication claims yet."""

from collections.abc import Awaitable, Callable
from typing import Literal

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel

app = FastAPI(title="BAYLab AI API", version="0.1.0")


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["baylab-api"] = "baylab-api"
    stage: Literal["scaffolding"] = "scaffolding"


@app.middleware("http")
async def security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
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
