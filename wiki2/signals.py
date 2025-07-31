# wiki2/signals.py
import os
import shutil
from django.db.models.signals import post_save, post_delete
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import Profile, WikiPage, WikiFile

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    instance.profile.save()


@receiver(post_delete, sender=WikiFile)
def delete_file_on_disk(sender, instance, **kwargs):
    if instance.file:
        if os.path.isfile(instance.file.path):
            os.remove(instance.file.path)

@receiver(post_delete, sender=WikiPage)
def delete_page_media_directory(sender, instance, **kwargs):
    page_media_dir = instance.get_media_directory_path()
    if page_media_dir and os.path.exists(page_media_dir) and os.path.isdir(page_media_dir):
        shutil.rmtree(page_media_dir, ignore_errors=True)