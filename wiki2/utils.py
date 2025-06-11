from django.urls import reverse, NoReverseMatch
from django.utils.text import slugify
from django.db.models import Q
from .models import WikiPage
from io import BytesIO
import qrcode
import base64
import re
import os
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
STANDARD_MARKDOWN_LINK_RE = re.compile(
    r"(?<!\!)"
    r"\[([^\]]+)\]"
    r"\("
    r"([^)\s]+?)"
    r"(?:\s+(['\"])(.*?)\3)?"
    r"\)"
)
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


# def filelink_replacer_factory(current_page=None):
    if not current_page:
        def no_page_replacer(match):
            target_filename = match.group(2).strip()
            raw_link_text = match.group(1).strip().rstrip('|').strip() if match.group(1) else target_filename
            display_link_text = escape(escape_markdown_chars(raw_link_text))
            return f'<span class="filelink-error" title="File link context error: {escape(target_filename)}">{display_link_text} (page context unavailable)</span>'
        return no_page_replacer

    page_files_list = list(current_page.files.all())

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

        for pf in page_files_list:
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

def standard_markdown_link_replacer_factory(current_page=None):
    page_files_list = []
    if current_page:
        page_files_list = list(current_page.files.all())

    COMMON_FILE_EXTENSIONS = getattr(settings, 'WIKI_COMMON_FILE_EXTENSIONS', [
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.txt', '.md', '.markdown', '.csv', '.rtf', '.odt', '.ods', '.odp',
        '.zip', '.tar', '.gz', '.rar', '.7z',
        '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp',
        '.html', '.htm', '.css', '.js', '.json', '.xml', '.py', '.java', '.c', '.cpp', '.h', '.php', '.rb', '.ipynb'
        '.mp3', '.mp4', '.avi', '.mov', '.mkv', '.webm',
    ])

    def replacer(match):
        link_text_markdown = match.group(1)
        target_path_or_url = match.group(2).strip()

        # Escape Markdown in link text, then HTML escape for safe display
        display_link_text = escape(escape_markdown_chars(link_text_markdown))
        escaped_target_for_titles = escape(target_path_or_url) # For use in HTML title attributes

        # 1. Handle External/Absolute/Root-relative links: leave them as is.
        if target_path_or_url.startswith(('http://', 'https://', '//', '/')):
            return match.group(0)

        # 2. Try to resolve as a WikiPage link (target_path_or_url could be a slug or title)
        resolved_page = None
        try:
            # Prefer slug match
            resolved_page = WikiPage.objects.get(slug=target_path_or_url)
        except WikiPage.DoesNotExist:
            try:
                # Fallback to title match (case-insensitive)
                resolved_page = WikiPage.objects.get(title__iexact=target_path_or_url)
            except WikiPage.DoesNotExist:
                pass # Not found as a page by slug or title
            except WikiPage.MultipleObjectsReturned:
                pages = WikiPage.objects.filter(title__iexact=target_path_or_url).order_by('-updated_at')
                if pages.exists():
                    resolved_page = pages.first()
        except WikiPage.MultipleObjectsReturned: # Should be rare for slug, but defensive
            pages = WikiPage.objects.filter(slug=target_path_or_url).order_by('-updated_at')
            if pages.exists():
                resolved_page = pages.first()

        if resolved_page:
            return f'<a href="{resolved_page.get_absolute_url()}" class="wikilink">{display_link_text}</a>'

        # 3. If not a page and current_page context exists, try to resolve as an attached file
        if current_page:
            attached_file = None
            link_target_stem, link_target_ext = os.path.splitext(target_path_or_url)
            link_target_ext = link_target_ext.lower()

            for pf in page_files_list: # pf is a WikiFile instance
                # Match 1: Full target matches filename_display (case-insensitive)
                if pf.filename_display.lower() == target_path_or_url.lower():
                    attached_file = pf
                    break

                # Match 2: If link target has no extension (e.g., [Text](my-document))
                if not link_target_ext: # target_path_or_url is effectively the stem
                    # Match target (as stem) against filename_slug (slug is extensionless)
                    if pf.filename_slug.lower() == target_path_or_url.lower():
                        attached_file = pf
                        break
                    
                    # Match target (as stem) against filename_display's stem,
                    # if filename_display also has no extension.
                    pf_display_stem, pf_display_ext = os.path.splitext(pf.filename_display)
                    if not pf_display_ext and pf_display_stem.lower() == target_path_or_url.lower():
                        attached_file = pf
                        break
                
                # Match 3: If link target has an extension (e.g. [Text](my-document.pdf))
                # (Match 1 already covers if pf.filename_display matches target_path_or_url fully)
                # This is for matching filename_slug against link's stem + actual file ext against link's ext
                else: 
                    _, pf_actual_ext = os.path.splitext(pf.file.name) # Get extension from actual stored file
                    pf_actual_ext = pf_actual_ext.lower()
                    
                    # Compare file's slug with link's stem, and file's actual extension with link's extension
                    if pf.filename_slug.lower() == link_target_stem.lower() and \
                       pf_actual_ext == link_target_ext:
                        attached_file = pf
                        break
            
            if attached_file:
                try:
                    return f'<a href="{attached_file.file.url}" class="filelink" target="_blank" title="View file: {escape(attached_file.filename_display)}">{display_link_text}</a>'
                except Exception: # Catch specific errors if possible, e.g., AttributeError
                    return f'<span class="filelink-error" title="File URL error for {escaped_target_for_titles}">{display_link_text} (URL error)</span>'

        # 4. If not external, not a resolved page, not a resolved file:
        #    Decide how to handle: "missing file" span or "create page" link.
        
        # Heuristic: if target has a common file extension, assume it was meant to be a file.
        looks_like_file = any(target_path_or_url.lower().endswith(ext) for ext in COMMON_FILE_EXTENSIONS)

        if current_page and looks_like_file: # If context for files exists and it looks like a file
            return f'<span class="filelink-missing" title="File not found on this page: {escaped_target_for_titles}">{display_link_text} (file not found)</span>'
        else: # Treat as a potential new page, or if no current_page, it's the best guess.
            try:
                # Use slugified target for the `title` query param, as create view might expect that.
                create_page_title_param = slugify(target_path_or_url)
                create_url = reverse('wiki:page_create') + f'?title={create_page_title_param}'
                return f'<a href="{create_url}" class="wikilink-missing" title="Create page: {escaped_target_for_titles}">{display_link_text} (create)</a>'
            except NoReverseMatch:
                return f'<span class="wikilink-error" title="Link target not found and create URL error: {escaped_target_for_titles}">{display_link_text} (link error)</span>'

    return replacer

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
    _markdown_image_replacer = markdown_image_replacer_factory(current_page)
    # ORDER MATTERS: image replacer should come before standard markdown link replacer
    _standard_markdown_link_replacer = standard_markdown_link_replacer_factory(current_page)

    for match in CODE_PATTERN_RE.finditer(markdown_text):
        text_before_code = markdown_text[last_end:match.start()]
        processed_text_before = WIKILINK_RE.sub(_wikilink_replacer, text_before_code)
        processed_text_before = MARKDOWN_IMAGE_RE.sub(_markdown_image_replacer, processed_text_before)
        processed_text_before = STANDARD_MARKDOWN_LINK_RE.sub(_standard_markdown_link_replacer, processed_text_before)
        processed_parts.append(processed_text_before)
        processed_parts.append(match.group(0))
        last_end = match.end()

    text_after_last_code = markdown_text[last_end:]

    processed_text_after = WIKILINK_RE.sub(_wikilink_replacer, text_after_last_code)
    processed_text_after = MARKDOWN_IMAGE_RE.sub(_markdown_image_replacer, processed_text_after)
    processed_text_after = STANDARD_MARKDOWN_LINK_RE.sub(_standard_markdown_link_replacer, processed_text_after)

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