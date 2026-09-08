from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SurveyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=5000)


class SurveyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    uploaded_by: str | None
    notes: str | None
    created_at: datetime


class UploadResponse(BaseModel):
    file_id: int
    job_id: int
    status: Literal["queued", "processing", "done", "failed"]


class JobRead(BaseModel):
    id: int
    file_id: int
    status: Literal["queued", "processing", "done", "failed"]
    progress: int
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None


class DetectionRead(BaseModel):
    id: int
    class_name: str = Field(serialization_alias="class", validation_alias="class")
    confidence: float
    bbox: list[float]
    lat: float | None
    lon: float | None
    size_m: float | None
    frame_index: int | None
    created_at: datetime


class DetectionPage(BaseModel):
    items: list[DetectionRead]
    total: int
    limit: int
    offset: int


class JobSummary(BaseModel):
    job_id: int
    total: int
    by_class: dict[str, int]
    area_covered: float
    processing_ms: int | None

