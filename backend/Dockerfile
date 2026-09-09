FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/app/backend

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY ml ./ml
COPY weights ./weights

COPY backend/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Nothing here needs root, and the data directory has to be writable by whoever
# does run it.
RUN useradd --create-home --uid 10001 app     && mkdir -p /app/data     && chown -R app:app /app
USER app

EXPOSE 8000

# Compose can then wait for the API to answer, not just for the container to
# start, the same way it already waits for Postgres.
HEALTHCHECK --interval=10s --timeout=3s --start-period=40s --retries=6     CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2).status == 200 else 1)"
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
