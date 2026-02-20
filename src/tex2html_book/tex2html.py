#!/usr/bin/env python3
"""
tex2html.py - Generalized LaTeX-to-HTML Card Converter

Converts LaTeX .tex chapter files into styled HTML cards suitable for
offline reference tools. Supports config-driven and auto-detect modes.

Usage:
  # Auto-detect mode: scan book directory for chapters
  python3 tex2html.py --book-dir ./book --output /tmp/cards.html

  # Config-driven mode: use JSON config file
  python3 tex2html.py --config book_config.json --output /tmp/cards.html

  # Single chapter
  python3 tex2html.py --config book_config.json --chapter 4 --output /tmp/ch04_cards.html

  # Auto-detect with metadata output
  python3 tex2html.py --book-dir ./book --output /tmp/cards.html --meta /tmp/cards_meta.json

Author: Dang Minh Tuan
Email:  tuanvietkey@gmail.com
"""

__author__ = "Dang Minh Tuan"
__email__ = "tuanvietkey@gmail.com"
__version__ = "1.0"
__date__ = "20-2-2026"

import re
import sys
import os
import argparse
import json
import base64
import glob as globmod
from pathlib import Path

# ============================================================================
# DEFAULT CONFIGURATION
# ============================================================================
DEFAULT_ENVIRONMENTS = {
    'dinhly':             ('env-theorem',  'Dinh ly'),
    'bode':               ('env-theorem',  'Bo de'),
    'menhde':             ('env-theorem',  'Menh de'),
    'hequa':              ('env-theorem',  'He qua'),
    'dinhri':             ('env-theorem',  'Dinh ly'),
    'giaithiet':          ('env-theorem',  'Gia thiet'),
    'phongdoan':          ('env-theorem',  'Phong doan'),
    'vidu':               ('env-example',  'Vi du'),
    'baitap':             ('env-example',  'Bai tap'),
    'trucgiac':           ('box-green',    'Truc giac'),
    'chungminhsocap':     ('env-proof',    'Chung minh'),
    'chungminhnangcao':   ('box-yellow',   'Chung minh (nang cao)'),
    'phachoa':            ('box-red',      'Phac hoa'),
    'giaithoai':          ('box-purple',   'Giai thoai'),
    'luuy':               ('box-yellow',   'Luu y'),
    'tomtat':             ('box-gray',     'Tom tat'),
    'thuatngu':           ('box-teal',     'Thuat ngu'),
    # Common English environments
    'theorem':            ('env-theorem',  'Theorem'),
    'lemma':              ('env-theorem',  'Lemma'),
    'proposition':        ('env-theorem',  'Proposition'),
    'corollary':          ('env-theorem',  'Corollary'),
    'definition':         ('env-theorem',  'Definition'),
    'conjecture':         ('env-theorem',  'Conjecture'),
    'example':            ('env-example',  'Example'),
    'exercise':           ('env-example',  'Exercise'),
    'remark':             ('box-yellow',   'Remark'),
    'note':               ('box-yellow',   'Note'),
}

# Vietnamese environment labels (override for vi language)
VI_ENVIRONMENT_LABELS = {
    'dinhly':             'Dinh ly',
    'bode':               'Bo de',
    'menhde':             'Menh de',
    'hequa':              'He qua',
    'dinhri':             'Dinh ly',
    'giaithiet':          'Gia thiet',
    'phongdoan':          'Phong doan',
    'vidu':               'Vi du',
    'baitap':             'Bai tap',
    'trucgiac':           'Truc giac',
    'chungminhsocap':     'Chung minh',
    'chungminhnangcao':   'Chung minh (nang cao)',
    'phachoa':            'Phac hoa',
    'giaithoai':          'Giai thoai',
    'luuy':               'Luu y',
    'tomtat':             'Tom tat',
    'thuatngu':           'Thuat ngu',
}

# Proper Vietnamese labels with diacritics
VI_LABELS_DIACRITICS = {
    'dinhly':             u'\u0110\u1ecbnh l\u00fd',
    'bode':               u'B\u1ed5 \u0111\u1ec1',
    'menhde':             u'M\u1ec7nh \u0111\u1ec1',
    'hequa':              u'H\u1ec7 qu\u1ea3',
    'dinhri':             u'\u0110\u1ecbnh l\u00fd',
    'giaithiet':          u'Gi\u1ea3 thi\u1ebft',
    'phongdoan':          u'Ph\u1ecfng \u0111o\u00e1n',
    'vidu':               u'V\u00ed d\u1ee5',
    'baitap':             u'B\u00e0i t\u1eadp',
    'trucgiac':           u'Tr\u1ef1c gi\u00e1c',
    'chungminhsocap':     u'Ch\u1ee9ng minh',
    'chungminhnangcao':   u'Ch\u1ee9ng minh (n\u00e2ng cao)',
    'phachoa':            u'Ph\u00e1c h\u1ecda',
    'giaithoai':          u'Giai tho\u1ea1i',
    'luuy':               u'L\u01b0u \u00fd',
    'tomtat':             u'T\u00f3m t\u1eaft',
    'thuatngu':           u'Thu\u1eadt ng\u1eef',
}

DEFAULT_EXERCISE_KEYWORDS = [
    'Bai tap', 'bai tap',
    u'B\u00e0i t\u1eadp', u'b\u00e0i t\u1eadp',
    'Exercise', 'exercise', 'Exercises', 'exercises',
]

DEFAULT_DIFF_COLORS = {
    1: "#48bb78", 2: "#48bb78",
    3: "#4299e1", 4: "#4299e1",
    5: "#ed8936", 6: "#ed8936",
    7: "#e53e3e", 8: "#e53e3e",
    9: "#805ad5", 10: "#805ad5",
}

DEFAULT_CROSS_REF_TEXT = '(xem phan lien quan)'

DEFAULT_KATEX_MACROS = {}

# ============================================================================
# CONFIGURATION LOADER
# ============================================================================
class Config:
    """Holds all configuration for a conversion run."""

    def __init__(self):
        self.book_dir = None
        self.chapters_dir = 'chapters'
        self.chapter_pattern = 'ch{:02d}.tex'
        self.num_chapters = None  # auto-detect if None
        self.main_tex = 'main.tex'
        self.language = 'vi'
        self.title = 'LaTeX Book'
        self.author = ''
        self.environments = {}
        self.cards = None  # list of card dicts, or None for auto-detect
        self.exercise_keywords = list(DEFAULT_EXERCISE_KEYWORDS)
        self.katex_macros = dict(DEFAULT_KATEX_MACROS)
        self.diff_colors = dict(DEFAULT_DIFF_COLORS)
        self.cross_ref_text = DEFAULT_CROSS_REF_TEXT
        self.proof_label = 'Proof'
        self.default_difficulty = 5

    @classmethod
    def from_json(cls, filepath):
        """Load configuration from a JSON file."""
        cfg = cls()
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        cfg.book_dir = data.get('book_dir', cfg.book_dir)
        cfg.chapters_dir = data.get('chapters_dir', cfg.chapters_dir)
        cfg.chapter_pattern = data.get('chapter_pattern', cfg.chapter_pattern)
        cfg.num_chapters = data.get('num_chapters', cfg.num_chapters)
        cfg.main_tex = data.get('main_tex', cfg.main_tex)
        cfg.language = data.get('language', cfg.language)
        cfg.title = data.get('title', cfg.title)
        cfg.author = data.get('author', cfg.author)
        cfg.default_difficulty = data.get('default_difficulty', cfg.default_difficulty)
        cfg.cross_ref_text = data.get('cross_ref_text', cfg.cross_ref_text)
        cfg.proof_label = data.get('proof_label', cfg.proof_label)

        if 'exercise_keywords' in data:
            cfg.exercise_keywords = data['exercise_keywords']

        if 'katex_macros' in data:
            cfg.katex_macros = data['katex_macros']

        # Accept both "diff_colors" and "difficulty_colors"
        dc_key = 'diff_colors' if 'diff_colors' in data else 'difficulty_colors'
        if dc_key in data:
            cfg.diff_colors = {int(k): v for k, v in data[dc_key].items()}

        # Environments: merge defaults with user overrides
        if 'environments' in data:
            for env_name, env_info in data['environments'].items():
                if env_name.startswith('_'):
                    continue  # skip _comment keys
                if isinstance(env_info, dict):
                    css = env_info.get('css', env_info.get('css_class', 'env-theorem'))
                    cfg.environments[env_name] = (
                        css,
                        env_info.get('label', env_name)
                    )
                elif isinstance(env_info, (list, tuple)) and len(env_info) == 2:
                    cfg.environments[env_name] = tuple(env_info)

        # Cards: explicit card metadata or "_auto_"
        if 'cards' in data:
            cards_val = data['cards']
            if isinstance(cards_val, list):
                cfg.cards = cards_val  # explicit list
            # "_auto_" or omitted → None (auto-detect)

        return cfg

    @classmethod
    def from_book_dir(cls, book_dir):
        """Create config by auto-detecting from a book directory."""
        cfg = cls()
        cfg.book_dir = book_dir
        return cfg

    def get_chapters_path(self):
        """Return the full path to the chapters directory."""
        if self.book_dir is None:
            raise ValueError("book_dir is not set")
        return os.path.join(self.book_dir, self.chapters_dir)

    def get_main_tex_path(self):
        """Return the full path to main.tex."""
        if self.book_dir is None:
            return None
        return os.path.join(self.book_dir, self.main_tex)

    def resolve_environments(self):
        """Build the final environment mapping from defaults + config overrides."""
        envs = dict(DEFAULT_ENVIRONMENTS)

        # Apply Vietnamese diacritic labels if language is vi
        if self.language == 'vi':
            for env_name, label in VI_LABELS_DIACRITICS.items():
                if env_name in envs:
                    envs[env_name] = (envs[env_name][0], label)
            self.proof_label = u'Ch\u1ee9ng minh'
            self.cross_ref_text = '(xem ph\u1ea7n li\u00ean quan)'

        # Apply user overrides
        envs.update(self.environments)
        return envs

    def detect_chapters(self):
        """Detect chapter .tex files from the chapters directory.

        Returns a sorted list of (chapter_num, filepath) tuples.
        """
        chapters_path = self.get_chapters_path()
        if not os.path.isdir(chapters_path):
            raise FileNotFoundError(
                f"Chapters directory not found: {chapters_path}")

        chapters = []

        if self.num_chapters is not None:
            # Use explicit count with pattern
            for ch_num in range(1, self.num_chapters + 1):
                filename = self.chapter_pattern.format(ch_num)
                filepath = os.path.join(chapters_path, filename)
                if os.path.isfile(filepath):
                    chapters.append((ch_num, filepath))
                else:
                    print(f"  WARNING: Expected chapter file not found: {filepath}",
                          file=sys.stderr)
        else:
            # Auto-detect: try pattern with numbers 1..99
            for ch_num in range(1, 100):
                filename = self.chapter_pattern.format(ch_num)
                filepath = os.path.join(chapters_path, filename)
                if os.path.isfile(filepath):
                    chapters.append((ch_num, filepath))

            # If pattern didn't work, try globbing for *.tex
            if not chapters:
                tex_files = sorted(globmod.glob(
                    os.path.join(chapters_path, '*.tex')))
                for i, fp in enumerate(tex_files, 1):
                    chapters.append((i, fp))

        return chapters

    def detect_parts(self):
        """Parse main.tex to detect \\part commands and chapter assignments.

        Returns a list of dicts: [{"num": "I", "name": "...", "chapters": [1,2,3]}]
        """
        main_path = self.get_main_tex_path()
        if main_path is None or not os.path.isfile(main_path):
            return []

        try:
            with open(main_path, 'r', encoding='utf-8') as f:
                text = f.read()
        except (IOError, OSError):
            return []

        # Find \part{...} and \input{chapters/...} commands
        part_pat = re.compile(r'\\part\{([^}]*)\}')
        input_pat = re.compile(
            r'\\input\{(?:chapters/)?ch(\d+)\}')

        parts = []
        current_part = None
        roman_numerals = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII',
                          'IX', 'X', 'XI', 'XII']
        part_idx = 0

        for line in text.split('\n'):
            line_stripped = line.strip()
            # Skip comments
            if line_stripped.startswith('%'):
                continue

            pm = part_pat.search(line_stripped)
            if pm:
                if current_part is not None:
                    parts.append(current_part)
                numeral = roman_numerals[part_idx] if part_idx < len(roman_numerals) else str(part_idx + 1)
                current_part = {
                    'num': numeral,
                    'name': pm.group(1).strip(),
                    'chapters': []
                }
                part_idx += 1
                continue

            im = input_pat.search(line_stripped)
            if im:
                ch_num = int(im.group(1))
                if current_part is not None:
                    current_part['chapters'].append(ch_num)

        if current_part is not None:
            parts.append(current_part)

        return parts

    def detect_chapter_titles(self, chapter_files):
        """Extract \\chapter{...} titles from each chapter file.

        Args:
            chapter_files: list of (chapter_num, filepath) tuples

        Returns:
            dict: {chapter_num: "Chapter Title"}
        """
        titles = {}
        ch_pat = re.compile(
            r'\\chapter\{((?:[^{}]|\{[^{}]*\})*)\}')
        for ch_num, filepath in chapter_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    text = f.read(2000)  # Title is near the top
                m = ch_pat.search(text)
                if m:
                    title = m.group(1).strip()
                    # Clean texorpdfstring
                    title = re.sub(
                        r'\\texorpdfstring\{([^}]*)\}\{[^}]*\}',
                        r'\1', title)
                    titles[ch_num] = title
                else:
                    titles[ch_num] = f'Chapter {ch_num}'
            except (IOError, OSError):
                titles[ch_num] = f'Chapter {ch_num}'
        return titles


# ============================================================================
# MATH PROTECTION
# ============================================================================
_MATH_PLACEHOLDER = '\x00MATH_%d\x00'


def protect_math(text):
    """Replace math with placeholders to avoid mangling by other conversions.

    Handles: $$...$$, \\[...\\] (with negative lookbehind for \\\\[6pt]),
    align/equation/gather/multline environments, and inline $...$.
    """
    store = []
    counter = [0]

    def save(m):
        store.append(m.group(0))
        ph = _MATH_PLACEHOLDER % counter[0]
        counter[0] += 1
        return ph

    def save_display(m):
        content = m.group(0)[2:-2]  # strip \[ and \]
        store.append('$$' + content + '$$')
        ph = _MATH_PLACEHOLDER % counter[0]
        counter[0] += 1
        return ph

    def save_aligned(m, env):
        content = m.group(0)
        inner = re.search(
            r'\\begin\{[^}]*\}(.*?)\\end\{[^}]*\}', content, re.DOTALL)
        if inner:
            store.append(
                '$$\\begin{aligned}' + inner.group(1) + '\\end{aligned}$$')
        else:
            store.append('$$' + content + '$$')
        ph = _MATH_PLACEHOLDER % counter[0]
        counter[0] += 1
        return ph

    # Display math: $$...$$
    text = re.sub(r'\$\$.*?\$\$', save, text, flags=re.DOTALL)

    # Display math: \[...\] with negative lookbehind to avoid \\[6pt]
    text = re.sub(
        r'(?<!\\)\\\[.*?\\\]',
        save_display, text, flags=re.DOTALL)

    # Named math environments
    math_envs = [
        'align', 'align*', 'equation', 'equation*',
        'gather', 'gather*', 'multline', 'multline*',
    ]
    for env in math_envs:
        pat = re.compile(
            r'\\begin\{' + re.escape(env) + r'\}.*?\\end\{'
            + re.escape(env) + r'\}', re.DOTALL)
        text = pat.sub(lambda m, e=env: save_aligned(m, e), text)

    # Inline math: $...$ (not $$)
    text = re.sub(
        r'(?<!\$)\$(?!\$)((?:[^$\\]|\\.)+?)\$(?!\$)', save, text)

    return text, store


def restore_math(text, store):
    """Restore math placeholders back to their original content."""
    for i, math in enumerate(store):
        text = text.replace(_MATH_PLACEHOLDER % i, math)
    return text


# ============================================================================
# COMMENT STRIPPING
# ============================================================================
def strip_comments(text):
    """Remove LaTeX comments (% to end-of-line, unless escaped)."""
    lines = text.split('\n')
    result = []
    for line in lines:
        cleaned = re.sub(r'(?<!\\)%.*$', '', line)
        result.append(cleaned)
    return '\n'.join(result)


# ============================================================================
# SECTION SPLITTING
# ============================================================================
def split_into_sections(tex_content, chapter_num, exercise_keywords=None):
    """Split chapter content into sections.

    Args:
        tex_content: The full text of the chapter .tex file (comments already stripped).
        chapter_num: The chapter number (for logging).
        exercise_keywords: List of keywords that identify exercise sections to skip.

    Returns:
        List of (title, content) tuples.
    """
    if exercise_keywords is None:
        exercise_keywords = DEFAULT_EXERCISE_KEYWORDS

    # Remove chapter command
    tex_content = re.sub(
        r'\\chapter\{.*?\}\s*', '', tex_content, flags=re.DOTALL)

    section_pat = re.compile(
        r'\\section(\*?)\{((?:[^{}]|\{[^{}]*\})*)\}', re.DOTALL)
    matches = list(section_pat.finditer(tex_content))

    if not matches:
        return [("(Content)", tex_content.strip())]

    sections = []
    for i, m in enumerate(matches):
        is_star = m.group(1) == '*'
        title_raw = m.group(2).strip()
        title = re.sub(
            r'\\texorpdfstring\{([^}]*)\}\{[^}]*\}', r'\1', title_raw)

        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(tex_content)
        content = tex_content[start:end].strip()

        # Skip exercise sections (starred sections matching keywords)
        if is_star:
            skip = False
            for kw in exercise_keywords:
                if kw in title or kw.lower() in title.lower():
                    skip = True
                    break
            if skip:
                continue

        # Remove \label right after section
        content = re.sub(r'^\s*\\label\{[^}]*\}\s*', '', content)

        sections.append((title, content))

    return sections


# ============================================================================
# ENVIRONMENT CONVERSION
# ============================================================================
def convert_environments(text, environments, proof_label='Proof', card_stt=0):
    """Convert LaTeX theorem/box environments to styled HTML divs.

    Environments with css class env-theorem, env-definition, env-example are
    numbered per label type using card STT prefix (Option A):
      Định nghĩa 8.1, Định nghĩa 8.2, Định lý 8.1, Ví dụ 8.1, ...
    Box environments (box-*) and proof are not numbered.

    Args:
        text: Input text (math already protected).
        environments: dict mapping env_name -> (css_class, label).
        proof_label: Label for \\begin{proof}...\\end{proof}.
        card_stt: Card sequential number for numbering prefix.

    Returns:
        Converted text.
    """
    NUMBERED_CSS = {'env-theorem', 'env-definition', 'env-example'}
    label_counters = {}  # {label: count}
    prefix = str(card_stt) if card_stt else ''

    for env_name, (css_class, label) in environments.items():
        should_number = css_class in NUMBERED_CSS

        # With title: \begin{env}[title]...\end{env}
        pat_title = re.compile(
            r'\\begin\{' + re.escape(env_name)
            + r'\}\[([^\]]*)\](.*?)\\end\{'
            + re.escape(env_name) + r'\}',
            re.DOTALL)

        def repl_title(m, cc=css_class, lb=label, sn=should_number):
            t = m.group(1).strip()
            c = m.group(2).strip()
            if sn:
                label_counters[lb] = label_counters.get(lb, 0) + 1
                num = f'{prefix}.{label_counters[lb]}' if prefix else str(label_counters[lb])
                ts = f"{lb} {num} ({t})" if t else f"{lb} {num}"
            else:
                ts = f"{lb} ({t})" if t else lb
            return f'<div class="{cc}"><strong>{ts}:</strong><br>\n{c}\n</div>'
        text = pat_title.sub(repl_title, text)

        # Without title: \begin{env}...\end{env}
        pat_no = re.compile(
            r'\\begin\{' + re.escape(env_name)
            + r'\}(.*?)\\end\{' + re.escape(env_name) + r'\}',
            re.DOTALL)

        def repl_no(m, cc=css_class, lb=label, sn=should_number):
            c = m.group(1).strip()
            if sn:
                label_counters[lb] = label_counters.get(lb, 0) + 1
                num = f'{prefix}.{label_counters[lb]}' if prefix else str(label_counters[lb])
                ts = f"{lb} {num}"
            else:
                ts = lb
            return f'<div class="{cc}"><strong>{ts}:</strong><br>\n{c}\n</div>'
        text = pat_no.sub(repl_no, text)

    # Standard proof environment (not numbered)
    text = re.sub(
        r'\\begin\{proof\}(.*?)\\end\{proof\}',
        lambda m: (
            f'<div class="env-proof"><strong>{proof_label}:</strong>'
            f'<br>\n{m.group(1).strip()}\n</div>'
        ),
        text, flags=re.DOTALL)

    return text


# ============================================================================
# TABLE CONVERSION
# ============================================================================
def _table_repl(m):
    """Shared replacement callback for tabular and longtable.

    Handles: longtable-specific commands, toprule/midrule/bottomrule/hline,
    caption, label, rowcolor, definecolor, renewcommand, textcolor,
    row splitting with optional \\\\[6pt] spacing, and duplicate header
    deduplication for longtable.
    """
    content = m.group(1).strip()

    # Remove longtable-specific commands
    content = re.sub(
        r'\\(endfirsthead|endhead|endfoot|endlastfoot)\s*', '', content)
    # Remove rules and hlines
    content = re.sub(
        r'\\(toprule|midrule|bottomrule|hline)\s*', '', content)
    # Remove \caption{...} and \label{...}
    content = re.sub(r'\\caption\{[^}]*\}\s*', '', content)
    content = re.sub(r'\\label\{[^}]*\}\s*', '', content)
    # Remove styling commands
    content = re.sub(r'\\rowcolor\{[^}]*\}\s*', '', content)
    content = re.sub(
        r'\\definecolor\{[^}]*\}\{[^}]*\}\{[^}]*\}\s*', '', content)
    content = re.sub(
        r'\\renewcommand\{[^}]*\}\{[^}]*\}\s*', '', content)
    # \textcolor{...}{CONTENT} -> CONTENT
    content = re.sub(
        r'\\textcolor\{[^}]*\}\{((?:[^{}]|\{[^{}]*\})*)\}',
        r'\1', content)

    # Split rows (handle optional \\[6pt] spacing)
    rows = [r.strip() for r in re.split(r'\\\\(?:\[[^\]]*\])?', content)
            if r.strip()]
    if not rows:
        return ''

    html = (
        '<table style="width:100%;border-collapse:collapse;margin:16px 0;'
        'border-radius:8px;overflow:hidden;'
        'box-shadow:0 1px 4px rgba(0,0,0,0.08);font-size:0.95em;">\n'
    )

    # Deduplicate repeated headers (longtable \endfirsthead/\endhead)
    seen_header = None
    data_rows = []
    for row in rows:
        cells_text = '|'.join(c.strip() for c in row.split('&'))
        if seen_header is None:
            seen_header = cells_text
            data_rows.append(row)
        elif cells_text == seen_header:
            continue  # skip duplicate header
        else:
            data_rows.append(row)

    for i, row in enumerate(data_rows):
        cells = [c.strip() for c in row.split('&')]
        if i == 0:
            html += '<thead><tr>\n'
            for cell in cells:
                html += (
                    f'  <th style="padding:10px 14px;font-weight:700;'
                    f'background:#1a365d;color:#fff;">{cell}</th>\n'
                )
            html += '</tr></thead>\n<tbody>\n'
        else:
            bg = '#fff' if i % 2 == 1 else '#f7fafc'
            html += f'<tr style="background:{bg};">\n'
            for cell in cells:
                border = (
                    'border-bottom:1px solid #e2e8f0;'
                    if i < len(data_rows) - 1 else ''
                )
                html += f'  <td style="padding:9px 14px;{border}">{cell}</td>\n'
            html += '</tr>\n'

    html += '</tbody></table>'
    return html


def convert_tabular(text):
    """Convert LaTeX tabular and longtable to styled HTML tables.

    Uses nested-braces-aware column spec regex: {p{3.5cm}p{1.6cm}...}
    """
    # Column spec handles nested braces like {p{3.5cm}p{1.6cm}p{6.5cm}}
    col_spec = r'\{(?:[^{}]|\{[^{}]*\})*\}'

    # Handle longtable first (more specific)
    pat_long = re.compile(
        r'\\begin\{longtable\}' + col_spec
        + r'(.*?)\\end\{longtable\}', re.DOTALL)
    text = pat_long.sub(_table_repl, text)

    # Handle regular tabular
    pat_tab = re.compile(
        r'\\begin\{tabular\}' + col_spec
        + r'(.*?)\\end\{tabular\}', re.DOTALL)
    text = pat_tab.sub(_table_repl, text)

    return text


# ============================================================================
# LIST CONVERSION
# ============================================================================
def convert_lists(text):
    """Convert LaTeX itemize/enumerate to HTML ul/ol.

    Handles nested lists by processing innermost first (up to 20 levels).
    """
    # Remove enumerate options like [label=(...)]
    text = re.sub(
        r'\\begin\{enumerate\}\[[^\]]*\]', r'\\begin{enumerate}', text)

    for _ in range(20):
        # Find innermost itemize or enumerate
        m = re.search(
            r'\\begin\{(itemize|enumerate)\}'
            r'((?:(?!\\begin\{(?:itemize|enumerate)\})'
            r'(?!\\end\{(?:itemize|enumerate)\}).)*?)'
            r'\\end\{\1\}',
            text, re.DOTALL)
        if not m:
            break

        tag = 'ul' if m.group(1) == 'itemize' else 'ol'
        content = m.group(2)
        items = re.split(r'\\item\b', content)
        html_items = []
        for item in items:
            item = item.strip()
            if not item:
                continue
            # Remove optional item label like [(a)]
            item = re.sub(r'^\[[^\]]*\]\s*', '', item)
            html_items.append(f'<li>{item}</li>')

        if html_items:
            html_list = f'<{tag}>\n' + '\n'.join(html_items) + f'\n</{tag}>'
        else:
            html_list = ''
        text = text[:m.start()] + html_list + text[m.end():]

    return text


# ============================================================================
# HEADING NUMBERING
# ============================================================================
def _number_headings(text, card_stt=0):
    """Convert \\subsection, \\subsubsection, \\paragraph to numbered HTML headings.

    Numbering uses card STT as prefix:
      \\subsection       -> <h4>8.1. Title</h4>
      \\subsubsection    -> <h5>8.1.1. Title</h5>
      \\paragraph        -> <h6>8.1.1.1. Title</h6>
    """
    heading_pat = re.compile(
        r'\\(subsection|subsubsection|paragraph)\*?\{((?:[^{}]|\{[^{}]*\})*)\}'
    )

    prefix = str(card_stt) if card_stt else ''
    subsec = [0]
    subsubsec = [0]
    para = [0]

    def _repl(m):
        level = m.group(1)
        title = m.group(2).strip()
        # Remove \label inside title
        title = re.sub(r'\\label\{[^}]*\}\s*', '', title)

        if level == 'subsection':
            subsec[0] += 1
            subsubsec[0] = 0
            para[0] = 0
            num = f'{prefix}.{subsec[0]}' if prefix else str(subsec[0])
            return f'<h4>{num}. {title}</h4>'
        elif level == 'subsubsection':
            subsubsec[0] += 1
            para[0] = 0
            num = f'{prefix}.{subsec[0]}.{subsubsec[0]}' if prefix else f'{subsec[0]}.{subsubsec[0]}'
            return f'<h5>{num}. {title}</h5>'
        else:  # paragraph
            para[0] += 1
            if subsubsec[0] > 0:
                num = f'{prefix}.{subsec[0]}.{subsubsec[0]}.{para[0]}' if prefix else f'{subsec[0]}.{subsubsec[0]}.{para[0]}'
            elif subsec[0] > 0:
                num = f'{prefix}.{subsec[0]}.{para[0]}' if prefix else f'{subsec[0]}.{para[0]}'
            else:
                num = f'{prefix}.{para[0]}' if prefix else str(para[0])
            return f'<h6>{num}. {title}</h6>'

    return heading_pat.sub(_repl, text)


# ============================================================================
# CODE ENVIRONMENTS (verbatim, lstlisting, minted)
# ============================================================================
def extract_code_environments(text, card_stt=0):
    """Extract verbatim/lstlisting/minted environments and replace with placeholders.

    Must be called BEFORE math protection, because code content should be
    preserved literally (no LaTeX processing).

    Args:
        text: LaTeX content string.
        card_stt: Card sequential number for caption numbering prefix.

    Returns:
        (processed_text, placeholders_dict)
    """
    placeholders = {}
    counter = [0]
    listing_counter = [0]  # For numbered captions
    prefix = str(card_stt) if card_stt else ''

    def _placeholder(html):
        key = f'@@CODE_BLOCK_{counter[0]}@@'
        counter[0] += 1
        placeholders[key] = html
        return key

    def _escape(s):
        return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    CODE_STYLE = (
        'background:#f6f8fa; border:1px solid #e1e4e8; border-radius:6px; '
        'padding:1em; overflow-x:auto; font-size:0.9em; line-height:1.5'
    )
    CAP_STYLE = 'text-align:center;font-size:0.9em;color:#586069'

    # --- verbatim ---
    def _verbatim_repl(m):
        content = _escape(m.group(1).strip())
        html = f'<pre style="{CODE_STYLE}"><code>{content}</code></pre>'
        return _placeholder(html)

    text = re.sub(
        r'\\begin\{verbatim\}(.*?)\\end\{verbatim\}',
        _verbatim_repl, text, flags=re.DOTALL)

    # --- lstlisting (with optional [language=X,...]) ---
    def _lst_repl(m):
        opts = m.group(1) or ''
        content = _escape(m.group(2).strip())
        lang = ''
        lang_m = re.search(r'language\s*=\s*(\w+)', opts)
        if lang_m:
            lang = lang_m.group(1)
        caption = ''
        cap_m = re.search(r'caption\s*=\s*\{?((?:[^},]|\{[^}]*\})*)', opts)
        if cap_m:
            caption = cap_m.group(1).strip().strip('{}')

        # Numbered caption if present
        cap_html = ''
        if caption:
            listing_counter[0] += 1
            num = f'{prefix}.{listing_counter[0]}' if prefix else str(listing_counter[0])
            cap_html = (f'<p style="{CAP_STYLE}">'
                        f'<em>Listing {num}: {caption}</em></p>')

        label = f' data-lang="{lang}"' if lang else ''
        lang_badge = (f'<div style="text-align:right;font-size:0.8em;color:#6a737d;'
                      f'margin-bottom:0.3em">{lang}</div>') if lang else ''
        html = f'{lang_badge}<pre style="{CODE_STYLE}"{label}><code>{content}</code></pre>{cap_html}'
        return _placeholder(html)

    text = re.sub(
        r'\\begin\{lstlisting\}\s*(?:\[([^\]]*)\])?\s*(.*?)\\end\{lstlisting\}',
        _lst_repl, text, flags=re.DOTALL)

    # --- minted (with {language} and optional [caption=...]) ---
    def _minted_repl(m):
        opts = m.group(1) or ''
        lang = m.group(2) or ''
        content = _escape(m.group(3).strip())

        # Check for caption in options
        caption = ''
        cap_m = re.search(r'caption\s*=\s*\{?((?:[^},]|\{[^}]*\})*)', opts)
        if cap_m:
            caption = cap_m.group(1).strip().strip('{}')

        cap_html = ''
        if caption:
            listing_counter[0] += 1
            num = f'{prefix}.{listing_counter[0]}' if prefix else str(listing_counter[0])
            cap_html = (f'<p style="{CAP_STYLE}">'
                        f'<em>Listing {num}: {caption}</em></p>')

        lang_badge = (f'<div style="text-align:right;font-size:0.8em;color:#6a737d;'
                      f'margin-bottom:0.3em">{lang}</div>') if lang else ''
        html = f'{lang_badge}<pre style="{CODE_STYLE}"><code>{content}</code></pre>{cap_html}'
        return _placeholder(html)

    text = re.sub(
        r'\\begin\{minted\}\s*(?:\[([^\]]*)\])?\s*\{(\w+)\}\s*(.*?)\\end\{minted\}',
        _minted_repl, text, flags=re.DOTALL)

    # --- Inline: \verb|...|, \lstinline|...|, \lstinline{...}, \mintinline{lang}{...} ---
    INLINE_STYLE = 'background:#f0f0f0; padding:0.15em 0.4em; border-radius:3px; font-family:monospace; font-size:0.9em'

    text = re.sub(
        r'\\verb\|([^|]*)\|',
        lambda m: f'<code style="{INLINE_STYLE}">{_escape(m.group(1))}</code>', text)
    text = re.sub(
        r'\\verb\+([^+]*)\+',
        lambda m: f'<code style="{INLINE_STYLE}">{_escape(m.group(1))}</code>', text)
    text = re.sub(
        r'\\lstinline\|([^|]*)\|',
        lambda m: f'<code style="{INLINE_STYLE}">{_escape(m.group(1))}</code>', text)
    text = re.sub(
        r'\\lstinline\{([^}]*)\}',
        lambda m: f'<code style="{INLINE_STYLE}">{_escape(m.group(1))}</code>', text)
    text = re.sub(
        r'\\mintinline\{\w+\}\{([^}]*)\}',
        lambda m: f'<code style="{INLINE_STYLE}">{_escape(m.group(1))}</code>', text)

    return text, placeholders


def restore_code_placeholders(text, placeholders):
    """Restore code block placeholders after all other processing."""
    for key, html in placeholders.items():
        text = text.replace(key, html)
    return text


# ============================================================================
# ALGORITHM / PSEUDOCODE ENVIRONMENTS
# ============================================================================
def _extract_brace_arg(text, start=0):
    """Extract content of first {...} starting at or after position start.

    Returns (content, end_pos) or ('', start) if no braces found.
    """
    idx = text.find('{', start)
    if idx < 0:
        return '', start
    depth = 0
    begin = idx + 1
    for i in range(idx, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return text[begin:i], i + 1
    return text[begin:], len(text)


def _convert_algorithmic_content(content):
    """Convert algorithmic commands to HTML lines with indentation.

    Handles: \\State, \\If/\\ElsIf/\\Else/\\EndIf, \\While/\\EndWhile,
    \\For/\\ForAll/\\EndFor, \\Repeat/\\Until, \\Return, \\Require, \\Ensure,
    \\Function/\\EndFunction, \\Procedure/\\EndProcedure, \\Comment, \\Call.
    """
    KW = '<span style="color:#0366d6;font-weight:bold">'
    KWE = '</span>'
    CMT = '<span style="color:#6a737d;font-style:italic">'
    CMTE = '</span>'

    # Ensure each command starts on a new line
    cmd_names = (
        'State|If|ElsIf|Else|EndIf|While|EndWhile|For|ForAll|EndFor|'
        'Repeat|Until|Loop|EndLoop|Return|Require|Ensure|'
        'Function|EndFunction|Procedure|EndProcedure|Comment'
    )
    content = re.sub(rf'(\\(?:{cmd_names})\b)', r'\n\1', content)

    lines_html = []
    indent = 0

    def _line(ind, html):
        pad = ind * 1.5
        lines_html.append(f'<div style="padding-left:{pad}em">{html}</div>')

    def _handle_comment_in(text_str):
        """Replace \\Comment{...} inline with styled comment."""
        return re.sub(
            r'\\Comment\{((?:[^{}]|\{[^{}]*\})*)\}',
            lambda m: f' {CMT}&#x25B7; {m.group(1)}{CMTE}',
            text_str)

    for raw_line in content.split('\n'):
        line = raw_line.strip()
        if not line:
            continue

        # --- End commands (decrease indent) ---
        end_m = re.match(r'\\End(If|While|For|Loop|Function|Procedure)\b', line)
        if end_m:
            indent = max(0, indent - 1)
            kw_map = {
                'If': 'end if', 'While': 'end while', 'For': 'end for',
                'Loop': 'end loop', 'Function': 'end function',
                'Procedure': 'end procedure'
            }
            _line(indent, f'{KW}{kw_map[end_m.group(1)]}{KWE}')
            continue

        # --- Else ---
        if re.match(r'\\Else\b', line) and not line.startswith('\\ElsIf'):
            indent = max(0, indent - 1)
            _line(indent, f'{KW}else{KWE}')
            indent += 1
            continue

        # --- ElsIf ---
        if line.startswith('\\ElsIf'):
            indent = max(0, indent - 1)
            cond, _ = _extract_brace_arg(line, 6)
            _line(indent, f'{KW}else if{KWE} {cond} {KW}then{KWE}')
            indent += 1
            continue

        # --- If ---
        if line.startswith('\\If'):
            cond, _ = _extract_brace_arg(line, 3)
            _line(indent, f'{KW}if{KWE} {cond} {KW}then{KWE}')
            indent += 1
            continue

        # --- While ---
        if line.startswith('\\While'):
            cond, _ = _extract_brace_arg(line, 6)
            _line(indent, f'{KW}while{KWE} {cond} {KW}do{KWE}')
            indent += 1
            continue

        # --- For / ForAll ---
        if line.startswith('\\ForAll'):
            cond, _ = _extract_brace_arg(line, 7)
            _line(indent, f'{KW}for all{KWE} {cond} {KW}do{KWE}')
            indent += 1
            continue
        if line.startswith('\\For'):
            cond, _ = _extract_brace_arg(line, 4)
            _line(indent, f'{KW}for{KWE} {cond} {KW}do{KWE}')
            indent += 1
            continue

        # --- Repeat / Until ---
        if line.startswith('\\Repeat'):
            _line(indent, f'{KW}repeat{KWE}')
            indent += 1
            continue
        if line.startswith('\\Until'):
            indent = max(0, indent - 1)
            cond, _ = _extract_brace_arg(line, 6)
            _line(indent, f'{KW}until{KWE} {cond}')
            continue

        # --- Loop ---
        if line.startswith('\\Loop'):
            _line(indent, f'{KW}loop{KWE}')
            indent += 1
            continue

        # --- Function / Procedure ---
        if line.startswith('\\Function') or line.startswith('\\Procedure'):
            is_func = line.startswith('\\Function')
            cmd_len = 9 if is_func else 10
            kw = 'function' if is_func else 'procedure'
            name, pos = _extract_brace_arg(line, cmd_len)
            params, _ = _extract_brace_arg(line, pos)
            _line(indent, f'{KW}{kw}{KWE} <span style="font-variant:small-caps">{name}</span>({params})')
            indent += 1
            continue

        # --- Require / Ensure ---
        if line.startswith('\\Require'):
            rest = _handle_comment_in(line[8:].strip())
            _line(indent, f'{KW}Require:{KWE} {rest}')
            continue
        if line.startswith('\\Ensure'):
            rest = _handle_comment_in(line[7:].strip())
            _line(indent, f'{KW}Ensure:{KWE} {rest}')
            continue

        # --- Return ---
        if line.startswith('\\Return'):
            rest = _handle_comment_in(line[7:].strip())
            _line(indent, f'{KW}return{KWE} {rest}')
            continue

        # --- State ---
        if line.startswith('\\State'):
            rest = _handle_comment_in(line[6:].strip())
            # Handle \Call{Name}{args}
            rest = re.sub(
                r'\\Call\{(\w+)\}\{((?:[^{}]|\{[^{}]*\})*)\}',
                lambda m: f'<span style="font-variant:small-caps">{m.group(1)}</span>({m.group(2)})',
                rest)
            _line(indent, rest)
            continue

        # --- Comment ---
        if line.startswith('\\Comment'):
            ctext, _ = _extract_brace_arg(line, 8)
            _line(indent, f'{CMT}&#x25B7; {ctext}{CMTE}')
            continue

        # --- Plain text (shouldn't happen often) ---
        if line and not line.startswith('\\'):
            _line(indent, _handle_comment_in(line))

    return '\n'.join(lines_html)


def _convert_algorithm2e_content(content):
    """Convert algorithm2e commands to HTML lines with indentation.

    algorithm2e uses different syntax: block-based {body} instead of \\End*.
    Handles: \\KwIn, \\KwOut, \\KwData, \\KwResult, \\If/\\ElseIf/\\Else,
    \\While, \\For, \\ForEach, \\Return, \\tcp, \\tcc.
    """
    KW = '<span style="color:#0366d6;font-weight:bold">'
    KWE = '</span>'
    CMT = '<span style="color:#6a737d;font-style:italic">'
    CMTE = '</span>'

    # algorithm2e uses \; as line terminator — remove it
    content = content.replace('\\;', '')

    # Handle \tcp{...} and \tcc{...} (inline comments)
    content = re.sub(
        r'\\tcp\*?\{((?:[^{}]|\{[^{}]*\})*)\}',
        lambda m: f' {CMT}// {m.group(1)}{CMTE}', content)
    content = re.sub(
        r'\\tcc\*?\{((?:[^{}]|\{[^{}]*\})*)\}',
        lambda m: f' {CMT}/* {m.group(1)} */{CMTE}', content)

    lines_html = []
    indent = 0

    def _line(ind, html):
        pad = ind * 1.5
        lines_html.append(f'<div style="padding-left:{pad}em">{html}</div>')

    # Split into lines
    for raw_line in content.split('\n'):
        line = raw_line.strip()
        if not line:
            continue

        # End markers
        if line == '}':
            indent = max(0, indent - 1)
            continue

        # \KwIn, \KwOut, \KwData, \KwResult
        kw_m = re.match(r'\\Kw(In|Out|Data|Result)\{((?:[^{}]|\{[^{}]*\})*)\}', line)
        if kw_m:
            kw_name = {'In': 'Input', 'Out': 'Output', 'Data': 'Data', 'Result': 'Result'}
            _line(indent, f'{KW}{kw_name[kw_m.group(1)]}:{KWE} {kw_m.group(2)}')
            continue

        # \If{cond}{body} or \uIf{cond}{body}\ElseIf...
        if_m = re.match(r'\\(?:u)?If\{((?:[^{}]|\{[^{}]*\})*)\}\s*\{', line)
        if if_m:
            _line(indent, f'{KW}if{KWE} {if_m.group(1)} {KW}then{KWE}')
            indent += 1
            continue

        elif_m = re.match(r'\\(?:u)?ElseIf\{((?:[^{}]|\{[^{}]*\})*)\}\s*\{', line)
        if elif_m:
            indent = max(0, indent - 1)
            _line(indent, f'{KW}else if{KWE} {elif_m.group(1)} {KW}then{KWE}')
            indent += 1
            continue

        if re.match(r'\\Else\s*\{', line):
            indent = max(0, indent - 1)
            _line(indent, f'{KW}else{KWE}')
            indent += 1
            continue

        # \While{cond}{body}
        while_m = re.match(r'\\While\{((?:[^{}]|\{[^{}]*\})*)\}\s*\{', line)
        if while_m:
            _line(indent, f'{KW}while{KWE} {while_m.group(1)} {KW}do{KWE}')
            indent += 1
            continue

        # \For{cond}{body}
        for_m = re.match(r'\\(?:For|ForEach)\{((?:[^{}]|\{[^{}]*\})*)\}\s*\{', line)
        if for_m:
            kw = 'for each' if 'ForEach' in line else 'for'
            _line(indent, f'{KW}{kw}{KWE} {for_m.group(1)} {KW}do{KWE}')
            indent += 1
            continue

        # \Return
        ret_m = re.match(r'\\Return\b\s*(.*)', line)
        if ret_m:
            _line(indent, f'{KW}return{KWE} {ret_m.group(1)}')
            continue

        # Plain statement
        _line(indent, line)

    return '\n'.join(lines_html)


def convert_algorithm_environments(text, card_stt=0):
    """Convert algorithm/algorithmic and algorithm2e environments to styled HTML.

    Should be called AFTER math protection (algorithm content often has $...$).
    The math placeholders (@@MATH_n@@) inside will be restored later by restore_math().
    """
    algo_counter = [0]

    ALGO_STYLE = (
        'background:#f8f9fa; border:1px solid #dee2e6; border-radius:6px; '
        'padding:1em; margin:1em 0'
    )
    PSEUDO_STYLE = 'font-size:0.95em; line-height:1.8'

    def _algo_repl(m):
        content = m.group(1)
        algo_counter[0] += 1

        # Extract caption
        cap_m = re.search(r'\\caption\{((?:[^{}]|\{[^{}]*\})*)\}', content)
        caption = cap_m.group(1) if cap_m else ''

        # Detect algorithmic variant
        algo_m = re.search(
            r'\\begin\{algorithmic\}\s*(?:\[\d+\])?\s*(.*?)\\end\{algorithmic\}',
            content, re.DOTALL)

        if algo_m:
            body_html = _convert_algorithmic_content(algo_m.group(1))
        else:
            # Maybe the whole content is algorithmic (no explicit \begin{algorithmic})
            body_html = _convert_algorithmic_content(content)

        num = f'{card_stt}.{algo_counter[0]}' if card_stt else str(algo_counter[0])
        cap_html = (
            f'<p style="font-weight:bold;margin-bottom:0.5em">'
            f'Thuật toán {num}: {caption}</p>'
        ) if caption else (
            f'<p style="font-weight:bold;margin-bottom:0.5em">'
            f'Thuật toán {num}</p>'
        )

        return (
            f'<div class="algorithm-box" style="{ALGO_STYLE}">\n'
            f'{cap_html}\n'
            f'<div class="pseudocode" style="{PSEUDO_STYLE}">\n{body_html}\n</div>\n'
            f'</div>'
        )

    # \begin{algorithm}...\end{algorithm}
    text = re.sub(
        r'\\begin\{algorithm\}\s*(?:\[[^\]]*\])?\s*(.*?)\\end\{algorithm\}',
        _algo_repl, text, flags=re.DOTALL)

    # Standalone \begin{algorithmic}...\end{algorithmic} (without algorithm wrapper)
    def _standalone_algorithmic(m):
        algo_counter[0] += 1
        body_html = _convert_algorithmic_content(m.group(1))
        num = f'{card_stt}.{algo_counter[0]}' if card_stt else str(algo_counter[0])
        return (
            f'<div class="algorithm-box" style="{ALGO_STYLE}">\n'
            f'<p style="font-weight:bold;margin-bottom:0.5em">Thuật toán {num}</p>\n'
            f'<div class="pseudocode" style="{PSEUDO_STYLE}">\n{body_html}\n</div>\n'
            f'</div>'
        )

    text = re.sub(
        r'\\begin\{algorithmic\}\s*(?:\[\d+\])?\s*(.*?)\\end\{algorithmic\}',
        _standalone_algorithmic, text, flags=re.DOTALL)

    # algorithm2e: \begin{algorithm2e}...\end{algorithm2e}
    def _algo2e_repl(m):
        content = m.group(1)
        algo_counter[0] += 1

        cap_m = re.search(r'\\caption\{((?:[^{}]|\{[^{}]*\})*)\}', content)
        caption = cap_m.group(1) if cap_m else ''
        if cap_m:
            content = content[:cap_m.start()] + content[cap_m.end():]

        body_html = _convert_algorithm2e_content(content)

        num = f'{card_stt}.{algo_counter[0]}' if card_stt else str(algo_counter[0])
        cap_html = (
            f'<p style="font-weight:bold;margin-bottom:0.5em">'
            f'Thuật toán {num}: {caption}</p>'
        ) if caption else (
            f'<p style="font-weight:bold;margin-bottom:0.5em">'
            f'Thuật toán {num}</p>'
        )

        return (
            f'<div class="algorithm-box" style="{ALGO_STYLE}">\n'
            f'{cap_html}\n'
            f'<div class="pseudocode" style="{PSEUDO_STYLE}">\n{body_html}\n</div>\n'
            f'</div>'
        )

    text = re.sub(
        r'\\begin\{algorithm2e\}\s*(?:\[[^\]]*\])?\s*(.*?)\\end\{algorithm2e\}',
        _algo2e_repl, text, flags=re.DOTALL)

    return text


# ============================================================================
# TIKZ / DIAGRAM PRE-RENDERING
# ============================================================================
def convert_tikz_environments(text, preamble_snippet='', root_dir=''):
    """Pre-render tikzpicture environments to PNG and embed as base64.

    Uses pdflatex to compile a standalone document, then pdftoppm to convert to PNG.
    Falls back to a placeholder if compilation tools are not available.

    Args:
        text: LaTeX content string.
        preamble_snippet: Extra preamble lines (tikz libraries, etc.).
        root_dir: Root directory of the LaTeX project (for resolving styles).

    Returns:
        Text with tikzpicture replaced by <img> or placeholder.
    """
    import subprocess
    import tempfile
    import shutil

    # Prefer xelatex (handles UTF-8 natively), fallback to pdflatex
    latex_cmd = shutil.which('xelatex') or shutil.which('pdflatex')
    pdftoppm = shutil.which('pdftoppm')
    if not latex_cmd:
        # Can't pre-render, replace with placeholder
        text = re.sub(
            r'\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}',
            lambda m: '<div style="background:#fff3cd;border:1px solid #ffc107;'
                      'border-radius:6px;padding:1em;margin:1em 0;text-align:center">'
                      '<em>[TikZ diagram — xelatex/pdflatex not available]</em></div>',
            text, flags=re.DOTALL)
        return text

    tikz_counter = [0]

    def _tikz_repl(m):
        tikz_code = m.group(0)
        tikz_counter[0] += 1
        print(f"  Pre-rendering TikZ diagram #{tikz_counter[0]}...", file=sys.stderr)

        # Build standalone LaTeX document (xelatex-compatible for UTF-8)
        doc = (
            '\\documentclass[border=5pt]{standalone}\n'
            '\\usepackage{fontspec}\n'
            '\\usepackage{tikz}\n'
            '\\usetikzlibrary{arrows,arrows.meta,shapes,shapes.geometric,'
            'positioning,calc,decorations.pathreplacing,fit,backgrounds,'
            'matrix,patterns}\n'
            '\\usepackage{amsmath,amssymb}\n'
        )
        if preamble_snippet:
            doc += preamble_snippet + '\n'
        doc += (
            '\\begin{document}\n'
            f'{tikz_code}\n'
            '\\end{document}\n'
        )

        with tempfile.TemporaryDirectory(prefix='tikz_') as tmpdir:
            tex_path = os.path.join(tmpdir, 'tikz.tex')
            pdf_path = os.path.join(tmpdir, 'tikz.pdf')

            with open(tex_path, 'w', encoding='utf-8') as f:
                f.write(doc)

            # Compile with pdflatex
            try:
                result = subprocess.run(
                    [latex_cmd, '-interaction=nonstopmode', '-halt-on-error',
                     '-output-directory', tmpdir, tex_path],
                    capture_output=True, text=True, timeout=30)
            except subprocess.TimeoutExpired:
                print(f"  WARNING: TikZ #{tikz_counter[0]} compilation timed out",
                      file=sys.stderr)
                return _tikz_placeholder(tikz_counter[0])

            if not os.path.isfile(pdf_path):
                print(f"  WARNING: TikZ #{tikz_counter[0]} compilation failed:\n"
                      f"    {result.stderr[-300:] if result.stderr else 'no output'}",
                      file=sys.stderr)
                return _tikz_placeholder(tikz_counter[0])

            # Convert PDF to PNG
            if pdftoppm:
                png_prefix = os.path.join(tmpdir, 'tikz')
                try:
                    subprocess.run(
                        [pdftoppm, '-png', '-r', '200', '-singlefile',
                         pdf_path, png_prefix],
                        capture_output=True, timeout=10)
                except subprocess.TimeoutExpired:
                    return _tikz_placeholder(tikz_counter[0])

                png_path = png_prefix + '.png'
                if os.path.isfile(png_path):
                    with open(png_path, 'rb') as f:
                        data = base64.b64encode(f.read()).decode('ascii')
                    size_kb = os.path.getsize(png_path) // 1024
                    print(f"  Embedded TikZ #{tikz_counter[0]}: {size_kb}KB",
                          file=sys.stderr)
                    return (f'<div style="text-align:center;margin:1em 0">'
                            f'<img src="data:image/png;base64,{data}" '
                            f'style="max-width:90%;display:inline-block" '
                            f'alt="TikZ diagram {tikz_counter[0]}">'
                            f'</div>')

            return _tikz_placeholder(tikz_counter[0])

    def _tikz_placeholder(num):
        return (
            '<div style="background:#fff3cd;border:1px solid #ffc107;'
            'border-radius:6px;padding:1em;margin:1em 0;text-align:center">'
            f'<em>[TikZ diagram #{num} — rendering failed]</em></div>'
        )

    text = re.sub(
        r'\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}',
        _tikz_repl, text, flags=re.DOTALL)

    # Also handle \begin{tikzcd}...\end{tikzcd} (commutative diagrams)
    text = re.sub(
        r'\\begin\{tikzcd\}.*?\\end\{tikzcd\}',
        lambda m: _tikz_repl_cd(m, tikz_counter, preamble_snippet, latex_cmd, pdftoppm),
        text, flags=re.DOTALL)

    return text


def _tikz_repl_cd(m, counter, preamble, latex_cmd, pdftoppm):
    """Pre-render tikzcd (commutative diagram) environment."""
    import subprocess
    import tempfile

    tikzcd_code = m.group(0)
    counter[0] += 1
    print(f"  Pre-rendering tikzcd diagram #{counter[0]}...", file=sys.stderr)

    doc = (
        '\\documentclass[border=5pt]{standalone}\n'
        '\\usepackage{fontspec}\n'
        '\\usepackage{tikz}\n'
        '\\usepackage{tikz-cd}\n'
        '\\usepackage{amsmath,amssymb}\n'
    )
    if preamble:
        doc += preamble + '\n'
    doc += f'\\begin{{document}}\n{tikzcd_code}\n\\end{{document}}\n'

    with tempfile.TemporaryDirectory(prefix='tikzcd_') as tmpdir:
        tex_path = os.path.join(tmpdir, 'tikzcd.tex')
        pdf_path = os.path.join(tmpdir, 'tikzcd.pdf')

        with open(tex_path, 'w', encoding='utf-8') as f:
            f.write(doc)

        try:
            subprocess.run(
                [latex_cmd, '-interaction=nonstopmode', '-halt-on-error',
                 '-output-directory', tmpdir, tex_path],
                capture_output=True, text=True, timeout=30)
        except (subprocess.TimeoutExpired, Exception):
            pass

        if os.path.isfile(pdf_path) and pdftoppm:
            png_prefix = os.path.join(tmpdir, 'tikzcd')
            try:
                subprocess.run(
                    [pdftoppm, '-png', '-r', '200', '-singlefile',
                     pdf_path, png_prefix],
                    capture_output=True, timeout=10)
            except (subprocess.TimeoutExpired, Exception):
                pass

            png_path = png_prefix + '.png'
            if os.path.isfile(png_path):
                with open(png_path, 'rb') as f:
                    data = base64.b64encode(f.read()).decode('ascii')
                size_kb = os.path.getsize(png_path) // 1024
                print(f"  Embedded tikzcd #{counter[0]}: {size_kb}KB",
                      file=sys.stderr)
                return (f'<div style="text-align:center;margin:1em 0">'
                        f'<img src="data:image/png;base64,{data}" '
                        f'style="max-width:90%;display:inline-block" '
                        f'alt="Commutative diagram {counter[0]}">'
                        f'</div>')

    return (
        '<div style="background:#fff3cd;border:1px solid #ffc107;'
        'border-radius:6px;padding:1em;margin:1em 0;text-align:center">'
        f'<em>[Commutative diagram #{counter[0]} — rendering failed]</em></div>'
    )


# ============================================================================
# IMAGE CONVERSION
# ============================================================================
def convert_includegraphics(text, images_dir=None):
    """Convert \\includegraphics[options]{filename} to <img> tags with base64 data URI.

    Searches for image files in images_dir (and common subdirectories).
    Embeds images as base64 so the HTML remains self-contained.

    Args:
        text: LaTeX content string.
        images_dir: Single directory path (str) or list of directory paths.
    """
    if images_dir is None:
        # Just strip \includegraphics if no images_dir
        text = re.sub(r'\\includegraphics\s*(?:\[[^\]]*\])?\s*\{[^}]*\}', '', text)
        return text

    # Normalize to list
    if isinstance(images_dir, str):
        images_dirs = [images_dir]
    else:
        images_dirs = list(images_dir)

    MIME_TYPES = {
        '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.gif': 'image/gif', '.svg': 'image/svg+xml', '.pdf': 'application/pdf',
    }

    def _repl(m):
        opts = m.group(1) or ''
        filename = m.group(2).strip()

        # Parse width from options
        style_parts = []
        w = re.search(r'width\s*=\s*([\d.]+)\\(textwidth|linewidth)', opts)
        if w:
            pct = float(w.group(1)) * 100
            style_parts.append(f'max-width:{pct:.0f}%')
        w2 = re.search(r'width\s*=\s*([\d.]+(?:cm|mm|in|pt|em))', opts)
        if w2:
            style_parts.append(f'max-width:{w2.group(1)}')

        # Build search list from all image dirs + their parents + common subdirs
        search_dirs = []
        seen = set()
        for d in images_dirs:
            if d and d not in seen:
                search_dirs.append(d)
                seen.add(d)
            parent = os.path.dirname(d) if d else None
            if parent and parent not in seen:
                search_dirs.append(parent)
                seen.add(parent)
                for sub in ['figures', 'fig', 'imgs']:
                    sd = os.path.join(parent, sub)
                    if sd not in seen:
                        search_dirs.append(sd)
                        seen.add(sd)

        img_path = None
        for d in search_dirs:
            if not d or not os.path.isdir(d):
                continue
            candidate = os.path.join(d, filename)
            if os.path.isfile(candidate):
                img_path = candidate
                break
            # Try adding extensions
            for ext in ['.png', '.jpg', '.jpeg', '.svg', '.pdf']:
                if os.path.isfile(candidate + ext):
                    img_path = candidate + ext
                    break
            if img_path:
                break

        if not img_path:
            searched = ', '.join(d for d in images_dirs if d)
            print(f"  WARNING: Image not found: {filename} (searched: {searched})",
                  file=sys.stderr)
            return f'<p class="table-caption" style="text-align:center"><em>[Image: {filename}]</em></p>'

        # Read and encode as base64
        ext = os.path.splitext(img_path)[1].lower()
        mime = MIME_TYPES.get(ext, 'image/png')

        if ext == '.pdf':
            # PDF can't be embedded as <img>, skip
            print(f"  WARNING: PDF image skipped: {img_path}", file=sys.stderr)
            return f'<p class="table-caption" style="text-align:center"><em>[PDF Image: {filename}]</em></p>'

        try:
            with open(img_path, 'rb') as f:
                data = base64.b64encode(f.read()).decode('ascii')
            style = '; '.join(style_parts) if style_parts else 'max-width:80%'
            style += '; display:block; margin:0.8em auto'
            print(f"  Embedded image: {os.path.basename(img_path)} ({os.path.getsize(img_path)//1024}KB)",
                  file=sys.stderr)
            return f'<img src="data:{mime};base64,{data}" style="{style}" alt="{filename}">'
        except Exception as e:
            print(f"  WARNING: Failed to read image {img_path}: {e}", file=sys.stderr)
            return f'<p class="table-caption" style="text-align:center"><em>[Image: {filename}]</em></p>'

    text = re.sub(
        r'\\includegraphics\s*(?:\[([^\]]*)\])?\s*\{([^}]*)\}',
        _repl, text)
    return text


def latex_to_html(tex_content, environments=None, proof_label='Proof',
                  cross_ref_text='(see related section)', images_dir=None,
                  chapter_num=0, figure_counter=None, table_counter=None,
                  card_stt=0, tikz_preamble='', root_dir=''):
    """Convert LaTeX content to HTML, preserving all content.

    This is the core conversion pipeline:
      0a. Extract code environments (verbatim, lstlisting, minted) → placeholders
      0b. Pre-render TikZ diagrams → embedded PNG images
      1. Strip comments
      2. Remove page breaks, labels, formatting-only commands
      3. Protect math ($$, \\[, align, $)
      4. Convert algorithm/pseudocode environments
      5. Convert theorem/proof environments
      6. Convert figures (with numbering), tables, images
      7. Convert lists (itemize, enumerate)
      8. Convert headings, formatting, citations, cross-refs, URLs
      9. Convert special characters
     10. Wrap in paragraphs
     11. Restore math
     12. Restore code blocks

    Args:
        tex_content: Raw LaTeX content string.
        environments: Dict of environment name -> (css_class, label).
        proof_label: Label for proof environment.
        cross_ref_text: Text to use for \\cref/\\ref replacements.
        images_dir: Directory (str) or list of directories for \\includegraphics.
        chapter_num: Chapter number (for figure/table numbering).
        figure_counter: Mutable list [n] shared across sections in same chapter.
        table_counter: Mutable list [n] shared across sections in same chapter.
        card_stt: Card sequential number (for numbering prefixes).
        tikz_preamble: Extra preamble for TikZ compilation (libraries, etc.).
        root_dir: Root directory of the LaTeX project.

    Returns:
        HTML string.
    """
    if environments is None:
        environments = DEFAULT_ENVIRONMENTS

    text = strip_comments(tex_content)

    # Step 0a: Extract code environments BEFORE any processing
    text, code_placeholders = extract_code_environments(text, card_stt=card_stt)

    # Step 0b: Pre-render TikZ diagrams
    text = convert_tikz_environments(text, tikz_preamble, root_dir)

    # Remove page breaks
    text = re.sub(r'\\(newpage|clearpage|cleardoublepage)\b', '', text)
    # Remove labels
    text = re.sub(r'\\label\{[^}]*\}', '', text)
    # Handle texorpdfstring
    text = re.sub(
        r'\\texorpdfstring\{([^}]*)\}\{[^}]*\}', r'\1', text)
    # Remove formatting-only commands
    text = re.sub(
        r'\\definecolor\{[^}]*\}\{[^}]*\}\{[^}]*\}\s*', '', text)
    text = re.sub(r'\\renewcommand\{[^}]*\}\{[^}]*\}\s*', '', text)
    text = re.sub(r'\\setlength\{[^}]*\}\{[^}]*\}\s*', '', text)

    # Protect math
    text, math_store = protect_math(text)

    # Convert algorithm/pseudocode environments (after math protection)
    text = convert_algorithm_environments(text, card_stt=card_stt)

    # Convert theorem/proof environments
    text = convert_environments(text, environments, proof_label, card_stt=card_stt)

    # Number and convert figure environments
    if figure_counter is None:
        figure_counter = [0]
    if table_counter is None:
        table_counter = [0]

    def _figure_repl(m):
        body = m.group(1)
        figure_counter[0] += 1
        num = f"{card_stt}.{figure_counter[0]}" if card_stt else str(figure_counter[0])
        # Add number to caption
        body = re.sub(
            r'\\caption\{((?:[^{}]|\{[^{}]*\})*)\}',
            lambda cm: f'\\caption{{Hình {num}: {cm.group(1)}}}',
            body, count=1)
        return body

    def _table_env_repl(m):
        body = m.group(1)
        table_counter[0] += 1
        num = f"{card_stt}.{table_counter[0]}" if card_stt else str(table_counter[0])
        body = re.sub(
            r'\\caption\{((?:[^{}]|\{[^{}]*\})*)\}',
            lambda cm: f'\\caption{{Bảng {num}: {cm.group(1)}}}',
            body, count=1)
        return body

    # Process figure environments (number captions)
    text = re.sub(
        r'\\begin\{figure\}\s*(?:\[[^\]]*\])?\s*(.*?)\\end\{figure\}',
        _figure_repl, text, flags=re.DOTALL)
    # Process table environments (number captions)
    text = re.sub(
        r'\\begin\{table\}\s*(?:\[[^\]]*\])?\s*(.*?)\\end\{table\}',
        _table_env_repl, text, flags=re.DOTALL)

    # Convert remaining captions to styled paragraphs
    text = re.sub(r'\\centering\s*', '', text)
    text = re.sub(r'\\caption\{((?:[^{}]|\{[^{}]*\})*)\}',
                  r'<p class="table-caption" style="text-align:center"><em>\1</em></p>', text)
    # Convert images
    text = convert_includegraphics(text, images_dir)
    # Convert tables
    text = convert_tabular(text)
    # Remove center wrappers
    text = re.sub(r'\\begin\{center\}\s*', '', text)
    text = re.sub(r'\\end\{center\}\s*', '', text)
    # Convert lists
    text = convert_lists(text)

    # Headings — numbered with card STT prefix
    text = _number_headings(text, card_stt=card_stt)

    # Text formatting (repeat for nested commands)
    for _ in range(3):
        text = re.sub(
            r'\\textbf\{((?:[^{}]|\{[^{}]*\})*)\}',
            r'<strong>\1</strong>', text)
        text = re.sub(
            r'\\textit\{((?:[^{}]|\{[^{}]*\})*)\}',
            r'<em>\1</em>', text)
        text = re.sub(
            r'\\emph\{((?:[^{}]|\{[^{}]*\})*)\}',
            r'<em>\1</em>', text)
        text = re.sub(
            r'\\texttt\{((?:[^{}]|\{[^{}]*\})*)\}',
            r'<code>\1</code>', text)
        text = re.sub(
            r'\\textsc\{((?:[^{}]|\{[^{}]*\})*)\}',
            r'\1', text)
        text = re.sub(
            r'\\underline\{((?:[^{}]|\{[^{}]*\})*)\}',
            r'<u>\1</u>', text)

    # \term commands (Vietnamese glossary)
    text = re.sub(
        r'\\termfull\{((?:[^{}]|\{[^{}]*\})*)\}'
        r'\{((?:[^{}]|\{[^{}]*\})*)\}'
        r'\{((?:[^{}]|\{[^{}]*\})*)\}',
        r'<strong>\1</strong> (<em>\2</em>): \3', text)
    text = re.sub(
        r'\\term\{((?:[^{}]|\{[^{}]*\})*)\}'
        r'\{((?:[^{}]|\{[^{}]*\})*)\}',
        r'<strong>\1</strong> (<em>\2</em>)', text)
    text = re.sub(
        r'\\termshort\{((?:[^{}]|\{[^{}]*\})*)\}',
        r'<strong>\1</strong>', text)

    # Citations
    text = re.sub(
        r'\\cite\{([^}]*)\}',
        lambda m: (
            '<span class="cite">['
            + ', '.join(k.strip() for k in m.group(1).split(','))
            + ']</span>'
        ), text)

    # Cross-references
    text = re.sub(r'\\[cC]ref\{[^}]*\}', cross_ref_text, text)
    text = re.sub(r'\\eqref\{[^}]*\}', '(PT)', text)
    text = re.sub(r'\\ref\{[^}]*\}', '(?)', text)

    # Footnotes
    text = re.sub(
        r'\\footnote\{((?:[^{}]|\{[^{}]*\})*)\}',
        r' (\1)', text)

    # URLs
    text = re.sub(
        r'\\url\{([^}]*)\}',
        r'<a href="\1" target="_blank">\1</a>', text)
    text = re.sub(
        r'\\href\{([^}]*)\}\{([^}]*)\}',
        r'<a href="\1" target="_blank">\2</a>', text)

    # Remove invisible/spacing commands
    text = re.sub(r'\\(levelone|leveltwo|levelthree)\b', '', text)
    text = re.sub(
        r'\\(vspace|hspace|bigskip|medskip|smallskip)\*?\{[^}]*\}',
        '', text)
    text = re.sub(
        r'\\(vspace|hspace|bigskip|medskip|smallskip)\b', '', text)
    text = re.sub(r'\\(noindent|indent)\b', '', text)
    text = re.sub(r'\\(phantom|hphantom|vphantom)\{[^}]*\}', '', text)
    text = re.sub(r'\\renewcommand\{[^}]*\}\{[^}]*\}', '', text)
    text = re.sub(r'\\setlength\{[^}]*\}\{[^}]*\}', '', text)

    # Special characters
    text = text.replace('\\&', '&amp;')
    text = text.replace('\\%', '%')
    text = text.replace('\\_', '_')
    text = text.replace('\\#', '#')
    text = text.replace('---', '&mdash;')
    text = text.replace('--', '&ndash;')
    text = re.sub(r"``", '\u201c', text)
    text = re.sub(r"''", '\u201d', text)
    text = text.replace('\\ldots', '\u2026')
    text = text.replace('\\dots', '\u2026')
    text = text.replace('\\colon', ':')
    text = text.replace('\\quad', ' ')
    text = text.replace('\\qquad', '  ')
    text = re.sub(r'\\,', ' ', text)
    text = text.replace('~', '\u00a0')
    text = text.replace('\\checkmark', '\u2713')

    # Paragraphs: split on blank lines, wrap non-block content in <p>
    blocks = re.split(r'\n\s*\n', text)
    result = []
    block_tags = ['<div', '<h4', '<h5', '<h6', '<ul', '<ol', '<table', '<pre', '$$', '<br', '@@CODE_BLOCK_']
    inline_block_tags = ['<div', '<h4', '<h5', '<h6', '<table', '<pre', '@@CODE_BLOCK_']
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        if any(block.startswith(t) for t in block_tags):
            result.append(block)
        elif any(t in block for t in inline_block_tags):
            result.append(block)
        else:
            result.append(f'<p>{block}</p>')
    text = '\n\n'.join(result)

    # Restore math
    text = restore_math(text, math_store)

    # Restore code blocks (after everything else)
    text = restore_code_placeholders(text, code_placeholders)

    # Cleanup multiple blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ============================================================================
# CARD HTML GENERATION
# ============================================================================
def get_diff_color(diff, colors=None):
    """Get the badge color for a difficulty level."""
    if colors is None:
        colors = DEFAULT_DIFF_COLORS
    return colors.get(diff, "#4299e1")


def generate_card_html(stt, ch, vi_title, en_title, diff, body_html,
                       diff_colors=None):
    """Generate a single HTML card div with data attributes.

    Args:
        stt: Sequential number (1-based).
        ch: Chapter number.
        vi_title: Vietnamese (primary language) title.
        en_title: English (secondary language) title.
        diff: Difficulty level (1-10).
        body_html: Converted HTML body content.
        diff_colors: Optional custom difficulty color map.

    Returns:
        HTML string for the card.
    """
    color = get_diff_color(diff, diff_colors)
    vi_safe = vi_title.replace('"', '&quot;')
    en_safe = en_title.replace('"', '&quot;')
    return f'''<div class="concept-card" id="c-{stt}" data-stt="{stt}" data-ch="{ch}"
     data-vi="{vi_safe}" data-en="{en_safe}" data-diff="{diff}">
  <div class="card-header" onclick="toggleCard({stt})">
    <span class="expand-icon" id="ei-{stt}">&#9654;</span>
    <span class="stt-badge">{stt}</span> {vi_title}
    <span class="en-label">({en_title})</span>
    <span class="badges">
      <span class="ch-badge">Ch.{ch}</span>
      <span class="diff-badge" style="background:{color}">{diff}</span>
    </span>
  </div>
  <div class="card-body" id="cb-{stt}">
{body_html}
  </div>
</div>'''


# ============================================================================
# CARD METADATA - AUTO-DETECT AND LOOKUP
# ============================================================================
def build_card_meta_from_config(cards_list):
    """Build a lookup dict from explicit card config.

    Args:
        cards_list: List of dicts with keys: ch, stt, en, diff, vi
                    Optionally section_idx (0-based). If omitted, auto-assigned
                    sequentially within each chapter.

    Returns:
        dict: {(ch, section_idx): {"stt": N, "en": "...", "diff": D, "vi": "..."}}
    """
    meta = {}
    # Sort by stt to ensure correct sequential order
    sorted_cards = sorted(cards_list, key=lambda c: c['stt'])
    # Track per-chapter section index
    ch_counters = {}
    for card in sorted_cards:
        ch = card['ch']
        if 'section_idx' in card:
            idx = card['section_idx']
        else:
            idx = ch_counters.get(ch, 0)
            ch_counters[ch] = idx + 1
        meta[(ch, idx)] = {
            'stt': card['stt'],
            'en': card.get('en', ''),
            'diff': card.get('diff', 5),
            'vi': card.get('vi', ''),
        }
    return meta


def auto_generate_card_meta(chapter_files, config):
    """Auto-generate card metadata by scanning section titles from .tex files.

    Args:
        chapter_files: list of (chapter_num, filepath) tuples
        config: Config object

    Returns:
        list of card dicts: [{"stt": N, "ch": C, "vi": "...", "en": "...", "diff": D}, ...]
    """
    environments = config.resolve_environments()
    cards = []
    stt_counter = 1

    for ch_num, filepath in chapter_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                tex = f.read()
        except (IOError, OSError) as e:
            print(f"  WARNING: Cannot read {filepath}: {e}", file=sys.stderr)
            continue

        tex = strip_comments(tex)
        sections = split_into_sections(
            tex, ch_num, config.exercise_keywords)

        for idx, (title, _content) in enumerate(sections):
            # Clean the title for use as English fallback
            en_title = _clean_title_for_en(title)
            cards.append({
                'stt': stt_counter,
                'ch': ch_num,
                'section_idx': idx,
                'vi': title,
                'en': en_title,
                'diff': config.default_difficulty,
            })
            stt_counter += 1

    return cards


def _clean_title_for_en(title):
    """Clean a LaTeX title string for use as an English-fallback title.

    Strips remaining LaTeX commands, keeps text.
    """
    # Remove \texorpdfstring
    t = re.sub(r'\\texorpdfstring\{([^}]*)\}\{[^}]*\}', r'\1', title)
    # Remove remaining \command{...} -> content
    t = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', t)
    # Remove remaining \command
    t = re.sub(r'\\[a-zA-Z]+', '', t)
    # Clean up
    t = re.sub(r'\s+', ' ', t).strip()
    return t if t else title


# ============================================================================
# CHAPTER PROCESSING
# ============================================================================
def process_chapter(filepath, chapter_num, card_meta, config, environments,
                    stt_fallback_start=900):
    """Process a single chapter .tex file into HTML cards.

    Args:
        filepath: Path to the .tex file.
        chapter_num: The chapter number.
        card_meta: dict {(ch, idx): {"stt", "en", "diff", ...}} or None.
        config: Config object.
        environments: Resolved environment mapping.
        stt_fallback_start: Starting STT for sections without metadata.

    Returns:
        list of (card_html_string, card_info_dict) tuples.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            tex = f.read()
    except (IOError, OSError) as e:
        print(f"  ERROR: Cannot read {filepath}: {e}", file=sys.stderr)
        return []

    tex = strip_comments(tex)
    sections = split_into_sections(
        tex, chapter_num, config.exercise_keywords)

    cards = []
    # Shared counters for figure/table numbering across sections in this chapter
    figure_counter = [0]
    table_counter = [0]

    for idx, (title, content) in enumerate(sections):
        key = (chapter_num, idx)

        if card_meta and key in card_meta:
            meta = card_meta[key]
            stt = meta['stt']
            en = meta.get('en', title)
            diff = meta.get('diff', config.default_difficulty)
        else:
            # Fallback: auto-assign
            stt = stt_fallback_start + idx
            en = _clean_title_for_en(title)
            diff = config.default_difficulty
            if card_meta is not None:
                # Only warn if we had explicit metadata but this section was missing
                print(
                    f"  WARNING: No metadata for ({chapter_num},{idx}): "
                    f"'{title}' -> stt={stt}",
                    file=sys.stderr)

        # Resolve images directories
        images_dirs = []
        if config.book_dir:
            for subdir in ['images', 'figures', 'imgs', 'fig']:
                img_dir = os.path.join(config.book_dir, subdir)
                if os.path.isdir(img_dir):
                    images_dirs.append(img_dir)
        images_dir = images_dirs if images_dirs else None

        html = latex_to_html(
            content,
            environments=environments,
            proof_label=config.proof_label,
            cross_ref_text=config.cross_ref_text,
            images_dir=images_dir,
            chapter_num=chapter_num,
            figure_counter=figure_counter,
            table_counter=table_counter,
            card_stt=stt,
        )
        card_html = generate_card_html(
            stt, chapter_num, title, en, diff, html, config.diff_colors)

        card_info = {
            'stt': stt,
            'ch': chapter_num,
            'vi': title,
            'en': en,
            'diff': diff,
        }
        cards.append((card_html, card_info))
        print(f"  Card {stt:3d}: Ch.{chapter_num} [{diff}] {title}",
              file=sys.stderr)

    return cards


# ============================================================================
# METADATA JSON OUTPUT
# ============================================================================
def generate_metadata_json(all_card_infos, chapter_titles, parts):
    """Generate the metadata JSON structure.

    Args:
        all_card_infos: list of card info dicts.
        chapter_titles: dict {ch_num: "title"}.
        parts: list of part dicts [{"num": "I", "name": "...", "chapters": [1,2,3]}].

    Returns:
        dict suitable for json.dumps().
    """
    return {
        'cards': [
            {
                'stt': ci['stt'],
                'ch': ci['ch'],
                'vi': ci['vi'],
                'en': ci['en'],
                'diff': ci['diff'],
            }
            for ci in all_card_infos
        ],
        'chapters': {
            str(ch): title for ch, title in sorted(chapter_titles.items())
        },
        'parts': parts,
    }


# ============================================================================
# CLI + MAIN
# ============================================================================
def parse_args():
    parser = argparse.ArgumentParser(
        description='Generalized LaTeX-to-HTML Card Converter',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-detect mode: scan book directory
  %(prog)s --book-dir ./book --output /tmp/cards.html

  # Config-driven mode
  %(prog)s --config book_config.json --output /tmp/cards.html

  # Single chapter
  %(prog)s --book-dir ./book --chapter 4 --output /tmp/ch04.html

  # With metadata JSON output
  %(prog)s --book-dir ./book --output /tmp/cards.html --meta /tmp/cards_meta.json

  # Dry run: show detected sections without converting
  %(prog)s --book-dir ./book --dry-run
""")

    source_group = parser.add_argument_group('Source (choose one)')
    source_group.add_argument(
        '--config', '-f',
        help='JSON config file path')
    source_group.add_argument(
        '--book-dir', '-d',
        help='Book root directory (auto-detect mode)')

    parser.add_argument(
        '--chapter', '-c', type=int,
        help='Process only this chapter number')
    parser.add_argument(
        '--output', '-o',
        help='Output HTML file path (default: stdout)')
    parser.add_argument(
        '--meta', '-m',
        help='Output metadata JSON file path')
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Show detected sections without generating HTML')
    parser.add_argument(
        '--lang',
        help='Override language (vi, en)')
    parser.add_argument(
        '--title',
        help='Override book title')
    parser.add_argument(
        '--chapters-dir',
        help='Override chapters subdirectory name')
    parser.add_argument(
        '--chapter-pattern',
        help='Override chapter filename pattern (e.g. "chapter_{}.tex")')
    parser.add_argument(
        '--num-chapters', type=int,
        help='Override number of chapters')
    parser.add_argument(
        '--default-diff', type=int, default=None,
        help='Default difficulty level for auto-detected sections (1-10)')
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='Verbose output')

    return parser.parse_args()


def main():
    args = parse_args()

    # ---- Build configuration ----
    if args.config:
        if not os.path.isfile(args.config):
            print(f"ERROR: Config file not found: {args.config}",
                  file=sys.stderr)
            sys.exit(1)
        config = Config.from_json(args.config)
        print(f"Loaded config from: {args.config}", file=sys.stderr)
    elif args.book_dir:
        config = Config.from_book_dir(args.book_dir)
        print(f"Auto-detect mode from: {args.book_dir}", file=sys.stderr)
    else:
        print("ERROR: Either --config or --book-dir is required.",
              file=sys.stderr)
        sys.exit(1)

    # CLI overrides
    if args.book_dir and config.book_dir is None:
        config.book_dir = args.book_dir
    if args.lang:
        config.language = args.lang
    if args.title:
        config.title = args.title
    if args.chapters_dir:
        config.chapters_dir = args.chapters_dir
    if args.chapter_pattern:
        config.chapter_pattern = args.chapter_pattern
    if args.num_chapters is not None:
        config.num_chapters = args.num_chapters
    if args.default_diff is not None:
        config.default_difficulty = args.default_diff

    # Validate book_dir
    if config.book_dir is None:
        print("ERROR: book_dir not set. Use --book-dir or set in config JSON.",
              file=sys.stderr)
        sys.exit(1)

    if not os.path.isdir(config.book_dir):
        print(f"ERROR: Book directory not found: {config.book_dir}",
              file=sys.stderr)
        sys.exit(1)

    # ---- Detect chapters ----
    try:
        chapter_files = config.detect_chapters()
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if not chapter_files:
        print("ERROR: No chapter files found.", file=sys.stderr)
        sys.exit(1)

    # Filter to single chapter if requested
    if args.chapter:
        chapter_files = [(ch, fp) for ch, fp in chapter_files
                         if ch == args.chapter]
        if not chapter_files:
            print(f"ERROR: Chapter {args.chapter} not found.",
                  file=sys.stderr)
            sys.exit(1)

    print(f"Found {len(chapter_files)} chapter(s): "
          f"{[ch for ch, _ in chapter_files]}", file=sys.stderr)

    # ---- Detect parts and chapter titles ----
    parts = config.detect_parts()
    chapter_titles = config.detect_chapter_titles(chapter_files)

    if parts:
        print(f"Detected {len(parts)} part(s):", file=sys.stderr)
        for p in parts:
            print(f"  Part {p['num']}: {p['name']} "
                  f"(chapters {p['chapters']})", file=sys.stderr)

    # ---- Build card metadata ----
    card_meta = None  # None means "auto-assign STTs sequentially"

    if config.cards:
        # Explicit card metadata from config
        card_meta = build_card_meta_from_config(config.cards)
        print(f"Using {len(card_meta)} explicit card metadata entries.",
              file=sys.stderr)
    else:
        # Auto-detect mode: pre-scan all chapters to assign sequential STTs
        print("Auto-detecting sections for card metadata...", file=sys.stderr)
        auto_cards = auto_generate_card_meta(chapter_files, config)
        card_meta = {}
        for card in auto_cards:
            key = (card['ch'], card['section_idx'])
            card_meta[key] = card
        print(f"Auto-detected {len(card_meta)} sections.", file=sys.stderr)

    # ---- Resolve environments ----
    environments = config.resolve_environments()

    # ---- Dry run mode ----
    if args.dry_run:
        print("\n--- DRY RUN: Detected Sections ---", file=sys.stderr)
        for ch_num, filepath in chapter_files:
            ch_title = chapter_titles.get(ch_num, '???')
            print(f"\nChapter {ch_num}: {ch_title}", file=sys.stderr)
            print(f"  File: {filepath}", file=sys.stderr)

            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    tex = f.read()
                tex = strip_comments(tex)
                sections = split_into_sections(
                    tex, ch_num, config.exercise_keywords)
                for idx, (title, content) in enumerate(sections):
                    key = (ch_num, idx)
                    meta = card_meta.get(key, {})
                    stt = meta.get('stt', '?')
                    diff = meta.get('diff', config.default_difficulty)
                    en = meta.get('en', _clean_title_for_en(title))
                    content_len = len(content)
                    print(f"  [{stt:>3}] (diff={diff}) {title}  "
                          f"[en: {en}]  ({content_len} chars)",
                          file=sys.stderr)
            except (IOError, OSError) as e:
                print(f"  ERROR reading file: {e}", file=sys.stderr)

        total = sum(
            1 for key in card_meta
            if args.chapter is None or key[0] == args.chapter
        )
        print(f"\nTotal: {total} sections", file=sys.stderr)
        return

    # ---- Process chapters ----
    print("\nConverting LaTeX to HTML cards...", file=sys.stderr)
    all_card_htmls = []
    all_card_infos = []

    for ch_num, filepath in chapter_files:
        ch_title = chapter_titles.get(ch_num, f'Chapter {ch_num}')
        print(f"\nChapter {ch_num}: {ch_title}", file=sys.stderr)
        print(f"  File: {filepath}", file=sys.stderr)

        results = process_chapter(
            filepath, ch_num, card_meta, config, environments)

        for card_html, card_info in results:
            all_card_htmls.append(card_html)
            all_card_infos.append(card_info)

    if not all_card_htmls:
        print("\nWARNING: No cards generated.", file=sys.stderr)
        sys.exit(0)

    # ---- Write HTML output ----
    output_html = '\n\n'.join(all_card_htmls)

    if args.output:
        # Ensure parent directory exists
        out_dir = os.path.dirname(args.output)
        if out_dir and not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_html)
        print(f"\nWritten {len(all_card_htmls)} cards to: {args.output}",
              file=sys.stderr)
    else:
        # Write to stdout
        print(output_html)

    # ---- Write metadata JSON ----
    if args.meta:
        meta_dir = os.path.dirname(args.meta)
        if meta_dir and not os.path.isdir(meta_dir):
            os.makedirs(meta_dir, exist_ok=True)

        meta_data = generate_metadata_json(
            all_card_infos, chapter_titles, parts)
        with open(args.meta, 'w', encoding='utf-8') as f:
            json.dump(meta_data, f, ensure_ascii=False, indent=2)
        print(f"Written metadata to: {args.meta}", file=sys.stderr)

    # ---- Also write metadata alongside HTML if --output was given ----
    if args.output and not args.meta:
        auto_meta_path = os.path.splitext(args.output)[0] + '_meta.json'
        meta_data = generate_metadata_json(
            all_card_infos, chapter_titles, parts)
        with open(auto_meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta_data, f, ensure_ascii=False, indent=2)
        print(f"Written metadata to: {auto_meta_path}", file=sys.stderr)

    # ---- Summary ----
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Summary:", file=sys.stderr)
    print(f"  Chapters processed: {len(chapter_files)}", file=sys.stderr)
    print(f"  Cards generated:    {len(all_card_htmls)}", file=sys.stderr)

    # Per-chapter breakdown
    ch_counts = {}
    for ci in all_card_infos:
        ch_counts[ci['ch']] = ch_counts.get(ci['ch'], 0) + 1
    for ch in sorted(ch_counts):
        ch_title = chapter_titles.get(ch, '')
        print(f"    Ch.{ch}: {ch_counts[ch]} cards  ({ch_title})",
              file=sys.stderr)

    # Difficulty distribution
    diff_counts = {}
    for ci in all_card_infos:
        d = ci['diff']
        diff_counts[d] = diff_counts.get(d, 0) + 1
    if len(diff_counts) > 1:
        print(f"  Difficulty distribution:", file=sys.stderr)
        for d in sorted(diff_counts):
            print(f"    Level {d}: {diff_counts[d]} cards", file=sys.stderr)

    print(f"{'='*60}", file=sys.stderr)


if __name__ == '__main__':
    main()
