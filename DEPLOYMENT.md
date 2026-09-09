# Deployment

## Before anything else

Generate a signing key. Tokens are signed with it, so a shared or guessed key
means anyone can mint a token for any account.

    python -c "import secrets; print(secrets.token_urlsafe(48))"

The service refuses to start with `ENVIRONMENT=production` and no
`SIH_SECRET_KEY`, and refuses any key under 32 bytes — HS256 signatures are
weakened by anything shorter.

## Environment

| Variable | Required | Notes |
|---|---|---|
| `SIH_SECRET_KEY` | in production | 32 bytes or more |
| `ENVIRONMENT` | no | `production` makes the key mandatory |
| `DATABASE_URL` | no | unset means SQLite at `<DATA_DIR>/debris.db` |
| `BOOTSTRAP_ADMIN_EMAIL` / `_PASSWORD` | first run | creates the only account that can create others |
| `ACCESS_TOKEN_MINUTES` | no | default 720 |
| `TRUST_PROXY_HEADERS` | behind a proxy | only then is `X-Forwarded-For` believed |
| `CORS_ORIGINS` | if split-deployed | default is localhost:5200 |
| `POSTGRES_PASSWORD` | with compose | |
| `LOG_LEVEL` | no | default INFO |

Never commit a filled-in `.env`. `.gitignore` already excludes it.

## Docker

    export SIH_SECRET_KEY=...            # compose refuses to start without it
    export BOOTSTRAP_ADMIN_EMAIL=admin@yourdomain
    export BOOTSTRAP_ADMIN_PASSWORD=...
    docker compose up --build

Migrations run from the entrypoint before the server starts. The API waits for
Postgres to pass its healthcheck, not merely to have a container.

The first build pulls torch and lands around 3 GB, so allow ten minutes. The
frontend is not in compose — build it with `npm run build` and serve `dist/`
from any static host, or run `npm run dev` beside it.

## Without Docker

    py -3.11 -m venv .venv && .venv\Scripts\activate
    pip install -r requirements.txt -r backend/requirements.txt
    cd backend && alembic upgrade head && cd ..
    set PYTHONPATH=.
    uvicorn app.main:app --app-dir backend

## Accounts

The first admin comes from `BOOTSTRAP_ADMIN_EMAIL` / `_PASSWORD`, and only when
the users table is empty — it cannot overwrite anyone or revive a disabled
account. Everyone else is created through the API by an admin.

    viewer    read the registry, jobs, detections, reports, map
    analyst   the above, plus uploads, detection runs, day plans, annotation ranking
    admin     the above, plus creating and disabling accounts

Roles are a floor, so an admin satisfies an analyst check without being listed
separately.

Everything else happens on the **Accounts** page, which only admins can see:
create an account, change someone's role, disable or re-enable them, and set a
new password. There is no sign-up, and nothing is emailed — you create the
account and tell the person the password directly.

A forgotten password is reset by an admin from that page. Without email there is
no reset link, and this is the only route back into an account short of editing
the database.

Change the bootstrap password after first sign-in — it was passed in as an
environment variable and will be sitting in shell history and process listings.

## Schema changes

`create_all` at startup only ever adds missing tables. Anything that alters an
existing one needs a migration:

    cd backend
    alembic revision --autogenerate -m "what changed"
    alembic upgrade head

Read the generated file before applying it; autogenerate is a first draft, and
it does not always get renames or type changes right. Migrations run in batch
mode on SQLite, so the same file works on both SQLite and Postgres.

## What is deliberately not here

**No refresh tokens.** A token is valid until it expires, so the expiry is kept
short rather than long. Disabling an account takes effect immediately anyway,
because the account is checked on every request rather than trusted from the
token alone.

**Rate limiting is per process.** Ten sign-in attempts per five minutes per
client address, counted in memory. Behind several workers the effective limit
multiplies by the worker count. A shared counter in Redis is what a fleet would
need; this is sized for one deployment.

**No upload retention policy.** Uploads and overlays accumulate under
`DATA_DIR`. A 17 MB XTF stays there indefinitely. Watch the disk, or add a
cleanup job.

**Health is the only open endpoint.** A load balancer cannot hold a token, so
`/api/health` answers without one. Everything else returns 401.
