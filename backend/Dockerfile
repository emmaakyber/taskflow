FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# Install deps first so this layer caches across code changes.
# Dev deps (pytest) are included so `docker compose run --rm backend pytest` works.
COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements-dev.txt

COPY . .

RUN useradd --create-home appuser && chown -R appuser:appuser /srv
USER appuser

EXPOSE 5000

HEALTHCHECK --interval=5s --timeout=3s --start-period=3s --retries=5 \
  CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=2).status == 200 else 1)"

# One worker on purpose: tasks live in process memory, so multiple workers
# would each hold a different task list. Threads give us concurrency instead.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "8", "--access-logfile", "-", "wsgi:app"]
