from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Detection, Job
from ..schemas import DetectionPage, DetectionRead, JobRead, JobSummary


router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def get_job_or_404(job_id: int, db: Session) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def detection_response(detection: Detection) -> DetectionRead:
    return DetectionRead(
        id=detection.id,
        **{
            "class": detection.class_name,
            "confidence": detection.confidence,
            "bbox": [detection.x, detection.y, detection.width, detection.height],
            "lat": detection.lat,
            "lon": detection.lon,
            "size_m": detection.size_m,
            "frame_index": detection.frame_index,
            "created_at": detection.created_at,
        },
    )


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: int, db: Session = Depends(get_db)) -> Job:
    return get_job_or_404(job_id, db)


@router.get("/{job_id}/detections", response_model=DetectionPage)
def list_detections(
    job_id: int,
    class_name: str | None = Query(default=None, alias="class"),
    min_conf: float = Query(default=0.0, ge=0.0, le=1.0),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> DetectionPage:
    get_job_or_404(job_id, db)
    query = select(Detection).where(Detection.job_id == job_id, Detection.confidence >= min_conf)
    count_query = select(func.count()).select_from(Detection).where(
        Detection.job_id == job_id, Detection.confidence >= min_conf
    )
    if class_name:
        query = query.where(Detection.class_name == class_name)
        count_query = count_query.where(Detection.class_name == class_name)
    total = db.scalar(count_query) or 0
    detections = db.scalars(query.order_by(Detection.id).offset(offset).limit(limit)).all()
    return DetectionPage(
        items=[detection_response(item) for item in detections],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{job_id}/summary", response_model=JobSummary)
def get_summary(job_id: int, db: Session = Depends(get_db)) -> JobSummary:
    job = get_job_or_404(job_id, db)
    rows = db.execute(
        select(Detection.class_name, func.count(Detection.id))
        .where(Detection.job_id == job_id)
        .group_by(Detection.class_name)
    ).all()
    return JobSummary(
        job_id=job_id,
        total=sum(count for _, count in rows),
        by_class={class_name: count for class_name, count in rows},
        area_covered=0.0,
        processing_ms=job.processing_ms,
    )


@router.get("/{job_id}/image")
def get_job_image(
    job_id: int,
    tile: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> FileResponse:
    job = get_job_or_404(job_id, db)
    if job.status != "done" or not job.overlay_path:
        raise HTTPException(status_code=409, detail="Processed image is not ready")
    if tile not in (None, "full") and not tile.isdigit():
        raise HTTPException(status_code=400, detail="tile must be 'full' or a numeric tile index")
    image_path = Path(job.overlay_path)
    if not image_path.is_file():
        raise HTTPException(status_code=404, detail="Processed image not found")
    return FileResponse(image_path, media_type="image/svg+xml", filename="overlay.svg")


@router.get("/{job_id}/export")
def export_job(
    job_id: int,
    format: str = Query(default="json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    get_job_or_404(job_id, db)
    detections = db.scalars(
        select(Detection).where(Detection.job_id == job_id).order_by(Detection.id)
    ).all()
    rows = [
        {
            "id": item.id,
            "class": item.class_name,
            "confidence": item.confidence,
            "x": item.x,
            "y": item.y,
            "w": item.width,
            "h": item.height,
            "lat": item.lat,
            "lon": item.lon,
            "size_m": item.size_m,
            "frame_index": item.frame_index,
        }
        for item in detections
    ]
    if format == "csv":
        stream = io.StringIO()
        fields = list(rows[0].keys()) if rows else ["id", "class", "confidence"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        content = stream.getvalue()
        media_type = "text/csv"
        filename = f"job_{job_id}_detections.csv"
    else:
        content = json.dumps({"job_id": job_id, "detections": rows}, indent=2)
        media_type = "application/json"
        filename = f"job_{job_id}_detections.json"
    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

