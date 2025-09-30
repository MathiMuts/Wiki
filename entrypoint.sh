#!/bin/sh

set -e

echo "Entrypoint script started as user: $(whoami)"

# ... (waiting for postgres block is fine) ...

echo "Setting ownership for static and media files..."
chown -R appuser:appuser /app/staticfiles /app/media

echo "Applying database migrations as appuser..."
gosu appuser python manage.py migrate --noinput

# --- NEW DEBUGGING BLOCK ---
echo "--- PRE-COLLECTSTATIC DEBUG ---"
echo "Current working directory: $(pwd)"
echo "Listing permissions for /app and /app/staticfiles:"
ls -ld /app /app/staticfiles
echo "Verifying STATIC_ROOT from within Django:"
gosu appuser python manage.py shell -c "from django.conf import settings; print('STATIC_ROOT from Django:', settings.STATIC_ROOT)"
echo "--- END DEBUG BLOCK ---"

echo "Collecting static files as appuser..."
gosu appuser python manage.py collectstatic --noinput --clear

echo "Starting application server as appuser..."
exec gosu appuser "$@"