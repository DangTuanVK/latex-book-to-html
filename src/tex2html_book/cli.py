#!/usr/bin/env python3
"""
cli.py - One-command LaTeX Book to HTML Converter

Converts any LaTeX book project into a self-contained offline HTML reference
with cards, tabs, math rendering (KaTeX), and embedded images.

Just point it at a main.tex file:

  book2html book/main.tex -o book/output.html

Under the hood it chains three modules:
  1. resolve_tex  - Analyze project structure, resolve includes
  2. tex2html     - Convert LaTeX chapters to HTML cards
  3. assemble     - Assemble cards into final HTML with skeleton template

For advanced customization, pass a config JSON:
  book2html book/main.tex -o output.html --config book_config.json

Author: Dang Minh Tuan
Email:  tuanvietkey@gmail.com
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from . import resolve_tex
from . import tex2html
from . import assemble as assemble_mod


def _default_skeleton_path():
    """Return the path to the bundled skeleton.html template."""
    try:
        from importlib.resources import files
        return str(files('tex2html_book').joinpath('data/skeleton.html'))
    except (ImportError, TypeError):
        # Fallback for Python 3.8 or running from source
        pkg_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(pkg_dir, 'data', 'skeleton.html')


# ============================================================================
# BRIDGE: ResolvedProject -> tex2html.Config
# ============================================================================
def project_to_config(project, user_config=None):
    """Convert a ResolvedProject to a tex2html.Config and assemble config dict.

    Args:
        project: resolve_tex.ResolvedProject instance.
        user_config: Optional dict of user overrides (from --config JSON).

    Returns:
        (tex2html_config, assemble_config_dict) tuple.
    """
    # Start with auto-generated config from project
    auto_cfg = resolve_tex.generate_config(project)

    # Merge user overrides
    if user_config:
        for key, val in user_config.items():
            if key.startswith('_'):
                continue  # skip _comment keys
            auto_cfg[key] = val

    # Build tex2html.Config
    t2h_cfg = tex2html.Config()
    t2h_cfg.book_dir = project.root_dir
    t2h_cfg.language = auto_cfg.get('language', 'vi')
    t2h_cfg.title = auto_cfg.get('title', project.title or 'Book')
    t2h_cfg.author = auto_cfg.get('author', project.author or '')
    t2h_cfg.default_difficulty = auto_cfg.get('default_difficulty', 5)
    t2h_cfg.cross_ref_text = auto_cfg.get('cross_ref_text', t2h_cfg.cross_ref_text)

    if 'exercise_keywords' in auto_cfg:
        t2h_cfg.exercise_keywords = auto_cfg['exercise_keywords']

    if 'katex_macros' in auto_cfg:
        t2h_cfg.katex_macros = auto_cfg['katex_macros']

    if 'difficulty_colors' in auto_cfg:
        t2h_cfg.diff_colors = {int(k): v for k, v in auto_cfg['difficulty_colors'].items()}

    if 'environments' in auto_cfg:
        for env_name, env_info in auto_cfg['environments'].items():
            if env_name.startswith('_'):
                continue
            if isinstance(env_info, dict):
                css = env_info.get('css', 'env-theorem')
                t2h_cfg.environments[env_name] = (css, env_info.get('label', env_name))

    # Cards: explicit or auto
    cards_val = auto_cfg.get('cards', '_auto_')
    if isinstance(cards_val, list):
        t2h_cfg.cards = cards_val

    # TikZ preamble for pre-rendering
    t2h_cfg.tikz_preamble = project.tikz_preamble or ''

    return t2h_cfg, auto_cfg


# ============================================================================
# CORE: Convert resolved chapters to cards
# ============================================================================
def convert_project_to_cards(project, t2h_cfg):
    """Convert all chapters from a ResolvedProject into HTML card fragments.

    Args:
        project: resolve_tex.ResolvedProject instance.
        t2h_cfg: tex2html.Config instance.

    Returns:
        (all_card_htmls, all_card_infos, chapter_titles) tuple.
    """
    environments = t2h_cfg.resolve_environments()

    # Build card metadata (sequential STTs across all chapters)
    # Create temporary (ch_num, section_idx) -> meta lookup
    card_meta = {}
    stt_counter = 1

    for ch in project.chapters:
        ch_num = ch['num']
        tex_content = tex2html.strip_comments(ch['content'])
        sections = tex2html.split_into_sections(
            tex_content, ch_num, t2h_cfg.exercise_keywords)
        for idx, (title, _) in enumerate(sections):
            en_title = tex2html._clean_title_for_en(title)
            card_meta[(ch_num, idx)] = {
                'stt': stt_counter,
                'en': en_title,
                'diff': t2h_cfg.default_difficulty,
                'vi': title,
            }
            stt_counter += 1

    # If user provided explicit cards metadata, use that instead
    if t2h_cfg.cards:
        card_meta = tex2html.build_card_meta_from_config(t2h_cfg.cards)

    # Resolve images directories (support multiple)
    images_dirs = [d for d in project.images_dirs if os.path.isdir(d)]
    # Also try default 'images' subdir if not already included
    default_img = os.path.join(project.root_dir, 'images')
    if os.path.isdir(default_img) and default_img not in images_dirs:
        images_dirs.append(default_img)
    images_dir = images_dirs if images_dirs else None

    # Process each chapter
    all_card_htmls = []
    all_card_infos = []
    chapter_titles = {}

    for ch in project.chapters:
        ch_num = ch['num']
        ch_title = ch['title']
        chapter_titles[ch_num] = ch_title

        print(f"\nChapter {ch_num}: {ch_title}", file=sys.stderr)

        # Split into sections
        tex_content = tex2html.strip_comments(ch['content'])
        sections = tex2html.split_into_sections(
            tex_content, ch_num, t2h_cfg.exercise_keywords)

        # Shared counters for figure/table numbering across sections
        figure_counter = [0]
        table_counter = [0]

        for idx, (title, content) in enumerate(sections):
            key = (ch_num, idx)
            meta = card_meta.get(key, {})
            stt = meta.get('stt', 900 + idx)
            en = meta.get('en', title)
            diff = meta.get('diff', t2h_cfg.default_difficulty)

            html = tex2html.latex_to_html(
                content,
                environments=environments,
                proof_label=t2h_cfg.proof_label,
                cross_ref_text=t2h_cfg.cross_ref_text,
                images_dir=images_dir,
                chapter_num=ch_num,
                figure_counter=figure_counter,
                table_counter=table_counter,
                card_stt=stt,
                tikz_preamble=getattr(t2h_cfg, 'tikz_preamble', ''),
                root_dir=project.root_dir,
            )
            card_html = tex2html.generate_card_html(
                stt, ch_num, title, en, diff, html, t2h_cfg.diff_colors)

            card_info = {
                'stt': stt, 'ch': ch_num,
                'vi': title, 'en': en, 'diff': diff,
            }
            all_card_htmls.append(card_html)
            all_card_infos.append(card_info)
            print(f"  Card {stt:3d}: [{diff}] {title}", file=sys.stderr)

    return all_card_htmls, all_card_infos, chapter_titles


# ============================================================================
# ASSEMBLE: Build final HTML from cards + skeleton + config
# ============================================================================
def assemble_html(cards_html_str, meta_dict, asm_config, bib_path, skeleton_path):
    """Assemble the final HTML file.

    This calls assemble module's internal functions to build header, sidebar,
    refs, etc. and insert them into the skeleton template.

    Args:
        cards_html_str: Concatenated card HTML fragments.
        meta_dict: Metadata dict with 'cards', 'chapters', 'parts'.
        asm_config: Config dict (assemble.py format).
        bib_path: Path to .bib file.
        skeleton_path: Path to skeleton.html template.

    Returns:
        Final assembled HTML string.
    """
    # Read skeleton
    skeleton = assemble_mod.read_file(skeleton_path, "Skeleton template")
    print(f"Loaded skeleton from {skeleton_path} ({len(skeleton)} chars)",
          file=sys.stderr)

    # Parse bib
    bib_entries = {}
    if bib_path and os.path.isfile(bib_path):
        bib_entries = assemble_mod.parse_bib(bib_path)
        print(f"Parsed {len(bib_entries)} bib entries from {bib_path}",
              file=sys.stderr)

    card_count = len(meta_dict['cards'])

    # Build all replacement components
    header_html = assemble_mod.build_header(asm_config, meta_dict)
    about_modal_html = assemble_mod.build_about_modal(asm_config, meta_dict)
    sidebar_html = assemble_mod.build_sidebar(meta_dict, asm_config)
    content_toolbar_html = assemble_mod.build_content_toolbar(meta_dict)
    tab_config_js = assemble_mod.build_tab_config(meta_dict, asm_config)
    katex_macros_js = assemble_mod.build_katex_macros(asm_config)
    refs_js = assemble_mod.build_refs_js(bib_entries)
    refs_urls_js = assemble_mod.build_refs_urls_js(asm_config)

    replacements = {
        "TITLE": asm_config.get("title", "Book"),
        "HEADER_HTML": header_html,
        "ABOUT_HTML": about_modal_html,
        "SIDEBAR_HTML": sidebar_html,
        "CARD_COUNT": str(card_count),
        "CARDS_HTML": cards_html_str,
        "TAB_CONFIG": tab_config_js,
        "KATEX_MACROS": katex_macros_js,
        "REFS": refs_js,
        "REFS_URLS": refs_urls_js,
    }

    result = assemble_mod.replace_placeholders(skeleton, replacements)

    # Online mode: replace embedded KaTeX with CDN links
    if asm_config.get('online', False):
        result = assemble_mod.convert_to_online(result)
        print("  Mode: ONLINE (KaTeX via CDN)", file=sys.stderr)
    else:
        print("  Mode: OFFLINE (self-contained)", file=sys.stderr)

    # Validate
    ok = assemble_mod.validate_output(result, card_count, bib_entries)

    return result, ok


# ============================================================================
# ENSURE REQUIRED CONFIG KEYS
# ============================================================================
def _ensure_assemble_config(cfg, project):
    """Ensure all required keys for assemble.py are present in config dict."""
    from datetime import date as _date
    today = _date.today()
    current_year = str(today.year)
    current_date = today.strftime('%d/%m/%Y')

    defaults = {
        'title': project.title or 'Book',
        'author': project.author or 'Author',
        'version': '1.0',
        'date': project.date or current_date,
        'copyright_year': current_year,
        'subtitle': project.subtitle or '',
        'affiliation': '',
        'author_url': '',
        'language': 'vi',
        'about_html': '',
        'katex_macros': project.katex_macros or {},
        'difficulty_colors': {},
        'refs_urls': {},
        'tabs': ['ch', 'vi', 'en', 'diff', 'ref', 'about'],
        'tab_labels': {
            'ch': 'Mục lục', 'vi': 'Tiếng Việt', 'en': 'English',
            'diff': 'Độ khó', 'ref': 'Tài liệu TK',
            'about': '\u2139 Giới thiệu',
        },
        'skeleton': _default_skeleton_path(),
        'bib': project.bib_file or '',
    }
    for key, val in defaults.items():
        cfg.setdefault(key, val)
    return cfg


# ============================================================================
# MAIN
# ============================================================================
def run(args):
    """Main execution flow."""
    main_tex = os.path.abspath(args.main_tex)
    output_path = os.path.abspath(args.output)

    print(f"{'=' * 60}", file=sys.stderr)
    print(f"book2html: LaTeX \u2192 HTML Converter", file=sys.stderr)
    print(f"{'=' * 60}", file=sys.stderr)

    # Step 1: Resolve LaTeX project
    print(f"\n[1/4] Resolving LaTeX project...", file=sys.stderr)
    project = resolve_tex.resolve_project(main_tex)
    print(f"\n{project.summary()}", file=sys.stderr)

    if not project.chapters:
        print("ERROR: No chapters/sections detected in the project.",
              file=sys.stderr)
        sys.exit(1)

    # Step 2: Build configuration
    print(f"\n[2/4] Building configuration...", file=sys.stderr)
    user_config = None
    if args.config:
        if os.path.isfile(args.config):
            with open(args.config, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
            print(f"  Loaded user config: {args.config}", file=sys.stderr)
        else:
            print(f"  WARNING: Config file not found: {args.config}",
                  file=sys.stderr)

    # CLI overrides
    overrides = {}
    if args.title:
        overrides['title'] = args.title
    if args.author:
        overrides['author'] = args.author
    if args.version:
        overrides['version'] = args.version
    if args.date:
        overrides['date'] = args.date
    if args.lang:
        overrides['language'] = args.lang
    if args.online:
        overrides['online'] = True
    if user_config:
        overrides.update(user_config)

    t2h_cfg, asm_config = project_to_config(
        project, user_config=overrides if overrides else None)
    asm_config = _ensure_assemble_config(asm_config, project)

    # Resolve skeleton path
    skeleton_path = asm_config.get('skeleton', '')
    if skeleton_path and not os.path.isabs(skeleton_path):
        # Try relative to CWD first
        if os.path.isfile(skeleton_path):
            skeleton_path = os.path.abspath(skeleton_path)
        else:
            skeleton_path = _default_skeleton_path()
    if not skeleton_path or not os.path.isfile(skeleton_path):
        skeleton_path = _default_skeleton_path()
    if not os.path.isfile(skeleton_path):
        print(f"ERROR: Skeleton template not found: {skeleton_path}",
              file=sys.stderr)
        sys.exit(1)

    # Resolve bib path
    bib_path = asm_config.get('bib', '') or project.bib_file
    if bib_path and not os.path.isabs(bib_path):
        bib_path = os.path.join(project.root_dir, bib_path)

    print(f"  Title: {asm_config.get('title')}", file=sys.stderr)
    print(f"  Author: {asm_config.get('author')}", file=sys.stderr)
    print(f"  Version: {asm_config.get('version', '1.0')}", file=sys.stderr)
    print(f"  Date: {asm_config.get('date', '(auto)')}", file=sys.stderr)
    print(f"  Chapters: {len(project.chapters)}", file=sys.stderr)
    print(f"  Skeleton: {skeleton_path}", file=sys.stderr)
    print(f"  Bib: {bib_path or '(none)'}", file=sys.stderr)

    # Step 3: Convert chapters to HTML cards
    print(f"\n[3/4] Converting LaTeX to HTML cards...", file=sys.stderr)
    all_card_htmls, all_card_infos, chapter_titles = \
        convert_project_to_cards(project, t2h_cfg)

    if not all_card_htmls:
        print("ERROR: No cards generated.", file=sys.stderr)
        sys.exit(1)

    cards_html_str = '\n\n'.join(all_card_htmls)

    # Build metadata for assemble
    meta_dict = {
        'cards': all_card_infos,
        'chapters': {str(ch): title for ch, title in sorted(chapter_titles.items())},
        'parts': project.parts,
    }

    # Step 4: Assemble final HTML
    print(f"\n[4/4] Assembling final HTML...", file=sys.stderr)
    result_html, ok = assemble_html(
        cards_html_str, meta_dict, asm_config, bib_path, skeleton_path)

    # Write output
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.isdir(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(result_html)

    file_size_kb = os.path.getsize(output_path) // 1024

    # Save config for reference
    if args.save_config:
        config_out = args.save_config
        with open(config_out, 'w', encoding='utf-8') as f:
            json.dump(asm_config, f, ensure_ascii=False, indent=2)
        print(f"\nSaved config to: {config_out}", file=sys.stderr)

    # Summary
    print(f"\n{'=' * 60}", file=sys.stderr)
    print(f"DONE", file=sys.stderr)
    print(f"{'=' * 60}", file=sys.stderr)
    print(f"  Output:    {output_path}", file=sys.stderr)
    print(f"  File size: {file_size_kb} KB", file=sys.stderr)
    print(f"  Cards:     {len(all_card_infos)}", file=sys.stderr)
    print(f"  Chapters:  {len(project.chapters)}", file=sys.stderr)

    ch_counts = {}
    for ci in all_card_infos:
        ch_counts[ci['ch']] = ch_counts.get(ci['ch'], 0) + 1
    for ch in sorted(ch_counts):
        ch_title = chapter_titles.get(ch, '')
        print(f"    Ch.{ch}: {ch_counts[ch]} cards  ({ch_title})",
              file=sys.stderr)

    print(f"{'=' * 60}", file=sys.stderr)

    if not ok:
        print("\nCompleted with warnings. Please review.", file=sys.stderr)
        sys.exit(2)


def main():
    parser = argparse.ArgumentParser(
        description='One-command LaTeX Book \u2192 HTML Converter',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Simplest: just provide main.tex and output path
  %(prog)s book/main.tex -o book/output.html

  # With custom config for tabs, environments, etc.
  %(prog)s book/main.tex -o book/output.html --config book_config.json

  # Override title, author, version, date
  %(prog)s book/main.tex -o output.html --title "My Book" --author "Author"
  %(prog)s book/main.tex -o output.html --version "2.0" --date "01/03/2026"

  # Online mode (use CDN, smaller file size)
  %(prog)s book/main.tex -o output.html --online

  # Analyze project structure first (dry run)
  %(prog)s book/main.tex --dry-run

  # Save auto-generated config for later editing
  %(prog)s book/main.tex -o output.html --save-config auto_config.json
""")

    parser.add_argument(
        'main_tex',
        help='Path to main .tex file (the entry point of the LaTeX project)')
    parser.add_argument(
        '-o', '--output',
        help='Output HTML file path (required unless --dry-run)')
    parser.add_argument(
        '--config', '-f',
        help='Optional config JSON for customizing tabs, environments, etc.')
    parser.add_argument(
        '--title',
        help='Override book title')
    parser.add_argument(
        '--author',
        help='Override author name')
    parser.add_argument(
        '--version',
        help='Override version string (e.g. "1.0", "2.1-beta")')
    parser.add_argument(
        '--date',
        help='Override date string (e.g. "20/02/2026")')
    parser.add_argument(
        '--lang', default=None,
        help='Language (vi, en). Default: vi')
    parser.add_argument(
        '--online', action='store_true',
        help='Online mode: use CDN for KaTeX instead of embedding (smaller file, requires Internet)')
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Analyze project and show structure without generating HTML')
    parser.add_argument(
        '--save-config',
        help='Save the auto-generated config to a JSON file for later editing')

    args = parser.parse_args()

    # Validate
    if not os.path.isfile(args.main_tex):
        print(f"ERROR: File not found: {args.main_tex}", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        # Just resolve and print
        project = resolve_tex.resolve_project(args.main_tex)
        print(f"\n{project.summary()}")

        if args.save_config:
            config_json = resolve_tex.generate_config_json(
                project, output_path=args.output)
            with open(args.save_config, 'w', encoding='utf-8') as f:
                f.write(config_json)
            print(f"\nConfig saved to: {args.save_config}")
        return

    if not args.output:
        print("ERROR: --output is required (unless using --dry-run).",
              file=sys.stderr)
        sys.exit(1)

    run(args)


if __name__ == '__main__':
    main()
