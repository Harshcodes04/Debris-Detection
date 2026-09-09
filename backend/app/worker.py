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
    # A survey line of a few thousand pings takes seconds, not minutes. Without
    # a limit a job that wedges - a corrupt file, a model that never returns -
    # holds its worker slot for the life of the process and nothing after it
    # runs. The soft limit lets the task clean up; the hard one kills it.
    task_soft_time_limit=600,
    task_time_limit=900,
    # Redelivered only if the worker dies mid-task, so a crash does not silently
    # lose an upload the user was told had been accepted.
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


@celery_app.task(name="debris_detection.process_job")
def process_job_task(job_id: int) -> None:
    process_job(job_id)

