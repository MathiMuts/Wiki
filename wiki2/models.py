import os
import shutil
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.conf import settings

from django.core.files.base import ContentFile
from io import BytesIO
import subprocess
import tempfile
import markdown2
# from . import utils # We will import utils locally in the method to avoid circular imports

class WikiPage(models.Model):
    title = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True, help_text="Leave blank to auto-generate from title.")
    content = models.TextField(blank=True, help_text="Write your content in Markdown.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wiki_pages_modified',
        help_text="User who last modified the page."
    )

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        original_slug = self.slug
        counter = 1
        queryset = WikiPage.objects.filter(slug=self.slug)
        if self.pk:
            queryset = queryset.exclude(pk=self.pk)
            
        while queryset.exists():
            self.slug = f"{original_slug}-{counter}"
            counter += 1
            queryset = WikiPage.objects.filter(slug=self.slug)
            if self.pk:
                queryset = queryset.exclude(pk=self.pk)

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        page_media_dir = self.get_media_directory_path()

        super().delete(*args, **kwargs) 

        if page_media_dir and os.path.exists(page_media_dir) and os.path.isdir(page_media_dir):
            try:
                if not os.listdir(page_media_dir): 
                    os.rmdir(page_media_dir)
                else:
                    shutil.rmtree(page_media_dir) 
                    
            except OSError as e:
                pass

    def get_absolute_url(self):
        return reverse('wiki:wiki_page', kwargs={'slug': self.slug})
    
    def get_media_directory_path(self):
        if not self.slug:
            return None
        return os.path.join(settings.MEDIA_ROOT, 'wiki_files', self.slug)

def wiki_page_file_path(instance, filename):
    page_slug = instance.page.slug if instance.page else 'unknown_page'
    _original_name_part, original_ext = os.path.splitext(filename)
    original_ext = original_ext.lower()

    final_filename_slug = instance.filename_slug
    if not final_filename_slug:
        temp_slug_base, _ = os.path.splitext(os.path.basename(filename))
        final_filename_slug = slugify(temp_slug_base) if temp_slug_base and slugify(temp_slug_base) else 'uploaded-file'

    new_filename = f"{final_filename_slug}{original_ext}"
    
    return f'wiki_files/{page_slug}/{new_filename}'

class WikiFile(models.Model):
    page = models.ForeignKey(WikiPage, related_name='files', on_delete=models.CASCADE)
    file = models.FileField(upload_to=wiki_page_file_path)
    filename_slug = models.SlugField(max_length=255, blank=True, help_text="The slugified name of the file, without extension. Auto-generated if blank.")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wiki_files_uploaded'
    )

    def __str__(self):
        return self.filename_display

    @property
    def filename_display(self):
        _name_on_disk, ext = os.path.splitext(os.path.basename(self.file.name))
        if self.filename_slug:
            return f"{self.filename_slug}{ext}"
        return os.path.basename(self.file.name) 

    def save(self, *args, **kwargs):
        if self.file and not self.filename_slug: 
            name_part, _ = os.path.splitext(os.path.basename(self.file.name))
            self.filename_slug = slugify(name_part) if name_part and slugify(name_part) else 'file'
            
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        file_path_to_delete = None
        if self.file and hasattr(self.file, 'path') and self.file.path:
            file_path_to_delete = self.file.path
        
        super().delete(*args, **kwargs) 

        if file_path_to_delete and os.path.isfile(file_path_to_delete):
            try:
                os.remove(file_path_to_delete)
            except OSError:
                pass 

def exam_page_pdf_path(instance, filename):
    parent_slug = instance.parent_page.slug if instance.parent_page else 'unknown_parent'
    exam_slug = instance.slug if instance.slug else 'unknown_exam'
    return f'wiki_exams/{parent_slug}/{exam_slug}.pdf'

class ExamPage(models.Model):
    PAGE_TYPE_CHOICES = [
        ('markdown', 'Markdown'),
        ('latex', 'LaTeX'),
    ]

    parent_page = models.ForeignKey(WikiPage, related_name='exam_subpages', on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, blank=True, help_text="Unique slug for this exam under its parent page.")
    content = models.TextField(blank=True, help_text="Content in selected format (Markdown or LaTeX).")
    page_type = models.CharField(
        max_length=10,
        choices=PAGE_TYPE_CHOICES,
        default='markdown',
        help_text="Choose the content type and PDF generation method."
    )
    pdf_file = models.FileField(upload_to=exam_page_pdf_path, blank=True, null=True, help_text="Compiled PDF of this exam.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wiki_exam_subpages_modified'
    )

    class Meta:
        unique_together = ('parent_page', 'slug')
        ordering = ['created_at']

    def __str__(self):
        return f"{self.title} (SubPage of: {self.parent_page.title})"

    def _get_base_pdf_filename(self):
        # Ensure slug is based on current state, in case it changed but not saved yet for a new instance
        current_slug = self.slug or slugify(self.title) or 'exam'
        return f"{current_slug}.pdf"

    def compile_and_save_pdf(self, force_recompile=False):
        if not self.content.strip():
            if self.pdf_file and self.pdf_file.name and hasattr(self.pdf_file, 'path') and os.path.exists(self.pdf_file.path):
                try:
                    os.remove(self.pdf_file.path)
                except OSError:
                    pass # Ignore if removal fails, super().save will handle field
            self.pdf_file = None # Set the FieldFile to None
            if self.pk and 'pdf_file' not in getattr(self, '_being_saved_fields', []):
                 super().save(update_fields=['pdf_file']) # Save the None value to DB if instance exists
            return False, "Content is empty, PDF not generated."

        pdf_needs_update = True
        if self.pdf_file and self.pdf_file.name and hasattr(self.pdf_file, 'path') and os.path.exists(self.pdf_file.path) and not force_recompile:
            try:
                pdf_mtime = os.path.getmtime(self.pdf_file.path)
                # Check against model's updated_at. If PDF is newer than model, no need to recompile.
                if self.updated_at and self.updated_at.timestamp() < pdf_mtime:
                    pdf_needs_update = False
            except OSError:
                 pdf_needs_update = True # If stat fails, assume update is needed

        if not pdf_needs_update and not force_recompile:
            return True, "PDF is already up-to-date."

        # If we proceed, it means we need to recompile.
        # Delete old physical PDF file first, if it exists.
        if self.pdf_file and self.pdf_file.name and hasattr(self.pdf_file, 'path') and os.path.exists(self.pdf_file.path):
            try:
                os.remove(self.pdf_file.path)
            except OSError:
                pass # If removal fails, it's not critical; new save will overwrite or fail.

        # Set the model's FileField to None in memory.
        # If compilation fails, this None state will be saved to the DB.
        self.pdf_file.name = None # Crucial: clears current file reference from FieldFile object in memory

        pdf_content_bytes = None
        temp_dir_for_latex = None

        try:
            if self.page_type == 'latex':
                temp_dir_for_latex = tempfile.mkdtemp()
                tex_file_path = os.path.join(temp_dir_for_latex, 'document.tex')
                with open(tex_file_path, 'w', encoding='utf-8') as f:
                    f.write(self.content)

                cmd = ['pdflatex', '-interaction=nonstopmode', '-output-directory', temp_dir_for_latex, tex_file_path]
                generated_pdf_path = os.path.join(temp_dir_for_latex, 'document.pdf')

                # First pass
                process_result_first_pass = subprocess.run(cmd, capture_output=True, text=False, timeout=300)

                process_result_final = process_result_first_pass # Default to first pass results

                # Check if first pass produced a PDF (exists and has size > 0)
                first_pass_pdf_exists = os.path.exists(generated_pdf_path) and os.path.getsize(generated_pdf_path) > 0

                if first_pass_pdf_exists:
                    # First pass seemed to produce a PDF, run a second pass for references, ToC etc.
                    process_result_second_pass = subprocess.run(cmd, capture_output=True, text=False, timeout=300)
                    process_result_final = process_result_second_pass # Use second pass results for final status
                else:
                    # First pass did not produce a valid PDF, so we consider it failed.
                    # process_result_final is already set to process_result_first_pass
                    pass

                # Now, check the outcome based on PDF existence primarily
                if os.path.exists(generated_pdf_path) and os.path.getsize(generated_pdf_path) > 0:
                    # PDF exists and is not empty, consider it a success.
                    with open(generated_pdf_path, 'rb') as f_pdf:
                        pdf_content_bytes = f_pdf.read()

                    if process_result_final.returncode != 0:
                        # Log a warning or debug message, but proceed since PDF is there.
                        # This can be changed to proper logging.
                        print(f"DEBUG: LaTeX compilation for ExamPage '{self.slug}' (ID: {self.pk or 'New'}) "
                              f"produced a PDF but pdflatex (final pass) exited with code {process_result_final.returncode}.")
                        # Stderr from process_result_final might contain useful warnings.
                else:
                    # PDF does not exist or is empty, so it's a clear failure.
                    # Use details from process_result_final for error reporting.
                    log_path = os.path.join(temp_dir_for_latex, 'document.log')
                    log_output_tail = "No log file found or log was empty."
                    if os.path.exists(log_path):
                        with open(log_path, 'r', encoding='utf-8', errors='ignore') as log_f:
                            log_content = log_f.read()
                            if log_content.strip():
                                log_output_tail = log_content[-1000:] # Get tail of log

                    stderr_output = process_result_final.stderr.decode(errors='ignore').strip() if process_result_final.stderr else ''
                    # stdout_output = process_result_final.stdout.decode(errors='ignore').strip() if process_result_final.stdout else '' # Uncomment if stdout might be useful

                    message = f"LaTeX compilation failed: PDF not generated or was empty. "
                    if process_result_final.returncode != 0:
                         message += f"Compiler exit code: {process_result_final.returncode}. "

                    if stderr_output:
                        message += f"Compiler messages (stderr): {stderr_output}. "
                    # elif stdout_output: # Fallback to stdout if stderr is empty
                    #    message += f"Compiler messages (stdout): {stdout_output[-1000:]}. "

                    message += f"Log tail: ...{log_output_tail}"

                    # Ensure pdf_file field (already None in memory due to self.pdf_file.name = None)
                    # is saved as None to DB if the instance already exists.
                    if self.pk:
                        super().save(update_fields=['pdf_file'])
                    return False, message

            elif self.page_type == 'markdown':
                try:
                    from weasyprint import HTML
                    # Ensure utils are imported here if needed
                    from . import utils as wiki_utils # Local import for utils

                    processed_markdown_content = wiki_utils.preprocess_markdown_with_links(
                        self.content,
                        current_page=self.parent_page
                    )

                    html_output = markdown2.markdown(
                        processed_markdown_content,
                        extras=["fenced-code-blocks", "tables", "header-ids", "break-on-newline"]
                    )

                    css_for_pdf = """
                    @page { size: A4; margin: 2cm; }
                    body { font-family: sans-serif; line-height: 1.5; font-size: 10pt; }
                    h1, h2, h3, h4, h5, h6 { page-break-after: avoid; margin-top: 1.5em; margin-bottom: 0.5em; }
                    h1 {font-size: 2em;} h2 {font-size: 1.75em;} h3 {font-size: 1.5em;}
                    h4 {font-size: 1.25em;} h5 {font-size: 1.1em;} h6 {font-size: 1em;}
                    p, ul, ol, blockquote { margin-bottom: 1em; }
                    pre {
                        font-family: monospace;
                        background-color: #f0f0f0;
                        padding: 1em;
                        border-radius: 4px;
                        overflow-x: auto;
                        page-break-inside: avoid;
                    }
                    code {
                        font-family: monospace;
                        background-color: #f0f0f0;
                        padding: 0.1em;
                        border-radius: 1px;
                        overflow-x: auto; /* Allow horizontal scroll for inline code if needed */
                        page-break-inside: avoid;
                    }
                    table { border-collapse: collapse; width: 100%; margin-bottom: 1em; page-break-inside: avoid; }
                    th, td { border: 1px solid #ccc; padding: 0.5em; text-align: left; }
                    th { background-color: #f8f8f8; }
                    img { max-width: 100%; height: auto; display: block; margin-bottom: 1em; }
                    a { color: #007bff; text-decoration: none; }
                    a:hover { text-decoration: underline; }
                    blockquote { border-left: 3px solid #ccc; padding-left: 1em; margin-left: 0; color: #555; }
                    hr { border: 0; border-top: 1px solid #ccc; margin: 2em 0; }
                    """

                    pdf_buffer = BytesIO()
                    full_html = f"<html><head><meta charset='UTF-8'><style>{css_for_pdf}</style></head><body>{html_output}</body></html>"
                    HTML(string=full_html).write_pdf(pdf_buffer)
                    pdf_content_bytes = pdf_buffer.getvalue()
                except ImportError:
                    if self.pk: super().save(update_fields=['pdf_file'])
                    return False, "Markdown to PDF requires WeasyPrint. Please install it: pip install WeasyPrint"
                except Exception as e_md:
                    if self.pk: super().save(update_fields=['pdf_file'])
                    return False, f"Markdown to PDF conversion error: {e_md}"

            # After attempting compilation for either type:
            if pdf_content_bytes:
                # self.pdf_file.name is currently None (or should be).
                # This FileField.save() populates self.pdf_file.name in memory and writes the physical file.
                # The filename for storage is determined by exam_page_pdf_path.
                # self._get_base_pdf_filename() provides the "filename" part for the upload_to function.
                self.pdf_file.save(self._get_base_pdf_filename(), ContentFile(pdf_content_bytes), save=False)

                # If the instance already has a PK, persist the newly saved PDF file reference to the database.
                # This calls models.Model.save(), bypassing this model's save() override for this specific update.
                if self.pk:
                    super().save(update_fields=['pdf_file'])
                # For new instances (no self.pk), the pdf_file field (now populated in memory)
                # will be saved when the main model's save() is called later.
                return True, "PDF compiled and saved successfully."
            else:
                # This case implies compilation (LaTeX or Markdown) finished without erroring out explicitly above,
                # but did not produce pdf_content_bytes (e.g., LaTeX failed silently according to our relaxed check).
                # self.pdf_file.name should still be None in memory. Persist this state if the instance exists.
                if self.pk:
                    super().save(update_fields=['pdf_file']) # Ensure DB reflects no PDF
                return False, "PDF content could not be generated (compilation produced no data, or an earlier error occurred without specific handling for this path)."

        except subprocess.TimeoutExpired:
            if self.pk: super().save(update_fields=['pdf_file'])
            return False, "PDF compilation timed out (e.g., LaTeX). Please check your content for complexity or errors."
        except Exception as e_compile:
            # General catch-all for other unexpected errors during the process
            if self.pk: super().save(update_fields=['pdf_file'])
            return False, f"General PDF compilation error: {str(e_compile)}"
        finally:
            if temp_dir_for_latex and os.path.exists(temp_dir_for_latex):
                shutil.rmtree(temp_dir_for_latex)

    def save(self, *args, **kwargs):
        # Handle slug generation if not provided
        if not self.slug:
            self.slug = slugify(self.title) if self.title else 'exam'

        # Ensure slug uniqueness within the parent_page scope
        original_slug = self.slug
        counter = 1
        # Build queryset for uniqueness check
        queryset = ExamPage.objects.filter(parent_page=self.parent_page, slug=self.slug)
        if self.pk: # If updating an existing instance, exclude itself from the check
            queryset = queryset.exclude(pk=self.pk)

        while queryset.exists():
            self.slug = f"{original_slug}-{counter}"
            counter += 1
            # Re-check with the new slug
            queryset = ExamPage.objects.filter(parent_page=self.parent_page, slug=self.slug)
            if self.pk:
                queryset = queryset.exclude(pk=self.pk)

        # Decide if we need to call compile_and_save_pdf
        # This is often done in a view or a signal after the main save.
        # If calling compile_and_save_pdf from here, be careful about recursion
        # and ensure fields are correctly set up.
        # For now, we assume compile_and_save_pdf is called separately.
        # If it *is* called from here, and it calls super().save(), it could recurse.
        # Let's assume compile_and_save_pdf has been called *before* this save,
        # or will be called *after* this save, but its result needs to be part of this save transaction.

        # The `compile_and_save_pdf` method now handles its own `super().save(update_fields=['pdf_file'])`
        # when a PDF is successfully generated for an existing object, or when it fails.
        # So, the main `save` method primarily deals with other fields.

        # If `compile_and_save_pdf` modifies `self.pdf_file` (e.g. `self.pdf_file.save(...)`),
        # that change to `self.pdf_file` (the FieldFile object in memory) will be persisted by this `super().save()`.

        super().save(*args, **kwargs)


    def delete(self, *args, **kwargs):
        pdf_path_to_delete = None
        if self.pdf_file and hasattr(self.pdf_file, 'path') and self.pdf_file.path:
            pdf_path_to_delete = self.pdf_file.path

        super().delete(*args, **kwargs) # Delete the model instance first

        # Then, attempt to delete the physical file
        if pdf_path_to_delete and os.path.exists(pdf_path_to_delete):
            try:
                os.remove(pdf_path_to_delete)
                # Optionally, try to remove the parent directory if it's empty
                # This needs careful handling if multiple exams share a parent_slug directory structure
                # For now, just removing the file.
                # pdf_dir = os.path.dirname(pdf_path_to_delete)
                # if not os.listdir(pdf_dir):
                #     os.rmdir(pdf_dir) # This could fail if other files/dirs exist
            except OSError:
                # Log or handle file deletion error if necessary
                pass

    def get_absolute_url(self):
        return reverse('wiki:exam_edit', kwargs={'parent_slug': self.parent_page.slug, 'exam_slug': self.slug})

    def get_download_url(self):
        if self.pdf_file and self.pdf_file.name:
            return reverse('wiki:exam_download', kwargs={'parent_slug': self.parent_page.slug, 'exam_slug': self.slug})
        return None
