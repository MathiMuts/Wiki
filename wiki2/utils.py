# wiki/utils.py
from django.urls import reverse, NoReverseMatch
from .models import WikiPage, ExamPage
from django.utils.text import slugify
from django.db.models import Q
from io import BytesIO
import qrcode
import base64
import re
import os
from django.utils.html import escape
from django.conf import settings
from . import constants

def escape_markdown_chars(text):
    if not text:
        return ""
    chars_to_escape = r"([\\`*_{}\[\]()#+.!-])"
    return re.sub(chars_to_escape, r"\\\1", text)

def wikilink_replacer_factory(current_page=None):
    def wikilink_replacer(match):
        link_text_group = match.group(1)
        target_group = match.group(2).strip()

        raw_link_text = target_group
        if link_text_group:
            raw_link_text = link_text_group.strip()

        display_link_text = escape(escape_markdown_chars(raw_link_text))

        safe_target_for_url = slugify(target_group)
        escaped_target_group_for_title = escape(target_group)

        try:
            page = WikiPage.objects.get(title__iexact=target_group)
            url = page.get_absolute_url()
            return f'<a href="{url}" class="wikilink">{display_link_text}</a>'
        except WikiPage.DoesNotExist:
            try:
                page = WikiPage.objects.get(slug=slugify(target_group))
                url = page.get_absolute_url()
                return f'<a href="{url}" class="wikilink">{display_link_text}</a>'
            except WikiPage.DoesNotExist:
                try:
                    create_url = reverse('wiki:page_create') + f'?title={safe_target_for_url}'
                    return f'<a href="{create_url}" class="wikilink-missing" title="Create page: {escaped_target_group_for_title}">{display_link_text} (create)</a>'
                except NoReverseMatch:
                    return f'<span class="wikilink-error" title="Page not found and create URL error: {escaped_target_group_for_title}">{display_link_text} (page not found, URL error)</span>'
        except WikiPage.MultipleObjectsReturned:
            pages = WikiPage.objects.filter(Q(title__iexact=target_group) | Q(slug=slugify(target_group))).order_by('-updated_at')
            if pages.exists():
                page = pages.first()
                url = page.get_absolute_url()
                return f'<a href="{url}" class="wikilink">{display_link_text}</a>'
            else:
                create_url = reverse('wiki:page_create') + f'?title={safe_target_for_url}'
                return f'<a href="{create_url}" class="wikilink-missing" title="Create page: {escaped_target_group_for_title}">{display_link_text} (create)</a>'
    return wikilink_replacer

def standard_markdown_link_replacer_factory(current_page=None):
    page_files_list = []
    exam_subpages_list = []

    if current_page:
        page_files_list = list(current_page.files.all())
        if hasattr(current_page, 'exam_subpages'):
            exam_subpages_list = list(current_page.exam_subpages.all())

    COMMON_FILE_EXTENSIONS = getattr(settings, 'WIKI_COMMON_FILE_EXTENSIONS', constants.DEFAULT_COMMON_FILE_EXTENSIONS)

    def replacer(match):
        link_text_markdown = match.group(1)
        target_path_or_url = match.group(2).strip()

        display_link_text = escape(escape_markdown_chars(link_text_markdown))
        escaped_target_for_titles = escape(target_path_or_url)

        if target_path_or_url.startswith(('http://', 'https://', '//', '/')):
            return match.group(0)

        resolved_page = None
        try:
            resolved_page = WikiPage.objects.get(slug=target_path_or_url)
        except WikiPage.DoesNotExist:
            try:
                resolved_page = WikiPage.objects.get(title__iexact=target_path_or_url)
            except WikiPage.DoesNotExist:
                pass
            except WikiPage.MultipleObjectsReturned:
                pages = WikiPage.objects.filter(title__iexact=target_path_or_url).order_by('-updated_at')
                if pages.exists():
                    resolved_page = pages.first()
        except WikiPage.MultipleObjectsReturned:
            pages = WikiPage.objects.filter(slug=target_path_or_url).order_by('-updated_at')
            if pages.exists():
                resolved_page = pages.first()

        if resolved_page:
            return f'<a href="{resolved_page.get_absolute_url()}" class="wikilink">{display_link_text}</a>'

        if current_page and exam_subpages_list:
            resolved_exam = None
            for exam in exam_subpages_list:
                if exam.slug.lower() == target_path_or_url.lower():
                    resolved_exam = exam
                    break
            if not resolved_exam:
                for exam in exam_subpages_list:
                    if exam.title.lower() == target_path_or_url.lower():
                        resolved_exam = exam
                        break
            
            if resolved_exam and resolved_exam.pdf_file and resolved_exam.pdf_file.name:
                try:
                    exam_pdf_url = resolved_exam.get_download_url() or resolved_exam.get_url()
                    if not exam_pdf_url and resolved_exam.pdf_file:
                        exam_pdf_url = resolved_exam.pdf_file.url

                    if exam_pdf_url:
                        return f'<a href="{exam_pdf_url}" class="filelink exam-pdflink" target="_blank" title="View exam PDF: {escape(resolved_exam.title)}">{display_link_text}</a>'
                except Exception:
                    pass

        if current_page:
            attached_file = None
            link_target_stem, link_target_ext = os.path.splitext(target_path_or_url)
            link_target_ext = link_target_ext.lower()

            for pf in page_files_list:
                if pf.filename_display.lower() == target_path_or_url.lower():
                    attached_file = pf
                    break

                if not link_target_ext:
                    if pf.filename_slug.lower() == target_path_or_url.lower():
                        attached_file = pf
                        break
                    
                    pf_display_stem, _ = os.path.splitext(pf.filename_display)
                    if pf_display_stem.lower() == target_path_or_url.lower():
                        attached_file = pf
                        break
                else:
                    _, pf_actual_ext = os.path.splitext(pf.file.name)
                    pf_actual_ext = pf_actual_ext.lower()
                    
                    if pf.filename_slug.lower() == link_target_stem.lower() and \
                       pf_actual_ext == link_target_ext:
                        attached_file = pf
                        break
            
            if attached_file:
                try:
                    return f'<a href="{attached_file.file.url}" class="filelink" target="_blank" title="View file: {escape(attached_file.filename_display)}">{display_link_text}</a>'
                except Exception:
                    return f'<span class="filelink-error" title="File URL error for {escaped_target_for_titles}">{display_link_text} (URL error)</span>'

        looks_like_file = any(target_path_or_url.lower().endswith(ext) for ext in COMMON_FILE_EXTENSIONS)

        if looks_like_file:
            return f'<span class="filelink-missing" title="File or Exam PDF not found on this page: {escaped_target_for_titles}">{display_link_text} (file not found)</span>'
        else:
            try:
                create_slug_param = slugify(target_path_or_url)
                create_title_param = target_path_or_url.replace('-', ' ').title()
                create_url = reverse('wiki:page_create') + f'?initial_title_str={create_title_param}&initial_slug_str={create_slug_param}'
                return f'<a href="{create_url}" class="wikilink-missing" title="Create page: {escaped_target_for_titles}">{display_link_text} (create)</a>'
            except NoReverseMatch:
                return f'<span class="wikilink-error" title="Link target not found and create URL error: {escaped_target_for_titles}">{display_link_text} (link error)</span>'

    return replacer

def markdown_image_replacer_factory(current_page=None):
    if not current_page:
        def no_page_image_replacer(match):
            return match.group(0)
        return no_page_image_replacer

    page_files_list = list(current_page.files.all())

    def image_replacer(match):
        alt_text = match.group(1)
        src_text = match.group(2).strip()
        escaped_alt_text = escape(alt_text)

        if src_text.startswith(('http://', 'https://', '//', '/')):
            return match.group(0)

        attached_file = None
        
        src_stem, src_ext = os.path.splitext(src_text)
        src_ext = src_ext.lower()

        for pf in page_files_list:
            if pf.filename_display.lower() == src_text.lower():
                attached_file = pf
                break
            
            if not src_ext:
                if pf.filename_slug.lower() == src_text.lower():
                    attached_file = pf
                    break
            else:
                _, pf_actual_ext = os.path.splitext(pf.file.name)
                pf_actual_ext = pf_actual_ext.lower()
                if pf.filename_slug.lower() == src_stem.lower() and pf_actual_ext == src_ext:
                    attached_file = pf
                    break
        
        if attached_file:
            try:
                file_url = attached_file.file.url
                return f'![{escaped_alt_text}]({file_url})'
            except Exception:
                return f'<span class="filelink-error" title="Error resolving URL for image: {escape(src_text)}">Image: {escaped_alt_text} (file URL error)</span>'
        else:
            return f'<span class="filelink-missing" title="Image file not found on this page: {escape(src_text)}">Image: {escaped_alt_text} (file not found)</span>'

    return image_replacer

def preprocess_markdown_with_links(markdown_text, current_page=None):
    processed_parts = []
    last_end = 0

    _wikilink_replacer = wikilink_replacer_factory(current_page)
    _markdown_image_replacer = markdown_image_replacer_factory(current_page)
    _standard_markdown_link_replacer = standard_markdown_link_replacer_factory(current_page)

    for match in constants.CODE_PATTERN_RE.finditer(markdown_text):
        text_before_code = markdown_text[last_end:match.start()]
        
        processed_text_before = constants.WIKILINK_RE.sub(_wikilink_replacer, text_before_code)
        processed_text_before = constants.MARKDOWN_IMAGE_RE.sub(_markdown_image_replacer, processed_text_before)
        processed_text_before = constants.STANDARD_MARKDOWN_LINK_RE.sub(_standard_markdown_link_replacer, processed_text_before)
        
        processed_parts.append(processed_text_before)
        processed_parts.append(match.group(0))
        last_end = match.end()

    text_after_last_code = markdown_text[last_end:]
    processed_text_after = constants.WIKILINK_RE.sub(_wikilink_replacer, text_after_last_code)
    processed_text_after = constants.MARKDOWN_IMAGE_RE.sub(_markdown_image_replacer, processed_text_after)
    processed_text_after = constants.STANDARD_MARKDOWN_LINK_RE.sub(_standard_markdown_link_replacer, processed_text_after)
    
    processed_parts.append(processed_text_after)

    return "".join(processed_parts)

def qr_img(request):
    current_url = request.build_absolute_uri()
    qr = qrcode.QRCode(box_size=5, border=0, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(current_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    img_base64 = base64.b64encode(buffer.getvalue()).decode()
    return img_base64