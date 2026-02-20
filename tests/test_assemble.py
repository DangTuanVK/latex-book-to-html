"""Tests for assemble module."""
import os
import sys

try:
    from tex2html_book import assemble
except ImportError:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
    from tex2html_book import assemble


class TestReplacePlaceholders:
    def test_basic(self):
        skeleton = "Hello __NAME__, welcome to __PLACE__!"
        result = assemble.replace_placeholders(skeleton, {
            "NAME": "World",
            "PLACE": "Earth",
        })
        assert result == "Hello World, welcome to Earth!"

    def test_missing_placeholder(self):
        skeleton = "Hello __NAME__!"
        # Should still work, just warn
        result = assemble.replace_placeholders(skeleton, {"NAME": "World"})
        assert result == "Hello World!"


class TestDiffColor:
    def test_known_level(self):
        config = {"difficulty_colors": {"5": "#4CAF50"}}
        result = assemble.diff_color(5, config)
        assert "#4CAF50" in result

    def test_default_color(self):
        result = assemble.diff_color(99, {})
        # Should return some default
        assert isinstance(result, str)


class TestBuildHeader:
    def test_basic(self):
        config = {
            "title": "Test Book",
            "author": "Author",
            "version": "1.0",
            "date": "2026",
            "copyright_year": "2026",
            "tabs": ["ch", "about"],
            "tab_labels": {"ch": "Contents", "about": "About"},
            "difficulty_colors": {},
        }
        meta = {
            "cards": [{"stt": 1, "ch": 1, "vi": "Test", "en": "Test", "diff": 5}],
            "chapters": {"1": "Chapter 1"},
            "parts": [],
        }
        result = assemble.build_header(config, meta)
        assert "Test Book" in result
        assert isinstance(result, str)


class TestBuildSidebar:
    def test_basic(self):
        meta = {
            "cards": [
                {"stt": 1, "ch": 1, "vi": "Section 1", "en": "Section 1", "diff": 5},
                {"stt": 2, "ch": 1, "vi": "Section 2", "en": "Section 2", "diff": 3},
            ],
            "chapters": {"1": "Chapter One"},
            "parts": [],
        }
        config = {
            "difficulty_colors": {},
            "tabs": ["ch", "vi", "en", "diff"],
            "tab_labels": {"ch": "Contents", "vi": "VI", "en": "EN", "diff": "Diff"},
        }
        result = assemble.build_sidebar(meta, config)
        assert "Section 1" in result
        assert isinstance(result, str)


class TestParseBib:
    def test_basic_entry(self):
        import tempfile
        bib_content = """
@article{euler1748,
  author = {Euler, Leonhard},
  title = {Introductio in analysin infinitorum},
  year = {1748},
  journal = {Lausanne}
}
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.bib', delete=False) as f:
            f.write(bib_content)
            bib_path = f.name

        try:
            entries = assemble.parse_bib(bib_path)
            assert 'euler1748' in entries
            assert 'Euler' in entries['euler1748'].get('author', '')
        finally:
            os.unlink(bib_path)


class TestConvertToOnline:
    def test_removes_embedded_katex(self):
        html = """<html><head>
<style>/* KaTeX */
body { font-size: 16px; }
.katex { display: inline; }
</style>
</head><body>
<script>/* KaTeX */
var katex = {};
</script>
<script>/* KaTeX auto-render */
renderMathInElement(document.body);
</script>
</body></html>"""
        result = assemble.convert_to_online(html)
        assert "cdn.jsdelivr.net" in result
        assert "/* KaTeX */" not in result.split("<!--")[0]  # Original CSS removed


class TestValidateOutput:
    def test_basic_validation(self):
        html = '<div class="card" data-stt="1">Card 1</div>'
        # Should return True/False without crashing
        result = assemble.validate_output(html, 1, {})
        assert isinstance(result, bool)


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
