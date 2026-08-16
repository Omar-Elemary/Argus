# ---- Argus backend ---------------------------------------------------
FROM python:3.11-slim AS backend

WORKDIR /srv/argus

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps for common wheels (none required for the pure-python stack,
# kept minimal to keep the image lean).
COPY pyproject.toml README.md ./
COPY backend ./backend

RUN pip install --no-cache-dir -e ".[dev]"

EXPOSE 8000

WORKDIR /srv/argus/backend

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]