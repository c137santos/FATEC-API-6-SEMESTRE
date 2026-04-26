FROM python:3.14-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc g++ \
    gdal-bin libgdal-dev && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-cache

COPY backend/ ./backend/

EXPOSE 8000

ENV PYTHONPATH=/app:/app/backend

CMD ["sh", "-c", "uv run alembic -c backend/alembic.ini upgrade head && uv run uvicorn --host 0.0.0.0 backend.app:app"]
