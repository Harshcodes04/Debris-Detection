from __future__ import annotations

import json
import redis
from datetime import datetime

from sqlalchemy import delete

from ..config import settings
from ..db import SessionLocal
from ..models import Detection, Job
from ml.inference import run_inference
from ml.enrich import enrich_detection, Context, to_dict as ctx_dict
from ml.risk import score_detection
from .registry import RegistryService

redis_client = redis.Redis.from_url(settings.redis_url)

def cached_enrich(lat: float | None, lon: float | None) -> Context | None:
    if lat is None or lon is None:
        return None
    key = f"enrich:{round(lat, 4)}:{round(lon, 4)}"
    try:
        cached = redis_client.get(key)
        if cached:
            return Context(**json.loads(cached))
    except Exception:
        pass  # fallback to active lookup if redis fails

    ctx = enrich_detection(lat, lon, navigation_is_real=True)
    if ctx:
        try:
            redis_client.setex(key, 86400 * 7, json.dumps(ctx_dict(ctx)))
        except Exception:
            pass
    return ctx


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
        
        cfg = {"output_dir": str(settings.overlays_dir)}
        result = run_inference(job.file.storage_path, config=cfg)

        job.progress = 80
        db.commit()
        db.execute(delete(Detection).where(Detection.job_id == job.id))
        for item in result["detections"]:
            x, y, width, height = item["bbox"]
            lat, lon = item.get("lat"), item.get("lon")
            
            ctx = cached_enrich(lat, lon)
            risk = score_detection(item["class"], item["confidence"], ctx)
            
            db.add(
                Detection(
                    job_id=job.id,
                    class_name=item["class"],
                    confidence=item["confidence"],
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    lat=lat,
                    lon=lon,
                    size_m=item.get("size_m"),
                    frame_index=item.get("frame_index"),
                    depth_m=ctx.depth_m if ctx else None,
                    biodiversity_species=ctx.biodiversity.get("species") if ctx and ctx.biodiversity else None,
                    nearest_port_km=ctx.nearest_port.get("distance_km") if ctx and ctx.nearest_port else None,
                    risk_score=risk.score,
                    risk_band=risk.band,
                    risk_reasons=json.dumps(risk.reasons)
                )
            )

        registry_service = RegistryService(db)
        registry_service.reconcile(result["detections"], survey=job.file.survey.name)

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

