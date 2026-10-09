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

RUN useradd --create-home appuser && mkdir -p /data && chown -R appuser:appuser /srv /data
USER appuser

# Storage backend. Default keeps the brief's behaviour (in memory, lost on restart).
# TASK_STORE=sqlite persists to /data, which docker-compose mounts as a named volume.
ENV TASK_STORE=memory \
    TASK_DB_PATH=/data/tasks.db

EXPOSE 5000

HEALTHCHECK --interval=5s --timeout=3s --start-period=3s --retries=5 \
  CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=2).status == 200 else 1)"

# Worker/thread choices and log filtering live in gunicorn.conf.py.
CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
