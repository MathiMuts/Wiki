import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'Prunes old backup files based on a GFS (Grandfather-Father-Son) retention policy.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--backup-dir',
            type=str,
            default='/backups_archive',
            help='The directory where backup ZIP files are stored.'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Don't delete files, just show which files would be deleted."
        )

    def handle(self, *args, **options):
        backup_dir = Path(options['backup_dir'])
        is_dry_run = options['dry_run']

        if not backup_dir.is_dir():
            raise CommandError(f"Backup directory not found: {backup_dir}")

        if is_dry_run:
            self.stdout.write(self.style.WARNING("--- Running in Dry Run Mode: No files will be deleted. ---"))

        # --- 1. Find and parse all backup files ---
        backup_files = []
        backup_pattern = re.compile(r"(\d{4}-\d{2}-\d{2}-\d{2}-\d{2})\.zip")

        for f in backup_dir.iterdir():
            if f.is_file():
                match = backup_pattern.match(f.name)
                if match:
                    try:
                        dt = datetime.strptime(match.group(1), '%Y-%m-%d-%H-%M')
                        backup_files.append({'path': f, 'dt': dt})
                    except ValueError:
                        self.stderr.write(self.style.WARNING(f"Could not parse date from filename: {f.name}"))

        if not backup_files:
            self.stdout.write(self.style.SUCCESS("No backup files found to prune."))
            return

        # Sort from OLDEST to NEWEST. This simplifies picking the fallback (first item).
        backups = sorted(backup_files, key=lambda x: x['dt'])
        self.stdout.write(f"Found {len(backups)} total backup files in {backup_dir}.")

        # --- 2. Group backups by period ---
        backups_by_week = defaultdict(list)
        backups_by_month = defaultdict(list)
        backups_by_year = defaultdict(list)

        for backup in backups:
            dt = backup['dt']
            week_key = (dt.isocalendar().year, dt.isocalendar().week)
            month_key = (dt.year, dt.month)
            year_key = dt.year
            
            backups_by_week[week_key].append(backup)
            backups_by_month[month_key].append(backup)
            backups_by_year[year_key].append(backup)

        # --- 3. Apply retention rules to determine which backups to keep ---
        now = datetime.now()
        to_keep = set()

        # Define retention periods
        daily_cutoff = now - timedelta(weeks=3)
        weekly_cutoff = now - timedelta(weeks=4*3) # Approx 3 months
        monthly_cutoff = now - timedelta(days=365) # Approx 1 year
        
        self.stdout.write("\n--- Determining which backups to keep ---")

        # Rule 1: Keep all daily backups for the last 3 weeks
        for backup in backups:
            if backup['dt'] > daily_cutoff:
                to_keep.add(backup['path'])
                self.stdout.write(f"  [KEEP/DAILY]  {backup['path'].name} (Within 3 weeks)")

        # Rule 2: Keep one weekly backup (preferring Monday) for the last 3 months
        for week_key, weekly_backups in backups_by_week.items():
            # Check if the week is within the retention period
            if weekly_backups[-1]['dt'] > weekly_cutoff:
                # Find a backup made on Monday (isoweekday() == 1)
                preferred = next((b for b in weekly_backups if b['dt'].isoweekday() == 1), None)
                
                if preferred:
                    to_keep.add(preferred['path'])
                    self.stdout.write(f"  [KEEP/WEEKLY-PREF] {preferred['path'].name} (Chosen Monday backup for week {week_key[1]})")
                else:
                    # Fallback: keep the first backup of that week
                    fallback = weekly_backups[0]
                    to_keep.add(fallback['path'])
                    self.stdout.write(f"  [KEEP/WEEKLY-FALLBACK] {fallback['path'].name} (No Monday backup, kept oldest for week {week_key[1]})")

        # Rule 3: Keep one monthly backup (oldest) for the last year
        for month_key, monthly_backups in backups_by_month.items():
            if monthly_backups[-1]['dt'] > monthly_cutoff:
                # Simple rule: keep the first backup of the month
                first_of_month = monthly_backups[0]
                to_keep.add(first_of_month['path'])
                self.stdout.write(f"  [KEEP/MONTHLY] {first_of_month['path'].name} (Oldest for month {month_key[1]}-{month_key[0]})")
        
        # Rule 4: Keep one yearly backup (preferring Jan 1st) indefinitely
        for year_key, yearly_backups in backups_by_year.items():
            # Find a backup made on January 1st
            preferred = next((b for b in yearly_backups if b['dt'].month == 1 and b['dt'].day == 1), None)

            if preferred:
                to_keep.add(preferred['path'])
                self.stdout.write(f"  [KEEP/YEARLY-PREF]  {preferred['path'].name} (Chosen Jan 1st backup for {year_key})")
            else:
                # Fallback: keep the oldest backup of that year
                fallback = yearly_backups[0]
                to_keep.add(fallback['path'])
                self.stdout.write(f"  [KEEP/YEARLY-FALLBACK] {fallback['path'].name} (No Jan 1st backup, kept oldest for {year_key})")


        # --- 4. Determine which files to delete ---
        all_backup_paths = {b['path'] for b in backups}
        to_delete = all_backup_paths - to_keep

        # --- 5. Execute deletion ---
        if not to_delete:
            self.stdout.write(self.style.SUCCESS("\nNo old backups to prune based on retention policy."))
        else:
            self.stdout.write(f"\n--- Pruning {len(to_delete)} old backups ---")
            for path in sorted(list(to_delete)): # Sort for predictable output
                self.stdout.write(f"  - Deleting {path.name}")
                if not is_dry_run:
                    try:
                        path.unlink()
                    except OSError as e:
                        self.stderr.write(self.style.ERROR(f"    Error deleting file {path}: {e}"))
            
            if is_dry_run:
                self.stdout.write(self.style.SUCCESS(f"\nDry run complete. Would have deleted {len(to_delete)} files."))
            else:
                self.stdout.write(self.style.SUCCESS(f"\nSuccessfully pruned {len(to_delete)} old backups."))