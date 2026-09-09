from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


class Settings:
    def __init__(self) -> None:
        self.data_dir = Path(os.getenv("DATA_DIR", str(DEFAULT_DATA_DIR))).resolve()
        default_database = f"sqlite:///{self.data_dir / 'debris.db'}"
        self.database_url = os.getenv("DATABASE_URL", default_database)
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.queue_mode = os.getenv("QUEUE_MODE", "local").lower()
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
        # Signing key for access tokens. There is no safe default: a fixed
        # fallback would mean every deployment signs with the same key and any
        # of them could mint a token for another. Refused rather than guessed
        # outside development.
        self.secret_key = os.getenv("SIH_SECRET_KEY", "")
        self.environment = os.getenv("ENVIRONMENT", "development").lower()
        if not self.secret_key:
            if self.environment == "production":
                raise RuntimeError(
                    "SIH_SECRET_KEY must be set when ENVIRONMENT=production. "
                    "Generate one with: python -c \"import secrets; "
                    "print(secrets.token_urlsafe(48))\""
                )
            self.secret_key = "dev-only-insecure-key-not-for-deployment-0123456789"
        # HS256 keys shorter than the 256-bit digest weaken the signature;
        # RFC 7518 3.2 requires at least that, and PyJWT warns below it.
        if len(self.secret_key.encode()) < 32:
            raise RuntimeError(
                "SIH_SECRET_KEY must be at least 32 bytes. Generate one with: "
                "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        self.access_token_minutes = int(os.getenv("ACCESS_TOKEN_MINUTES", "720"))
        # Only honour X-Forwarded-For when something in front actually sets it.
        # Trusting it by default lets a caller forge their own rate-limit key.
        self.trust_proxy_headers = os.getenv("TRUST_PROXY_HEADERS", "false").lower() in {"1", "true", "yes"}

        # Seed account, created once on first startup if no users exist.
        self.bootstrap_admin_email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "")
        self.bootstrap_admin_password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")

        self.cors_origins = [
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS", "http://localhost:5200,http://127.0.0.1:5200"
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
