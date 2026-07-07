"""A shared Bokeh document theme so plots match the UI chrome.

Applied once at app startup via ``apply()``. Plot-building code in ``plots.py``
is not modified; this only sets document-level visual defaults.
"""
from __future__ import annotations

from bokeh.themes import Theme

from .tokens import (
    AXIS_LINE,
    COLORS,
    FONT,
    INK,
    INK_SOFT,
    GRID,
    MONO,
    MUTED,
    SURFACE,
    UI_SCALE,
)


def _fs(px: int) -> str:
    """A Bokeh font-size string scaled by UI_SCALE, matching the chrome's type."""
    return f"{max(1, round(px * UI_SCALE))}px"


# Derived from tokens.py so plots match the UI chrome. Tick labels use the
# monospace face so plot numerics align with the readouts in the panels. Font
# sizes are scaled by UI_SCALE (these equal Bokeh's defaults at scale 1.0) so
# plot text shrinks in lockstep with the rest of the interface.
QCM_BOKEH_THEME = Theme(
    json={
        "attrs": {
            "Plot": {"background_fill_color": SURFACE, "border_fill_color": SURFACE, "outline_line_color": None},
            "Axis": {
                "axis_label_text_font": FONT,
                "axis_label_text_font_style": "normal",
                "axis_label_text_color": INK_SOFT,
                "axis_label_text_font_size": _fs(13),
                "major_label_text_font": MONO,
                "major_label_text_color": MUTED,
                "major_label_text_font_size": _fs(11),
                "axis_line_color": AXIS_LINE,
                "major_tick_line_color": AXIS_LINE,
                "minor_tick_line_color": None,
            },
            "Grid": {"grid_line_color": GRID},
            "Legend": {
                "label_text_font": FONT,
                "label_text_color": INK_SOFT,
                "label_text_font_size": _fs(12),
                "border_line_color": COLORS["border"],
                "background_fill_color": SURFACE,
                "background_fill_alpha": 0.94,
                "padding": 6,
                "spacing": 2,
            },
            "Title": {"text_font": FONT, "text_color": INK, "text_font_style": "bold",
                      "text_font_size": _fs(13)},
        }
    }
)


def apply() -> None:
    """Make the QCM theme the active Bokeh/HoloViews document theme."""
    import holoviews as hv

    hv.renderer("bokeh").theme = QCM_BOKEH_THEME
