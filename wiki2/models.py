import shutil
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.conf import settings
import os

from django.core.files.base import ContentFile
from io import BytesIO
import subprocess
import tempfile
import markdown2

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
    # file will be uploaded to MEDIA_ROOT/wiki_files/<page_slug>/<sanitized_filename>

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
        if self.file:
            if hasattr(self.file, 'path') and self.file.path and os.path.isfile(self.file.path):
                try:
                    os.remove(self.file.path)
                except OSError:
                    pass 
        super().delete(*args, **kwargs)

def exam_page_pdf_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/wiki_exams/<parent_page_slug>/<exam_slug>.pdf

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
        return f"{self.slug or slugify(self.title) or 'exam'}.pdf"

    def compile_and_save_pdf(self, force_recompile=False): # FIXME: consider async compiling to pdf as this can take time
        """
        Compiles the content to PDF based on page_type and saves it to pdf_file.
        Returns (True, "Success message") or (False, "Error message").
        """
        if not self.content.strip():
            if self.pdf_file: # Delete old PDF if content is now empty
                if os.path.exists(self.pdf_file.path): os.remove(self.pdf_file.path)
                self.pdf_file = None
                super().save(update_fields=['pdf_file']) # Use super to avoid recursion
            return False, "Content is empty, PDF not generated."

        # Simplified check: if content modified time is newer than pdf file mod time, or no pdf
        pdf_needs_update = True
        if self.pdf_file and os.path.exists(self.pdf_file.path) and not force_recompile:
            pdf_mtime = os.path.getmtime(self.pdf_file.path)
            # Compare with updated_at of the ExamPage instance itself
            if self.updated_at and self.updated_at.timestamp() < pdf_mtime:
                pdf_needs_update = False
        
        if not pdf_needs_update and not force_recompile:
            return True, "PDF is already up-to-date."

        # Clear old PDF first to ensure a fresh one is generated or it's removed on failure
        if self.pdf_file and os.path.exists(self.pdf_file.path):
            os.remove(self.pdf_file.path)
        self.pdf_file = None # Will be re-assigned on success

        pdf_content_bytes = None
        temp_dir_for_latex = None

        try:
            if self.page_type == 'latex':
                temp_dir_for_latex = tempfile.mkdtemp()
                tex_file_path = os.path.join(temp_dir_for_latex, 'document.tex')
                with open(tex_file_path, 'w', encoding='utf-8') as f:
                    f.write(self.content)

                # Run pdflatex (might need to run twice for TOC/references)
                # Ensure pdflatex is in your system's PATH
                cmd = ['pdflatex', '-interaction=nonstopmode', '-output-directory', temp_dir_for_latex, tex_file_path]
                process_result = subprocess.run(cmd, capture_output=True, text=False, timeout=30) # 30s timeout
                # Run again for references if first pass was okay
                if process_result.returncode == 0:
                    process_result = subprocess.run(cmd, capture_output=True, text=False, timeout=30)

                generated_pdf_path = os.path.join(temp_dir_for_latex, 'document.pdf')
                if process_result.returncode == 0 and os.path.exists(generated_pdf_path):
                    with open(generated_pdf_path, 'rb') as f_pdf:
                        pdf_content_bytes = f_pdf.read()
                else:
                    log_path = os.path.join(temp_dir_for_latex, 'document.log')
                    log_output = "No log file found."
                    if os.path.exists(log_path):
                        with open(log_path, 'r', encoding='utf-8', errors='ignore') as log_f:
                            log_output = log_f.read()[-1000:] # Last 1000 chars
                    return False, f"LaTeX compilation failed. Error: {process_result.stderr.decode(errors='ignore') if process_result.stderr else 'Unknown error'}. Log: ...{log_output}"

            elif self.page_type == 'markdown':
                # Using WeasyPrint for Markdown to PDF
                try:
                    from weasyprint import HTML
                    # You might want to use your existing markdown preprocessing here
                    # html_output = markdown2.markdown(self.content, extras=["fenced-code-blocks", "tables", ...])
                    # For simplicity, a basic conversion:
                    html_output = markdown2.markdown(self.content, extras=["fenced-code-blocks", "tables", "header-ids"])
                    
                    # Basic CSS for better PDF output
                    css_for_pdf = """
                    @page { size: A4; margin: 2cm; }
                    body { font-family: sans-serif; line-height: 1.5; }
                    h1, h2, h3, h4, h5, h6 { page-break-after: avoid; }
                    pre, code { font-family: monospace; }
                    table { border-collapse: collapse; width: 100%; }
                    th, td { border: 1px solid #ccc; padding: 0.5em; }
                    img { max-width: 100%; height: auto; }
                    """
                    
                    pdf_buffer = BytesIO()
                    HTML(string=f"<html><head><style>{css_for_pdf}</style></head><body>{html_output}</body></html>").write_pdf(pdf_buffer)
                    pdf_content_bytes = pdf_buffer.getvalue()
                except ImportError:
                    return False, "Markdown to PDF requires WeasyPrint. Please run: pip install WeasyPrint"
                except Exception as e_md:
                    return False, f"Markdown to PDF conversion error: {e_md}"
            
            if pdf_content_bytes:
                self.pdf_file.save(self._get_base_pdf_filename(), ContentFile(pdf_content_bytes), save=False) # save=False to avoid recursion
                super().save(update_fields=['pdf_file']) # Save only pdf_file field now
                return True, "PDF compiled and saved successfully."
            else:
                # This case should ideally be caught by specific errors above
                return False, "PDF content could not be generated (no specific error)."

        except subprocess.TimeoutExpired:
            return False, "PDF compilation timed out."
        except Exception as e_compile:
            return False, f"General PDF compilation error: {str(e_compile)}"
        finally:
            if temp_dir_for_latex and os.path.exists(temp_dir_for_latex):
                shutil.rmtree(temp_dir_for_latex)


    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        
        # Ensure slug uniqueness per parent page
        original_slug = self.slug
        counter = 1
        while ExamPage.objects.filter(parent_page=self.parent_page, slug=self.slug).exclude(pk=self.pk).exists():
            self.slug = f"{original_slug}-{counter}"
            counter += 1
        
        # Decide if PDF needs recompilation
        # This is a bit tricky: when is `updated_at` set? Before or after this save?
        # A simple check: if 'content' or 'page_type' are in update_fields or it's a new instance.
        # Or, just always try to recompile if the save method is called explicitly for an update.
        # The compile_and_save_pdf method itself now has logic to check if update is needed.
        
        # Save the model fields first
        super().save(*args, **kwargs)

        # We'll call compile_and_save_pdf from the view after form.save()
        # to ensure the instance (and its ID/slugs) is fully saved before file operations.
        # If called here directly, and `upload_to` depends on instance properties that are not yet saved, it can fail.

    def delete(self, *args, **kwargs):
        if self.pdf_file and os.path.exists(self.pdf_file.path):
            os.remove(self.pdf_file.path)
        super().delete(*args, **kwargs)

    def get_absolute_url(self): # For editing
        return reverse('wiki:exam_edit', kwargs={'parent_slug': self.parent_page.slug, 'exam_slug': self.slug})

    def get_download_url(self):
        if self.pdf_file:
            return reverse('wiki:exam_download', kwargs={'parent_slug': self.parent_page.slug, 'exam_slug': self.slug})
        return None