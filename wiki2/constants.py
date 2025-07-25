# wiki/constants.py
import re

# --- Page Slugs ---
ROOT_WIKI_PAGE_SLUG = "home"
MENU_CONFIG_PAGE_SLUG = "menu-config"

# --- Default Content ---
DEFAULT_ROOT_PAGE_CONTENT = '''
# Welcome to the Wiki!

This is the explaination page of the new wiki. Below is a demonstration of the formatting features available.

---
## Standard Markdown Features

This wiki uses Markdown for formatting content. Here are some common examples:

### Text Formatting
- *Italic text*: `*Italic text*` or `_italic text_`
- **Bold text**: `**Bold text**` or `__bold text__`
- `Codeblocks`: `` `Inline code span` `` or ```` ``` `Backticks` ``` ```` for literal backticks inside.

# Heading 1 (equivalent to page title, usually only one per page)
`# Heading 1`
## Heading 2 (like this section's title)
`## Heading 2`
### Heading 3
`### Heading 3`
#### Heading 4
`#### Heading 4`
##### Heading 5
`##### Heading 5`
###### Heading 6
`###### Heading 6`

#### Unordered List
- Item 1
- Item 2
    - Sub-item 2.1
    - Sub-item 2.2
- Item 3

```
#### Unordered List
- Item 1
- Item 2
    - Sub-item 2.1
    - Sub-item 2.2
- Item 3
```

#### Ordered List
1. First item
2. Second item
    1. Sub-item 2.a
    2. Sub-item 2.b
3. Third item

```
#### Ordered List
1. First item
2. Second item
    1. Sub-item 2.a
    2. Sub-item 2.b
3. Third item
```

### Links
- [This is an external link to the Markdown docs.](https://www.markdownguide.org/) `[This is an external link to the Markdown docs.](https://www.markdownguide.org/)`
- [[ Use double square brackets to link to other pages within this wiki.| Menu Config ]] `[[ Menu Config ]]` or `[[ Display Text | Menu Config ]]`
- [Use links to attached files to link them in the text.](test-document.pdf) `[Display Text.](test-document.pdf)`

### Blockquotes
> This is a blockquote.
> It can span multiple lines.
>
> > Nested blockquotes are also possible.
```
> This is a blockquote.
> It can span multiple lines.
>
> > Nested blockquotes are also possible.
```

### Code Blocks
For a block of code, use triple backticks (fenced code blocks):

```
This is a generic code block
without language specification.
Plain text.
```

````
```
This is a generic code block
without language specification.
Plain text.
```
````

### Horizontal Rule

***

---

___

```
---
___
***
```

### Tables
| Header 1      | Header 2      | Header 3      |
|---------------|---------------|---------------|
| Cell 1.1      | Cell 1.2      | Cell 1.3      |
| Cell 2.1      | **Cell 2.2** (can have Markdown) | Cell 2.3      |
| `Cell 3.1`    | Cell 3.2      | _Cell 3.3_    |

```
| Header 1      | Header 2      | Header 3      |
|---------------|---------------|---------------|
| Cell 1.1      | Cell 1.2      | Cell 1.3      |
| Cell 2.1      | **Cell 2.2** (can have Markdown) | Cell 2.3      |
| `Cell 3.1`    | Cell 3.2      | _Cell 3.3_    |
```

### Images
![Alt text for an image](https://picsum.photos/200/300)
![Alt text for an image](test-image.jpg)

```
![Alt text for an image](https://picsum.photos/200/300)
![This image is attatched below](test-image.jpg)
```

### PDFs
![This PDF is attatched below](test-document.pdf)

```
![This PDF is attatched below](test-document.pdf)
```

### Image galleries
![Alt text for an image gallery](test-archive)

```
![Alt text for an image gallery](test-archive)
```

Happy Wiki-ing!



'''

DEFAULT_MENU_CONFIG = """
## Be carefull, NO TRAILING COMMAS `,`!
```
[
    {
        "title": "Navigation",
        "title_color": "#000000",
        "section_link_slug": "home",
        "items": [
            {"text": "Home", "slug": "home"},
            {"text": "Markdown Guide", "url": "https://www.markdownguide.org/basic-syntax/"}
        ]
    },
    {
        "title": "Second section",
        "section_link_slug": "2nd-section",
        "title_color": "green",
        "items": [
            {"text": "1ˢᵗᵉ item", "slug": "1-item-default", "circle_color": "green"},
            {"text": "2ᵈᵉ item", "slug": "2-item-default", "circle_color": "green"}
        ]
    }
]
```
"""

# --- Configuration Values ---
DEFAULT_COMMON_FILE_EXTENSIONS = [
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.txt', '.md', '.markdown', '.csv', '.rtf', '.odt', '.ods', '.odp',
    '.zip', '.tar', '.gz', '.rar', '.7z',
    '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.heic',
    '.html', '.htm', '.css', '.js', '.json', '.xml', '.py', '.java', '.c', '.cpp', '.h', '.php', '.rb', '.ipynb',
    '.mp3', '.mp4', '.avi', '.mov', '.mkv', '.webm',
]

# --- Picture extensions for gallery ---
WIKI_PICTURE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.heic']

# --- Archives supported for photo galleries ---
WIKI_ARCHIVE_EXTENSIONS = ['.zip']

DEFAULT_MARKDOWN_TO_PDF_CSS = """
@page { size: A4; margin: 2cm; }
body { font-family: sans-serif; line-height: 1.5; font-size: 10pt; }
h1, h2, h3, h4, h5, h6 { page-break-after: avoid; margin-top: 1.5em; margin-bottom: 0.5em; }
h1 {font-size: 2em;} h2 {font-size: 1.75em;} h3 {font-size: 1.5em;}
h4 {font-size: 1.25em;} h5 {font-size: 1.1em;} h6 {font-size: 1em;}
p, ul, ol, blockquote { margin-bottom: 1em; }
pre {
    font-family: monospace;
    background-color: #f0f0f0;
    padding: 1em;
    border-radius: 4px;
    overflow-x: auto;
    page-break-inside: avoid;
}
code {
    font-family: monospace;
    background-color: #f0f0f0;
    padding: 0.1em;
    border-radius: 1px;
    overflow-x: auto; /* Allow horizontal scroll for inline code if needed */
    page-break-inside: avoid;
}
table { border-collapse: collapse; width: 100%; margin-bottom: 1em; page-break-inside: avoid; }
th, td { border: 1px solid #ccc; padding: 0.5em; text-align: left; }
th { background-color: #f8f8f8; }
img { max-width: 100%; height: auto; display: block; margin-bottom: 1em; }
a { color: #007bff; text-decoration: none; }
a:hover { text-decoration: underline; }
blockquote { border-left: 3px solid #ccc; padding-left: 1em; margin-left: 0; color: #555; }
hr { border: 0; border-top: 1px solid #ccc; margin: 2em 0; }
"""

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