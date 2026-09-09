from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_analyst, require_viewer
from ..models import Job, Survey, SurveyFile, User
from ..schemas import SurveyCreate, SurveyRead, UploadResponse
from ..services.queue import enqueue_job
from ..storage import StorageError, save_upload


router = APIRouter(prefix="/api/surveys", tags=["surveys"],
                   dependencies=[Depends(require_viewer)])


@router.get("", response_model=list[SurveyRead])
def list_surveys(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[Survey]:
    return db.scalars(
        select(Survey).order_by(Survey.created_at.desc()).offset(offset).limit(limit)
    ).all()


@router.post("", response_model=SurveyRead, status_code=status.HTTP_201_CREATED)
def create_survey(payload: SurveyCreate, db: Session = Depends(get_db),
                  _: User = Depends(require_analyst)) -> Survey:
    survey = Survey(name=payload.name.strip(), notes=payload.notes)
    if not survey.name:
        raise HTTPException(status_code=422, detail="Survey name cannot be empty")
    db.add(survey)
    db.commit()
    db.refresh(survey)
    return survey


@router.post("/{survey_id}/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_sonar_file(
    survey_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_analyst),
) -> UploadResponse:
    survey = db.get(Survey, survey_id)
    if survey is None:
        raise HTTPException(status_code=404, detail="Survey not found")

    filename = file.filename or "upload.bin"
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if not extension:
        raise HTTPException(status_code=400, detail="Uploaded file must have an extension")

    pending_file = SurveyFile(
        survey_id=survey.id,
        filename=filename,
        format=extension,
        size_bytes=0,
        storage_path="pending",
    )
    db.add(pending_file)
    db.flush()
    try:
        destination, size_bytes = await save_upload(file, survey.id, pending_file.id)
    except StorageError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    pending_file.filename = destination.name.split("_", 1)[-1]
    pending_file.size_bytes = size_bytes
    pending_file.storage_path = str(destination)
    job = Job(file=pending_file, status="queued", progress=0)
    db.add(job)
    db.commit()
    db.refresh(job)
    enqueue_job(job.id, background_tasks)
    return UploadResponse(file_id=pending_file.id, job_id=job.id, status=job.status)
