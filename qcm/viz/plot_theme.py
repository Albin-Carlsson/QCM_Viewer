"""A shared Bokeh document theme so plots match the UI chrome.

Applied once at app startup via ``apply()``. Plot-building code in ``plots.py``
is not modified; this only sets document-level visual defaults.
"""
from __future__ import annotations

from bokeh.themes import Theme

_FONT = '"Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'

QCM_BOKEH_THEME = Theme(
    json={
        "attrs": {
            "Plot": {"background_fill_color": "#ffffff", "border_fill_color": "#ffffff", "outline_line_color": None},
            "Axis": {
                "axis_label_text_font": _FONT,
                "axis_label_text_font_style": "normal",
                "axis_label_text_color": "#475569",
                "major_label_text_font": _FONT,
                "major_label_text_color": "#64748b",
                "axis_line_color": "#cbd5e1",
                "major_tick_line_color": "#cbd5e1",
                "minor_tick_line_color": None,
            },
            "Grid": {"grid_line_color": "#eef2f7"},
            "Legend": {
                "label_text_font": _FONT,
                "label_text_color": "#334155",
                "border_line_color": "#e2e8f0",
                "background_fill_alpha": 0.85,
            },
            "Title": {"text_font": _FONT, "text_color": "#0f172a", "text_font_style": "bold"},
        }
    }
)


def apply() -> None:
    """Make the QCM theme the active Bokeh/HoloViews document theme."""
    import holoviews as hv

    hv.renderer("bokeh").theme = QCM_BOKEH_THEME
