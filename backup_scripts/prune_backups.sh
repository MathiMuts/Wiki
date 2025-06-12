      
#!/bin/bash

# Exit on error
set -e

BACKUP_DIR="$1"

if [ -z "$BACKUP_DIR" ]; then
    echo "Usage: $0 <backup_directory>"
    exit 1
fi

if [ ! -d "$BACKUP_DIR" ]; then
    echo "Backup directory $BACKUP_DIR does not exist."
    exit 1
fi

echo "Pruning backups in $BACKUP_DIR with retention policy:"
echo "- Daily for last 7 days"
echo "- Sunday for last 8 weeks (approx 2 months)"
echo "- 1st of month for last 12 months"
echo "- 1st of January indefinitely"

# Use find to locate backup files (assuming a consistent naming pattern)
# Pattern: type_backup_YYYY-MM-DD_HH-MM-SS.suffix
# We need to parse dates from filenames.

# Get current date details
NOW_EPOCH=$(date +%s)
TODAY_YYYYMMDD=$(date +%Y-%m-%d)

# Keep all backups from the last 7 days
echo "Keeping all backups from the last 7 days..."
find "$BACKUP_DIR" -type f \( -name "db_backup_*.sql.gz" -o -name "media_backup_*.tar.gz" \) -mtime -7 -print -exec echo "KEEP (daily < 7 days): {}" \;

# Keep Sunday backups for the last 8 weeks (approx. 2 months)
echo "Processing Sunday backups for the last 8 weeks..."
for i in $(seq 0 8); do
    SUNDAY_DATE=$(date -d "last Sunday -${i} weeks" +%Y-%m-%d)
    # Find files matching this Sunday's date prefix
    find "$BACKUP_DIR" -type f \( -name "db_backup_${SUNDAY_DATE}_*.sql.gz" -o -name "media_backup_${SUNDAY_DATE}_*.tar.gz" \) -print -exec echo "KEEP (Sunday < 8 weeks): {}" \;
done

# Keep 1st of the month backups for the last 12 months
echo "Processing 1st of month backups for the last 12 months..."
for i in $(seq 0 11); do
    FIRST_OF_MONTH=$(date -d "$(date +%Y-%m-01) -${i} months" +%Y-%m-01)
    find "$BACKUP_DIR" -type f \( -name "db_backup_${FIRST_OF_MONTH}_*.sql.gz" -o -name "media_backup_${FIRST_OF_MONTH}_*.tar.gz" \) -print -exec echo "KEEP (1st of month < 12m): {}" \;
done

# Keep 1st of January backups indefinitely
echo "Processing 1st of January backups (indefinitely)..."
find "$BACKUP_DIR" -type f \( -name "db_backup_????-01-01_*.sql.gz" -o -name "media_backup_????-01-01_*.tar.gz" \) -print -exec echo "KEEP (Jan 1st): {}" \;


# Create a list of files to keep
KEEP_FILES_LIST=$(mktemp)

# Daily for last 7 days
find "$BACKUP_DIR" -type f \( -name "db_backup_*.sql.gz" -o -name "media_backup_*.tar.gz" \) -mtime -7 -print >> "$KEEP_FILES_LIST"

# Sunday for last 8 weeks
for i in $(seq 0 8); do
    SUNDAY_DATE=$(date -d "last Sunday -${i} weeks" +%Y-%m-%d)
    find "$BACKUP_DIR" -type f \( -name "db_backup_${SUNDAY_DATE}_*.sql.gz" -o -name "media_backup_${SUNDAY_DATE}_*.tar.gz" \) -print >> "$KEEP_FILES_LIST"
done

# 1st of month for last 12 months
for i in $(seq 0 11); do
    FIRST_OF_MONTH=$(date -d "$(date +%Y-%m-01) -${i} months" +%Y-%m-01)
    find "$BACKUP_DIR" -type f \( -name "db_backup_${FIRST_OF_MONTH}_*.sql.gz" -o -name "media_backup_${FIRST_OF_MONTH}_*.tar.gz" \) -print >> "$KEEP_FILES_LIST"
done

# 1st of January indefinitely
find "$BACKUP_DIR" -type f \( -name "db_backup_????-01-01_*.sql.gz" -o -name "media_backup_????-01-01_*.tar.gz" \) -print >> "$KEEP_FILES_LIST"

# Sort and unique the list of files to keep
sort -u "$KEEP_FILES_LIST" -o "$KEEP_FILES_LIST"

echo "--- Files to KEEP based on policy ---"
cat "$KEEP_FILES_LIST"
echo "-------------------------------------"

# Delete files NOT in the KEEP_FILES_LIST
echo "Pruning files not in the keep list..."
find "$BACKUP_DIR" -type f \( -name "db_backup_*.sql.gz" -o -name "media_backup_*.tar.gz" \) | while read -r FILE_TO_CHECK; do
    if ! grep -qxF "$FILE_TO_CHECK" "$KEEP_FILES_LIST"; then
        echo "DELETE: $FILE_TO_CHECK"
        rm -f "$FILE_TO_CHECK"
    fi
done

rm -f "$KEEP_FILES_LIST"
echo "Pruning complete."

    