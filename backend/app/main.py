from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models
from .config import settings
from .db import Base, engine
from .routers import jobs, surveys


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.ensure_directories()
    Base.metadata.create_all(bind=engine)
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


@app.get("/api/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}

