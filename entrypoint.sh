#!/bin/sh

# Exit immediately if a command exits with a non-zero status.
set -e

# --- NOTE: This part runs as root ---
echo "Entrypoint script started as user: $(whoami)"

echo "Creating environment file for cron jobs..."
# This path needs to be accessible by the appuser when the cron job runs
# /home/appuser/ is good.
ENV_FILE_CRON="/home/${APP_USER:-appuser}/project_env.sh"
# Ensure the target directory exists and appuser can write to it if needed
# mkdir -p "$(dirname "$ENV_FILE_CRON")" # Home dir should exist from useradd -m
# chown "${APP_USER:-appuser}:${APP_USER:-appuser}" "$(dirname "$ENV_FILE_CRON")" # Home dir owned by appuser

#!/bin/sh
set -e

# --- This part runs as root ---
echo "Entrypoint script started as user: $(whoami)"

echo "Creating environment file for cron jobs..."
# This path needs to be accessible by the appuser when the cron job runs
# /home/appuser/ is good.
ENV_FILE_CRON="/home/${APP_USER:-appuser}/project_env.sh"
# Ensure the target directory exists and appuser can write to it if needed
# mkdir -p "$(dirname "$ENV_FILE_CRON")" # Home dir should exist from useradd -m
# chown "${APP_USER:-appuser}:${APP_USER:-appuser}" "$(dirname "$ENV_FILE_CRON")" # Home dir owned by appuser

# Write the env vars (as root, but to a file appuser can source)
echo "#!/bin/sh" > "$ENV_FILE_CRON"
echo "# Environment variables for cron jobs" >> "$ENV_FILE_CRON"
printenv | grep -E '^(DB_HOST|DB_USER|DB_NAME|DB_PASSWORD|DJANGO_SETTINGS_MODULE|APP_USER)' | \
  sed -e 's/^\(.*\)$/export \1/g' -e 's/"/\\"/g' -e "s/'/'\"'\"'/g" -e 's/\(.*\)/"\1"/g' >> "$ENV_FILE_CRON"
if [ -n "$DB_PASSWORD" ]; then
    echo "export PGPASSWORD=\"$DB_PASSWORD\"" >> "$ENV_FILE_CRON"
fi
chown "${APP_USER:-appuser}:${APP_USER:-appuser}" "$ENV_FILE_CRON"
chmod +x "$ENV_FILE_CRON"
echo "Cron environment file created at $ENV_FILE_CRON"

# Start cron daemon in the background (as root)
echo "Starting cron daemon..."
cron # or cron -f if you want it in foreground (not for here)
echo "Cron daemon started."

# --- Wait for services, run migrations etc. (can still be root or drop privs early for these) ---
if [ -n "$DB_HOST" ] && [ -n "$DB_PORT" ]; then
    echo "Waiting for PostgreSQL at $DB_HOST:$DB_PORT..."
    # nc might need to be run as appuser if network policies are strict, but usually fine as root for this.
    while ! nc -z $DB_HOST $DB_PORT; do
      sleep 0.1
    done
    echo "PostgreSQL started"
fi

# Run Django management commands as the appuser
# Using gosu: gosu appuser python manage.py migrate --noinput
# Using su-exec: su-exec appuser python manage.py migrate --noinput
# Assuming APP_USER env var is set (e.g., from Dockerfile ARG) or default to 'appuser'
# --- NOTE: This part runs as non-root ---
CURRENT_APP_USER="${APP_USER:-appuser}"

echo "Applying database migrations (as $CURRENT_APP_USER)..."
gosu "$CURRENT_APP_USER" python manage.py migrate --noinput

echo "Collecting static files (as $CURRENT_APP_USER)..."
gosu "$CURRENT_APP_USER" python manage.py collectstatic --noinput --clear

if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
  echo "Attempting to create superuser $DJANGO_SUPERUSER_USERNAME (as $CURRENT_APP_USER)..."
  gosu "$CURRENT_APP_USER" python manage.py shell <<EOF
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

      
# Execute the main command (passed from CMD in Dockerfile) as the appuser
echo "Starting application server (as $CURRENT_APP_USER)..."
exec gosu "$CURRENT_APP_USER" "$@"
```
