# wiki2/models.py
import os
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Q


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    pfp = models.ImageField(default='profile_pics/default.jpg', upload_to='profile_pics')

    def __str__(self):
        return f'{self.user.username} Profile'

class WikiPageManager(models.Manager):
    def find_by_title_or_slug(self, term):
        return self.filter(Q(title__iexact=term) | Q(slug=slugify(term))).first()

class WikiPage(models.Model):
    
    class Visibility(models.TextChoices):
        LOGGED_IN = 'LOGGED_IN', 'Logged-In'
        PRIVATE = 'PRIVATE', 'Private'
        PUBLIC = 'PUBLIC', 'Public'

    title = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True, help_text="Leave blank to auto-generate from title.")
    content = models.TextField(blank=True, help_text="Write your content in Markdown.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_wiki_pages',
        help_text="The owner of this page. Only used for 'Private' pages."
    )
    last_modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wiki_pages_modified',
        help_text="User who last modified the page."
    )
    visibility = models.CharField(
        max_length=10,
        choices=Visibility.choices,
        default=Visibility.LOGGED_IN,
        help_text="Control who can view this page."
    )

    objects = WikiPageManager()

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

        if self.visibility == self.Visibility.PRIVATE:
            self.author = self.last_modified_by
        elif self.visibility != self.Visibility.PRIVATE:
            self.author = None

        super().save(*args, **kwargs)


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