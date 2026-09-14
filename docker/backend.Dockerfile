FROM python:3.12-slim

WORKDIR /srv/fellows

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY pyproject.toml README.md ./
COPY backend ./backend

RUN pip install --no-cache-dir -e "."

EXPOSE 8000

WORKDIR /srv/fellows/backend

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
