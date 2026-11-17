"""Escaping and small HTML builders. Every dynamic value passes through esc() or md()."""
from __future__ import annotations

import html as _html
import re

import streamlit as st

# Characters with meaning in Streamlit Markdown (CommonMark + :colour[...] / :material/...: directives).
_MD_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+\-.!|<>~$:=^&])")

TONES = ("neutral", "blue", "green", "amber", "red", "violet")


def esc(value) -> str:
    """HTML-escape any value (quotes included) for use inside st.html content or attributes."""
    return _html.escape("" if value is None else str(value), quote=True)


def md(value) -> str:
    """Escape text for Markdown contexts (st.markdown, captions, widget labels, alerts)."""
    text = "" if value is None else str(value)
    return _MD_SPECIAL.sub(r"\\\1", text).replace("\n", " ")


def code(value) -> str:
    """Inline Markdown code span. Contents of a code span are literal, so md() must not be used
    inside it; backticks are replaced so the value cannot close the span."""
    return "`" + ("" if value is None else str(value)).replace("`", "'").replace("\n", " ") + "`"


def chip(text, tone: str = "neutral", *, dot: bool = False, title: str | None = None) -> str:
    """Inline status chip. tone: neutral | blue | green | amber | red | violet."""
    tone = tone if tone in TONES else "neutral"
    dot_html = '<span class="ai-dot" aria-hidden="true"></span>' if dot else ""
    title_attr = f' title="{esc(title)}"' if title else ""
    return f'<span class="ai-chip ai-chip--{tone}"{title_attr}>{dot_html}{esc(text)}</span>'


def render(content: str, *, width="stretch") -> None:
    """Render trusted markup built from esc()/chip(). Never pass raw user text here."""
    st.html(content, width=width)


def page_header(title: str, subtitle: str = "", eyebrow: str = "") -> None:
    eyebrow_html = f'<div class="ai-eyebrow">{esc(eyebrow)}</div>' if eyebrow else ""
    sub_html = f'<p class="ai-page-sub">{esc(subtitle)}</p>' if subtitle else ""
    render(f'<div class="ai-page-head">{eyebrow_html}<h1 class="ai-page-title">{esc(title)}</h1>{sub_html}</div>')


def section_title(title: str, subtitle: str = "", right_html: str = "") -> None:
    """Card heading row. right_html must already be escaped markup (e.g. chip())."""
    sub_html = f'<p class="ai-section-sub">{esc(subtitle)}</p>' if subtitle else ""
    right = f'<div class="ai-section-right">{right_html}</div>' if right_html else ""
    render(f'<div class="ai-section-head"><div><h2 class="ai-section-title">{esc(title)}</h2>'
           f'{sub_html}</div>{right}</div>')


def bullet_list(items, *, cls: str = "ai-list") -> str:
    return f'<ul class="{cls}">' + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>"
