#!/bin/sh
set -e

echo "cron_entrypoint.sh: Starting cron daemon..."

CRON_SCHEDULE_INPUT="${BACKUP_TIME:-03:00}"
FINAL_CRON_SCHEDULE=""

if echo "$CRON_SCHEDULE_INPUT" | grep -qE '^[0-9]{1,2}:[0-9]{1,2}$'; then
    BACKUP_HOUR=$(echo "$CRON_SCHEDULE_INPUT" | cut -d: -f1)
    BACKUP_MINUTE=$(echo "$CRON_SCHEDULE_INPUT" | cut -d: -f2)
    FINAL_CRON_SCHEDULE="${BACKUP_MINUTE} ${BACKUP_HOUR} * * *"
elif echo "$CRON_SCHEDULE_INPUT" | grep -qE '^([0-9*,/-]+ ){4}[0-9*,/-]+$'; then
    FINAL_CRON_SCHEDULE="$CRON_SCHEDULE_INPUT"
else
    echo "cron_entrypoint.sh: Warning: BACKUP_TIME format '${CRON_SCHEDULE_INPUT}' not recognized. Defaulting to 3 AM daily (0 3 * * *)."
    FINAL_CRON_SCHEDULE="0 3 * * *"
fi

echo "cron_entrypoint.sh: Configuring cron job with schedule: '${FINAL_CRON_SCHEDULE}'"

CRON_JOB_COMMAND="/app/run_backup_job.sh"
CRONTAB_LINE="${FINAL_CRON_SCHEDULE} ${CRON_JOB_COMMAND} >> /proc/1/fd/1 2>> /proc/1/fd/2"

echo "${CRONTAB_LINE}" > /tmp/new_root_cron
echo "" >> /tmp/new_root_cron

crontab -u root /tmp/new_root_cron
rm /tmp/new_root_cron

echo "cron_entrypoint.sh: Cron deamon ready."

exec cron -f -L 8