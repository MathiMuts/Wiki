# wiki/forms.py
from django import forms
from .models import WikiPage, WikiFile, Profile
from django.contrib.auth.models import User
from django.utils.text import slugify

class WikiPageForm(forms.ModelForm):
    class Meta:
        model = WikiPage
        fields = ['title', 'slug', 'content']
        widgets = {
            'title': forms.TextInput(attrs={
                'id': 'wiki-form-title-input',
                'placeholder': 'Name the Page here',
                'class': 'form-control some-other-class input',
                'autocomplete': 'off',
            }),
            'slug': forms.TextInput(attrs={
                'id': 'wiki-form-slug-input',
                'placeholder': 'Leave blank to auto-generate from title',
                'class': 'form-control input',
                'autocomplete': 'off',
            }),
            'content': forms.Textarea(attrs={
                'id': 'wiki-form-content-textarea',
                'rows': 10,
                'cols': 80,
                'class': 'form-control markdown-editor-area input',
                'autocomplete': 'off',
            }),
        }
        help_texts = {
            'slug': 'Leave blank to auto-generate from title. WARNING: Changing the slug will change the page URL and can break existing links.',
        }

    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        if slug:
            if slugify(slug) != slug:
                pass 
        return slug

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data

class WikiFileForm(forms.ModelForm):
    class Meta:
        model = WikiFile
        fields = ['file', 'filename_slug']
        widgets = {
            'file': forms.ClearableFileInput(attrs={'class': 'form-control-file input'}),
            'filename_slug': forms.TextInput(attrs={
                'class': 'form-control input', 
                'placeholder': 'Auto-generated from filename',
            }),
        }
        labels = {
            'file': 'Select file',
            'filename_slug': 'Proposed Slug'
        }
        help_texts = {
            'filename_slug': 'This name (without extension) will be used for display. It will be auto-generated. This is also the name used to refrence this file in the wiki.'
        }

class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'wiki-input-styled'}),
            'last_name': forms.TextInput(attrs={'class': 'wiki-input-styled'}),
            'email': forms.EmailInput(attrs={'class': 'wiki-input-styled'}),
        }

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['pfp']
        labels = {
            'pfp': 'Change Profile Picture'
        }
        widgets = {
            'pfp': forms.ClearableFileInput(attrs={'class': 'wiki-input-styled'}),
        }
