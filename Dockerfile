# syntax=docker/dockerfile:1

# --- Base Stage ---
FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# --- Builder Stage (for Python dependencies) ---
FROM base AS builder
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# --- Final Stage ---
FROM base AS final

ARG APP_USER=appuser

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    libpq5 \
    netcat-openbsd \
    texlive-latex-base \
    texlive-fonts-recommended \
    texlive-latex-extra \
    texlive-fonts-extra \
    libpango-1.0-0 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libpangoft2-1.0-0 \
    gzip \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

RUN groupadd -r ${APP_USER} && useradd --no-log-init -r -g ${APP_USER} -d /home/${APP_USER} -m ${APP_USER}

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# --- Application Setup ---
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh
COPY . .

RUN mkdir -p /app/staticfiles /app/media /backups_volume && \
    chown -R ${APP_USER}:${APP_USER} /app

# Switch to non-root
USER ${APP_USER}

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]