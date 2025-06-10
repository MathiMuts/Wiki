import json
from django.urls import reverse, NoReverseMatch
from .models import WikiPage
import re
from .views import MENU_CONFIG_PAGE_SLUG

DEFAULT_MENU_CONFIG = f"""
```
[
    {{
        "title": "Navigation",
        "items": [
            {{"text": "Home", "slug": "home"}},
            {{"text": "All Pages", "url_name": "wiki:all_pages"}},
            {{"text": "Create New Page", "url_name": "wiki:page_create", "login_required": true}}
        ]
    }},
    {{
        "title": "Configuration",
        "items": [
            {{"text": "Menu bar", "slug": "{MENU_CONFIG_PAGE_SLUG}"}},
            {{"text": "Markdown", "url": "https://www.markdownguide.org/basic-syntax/"}}
        ]
    }}
]
```
"""
def _extract_json_array_from_text(text_content):
    code_block_match = re.search(r"^```(?:json)?\s*\n(.*?\n)```", text_content, re.DOTALL | re.MULTILINE)
    
    content_to_search = text_content
    if code_block_match:
        content_to_search = code_block_match.group(1)


    start_index = content_to_search.find('[')
    if start_index == -1:
        return None

    brace_level = 0
    for i in range(start_index, len(content_to_search)):
        char = content_to_search[i]
        if char == '[':
            brace_level += 1
        elif char == ']':
            brace_level -= 1
            if brace_level == 0:
                json_array_str = content_to_search[start_index : i + 1]
                try:
                    json.loads(json_array_str)
                    return json_array_str
                except json.JSONDecodeError:
                    return None
    
    return None

def _parse_menu_data(menu_raw_content, source_page_slug="menu"):
    menu_json_string = _extract_json_array_from_text(menu_raw_content)
    
    if not menu_json_string:
        return []
        
    parsed_sections = []
    try:
        sections_data = json.loads(menu_json_string)
        if not isinstance(sections_data, list):
            return []
    except json.JSONDecodeError as e:
        return []

    for section_data in sections_data:
        if not isinstance(section_data, dict) or "title" not in section_data or "items" not in section_data:
            continue

        current_section = {"title": section_data["title"], "items": []}
        if not isinstance(section_data["items"], list):
            continue

        for item_data in section_data["items"]:
            if not isinstance(item_data, dict) or "text" not in item_data:
                continue

            text = item_data["text"]
            url = "#" # Default URL if others fail
            login_required = item_data.get("login_required", False)
            is_external = False

            if "url" in item_data:
                url = item_data["url"]
                is_external = True
            elif "slug" in item_data:
                try:
                    url = reverse('wiki:wiki_page', kwargs={'slug': item_data["slug"]})
                except NoReverseMatch:
                    pass # url remains "#"
            elif "url_name" in item_data:
                try:
                    url_args = item_data.get("url_args", [])
                    url_kwargs = item_data.get("url_kwargs", {})
                    url = reverse(item_data["url_name"], args=url_args, kwargs=url_kwargs)
                except NoReverseMatch:
                    pass # url remains "#"

            current_section["items"].append({
                "text": text,
                "url": url,
                "login_required": login_required,
                "is_external": is_external
            })
        
        if current_section["items"]: # Only add section if it has actual items
            parsed_sections.append(current_section)
            
    return parsed_sections


def wiki_menu(request):
    menu_config_content = None
    menu_page_slug_val = MENU_CONFIG_PAGE_SLUG 
    menu_page_title = menu_page_slug_val.replace('-', ' ').title()

    try:
        menu_config_page = WikiPage.objects.get(slug=menu_page_slug_val)
        menu_config_content = menu_config_page.content
    except WikiPage.DoesNotExist:
        try:
            new_menu_page, created = WikiPage.objects.get_or_create(
                slug=menu_page_slug_val,
                defaults={'title': menu_page_title, 'content': DEFAULT_MENU_CONFIG}
            )
            menu_config_content = new_menu_page.content
        except Exception as e_create:
            menu_config_content = DEFAULT_MENU_CONFIG
    except WikiPage.MultipleObjectsReturned:
        menu_config_page = WikiPage.objects.filter(slug=menu_page_slug_val).order_by('id').first()
        if menu_config_page:
            menu_config_content = menu_config_page.content
        else:
            menu_config_content = DEFAULT_MENU_CONFIG
    except Exception as e_fetch: 
        menu_config_content = DEFAULT_MENU_CONFIG

    if menu_config_content is None:
        menu_config_content = DEFAULT_MENU_CONFIG
        
    custom_menu_sections = _parse_menu_data(menu_config_content, source_page_slug=menu_page_slug_val)

    if not custom_menu_sections:
        custom_menu_sections = _parse_menu_data(DEFAULT_MENU_CONFIG, source_page_slug="DEFAULT_MENU_CONFIG_fallback")
        
        if not custom_menu_sections:
            try:
                menu_config_page_url_for_error = f"/wiki/{menu_page_slug_val}/"
            except Exception:
                 menu_config_page_url_for_error = "#"

            custom_menu_sections = [
                {
                    "title": "Menu Config Error",
                    "items": [{"text": "Please check menu configuration.", "url": menu_config_page_url_for_error}]
                }
            ]

    return {
        "custom_wiki_menu_sections": custom_menu_sections,
        "MENU_CONFIG_PAGE_SLUG": menu_page_slug_val
    }