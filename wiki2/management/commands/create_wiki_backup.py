import os
import shutil
import zipfile
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from wiki2.models import WikiPage

class Command(BaseCommand):
    help = 'Creates a backup of all wiki pages, their content and attachments.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default='/backups_archive',
            help='The directory where backup ZIP files will be stored.'
        )

    def handle(self, *args, **options):
        output_dir = options['output_dir']
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir, exist_ok=True)
                self.stdout.write(self.style.SUCCESS(f"Created backup output directory: {output_dir}"))
            except OSError as e:
                raise CommandError(f"Could not create backup output directory {output_dir}: {e}")

        timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M')
        temp_base_staging_dir = os.path.join(settings.BASE_DIR, 'temp_backup_staging')
        current_backup_staging_path = os.path.join(temp_base_staging_dir, timestamp)
        
        if os.path.exists(current_backup_staging_path):
            shutil.rmtree(current_backup_staging_path)
        os.makedirs(current_backup_staging_path, exist_ok=True)

        self.stdout.write(f"Starting backup process. Staging in: {current_backup_staging_path}")

        try:
            pages = WikiPage.objects.all()
            if not pages.exists():
                self.stdout.write(self.style.WARNING("No wiki pages found to back up."))
                shutil.rmtree(current_backup_staging_path)
                return

            for page in pages:
                page_slug_for_path = page.slug if page.slug else f"page-id-{page.id}"
                self.stdout.write(f"Backing up page: '{page.title}' (slug: {page_slug_for_path})")
                
                page_backup_content_dir = os.path.join(current_backup_staging_path, page_slug_for_path)
                os.makedirs(page_backup_content_dir, exist_ok=True)

                # NOTE: 1. Save main content (plain-text)
                content_file_path = os.path.join(page_backup_content_dir, 'content.md')
                with open(content_file_path, 'w', encoding='utf-8') as f:
                    f.write(page.content)
                self.stdout.write(f"  - Saved content.md for '{page_slug_for_path}'")

                # NOTE: 2. Save attachments
                attachments = page.files.all()
                if attachments.exists():
                    attachments_dir = os.path.join(page_backup_content_dir, 'attachments')
                    os.makedirs(attachments_dir, exist_ok=True)
                    for attachment in attachments:
                        if attachment.file and hasattr(attachment.file, 'path'):
                            try:
                                source_path = attachment.file.path
                                if os.path.exists(source_path):
                                    dest_filename = attachment.filename_display
                                    dest_path = os.path.join(attachments_dir, dest_filename)
                                    shutil.copy2(source_path, dest_path)
                                    self.stdout.write(f"    - Copied attachment: {dest_filename}")
                                else:
                                    self.stderr.write(self.style.WARNING(f"    - Attachment file not found: {source_path} for page '{page_slug_for_path}'"))
                            except Exception as e:
                                self.stderr.write(self.style.ERROR(f"    - Error copying attachment {getattr(attachment, 'filename_display', 'N/A')} for page '{page_slug_for_path}': {e}"))
                        else:
                             self.stderr.write(self.style.WARNING(f"    - Attachment object for page '{page_slug_for_path}' lacks file or path attribute."))
                else:
                    self.stdout.write(f"  - No attachments for '{page_slug_for_path}'")

            zip_filename = f"{timestamp}.zip"
            zip_filepath = os.path.join(output_dir, zip_filename)
            
            self.stdout.write(f"Zipping backup contents from {current_backup_staging_path} to {zip_filepath}...")
            with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(current_backup_staging_path):
                    for file_item in files:
                        file_path_to_zip = os.path.join(root, file_item)
                        arcname = os.path.relpath(file_path_to_zip, current_backup_staging_path)
                        zf.write(file_path_to_zip, arcname=arcname)
            
            self.stdout.write(self.style.SUCCESS(f"Successfully created backup: {zip_filepath}"))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"An error occurred during backup: {e}"))
            import traceback
            self.stderr.write(traceback.format_exc())
        finally:
            if os.path.exists(current_backup_staging_path):
                shutil.rmtree(current_backup_staging_path)
                self.stdout.write(f"Cleaned up temporary staging directory: {current_backup_staging_path}")