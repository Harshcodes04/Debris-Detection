from __future__ import annotations

from celery import Celery

from .config import settings
from .services.jobs import process_job


celery_app = Celery(
    "debris_detection",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
)


@celery_app.task(name="debris_detection.process_job")
def process_job_task(job_id: int) -> None:
    process_job(job_id)

