# wiki2/services.py
import os
import re
import zipfile
import tarfile
import tempfile
import hashlib
from io import BytesIO

import markdown2
from requests import post
from heic2png import HEIC2PNG # pyright: ignore[reportMissingImports] # INFO: Fake ass warning
from urllib.parse import quote, urlencode, parse_qsl

from django.db.models import Q
from django.urls import reverse, NoReverseMatch
from django.utils.html import escape
from django.utils.text import slugify
from django.conf import settings
from django.core.cache import cache
from django.template.loader import render_to_string

from .models import WikiPage, WikiFile
from . import constants

# --- Notification Service ---

def send_ntfy_notification(title, message, click_url, priority="3", tags=""):
    """Sends a notification to the configured ntfy.sh topic."""
    if not all([settings.NTFY_BASE_URL, settings.NTFY_TOPIC]):
        return # Silently fail if not configured

    headers = {"Title": title, "Priority": str(priority)}
    if tags:
        headers["Tags"] = tags
    if click_url:
        headers["Click"] = click_url

    try:
        post(f"{settings.NTFY_BASE_URL}{settings.NTFY_TOPIC}", data=message, headers=headers)
    except Exception:
        # Log the error in a real application
        pass


# --- Image and Archive Services ---

def convert_heic_to_png_bytes(heic_bytes: bytes) -> bytes:
    """Converts HEIC image bytes to PNG bytes, using temporary files."""
    tmp_heic_path = None
    output_png_path = None
    try:
        # Create a temporary file to write the HEIC bytes
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.heic', delete=False) as tmp_heic:
            tmp_heic.write(heic_bytes)
            tmp_heic_path = tmp_heic.name

        # Convert the temporary HEIC file to PNG
        heic_img = HEIC2PNG(tmp_heic_path, quality=90)
        heic_img.save()

        output_png_path = os.path.splitext(tmp_heic_path)[0] + '.png'

        # Read the resulting PNG file back into bytes
        with open(output_png_path, 'rb') as png_file:
            return png_file.read()
    finally:
        # Clean up temporary files
        if tmp_heic_path and os.path.exists(tmp_heic_path):
            os.remove(tmp_heic_path)
        if output_png_path and os.path.exists(output_png_path):
            os.remove(output_png_path)


def get_image_bytes_from_archive(wiki_file: WikiFile, image_path: str) -> bytes | None:
    """Extracts a single file's bytes from a zip or tar archive."""
    archive_filename = wiki_file.file.name
    _, archive_ext = os.path.splitext(archive_filename.lower())
    image_bytes = None

    try:
        with wiki_file.file.open('rb') as archive_file_obj:
            if archive_ext == '.zip':
                with zipfile.ZipFile(archive_file_obj, 'r') as zf:
                    if image_path in zf.namelist():
                        image_bytes = zf.read(image_path)
            elif archive_ext in ['.tar', '.gz', '.bz2', '.xz']:
                with tarfile.open(fileobj=archive_file_obj, mode='r:*') as tf:
                    for member in tf.getmembers():
                        if member.name == image_path and member.isfile():
                            extracted_file = tf.extractfile(member)
                            if extracted_file:
                                image_bytes = extracted_file.read()
                            break
        return image_bytes
    except (zipfile.BadZipFile, tarfile.TarError):
        # Log this error in a real app
        return None


def get_image_list_from_archive(wiki_file: WikiFile) -> list[str] | None:
    """Inspects an archive and returns a sorted list of all file paths within it."""
    archive_filename = wiki_file.file.name
    _, archive_ext = os.path.splitext(archive_filename.lower())
    paths = []
    try:
        with wiki_file.file.open('rb') as file_obj:
            if archive_ext == '.zip':
                with zipfile.ZipFile(file_obj, 'r') as zf:
                    paths = [f for f in zf.namelist() if not f.endswith('/') and not f.startswith('__MACOSX')]
            elif archive_ext in ['.tar', '.gz', '.bz2', '.xz']:
                with tarfile.open(fileobj=file_obj, mode='r:*') as tf:
                    paths = [m.name for m in tf.getmembers() if m.isfile()]
        return sorted(paths)
    except (zipfile.BadZipFile, tarfile.TarError):
        return None


# --- Markdown Processing Service (Major Refactor) ---

def _parse_pdf_embed_params(param_string: str) -> str:
    """Safely parses a string of parameters for PDF embedding."""
    if not param_string:
        return ""
    ALLOWED_PDF_PARAMS = ['page', 'zoom', 'view', 'toolbar', 'navpanes', 'scrollbar']
    params = parse_qsl(param_string)
    safe_params = {key: value for key, value in params if key in ALLOWED_PDF_PARAMS}
    return urlencode(safe_params)


def render_markdown_to_html(markdown_text: str, current_page: WikiPage) -> str:
    """
    Efficiently processes Markdown text by pre-fetching all potential links
    and files from the database in batches, avoiding N+1 query problems.
    """
    # --- Pass 1: Collect all potential link and file targets from the text ---
    wikilink_targets = {match.group(2).strip() for match in constants.WIKILINK_RE.finditer(markdown_text)}
    
    md_link_targets = set()
    for match in constants.STANDARD_MARKDOWN_LINK_RE.finditer(markdown_text):
        target = match.group(2).strip()
        if not target.startswith(('http', '//', '/')):
            md_link_targets.add(target)

    image_targets = set()
    for match in constants.MARKDOWN_IMAGE_RE.finditer(markdown_text):
        target = match.group(2).strip()
        if not target.startswith(('http', '//', '/')):
            image_targets.add(target)

    # --- Pass 2: Batch query the database for all collected targets ---
    all_page_targets = {slugify(t) for t in wikilink_targets | md_link_targets}
    all_page_titles = wikilink_targets | md_link_targets
    
    resolved_pages = WikiPage.objects.filter(
        Q(slug__in=all_page_targets) | Q(title__in=all_page_titles)
    )
    # Create lookup dictionaries for fast access
    pages_by_slug = {p.slug: p for p in resolved_pages}
    pages_by_title = {p.title.lower(): p for p in resolved_pages}

    all_file_targets = md_link_targets | image_targets
    page_files = current_page.files.all()
    # Create lookup dictionaries for files attached to the current page
    files_by_name = {pf.filename_display.lower(): pf for pf in page_files}
    files_by_slug = {pf.filename_slug.lower(): pf for pf in page_files}

    # --- Pass 3: Define replacer functions that use the pre-fetched data ---

    def wikilink_replacer(match):
        link_text_group = match.group(1)
        target_group = match.group(2).strip()
        display_text = escape(link_text_group.strip() if link_text_group else target_group)

        page = pages_by_title.get(target_group.lower()) or pages_by_slug.get(slugify(target_group))
        if page:
            return f'<a href="{page.get_absolute_url()}" class="wikilink">{display_text}</a>'
        else:
            create_url = reverse('wiki:page_create') + f'?initial_title_str={quote(target_group)}'
            return f'<a href="{create_url}" class="wikilink-missing" title="Create page: {escape(target_group)}">{display_text} (create)</a>'

    def markdown_link_replacer(match):
        display_text = escape(match.group(1))
        target = match.group(2).strip()

        # External links are returned as-is
        if target.startswith(('http://', 'https://', '//', '/')):
            return match.group(0)
        
        # Check for WikiPage link
        page = pages_by_title.get(target.lower()) or pages_by_slug.get(slugify(target))
        if page:
            return f'<a href="{page.get_absolute_url()}" class="wikilink">{display_text}</a>'

        # Check for attached file link
        file = files_by_name.get(target.lower()) or files_by_slug.get(os.path.splitext(target)[0].lower())
        if file:
            return f'<a href="{file.file.url}" class="filelink" target="_blank" title="View file: {escape(file.filename_display)}">{display_text}</a>'

        # If not found, assume it's a link to a missing page
        create_url = reverse('wiki:page_create') + f'?initial_title_str={quote(target)}'
        return f'<a href="{create_url}" class="wikilink-missing" title="Create page: {escape(target)}">{display_text} (create)</a>'

    def image_replacer(match):
        alt_text, src, title = escape(match.group(1)), match.group(2).strip(), match.group(3) or match.group(4)
        
        if src.startswith(('http', '//', '/')):
            return match.group(0)

        file = files_by_name.get(src.lower()) or files_by_slug.get(os.path.splitext(src)[0].lower())
        if not file:
            return f'<span class="filelink-missing" title="File not found on page: {escape(src)}">Image: {alt_text} (not found)</span>'

        file_url = file.file.url
        file_ext = os.path.splitext(file.file.name)[1].lower()

        # Handle image archives
        if file_ext in constants.WIKI_ARCHIVE_EXTENSIONS:
            cache_key = f'wiki_gallery_{file.id}_{file.uploaded_at.timestamp()}'
            image_list = cache.get(cache_key)
            if image_list is None:
                image_list = get_image_list_from_archive(file)
                cache.set(cache_key, image_list, timeout=3600)
            
            if image_list:
                context = {'images': [], 'alt_text': alt_text}
                for image_path in image_list:
                    img_src_url = reverse('wiki:view_image_in_archive', args=[file.id]) + f'?path={quote(image_path)}'
                    context['images'].append({'url': img_src_url, 'name': os.path.basename(image_path)})
                return render_to_string('wiki/modules/_archive_gallery.html', context)
            else: # Archive is not a valid image gallery
                return f'<a href="{file_url}" class="filelink" target="_blank">{alt_text or escape(file.filename_display)}</a>'

        # Handle PDF embeds
        elif file_ext == '.pdf':
            pdf_params = _parse_pdf_embed_params(title)
            iframe_src = f"{file_url}#{pdf_params}"
            return f'''<div class="pdf-embed-container">
                           <iframe src="{iframe_src}" title="Embedded PDF: {alt_text}"></iframe>
                       </div>'''
        
        # Handle standard images
        else:
            title_part = f' title="{escape(title)}"' if title else ""
            return f'<img src="{file_url}" alt="{alt_text}"{title_part}>'
    
    # --- Final Step: Apply replacements, skipping code blocks ---
    
    processed_parts = []
    last_end = 0
    # Process text outside of code blocks
    for match in constants.CODE_PATTERN_RE.finditer(markdown_text):
        # Process the segment before the code block
        text_before_code = markdown_text[last_end:match.start()]
        text_before_code = constants.WIKILINK_RE.sub(wikilink_replacer, text_before_code)
        text_before_code = constants.MARKDOWN_IMAGE_RE.sub(image_replacer, text_before_code)
        text_before_code = constants.STANDARD_MARKDOWN_LINK_RE.sub(markdown_link_replacer, text_before_code)
        processed_parts.append(text_before_code)
        
        # Add the code block itself, unprocessed
        processed_parts.append(match.group(0))
        last_end = match.end()

    # Process the final segment after the last code block
    text_after = markdown_text[last_end:]
    text_after = constants.WIKILINK_RE.sub(wikilink_replacer, text_after)
    text_after = constants.MARKDOWN_IMAGE_RE.sub(image_replacer, text_after)
    text_after = constants.STANDARD_MARKDOWN_LINK_RE.sub(markdown_link_replacer, text_after)
    processed_parts.append(text_after)

    final_markdown = "".join(processed_parts)
    
    return markdown2.markdown(final_markdown, extras=["fenced-code-blocks", "tables", "nofollow", "header-ids", "break-on-newline", "html-classes"])