"""Token-driven, reusable Panel UI building blocks for the QCM shell/steps.

Presentational only. HTML-returning helpers escape user/data text; ``hint``
intentionally trusts its caller so step code can pass inline markup.
"""
from __future__ import annotations

from html import escape

import panel as pn


def _html(markup: str, *, css_classes: list[str] | None = None) -> pn.pane.HTML:
    return pn.pane.HTML(markup, margin=0, sizing_mode="stretch_width", css_classes=css_classes or [])


def section_title(title: str, eyebrow: str | None = None) -> pn.pane.HTML:
    eyebrow_html = f"<div class='eyebrow'>{escape(eyebrow)}</div>" if eyebrow else ""
    return _html(
        f"<div class='qcm-section-title'>{eyebrow_html}<h2>{escape(title)}</h2></div>"
    )


def pill(label: str, value: str) -> str:
    """Return an inline HTML pill string (used to compose the context bar)."""
    return (
        "<div class='qcm-pill'>"
        f"<div class='label'>{escape(label)}</div>"
        f"<div class='value'>{escape(value)}</div>"
        "</div>"
    )


def stat_badge(label: str, value: str, caption: str = "", *, tone: str = "neutral") -> pn.pane.HTML:
    safe_tone = tone if tone in {"accent", "success", "warning", "danger", "neutral"} else "neutral"
    caption_html = f"<div class='caption'>{escape(caption)}</div>" if caption else ""
    return _html(
        f"<div class='qcm-stat {safe_tone}'>"
        f"<div class='label'>{escape(label)}</div>"
        f"<div class='value'>{escape(value)}</div>"
        f"{caption_html}</div>"
    )


def metric_strip(items: list[tuple[str, str, str]]) -> pn.pane.HTML:
    cells = "".join(
        "<div class='qcm-stat'>"
        f"<div class='label'>{escape(label)}</div>"
        f"<div class='value'>{escape(value)}</div>"
        + (f"<div class='caption'>{escape(caption)}</div>" if caption else "")
        + "</div>"
        for label, value, caption in items
    )
    return _html(f"<div class='qcm-metric-strip'>{cells}</div>")


def empty_state(text: str) -> pn.pane.HTML:
    return _html(f"<div class='qcm-empty'>{escape(text)}</div>")


def hint(markup: str, *, tone: str = "info") -> pn.pane.HTML:
    safe_tone = tone if tone in {"info", "warning"} else "info"
    return _html(f"<div class='qcm-hint {safe_tone}'>{markup}</div>")


def card(*objects, title: str | None = None, collapsible: bool = False, collapsed: bool = False,
         css_classes: list[str] | None = None) -> pn.Card:
    classes = ["qcm-card", *(css_classes or [])]
    return pn.Card(
        *objects,
        title=title or "",
        collapsible=collapsible,
        collapsed=collapsed,
        hide_header=title is None,
        margin=0,
        sizing_mode="stretch_width",
        css_classes=classes,
    )


def toolbar(*objects) -> pn.Row:
    return pn.Row(*objects, margin=0, sizing_mode="stretch_width", css_classes=["qcm-toolbar"])
