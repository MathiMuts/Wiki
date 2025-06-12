# syntax=docker/dockerfile:1

# --- Base Stage ---
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies (for builder stage)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# --- Builder Stage (for Python dependencies) ---
FROM base AS builder
# WORKDIR /app is inherited
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# --- Final Stage ---
FROM base AS final
# WORKDIR /app is inherited

ARG APP_USER=appuser

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean # Clean up apt cache

# Create user and group
RUN groupadd -r ${APP_USER} && useradd --no-log-init -r -g ${APP_USER} -d /home/${APP_USER} -m ${APP_USER}

# Copy pre-built wheels and install Python dependencies
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# --- Application Setup ---
# Explicitly copy entrypoint.sh first and set permissions
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Copy the rest of the application code
COPY . .

# Create media/static dirs and set ownership (within /app)
RUN mkdir -p /app/staticfiles /app/media

# Change ownership of the entire app directory to the app user
RUN chown -R ${APP_USER}:${APP_USER} /app

# Switch to non-root user
USER ${APP_USER}

# Expose port
EXPOSE 8000

# Define ENTRYPOINT
ENTRYPOINT ["/app/entrypoint.sh"]