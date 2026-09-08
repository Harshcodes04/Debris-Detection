from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models import Detection, Job, Survey, SurveyFile
from app.services.inference import run_fake_inference


def seed_demo() -> int:
    settings.ensure_directories()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = db.scalar(select(Survey).where(Survey.name == "Demo survey"))
        if existing is not None:
            return existing.id

        sample_dir = settings.uploads_dir / "demo"
        sample_dir.mkdir(parents=True, exist_ok=True)
        sample_path = sample_dir / "sample.png"
        sample_path.write_bytes(b"demo sonar sample")

        survey = Survey(name="Demo survey", uploaded_by="seed", notes="Local demo data")
        db.add(survey)
        db.flush()
        uploaded_file = SurveyFile(
            survey_id=survey.id,
            filename=sample_path.name,
            format="png",
            size_bytes=sample_path.stat().st_size,
            storage_path=str(sample_path),
        )
        db.add(uploaded_file)
        db.flush()
        job = Job(
            file_id=uploaded_file.id,
            status="processing",
            progress=80,
            started_at=datetime.utcnow(),
        )
        db.add(job)
        db.flush()

        result = run_fake_inference(sample_path, settings.overlays_dir / str(job.id))
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
        return survey.id
    finally:
        db.close()


if __name__ == "__main__":
    print(f"Seeded demo survey id={seed_demo()}")

