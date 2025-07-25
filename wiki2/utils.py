# wiki/utils.py
from django.urls import reverse, NoReverseMatch
from .models import WikiPage
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
from urllib.parse import urlencode, parse_qsl, quote
from django.core.cache import cache
import zipfile
import tarfile
from django.template.loader import render_to_string


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

    if current_page:
        page_files_list = list(current_page.files.all())

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
            return f'<span class="filelink-missing" title="File not found on this page: {escaped_target_for_titles}">{display_link_text} (file not found)</span>'
        else:
            try:
                create_slug_param = slugify(target_path_or_url)
                create_title_param = target_path_or_url.replace('-', ' ').title()
                create_url = reverse('wiki:page_create') + f'?initial_title_str={create_title_param}&initial_slug_str={create_slug_param}'
                return f'<a href="{create_url}" class="wikilink-missing" title="Create page: {escaped_target_for_titles}">{display_link_text} (create)</a>'
            except NoReverseMatch:
                return f'<span class="wikilink-error" title="Link target not found and create URL error: {escaped_target_for_titles}">{display_link_text} (link error)</span>'

    return replacer

def _parse_pdf_embed_params(param_string):
    """
    Safely parses a string of parameters (e.g., "page=5&toolbar=0")
    into a URL-encoded string, only allowing a specific set of keys.
    """
    if not param_string:
        return ""
    ALLOWED_PDF_PARAMS = ['page', 'zoom', 'view', 'toolbar', 'navpanes', 'scrollbar']
    params = parse_qsl(param_string)
    safe_params = {key: value for key, value in params if key in ALLOWED_PDF_PARAMS}
    return urlencode(safe_params)

def _get_image_list_from_archive(wiki_file):
    """
    Inspects an archive file (zip, tar) in memory. If it contains ONLY 
    allowed image types, it returns a sorted list of their paths. 
    Otherwise, it returns None.
    """
    archive_filename = wiki_file.file.name
    _, archive_ext = os.path.splitext(archive_filename.lower())
    PICTURE_EXTENSIONS = tuple(constants.WIKI_PICTURE_EXTENSIONS)

    image_paths = []
    try:
        with wiki_file.file.open('rb') as file_obj:
            all_files_are_images = True
            
            if archive_ext == '.zip':
                with zipfile.ZipFile(file_obj, 'r') as zf:
                    file_list = [f for f in zf.namelist() if not f.endswith('/') and not f.startswith('__MACOSX')]
                    if not file_list: return None
                    for name in file_list:
                        if name.lower().endswith(PICTURE_EXTENSIONS):
                            image_paths.append(name)
                        else:
                            all_files_are_images = False; break
            
            elif archive_ext in ['.tar', '.gz', '.bz2', '.xz']:
                with tarfile.open(fileobj=file_obj, mode='r:*') as tf:
                    member_list = [m for m in tf.getmembers() if m.isfile()]
                    if not member_list: return None
                    for member in member_list:
                        if member.name.lower().endswith(PICTURE_EXTENSIONS):
                            image_paths.append(member.name)
                        else:
                            all_files_are_images = False; break
            
            return sorted(image_paths) if all_files_are_images else None
    except (zipfile.BadZipFile, tarfile.TarError):
        return None
    
def markdown_image_replacer_factory(current_page=None):
    if not current_page:
        def no_page_image_replacer(match): return match.group(0)
        return no_page_image_replacer

    page_files_list = list(current_page.files.all())
    ARCHIVE_EXTENSIONS = tuple(constants.WIKI_ARCHIVE_EXTENSIONS)

    def image_replacer(match):
        alt_text = match.group(1)
        src_text = match.group(2).strip()
        title_text = match.group(3) or match.group(4)
        escaped_alt_text = escape(alt_text)

        if src_text.startswith(('http://', 'https://', '//', '/')):
            return match.group(0)

        attached_file = None
        src_stem, src_ext = os.path.splitext(src_text)
        src_ext = src_ext.lower()
        for pf in page_files_list:
            if pf.filename_display.lower() == src_text.lower(): attached_file = pf; break
            if not src_ext and pf.filename_slug.lower() == src_text.lower(): attached_file = pf; break
            elif src_ext:
                _, pf_actual_ext = os.path.splitext(pf.file.name)
                if pf.filename_slug.lower() == src_stem.lower() and pf_actual_ext.lower() == src_ext:
                    attached_file = pf; break
        
        if attached_file:
            try:
                file_url = attached_file.file.url
                file_ext_lower = os.path.splitext(attached_file.file.name)[1].lower()

                if file_ext_lower in ARCHIVE_EXTENSIONS:
                    cache_key = f'wiki_gallery_{attached_file.id}_{attached_file.uploaded_at.timestamp()}'
                    image_list = cache.get(cache_key)
                    
                    if image_list is None:
                        image_list = _get_image_list_from_archive(attached_file)
                        cache.set(cache_key, image_list, timeout=3600)
                    
                    if image_list:
                        context = {
                            'images': [],
                            'alt_text': escaped_alt_text,
                        }
                        for image_path in image_list:
                            img_src_url = reverse('wiki:view_image_in_archive', args=[attached_file.id]) + f'?path={quote(image_path)}'
                            img_name = os.path.basename(image_path)
                            context['images'].append({'url': img_src_url, 'path': image_path, 'name': img_name})
                        
                        return render_to_string('wiki/modules/_archive_gallery.html', context)
                    else:
                        return f'<a href="{file_url}" class="filelink" target="_blank" title="Download archive: {escape(attached_file.filename_display)}">{escaped_alt_text or escape(attached_file.filename_display)}</a>'

                elif file_ext_lower == '.pdf':
                    pdf_params = _parse_pdf_embed_params(title_text)
                    iframe_src = f"{file_url}#{pdf_params}" if pdf_params else file_url
                    return f'''<div class="pdf-embed-container">
                                   <iframe src="{iframe_src}" title="Embedded PDF: {escaped_alt_text}">
                                       <p>Your browser does not support embedded PDFs. Please <a href="{file_url}" target="_blank">download the PDF</a> to view it.</p>
                                   </iframe>
                               </div>'''
                
                else:
                    title_part = f' "{escape(title_text)}"' if title_text else ""
                    return f'![{escaped_alt_text}]({file_url}{title_part})'
            
            except Exception as e:
                return f'<span class="filelink-error" title="Error processing file: {escape(src_text)}">File: {escaped_alt_text} (processing error: {e})</span>'
        else:
            return f'<span class="filelink-missing" title="File not found on page: {escape(src_text)}">File: {escaped_alt_text} (not found)</span>'

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