from django.urls import reverse, NoReverseMatch
from django.utils.text import slugify
from django.db.models import Q
from .models import WikiPage, WikiFile 
from io import BytesIO
import qrcode
import base64
import re
import os
from django.utils.html import escape
from django.utils.html import escape
from django.conf import settings

CODE_PATTERN_RE = re.compile(
    r"("
    r"(?:^```[^\n]*\n(?:.|\n)*?^\s*```$)"
    r"|(?:^~~~[^\n]*\n(?:.|\n)*?^\s*~~~$)"
    r"|(?P<ticks>`+)(?:(?!(?P=ticks)).|\n)*?(?P=ticks)"
    r")",
    re.MULTILINE
)
WIKILINK_RE = re.compile(r"\[\[(?:([^|\]]+)\|)?([^\]]+)\]\]")
FILELINK_RE = re.compile(r"\{\{(?:([^|}]+\|))?([^}]+)\}\}") 
MARKDOWN_IMAGE_RE = re.compile(r"!\[(.*?)\]\((.*?)(?:\s+(['\"])(.*?)\3)?\)")

def escape_markdown_chars(text):
    if not text:
        return ""
    # Characters to escape: *, _, `, [, ], (, ), #, +, -, ., !
    # Note: Escaping . and - might be too aggressive depending on context.
    # Let's focus on the most common ones for emphasis, links, code.
    # \ must be escaped first!
    chars_to_escape = r"([\\`*_{}\[\]()#+.!-])" # Added hyphen
    return re.sub(chars_to_escape, r"\\\1", text)

  
def wikilink_replacer_factory(current_page=None):
    def wikilink_replacer(match):
        link_text_group = match.group(1)
        target_group = match.group(2).strip()

        raw_link_text = target_group 
        if link_text_group:
            raw_link_text = link_text_group.strip()
        
        # First, escape Markdown characters in the raw link text
        # Then, escape HTML special characters for safe insertion into HTML
        display_link_text = escape(escape_markdown_chars(raw_link_text))

        safe_target_for_url = slugify(target_group)
        escaped_target_group_for_title = escape(target_group) # For use in title attributes

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


def filelink_replacer_factory(current_page=None):
    if not current_page:
        def no_page_replacer(match):
            target_filename = match.group(2).strip()
            raw_link_text = match.group(1).strip().rstrip('|').strip() if match.group(1) else target_filename
            display_link_text = escape(escape_markdown_chars(raw_link_text))
            return f'<span class="filelink-error" title="File link context error: {escape(target_filename)}">{display_link_text} (page context unavailable)</span>'
        return no_page_replacer

    def filelink_replacer(match):
        link_text_group = match.group(1) 
        target_filename_from_tag = match.group(2).strip()

        raw_link_text = target_filename_from_tag 
        if link_text_group:
            raw_link_text = link_text_group.strip().rstrip('|').strip()
        
        display_link_text = escape(escape_markdown_chars(raw_link_text))
        
        target_slug_part, target_ext_part = os.path.splitext(target_filename_from_tag)
        target_ext_part = target_ext_part.lower()
        escaped_target_filename_for_title = escape(target_filename_from_tag)

        attached_file = None
        page_files = current_page.files.all()

        for pf in page_files:
            if pf.filename_display.lower() == target_filename_from_tag.lower():
                attached_file = pf
                break
            if not target_ext_part and pf.filename_slug.lower() == target_slug_part.lower():
                attached_file = pf
                break
            if target_ext_part:
                _pf_name, pf_ext = os.path.splitext(pf.file.name)
                if pf.filename_slug.lower() == target_slug_part.lower() and pf_ext.lower() == target_ext_part:
                    attached_file = pf
                    break
        
        if attached_file:
            try:
                return f'<a href="{attached_file.file.url}" class="filelink" target="_blank" title="View file: {escape(attached_file.filename_display)}">{display_link_text}</a>'
            except NoReverseMatch:
                 return f'<span class="filelink-error" title="File URL error for {escaped_target_filename_for_title}">{display_link_text} (URL error)</span>'
        else:
            return f'<span class="filelink-missing" title="File not found on this page: {escaped_target_filename_for_title}">{display_link_text} (file not found)</span>'

    return filelink_replacer


def markdown_image_replacer_factory(current_page=None):
    if not current_page:
        def no_page_image_replacer(match):
            return match.group(0)
        return no_page_image_replacer

    def image_replacer(match):
        alt_text = match.group(1)
        src_text = match.group(2).strip()

        escaped_alt_text = escape(alt_text)

        if src_text.startswith(('http://', 'https://', '//', '/')):
            return match.group(0)

        target_filename_slug = src_text
        
        attached_file = None
        page_files = current_page.files.all()
        potential_slug, potential_ext = os.path.splitext(target_filename_slug)
        potential_ext = potential_ext.lower()

        for pf in page_files:
            if pf.filename_slug == target_filename_slug:
                attached_file = pf
                break
        
        if not attached_file:
            for pf in page_files:
                 if pf.filename_slug.lower() == target_filename_slug.lower():
                    attached_file = pf
                    break
        
        if not attached_file:
            for pf in page_files:
                if pf.filename_display.lower() == target_filename_slug.lower():
                    attached_file = pf
                    break
        
        if not attached_file and not potential_ext:
            for pf in page_files:
                if pf.filename_slug.lower() == potential_slug.lower():
                    attached_file = pf
                    break


        if attached_file:
            try:
                file_url = attached_file.file.url
                return f'![{escaped_alt_text}]({file_url})'
            except Exception:
                return f'<span class="filelink-error" title="Error resolving URL for image: {escape(target_filename_slug)}">Image: {escaped_alt_text} (file URL error)</span>'
        else:
            return f'<span class="filelink-missing" title="Image file not found on this page: {escape(target_filename_slug)}">Image: {escaped_alt_text} (file not found)</span>'

    return image_replacer


def preprocess_markdown_with_links(markdown_text, current_page=None):
    processed_parts = []
    last_end = 0

    _wikilink_replacer = wikilink_replacer_factory(current_page)
    _filelink_replacer = filelink_replacer_factory(current_page)

    _markdown_image_replacer = markdown_image_replacer_factory(current_page)

    for match in CODE_PATTERN_RE.finditer(markdown_text):
        text_before_code = markdown_text[last_end:match.start()]

        processed_text_before = MARKDOWN_IMAGE_RE.sub(_markdown_image_replacer, text_before_code)
        
        processed_text_before = WIKILINK_RE.sub(_wikilink_replacer, processed_text_before)
        processed_text_before = FILELINK_RE.sub(_filelink_replacer, processed_text_before)
        
        processed_parts.append(processed_text_before)
        processed_parts.append(match.group(0))
        last_end = match.end()

    text_after_last_code = markdown_text[last_end:]

    processed_text_after = MARKDOWN_IMAGE_RE.sub(_markdown_image_replacer, text_after_last_code)
    processed_text_after = WIKILINK_RE.sub(_wikilink_replacer, processed_text_after)
    processed_text_after = FILELINK_RE.sub(_filelink_replacer, processed_text_after)

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