from __future__ import annotations

import pytest
from pathlib import Path
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

    sample_path = Path(__file__).resolve().parent.parent.parent / "demo" / "samples" / "000346.jpg"
    with open(sample_path, "rb") as f:
        image_bytes = f.read()

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

    # 000346.jpg is a shipwreck in sand ripples - the wreck head finds it at
    # about 0.90. "debris" is not in the frozen class list at all; asserting it
    # only passed while inference was mocked.
    detections_response = client.get(
        f"/api/jobs/{job_id}/detections", params={"class": "wreck", "min_conf": 0.8}
    )
    assert detections_response.status_code == 200
    assert detections_response.json()["total"] == 1
    # Box position, not its exact pixels - the numbers move with the weights
    # and the torch version, and a test that pins them breaks on every retrain.
    x, y, w, h = detections_response.json()["items"][0]["bbox"]
    assert 100 < x < 160 and 110 < y < 160
    assert 70 < w < 130 and 250 < h < 320

    summary_response = client.get(f"/api/jobs/{job_id}/summary")
    assert summary_response.json()["by_class"] == {"wreck": 1}

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
