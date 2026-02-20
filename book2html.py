#!/usr/bin/env python3
"""
Standalone runner for latex-book-to-html.

No pip install required — just run:

  python3 book2html.py book/main.tex -o output.html

This script adds src/ to the Python path and invokes the package CLI.
For pip-installed usage, use the `book2html` command directly.
"""
import os
import sys

# Add src/ directory to path so tex2html_book package can be imported
_ROOT = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_ROOT, 'src')
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tex2html_book.cli import main

if __name__ == '__main__':
    main()
