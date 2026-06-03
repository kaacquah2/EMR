# Stage 1: Build dependencies
FROM python:3.12-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# Stage 2: Final image
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 medsync \
    && useradd --uid 1000 --gid medsync --create-home --shell /usr/sbin/nologin medsync

COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache /wheels/*

COPY . .

# Collect static assets at build time (WhiteNoise serves them in production)
RUN DEBUG=True SECRET_KEY=build-collectstatic-only \
    DATABASE_URL=sqlite:////tmp/build.db \
    FIELD_ENCRYPTION_KEY=build-time-encryption-key-32-chars-min \
    AUDIT_LOG_SIGNING_KEY=build-time-audit-signing-key-min \
    python manage.py collectstatic --noinput

RUN chown -R medsync:medsync /app

USER medsync

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:8000/api/v1/health || exit 1

# ASGI via Daphne (Channels/WebSockets). Override in compose for dev hot-reload.
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "medsync_backend.asgi:application"]
