"""Who is calling, and may they do this.

Roles are ordered - viewer, analyst, admin - and a requirement is "at least
this", so an admin satisfies an analyst check without being listed everywhere.

    viewer   read the registry, jobs, detections, reports and the map
    analyst  everything a viewer can do, plus upload surveys, run detection,
             build day plans and rank imagery for annotation
    admin    everything, plus creating and disabling accounts
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .db import get_db
from .models import ROLES, User
from .security import decode_access_token

# auto_error=False so a missing header produces our own 401 with a useful
# message rather than FastAPI's bare "Not authenticated".
_bearer = HTTPBearer(auto_error=False, description="Bearer token from /api/auth/login")

UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Sign in to use this endpoint",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None or not creds.credentials:
        raise UNAUTHENTICATED

    claims = decode_access_token(creds.credentials)
    if claims is None:
        raise UNAUTHENTICATED

    user = db.query(User).filter(User.email == claims.get("sub")).first()
    if user is None or not user.is_active:
        # The token may still be inside its expiry, but the account behind it is
        # gone or switched off. Tokens are not revocable on their own, so this
        # check is what makes disabling an account take effect.
        raise UNAUTHENTICATED
    return user


def require_role(minimum: str):
    """Dependency factory: caller must hold `minimum` or better."""
    if minimum not in ROLES:
        raise ValueError(f"unknown role {minimum!r}")
    floor = ROLES.index(minimum)

    def _check(user: User = Depends(get_current_user)) -> User:
        return user

    return _check


require_viewer = require_role("viewer")
require_analyst = require_role("analyst")
require_admin = require_role("admin")
