# latex-book-to-html

Convert LaTeX book projects into self-contained offline HTML references with math rendering, interactive cards, and tabbed navigation.

## Features

- **Math rendering** — KaTeX embedded (offline) or via CDN (online mode)
- **Card-based layout** — Each section becomes a navigable card
- **Tabbed views** — Table of contents, Vietnamese/English titles, difficulty levels, references
- **LaTeX environments** — Theorems, proofs, definitions, examples, custom tcolorbox environments
- **Tables and figures** — Auto-numbered with captions
- **Code blocks** — verbatim, lstlisting, minted environments with syntax highlighting
- **TikZ diagrams** — Pre-rendered to images (requires xelatex + pdftoppm)
- **Cross-references** — `\ref`, `\label`, `\cite` resolved to clickable links
- **Bibliography** — Parses .bib files, citation tooltips with full reference info
- **Self-contained** — Single HTML file, no external dependencies (offline mode)
- **Online mode** — Use KaTeX CDN for ~40% smaller file size

## Quick Start

```bash
# Clone the repository
git clone https://github.com/dangtuanvk/latex-book-to-html.git
cd latex-book-to-html

# Convert the example book (no install required)
python3 book2html.py examples/minimal-book/main.tex -o output.html

# Open in browser
xdg-open output.html    # Linux
open output.html         # macOS
```

## Installation

### Option 1: Standalone (no install)

Just clone and run — requires only Python 3.8+:

```bash
python3 book2html.py your-book/main.tex -o output.html
```

### Option 2: pip install

```bash
pip install .
# or for development:
pip install -e .
```

Then use the `book2html` command anywhere:

```bash
book2html your-book/main.tex -o output.html
```

## Usage

```
book2html main.tex -o output.html [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-o, --output FILE` | Output HTML file path (required) |
| `--config FILE` | JSON config for tabs, environments, etc. |
| `--title TEXT` | Override book title |
| `--author TEXT` | Override author name |
| `--version TEXT` | Override version string |
| `--date TEXT` | Override date string |
| `--lang LANG` | Language: `vi` or `en` (default: `vi`) |
| `--online` | Use CDN for KaTeX (smaller file, needs Internet) |
| `--dry-run` | Analyze project structure without generating HTML |
| `--save-config FILE` | Save auto-generated config for later editing |

### Examples

```bash
# Basic conversion
book2html book/main.tex -o book/output.html

# With custom title and author
book2html book/main.tex -o output.html --title "My Book" --author "Author Name"

# Online mode (smaller file)
book2html book/main.tex -o output.html --online

# Analyze project structure first
book2html book/main.tex --dry-run

# Save config for customization
book2html book/main.tex -o output.html --save-config my_config.json
# Edit my_config.json, then:
book2html book/main.tex -o output.html --config my_config.json
```

## Configuration

The converter auto-detects most settings from your LaTeX project. For advanced customization, use a JSON config file:

```json
{
    "title": "My Book Title",
    "author": "Author Name",
    "version": "1.0",
    "language": "en",
    "tabs": ["ch", "vi", "en", "diff", "ref", "about"],
    "tab_labels": {
        "ch": "Contents",
        "vi": "Vietnamese",
        "en": "English",
        "diff": "Difficulty",
        "ref": "References",
        "about": "About"
    },
    "environments": {
        "theorem": {"css": "env-theorem", "label": "Theorem"},
        "lemma": {"css": "env-theorem", "label": "Lemma"},
        "definition": {"css": "env-definition", "label": "Definition"}
    },
    "katex_macros": {
        "\\R": "\\mathbb{R}",
        "\\Z": "\\mathbb{Z}"
    }
}
```

## Supported LaTeX Features

| Feature | LaTeX Commands |
|---------|---------------|
| Book structure | `\part`, `\chapter`, `\section`, `\subsection` |
| Math | `$...$`, `$$...$$`, `\[...\]`, `\begin{equation}`, `align`, `gather` |
| Theorems | `\begin{theorem}`, `\begin{lemma}`, `\begin{proof}`, etc. |
| Lists | `\begin{itemize}`, `\begin{enumerate}`, `\begin{description}` |
| Tables | `\begin{tabular}`, `\begin{table}` with captions |
| Figures | `\includegraphics`, `\begin{figure}` with captions |
| Code | `\begin{verbatim}`, `\begin{lstlisting}`, `\begin{minted}` |
| TikZ | `\begin{tikzpicture}` (pre-rendered with xelatex) |
| References | `\label`, `\ref`, `\cite`, `\begin{thebibliography}` |
| Formatting | `\textbf`, `\textit`, `\emph`, `\texttt`, `\underline` |
| Includes | `\input`, `\include`, `\subimport` |

## Optional Dependencies

- **xelatex** + **pdftoppm** — Required only for TikZ diagram rendering. Without these, TikZ blocks are shown as formatted LaTeX source.

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.
