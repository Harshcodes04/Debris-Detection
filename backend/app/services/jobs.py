from __future__ import annotations

import traceback
from datetime import datetime

from sqlalchemy import delete

from ..config import settings
from ..db import SessionLocal
from ..models import Detection, Job
from .inference import run_fake_inference


def process_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None:
            return

        job.status = "processing"
        job.progress = 10
        job.started_at = datetime.utcnow()
        job.error = None
        db.commit()

        job.progress = 30
        db.commit()
        result = run_fake_inference(job.file.storage_path, settings.overlays_dir / str(job.id))

        job.progress = 80
        db.commit()
        db.execute(delete(Detection).where(Detection.job_id == job.id))
        for item in result["detections"]:
            x, y, width, height = item["bbox"]
            db.add(
                Detection(
                    job_id=job.id,
                    class_name=item["class"],
                    confidence=item["confidence"],
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    lat=item.get("lat"),
                    lon=item.get("lon"),
                    size_m=item.get("size_m"),
                    frame_index=item.get("frame_index"),
                )
            )

        job.overlay_path = result["overlay_path"]
        job.processing_ms = result["processing_ms"]
        job.progress = 100
        job.status = "done"
        job.finished_at = datetime.utcnow()
        db.commit()
    except Exception:
        db.rollback()
        job = db.get(Job, job_id)
        if job is not None:
            job.status = "failed"
            job.error = traceback.format_exc(limit=8)
            job.finished_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()

