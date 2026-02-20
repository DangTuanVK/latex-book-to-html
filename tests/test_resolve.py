"""Tests for resolve_tex module."""
import os
import sys
import tempfile

# Support running tests both with pytest (installed package) and standalone
try:
    from tex2html_book import resolve_tex
except ImportError:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
    from tex2html_book import resolve_tex


def _write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


class TestStripComments:
    def test_line_comment(self):
        assert resolve_tex._strip_tex_comments("hello % world\n") == "hello \n"

    def test_no_comment(self):
        assert resolve_tex._strip_tex_comments("hello world\n") == "hello world\n"

    def test_escaped_percent(self):
        # \% should NOT be stripped
        result = resolve_tex._strip_tex_comments("50\\% done\n")
        assert "50\\%" in result


class TestResolveProject:
    def test_minimal_book(self):
        """Test resolving a minimal 2-chapter book."""
        with tempfile.TemporaryDirectory() as tmp:
            chapters_dir = os.path.join(tmp, 'chapters')
            os.makedirs(chapters_dir)

            _write_file(os.path.join(tmp, 'main.tex'), r"""
\documentclass{book}
\usepackage{amsmath}
\title{Test Book}
\author{Test Author}
\begin{document}
\part{Part One}
\input{chapters/ch01}
\input{chapters/ch02}
\end{document}
""")
            _write_file(os.path.join(chapters_dir, 'ch01.tex'), r"""
\chapter{First Chapter}
\section{Introduction}
Hello world. $E = mc^2$.
\section{Details}
More content here.
""")
            _write_file(os.path.join(chapters_dir, 'ch02.tex'), r"""
\chapter{Second Chapter}
\section{Analysis}
Some analysis content.
""")
            project = resolve_tex.resolve_project(os.path.join(tmp, 'main.tex'))
            assert project.title == 'Test Book'
            assert project.author == 'Test Author'
            assert len(project.chapters) == 2
            assert project.chapters[0]['num'] == 1
            assert 'First Chapter' in project.chapters[0]['title']
            assert project.chapters[1]['num'] == 2

    def test_single_file_book(self):
        """Test resolving a book with everything in main.tex."""
        with tempfile.TemporaryDirectory() as tmp:
            _write_file(os.path.join(tmp, 'main.tex'), r"""
\documentclass{book}
\title{Single File}
\author{Author}
\begin{document}
\chapter{Only Chapter}
\section{Section One}
Content $x^2$.
\end{document}
""")
            project = resolve_tex.resolve_project(os.path.join(tmp, 'main.tex'))
            assert project.title == 'Single File'
            assert len(project.chapters) >= 1


class TestGenerateConfig:
    def test_config_has_required_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_file(os.path.join(tmp, 'main.tex'), r"""
\documentclass{book}
\title{Config Test}
\author{Author}
\begin{document}
\chapter{Chapter}
\section{Section}
Content.
\end{document}
""")
            project = resolve_tex.resolve_project(os.path.join(tmp, 'main.tex'))
            config = resolve_tex.generate_config(project)
            assert 'title' in config
            assert 'author' in config
            assert 'language' in config
            assert config['title'] == 'Config Test'


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
