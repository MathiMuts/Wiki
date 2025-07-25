#!/bin/sh

set -e

echo "Entrypoint script started as user: $(whoami)"

echo "Creating environment file for cron jobs..."

# --- Wait for services, run migrations etc. (can still be root or drop privs early for these) ---
if [ -n "$DB_HOST" ] && [ -n "$DB_PORT" ]; then
    echo "Waiting for PostgreSQL at $DB_HOST:$DB_PORT..."
    while ! nc -z $DB_HOST $DB_PORT; do
      sleep 0.1
    done
    echo "PostgreSQL started"
fi

# --- NOTE: This part runs as non-root ---
echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput --clear
 
echo "Starting application server..."
exec "$@"
```
