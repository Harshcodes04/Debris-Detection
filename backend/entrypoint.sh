#!/bin/sh
# Bring the schema up to date before serving. create_all in the app only ever
# adds missing tables; anything that alters an existing one has to come from a
# migration, and this is the moment to apply it.
set -e
cd /app/backend
echo "applying migrations..."
alembic upgrade head
cd /app

# Render (and most PaaS) assign a port and expect the process to bind it. With a
# hardcoded port the health check never answers and the deploy is marked failed.
: "${PORT:=8000}"
exec "$@" --port "$PORT"
