# wiki2/views.py
import os
import mimetypes
import hashlib

from .models import WikiPage, WikiFile
from .forms import WikiPageForm, WikiFileForm, UserUpdateForm, ProfileUpdateForm
from . import constants
from . import utils
from . import services

from django.conf import settings
from django.urls import reverse
from django.http import Http404, HttpResponse, JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache
from urllib.parse import urlencode


@login_required
def profile(request):
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user.profile)
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, f'Your account has been updated!')
            return redirect('wiki:profile')
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)
    context = {'u_form': u_form, 'p_form': p_form}
    return render(request, 'wiki/pages/profile.html', context)


@login_required
def search(request):
    query = request.GET.get('q', '').strip()
    if not query:
        messages.warning(request, "Please enter a search term.")
        return redirect('wiki:wiki')

    exact_match = WikiPage.objects.find_by_title_or_slug(query)
    if exact_match:
        return redirect(exact_match.get_absolute_url())

    results = WikiPage.objects.filter(
        Q(title__icontains=query) | Q(content__icontains=query)
    ).distinct().order_by('-updated_at')

    if results.exists():
        if results.count() == 1:
            return redirect(results.first().get_absolute_url())
        return render(request, 'wiki/pages/wiki_list.html', {'pages': results, 'is_search': True, 'query': query})
    else:
        messages.warning(request, f"No results found for '{query}'.")
        return redirect('wiki:wiki')


@login_required
def wiki(request):
    landing_page = get_object_or_404(WikiPage, slug=constants.ROOT_WIKI_PAGE_SLUG)
    return redirect(landing_page.get_absolute_url())


@login_required
def all_wiki_pages(request):
    pages = WikiPage.objects.all().order_by('-updated_at')
    return render(request, 'wiki/pages/wiki_list.html', {'pages': pages, 'list_title': "All Wiki Pages"})


@login_required
def wiki_page(request, slug):
    try:
        page = WikiPage.objects.get(slug=slug)
        html_content = services.render_markdown_to_html(page.content, current_page=page)
        
        qr = utils.qr_img(request)
        page_files = page.files.all().order_by('-uploaded_at')

        return render(request, 'wiki/pages/wiki_page.html', {
            'page': page,
            'html_content': html_content,
            'qrcode': qr,
            'page_files': page_files,
        })

    except WikiPage.DoesNotExist:
        create_url = reverse('wiki:page_create')
        params = {'initial_slug_str': slug}
        return redirect(f"{create_url}?{urlencode(params)}")
    except WikiPage.MultipleObjectsReturned:
        messages.error(request, f"Error: Multiple pages found for '{slug}'. Please contact an admin.")
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
        initial_slug = request.GET.get('initial_slug_str', '')
        initial_title = request.GET.get('initial_title_str', initial_slug.replace('-', ' ').title())
        
        initial_data = {}
        if initial_title:
            initial_data['title'] = initial_title
        if initial_slug:
            initial_data['slug'] = initial_slug

        form = WikiPageForm(initial=initial_data)

        if initial_title and not WikiPage.objects.filter(Q(slug=initial_slug) | Q(title__iexact=initial_title)).exists():
            messages.info(request, f"The page '{initial_title}' does not exist. You can create it now.")

    return render(request, 'wiki/pages/wiki_form.html', {'form': form, 'action': 'Create'})


@login_required
def page_edit(request, slug):
    page = get_object_or_404(WikiPage, slug=slug)
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

    page_files = page.files.all().order_by('-uploaded_at')
    upload_form = WikiFileForm()
    return render(request, 'wiki/pages/wiki_form.html', {
        'form': form, 'page': page, 'action': 'Edit',
        'page_files': page_files, 'upload_form': upload_form,
    })


@login_required
def page_delete(request, slug):
    page = get_object_or_404(WikiPage, slug=slug)
    if request.method == 'POST':
        page_title = page.title
        
        click_url = request.build_absolute_uri(reverse('wiki:wiki'))
        services.send_ntfy_notification(
            title="Wiki Page Deleted",
            message=f"The wiki page '{page_title}' was deleted by {request.user.username}.",
            click_url=click_url,
            tags="wastebasket,warning"
        )
        
        page.delete()
        messages.success(request, f"Page '{page_title}' deleted successfully.")
        return redirect('wiki:wiki')

    return render(request, 'wiki/pages/page_confirm_delete.html', {'page': page})


@login_required
def page_upload_file(request, slug):
    page = get_object_or_404(WikiPage, slug=slug)
    if request.method == 'POST':
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
                'delete_url': reverse('wiki:page_delete_file', kwargs={'slug': page.slug, 'file_id': wiki_file.id})
            }
            return JsonResponse({'status': 'success', 'file': file_data})
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
    return HttpResponseBadRequest("Invalid request method")


@login_required
def page_delete_file(request, slug, file_id):
    if request.method != 'POST':
        return HttpResponseBadRequest("Invalid request method")
    
    file_to_delete = get_object_or_404(WikiFile, id=file_id, page__slug=slug)
    filename = file_to_delete.filename_display
    file_to_delete.delete()
    return JsonResponse({'status': 'success', 'message': f"File '{filename}' deleted successfully."})

@login_required
def page_download_file(request, slug, file_id):
    wiki_file = get_object_or_404(WikiFile, id=file_id, page__slug=slug)
    file_path = wiki_file.file.path
    if not os.path.exists(file_path):
        raise Http404("File does not exist.")

    mime_type, _ = mimetypes.guess_type(file_path)
    response = HttpResponse(wiki_file.file.read(), content_type=mime_type or 'application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{wiki_file.filename_display}"'
    return response


@login_required
def view_image_in_archive(request, file_id):
    wiki_file = get_object_or_404(WikiFile, pk=file_id)
    image_path = request.GET.get('path')

    if not image_path or '..' in image_path or image_path.startswith('/'):
        return HttpResponseBadRequest("Invalid or missing 'path' parameter.")

    _root, image_ext = os.path.splitext(image_path)
    is_heic = image_ext.lower() in ['.heic', '.heif']

    if is_heic:
        cache_key = f"heic-png:{wiki_file.id}:{hashlib.md5(image_path.encode()).hexdigest()}"
        cached_png_bytes = cache.get(cache_key)
        if cached_png_bytes:
            return HttpResponse(cached_png_bytes, content_type='image/png')
    
    image_bytes = services.get_image_bytes_from_archive(wiki_file, image_path)
    if not image_bytes:
        raise Http404(f"Image '{image_path}' not found in archive or archive is invalid.")
    
    if is_heic:
        try:
            png_bytes = services.convert_heic_to_png_bytes(image_bytes)
            cache.set(cache_key, png_bytes, timeout=settings.HEIC_CACHE_DURATION)
            return HttpResponse(png_bytes, content_type='image/png')
        except Exception as e:
            raise Http404(f"Failed to convert HEIC image: {e}")
    else:
        content_type, _ = mimetypes.guess_type(image_path)
        return HttpResponse(image_bytes, content_type=content_type or 'application/octet-stream')