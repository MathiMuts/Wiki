import shutil
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.conf import settings
import os

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