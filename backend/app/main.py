from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
import logging
import os

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import models
from .config import settings
from .db import Base, SessionLocal, engine
from .routers import (auth, jobs, surveys, reports, registry, recovery,
                      active_learning)


# Nothing in this service logged anything, so a failure in production left no
# trace to read. LOG_LEVEL raises or lowers it without a code change.
log = logging.getLogger(__name__)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)

@asynccontextmanager
def _bootstrap_admin() -> None:
    """Create the first admin, once, from the environment.

    Without this a fresh deployment has a database with no accounts and no way
    to make one, since creating an account needs an admin. It runs only when the
    users table is empty, so it cannot overwrite anyone or resurrect a disabled
    account.
    """
    from .models import User
    from .security import hash_password

    email = settings.bootstrap_admin_email.strip().lower()
    password = settings.bootstrap_admin_password
    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            return
        if not email or not password:
            log.warning(
                "no accounts exist and BOOTSTRAP_ADMIN_EMAIL/PASSWORD are unset - "
                "nobody can sign in. Set both and restart.")
            return
        db.add(User(email=email, full_name="Administrator", role="admin",
                    password_hash=hash_password(password)))
        db.commit()
        log.info("created the first admin account: %s", email)
    finally:
        db.close()


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
    _bootstrap_admin()
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
    # No cookie or session is used, so credentials do not need to cross origins.
    # Pairing credentials with wildcard methods and headers is the combination
    # worth avoiding.
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)
app.include_router(auth.router)
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
