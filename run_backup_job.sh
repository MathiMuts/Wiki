#!/bin/sh
set -e

# --- Log Start ---
# Using /proc/1/fd/1 and /proc/1/fd/2 to send output to the container's main stdout/stderr
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] run_backup_job.sh: $1" >> /proc/1/fd/1 2>> /proc/1/fd/2
}

log_message "Backup job started."

# --- Verify Critical Environment Variables (Optional but good for sanity checking) ---
# These should be inherited from the container's environment (set via docker-compose env_file/environment)
# log_message "DJANGO_SETTINGS_MODULE is: '${DJANGO_SETTINGS_MODULE}'"
# log_message "DB_HOST is: '${DB_HOST}'"
# log_message "DB_NAME is: '${DB_NAME}'"
# Add any other critical env vars you want to check if they are present.
# If they are blank here, it means cron isn't inheriting them properly from the container's main env.

# --- Define and Execute Backup Command ---
COMMAND_TO_RUN="cd /app && /usr/local/bin/python manage.py create_wiki_backup --output-dir /backups_archive"
# log_message "Executing: ${COMMAND_TO_RUN}" # Usually not needed if the command itself logs

# Execute the command. Its stdout/stderr will be redirected by the crontab entry.
sh -c "${COMMAND_TO_RUN}"
EXIT_CODE=$?

# --- Log Completion ---
if [ $EXIT_CODE -eq 0 ]; then
    log_message "Backup command finished successfully (exit code ${EXIT_CODE})."
else
    log_message "Backup command FAILED (exit code ${EXIT_CODE}). Check logs from the command itself."
fi

exit $EXIT_CODE