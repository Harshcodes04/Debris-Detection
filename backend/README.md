# Backend

This is the first local backend slice for the marine debris detection system.

## Run locally

From this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`. OpenAPI documentation is at
`http://127.0.0.1:8000/docs`.

The service uses PostgreSQL and local storage when started with the local
`.env` file. Uploading a valid file starts a background job using a fake
inference adapter. That adapter returns the same detection shape expected from
the future ML wrapper. SQLite remains available for isolated tests.

Start the database from the repository root before starting the API:

```powershell
docker compose up -d postgres redis
```

To create a local demo survey without uploading a file, run:

```powershell
.venv\Scripts\python.exe -m scripts.seed_demo
```

## Test

```powershell
pytest
```

The next production hardening pass will replace the fake adapter and run the
API and worker as containerized services.

To use Celery instead of the local FastAPI background task, set
`QUEUE_MODE=celery` in `.env`, start Redis, and run this from the backend
directory in a separate terminal:

```powershell
celery -A app.worker:celery_app worker --loglevel=info --pool=solo
```

Keep `QUEUE_MODE=local` for the simple local setup and API tests.
