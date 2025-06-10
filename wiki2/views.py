# wiki/views.py
import mimetypes
import os
from django.shortcuts import render, get_object_or_404, redirect
from .models import WikiPage, WikiFile 
from .forms import WikiPageForm, WikiFileForm 
import markdown2
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from . import utils
from django.contrib import messages 
from django.urls import reverse
from django.http import Http404, HttpResponse, JsonResponse


ROOT_WIKI_PAGE_SLUG = "home"
MENU_CONFIG_PAGE_SLUG = "menu-config"

DEFAULT_ROOT_PAGE_CONTENT = '''
# Welcome to the Wiki!

This is the explaination page of the new wiki. Below is a demonstration of the formatting features available.

---
## Standard Markdown Features

This wiki uses Markdown for formatting content. Here are some common examples:

### Text Formatting
- *Italic text*: `*Italic text*` or `_italic text_`
- **Bold text**: `**Bold text**` or `__bold text__`
- `Codeblocks`: `` `Inline code span` `` or ```` ``` `Backticks` ``` ```` for literal backticks inside.

# Heading 1 (equivalent to page title, usually only one per page)
`# Heading 1`
## Heading 2 (like this section's title)
`## Heading 2`
### Heading 3
`### Heading 3`
#### Heading 4
`#### Heading 4`
##### Heading 5
`##### Heading 5`
###### Heading 6
`###### Heading 6`

#### Unordered List
- Item 1
- Item 2
    - Sub-item 2.1
    - Sub-item 2.2
- Item 3

```
#### Unordered List
- Item 1
- Item 2
    - Sub-item 2.1
    - Sub-item 2.2
- Item 3
```

#### Ordered List
1. First item
2. Second item
    1. Sub-item 2.a
    2. Sub-item 2.b
3. Third item

```
#### Ordered List
1. First item
2. Second item
    1. Sub-item 2.a
    2. Sub-item 2.b
3. Third item
```

### Links
- [This is an external link to the Markdown docs.](https://www.markdownguide.org/) `[This is an external link to the Markdown docs.](https://www.markdownguide.org/)`
- [[ Use double square brackets to link to other pages within this wiki.| Menu Config ]] `[[ Menu Config ]]` or `[[ Display Text | Menu Config ]]`
- {{ Use double curly braces to link to files attached to the *current page*| test}} `{{ test }}` or `{{ Display Text | test}}`

### Images
![Alt text for an image](https://picsum.photos/200/300)
![Alt text for an image](test)

```
![Alt text for an image](https://picsum.photos/200/300)
![This image is attatched below](test)
```

### Blockquotes
> This is a blockquote.
> It can span multiple lines.
>
> > Nested blockquotes are also possible.
```
> This is a blockquote.
> It can span multiple lines.
>
> > Nested blockquotes are also possible.
```

### Code Blocks
For a block of code, use triple backticks (fenced code blocks):

```
This is a generic code block
without language specification.
Plain text.
```

````
```
This is a generic code block
without language specification.
Plain text.
```
````

### Horizontal Rule

***

---

___

```
---
___
***
```

### Tables
| Header 1      | Header 2      | Header 3      |
|---------------|---------------|---------------|
| Cell 1.1      | Cell 1.2      | Cell 1.3      |
| Cell 2.1      | **Cell 2.2** (can have Markdown) | Cell 2.3      |
| `Cell 3.1`    | Cell 3.2      | _Cell 3.3_    |

```
| Header 1      | Header 2      | Header 3      |
|---------------|---------------|---------------|
| Cell 1.1      | Cell 1.2      | Cell 1.3      |
| Cell 2.1      | **Cell 2.2** (can have Markdown) | Cell 2.3      |
| `Cell 3.1`    | Cell 3.2      | _Cell 3.3_    |
```

Happy Wiki-ing!



'''


def search(request):
    query = request.GET.get('q', '').strip()
    results = []
    exact_match = None

    if query:
        try:
            exact_match = WikiPage.objects.get(title__iexact=query)
        except WikiPage.DoesNotExist:
            exact_match = None
        except WikiPage.MultipleObjectsReturned: 
            exact_match = None 
        if not exact_match:
            results = WikiPage.objects.filter(
                Q(title__icontains=query) | 
                Q(content__icontains=query)
            ).distinct().order_by('-updated_at')

            if results.count() == 1:
                exact_match = results.first()
                results = []

        if exact_match:
            return redirect(exact_match.get_absolute_url())
        
    if query and results.exists():
        return render(request, 'wiki/modules/wiki_list.html', {'pages': results , 'is_search': True})
    else:
        messages.warning(request, f"No results found for '{query}'.")
        return redirect('wiki:wiki')

def wiki(request):
    landing_page = None
    page_title = ROOT_WIKI_PAGE_SLUG.replace('-', ' ').title()

    try:
        landing_page = WikiPage.objects.get(slug=ROOT_WIKI_PAGE_SLUG)
    except WikiPage.DoesNotExist:
        try:
            landing_page = WikiPage.objects.create(
                title=page_title,
                slug=ROOT_WIKI_PAGE_SLUG,
                content=DEFAULT_ROOT_PAGE_CONTENT
            )
            
        except Exception as e_create:
            pages = WikiPage.objects.all().order_by('-updated_at')
            return render(request, 'wiki/modules/wiki_list.html', {
                'pages': pages,
                'list_title': "Wiki Error",
            })
        
    except WikiPage.MultipleObjectsReturned:
        landing_page = WikiPage.objects.filter(slug=ROOT_WIKI_PAGE_SLUG).order_by('created_at').first()
        if not landing_page:
            pages = WikiPage.objects.all().order_by('-updated_at')
            return render(request, 'wiki/modules/wiki_list.html', {
                'pages': pages,
                'list_title': "Wiki Error",
            })

    if landing_page:
        return redirect(landing_page.get_absolute_url())
    else:
        pages = WikiPage.objects.all().order_by('-updated_at')
        return render(request, 'wiki/modules/wiki_list.html', {
            'pages': pages,
            'list_title': "Wiki Error",
        })
    

def all_wiki_pages(request):
    pages = WikiPage.objects.all().order_by('-updated_at')
    return render(request, 'wiki/modules/wiki_list.html', {'pages': pages, 'list_title': "All Wiki Pages"})

def wiki_page(request, slug):
    page = get_object_or_404(WikiPage, slug=slug)
    processed_markdown_content = utils.preprocess_markdown_with_links(page.content, current_page=page)
    html_content = markdown2.markdown(processed_markdown_content, extras=["fenced-code-blocks", "tables", "nofollow", "header-ids", "break-on-newline"])

    qr = utils.qr_img(request)
    
    page_files = page.files.all().order_by('-uploaded_at')

    return render(request, 'wiki/modules/wiki_page.html', {
        'page': page, 
        'html_content': html_content, 
        'qrcode': qr,
        'page_files': page_files,
    })

@login_required
def page_create(request):
    if request.method == 'POST':
        form = WikiPageForm(request.POST)
        if form.is_valid():
            page = form.save(commit=False)
            page.last_modified_by = request.user
            page.save()
            messages.success(request, f"Page '{page.title}' created successfully.")
            return redirect(page.get_absolute_url())
    else:
        initial_title = request.GET.get('title', '')
        form = WikiPageForm(initial={'title': initial_title.replace('-', ' ').title() if initial_title else ''})
    return render(request, 'wiki/modules/wiki_form.html', {'form': form, 'action': 'Create', 'page_files': None, 'upload_form': None})

@login_required
def page_edit(request, slug):
    page = get_object_or_404(WikiPage, slug=slug)
    page_files = page.files.all().order_by('-uploaded_at')
    upload_form = WikiFileForm() 

    if request.method == 'POST': 
        form = WikiPageForm(request.POST, instance=page)
        if form.is_valid():
            edited_page = form.save(commit=False)
            edited_page.last_modified_by = request.user
            edited_page.save()
            messages.success(request, f"Page '{edited_page.title}' updated successfully.")
            return redirect(edited_page.get_absolute_url())
    else: 
        form = WikiPageForm(instance=page)
        
    return render(request, 'wiki/modules/wiki_form.html', {
        'form': form, 
        'page': page, 
        'action': 'Edit',
        'page_files': page_files,
        'upload_form': upload_form, 
    })

@login_required
def page_delete(request, slug):
    page = get_object_or_404(WikiPage, slug=slug)
    if request.method == 'POST':
        page_title = page.title
        page.delete()
        messages.success(request, f"Page '{page_title}' deleted successfully.")
        return redirect('wiki:wiki')
    return render(request, 'wiki/modules/page_confirm_delete.html', {'page': page})

@login_required
def page_upload_file(request, slug):
    page = get_object_or_404(WikiPage, slug=slug)
    
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return JsonResponse({'status': 'error', 'message': 'Authentication required.'}, status=403)

        form = WikiFileForm(request.POST, request.FILES)
        if form.is_valid():
            wiki_file = form.save(commit=False)
            wiki_file.page = page
            wiki_file.uploaded_by = request.user
            
            wiki_file.save()
            
            file_data = {
                'id': wiki_file.id,
                'url': wiki_file.file.url,
                'name': wiki_file.filename_display, 
                'filename_slug_stored': wiki_file.filename_slug,
                'uploaded_at_display': wiki_file.uploaded_at.strftime("%b %d, %Y %H:%M"),
                'uploaded_by_username': wiki_file.uploaded_by.username if wiki_file.uploaded_by else "",
                'delete_url': reverse('wiki:page_delete_file', kwargs={'slug': page.slug, 'file_id': wiki_file.id})
            }
            return JsonResponse({'status': 'success', 'message': 'File uploaded successfully.', 'file': file_data})
        else:
            errors = {field: [str(e) for e in error_list] for field, error_list in form.errors.items()}
            return JsonResponse({'status': 'error', 'message': 'Upload failed.', 'errors': errors}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method. Only POST is allowed.'}, status=405)

def page_download_file(request, slug, file_id):
    page = get_object_or_404(WikiPage, slug=slug) # Optionally check if user has access to page
    wiki_file = get_object_or_404(WikiFile, id=file_id, page=page)

    try:
        file_path = wiki_file.file.path
        if os.path.exists(file_path):
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type is None:
                mime_type = 'application/octet-stream'

            with open(file_path, 'rb') as fh:
                response = HttpResponse(fh.read(), content_type=mime_type)
                response['Content-Disposition'] = f'attachment; filename="{wiki_file.filename_display}"'
                return response
        else:
            raise Http404("File does not exist on server.")
    except Exception as e:
        raise Http404("Error downloading file.")

@login_required
def page_delete_file(request, slug, file_id):
    page = get_object_or_404(WikiPage, slug=slug)
    file_to_delete = get_object_or_404(WikiFile, id=file_id, page=page)

    if not request.user.is_authenticated:
         return JsonResponse({'status': 'error', 'message': 'Authentication required.'}, status=403)

    if request.method == 'POST':
        filename = file_to_delete.filename_display
        try:
            file_to_delete.delete() 
            return JsonResponse({'status': 'success', 'message': f"File '{filename}' deleted successfully."})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': 'Could not delete file.'}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method. Only POST is allowed.'}, status=405)