"""Tests for tex2html module."""
import os
import sys

try:
    from tex2html_book import tex2html
except ImportError:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
    from tex2html_book import tex2html


class TestStripComments:
    def test_basic(self):
        result = tex2html.strip_comments("hello % comment\nworld\n")
        assert "hello" in result
        assert "comment" not in result
        assert "world" in result


class TestProtectMath:
    def test_inline_math(self):
        text = "The formula $x^2 + y^2 = z^2$ is famous."
        protected = tex2html.protect_math(text)
        assert "$" not in protected or "MATH" in protected

    def test_display_math(self):
        text = r"We have \[ E = mc^2 \] which is important."
        protected = tex2html.protect_math(text)
        assert "\\[" not in protected


class TestLatexToHtml:
    def test_bold(self):
        result = tex2html.latex_to_html(r"\textbf{hello}")
        assert "<strong>" in result or "<b>" in result
        assert "hello" in result

    def test_italic(self):
        result = tex2html.latex_to_html(r"\textit{world}")
        assert "<em>" in result or "<i>" in result
        assert "world" in result

    def test_inline_math_preserved(self):
        result = tex2html.latex_to_html("Formula $x^2$.")
        # KaTeX will render this, so the math delimiters should be present
        assert "x^2" in result

    def test_display_math_preserved(self):
        result = tex2html.latex_to_html(r"Result: \[ a + b = c \]")
        assert "a + b = c" in result

    def test_itemize(self):
        tex = r"""
\begin{itemize}
\item First
\item Second
\end{itemize}
"""
        result = tex2html.latex_to_html(tex)
        assert "<li>" in result
        assert "First" in result
        assert "Second" in result

    def test_enumerate(self):
        tex = r"""
\begin{enumerate}
\item Alpha
\item Beta
\end{enumerate}
"""
        result = tex2html.latex_to_html(tex)
        assert "<li>" in result or "<ol>" in result

    def test_theorem_environment(self):
        envs = {"theorem": ("env-theorem", "Theorem")}
        tex = r"""
\begin{theorem}
Every even number greater than 2 is the sum of two primes.
\end{theorem}
"""
        result = tex2html.latex_to_html(tex, environments=envs)
        assert "Theorem" in result
        assert "two primes" in result

    def test_tabular(self):
        tex = r"""
\begin{tabular}{|c|c|}
\hline
A & B \\
\hline
1 & 2 \\
\hline
\end{tabular}
"""
        result = tex2html.latex_to_html(tex)
        assert "<table" in result
        assert "<td" in result


class TestSplitIntoSections:
    def test_basic_split(self):
        tex = r"""
\section{Introduction}
Hello world.
\section{Methods}
Some methods.
"""
        sections = tex2html.split_into_sections(tex, chapter_num=1)
        assert len(sections) >= 2
        titles = [s[0] for s in sections]
        assert any("Introduction" in t for t in titles)
        assert any("Methods" in t for t in titles)


class TestGenerateCardHtml:
    def test_card_structure(self):
        html = tex2html.generate_card_html(
            stt=1, ch=1, vi_title="Test", en_title="Test",
            diff=5, body_html="<p>Content</p>")
        assert 'class="card"' in html or 'data-stt="1"' in html
        assert "Content" in html


class TestConfig:
    def test_defaults(self):
        cfg = tex2html.Config()
        assert cfg.language == 'vi'
        assert cfg.proof_label == 'Chứng minh' or cfg.proof_label


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
