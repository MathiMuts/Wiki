# wiki/admin.py
from django.contrib import admin
from .models import WikiPage, WikiFile
from django.urls import reverse
from django.utils.html import format_html

@admin.register(WikiPage)
class WikiPageAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'last_modified_by', 'updated_at', 'created_at')
    search_fields = ('title', 'content')
    prepopulated_fields = {'slug': ('title',)}
    list_filter = ('updated_at', 'created_at', 'last_modified_by')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(WikiFile)
class WikiFileAdmin(admin.ModelAdmin):
    list_display = ('filename_display', 'page_link', 'filename_slug', 'uploaded_at', 'uploaded_by_username')
    list_filter = ('uploaded_at', 'page__title', 'uploaded_by__username')
    search_fields = ('file', 'filename_slug', 'page__title')
    readonly_fields = ('uploaded_at', 'uploaded_by')
    autocomplete_fields = ['page'] 

    def page_link(self, obj):
        if obj.page:
            url = reverse("admin:wiki_wikipage_change", args=[obj.page.pk])
            return format_html('<a href="{}">{}</a>', url, obj.page.title)
        return "-"
    page_link.short_description = 'Page'

    def uploaded_by_username(self, obj):
        if obj.uploaded_by:
            return obj.uploaded_by.username
        return "-"
    uploaded_by_username.short_description = 'Uploaded By'

    def save_model(self, request, obj, form, change):
        if not obj.pk: 
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)