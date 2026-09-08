from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import models
from .config import settings
from .db import Base, engine
from .routers import jobs, surveys, reports, registry, recovery, active_learning


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.ensure_directories()
    # Retry DB connection — PostGIS runs extension setup after pg_isready
    # returns healthy, so there's a brief window where connections can fail.
    for attempt in range(10):
        try:
            Base.metadata.create_all(bind=engine)
            break
        except Exception as exc:
            if attempt == 9:
                raise
            wait = 2 ** attempt  # 1s, 2s, 4s, 8s…
            print(f"DB not ready (attempt {attempt + 1}/10): {exc}. Retrying in {wait}s…")
            time.sleep(wait)
    yield


app = FastAPI(
    title="Marine Debris Detection API",
    version="0.1.0",
    description="Backend foundation for side-scan sonar debris detection.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(surveys.router)
app.include_router(jobs.router)
app.include_router(reports.router)
app.include_router(registry.router)
app.include_router(recovery.router)
app.include_router(active_learning.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exception: HTTPException) -> JSONResponse:
    detail = exception.detail
    message = detail if isinstance(detail, str) else "Request failed"
    content: dict[str, object] = {"message": message}
    if not isinstance(detail, str):
        content["details"] = detail
    return JSONResponse(status_code=exception.status_code, content=content)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _: Request, exception: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"message": "Request validation failed", "details": exception.errors()},
    )


@app.get("/api/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}
