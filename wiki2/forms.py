from django import forms
from .models import WikiPage, WikiFile, ExamPage
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
            'filename_slug': 'This name (without extension) will be used for display. It will be auto-generated. You can modify it once a file is selected if allowed by admin.'
        }

class ExamPageForm(forms.ModelForm):
    class Meta:
        model = ExamPage
        fields = ['title', 'slug', 'page_type', 'content']
        widgets = {
            'title': forms.TextInput(attrs={
                'id': 'exam-form-title-input',
                'placeholder': 'Title for this Exam/Sub-Page',
                'class': 'form-control input',
            }),
            'slug': forms.TextInput(attrs={
                'id': 'exam-form-slug-input',
                'placeholder': 'Auto-generated from title, or set a custom one',
                'class': 'form-control input',
            }),
            'page_type': forms.Select(attrs={
                'id': 'exam-form-page-type-select',
                'class': 'form-control input',
            }),
            'content': forms.Textarea(attrs={
                'id': 'exam-form-content-textarea',
                'rows': 15,
                'class': 'form-control markdown-editor-area input',
                'placeholder': 'Enter content here. PDF will be generated based on selected type.'
            }),
        }
        help_texts = {
            'slug': 'Leave blank for auto-generation. Must be unique for this parent wiki page.',
            'page_type': 'This choice determines how the PDF is generated.',
        }

    def __init__(self, *args, **kwargs):
        self.parent_page = kwargs.pop('parent_page', None)
        super().__init__(*args, **kwargs)


    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        title = self.cleaned_data.get('title')

        if not slug and title:
            slug = slugify(title)
        elif slug:
            slug = slugify(slug)
        
        if not slug:
            raise forms.ValidationError("Slug cannot be empty. Please provide a title or a slug.")

        if self.parent_page:
            queryset = ExamPage.objects.filter(parent_page=self.parent_page, slug=slug)
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise forms.ValidationError("An exam/sub-page with this slug already exists for this wiki page.")
        elif not self.instance.pk:
            raise forms.ValidationError("Parent page context is missing for slug validation.")
            
        return slug