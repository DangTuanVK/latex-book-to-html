#!/usr/bin/env python3
"""
Config-driven HTML assembler.

Reads a skeleton HTML template with __PLACEHOLDER__ markers and replaces them
with generated content from cards HTML, cards metadata JSON, a book config
JSON, and a references.bib file.

Usage:
    python3 assemble.py --config book_config.json \\
                        --cards /tmp/cards.html \\
                        --meta /tmp/cards_meta.json \\
                        --output book/SachBSD.html

The skeleton template path and bib path are read from the config JSON.

Author: Dang Minh Tuan
Email:  tuanvietkey@gmail.com
"""

__author__ = "Dang Minh Tuan"
__email__ = "tuanvietkey@gmail.com"
__version__ = "1.0"
__date__ = "20-2-2026"

import argparse
import json
import os
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def die(msg: str) -> None:
    """Print error message and exit with code 1."""
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def read_file(path: str, label: str = "") -> str:
    """Read a UTF-8 file or die with a clear message."""
    p = Path(path)
    if not p.exists():
        die(f"{label or 'File'} not found: {path}")
    if not p.is_file():
        die(f"{label or 'Path'} is not a file: {path}")
    try:
        return p.read_text(encoding="utf-8")
    except Exception as e:
        die(f"Cannot read {label or 'file'} {path}: {e}")


def resolve_path(path: str, base_dir: str) -> str:
    """Resolve a path relative to base_dir if not absolute."""
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(base_dir, path))


# ---------------------------------------------------------------------------
# Config loading and validation
# ---------------------------------------------------------------------------

REQUIRED_CONFIG_KEYS = [
    "title", "author", "version", "date", "copyright_year",
    "skeleton", "bib", "tabs", "tab_labels",
]

OPTIONAL_CONFIG_DEFAULTS = {
    "subtitle": "",
    "affiliation": "",
    "author_url": "",
    "language": "vi",
    "about_html": "",
    "katex_macros": {},
    "difficulty_colors": {},
    "refs_urls": {},
}


def load_config(config_path: str) -> dict:
    """Load and validate the book config JSON."""
    text = read_file(config_path, "Config")
    try:
        config = json.loads(text)
    except json.JSONDecodeError as e:
        die(f"Invalid JSON in config {config_path}: {e}")

    missing = [k for k in REQUIRED_CONFIG_KEYS if k not in config]
    if missing:
        die(f"Config is missing required keys: {', '.join(missing)}")

    # Apply defaults for optional keys
    for k, v in OPTIONAL_CONFIG_DEFAULTS.items():
        config.setdefault(k, v)

    return config


def load_meta(meta_path: str) -> dict:
    """Load and validate the cards metadata JSON."""
    text = read_file(meta_path, "Metadata")
    try:
        meta = json.loads(text)
    except json.JSONDecodeError as e:
        die(f"Invalid JSON in metadata {meta_path}: {e}")

    if "cards" not in meta:
        die(f"Metadata JSON must have a 'cards' array")
    if not isinstance(meta["cards"], list) or len(meta["cards"]) == 0:
        die(f"Metadata 'cards' must be a non-empty array")

    # Validate each card has required fields
    required_card_fields = {"stt", "ch", "vi", "en", "diff"}
    for i, card in enumerate(meta["cards"]):
        missing_fields = required_card_fields - set(card.keys())
        if missing_fields:
            die(f"Card at index {i} (stt={card.get('stt','?')}) is missing fields: {', '.join(missing_fields)}")

    # Validate chapters exist if present
    if "chapters" not in meta:
        meta["chapters"] = {}
    if "parts" not in meta:
        meta["parts"] = []

    return meta


# ---------------------------------------------------------------------------
# Difficulty color
# ---------------------------------------------------------------------------

DEFAULT_DIFF_COLORS = {
    "1": "#48bb78", "2": "#48bb78",
    "3": "#4299e1", "4": "#4299e1",
    "5": "#ed8936", "6": "#ed8936",
    "7": "#e53e3e", "8": "#e53e3e",
    "9": "#805ad5", "10": "#805ad5",
}


def diff_color(level: int, config: dict) -> str:
    """Get the color for a difficulty level from config or defaults."""
    colors = config.get("difficulty_colors", {})
    if not colors:
        colors = DEFAULT_DIFF_COLORS
    key = str(level)
    if key in colors:
        return colors[key]
    # Fallback logic
    if level <= 2:
        return "#48bb78"
    if level <= 4:
        return "#4299e1"
    if level <= 6:
        return "#ed8936"
    if level <= 8:
        return "#e53e3e"
    return "#805ad5"


# ---------------------------------------------------------------------------
# Build header
# ---------------------------------------------------------------------------

def build_header(config: dict, meta: dict) -> str:
    """Build the header HTML with title, subtitle, author info, and tab buttons."""
    card_count = len(meta["cards"])
    title = config["title"]
    subtitle = config.get("subtitle", "")
    author = config["author"]
    affiliation = config.get("affiliation", "")
    author_url = config.get("author_url", "")
    version = config["version"]
    date = config["date"]
    copyright_year = config["copyright_year"]

    # Build subtitle line
    if not subtitle:
        ch_count = len(meta.get("chapters", {}))
        if ch_count:
            subtitle = f"{card_count} mục tra cứu từ {ch_count} chương sách &mdash; {author}"
        else:
            subtitle = f"{card_count} mục &mdash; {author}"

    # Author info block
    author_line = f"{author}"
    if affiliation:
        author_line += f" &mdash; {affiliation}"

    url_line = ""
    if author_url:
        url_line = f'<br>\n    <a href="{author_url}" target="_blank">{author_url}</a>'

    # Tab buttons
    tabs_html = []
    tab_list = config.get("tabs", ["ch", "vi", "en", "diff", "ref", "about"])
    tab_labels = config.get("tab_labels", {})
    default_labels = {
        "ch": "Mục lục", "vi": "Tiếng Việt", "en": "English",
        "diff": "Độ khó", "ref": "Tài liệu tham khảo",
        "about": "&#8505; Giới thiệu", "stt": "Danh mục",
    }

    for tab_id in tab_list:
        label = tab_labels.get(tab_id, default_labels.get(tab_id, tab_id))
        active = ' active' if tab_id == tab_list[0] else ''
        extra_class = ''
        extra_id = ''
        if tab_id == "about":
            extra_class = ' tab-btn-about'
            extra_id = ' id="btn-about"'
            # Prepend info icon if not already present
            if not label.startswith("&#") and not label.startswith("\u2139"):
                label = "&#8505; " + label
        tabs_html.append(
            f'  <button class="tab-btn{active}{extra_class}"{extra_id} data-tab="{tab_id}">{label}</button>'
        )

    return f"""<div class="header">
  <div class="header-left">
    <h1>{title}</h1>
    <div class="subtitle">{subtitle}</div>
  </div>
  <div class="author-info">
    Phiên bản {version} &nbsp;&middot;&nbsp; Cập nhật: {date} &nbsp;&middot;&nbsp; &copy; {copyright_year}<br>
    {author_line}{url_line}
  </div>
</div>

<div class="tabs">
{chr(10).join(tabs_html)}
</div>
"""


# ---------------------------------------------------------------------------
# Build about modal
# ---------------------------------------------------------------------------

def build_about_modal(config: dict, meta: dict) -> str:
    """Build the about modal and references panel HTML."""
    title = config["title"]
    author = config["author"]
    affiliation = config.get("affiliation", "")
    author_url = config.get("author_url", "")
    version = config["version"]
    date = config["date"]
    copyright_year = config["copyright_year"]
    about_html = config.get("about_html", "")
    card_count = len(meta["cards"])

    # Build about body content
    if about_html:
        body_content = about_html
    else:
        # Default about body
        ch_count = len(meta.get("chapters", {}))
        part_count = len(meta.get("parts", []))
        structure_desc = ""
        if part_count and ch_count:
            structure_desc = f"<strong>{part_count} phần</strong>, <strong>{ch_count} chương</strong> với "
        online = config.get('online', False)
        if online:
            mode_html = ('&#127760; Bản online &mdash; cần kết nối Internet để hiển thị '
                         'công thức toán (KaTeX qua CDN). File nhẹ hơn đáng kể.')
        else:
            mode_html = ('&#128230; File tự chứa hoàn toàn &mdash; không cần Internet, '
                         'không gọi CDN ngoài, mở được mọi lúc mọi nơi.')

        body_content = f"""
      <h3>Tác giả</h3>
      <p><strong>{author}</strong><br>
      {affiliation}<br>
      Website: <a href="{author_url}" target="_blank" style="color:#2b6cb0">{author_url}</a></p>
      <p>Tài liệu gồm {structure_desc}<strong>{card_count} mục</strong>.</p>
      <div class="highlight-box">Phiên bản {version} &nbsp;&middot;&nbsp; Cập nhật: {date} &nbsp;&middot;&nbsp; &copy; {copyright_year} {author}</div>

      <h3>Về file HTML này</h3>
      <div class="tech-note-offline">{mode_html}</div>
"""

    url_line = ""
    if author_url:
        url_line = f'\n      Website: <a href="{author_url}" target="_blank" style="color:#2b6cb0">{author_url}</a>'

    return f"""<div class="modal-overlay" id="aboutModal">
  <div class="modal-box">
    <div class="modal-header">
      <h2>Thông tin về sách</h2>
      <div class="modal-sub">{title} &mdash; Tra cứu nội dung sách</div>
    </div>
    <div class="modal-body">
{body_content}
    </div>
    <div class="modal-footer">
      <button id="aboutModalOk">OK</button>
    </div>
  </div>
</div>

<!-- References panel -->
<div class="ref-panel" id="refPanel">
  <h2>Tài liệu tham khảo <span class="ref-count" id="refCount"></span></h2>
  <input type="text" class="ref-search" id="refSearch" placeholder="Tìm tài liệu (tên tác giả, tiêu đề, năm...)">
  <div class="ref-list-wrapper">
    <div class="ref-header">
      <span class="rh-stt">STT</span>
      <span class="rh-type">Loại</span>
      <span class="rh-key">Mã tham khảo</span>
      <span class="rh-text">Thông tin tài liệu (Xếp theo tên tác giả)</span>
    </div>
    <ol class="ref-list" id="refList"></ol>
  </div>
</div>
"""


# ---------------------------------------------------------------------------
# Build sidebar
# ---------------------------------------------------------------------------

def build_sidebar(meta: dict, config: dict) -> str:
    """Build all sidebar panels (stt, vi, en, ch, diff)."""
    cards = meta["cards"]
    chapters = meta.get("chapters", {})
    parts = meta.get("parts", [])
    tab_list = config.get("tabs", [])

    lines = []

    # Determine which sidebar panels to build based on tabs
    # Standard panels: stt, vi, en, ch, diff
    # The "ch" panel is the default active one

    # Panel STT (plain numbered list)
    if "stt" in tab_list:
        lines.append('<div class="sidebar-panel" id="sb-stt">')
        lines.append('<div class="sidebar-search"><input type="text" placeholder="Tìm mục..." id="sidebar-search-stt"></div>')
        lines.append('<div class="sidebar-list" id="sidebar-list-stt">')
        for card in cards:
            stt = card["stt"]
            vi = card["vi"]
            lines.append(f'<a class="sidebar-item" data-stt="{stt}">{stt}. {vi}</a>')
        lines.append('</div></div>')

    # Panel VI (alphabetical Vietnamese)
    if "vi" in tab_list:
        sorted_vi = sorted(cards, key=lambda c: c["vi"].lower())
        lines.append('<div class="sidebar-panel" id="sb-vi">')
        lines.append('<div class="sidebar-search"><input type="text" placeholder="Tìm mục..." id="sidebar-search-vi"></div>')
        lines.append('<div class="sidebar-list" id="sidebar-list-vi">')
        for card in sorted_vi:
            stt = card["stt"]
            vi = card["vi"]
            lines.append(f'<a class="sidebar-item" data-stt="{stt}">{stt}. {vi}</a>')
        lines.append('</div></div>')

    # Panel EN (alphabetical English)
    if "en" in tab_list:
        sorted_en = sorted(cards, key=lambda c: c["en"].lower())
        lines.append('<div class="sidebar-panel" id="sb-en">')
        lines.append('<div class="sidebar-search"><input type="text" placeholder="Search..." id="sidebar-search-en"></div>')
        lines.append('<div class="sidebar-list" id="sidebar-list-en">')
        for card in sorted_en:
            stt = card["stt"]
            en = card["en"]
            lines.append(f'<a class="sidebar-item" data-stt="{stt}">{stt}. {en}</a>')
        lines.append('</div></div>')

    # Panel Ch (grouped by Part > Chapter -- active by default)
    if "ch" in tab_list:
        lines.append('<div class="sidebar-panel active" id="sb-ch">')
        lines.append('<div class="sidebar-search"><input type="text" placeholder="Tìm mục..." id="sidebar-search-ch"></div>')
        lines.append('<div class="sidebar-list" id="sidebar-list-ch">')

        # Build lookup: chapter_num -> part info
        ch_to_part = {}
        for part in parts:
            for ch_num in part.get("chapters", []):
                ch_to_part[ch_num] = part

        emitted_parts = set()
        emitted_chs = set()

        for card in cards:
            stt = card["stt"]
            ch = card["ch"]
            vi = card["vi"]

            # Emit part header if this is the first card in a new part
            if ch in ch_to_part and ch not in emitted_chs:
                part = ch_to_part[ch]
                part_key = part.get("num", "")
                if part_key and part_key not in emitted_parts:
                    emitted_parts.add(part_key)
                    part_name = part.get("name", "")
                    lines.append(f'<div class="sb-part-header">Phần {part_key}: {part_name}</div>')

            # Emit chapter header if first card in chapter
            if ch not in emitted_chs:
                emitted_chs.add(ch)
                ch_name = chapters.get(str(ch), f"Chương {ch}")
                lines.append(f'<div class="sb-ch-header">Ch.{ch}: {ch_name}</div>')

            lines.append(f'<a class="sidebar-item" data-stt="{stt}">{stt}. {vi}</a>')

        lines.append('</div></div>')

    # Panel Diff (grouped by difficulty level)
    if "diff" in tab_list:
        lines.append('<div class="sidebar-panel" id="sb-diff">')
        lines.append('<div class="sidebar-search"><input type="text" placeholder="Tìm mục..." id="sidebar-search-diff"></div>')
        lines.append('<div class="sidebar-list" id="sidebar-list-diff">')

        # Find the range of difficulty levels
        all_diffs = sorted(set(c["diff"] for c in cards))
        for level in all_diffs:
            items = [c for c in cards if c["diff"] == level]
            if items:
                color = diff_color(level, config)
                lines.append(f'<div class="sb-group-header" style="color:{color}">Mức {level} ({len(items)} mục)</div>')
                for card in items:
                    stt = card["stt"]
                    vi = card["vi"]
                    lines.append(f'<a class="sidebar-item" data-stt="{stt}">{stt}. {vi}</a>')

        lines.append('</div></div>')

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Build content toolbar
# ---------------------------------------------------------------------------

def build_content_toolbar(meta: dict) -> str:
    """Build the content toolbar with expand/collapse buttons, card count, and search."""
    card_count = len(meta["cards"])
    return f"""<div class="content" id="content">
    <div class="content-toolbar">
      <div class="toolbar-left">
        <button onclick="expandAll()">Mở tất cả</button>
        <button onclick="collapseAll()">Đóng tất cả</button>
        <span class="count" id="card-count">{card_count} mục</span>
      </div>
      <input type="text" placeholder="Tìm kiếm trong nội dung..." id="content-search">
    </div>
<div class="content-cards" id="content-cards">
"""


# ---------------------------------------------------------------------------
# Build TAB_CONFIG JavaScript object
# ---------------------------------------------------------------------------

def first_letter(s: str) -> str:
    """Get first uppercase letter of a string for alphabetical grouping."""
    for c in s:
        if c.isalpha():
            return c.upper()
    return '#'


def build_tab_config(meta: dict, config: dict) -> str:
    """Build TAB_CONFIG JavaScript object.

    Each tab: {"order": [stt...], "groups": [{before, label, type}, ...]}
    """
    cards = meta["cards"]
    chapters = meta.get("chapters", {})
    parts = meta.get("parts", [])
    tab_list = config.get("tabs", [])

    tc = {}

    # stt tab: sequential, no groups
    if "stt" in tab_list:
        tc["stt"] = {
            "order": [c["stt"] for c in cards],
            "groups": []
        }

    # vi tab: alphabetical by Vietnamese title, letter groups
    if "vi" in tab_list:
        sorted_vi = sorted(cards, key=lambda c: c["vi"].lower())
        vi_order = [c["stt"] for c in sorted_vi]
        vi_groups = []
        prev_letter = ''
        for c in sorted_vi:
            letter = first_letter(c["vi"])
            if letter != prev_letter:
                vi_groups.append({"before": c["stt"], "label": letter, "type": "letter"})
                prev_letter = letter
        tc["vi"] = {"order": vi_order, "groups": vi_groups}

    # en tab: alphabetical by English title, letter groups
    if "en" in tab_list:
        sorted_en = sorted(cards, key=lambda c: c["en"].lower())
        en_order = [c["stt"] for c in sorted_en]
        en_groups = []
        prev_letter = ''
        for c in sorted_en:
            letter = first_letter(c["en"])
            if letter != prev_letter:
                en_groups.append({"before": c["stt"], "label": letter, "type": "letter"})
                prev_letter = letter
        tc["en"] = {"order": en_order, "groups": en_groups}

    # ch tab: by part > chapter
    if "ch" in tab_list:
        ch_order = [c["stt"] for c in cards]
        ch_groups = []

        # Build lookup
        ch_to_part = {}
        for part in parts:
            for ch_num in part.get("chapters", []):
                ch_to_part[ch_num] = part

        seen_parts = set()
        seen_chs = set()
        for c in cards:
            stt, ch = c["stt"], c["ch"]
            if ch in ch_to_part:
                part = ch_to_part[ch]
                part_key = part.get("num", "")
                if part_key and part_key not in seen_parts:
                    seen_parts.add(part_key)
                    ch_groups.append({
                        "before": stt,
                        "label": f"Phần {part_key}: {part.get('name', '')}",
                        "type": "chapter"
                    })
            if ch not in seen_chs:
                seen_chs.add(ch)
                ch_name = chapters.get(str(ch), f"Chương {ch}")
                ch_groups.append({
                    "before": stt,
                    "label": f"Ch.{ch}: {ch_name}",
                    "type": "chapter"
                })

        tc["ch"] = {"order": ch_order, "groups": ch_groups}

    # diff tab: by difficulty level
    if "diff" in tab_list:
        diff_order = []
        diff_groups = []
        all_diffs = sorted(set(c["diff"] for c in cards))
        for level in all_diffs:
            items = [c for c in cards if c["diff"] == level]
            if items:
                diff_groups.append({
                    "before": items[0]["stt"],
                    "label": f"Mức {level} ({len(items)} mục)",
                    "type": "difficulty"
                })
                diff_order.extend(c["stt"] for c in items)
        tc["diff"] = {"order": diff_order, "groups": diff_groups}

    return json.dumps(tc, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Build KaTeX macros
# ---------------------------------------------------------------------------

DEFAULT_KATEX_MACROS = {
    "\\Sha": "\\mathrm{Sha}",
    "\\Q": "\\mathbb{Q}",
    "\\Z": "\\mathbb{Z}",
    "\\R": "\\mathbb{R}",
    "\\C": "\\mathbb{C}",
    "\\F": "\\mathbb{F}",
    "\\A": "\\mathbb{A}",
    "\\GL": "\\mathrm{GL}",
    "\\SL": "\\mathrm{SL}",
    "\\Gal": "\\mathrm{Gal}",
    "\\Aut": "\\mathrm{Aut}",
    "\\Hom": "\\mathrm{Hom}",
    "\\End": "\\mathrm{End}",
    "\\Ker": "\\mathrm{Ker}",
    "\\ord": "\\mathrm{ord}",
    "\\rk": "\\mathrm{rk}",
    "\\Tr": "\\mathrm{Tr}",
    "\\Spec": "\\mathrm{Spec}",
    "\\Image": "\\mathrm{Im}",
}


def build_katex_macros(config: dict) -> str:
    """Build the katex macros JS object body (just the key-value pairs)."""
    macros = dict(DEFAULT_KATEX_MACROS)
    macros.update(config.get("katex_macros", {}))

    lines = ['{']
    entries = []
    for key, val in sorted(macros.items()):
        # Escape backslashes and quotes for JS
        k_esc = key.replace("\\", "\\\\")
        v_esc = val.replace("\\", "\\\\")
        entries.append(f"    '{k_esc}': '{v_esc}'")
    lines.append(",\n".join(entries))
    lines.append('  }')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Parse .bib file
# ---------------------------------------------------------------------------

def parse_bib(bib_path: str) -> dict:
    """Parse references.bib into a dict of {key: {type, text, author, year, title}}.

    Handles math expressions in $...$ by protecting them before stripping braces.
    """
    text = read_file(bib_path, "BibTeX")

    entries = {}
    # Match @type{key, ...}
    pattern = r'@(\w+)\{([^,]+),\s*(.*?)\n\}'
    for m in re.finditer(pattern, text, re.DOTALL):
        btype = m.group(1).lower()
        key = m.group(2).strip()
        body = m.group(3)

        fields = {}
        for fm in re.finditer(r'(\w+)\s*=\s*\{(.+?)\}(?:\s*,|\s*$)', body, re.DOTALL):
            fname = fm.group(1).lower()
            fval = fm.group(2).strip().replace('\n', ' ').replace('  ', ' ')
            # Clean LaTeX markup
            fval = re.sub(r'\\textit\{([^}]*)\}', r'\1', fval)
            fval = re.sub(r'\\emph\{([^}]*)\}', r'\1', fval)
            fval = fval.replace('\\-', '')  # hyphenation hints

            # Protect $...$ math before stripping braces
            math_placeholders = []

            def _save_math(match):
                math_placeholders.append(match.group(0))
                return f'\x00MATH{len(math_placeholders) - 1}\x00'

            fval = re.sub(r'\$[^$]+?\$', _save_math, fval)
            fval = re.sub(r'[{}]', '', fval)

            # Restore math
            for i, mp in enumerate(math_placeholders):
                fval = fval.replace(f'\x00MATH{i}\x00', mp)

            fval = fval.replace('\\&', '&amp;').replace('&', '&amp;')
            fval = fval.replace("---", "&mdash;").replace("--", "&ndash;")
            fields[fname] = fval

        author = fields.get('author', 'Unknown')
        title = fields.get('title', '')
        year = fields.get('year', '')
        journal = fields.get('journal', fields.get('booktitle', ''))
        publisher = fields.get('publisher', '')
        volume = fields.get('volume', '')
        pages = fields.get('pages', '')

        # Type mapping
        type_map = {
            'article': 'Bài báo', 'book': 'Sách', 'inproceedings': 'Hội nghị',
            'incollection': 'Chương sách', 'phdthesis': 'Luận văn', 'misc': 'Khác',
            'unpublished': 'Chưa xuất bản',
        }
        btype_vi = type_map.get(btype, btype.capitalize())

        # Build display text with <strong> author and <em> title
        display = f'<strong>{author}</strong>'
        if year:
            display += f' ({year})'
        if title:
            display += f'. <em>{title}</em>'
        if journal:
            display += f'. {journal}'
            if volume:
                display += f' vol. {volume}'
            if pages:
                display += f', pp. {pages}'
        if publisher:
            display += f'. {publisher}'
        display += '.'

        entries[key] = {
            'type': btype_vi,
            'text': display,
            'author': author,
            'year': year,
            'title': title,
        }

    return entries


# ---------------------------------------------------------------------------
# Build REFS JavaScript
# ---------------------------------------------------------------------------

def build_refs_js(bib_entries: dict) -> str:
    """Build the REFS JavaScript dictionary.

    Format: const REFS = { 'key': 'Author (Year). Title. Publisher.', ... };
    Sorted by author name. Used by both tooltip IIFE and buildRefList().
    """
    sorted_keys = sorted(bib_entries.keys(), key=lambda k: bib_entries[k]['author'].lower())

    lines = ['{']
    for key in sorted_keys:
        e = bib_entries[key]
        text_escaped = e['text'].replace('\\', '\\\\').replace("'", "\\'")
        lines.append(f"    '{key}': '{text_escaped}',")
    lines.append('  }')

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Build REFS_URLS JavaScript
# ---------------------------------------------------------------------------

def build_refs_urls_js(config: dict) -> str:
    """Build the REFS_URLS JavaScript dictionary from config."""
    urls = config.get("refs_urls", {})
    if not urls:
        return "{}"

    lines = ['{']
    for key in sorted(urls.keys()):
        url_escaped = urls[key].replace('\\', '\\\\').replace("'", "\\'")
        lines.append(f"    '{key}': '{url_escaped}',")
    lines.append('  }')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Placeholder replacement
# ---------------------------------------------------------------------------

PLACEHOLDER_RE = re.compile(r'__([A-Z][A-Z0-9_]+)__')


def replace_placeholders(skeleton: str, replacements: dict) -> str:
    """Replace all __PLACEHOLDER__ markers in skeleton with values from replacements.

    Any placeholder found in the skeleton that has no replacement will cause a warning.
    """
    found = set(PLACEHOLDER_RE.findall(skeleton))
    provided = set(replacements.keys())

    # Warn about placeholders without replacements
    missing = found - provided
    if missing:
        for m in sorted(missing):
            print(f"WARNING: Placeholder __{m}__ found in skeleton but no replacement provided", file=sys.stderr)

    # Warn about unused replacements
    unused = provided - found
    if unused:
        for u in sorted(unused):
            print(f"INFO: Replacement '{u}' provided but no __{u}__ found in skeleton", file=sys.stderr)

    def _replacer(match):
        key = match.group(1)
        if key in replacements:
            return replacements[key]
        return match.group(0)  # Leave unchanged if no replacement

    return PLACEHOLDER_RE.sub(_replacer, skeleton)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_output(html: str, expected_cards: int, bib_entries: dict) -> bool:
    """Validate the assembled HTML and print diagnostics. Returns True if all checks pass."""
    open_divs = len(re.findall(r'<div[\s>]', html))
    close_divs = len(re.findall(r'</div>', html))
    card_count = len(re.findall(r'class="concept-card"', html))
    cite_count = len(re.findall(r'class="cite"', html))

    # Extract all citation keys used in cards
    cite_keys = set()
    for m in re.finditer(r'class="cite"[^>]*>\[([^\]]+)\]', html):
        for key in m.group(1).split(','):
            cite_keys.add(key.strip())

    # Check which cite keys are missing from bib
    missing_refs = cite_keys - set(bib_entries.keys())

    all_ok = True
    issues = []

    # Div balance
    if open_divs != close_divs:
        all_ok = False
        issues.append(f"Div balance MISMATCH: {open_divs} open / {close_divs} close")

    # Card count
    if card_count != expected_cards:
        all_ok = False
        issues.append(f"Card count mismatch: found {card_count}, expected {expected_cards}")

    # Missing citations
    if missing_refs:
        all_ok = False
        issues.append(f"Citations not in bib: {', '.join(sorted(missing_refs))}")

    # Essential elements
    essential_ids = ['sidebarContainer', 'content-cards', 'refPanel', 'aboutModal']
    for eid in essential_ids:
        if f'id="{eid}"' not in html:
            all_ok = False
            issues.append(f"Missing essential element: id=\"{eid}\"")

    # Print report
    print()
    print("=" * 50)
    print("ASSEMBLY REPORT")
    print("=" * 50)
    print(f"  Cards:        {card_count} (expected {expected_cards})")
    print(f"  Div balance:  {open_divs} open / {close_divs} close {'OK' if open_divs == close_divs else 'MISMATCH'}")
    print(f"  Citations:    {cite_count} total, {len(cite_keys)} unique keys")
    print(f"  Bib entries:  {len(bib_entries)}")
    if missing_refs:
        print(f"  Missing refs: {', '.join(sorted(missing_refs))}")
    print(f"  File size:    {len(html.encode('utf-8')) / 1024:.0f} KB")
    print(f"  Total lines:  {html.count(chr(10))}")

    if issues:
        print()
        print("WARNINGS:")
        for issue in issues:
            print(f"  - {issue}")

    if all_ok:
        print()
        print("All checks passed.")
    print("=" * 50)

    return all_ok


# ---------------------------------------------------------------------------
# Online mode conversion
# ---------------------------------------------------------------------------

KATEX_VERSION = '0.16.11'

KATEX_CDN_HEAD = f"""<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@{KATEX_VERSION}/dist/katex.min.css"
      crossorigin="anonymous">
<script defer src="https://cdn.jsdelivr.net/npm/katex@{KATEX_VERSION}/dist/katex.min.js"
        crossorigin="anonymous"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@{KATEX_VERSION}/dist/contrib/auto-render.min.js"
        crossorigin="anonymous"></script>"""


def convert_to_online(html_str: str) -> str:
    """Convert a self-contained (offline) HTML to online mode.

    Replaces embedded KaTeX CSS+JS (~1.7MB) with CDN links (~0.5KB).
    The resulting file requires Internet access to render math formulas.

    Args:
        html_str: The assembled HTML string with embedded KaTeX.

    Returns:
        HTML string with CDN links instead of embedded KaTeX.
    """
    # 1. Replace embedded KaTeX CSS (<style>/* KaTeX */\n...massive...\n</style>)
    #    with all 3 CDN links (CSS + JS + auto-render) in <head>
    html_str = re.sub(
        r'<style>/\* KaTeX \*/\s*\n.*?\n\s*</style>',
        '<!-- KaTeX (CDN) -->\n' + KATEX_CDN_HEAD,
        html_str,
        count=1,
        flags=re.DOTALL,
    )

    # 2. Remove embedded KaTeX JS (now loaded from CDN in <head>)
    html_str = re.sub(
        r'<script>/\* KaTeX \*/\s*\n.*?\n</script>',
        '<!-- KaTeX JS: loaded via CDN in <head> -->',
        html_str,
        count=1,
        flags=re.DOTALL,
    )

    # 3. Remove embedded KaTeX auto-render (now loaded from CDN in <head>)
    html_str = re.sub(
        r'<script>/\* KaTeX auto-render \*/\s*\n.*?\n</script>',
        '<!-- KaTeX auto-render: loaded via CDN in <head> -->',
        html_str,
        count=1,
        flags=re.DOTALL,
    )

    return html_str


# ---------------------------------------------------------------------------
# Main assembly
# ---------------------------------------------------------------------------

def assemble(args: argparse.Namespace) -> None:
    """Main assembly function."""

    # Resolve paths
    config_path = os.path.abspath(args.config)
    cwd = os.getcwd()

    # Load config
    config = load_config(config_path)

    # Resolve skeleton and bib paths relative to CWD (not config dir)
    # Config paths like "scripts/skeleton.html" or "book/references.bib"
    # are meant to be relative to the project root where the user runs the command
    skeleton_path = resolve_path(config["skeleton"], cwd)
    bib_path = resolve_path(config["bib"], cwd)

    # Load inputs
    skeleton = read_file(skeleton_path, "Skeleton template")
    cards_html = read_file(args.cards, "Cards HTML")
    meta = load_meta(args.meta)
    bib_entries = parse_bib(bib_path)

    card_count = len(meta["cards"])
    print(f"Loaded config from {config_path}")
    print(f"Loaded skeleton from {skeleton_path} ({len(skeleton)} chars)")
    print(f"Loaded {card_count} cards from metadata")
    print(f"Loaded cards HTML from {args.cards} ({len(cards_html)} chars)")
    print(f"Parsed {len(bib_entries)} bib entries from {bib_path}")

    # Build all replacement components
    header_html = build_header(config, meta)
    about_modal_html = build_about_modal(config, meta)
    sidebar_html = build_sidebar(meta, config)
    content_toolbar_html = build_content_toolbar(meta)
    tab_config_js = build_tab_config(meta, config)
    katex_macros_js = build_katex_macros(config)
    refs_js = build_refs_js(bib_entries)
    refs_urls_js = build_refs_urls_js(config)

    # Content closing tags
    content_close = """</div><!-- end content-cards -->
</div><!-- end content -->
</div><!-- end main-area -->"""

    # Build the replacements dict
    # Keys must match __PLACEHOLDER__ markers in skeleton.html
    replacements = {
        "TITLE": config["title"],
        "HEADER_HTML": header_html,
        "ABOUT_HTML": about_modal_html,
        "SIDEBAR_HTML": sidebar_html,
        "CARD_COUNT": str(card_count),
        "CARDS_HTML": cards_html,
        "TAB_CONFIG": tab_config_js,
        "KATEX_MACROS": katex_macros_js,
        "REFS": refs_js,
        "REFS_URLS": refs_urls_js,
    }

    # Perform replacement
    result = replace_placeholders(skeleton, replacements)

    # Validate
    output_path = os.path.abspath(args.output)
    ok = validate_output(result, card_count, bib_entries)

    # Write output
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.isdir(output_dir):
        die(f"Output directory does not exist: {output_dir}")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(result)

    print(f"\nOutput written to: {output_path}")

    if not ok:
        print("\nAssembly completed with warnings. Please review the issues above.", file=sys.stderr)
        sys.exit(2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Config-driven HTML assembler for offline reference books.",
        epilog=(
            "Example:\n"
            "  python3 assemble.py --config book_config.json \\\n"
            "                      --cards /tmp/cards.html \\\n"
            "                      --meta /tmp/cards_meta.json \\\n"
            "                      --output book/SachBSD.html\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config", required=True,
        help="Path to book config JSON (contains skeleton path, bib path, title, tabs, etc.)",
    )
    parser.add_argument(
        "--cards", required=True,
        help="Path to cards HTML file (output from tex2html.py, contains only card divs)",
    )
    parser.add_argument(
        "--meta", required=True,
        help="Path to cards metadata JSON file (output from tex2html.py, contains card list and chapter/part info)",
    )
    parser.add_argument(
        "--output", required=True,
        help="Path for the assembled output HTML file",
    )

    args = parser.parse_args()

    # Validate input files exist before proceeding
    for path, label in [(args.config, "Config"), (args.cards, "Cards HTML"), (args.meta, "Metadata")]:
        if not os.path.isfile(path):
            die(f"{label} file not found: {path}")

    assemble(args)


if __name__ == '__main__':
    main()
