from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"


class Settings:
    def __init__(self) -> None:
        self.data_dir = Path(os.getenv("DATA_DIR", str(DEFAULT_DATA_DIR))).resolve()
        default_database = f"sqlite:///{self.data_dir / 'debris.db'}"
        self.database_url = os.getenv("DATABASE_URL", default_database)
        self.max_upload_size_bytes = int(
            os.getenv("MAX_UPLOAD_SIZE_BYTES", str(100 * 1024 * 1024))
        )
        self.allowed_extensions = {
            extension.strip().lower().lstrip(".")
            for extension in os.getenv(
                "ALLOWED_EXTENSIONS", "png,jpg,jpeg,tif,tiff,xtf,jsf,segy"
            ).split(",")
            if extension.strip()
        }
        self.cors_origins = [
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
            ).split(",")
            if origin.strip()
        ]

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def overlays_dir(self) -> Path:
        return self.data_dir / "overlays"

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.overlays_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()

