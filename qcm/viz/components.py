"""Token-driven, reusable Panel UI building blocks for the QCM shell/steps.

Presentational only. HTML-returning helpers escape user/data text; ``hint``
intentionally trusts its caller so step code can pass inline markup.
"""
from __future__ import annotations

from html import escape

import panel as pn

# --------------------------------------------------------------------- icons
# Small inline line-icons (24px, stroke=currentColor) so HTML cards can carry a
# glyph without a webfont. Keyed by quantity family + a few UI roles.
_ICONS: dict[str, str] = {
    "frequency": "<path d='M3 12h3l3 8 4-16 3 8h5'/>",
    "dissipation": "<path d='M12 3c3 4 5 6.5 5 9a5 5 0 0 1-10 0c0-2.5 2-5 5-9z'/>",
    "mass": "<path d='M12 4v16M5 8h14M7 8l-3 6h6zM17 8l-3 6h6z'/>",
    "charge": "<path d='M13 3 4 14h6l-1 7 9-11h-6z'/>",
    "mpe": "<circle cx='12' cy='12' r='2.2'/><ellipse cx='12' cy='12' rx='9' ry='3.6'/>"
           "<ellipse cx='12' cy='12' rx='9' ry='3.6' transform='rotate(60 12 12)'/>"
           "<ellipse cx='12' cy='12' rx='9' ry='3.6' transform='rotate(120 12 12)'/>",
    "density": "<path d='M9 3h6M10 3v5l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3'/>",
    "ratio": "<path d='M5 19 19 5M8 7.5a1.5 1.5 0 1 0 0-.001M16 16.5a1.5 1.5 0 1 0 0-.001'/>",
    "time": "<circle cx='12' cy='12' r='8'/><path d='M12 8v4l3 2'/>",
    "info": "<circle cx='12' cy='12' r='9'/><path d='M12 11v5M12 8h.01'/>",
}


def _svg(name: str) -> str:
    body = _ICONS.get(name, _ICONS["info"])
    return (
        "<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' "
        "stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round' "
        f"aria-hidden='true'>{body}</svg>"
    )


# --------------------------------------------------------------------- base
def _html(markup: str, *, css_classes: list[str] | None = None) -> pn.pane.HTML:
    return pn.pane.HTML(markup, margin=0, sizing_mode="stretch_width", css_classes=css_classes or [])


def section_title(title: str, eyebrow: str | None = None, *, action: str = "") -> pn.pane.HTML:
    eyebrow_html = f"<div class='eyebrow'>{escape(eyebrow)}</div>" if eyebrow else ""
    action_html = f"<div class='qcm-section-action'>{action}</div>" if action else ""
    return _html(
        "<div class='qcm-section-title-row'>"
        f"<div class='qcm-section-title'>{eyebrow_html}<h2>{escape(title)}</h2></div>"
        f"{action_html}</div>"
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


def card(*objects: pn.viewable.Viewable, title: str | None = None, collapsible: bool = False,
         collapsed: bool = False, css_classes: list[str] | None = None) -> pn.Card:
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


def toolbar(*objects: pn.viewable.Viewable) -> pn.Row:
    return pn.Row(*objects, margin=0, sizing_mode="stretch_width", css_classes=["qcm-toolbar"])


# ----------------------------------------------------------- redesign atoms
def brand(title: str = "QCM-D Viewer") -> pn.pane.HTML:
    """The product wordmark shown at the top of the sidebar."""
    mark = _svg("frequency")
    return _html(
        f"<div class='qcm-brand'><span class='qcm-brand-mark'>{mark}</span>"
        f"<span class='qcm-brand-name'>{escape(title)}</span></div>"
    )


def nav_sublabel(text: str) -> pn.pane.HTML:
    return _html(f"<div class='qcm-nav-sub'>{escape(text)}</div>")


def icon_stat(label: str, value: str, *, icon: str = "info", tone: str = "neutral",
              caption: str = "") -> str:
    """Return an HTML icon-stat cell (used inside a ``stat_grid``)."""
    safe_tone = tone if tone in {"accent", "success", "warning", "danger", "neutral"} else "neutral"
    cap = f"<div class='caption'>{escape(caption)}</div>" if caption else ""
    return (
        f"<div class='qcm-iconstat {safe_tone}'>"
        f"<div class='qcm-iconstat-icon'>{_svg(icon)}</div>"
        "<div class='qcm-iconstat-body'>"
        f"<div class='label'>{escape(label)}</div>"
        f"<div class='value'>{escape(value)}</div>{cap}</div></div>"
    )


def stat_grid(cells: list[str]) -> pn.pane.HTML:
    """Lay a list of ``icon_stat`` HTML cells into a responsive grid."""
    return _html(f"<div class='qcm-statgrid'>{''.join(cells)}</div>")


def run_info_table(rows: list[tuple[str, str]]) -> pn.pane.HTML:
    """A compact key/value table for the sidebar Run-info card."""
    body = "".join(
        "<div class='qcm-kv'>"
        f"<span class='k'>{escape(k)}</span>"
        f"<span class='v'>{escape(v)}</span></div>"
        for k, v in rows
    )
    return _html(f"<div class='qcm-kvtable'>{body}</div>")


def phase_row(color: str, name: str, time_range: str) -> str:
    """One colored-dot phase entry for the right-rail Phases card."""
    return (
        "<div class='qcm-phase-row'>"
        f"<span class='qcm-phase-dot' style='background:{escape(color)}'></span>"
        f"<span class='qcm-phase-name'>{escape(name)}</span>"
        f"<span class='qcm-phase-time'>{escape(time_range)}</span></div>"
    )


def phase_list(rows: list[str]) -> pn.pane.HTML:
    if not rows:
        return empty_state("No phases saved yet.")
    return _html(f"<div class='qcm-phase-list'>{''.join(rows)}</div>")


def selection_chip(label: str, value: str, *, tone: str = "accent") -> pn.pane.HTML:
    return _html(
        f"<div class='qcm-selchip {escape(tone)}'>"
        f"<span class='k'>{escape(label)}</span>"
        f"<span class='v'>{escape(value)}</span></div>"
    )


def metric_definitions(items: list[tuple[str, str]]) -> pn.pane.HTML:
    """A small glossary card ('Metrics explanation') for the Results page."""
    body = "".join(
        "<div class='qcm-def'>"
        f"<span class='term'>{escape(term)}</span>"
        f"<span class='desc'>{escape(desc)}</span></div>"
        for term, desc in items
    )
    return _html(f"<div class='qcm-defs'>{body}</div>")
