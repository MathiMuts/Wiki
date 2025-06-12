# wiki/context_processors.py
import json
from django.urls import reverse, NoReverseMatch
from .models import WikiPage
import re
from . import constants


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
        if not isinstance(section_data, dict) or "title" not in section_data:
            continue

        section_url = None
        section_is_external = False

        if "section_link_url" in section_data:
            section_url = section_data["section_link_url"]
            section_is_external = True
        elif "section_link_slug" in section_data:
            try:
                section_url = reverse('wiki:wiki_page', kwargs={'slug': section_data["section_link_slug"]})
            except NoReverseMatch:
                pass
        elif "section_link_url_name" in section_data:
            try:
                url_args = section_data.get("section_link_url_args", [])
                url_kwargs = section_data.get("section_link_url_kwargs", {})
                section_url = reverse(section_data["section_link_url_name"], args=url_args, kwargs=url_kwargs)
            except NoReverseMatch:
                pass
        elif "items" in section_data and isinstance(section_data["items"], list) and section_data["items"]:
            first_item_data = section_data["items"][0]
            if isinstance(first_item_data, dict):
                if "url" in first_item_data:
                    temp_url = first_item_data["url"]
                    if temp_url and temp_url != "#":
                        section_url = temp_url
                        section_is_external = True
                elif "slug" in first_item_data:
                    try:
                        temp_url = reverse('wiki:wiki_page', kwargs={'slug': first_item_data["slug"]})
                        if temp_url and temp_url != "#":
                             section_url = temp_url
                    except NoReverseMatch:
                        pass
                elif "url_name" in first_item_data:
                    try:
                        url_args = first_item_data.get("url_args", [])
                        url_kwargs = first_item_data.get("url_kwargs", {})
                        temp_url = reverse(first_item_data["url_name"], args=url_args, kwargs=url_kwargs)
                        if temp_url and temp_url != "#":
                            section_url = temp_url
                    except NoReverseMatch:
                        pass

        current_section = {
            "title": section_data["title"],
            "items": [],
            "title_color": section_data.get("title_color"),
            "section_url": section_url,
            "section_is_external": section_is_external
        }

        if "items" in section_data and isinstance(section_data["items"], list):
            for item_data in section_data["items"]:
                if not isinstance(item_data, dict) or "text" not in item_data:
                    continue

                text = item_data["text"]
                item_url_val = "#"
                item_is_external = False
                circle_color = item_data.get("circle_color")

                if "url" in item_data:
                    item_url_val = item_data["url"]
                    item_is_external = True
                elif "slug" in item_data:
                    try:
                        item_url_val = reverse('wiki:wiki_page', kwargs={'slug': item_data["slug"]})
                    except NoReverseMatch:
                        pass
                elif "url_name" in item_data:
                    try:
                        url_args = item_data.get("url_args", [])
                        url_kwargs = item_data.get("url_kwargs", {})
                        item_url_val = reverse(item_data["url_name"], args=url_args, kwargs=url_kwargs)
                    except NoReverseMatch:
                        pass

                item_dict = {
                    "text": text,
                    "url": item_url_val,
                    "login_required": item_data.get("login_required", False),
                    "is_external": item_is_external,
                    "slug": item_data.get("slug"),
                    "circle_color": circle_color
                }
                current_section["items"].append(item_dict)

        if current_section["title"]:
            parsed_sections.append(current_section)

    return parsed_sections


def wiki_menu(request):
    menu_config_content = None
    menu_page_slug_val = constants.MENU_CONFIG_PAGE_SLUG
    menu_page_title = menu_page_slug_val.replace('-', ' ').title()

    try:
        menu_config_page = WikiPage.objects.get(slug=menu_page_slug_val)
        menu_config_content = menu_config_page.content
    except WikiPage.DoesNotExist:
        try:
            new_menu_page, created = WikiPage.objects.get_or_create(
                slug=menu_page_slug_val,
                defaults={'title': menu_page_title, 'content': constants.DEFAULT_MENU_CONFIG}
            )
            menu_config_content = new_menu_page.content
        except Exception:
            menu_config_content = constants.DEFAULT_MENU_CONFIG
    except WikiPage.MultipleObjectsReturned:
        menu_config_page = WikiPage.objects.filter(slug=menu_page_slug_val).order_by('id').first()
        menu_config_content = menu_config_page.content if menu_config_page else constants.DEFAULT_MENU_CONFIG
    except Exception:
        menu_config_content = constants.DEFAULT_MENU_CONFIG

    if menu_config_content is None:
        menu_config_content = constants.DEFAULT_MENU_CONFIG

    custom_menu_sections = _parse_menu_data(menu_config_content, source_page_slug=menu_page_slug_val)

    if not custom_menu_sections:
        custom_menu_sections = _parse_menu_data(constants.DEFAULT_MENU_CONFIG, source_page_slug="DEFAULT_MENU_CONFIG_fallback")
        if not custom_menu_sections:
            try:
                menu_config_page_url_for_error = reverse('wiki:wiki_page', kwargs={'slug': menu_page_slug_val})
            except Exception:
                 menu_config_page_url_for_error = f"/wiki/{menu_page_slug_val}/"
            custom_menu_sections = [
                {
                    "title": "Menu Config Error",
                    "items": [{"text": "Check menu config.", "url": menu_config_page_url_for_error, "slug": menu_page_slug_val, "circle_color": "red"}],
                    "title_color": "red",
                    "section_url": menu_config_page_url_for_error,
                    "section_is_external": False
                }
            ]

    all_pages_for_search = []
    try:
        pages = WikiPage.objects.all().values('title', 'slug')
        for page in pages:
            try:
                page_url = reverse('wiki:wiki_page', kwargs={'slug': page['slug']})
                all_pages_for_search.append({
                    "title": page['title'],
                    "slug": page['slug'],
                    "url": page_url
                })
            except NoReverseMatch:
                pass
    except Exception:
        pass

    return {
        "custom_wiki_menu_sections": custom_menu_sections,
        "MENU_CONFIG_PAGE_SLUG": menu_page_slug_val,
        "all_wiki_pages_json": json.dumps(all_pages_for_search)
    }