import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.core.files import File

from wiki2.models import WikiPage, WikiFile

class Command(BaseCommand):
    help = (
        'Restores the wiki from a backup ZIP file created by the '
        'create_wiki_backup command.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'zip_filepath',
            type=str,
            help='The full path to the backup ZIP file to restore.'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Don't actually change any data; just show what would be done."
        )
        parser.add_argument(
            '--delete-unmatched',
            action='store_true',
            help=(
                'Delete any existing wiki pages that are NOT present in the backup file. '
                'Use this for a complete point-in-time restore.'
            )
        )

    @transaction.atomic
    def handle(self, *args, **options):
        zip_filepath = Path(options['zip_filepath'])
        is_dry_run = options['dry_run']
        delete_unmatched = options['delete_unmatched']
        
        self.stdout.write(self.style.WARNING("--- Wiki Restore Initialized ---"))
        if is_dry_run:
            self.stdout.write(self.style.WARNING("--- Running in Dry Run Mode: No changes will be made. ---"))
        
        # --- 1. Validate Input ---
        if not zip_filepath.exists() or not zip_filepath.is_file():
            raise CommandError(f"Backup file not found at: {zip_filepath}")
        if not zipfile.is_zipfile(zip_filepath):
            raise CommandError(f"File is not a valid ZIP archive: {zip_filepath}")
            
        self.stdout.write(f"Restoring from backup file: {zip_filepath.name}")

        slugs_in_backup = set()

        # Use a temporary directory that cleans itself up automatically
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            self.stdout.write(f"Extracting backup to temporary directory: {temp_path}")
            
            with zipfile.ZipFile(zip_filepath, 'r') as zf:
                zf.extractall(temp_path)

            # --- 2. Process each page from the backup ---
            # The top-level items in the extracted archive should be page-slug directories
            for page_slug_dir in temp_path.iterdir():
                if not page_slug_dir.is_dir():
                    continue

                page_slug = page_slug_dir.name
                slugs_in_backup.add(page_slug)
                self.stdout.write(f"\nProcessing page slug: '{page_slug}'")

                # Restore content
                content_file = page_slug_dir / 'content.md'
                if not content_file.exists():
                    self.stderr.write(self.style.WARNING(f"  - Warning: content.md not found for '{page_slug}'. Skipping content restore."))
                    continue
                
                restored_content = content_file.read_text(encoding='utf-8')

                # Get or create the page object
                page, created = WikiPage.objects.get_or_create(slug=page_slug)
                action_str = "CREATED" if created else "UPDATED"
                self.stdout.write(f"  - Page '{page_slug}': {action_str}")

                page.content = restored_content
                # If the page is new, we derive a title from the slug.
                if created:
                    page.title = page_slug.replace('-', ' ').replace('_', ' ').title()

                if not is_dry_run:
                    page.save()

                # Restore attachments
                attachments_dir = page_slug_dir / 'attachments'
                
                # First, clear existing attachments for this page to avoid duplicates
                if page.files.exists():
                    self.stdout.write(f"  - Deleting {page.files.count()} existing attachment(s) for this page.")
                    if not is_dry_run:
                        page.files.all().delete()
                
                if attachments_dir.exists() and attachments_dir.is_dir():
                    for attachment_file_path in attachments_dir.iterdir():
                        if attachment_file_path.is_file():
                            self.stdout.write(f"    - Restoring attachment: {attachment_file_path.name}")
                            if not is_dry_run:
                                # Create a new WikiFile object and attach the file
                                wf = WikiFile(page=page)
                                with open(attachment_file_path, 'rb') as f:
                                    # Django's FileField.save handles moving the file to MEDIA_ROOT
                                    wf.file.save(attachment_file_path.name, File(f), save=True)
                else:
                    self.stdout.write("  - No attachments found in backup for this page.")
            
            # --- 3. Handle pages in DB but not in backup (if requested) ---
            if delete_unmatched:
                self.stdout.write("\nChecking for pages to delete (present in DB but not in backup)...")
                slugs_in_db = set(WikiPage.objects.values_list('slug', flat=True))
                slugs_to_delete = slugs_in_db - slugs_in_backup
                
                if slugs_to_delete:
                    self.stdout.write(self.style.WARNING(f"Found {len(slugs_to_delete)} page(s) to delete:"))
                    for slug in sorted(list(slugs_to_delete)):
                        self.stdout.write(f"  - {slug}")
                    
                    if not is_dry_run:
                        pages_to_delete = WikiPage.objects.filter(slug__in=slugs_to_delete)
                        count, _ = pages_to_delete.delete()
                        self.stdout.write(self.style.SUCCESS(f"Successfully deleted {count} page(s)."))
                else:
                    self.stdout.write("  - No pages to delete.")

        if is_dry_run:
            self.stdout.write(
                self.style.SUCCESS("\n--- Dry Run Complete. No actual changes were made to the database or media files. ---")
            )
            # Since this is a dry run within a transaction, we must cause it to rollback.
            raise CommandError("Dry run successful. Rolling back transaction.")
        else:
            self.stdout.write(self.style.SUCCESS("\n--- Wiki Restore Completed Successfully! ---"))