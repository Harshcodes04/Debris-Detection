from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


def utc_now() -> datetime:
    return datetime.utcnow()


# Ordered least to most privileged; a check is "at least this role".
ROLES = ("viewer", "analyst", "admin")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True,
                                       nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Argon2id output, never the password itself.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now,
                                                 nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Survey(Base):
    __tablename__ = "surveys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    uploaded_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    files: Mapped[list[SurveyFile]] = relationship(
        back_populates="survey", cascade="all, delete-orphan"
    )


class SurveyFile(Base):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    survey_id: Mapped[int] = mapped_column(ForeignKey("surveys.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    survey: Mapped[Survey] = relationship(back_populates="files")
    jobs: Mapped[list[Job]] = relationship(
        back_populates="file", cascade="all, delete-orphan"
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    overlay_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    processing_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    file: Mapped[SurveyFile] = relationship(back_populates="jobs")
    detections: Mapped[list[Detection]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    class_name: Mapped[str] = mapped_column("class", String(100), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    width: Mapped[float] = mapped_column("w", Float, nullable=False)
    height: Mapped[float] = mapped_column("h", Float, nullable=False)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    size_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    frame_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Enrichment context
    depth_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    biodiversity_species: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nearest_port_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    # Risk
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_band: Mapped[str | None] = mapped_column(String(20), nullable=True)
    risk_reasons: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON serialized list
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    job: Mapped[Job] = relationship(back_populates="detections")


Index(
    "ix_detections_job_class_confidence",
    Detection.job_id,
    Detection.class_name,
    Detection.confidence,
)


class RegistryEntry(Base):
    __tablename__ = "registry_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hazard_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    class_name: Mapped[str] = mapped_column("class", String(100), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    
    first_seen: Mapped[str] = mapped_column(String(30), nullable=False)
    last_seen: Mapped[str] = mapped_column(String(30), nullable=False)
    times_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    consecutive_misses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="present")
    best_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    surveys: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON serialized list of survey names
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


