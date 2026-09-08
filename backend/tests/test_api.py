from __future__ import annotations

import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app




@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_survey_history_and_error_shape(client: TestClient) -> None:
    client.post("/api/surveys", json={"name": "History survey"})

    surveys_response = client.get("/api/surveys")
    assert surveys_response.status_code == 200
    assert surveys_response.json()[0]["name"] == "History survey"

    missing_job_response = client.get("/api/jobs/999999")
    assert missing_job_response.status_code == 404
    assert missing_job_response.json() == {"message": "Job not found"}


def test_upload_processing_and_exports(client: TestClient) -> None:
    survey_response = client.post("/api/surveys", json={"name": "Demo survey"})
    assert survey_response.status_code == 201
    survey_id = survey_response.json()["id"]

    # Generate a minimal valid JPEG in memory — avoids any filesystem dependency
    # so this test runs identically locally and inside the Docker container.
    buf = io.BytesIO()
    Image.new("RGB", (640, 480), color=(30, 30, 30)).save(buf, format="JPEG")
    image_bytes = buf.getvalue()

    upload_response = client.post(
        f"/api/surveys/{survey_id}/upload",
        files={"file": ("000346.jpg", image_bytes, "image/jpeg")},
    )
    assert upload_response.status_code == 202
    job_id = upload_response.json()["job_id"]

    job_response = client.get(f"/api/jobs/{job_id}")
    assert job_response.status_code == 200
    assert job_response.json()["status"] == "done"
    assert job_response.json()["progress"] == 100

    detections_response = client.get(
        f"/api/jobs/{job_id}/detections", params={"class": "debris", "min_conf": 0.8}
    )
    assert detections_response.status_code == 200
    # Assert response shape — not prediction count, which depends on the ML model.
    det_body = detections_response.json()
    assert "total" in det_body
    assert "items" in det_body
    assert isinstance(det_body["total"], int)
    assert isinstance(det_body["items"], list)

    summary_response = client.get(f"/api/jobs/{job_id}/summary")
    assert summary_response.status_code == 200
    # Assert response shape — not specific class counts.
    summary_body = summary_response.json()
    assert "by_class" in summary_body
    assert isinstance(summary_body["by_class"], dict)

    image_response = client.get(f"/api/jobs/{job_id}/image")
    assert image_response.status_code == 200
    assert image_response.headers["content-type"].startswith("image/svg+xml")

    json_response = client.get(f"/api/jobs/{job_id}/export", params={"format": "json"})
    assert json_response.status_code == 200
    assert json_response.json()["job_id"] == job_id

    csv_response = client.get(f"/api/jobs/{job_id}/export", params={"format": "csv"})
    assert csv_response.status_code == 200
    assert "confidence" in csv_response.text


def test_upload_validation(client: TestClient) -> None:
    survey_id = client.post("/api/surveys", json={"name": "Validation survey"}).json()["id"]

    unsupported = client.post(
        f"/api/surveys/{survey_id}/upload",
        files={"file": ("sample.exe", b"data", "application/octet-stream")},
    )
    assert unsupported.status_code == 400

    empty = client.post(
        f"/api/surveys/{survey_id}/upload",
        files={"file": ("empty.png", b"", "image/png")},
    )
    assert empty.status_code == 400
