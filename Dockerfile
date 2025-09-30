# --- Final Stage ---
FROM base AS final

ARG APP_USER=appuser

ENV TZ=Europe/Brussels

# Add gosu for privilege dropping
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    gosu \
    libpq5 \
    netcat-openbsd \
    libpango-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-xlib-2.0-0 \
    libpangoft2-1.0-0 \
    cron \
    zip \
    procps \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

RUN groupadd -r ${APP_USER} && useradd --no-log-init -r -g ${APP_USER} -d /home/${APP_USER} -m ${APP_USER}

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# --- Application Setup ---
COPY entrypoint.sh /app/entrypoint.sh
COPY cron_entrypoint.sh /app/cron_entrypoint.sh
RUN chmod +x /app/entrypoint.sh /app/cron_entrypoint.sh

COPY . .

# NOTE: The chown here is still good for files copied into the image,
# but we will re-run it in the entrypoint for the volumes.
RUN chown -R ${APP_USER}:${APP_USER} /app

# REMOVE the USER instruction. The container will now start as root.
# We will drop to the appuser inside the entrypoint script.
# USER ${APP_USER}

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]