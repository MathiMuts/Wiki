#!/bin/sh

# Exit on error
set -e

# Configuration - These should ideally come from environment variables if possible
# but for simplicity in the script, we can define them here or pass them.
# The DB variables will be available from the .env file in the container.
BACKUP_DIR="/backups_volume" # This will be the mount point inside the container
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
PG_DUMP_FILE="$BACKUP_DIR/db_backup_${TIMESTAMP}.sql.gz"
MEDIA_BACKUP_FILE="$BACKUP_DIR/media_backup_${TIMESTAMP}.tar.gz"
MEDIA_DIR="/app/media" # Path to your media directory inside the container

echo "Starting backup: ${TIMESTAMP}"

# --- PostgreSQL Database Backup ---
echo "Backing up PostgreSQL database..."
# Ensure DB_USER, DB_HOST, DB_NAME, and PGPASSWORD are set as environment variables
# PGPASSWORD will be used by pg_dump automatically if set.
if [ -z "$DB_HOST" ] || [ -z "$DB_USER" ] || [ -z "$DB_NAME" ] || [ -z "$DB_PASSWORD" ]; then
  echo "Error: Database environment variables (DB_HOST, DB_USER, DB_NAME, DB_PASSWORD) are not set."
  exit 1
fi

export PGPASSWORD="$DB_PASSWORD" # pg_dump uses PGPASSWORD
pg_dump -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -Fc | gzip > "$PG_DUMP_FILE"
unset PGPASSWORD # Unset the password variable

if [ $? -eq 0 ]; then
  echo "Database backup successful: $PG_DUMP_FILE"
else
  echo "Database backup FAILED"
  # Consider removing the failed dump file if it was created partially
  rm -f "$PG_DUMP_FILE"
  exit 1 # Or handle error differently
fi

# --- Media Files Backup ---
if [ -d "$MEDIA_DIR" ] && [ "$(ls -A $MEDIA_DIR)" ]; then
  echo "Backing up media files from $MEDIA_DIR..."
  tar -czf "$MEDIA_BACKUP_FILE" -C "$(dirname "$MEDIA_DIR")" "$(basename "$MEDIA_DIR")"
  if [ $? -eq 0 ]; then
    echo "Media files backup successful: $MEDIA_BACKUP_FILE"
  else
    echo "Media files backup FAILED"
    rm -f "$MEDIA_BACKUP_FILE"
    # Decide if a failed media backup should stop the whole script
  fi
else
  echo "Media directory $MEDIA_DIR is empty or does not exist. Skipping media backup."
fi

echo "Backup finished: ${TIMESTAMP}"

# --- Prune old backups ---
# Call the pruning script after a successful backup
echo "Pruning old backups..."
/backup_scripts/prune_backups.sh "$BACKUP_DIR" # Pass the backup directory as an argument

echo "Pruning finished."
echo "----------------------------------------"

exit 0