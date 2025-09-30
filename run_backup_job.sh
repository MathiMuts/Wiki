#!/bin/sh
set -e

# --- Log Start ---
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] run_backup_job.sh: $1" >> /proc/1/fd/1 2>> /proc/1/fd/2
}

log_message "Backup job started."

# --- 1. Execute Backup Command ---
log_message "Running Django create_wiki_backup command..."
COMMAND_CREATE_BACKUP="cd /app && /usr/local/bin/python manage.py create_wiki_backup --output-dir /backups_archive"

sh -c "${COMMAND_CREATE_BACKUP}"
CREATE_EXIT_CODE=$?

# --- 2. Check result and conditionally run Prune Command ---
if [ $CREATE_EXIT_CODE -eq 0 ]; then
    log_message "Backup command finished successfully. Now pruning old backups..."
    
    COMMAND_PRUNE_BACKUPS="cd /app && /usr/local/bin/python manage.py prune_backups --backup-dir /backups_archive"
    
    sh -c "${COMMAND_PRUNE_BACKUPS}"
    PRUNE_EXIT_CODE=$?

    if [ $PRUNE_EXIT_CODE -eq 0 ]; then
        log_message "Pruning command finished successfully."
    else
        log_message "Pruning command FAILED with exit code ${PRUNE_EXIT_CODE}."
    fi
    # We exit with the prune exit code, which will be 0 on success.
    exit $PRUNE_EXIT_CODE

else
    log_message "Backup command FAILED with exit code ${CREATE_EXIT_CODE}. Skipping prune step."
    exit $CREATE_EXIT_CODE
fi