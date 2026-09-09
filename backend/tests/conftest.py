from __future__ import annotations

import os
import tempfile
from pathlib import Path


test_data_dir = Path(tempfile.mkdtemp(prefix="debris-backend-test-"))
os.environ["DATA_DIR"] = str(test_data_dir)
os.environ["DATABASE_URL"] = f"sqlite:///{test_data_dir / 'test.db'}"
os.environ["QUEUE_MODE"] = "local"

# Every endpoint except /api/health now needs a signed-in caller, so the suite
# needs an account to sign in as. Set before the app is imported, because the
# settings object reads the environment once at import time.
os.environ["BOOTSTRAP_ADMIN_EMAIL"] = "test-admin@sih.local"
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "test-admin-password-123"
os.environ["SIH_SECRET_KEY"] = "test-only-signing-key-long-enough-for-hs256"

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def admin_client():
    """A TestClient whose every request carries an admin bearer token."""
    from app.main import app

    with TestClient(app) as client:
        token = client.post("/api/auth/login", json={
            "email": os.environ["BOOTSTRAP_ADMIN_EMAIL"],
            "password": os.environ["BOOTSTRAP_ADMIN_PASSWORD"],
        }).json()["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client
