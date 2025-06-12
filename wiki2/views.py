# wiki/views.py
import os
import mimetypes
import markdown2
from . import utils
from . import constants
from urllib.parse import urlencode
from .models import WikiPage, WikiFile, ExamPage
from .forms import WikiPageForm, WikiFileForm, ExamPageForm

from django.urls import reverse
from django.http import Http404, HttpResponse, JsonResponse, FileResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.text import slugify


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

def all_wiki_pages(request):
    pages = WikiPage.objects.all().order_by('-updated_at')
    return render(request, 'wiki/pages/wiki_list.html', {'pages': pages, 'list_title': "All Wiki Pages"})

def wiki_page(request, slug):
    try:
        page = WikiPage.objects.get(slug=slug)
        exam_subpages = page.exam_subpages.all().order_by('created_at')
        processed_markdown_content = utils.preprocess_markdown_with_links(page.content, current_page=page)
        html_content = markdown2.markdown(processed_markdown_content, extras=["fenced-code-blocks", "tables", "nofollow", "header-ids", "break-on-newline"])
        qr = utils.qr_img(request)
        page_files = page.files.all().order_by('-uploaded_at')

        return render(request, 'wiki/pages/wiki_page.html', {
            'page': page,
            'html_content': html_content,
            'qrcode': qr,
            'page_files': page_files,
            'exam_subpages': exam_subpages,
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
    exam_subpages = page.exam_subpages.all().order_by('created_at')

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
        'exam_subpages': exam_subpages,
    })

@login_required
def page_delete(request, slug):
    page = get_object_or_404(WikiPage, slug=slug)
    if request.method == 'POST':
        page_title = page.title
        page.delete()
        messages.success(request, f"Page '{page_title}' deleted successfully.")
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

@login_required
def exam_create(request, parent_slug):
    parent_page = get_object_or_404(WikiPage, slug=parent_slug)

    if request.method == 'POST':
        form = ExamPageForm(request.POST, parent_page=parent_page)
        if form.is_valid():
            exam = form.save(commit=False)
            exam.parent_page = parent_page
            exam.last_modified_by = request.user
            exam.save()

            success, message = exam.compile_and_save_pdf(force_recompile=True)
            if success:
                messages.success(request, f"Exam '{exam.title}' created. {message}")
            else:
                messages.warning(request, f"Exam '{exam.title}' created, but PDF generation failed: {message}")
            return redirect(parent_page.get_absolute_url())
    else:
        now_str = timezone.now().strftime("%b %d, %Y")
        default_slug_date_str = timezone.now().strftime("%d-%m-%Y")

        default_title = f"Exam {parent_page.title}: {now_str}"
        default_slug = f"{parent_page.slug}-{default_slug_date_str}"

        initial_data = {
            'title': default_title,
            'slug': default_slug,
        }
        form = ExamPageForm(initial=initial_data, parent_page=parent_page)

    return render(request, 'wiki/pages/exam_form.html', {
        'form': form,
        'parent_page': parent_page,
        'action': 'Create',
        'exam': None,
    })

@login_required
def exam_edit(request, parent_slug, exam_slug):
    parent_page = get_object_or_404(WikiPage, slug=parent_slug)
    exam = get_object_or_404(ExamPage, parent_page=parent_page, slug=exam_slug)

    if request.method == 'POST':
        form = ExamPageForm(request.POST, instance=exam, parent_page=parent_page)
        if form.is_valid():
            edited_exam = form.save(commit=False)
            edited_exam.last_modified_by = request.user

            recompile_hint = False
            if 'content' in form.changed_data or 'page_type' in form.changed_data:
                recompile_hint = True

            edited_exam.save()

            success, message = edited_exam.compile_and_save_pdf(force_recompile=recompile_hint)
            if success:
                messages.success(request, f"Exam '{edited_exam.title}' updated. {message}")
            else:
                messages.warning(request, f"Exam '{edited_exam.title}' updated, but PDF processing failed: {message}")
            return redirect(parent_page.get_absolute_url())
    else:
        form = ExamPageForm(instance=exam, parent_page=parent_page)

    return render(request, 'wiki/pages/exam_form.html', {
        'form': form,
        'exam': exam,
        'parent_page': parent_page,
        'action': 'Edit'
    })

@login_required
def exam_delete(request, parent_slug, exam_slug):
    parent_page = get_object_or_404(WikiPage, slug=parent_slug)
    exam = get_object_or_404(ExamPage, parent_page=parent_page, slug=exam_slug)
    if request.method == 'POST':
        exam_title = exam.title
        exam.delete()
        messages.success(request, f"Exam '{exam_title}' deleted successfully.")
        return redirect(parent_page.get_absolute_url())
    return render(request, 'wiki/pages/exam_confirm_delete.html', {'exam': exam, 'parent_page': parent_page})

def exam_download(request, parent_slug, exam_slug):
    exam = get_object_or_404(ExamPage, parent_page__slug=parent_slug, slug=exam_slug)

    if not exam.pdf_file or not os.path.exists(exam.pdf_file.path):
        messages.info(request, f"PDF for '{exam.title}' was missing, attempting to regenerate...")
        success, msg = exam.compile_and_save_pdf(force_recompile=True)
        if not success or not exam.pdf_file or not os.path.exists(exam.pdf_file.path):
            messages.error(request, f"Could not generate or find PDF for '{exam.title}'. Error: {msg}")
            return redirect(exam.parent_page.get_absolute_url())
        exam.refresh_from_db()


    try:
        return FileResponse(open(exam.pdf_file.path, 'rb'), as_attachment=True, filename=exam._get_base_pdf_filename())
    except FileNotFoundError:
        messages.error(request, f"PDF file for '{exam.title}' not found on the server, even after trying to regenerate.")
        return redirect(exam.parent_page.get_absolute_url())
    except Exception as e:
        messages.error(request, f"Error serving PDF for '{exam.title}': {e}")
        return redirect(exam.parent_page.get_absolute_url())

def exam(request, parent_slug, exam_slug):
    exam = get_object_or_404(ExamPage, parent_page__slug=parent_slug, slug=exam_slug)

    if not exam.pdf_file or not os.path.exists(exam.pdf_file.path):
        messages.info(request, f"PDF for '{exam.title}' was missing, attempting to regenerate...")
        success, msg = exam.compile_and_save_pdf(force_recompile=True)
        if not success or not exam.pdf_file or not os.path.exists(exam.pdf_file.path):
            messages.error(request, f"Could not generate or find PDF for '{exam.title}'. Error: {msg}")
            return redirect(exam.parent_page.get_absolute_url())
        exam.refresh_from_db()


    try:
        return FileResponse(open(exam.pdf_file.path, 'rb'), filename=exam._get_base_pdf_filename())
    except FileNotFoundError:
        messages.error(request, f"PDF file for '{exam.title}' not found on the server, even after trying to regenerate.")
        return redirect(exam.parent_page.get_absolute_url())
    except Exception as e:
        messages.error(request, f"Error serving PDF for '{exam.title}': {e}")
        return redirect(exam.parent_page.get_absolute_url())