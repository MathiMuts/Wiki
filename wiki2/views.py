# wiki/views.py
import os
import mimetypes
import markdown2
from . import utils
from . import constants
from requests import post
from urllib.parse import urlencode
from .models import WikiPage, WikiFile
from .forms import WikiPageForm, WikiFileForm

from django.conf import settings
from django.urls import reverse
from django.http import Http404, HttpResponse, JsonResponse, FileResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages

def login_view(request):
    if request.method == 'GET':
        next_url = request.GET.get('next')
        admin_login_url = reverse('admin:login')

        if next_url:
            return redirect(f'{admin_login_url}?next={next_url}')
        else:
            return redirect(admin_login_url)

    elif request.method == 'POST':
        admin_login_url = reverse('admin:login')
        next_url = request.POST.get('next', request.GET.get('next'))
        if next_url:
             return redirect(f'{admin_login_url}?next={next_url}')
        return redirect(admin_login_url)

@login_required
def logout_view(request):
    previous_page = request.META.get('HTTP_REFERER')
    logout_url = request.build_absolute_uri(reverse('wiki:logout'))

    if previous_page:
        if not url_has_allowed_host_and_scheme(
            url=previous_page,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            previous_page = None
        elif previous_page == logout_url:
            previous_page = None

    logout(request)
    messages.info(request, "You have been successfully logged out.")

    if previous_page:
        return redirect(previous_page)
    else:
        return redirect(getattr(settings, 'LOGOUT_REDIRECT_URL', reverse('wiki:wiki')))

@login_required
def profile(request):
    return render(request, 'wiki/pages/profile.html', {'user': request.user})

@login_required
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
        return render(request, 'wiki/pages/wiki_list.html', {'pages': results , 'is_search': True})
    else:
        messages.warning(request, f"No results found for '{query}'.")
        return redirect('wiki:wiki')

@login_required
def wiki(request):
    landing_page = None
    page_title = constants.ROOT_WIKI_PAGE_SLUG.replace('-', ' ').title()

    try:
        landing_page = WikiPage.objects.get(slug=constants.ROOT_WIKI_PAGE_SLUG)
    except WikiPage.DoesNotExist:
        try:
            landing_page = WikiPage.objects.create(
                title=page_title,
                slug=constants.ROOT_WIKI_PAGE_SLUG,
                content=constants.DEFAULT_ROOT_PAGE_CONTENT
            )

        except Exception as e_create:
            pages = WikiPage.objects.all().order_by('-updated_at')
            return render(request, 'wiki/pages/wiki_list.html', {
                'pages': pages,
                'list_title': "Wiki Error",
            })

    except WikiPage.MultipleObjectsReturned:
        landing_page = WikiPage.objects.filter(slug=constants.ROOT_WIKI_PAGE_SLUG).order_by('created_at').first()
        if not landing_page:
            pages = WikiPage.objects.all().order_by('-updated_at')
            return render(request, 'wiki/pages/wiki_list.html', {
                'pages': pages,
                'list_title': "Wiki Error",
            })

    if landing_page:
        return redirect(landing_page.get_absolute_url())
    else:
        pages = WikiPage.objects.all().order_by('-updated_at')
        return render(request, 'wiki/pages/wiki_list.html', {
            'pages': pages,
            'list_title': "Wiki Error",
        })

@login_required
def all_wiki_pages(request):
    pages = WikiPage.objects.all().order_by('-updated_at')
    return render(request, 'wiki/pages/wiki_list.html', {'pages': pages, 'list_title': "All Wiki Pages"})

@login_required
def wiki_page(request, slug):
    try:
        page = WikiPage.objects.get(slug=slug)
        processed_markdown_content = utils.preprocess_markdown_with_links(page.content, current_page=page)
        html_content = markdown2.markdown(processed_markdown_content, extras=["fenced-code-blocks", "tables", "nofollow", "header-ids", "break-on-newline"])
        qr = utils.qr_img(request)
        page_files = page.files.all().order_by('-uploaded_at')

        return render(request, 'wiki/pages/wiki_page.html', {
            'page': page,
            'html_content': html_content,
            'qrcode': qr,
            'page_files': page_files,
        })

    except WikiPage.DoesNotExist:
        # Page does not exist, redirect to the create page view
        create_url = reverse('wiki:page_create')
        params = {
            'initial_title_str': slug.replace('-', ' ').title(),
            'initial_slug_str': slug
        }
        redirect_url = f"{create_url}?{urlencode(params)}"
        return redirect(redirect_url)
    except WikiPage.MultipleObjectsReturned:
        messages.error(request, f"Error: Multiple pages found for the URL '{slug}'. Please contact an administrator.")
        return redirect('wiki:wiki')

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
        initial_data = {}

        raw_initial_title = request.GET.get('initial_title_str', '')
        raw_initial_slug = request.GET.get('initial_slug_str', '')

        final_title = ''
        final_slug = ''

        if raw_initial_title:
            if raw_initial_title == slugify(raw_initial_title) and '-' in raw_initial_title:
                final_title = raw_initial_title.replace('-', ' ').title()
            else:
                final_title = raw_initial_title
        elif raw_initial_slug:
            final_title = raw_initial_slug.replace('-', ' ').title()

        if raw_initial_slug:
            final_slug = raw_initial_slug

        if final_title:
            initial_data['title'] = final_title
        if final_slug:
            initial_data['slug'] = final_slug

        form = WikiPageForm(initial=initial_data)

        if raw_initial_title or raw_initial_slug:
            page_display_name_for_msg = initial_data.get('title', 'this page')

            page_exists_now = False
            intended_slug_for_check = initial_data.get('slug')
            if not intended_slug_for_check and initial_data.get('title'):
                intended_slug_for_check = slugify(initial_data.get('title'))

            if intended_slug_for_check and WikiPage.objects.filter(slug=intended_slug_for_check).exists():
                page_exists_now = True

            if not page_exists_now:
                 messages.info(request, f"The page '{page_display_name_for_msg}' does not exist. You can create it now.")

    return render(request, 'wiki/pages/wiki_form.html', {'form': form, 'action': 'Create', 'page_files': None, 'upload_form': None})

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

    return render(request, 'wiki/pages/wiki_form.html', {
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

        post(f"{settings.NTFY_BASE_URL}{settings.NTFY_TOPIC}",
        data=f"The wiki-page '{page.title}' has been deleted by {request.user}",
        headers={
            "Title": f"Wiki Page Deleted",
            "Priority": f"3", # 1 is no ping, 3 is with ping (sound notification)
            "Tags": f"warning", # OR wastebasket, warning, no_entry_sign, triangular_flag_on_post
            "Click": f"{reverse('wiki:wiki')}",
        })
        
        page.delete()
        messages.success(request, f"Page '{page.title}' deleted successfully.")
        return redirect('wiki:wiki')
    return render(request, 'wiki/pages/page_confirm_delete.html', {'page': page})

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

@login_required
def page_download_file(request, slug, file_id):
    page = get_object_or_404(WikiPage, slug=slug)
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