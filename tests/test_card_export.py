"""Tests for story card image export."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from code_storyteller.export.card_renderer import (
    render_html,
    export_card,
    _get_theme,
    _markdown_to_html,
    _inline_format,
    THEMES,
)


SAMPLE_STORY = """## 🎬 The Crew
- **validate_token** — the bouncer at the door
- **get_user** — the inside man

## 🎯 The Target
The user's identity data.

## 📋 The Plan
1. Token arrives at the door
2. Bouncer checks credentials
3. Inside man fetches the goods

## 💥 What Could Go Wrong
Token expired → alarm gets triggered

```python
return user
```
"""


class TestGetTheme:
    def test_known_style_returns_colors(self):
        bg, text, accent, sec = _get_theme("heist")
        assert bg == "#1a1a2e"
        assert accent == "#e94560"

    def test_all_styles_have_themes(self):
        for style in THEMES:
            bg, text, accent, sec = _get_theme(style)
            assert all(c.startswith("#") for c in [bg, text, accent, sec])

    def test_unknown_style_returns_default(self):
        bg, text, accent, sec = _get_theme("nonexistent")
        assert bg is not None
        assert accent is not None


class TestInlineFormat:
    def test_bold(self):
        result = _inline_format("hello **world**")
        assert result == "hello <strong>world</strong>"

    def test_italic(self):
        result = _inline_format("hello *world*")
        assert result == "hello <em>world</em>"

    def test_inline_code(self):
        result = _inline_format("use `validate_token` here")
        assert result == "use <code>validate_token</code> here"

    def test_html_escaping(self):
        result = _inline_format("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result


class TestMarkdownToHtml:
    def test_heading_h1(self):
        result = _markdown_to_html("# Hello World")
        assert "<h1>Hello World</h1>" in result

    def test_heading_h2(self):
        result = _markdown_to_html("## The Crew")
        assert "<h2>The Crew</h2>" in result

    def test_heading_h3(self):
        result = _markdown_to_html("### Sub Section")
        assert "<h3>Sub Section</h3>" in result

    def test_unordered_list(self):
        md = "- item one\n- item two\n- item three"
        result = _markdown_to_html(md)
        assert "<ul>" in result
        assert "<li>item one</li>" in result
        assert "<li>item two</li>" in result
        assert "</ul>" in result

    def test_code_block(self):
        md = "```python\ndef foo():\n    pass\n```"
        result = _markdown_to_html(md)
        assert "<pre><code>" in result
        assert "def foo():" in result
        assert "</code></pre>" in result

    def test_paragraph(self):
        result = _markdown_to_html("Just a normal paragraph.")
        assert "<p>Just a normal paragraph.</p>" in result

    def test_empty_line(self):
        result = _markdown_to_html("")
        assert result.strip() == "" or "<br/>" in result

    def test_story_with_all_elements(self):
        result = _markdown_to_html(SAMPLE_STORY)
        assert "<h2>" in result
        assert "<li>" in result
        assert "<pre><code>" in result
        assert "The user&#x27;s identity data." in result or "The user's identity data." in result


class TestRenderHtml:
    def test_contains_style_badge(self):
        result = render_html(SAMPLE_STORY, style="heist", filepath="auth.py")
        assert "HEIST" in result
        assert "🎬" in result

    def test_contains_filename(self):
        result = render_html(SAMPLE_STORY, style="heist", filepath="src/auth.py")
        assert "auth.py" in result

    def test_contains_theme_colors(self):
        result = render_html(SAMPLE_STORY, style="heist")
        bg, text, accent, sec = _get_theme("heist")
        assert bg in result
        assert accent in result

    def test_recipe_style_theme(self):
        result = render_html(SAMPLE_STORY, style="recipe", filepath="cook.py")
        bg, text, accent, sec = _get_theme("recipe")
        assert bg in result
        assert "🍽️" in result

    def test_5yo_style_theme(self):
        result = render_html(SAMPLE_STORY, style="5yo")
        assert "🧸" in result

    def test_output_is_valid_html(self):
        result = render_html(SAMPLE_STORY, style="heist", filepath="test.py")
        assert result.startswith("<!DOCTYPE html>")
        assert "</html>" in result
        assert "<style>" in result

    def test_story_content_preserved(self):
        result = render_html(SAMPLE_STORY, style="heist", filepath="test.py")
        assert "validate_token" in result
        assert "The Plan" in result


class TestExportCard:
    def test_html_export_writes_file(self, tmp_path):
        output = str(tmp_path / "card.html")
        result = export_card(SAMPLE_STORY, output, style="heist", filepath="test.py")
        assert Path(result).exists()
        content = Path(result).read_text()
        assert "<html>" in content

    def test_html_export_preserves_content(self, tmp_path):
        output = str(tmp_path / "card.html")
        export_card(SAMPLE_STORY, output, style="heist")
        content = Path(output).read_text()
        assert "validate_token" in content
        assert "HEIST" in content

    def test_unknown_format_fallback_to_pdf(self, tmp_path):
        """Unknown extension falls back to .pdf appended."""
        output = str(tmp_path / "card.xyz")
        with pytest.raises(Exception):
            export_card(SAMPLE_STORY, output, style="heist")

    def test_style_badge_present_in_all_styles(self, tmp_path):
        for style in THEMES:
            output = str(tmp_path / f"card_{style}.html")
            export_card(SAMPLE_STORY, output, style=style, filepath="test.py")
            content = Path(output).read_text()
            assert style.upper() in content
