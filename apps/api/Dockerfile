# ScopeGuard API + worker image (same image runs both).
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps: build tools for any wheels that need compiling (kept minimal).
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

COPY alembic.ini ./
COPY alembic ./alembic
COPY prompts ./prompts
COPY app ./app
COPY evaluations ./evaluations

# Non-root runtime user
RUN useradd --create-home --uid 10001 scopeguard \
    && chown -R scopeguard:scopeguard /app
USER scopeguard

EXPOSE 8000

# Default command is overridden by docker-compose for api vs worker.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
