"""Access control.

The other suite checks what the API does; this checks who is allowed to make it
do it. The cases worth having are the ones that fail quietly if someone later
adds a route and forgets the dependency, or relaxes a role check by hand.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

ADMIN = {"email": os.environ["BOOTSTRAP_ADMIN_EMAIL"],
         "password": os.environ["BOOTSTRAP_ADMIN_PASSWORD"]}


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def token_for(client: TestClient, email: str, password: str) -> str:
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- signing in ------------------------------------------------------------

def test_health_stays_open(client):
    """A load balancer cannot hold a token."""
    assert client.get("/api/health").status_code == 200


@pytest.mark.parametrize("path", [
    "/api/registry", "/api/surveys", "/api/registry/heatmap",
])
def test_reads_need_a_token(client, path):
    assert client.get(path).status_code == 401


def test_wrong_password_and_unknown_account_look_the_same(client):
    """Telling them apart says which addresses are real."""
    wrong = client.post("/api/auth/login",
                        json={"email": ADMIN["email"], "password": "not-it"})
    unknown = client.post("/api/auth/login",
                          json={"email": "nobody@sih.local", "password": "not-it"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_a_tampered_token_is_refused(client):
    good = token_for(client, **ADMIN)
    tampered = good[:-4] + ("aaaa" if not good.endswith("aaaa") else "bbbb")
    assert client.get("/api/registry", headers=auth(tampered)).status_code == 401


def test_nonsense_in_the_header_is_refused(client):
    assert client.get("/api/registry", headers=auth("nonsense")).status_code == 401


def test_me_returns_the_signed_in_account(client):
    r = client.get("/api/auth/me", headers=auth(token_for(client, **ADMIN)))
    assert r.status_code == 200
    assert r.json()["email"] == ADMIN["email"]
    assert r.json()["role"] == "admin"


# --- roles -----------------------------------------------------------------

def make_viewer(client: TestClient, admin_token: str, email: str) -> str:
    r = client.post("/api/auth/users", headers=auth(admin_token), json={
        "email": email, "password": "a-viewer-password-1", "role": "viewer"})
    assert r.status_code == 201, r.text
    return token_for(client, email, "a-viewer-password-1")


def test_a_viewer_can_read_but_not_write(client):
    admin = token_for(client, **ADMIN)
    viewer = make_viewer(client, admin, "read-only@sih.local")

    assert client.get("/api/registry", headers=auth(viewer)).status_code == 200
    denied = client.post("/api/surveys", headers=auth(viewer), json={"name": "nope"})
    assert denied.status_code == 403
    assert "analyst" in (denied.json().get("message") or denied.json().get("detail", ""))


def test_only_an_admin_manages_accounts(client):
    admin = token_for(client, **ADMIN)
    viewer = make_viewer(client, admin, "not-an-admin@sih.local")
    assert client.get("/api/auth/users", headers=auth(viewer)).status_code == 403
    assert client.get("/api/auth/users", headers=auth(admin)).status_code == 200


def test_an_admin_satisfies_a_lower_requirement(client):
    """Roles are a floor, not a list; an admin must not need to be enumerated."""
    admin = token_for(client, **ADMIN)
    assert client.post("/api/surveys", headers=auth(admin),
                       json={"name": "admin can write"}).status_code == 201


# --- accounts --------------------------------------------------------------

def test_a_short_password_is_refused(client):
    admin = token_for(client, **ADMIN)
    r = client.post("/api/auth/users", headers=auth(admin),
                    json={"email": "weak@sih.local", "password": "short", "role": "viewer"})
    assert r.status_code == 422


def test_an_internal_domain_is_accepted(client):
    """A deployment on a LAN has accounts at .local, which EmailStr rejects."""
    admin = token_for(client, **ADMIN)
    r = client.post("/api/auth/users", headers=auth(admin), json={
        "email": "Operator@SIH.Local", "password": "internal-domain-ok-1",
        "role": "analyst"})
    assert r.status_code == 201
    assert r.json()["email"] == "operator@sih.local"      # normalised


def test_duplicate_accounts_are_refused(client):
    admin = token_for(client, **ADMIN)
    body = {"email": "twice@sih.local", "password": "first-password-123",
            "role": "viewer"}
    assert client.post("/api/auth/users", headers=auth(admin), json=body).status_code == 201
    assert client.post("/api/auth/users", headers=auth(admin), json=body).status_code == 409


def test_disabling_an_account_takes_effect_immediately(client):
    """Tokens are not revocable, so the account check on each request is what
    makes disabling work before the token expires."""
    admin = token_for(client, **ADMIN)
    viewer = make_viewer(client, admin, "about-to-go@sih.local")
    assert client.get("/api/registry", headers=auth(viewer)).status_code == 200

    users = client.get("/api/auth/users", headers=auth(admin)).json()
    target = next(u for u in users if u["email"] == "about-to-go@sih.local")
    assert client.post(f"/api/auth/users/{target['id']}/disable",
                       headers=auth(admin)).status_code == 200

    assert client.get("/api/registry", headers=auth(viewer)).status_code == 401


def test_an_admin_cannot_lock_themselves_out(client):
    admin = token_for(client, **ADMIN)
    me = client.get("/api/auth/me", headers=auth(admin)).json()
    r = client.post(f"/api/auth/users/{me['id']}/disable", headers=auth(admin))
    assert r.status_code == 400


def test_changing_a_password_needs_the_current_one(client):
    admin = token_for(client, **ADMIN)
    viewer_email = "rotates@sih.local"
    viewer = make_viewer(client, admin, viewer_email)

    wrong = client.post("/api/auth/change-password", headers=auth(viewer),
                        json={"current_password": "not-it",
                              "new_password": "a-new-password-9876"})
    assert wrong.status_code == 400

    ok = client.post("/api/auth/change-password", headers=auth(viewer),
                     json={"current_password": "a-viewer-password-1",
                           "new_password": "a-new-password-9876"})
    assert ok.status_code == 204
    assert token_for(client, viewer_email, "a-new-password-9876")


def test_repeated_failures_are_rate_limited(client):
    """Argon2 is slow, but not slow enough to leave the endpoint open."""
    from app.routers.auth import LOGIN_MAX_ATTEMPTS, _attempts

    _attempts.clear()
    codes = [
        client.post("/api/auth/login",
                    json={"email": ADMIN["email"], "password": "wrong"}).status_code
        for _ in range(LOGIN_MAX_ATTEMPTS + 2)
    ]
    assert codes[0] == 401
    assert 429 in codes, "brute force was never throttled"
    _attempts.clear()


def test_a_success_clears_the_counter(client):
    """One mistyped password should not cost someone the rest of the window."""
    from app.routers.auth import _attempts

    _attempts.clear()
    client.post("/api/auth/login", json={"email": ADMIN["email"], "password": "wrong"})
    assert client.post("/api/auth/login", json=ADMIN).status_code == 200
    assert all(len(w) == 0 for w in _attempts.values()) or not _attempts
    _attempts.clear()


def test_an_admin_can_undo_a_disable(client):
    """Disable was one-way; undoing it meant editing the database by hand."""
    admin = token_for(client, **ADMIN)
    make_viewer(client, admin, "back-again@sih.local")
    users = client.get("/api/auth/users", headers=auth(admin)).json()
    uid = next(u for u in users if u["email"] == "back-again@sih.local")["id"]

    client.post(f"/api/auth/users/{uid}/disable", headers=auth(admin))
    assert token_for.__name__  # sanity
    denied = client.post("/api/auth/login",
                         json={"email": "back-again@sih.local",
                               "password": "a-viewer-password-1"})
    assert denied.status_code == 401

    r = client.post(f"/api/auth/users/{uid}/enable", headers=auth(admin))
    assert r.status_code == 200 and r.json()["is_active"] is True
    assert token_for(client, "back-again@sih.local", "a-viewer-password-1")


def test_an_admin_can_reset_a_forgotten_password(client):
    """There is no email, so this is the only route back into an account."""
    admin = token_for(client, **ADMIN)
    make_viewer(client, admin, "forgot@sih.local")
    users = client.get("/api/auth/users", headers=auth(admin)).json()
    uid = next(u for u in users if u["email"] == "forgot@sih.local")["id"]

    r = client.post(f"/api/auth/users/{uid}/reset-password", headers=auth(admin),
                    json={"new_password": "an-admin-set-password-1"})
    assert r.status_code == 204
    assert token_for(client, "forgot@sih.local", "an-admin-set-password-1")


def test_an_admin_cannot_demote_themselves(client):
    admin = token_for(client, **ADMIN)
    me = client.get("/api/auth/me", headers=auth(admin)).json()
    r = client.post(f"/api/auth/users/{me['id']}/role", headers=auth(admin),
                    json={"role": "viewer"})
    assert r.status_code == 400


def test_role_changes_take_effect(client):
    admin = token_for(client, **ADMIN)
    make_viewer(client, admin, "promoted@sih.local")
    users = client.get("/api/auth/users", headers=auth(admin)).json()
    uid = next(u for u in users if u["email"] == "promoted@sih.local")["id"]

    viewer = token_for(client, "promoted@sih.local", "a-viewer-password-1")
    assert client.post("/api/surveys", headers=auth(viewer),
                       json={"name": "before"}).status_code == 403

    client.post(f"/api/auth/users/{uid}/role", headers=auth(admin),
                json={"role": "analyst"})
    promoted = token_for(client, "promoted@sih.local", "a-viewer-password-1")
    assert client.post("/api/surveys", headers=auth(promoted),
                       json={"name": "after"}).status_code == 201


def test_a_cross_origin_browser_can_send_its_token(client):
    """Frontend on Vercel, API on Render: every authenticated call is
    preflighted, and a preflight that does not allow Authorization fails before
    the request is ever sent. Same-origin development never exercises this.

    The middleware captures the origin list when the app is built, so this uses
    whichever origin is configured rather than patching settings afterwards."""
    from app.config import settings

    origin = settings.cors_origins[0]
    r = client.options("/api/registry", headers={
        "Origin": origin,
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization",
    })
    assert r.status_code == 200
    assert "authorization" in r.headers.get("access-control-allow-headers", "").lower()
    assert r.headers.get("access-control-allow-origin") == origin


def test_an_unlisted_origin_is_refused(client):
    r = client.options("/api/registry", headers={
        "Origin": "https://not-ours.example",
        "Access-Control-Request-Method": "GET",
    })
    assert r.headers.get("access-control-allow-origin") is None


def test_hosted_database_urls_are_usable(monkeypatch):
    """Render hands out postgres:// - SQLAlchemy 2.0 rejects that scheme, and
    plain postgresql:// selects psycopg2, which is not what is installed."""
    from app.config import _normalise_db_url

    assert _normalise_db_url("postgres://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert _normalise_db_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    # already correct, and sqlite, both left alone
    assert _normalise_db_url("postgresql+psycopg://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert _normalise_db_url("sqlite:///x.db") == "sqlite:///x.db"
