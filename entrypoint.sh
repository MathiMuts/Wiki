#!/bin/sh

# Exit immediately if a command exits with a non-zero status.
set -e

# Wait for PostgreSQL to be ready (optional, but good practice)
# This simple version just checks if the port is open.
# A more robust check would try to connect with psql.
if [ -n "$DB_HOST" ] && [ -n "$DB_PORT" ]; then
    echo "Waiting for PostgreSQL at $DB_HOST:$DB_PORT..."
    while ! nc -z $DB_HOST $DB_PORT; do
      sleep 0.1
    done
    echo "PostgreSQL started"
fi

# Apply database migrations
echo "Applying database migrations..."
python manage.py migrate --noinput

# Collect static files (if not done in Dockerfile or if you want it to run every time)
echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

# Create Superuser if DJANGO_SUPERUSER_USERNAME and DJANGO_SUPERUSER_PASSWORD are set
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
  echo "Attempting to create superuser $DJANGO_SUPERUSER_USERNAME..."
  # Use python manage.py shell to execute a script
  # Ensure your project name in DJANGO_SETTINGS_MODULE is correct (e.g., wiki2_project.settings)
  python manage.py shell <<EOF
import os
from django.contrib.auth import get_user_model
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist

User = get_user_model()
username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '') # Email is optional for create_superuser if not provided

if username and password:
    try:
        # Check if user already exists
        User.objects.get(username=username)
        print(f"Superuser '{username}' already exists.")
    except ObjectDoesNotExist:
        # User does not exist, create them
        print(f"Creating superuser '{username}'...")
        User.objects.create_superuser(username=username, email=email, password=password)
        print(f"Superuser '{username}' created successfully.")
    except MultipleObjectsReturned:
        print(f"Multiple users found with username '{username}'. This should not happen. Skipping superuser creation.")
    except Exception as e:
        print(f"An error occurred during superuser creation: {e}")
else:
    print("DJANGO_SUPERUSER_USERNAME or DJANGO_SUPERUSER_PASSWORD not set. Skipping superuser creation.")
EOF
else
  echo "DJANGO_SUPERUSER_USERNAME and/or DJANGO_SUPERUSER_PASSWORD not set. Skipping superuser creation."
fi

# Start Gunicorn server
# The CMD from Dockerfile or docker-compose will be passed as "$@"
# Example: gunicorn wiki2_project.wsgi:application --bind 0.0.0.0:8000 --workers 3
echo "Starting Gunicorn server..."
exec "$@"

    