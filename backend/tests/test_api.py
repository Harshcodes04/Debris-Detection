from __future__ import annotations

import pytest
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


def test_upload_processing_and_exports(client: TestClient) -> None:
    survey_response = client.post("/api/surveys", json={"name": "Demo survey"})
    assert survey_response.status_code == 201
    survey_id = survey_response.json()["id"]

    upload_response = client.post(
        f"/api/surveys/{survey_id}/upload",
        files={"file": ("sample.png", b"fake-image-data", "image/png")},
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
    assert detections_response.json()["total"] == 1
    assert detections_response.json()["items"][0]["bbox"] == [320.0, 220.0, 144.0, 96.0]

    summary_response = client.get(f"/api/jobs/{job_id}/summary")
    assert summary_response.json()["by_class"] == {"debris": 1}

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
