"""Display constants and re-exports of the science quantity registry.

The science half (constants, ``ExperimentParams``, quantity/axis registries)
lives UI-free in :mod:`qcm.science.quantities` and is re-exported here so the
long-standing ``from .theme import …`` call sites keep working. The visual
identity lives in :mod:`qcm.viz.tokens` (the single source of truth) and is
re-exported the same way. What remains *defined* here is display policy only.
"""
from __future__ import annotations

from qcm.science.quantities import *  # noqa: F401,F403  (science re-export)
from .tokens import (  # noqa: F401  (look-and-feel re-export)
    ACCENT,
    BASELINE_COLOR,
    CARD_PADDING,
    COMPACT_PLOT_HEIGHT,
    EVENT_COLOR,
    HEADER_BG,
    HERO_HEIGHT,
    OVERTONE_PALETTE,
    PLOT_HEIGHT,
    RESULTS_PLOT_HEIGHT,
    SECTION_GAP,
    SWEEP_PANEL_HEIGHT,
    WATERFALL_PANEL_HEIGHT,
    color_for_run,
    color_for_run_overtone,
    color_for_slot,
)

# Max points sent to the browser *per line*. Pyramid frames can carry tens of
# thousands of points per group when the sweep rate is high; a plot is ~1200px
# wide, so anything beyond a couple thousand points per curve only slows Bokeh's
# redraw without adding visible detail. Curves are decimated with a min/max
# envelope (see plots._decimate_xy) so spikes/artifacts survive the downsample.
MAX_PLOT_POINTS = 2000

# Most cycles drawn as individual traces in a per-cycle echem plot. A long
# cycling run ("All" cycles) has hundreds; drawing each is unreadable spaghetti
# and slow, so an evenly spaced subset (always incl. first/last) represents the
# evolution. Explicit cycle/range selection is never thinned.
MAX_PLOTTED_CYCLES = 12

# Overtones shown by default on a fresh run. QCM-D practice reads n = 3, 5, 7:
# the fundamental couples to mounting/liquid artifacts and the high overtones
# mostly restate the middle ones (see the reference notebook, which plots
# exactly these three). Everything stays one click away in the channels list.
DEFAULT_VISIBLE_OVERTONES = (3, 5, 7)
