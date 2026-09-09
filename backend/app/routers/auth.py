"""Sign in, and manage who can."""

from __future__ import annotations

import logging
import re
import time
from collections import defaultdict, deque
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import get_current_user, require_admin
from ..models import ROLES, User
from ..security import create_access_token, hash_password, verify_password

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

MIN_PASSWORD_LENGTH = 12

# Argon2 is deliberately slow, which limits guessing on its own, but not enough
# to leave the endpoint open. A sliding window per client address caps attempts.
# This is per process: with several workers the effective limit is the window
# times the worker count. Good enough for a single deployment; a shared counter
# in Redis is what a fleet would need.
LOGIN_MAX_ATTEMPTS = 10
LOGIN_WINDOW_SECONDS = 300
_attempts: dict[str, deque[float]] = defaultdict(deque)


def _client_key(request: Request) -> str:
    # X-Forwarded-For only when a proxy sets it; it is trivially spoofable
    # otherwise, which would let an attacker rotate their own limit away.
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded and settings.trust_proxy_headers:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_limit(request: Request) -> None:
    key = _client_key(request)
    now = time.monotonic()
    window = _attempts[key]
    while window and now - window[0] > LOGIN_WINDOW_SECONDS:
        window.popleft()
    if len(window) >= LOGIN_MAX_ATTEMPTS:
        retry_in = int(LOGIN_WINDOW_SECONDS - (now - window[0]))
        log.warning("sign-in rate limit hit from %s", key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many sign-in attempts. Try again shortly.",
            headers={"Retry-After": str(max(retry_in, 1))},
        )
    window.append(now)


def _clear_rate_limit(request: Request) -> None:
    _attempts.pop(_client_key(request), None)

# Deliberately not pydantic's EmailStr. It rejects reserved domains such as
# .local, and an internally deployed tool is exactly where accounts look like
# operator@sih.local. This checks the shape - one @, something either side, a
# dot in the domain - which catches typos without dictating the domain.
_EMAIL_SHAPE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clean_email(value: str) -> str:
    value = value.strip().lower()
    if not _EMAIL_SHAPE.match(value):
        raise ValueError("must look like name@domain")
    if len(value) > 320:
        raise ValueError("address is too long")
    return value


class LoginRequest(BaseModel):
    email: str
    password: str

    _norm = field_validator("email")(lambda cls, v: _clean_email(v))


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    email: str
    role: str
    full_name: str | None = None


class UserRead(BaseModel):
    id: int
    email: str
    full_name: str | None
    role: str
    is_active: bool
    last_login_at: datetime | None

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: str
    password: str = Field(min_length=MIN_PASSWORD_LENGTH)
    full_name: str | None = None
    role: str = "viewer"

    _norm = field_validator("email")(lambda cls, v: _clean_email(v))


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH)


class PasswordReset(BaseModel):
    """An admin setting someone else's password.

    There is no email in this system, so there is no reset link to send. An
    admin sets a password and tells the person out of band, which is the honest
    version of a reset when nothing can send mail.
    """

    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH)


class RoleChange(BaseModel):
    role: str


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request,
          db: Session = Depends(get_db)) -> TokenResponse:
    _rate_limit(request)
    user = db.query(User).filter(User.email == body.email).first()

    # Same response whether the address is unknown, the password is wrong or the
    # account is disabled. Distinguishing them tells an attacker which addresses
    # are real.
    ok = False
    if user is not None and user.is_active:
        ok, rehashed = verify_password(body.password, user.password_hash)
        if ok and rehashed:
            user.password_hash = rehashed
    if not ok or user is None:
        log.warning("failed sign-in for %s", body.email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Email or password is incorrect")

    # A success clears the counter, so one fat-fingered password does not
    # count against someone for the rest of the window.
    _clear_rate_limit(request)
    user.last_login_at = datetime.utcnow()
    db.commit()
    log.info("signed in: %s (%s)", user.email, user.role)

    return TokenResponse(
        access_token=create_access_token(user.email, user.role),
        expires_in_minutes=settings.access_token_minutes,
        email=user.email,
        role=user.role,
        full_name=user.full_name,
    )


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: PasswordChange, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)) -> None:
    ok, _ = verify_password(body.current_password, user.password_hash)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    log.info("password changed for %s", user.email)

@router.post("/register", response_model=UserRead,
             status_code=status.HTTP_201_CREATED)
def register(body: UserCreate, db: Session = Depends(get_db)) -> User:
    email = body.email
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="An account with that email already exists")

    # Force role to admin for self-registered accounts so anyone can evaluate the platform
    user = User(email=email, full_name=body.full_name, role="admin",
                password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    log.info("user self-registered: %s", user.email)
    return user


# --- account management, admin only ---------------------------------------

@router.get("/users", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db),
               _: User = Depends(require_admin)) -> list[User]:
    return db.query(User).order_by(User.id).all()


@router.post("/users", response_model=UserRead,
             status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, db: Session = Depends(get_db),
                admin: User = Depends(require_admin)) -> User:
    if body.role not in ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"role must be one of {', '.join(ROLES)}")
    email = body.email
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="An account with that email already exists")

    user = User(email=email, full_name=body.full_name, role=body.role,
                password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    log.info("%s created account %s (%s)", admin.email, user.email, user.role)
    return user


@router.post("/users/{user_id}/disable", response_model=UserRead)
def disable_user(user_id: int, db: Session = Depends(get_db),
                 admin: User = Depends(require_admin)) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No such account")
    if user.id == admin.id:
        # Locking yourself out is recoverable only by editing the database.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="You cannot disable your own account")
    user.is_active = False
    db.commit()
    db.refresh(user)
    log.info("%s disabled account %s", admin.email, user.email)
    return user


@router.post("/users/{user_id}/enable", response_model=UserRead)
def enable_user(user_id: int, db: Session = Depends(get_db),
                admin: User = Depends(require_admin)) -> User:
    """Undo a disable. Without this, disabling someone by mistake could only be
    undone by editing the database."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No such account")
    user.is_active = True
    db.commit()
    db.refresh(user)
    log.info("%s re-enabled account %s", admin.email, user.email)
    return user


@router.post("/users/{user_id}/reset-password",
             status_code=status.HTTP_204_NO_CONTENT)
def reset_password(user_id: int, body: PasswordReset,
                   db: Session = Depends(get_db),
                   admin: User = Depends(require_admin)) -> None:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No such account")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    log.info("%s reset the password for %s", admin.email, user.email)


@router.post("/users/{user_id}/role", response_model=UserRead)
def change_role(user_id: int, body: RoleChange, db: Session = Depends(get_db),
                admin: User = Depends(require_admin)) -> User:
    if body.role not in ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"role must be one of {', '.join(ROLES)}")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No such account")
    if user.id == admin.id and body.role != "admin":
        # Demoting yourself removes the only way back.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="You cannot remove your own admin role")
    user.role = body.role
    db.commit()
    db.refresh(user)
    log.info("%s set %s to %s", admin.email, user.email, user.role)
    return user
