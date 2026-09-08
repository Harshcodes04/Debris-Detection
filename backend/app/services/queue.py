from __future__ import annotations

from fastapi import BackgroundTasks

from ..config import settings
from .jobs import process_job


def enqueue_job(job_id: int, background_tasks: BackgroundTasks) -> None:
    """Dispatch a job locally or through Celery based on QUEUE_MODE."""
    if settings.queue_mode == "celery":
        from ..worker import process_job_task

        process_job_task.delay(job_id)
        return
    background_tasks.add_task(process_job, job_id)

