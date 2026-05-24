# Stage 1: Build dependencies
FROM python:3.12-slim as builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-local.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements-local.txt

# Stage 2: Final image
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements-local.txt .
RUN pip install --no-cache /wheels/*

COPY . .

# Default command (can be overridden in docker-compose)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
