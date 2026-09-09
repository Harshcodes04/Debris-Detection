"""Password hashing and access tokens.

Argon2id rather than bcrypt: bcrypt silently truncates anything past 72 bytes,
which turns a long passphrase into a shorter one without telling anyone. Argon2
was the Password Hashing Competition winner and is what OWASP recommends first.

Tokens are short-lived JWTs signed with SIH_SECRET_KEY. There is no refresh
token and no server-side session; a token is valid until it expires, so the
expiry is kept short rather than long.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from .config import settings

log = logging.getLogger(__name__)

_hasher = PasswordHasher()

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> tuple[bool, str | None]:
    """Check a password. Returns (ok, new_hash_or_None).

    Argon2's parameters get stronger over time. When a stored hash was made with
    weaker ones, this hands back a fresh hash so the caller can store it - the
    only moment the plaintext is available to rehash with.
    """
    try:
        _hasher.verify(hashed, password)
    except (VerifyMismatchError, InvalidHashError):
        return False, None
    except Exception:                       # corrupt hash, unknown variant
        log.exception("password hash could not be checked")
        return False, None
    if _hasher.check_needs_rehash(hashed):
        return True, _hasher.hash(password)
    return True, None


def create_access_token(subject: str, role: str,
                        expires_minutes: int | None = None) -> str:
    minutes = expires_minutes or settings.access_token_minutes
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
        "iss": "sih-ps57",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Return the claims, or None if the token is invalid, expired or not ours."""
    try:
        return jwt.decode(
            token,
            settings.secret_key,
            algorithms=[ALGORITHM],
            issuer="sih-ps57",
            options={"require": ["exp", "sub", "iss"]},
        )
    except jwt.PyJWTError:
        # Wrong signature, expired, tampered, or issued by something else. The
        # caller only needs to know it is not usable.
        return None
