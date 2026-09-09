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


---

# Render and Vercel

The backend and the frontend end up on different origins, which is not how the
development setup runs — there Vite proxies `/api` and no CORS is involved. Four
things follow from that.

## Backend on Render

Create the service from `render.yaml` (Blueprint → New Blueprint Instance) rather
than by hand, so the environment cannot drift from what the code expects.

Set these in the dashboard before the first deploy; the blueprint marks them
`sync: false` deliberately:

| Variable | Value |
|---|---|
| `CORS_ORIGINS` | your Vercel URL, exactly — `https://your-app.vercel.app` |
| `BOOTSTRAP_ADMIN_EMAIL` | the first admin |
| `BOOTSTRAP_ADMIN_PASSWORD` | their password; change it after signing in |

`SIH_SECRET_KEY` is generated by Render. `DATABASE_URL` comes from the managed
Postgres in the same blueprint.

**A disk is not optional.** Uploads, overlays and — if you skip Postgres — the
SQLite file all live under `DATA_DIR`. Without the 10 GB disk the blueprint
declares, every deploy and every restart wipes them.

**Not the free plan.** Torch, ultralytics and opencv build to roughly 3 GB and
the models are loaded into memory at first use. The free instance does not have
the memory and will be killed mid-request.

**The first request after a cold start is slow.** Two YOLO checkpoints load on
demand, which is several seconds before anything is returned.

## Frontend on Vercel

Set the project's **root directory to `frontend`**. `vercel.json` supplies the
build command, the output directory and a rewrite so `/map` and `/accounts` do
not 404 when someone refreshes.

One environment variable, at build time:

    VITE_API_BASE_URL = https://your-service.onrender.com

No trailing slash, and no `/api` — the client appends that. Vite inlines the
value into the bundle when it builds, so **changing it needs a redeploy**, not
just a restart.

## The order matters

Render first: you cannot set `VITE_API_BASE_URL` before the API has a URL. Then
Vercel. Then go back and put the Vercel URL into `CORS_ORIGINS` on Render, which
is the step that is easy to forget — until it is done, the browser refuses every
call and the app looks broken with nothing in the logs to explain it.

## Things that only break once the two are split

These all worked in development because the Vite proxy makes everything
same-origin, and all four are handled:

- **`Authorization` has to be allowed on preflight.** A cross-origin
  authenticated request is preflighted, and a preflight that does not list this
  header fails before the request is sent.
- **`postgres://` is not a URL SQLAlchemy accepts**, and plain `postgresql://`
  selects psycopg2, which is not installed here. Whatever Render hands over is
  rewritten to name psycopg 3.
- **The port is assigned by the platform.** A hardcoded one means the health
  check never answers and the deploy is marked failed.
- **`TRUST_PROXY_HEADERS=true`**, because Render terminates TLS in front. Without
  it the rate limiter counts every request against the proxy's address, and one
  client can exhaust everyone's allowance.
