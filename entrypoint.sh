#!/bin/sh

set -e

echo "Entrypoint script started as user: $(whoami)"

# Wait for the database to be ready
if [ -n "$DB_HOST" ] && [ -n "$DB_PORT" ]; then
    echo "Waiting for PostgreSQL at $DB_HOST:$DB_PORT..."
    while ! nc -z $DB_HOST $DB_PORT; do
      sleep 0.1
    done
    echo "PostgreSQL started"
fi

# Set ownership of volume mounts to the app user
# This is the key fix for the PermissionError
echo "Setting ownership for static and media files..."
chown -R appuser:appuser /app/staticfiles /app/media

# It's good practice to run migrations and other management commands as the app user too.
# We use gosu to temporarily become 'appuser' for a single command.
echo "Applying database migrations as appuser..."
gosu appuser python manage.py migrate --noinput

echo "Collecting static files as appuser..."
gosu appuser python manage.py collectstatic --noinput --clear

echo "Starting application server as appuser..."
# Use gosu to drop privileges and execute the main process
exec gosu appuser "$@"