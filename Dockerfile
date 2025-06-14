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
    gosu \
    cron \
    gzip \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

RUN groupadd -r ${APP_USER} && useradd --no-log-init -r -g ${APP_USER} -d /home/${APP_USER} -m ${APP_USER}

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# --- Application and Backup Scripts Setup ---
COPY backup_scripts/backup.sh /backup_scripts/backup.sh
COPY backup_scripts/prune_backups.sh /backup_scripts/prune_backups.sh
COPY backup_scripts/crontab.txt /etc/cron.d/backup_cron

RUN chmod +x /backup_scripts/backup.sh && \
    chmod +x /backup_scripts/prune_backups.sh

RUN chmod 0644 /etc/cron.d/backup_cron

RUN touch /var/log/cron.log && \
    chown ${APP_USER}:${APP_USER} /var/log/cron.log

COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh
COPY . .

RUN mkdir -p /app/staticfiles /app/media /backups_volume && \
    chown -R ${APP_USER}:${APP_USER} /app && \
    chown ${APP_USER}:${APP_USER} /backups_volume


# USER ${APP_USER} # User is not set to not-root because there is something called `gosu` that will let us start the app as a non-root user (appuser) later.

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]