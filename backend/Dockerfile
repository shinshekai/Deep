FROM python:3.12-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential tesseract-ocr libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user and group up front so the image never runs as
# root. ``useradd --create-home`` ensures the home directory exists for
# caches and any persisted state.
RUN groupadd --system --gid 1000 udip \
    && useradd --system --uid 1000 --gid udip --create-home --shell /bin/bash udip

WORKDIR /app

# Install dependencies as root, then drop privileges for the application.
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir . \
    && pip install --no-cache-dir opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-fastapi

COPY app/ ./app/
RUN mkdir -p /app/data /app/data/logs /app/data/knowledge_bases /app/data/metrics \
    && chown -R udip:udip /app

# Switch to the unprivileged user for the rest of the build and at runtime.
USER udip

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8001/api/v1/health').raise_for_status()" || exit 1

EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--log-level", "info"]
