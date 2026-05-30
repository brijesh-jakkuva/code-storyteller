"""Render story markdown as image cards (PNG, PDF, HTML)."""

from __future__ import annotations
import html
import os
import re
from pathlib import Path
from typing import Optional

from code_storyteller.templates.styles import get_template

# Card dimensions (px) at 2x for retina-quality output
CARD_WIDTH = 800
CARD_PADDING = 40


# Per-style color themes: (bg, text, accent, secondary_bg)
THEMES = {
    "heist": ("#1a1a2e", "#e0e0e0", "#e94560", "#16213e"),
    "recipe": ("#fef9ef", "#3d2b1f", "#e87a24", "#fff3e0"),
    "5yo": ("#fff5f9", "#4a4a4a", "#ff6b9d", "#ffe0ec"),
    "pm": ("#f0f4f8", "#1a202c", "#3182ce", "#e2e8f0"),
    "sports": ("#0d1b2a", "#e0e1dd", "#ff6b35", "#1b2838"),
}

DEFAULT_THEME = ("#1e1e2e", "#cdd6f4", "#f38ba8", "#313244")


def _get_theme(style: str) -> tuple[str, str, str, str]:
    return THEMES.get(style, DEFAULT_THEME)


def _markdown_to_html(md_text: str) -> str:
    """Lightweight markdown→HTML converter. Covers the story output format."""
    import html as _html
    lines = md_text.split("\n")
    html_lines = []
    in_code = False
    code_lines = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        # Code fences
        if stripped.startswith("```"):
            if in_code:
                code_body = _html.escape("\n".join(code_lines))
                html_lines.append(f"<pre><code>{code_body}</code></pre>")
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue

        if in_code:
            code_lines.append(line)
            continue

        # Close list if needed
        if not stripped.startswith("- ") and in_list:
            html_lines.append("</ul>")
            in_list = False

        # Headings
        if stripped.startswith("### "):
            html_lines.append(f"<h3>{_html.escape(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            html_lines.append(f"<h2>{_html.escape(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            html_lines.append(f"<h1>{_html.escape(stripped[2:])}</h1>")
        # List items
        elif stripped.startswith("- "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{_inline_format(stripped[2:])}</li>")
        # Empty line
        elif not stripped:
            html_lines.append("<br/>")
        # Regular paragraph
        else:
            html_lines.append(f"<p>{_inline_format(stripped)}</p>")

    if in_code and code_lines:
        code_body = _html.escape("\n".join(code_lines))
        html_lines.append(f"<pre><code>{code_body}</code></pre>")
    if in_list:
        html_lines.append("</ul>")

    return "\n".join(html_lines)


def _inline_format(text: str) -> str:
    """Handle **bold**, *italic*, `code` inline formatting."""
    import html as _html
    text = _html.escape(text)
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # Italic
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    # Inline code
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    return text


def _build_css(style: str) -> str:
    bg, text, accent, sec_bg = _get_theme(style)
    return f"""
    @page {{
        size: {CARD_WIDTH}px auto;
        margin: 0;
    }}
    body {{
        background: {bg};
        color: {text};
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
        font-size: 15px;
        line-height: 1.6;
        padding: {CARD_PADDING}px;
        margin: 0;
        width: {CARD_WIDTH - CARD_PADDING * 2}px;
    }}
    h1 {{
        color: {accent};
        font-size: 22px;
        margin: 0 0 12px 0;
        border-bottom: 2px solid {accent}33;
        padding-bottom: 8px;
    }}
    h2 {{
        color: {accent};
        font-size: 18px;
        margin: 16px 0 8px 0;
    }}
    h3 {{
        color: {accent}cc;
        font-size: 16px;
        margin: 12px 0 6px 0;
    }}
    pre {{
        background: {sec_bg};
        border-radius: 8px;
        padding: 12px;
        overflow-x: auto;
        font-size: 13px;
        line-height: 1.45;
        border-left: 3px solid {accent};
        margin: 10px 0;
    }}
    code {{
        background: {sec_bg}88;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 13px;
    }}
    pre code {{
        background: none;
        padding: 0;
    }}
    ul {{
        padding-left: 20px;
        margin: 6px 0;
    }}
    li {{
        margin: 4px 0;
    }}
    strong {{
        color: {accent};
    }}
    em {{
        opacity: 0.85;
    }}
    p {{
        margin: 6px 0;
    }}
    """


def _style_badge(style: str) -> str:
    bg, text, accent, sec_bg = _get_theme(style)
    emoji = {"heist": "🎬", "recipe": "🍽️", "5yo": "🧸", "pm": "📋", "sports": "🏆"}.get(style, "🎭")
    return f"""
    <div style="position:absolute;top:12px;right:12px;background:{accent}22;color:{accent};
    padding:3px 10px;border-radius:12px;font-size:12px;font-weight:bold;border:1px solid {accent}44;">
        {emoji} {style.upper()}
    </div>
    """


def render_html(story_md: str, style: str = "heist", filepath: str = "") -> str:
    """Render story markdown as styled HTML string."""
    bg, text, accent, sec_bg = _get_theme(theme := style)
    css = _build_css(style)
    body_html = _markdown_to_html(story_md)
    badge = _style_badge(style)
    title = html.escape(Path(filepath).name) if filepath else "Code Story"

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>{css}</style></head>
<body>
{badge}
<h1 style="padding-right:80px;">📄 {title}</h1>
{body_html}
</body>
</html>"""


def render_pdf(story_md: str, output_path: str, style: str = "heist", filepath: str = "") -> str:
    """Render story as PDF file. Returns output path."""
    try:
        from weasyprint import HTML
    except ImportError:
        raise ImportError(
            "weasyprint required for PDF export. Install: pip install weasyprint\n"
            "See: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html"
        )

    html_str = render_html(story_md, style, filepath)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_str).write_pdf(str(output))
    return str(output)


def render_png(story_md: str, output_path: str, style: str = "heist", filepath: str = "") -> str:
    """Render story as PNG file. Returns output path."""
    try:
        from weasyprint import HTML
    except ImportError:
        raise ImportError(
            "weasyprint required for PNG export. Install: pip install weasyprint\n"
            "See: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html"
        )

    html_str = render_html(story_md, style, filepath)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = HTML(string=html_str).render()
    # weasyprint renders to PDF; use pdf2image as bridge to PNG
    try:
        from pdf2image import convert_from_bytes
        pdf_bytes = doc.write_pdf()
        images = convert_from_bytes(pdf_bytes, dpi=200)
        if images:
            images[0].save(str(output), "PNG")
    except ImportError:
        # Fallback: write PDF alongside
        pdf_path = output.with_suffix(".pdf")
        doc.write_pdf(str(pdf_path))
        raise ImportError(
            "pdf2image required for PNG export. Install: pip install pdf2image\n"
            "PDF saved to {pdf_path} as fallback."
        )
    return str(output)


def export_card(
    story_md: str,
    output_path: str,
    style: str = "heist",
    filepath: str = "",
) -> str:
    """Export story card. Format determined by output extension (.png, .pdf, .html)."""
    ext = Path(output_path).suffix.lower()
    if ext == ".pdf":
        return render_pdf(story_md, output_path, style, filepath)
    elif ext == ".html":
        html_str = render_html(story_md, style, filepath)
        Path(output_path).write_text(html_str)
        return output_path
    elif ext == ".png":
        return render_png(story_md, output_path, style, filepath)
    else:
        # Default to PDF
        return render_pdf(story_md, output_path + ".pdf", style, filepath)
