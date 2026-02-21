#!/usr/bin/env python3
"""
resolve_tex.py - LaTeX Project Resolver

Analyzes a LaTeX project starting from main.tex, recursively resolves all
\\input/\\include/\\subimport commands, detects document structure (parts,
chapters, sections), and produces a normalized representation that
tex2html.py can process.

Supports:
  - Single-file books (everything in main.tex)
  - Chapters as separate files (\\input{chapters/ch01})
  - Chapters with sub-files (\\input{ch01/sec01})
  - Nested includes (recursive resolution)
  - \\subimport{dir}{file} (from import package)
  - Article-class documents (sections as top-level)

Usage:
  # Analyze and print structure
  python3 resolve_tex.py main.tex

  # Generate config JSON
  python3 resolve_tex.py main.tex --gen-config -o book_config.json

  # Flatten chapters to temp dir
  python3 resolve_tex.py main.tex --flatten -o /tmp/resolved/

Author: Dang Minh Tuan
Email:  tuanvietkey@gmail.com
"""

__author__ = "Dang Minh Tuan"
__email__ = "tuanvietkey@gmail.com"
__version__ = "1.0"
__date__ = "20-2-2026"

import re
import os
import sys
import json
import argparse
from pathlib import Path


# ============================================================================
# RESOLVED PROJECT DATA
# ============================================================================
class ResolvedProject:
    """Holds the fully resolved structure of a LaTeX project."""

    def __init__(self):
        self.root_dir = ''          # directory containing main.tex
        self.main_tex = ''          # path to main.tex
        self.docclass = 'book'      # book, article, report, memoir, etc.
        self.title = ''
        self.subtitle = ''
        self.author = ''
        self.date = ''
        self.preamble = ''          # everything before \\begin{document}
        self.body = ''              # everything inside \\begin{document}..\\end{document}

        self.parts = []             # [{"num": "I", "name": "...", "chapters": [1,2,3]}]
        self.chapters = []          # [{"num": 1, "title": "...", "content": "...", "source": "..."}]

        self.bib_file = ''          # path to .bib
        self.images_dirs = []       # paths from \\graphicspath
        self.custom_envs = {}       # {env_name: {"label": "...", "type": "theorem|box"}}
        self.katex_macros = {}      # {macro: definition}
        self.tikz_preamble = ''     # Extra preamble lines for TikZ compilation

    def summary(self):
        """Return a human-readable summary string."""
        lines = [
            f"LaTeX Project: {self.main_tex}",
            f"  Document class: {self.docclass}",
            f"  Title: {self.title or '(not found)'}",
            f"  Author: {self.author or '(not found)'}",
            f"  Parts: {len(self.parts)}",
            f"  Chapters: {len(self.chapters)}",
        ]
        if self.bib_file:
            lines.append(f"  Bibliography: {self.bib_file}")
        if self.images_dirs:
            lines.append(f"  Image dirs: {self.images_dirs}")
        if self.custom_envs:
            lines.append(f"  Custom environments: {len(self.custom_envs)}")
        if self.katex_macros:
            lines.append(f"  Math macros: {len(self.katex_macros)}")

        if self.parts:
            lines.append("\n  Structure:")
            for part in self.parts:
                lines.append(f"    Part {part['num']}: {part['name']}")
                for ch_num in part['chapters']:
                    ch = next((c for c in self.chapters if c['num'] == ch_num), None)
                    if ch:
                        src = os.path.basename(ch.get('source', ''))
                        lines.append(
                            f"      Ch.{ch_num}: {ch['title']}  "
                            f"({len(ch['content'])} chars) [{src}]")
        elif self.chapters:
            lines.append("\n  Chapters:")
            for ch in self.chapters:
                src = os.path.basename(ch.get('source', ''))
                lines.append(
                    f"    Ch.{ch['num']}: {ch['title']}  "
                    f"({len(ch['content'])} chars) [{src}]")

        return '\n'.join(lines)


# ============================================================================
# INCLUDE RESOLUTION
# ============================================================================
def _strip_tex_comments(text):
    """Remove LaTeX comments (% to end-of-line) but keep escaped \\%."""
    lines = text.split('\n')
    result = []
    for line in lines:
        cleaned = re.sub(r'(?<!\\)%.*$', '', line)
        result.append(cleaned)
    return '\n'.join(result)


def _resolve_file_path(filename, current_dir, root_dir):
    """Try to find a .tex file given a filename reference.

    Searches in order:
      1. Relative to current file's directory
      2. Relative to project root
      3. With .tex extension appended

    Returns the resolved absolute path or None.
    """
    candidates = []

    # Try as-is and with .tex extension, relative to current_dir
    candidates.append(os.path.join(current_dir, filename))
    if not filename.endswith('.tex'):
        candidates.append(os.path.join(current_dir, filename + '.tex'))

    # Try relative to root
    if current_dir != root_dir:
        candidates.append(os.path.join(root_dir, filename))
        if not filename.endswith('.tex'):
            candidates.append(os.path.join(root_dir, filename + '.tex'))

    for c in candidates:
        if os.path.isfile(c):
            return os.path.abspath(c)

    return None


def resolve_includes(filepath, root_dir, visited=None, depth=0):
    """Recursively read a .tex file and inline all \\input/\\include/\\subimport.

    Args:
        filepath: Path to the .tex file to read.
        root_dir: Project root directory.
        visited: Set of already-visited absolute paths (circular include guard).
        depth: Current recursion depth (safety limit).

    Returns:
        The fully resolved text content.
    """
    MAX_DEPTH = 20
    if depth > MAX_DEPTH:
        print(f"  WARNING: Max include depth ({MAX_DEPTH}) reached at {filepath}",
              file=sys.stderr)
        return ''

    if visited is None:
        visited = set()

    abs_path = os.path.abspath(filepath)
    if abs_path in visited:
        print(f"  WARNING: Circular include detected: {filepath}", file=sys.stderr)
        return ''
    visited.add(abs_path)

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
    except (IOError, OSError) as e:
        print(f"  WARNING: Cannot read {filepath}: {e}", file=sys.stderr)
        return ''

    current_dir = os.path.dirname(abs_path)

    # Pattern for \input{...} and \include{...}
    # Negative lookbehind: not preceded by % on the same line
    def _replace_input(m):
        full_match = m.group(0)
        # Check if this match is inside a comment
        line_start = text.rfind('\n', 0, m.start()) + 1
        line_before = text[line_start:m.start()]
        if '%' in line_before and not line_before.rstrip().endswith('\\'):
            return full_match  # inside comment, don't resolve

        cmd = m.group(1)  # 'input' or 'include'
        filename = m.group(2).strip()

        resolved = _resolve_file_path(filename, current_dir, root_dir)
        if resolved is None:
            print(f"  WARNING: Include not found: \\{cmd}{{{filename}}} "
                  f"(from {filepath})", file=sys.stderr)
            return full_match

        content = resolve_includes(resolved, root_dir, visited, depth + 1)

        if cmd == 'include':
            content = '\n\\clearpage\n' + content + '\n\\clearpage\n'

        return content

    text = re.sub(
        r'\\(input|include)\{([^}]*)\}',
        _replace_input, text)

    # Handle \subimport{dir}{file} and \import{dir}{file}
    def _replace_subimport(m):
        full_match = m.group(0)
        line_start = text.rfind('\n', 0, m.start()) + 1
        line_before = text[line_start:m.start()]
        if '%' in line_before:
            return full_match

        subdir = m.group(1).strip()
        filename = m.group(2).strip()
        search_dir = os.path.join(current_dir, subdir) if subdir else current_dir
        resolved = _resolve_file_path(filename, search_dir, root_dir)
        if resolved is None:
            print(f"  WARNING: Subimport not found: {subdir}{filename} "
                  f"(from {filepath})", file=sys.stderr)
            return full_match
        return resolve_includes(resolved, root_dir, visited, depth + 1)

    text = re.sub(
        r'\\(?:sub)?import\{([^}]*)\}\{([^}]*)\}',
        _replace_subimport, text)

    return text


# ============================================================================
# PREAMBLE PARSING
# ============================================================================
def _parse_preamble(preamble):
    """Extract useful information from the LaTeX preamble.

    Returns dict with: docclass, title, author, date, bib, images_dirs,
    custom_envs, katex_macros.
    """
    info = {
        'docclass': 'book',
        'title': '',
        'subtitle': '',
        'author': '',
        'date': '',
        'bib': '',
        'images_dirs': [],
        'custom_envs': {},
        'katex_macros': {},
    }

    # Document class
    m = re.search(r'\\documentclass(?:\[[^\]]*\])?\{(\w+)\}', preamble)
    if m:
        info['docclass'] = m.group(1)

    # Title, author, date
    m = re.search(r'\\title\{((?:[^{}]|\{[^{}]*\})*)\}', preamble)
    if m:
        info['title'] = _clean_latex(m.group(1))

    m = re.search(r'\\subtitle\{((?:[^{}]|\{[^{}]*\})*)\}', preamble)
    if m:
        info['subtitle'] = _clean_latex(m.group(1))

    m = re.search(r'\\author\{((?:[^{}]|\{[^{}]*\})*)\}', preamble)
    if m:
        info['author'] = _clean_latex(m.group(1))

    m = re.search(r'\\date\{((?:[^{}]|\{[^{}]*\})*)\}', preamble)
    if m:
        info['date'] = _clean_latex(m.group(1))

    # Bibliography file
    m = re.search(r'\\addbibresource\{([^}]*)\}', preamble)
    if m:
        info['bib'] = m.group(1)
    else:
        m = re.search(r'\\bibliography\{([^}]*)\}', preamble)
        if m:
            bib = m.group(1).strip()
            if not bib.endswith('.bib'):
                bib += '.bib'
            info['bib'] = bib

    # graphicspath
    m = re.search(r'\\graphicspath\{((?:\{[^}]*\})+)\}', preamble)
    if m:
        info['images_dirs'] = re.findall(r'\{([^}]*)\}', m.group(1))

    # Custom theorem environments: \newtheorem{name}{Label}
    for m in re.finditer(
            r'\\newtheorem\{(\w+)\}(?:\[(\w+)\])?\{([^}]*)\}', preamble):
        env_name = m.group(1)
        label = m.group(3).strip()
        info['custom_envs'][env_name] = {'label': label, 'type': 'theorem'}

    # tcolorbox environments: \newtcolorbox{name} or \NewTColorBox{name}
    for m in re.finditer(
            r'\\(?:newtcolorbox|NewTColorBox|DeclareTColorBox)\{(\w+)\}', preamble):
        env_name = m.group(1)
        if env_name not in info['custom_envs']:
            info['custom_envs'][env_name] = {
                'label': env_name.capitalize(), 'type': 'box'}

    # tcolorbox with title: look for title= in newtcolorbox definition
    for m in re.finditer(
            r'\\newtcolorbox\{(\w+)\}[^{]*title\s*=\s*\{?([^},]+)', preamble):
        env_name = m.group(1)
        label = m.group(2).strip().rstrip('}')
        info['custom_envs'][env_name] = {'label': label, 'type': 'box'}

    # Math operators: \DeclareMathOperator{\cmd}{text}
    for m in re.finditer(
            r'\\DeclareMathOperator\{\\(\w+)\}\{([^}]*)\}', preamble):
        cmd = m.group(1)
        defn = m.group(2)
        info['katex_macros'][f'\\{cmd}'] = f'\\mathrm{{{defn}}}'

    # Simple newcommand for math: \newcommand{\Q}{\mathbb{Q}}
    # Also handles \newcommand{\Qp}{\mathbb{Q}_p} and similar
    for m in re.finditer(
            r'\\(?:new|renew)command\{\\(\w+)\}\{(\\math\w+\{[^}]*\}[^}]*)\}',
            preamble):
        cmd = m.group(1)
        defn = m.group(2)
        info['katex_macros'][f'\\{cmd}'] = defn

    # \newcommand for \mathrm wrappers: \newcommand{\GL}{\mathrm{GL}}
    for m in re.finditer(
            r'\\(?:new|renew)command\{\\(\w+)\}\{(\\mathrm\{[^}]*\})\}',
            preamble):
        cmd = m.group(1)
        defn = m.group(2)
        if f'\\{cmd}' not in info['katex_macros']:
            info['katex_macros'][f'\\{cmd}'] = defn

    # \newcommand for \mathcal wrappers: \newcommand{\Mhit}{\mathcal{M}_{\mathrm{Hit}}}
    for m in re.finditer(
            r'\\(?:new|renew)command\{\\(\w+)\}\{(\\mathcal'
            r'\{[^}]*\}(?:[_^]\{[^}]*(?:\{[^}]*\}[^}]*)?\})*)\}',
            preamble):
        cmd = m.group(1)
        defn = m.group(2)
        if f'\\{cmd}' not in info['katex_macros']:
            info['katex_macros'][f'\\{cmd}'] = defn

    # \def\Q{\mathbb{Q}}
    for m in re.finditer(
            r'\\def\\(\w+)\{(\\math\w+\{[^}]*\}[^}]*)\}', preamble):
        cmd = m.group(1)
        defn = m.group(2)
        if f'\\{cmd}' not in info['katex_macros']:
            info['katex_macros'][f'\\{cmd}'] = defn

    # Macros with arguments: \newcommand{\SOI}[2]{SO_{#1}\!\left(#2\right)}
    # Body may contain one level of nested braces
    for m in re.finditer(
            r'\\(?:new|renew)command\{\\(\w+)\}\[\d+\]'
            r'\{((?:[^{}]|\{[^{}]*\})*)\}',
            preamble):
        cmd = m.group(1)
        defn = m.group(2).strip()
        if f'\\{cmd}' not in info['katex_macros'] and '#' in defn:
            info['katex_macros'][f'\\{cmd}'] = defn

    # TikZ preamble: collect \usetikzlibrary and tikz-related \usepackage
    tikz_lines = []
    for m in re.finditer(r'\\usetikzlibrary\{[^}]*\}', preamble):
        tikz_lines.append(m.group(0))
    for m in re.finditer(r'\\usepackage(?:\[[^\]]*\])?\{(tikz[^}]*)\}', preamble):
        tikz_lines.append(m.group(0))
    for m in re.finditer(r'\\usepackage(?:\[[^\]]*\])?\{(pgfplots[^}]*)\}', preamble):
        tikz_lines.append(m.group(0))
    for m in re.finditer(r'\\pgfplotsset\{[^}]*\}', preamble):
        tikz_lines.append(m.group(0))
    info['tikz_preamble'] = '\n'.join(tikz_lines)

    return info


def _clean_latex(text):
    """Remove common LaTeX formatting from a metadata string."""
    text = re.sub(r'\\texorpdfstring\{([^}]*)\}\{[^}]*\}', r'\1', text)
    text = re.sub(r'\\textbf\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\textit\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\emph\{([^}]*)\}', r'\1', text)
    # Remove line breaks with optional spacing: \\[6pt], \\[4pt], \\
    text = re.sub(r'\\\\(?:\[\d+\w*\])?', ' ', text)
    text = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\[a-zA-Z]+', '', text)
    text = re.sub(r'[{}]', '', text)
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# ============================================================================
# STRUCTURE DETECTION
# ============================================================================
ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X',
         'XI', 'XII', 'XIII', 'XIV', 'XV']


def _detect_structure(body, docclass):
    """Detect parts and chapters/sections from the resolved document body.

    For book/report: splits by \\chapter
    For article: splits by \\section (treated as "chapters" for the pipeline)

    Returns (parts, chapters) where:
      parts = [{"num": "I", "name": "...", "chapters": [1,2,3]}]
      chapters = [{"num": 1, "title": "...", "content": "...", "source": "inline"}]
    """
    # Choose the top-level sectioning command
    if docclass in ('article', 'scrartcl'):
        top_cmd = 'section'
        has_parts = False
    else:
        top_cmd = 'chapter'
        # Check if \chapter actually appears; fall back to \section
        if not re.search(r'\\chapter\*?\{', body):
            top_cmd = 'section'
        has_parts = bool(re.search(r'\\part\*?\{', body))

    # Split body into tokens: part markers, chapter markers, and content
    parts = []
    chapters = []

    # Combined pattern to find parts and chapters in order
    token_pat = re.compile(
        r'\\(part|' + re.escape(top_cmd)
        + r')\*?\{((?:[^{}]|\{[^{}]*\})*)\}',
        re.DOTALL
    )

    matches = list(token_pat.finditer(body))

    if not matches:
        # No structure found — treat entire body as one chapter
        return [], [{'num': 1, 'title': '(Content)', 'content': body.strip(),
                     'source': 'inline'}]

    current_part = None
    part_idx = 0
    ch_num = 0

    for i, m in enumerate(matches):
        cmd = m.group(1)
        title_raw = m.group(2).strip()
        title = re.sub(r'\\texorpdfstring\{([^}]*)\}\{[^}]*\}', r'\1', title_raw)
        title = re.sub(r'\\label\{[^}]*\}', '', title).strip()

        # Content: from end of this match to start of next match
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        content = body[start:end].strip()

        if cmd == 'part':
            if current_part is not None:
                parts.append(current_part)
            numeral = ROMAN[part_idx] if part_idx < len(ROMAN) else str(part_idx + 1)
            current_part = {'num': numeral, 'name': title, 'chapters': []}
            part_idx += 1
        else:
            # It's a chapter/section
            ch_num += 1
            chapters.append({
                'num': ch_num,
                'title': title,
                'content': content,
                'source': 'inline',
            })
            if current_part is not None:
                current_part['chapters'].append(ch_num)

    if current_part is not None:
        parts.append(current_part)

    return parts, chapters


def _detect_chapter_sources(body, root_dir):
    """Try to detect which source file each chapter came from.

    Looks for patterns like:
      \\input{chapters/ch01}
      \\chapter{Title}
    in the original (pre-resolved) main.tex.

    Returns dict: {chapter_title_cleaned: source_filepath}
    """
    # This is a best-effort heuristic
    sources = {}
    input_pat = re.compile(r'\\input\{([^}]*)\}')
    ch_pat = re.compile(r'\\chapter\*?\{((?:[^{}]|\{[^{}]*\})*)\}')

    # Read original main.tex (not resolved) to find input->chapter mapping
    # Not always possible, so this is optional
    return sources


# ============================================================================
# MAIN RESOLVER
# ============================================================================
def resolve_project(main_tex_path):
    """Resolve a LaTeX project from its main.tex file.

    Args:
        main_tex_path: Path to the main .tex file.

    Returns:
        ResolvedProject instance with all structure detected.
    """
    main_tex_path = os.path.abspath(main_tex_path)
    if not os.path.isfile(main_tex_path):
        raise FileNotFoundError(f"Main TeX file not found: {main_tex_path}")

    root_dir = os.path.dirname(main_tex_path)
    project = ResolvedProject()
    project.root_dir = root_dir
    project.main_tex = main_tex_path

    print(f"Resolving: {main_tex_path}", file=sys.stderr)
    print(f"Root dir:  {root_dir}", file=sys.stderr)

    # Step 1: Resolve all includes
    full_text = resolve_includes(main_tex_path, root_dir)
    print(f"Resolved text: {len(full_text)} chars", file=sys.stderr)

    # Step 2: Split into preamble and body
    doc_begin = re.search(r'\\begin\{document\}', full_text)
    doc_end = re.search(r'\\end\{document\}', full_text)

    if doc_begin:
        project.preamble = full_text[:doc_begin.start()]
        body_end = doc_end.start() if doc_end else len(full_text)
        project.body = full_text[doc_begin.end():body_end]
    else:
        # No \begin{document} found — treat everything as body
        project.preamble = ''
        project.body = full_text

    # Step 2b: Inline local .sty files referenced by \usepackage
    def _inline_local_sty(preamble_text, root):
        """Append contents of local .sty files to preamble for macro detection."""
        extra = ''
        for m in re.finditer(
                r'\\usepackage(?:\[[^\]]*\])?\{([^}]+)\}', preamble_text):
            pkg = m.group(1)
            # Try to find as local file
            for candidate in [
                os.path.join(root, pkg + '.sty'),
                os.path.join(root, pkg),
            ]:
                if os.path.isfile(candidate):
                    try:
                        with open(candidate, 'r', encoding='utf-8',
                                  errors='replace') as f:
                            extra += '\n' + f.read()
                    except Exception:
                        pass
                    break
        return preamble_text + extra

    project.preamble = _inline_local_sty(project.preamble, root_dir)

    # Step 3: Parse preamble
    preamble_info = _parse_preamble(project.preamble)
    project.docclass = preamble_info['docclass']
    project.title = preamble_info['title']
    project.subtitle = preamble_info['subtitle']
    project.author = preamble_info['author']
    project.date = preamble_info['date']
    project.custom_envs = preamble_info['custom_envs']
    project.katex_macros = preamble_info['katex_macros']
    project.tikz_preamble = preamble_info.get('tikz_preamble', '')

    # Resolve bib file path
    if preamble_info['bib']:
        bib_path = _resolve_file_path(
            preamble_info['bib'], root_dir, root_dir)
        if bib_path:
            project.bib_file = bib_path
        else:
            # Try common locations
            for candidate in [
                os.path.join(root_dir, preamble_info['bib']),
                os.path.join(root_dir, 'references.bib'),
                os.path.join(root_dir, 'bibliography.bib'),
                os.path.join(root_dir, 'refs.bib'),
            ]:
                if os.path.isfile(candidate):
                    project.bib_file = candidate
                    break

    # Resolve image directories
    for img_dir in preamble_info['images_dirs']:
        abs_img = os.path.join(root_dir, img_dir)
        if os.path.isdir(abs_img):
            project.images_dirs.append(abs_img)
    # Also check common image directory names
    for common_name in ['images', 'figures', 'imgs', 'fig']:
        d = os.path.join(root_dir, common_name)
        if os.path.isdir(d) and d not in project.images_dirs:
            project.images_dirs.append(d)

    # Step 4: Detect document structure
    body_clean = _strip_tex_comments(project.body)
    parts, chapters = _detect_structure(body_clean, project.docclass)
    project.parts = parts
    project.chapters = chapters

    # Step 5: Try to detect source files for each chapter
    # Read original main.tex to map \input → \chapter
    _enrich_chapter_sources(project)

    print(f"Detected: {len(parts)} parts, {len(chapters)} chapters",
          file=sys.stderr)

    return project


def _enrich_chapter_sources(project):
    """Try to figure out which source file each chapter content came from.

    Reads the original (non-resolved) main.tex to find \\input commands
    and tries to match them to detected chapters.
    """
    try:
        with open(project.main_tex, 'r', encoding='utf-8') as f:
            original = f.read()
    except (IOError, OSError):
        return

    # Find all \input{...} lines (non-commented)
    input_files = []
    for line in original.split('\n'):
        line_stripped = line.strip()
        if line_stripped.startswith('%'):
            continue
        m = re.search(r'\\input\{([^}]*)\}', line_stripped)
        if m:
            filename = m.group(1)
            resolved = _resolve_file_path(
                filename, project.root_dir, project.root_dir)
            if resolved:
                input_files.append(resolved)

    # For each chapter, try to find its source by checking which input file
    # contains the \chapter command with matching title
    for ch in project.chapters:
        title_words = ch['title'][:30]  # first 30 chars for matching
        for inp_file in input_files:
            try:
                with open(inp_file, 'r', encoding='utf-8') as f:
                    head = f.read(3000)  # read beginning
                if title_words in head:
                    ch['source'] = inp_file
                    break
            except (IOError, OSError):
                continue


# ============================================================================
# CONFIG GENERATION
# ============================================================================
def generate_config(project, output_path=None):
    """Generate a book_config.json-compatible dict from a ResolvedProject.

    Args:
        project: ResolvedProject instance.
        output_path: Optional output HTML path for the config.

    Returns:
        dict suitable for json.dumps() and compatible with tex2html.py Config.
    """
    config = {
        'title': project.title or 'LaTeX Book',
        'subtitle': project.subtitle,
        'author': project.author or 'Author',
        'version': '1.0',
        'date': project.date or '',
        'copyright_year': project.date[-4:] if project.date and len(project.date) >= 4 else '2025',
        'language': 'vi',

        'book_dir': project.root_dir,
        'chapters_dir': 'chapters',
        'num_chapters': len(project.chapters),
        'bib': project.bib_file or '',

        'skeleton': os.path.join(os.path.dirname(__file__), 'skeleton.html'),
        'output': output_path or 'output.html',

        'tabs': ['ch', 'vi', 'en', 'diff', 'ref', 'about'],
        'tab_labels': {
            'ch': 'Mục lục',
            'vi': 'Tiếng Việt',
            'en': 'English',
            'diff': 'Độ khó',
            'ref': 'Tài liệu TK',
            'about': '\u2139 Giới thiệu',
        },

        'about_html': (
            f'<p><strong>{project.title}</strong></p>'
            f'<p>{project.author}</p>'
        ),

        'parts': project.parts,

        'katex_macros': project.katex_macros,

        'cards': '_auto_',
    }

    # Add detected environments
    if project.custom_envs:
        envs = {}
        for env_name, env_info in project.custom_envs.items():
            if env_info['type'] == 'theorem':
                css = 'env-theorem'
            elif env_info['type'] == 'box':
                css = 'box-green'
            else:
                css = 'env-theorem'
            envs[env_name] = {'css': css, 'label': env_info['label']}
        config['environments'] = envs

    return config


def generate_config_json(project, output_path=None, indent=2):
    """Generate config JSON string."""
    config = generate_config(project, output_path)
    return json.dumps(config, ensure_ascii=False, indent=indent)


# ============================================================================
# FLATTEN: Write each chapter as a separate .tex file
# ============================================================================
def flatten_chapters(project, output_dir):
    """Write each chapter's resolved content to a separate .tex file.

    Creates: output_dir/ch01.tex, output_dir/ch02.tex, ...

    Args:
        project: ResolvedProject instance.
        output_dir: Directory to write flattened chapter files.

    Returns:
        List of (chapter_num, filepath) tuples.
    """
    os.makedirs(output_dir, exist_ok=True)
    result = []

    for ch in project.chapters:
        filename = f"ch{ch['num']:02d}.tex"
        filepath = os.path.join(output_dir, filename)
        # Wrap content with chapter command so tex2html can parse it
        content = f"\\chapter{{{ch['title']}}}\n\n{ch['content']}"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        result.append((ch['num'], filepath))
        print(f"  Wrote: {filepath} ({len(content)} chars)", file=sys.stderr)

    return result


# ============================================================================
# CLI
# ============================================================================
def main():
    parser = argparse.ArgumentParser(
        description='LaTeX Project Resolver - Analyze and normalize LaTeX projects',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show detected structure
  %(prog)s book/main.tex

  # Generate config JSON
  %(prog)s book/main.tex --gen-config -o book_config_auto.json

  # Flatten chapters to temp directory
  %(prog)s book/main.tex --flatten -o /tmp/resolved/

  # Full JSON output (for piping to other tools)
  %(prog)s book/main.tex --json
""")

    parser.add_argument(
        'main_tex',
        help='Path to main .tex file')
    parser.add_argument(
        '--gen-config', action='store_true',
        help='Generate book_config.json')
    parser.add_argument(
        '--flatten', action='store_true',
        help='Flatten chapters to separate .tex files')
    parser.add_argument(
        '--json', action='store_true',
        help='Output full project info as JSON')
    parser.add_argument(
        '-o', '--output',
        help='Output path (config JSON, flatten dir, or JSON output)')

    args = parser.parse_args()

    if not os.path.isfile(args.main_tex):
        print(f"ERROR: File not found: {args.main_tex}", file=sys.stderr)
        sys.exit(1)

    project = resolve_project(args.main_tex)

    if args.gen_config:
        config_json = generate_config_json(project, output_path=args.output)
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(config_json)
            print(f"\nConfig written to: {args.output}", file=sys.stderr)
        else:
            print(config_json)

    elif args.flatten:
        out_dir = args.output or '/tmp/resolved_tex'
        files = flatten_chapters(project, out_dir)
        print(f"\nFlattened {len(files)} chapters to: {out_dir}", file=sys.stderr)

    elif args.json:
        info = {
            'root_dir': project.root_dir,
            'main_tex': project.main_tex,
            'docclass': project.docclass,
            'title': project.title,
            'author': project.author,
            'parts': project.parts,
            'chapters': [
                {'num': ch['num'], 'title': ch['title'],
                 'content_length': len(ch['content']),
                 'source': ch.get('source', '')}
                for ch in project.chapters
            ],
            'bib_file': project.bib_file,
            'images_dirs': project.images_dirs,
            'custom_envs': project.custom_envs,
            'katex_macros': project.katex_macros,
        }
        output = json.dumps(info, ensure_ascii=False, indent=2)
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output)
            print(f"\nJSON written to: {args.output}", file=sys.stderr)
        else:
            print(output)

    else:
        # Default: print summary
        print(project.summary())


if __name__ == '__main__':
    main()
