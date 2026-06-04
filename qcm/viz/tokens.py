"""Single source of truth for the QCM viewer's visual identity.

Scientific minimalism: white surfaces, hairline borders, one blue action color,
instrument-dense spacing, a sans UI typeface, and a monospace face for every
numeric readout so figures align in columns.

Everything visual derives from the dictionaries below:

- ``root_css()`` renders the CSS ``:root { --qcm-* }`` custom-property block that
  ``design.py`` prepends to the app stylesheet. UI chrome reads those variables.
- The module-level Python constants (``ACCENT``, ``INK``, ``MONO``,
  ``PHASE_COLORS``, the plot heights, …) feed Bokeh/HoloViews plot code, which
  cannot read CSS variables. ``theme.py`` re-exports them for back-compat.

This module is the *only* place that holds raw hex. If a color appears anywhere
else under ``qcm/viz``, it has drifted from the system.
"""
from __future__ import annotations

# --- palette ---------------------------------------------------------------
# Keyed by the CSS token suffix (``bg`` -> ``--qcm-bg``). Order is preserved in
# the rendered :root block.
COLORS: dict[str, str] = {
    "bg": "#f4f6f9",            # app canvas behind the surfaces
    "surface": "#ffffff",       # cards, sidebar, topbar
    "surface-muted": "#f5f7fa", # table stripes, inset fills
    "border": "#e4e8ee",        # hairline dividers
    "border-strong": "#cbd3dd", # input borders, axis lines
    "text": "#0f172a",          # ink
    "text-soft": "#334155",
    "muted": "#64748b",
    "faint": "#94a3b8",
    "accent": "#2563eb",        # the one action color
    "accent-strong": "#1d4ed8", # hover
    "accent-active": "#1e40af", # pressed
    "accent-soft": "#eff6ff",
    "on-accent": "#ffffff",     # text/icon on a filled accent surface
    "success": "#16a34a",
    "warning": "#d97706",
    "danger": "#dc2626",
    "violet": "#7c3aed",        # data only (phase palette) — never UI chrome
    # Tonal fills / borders for the accent + status states (soft backgrounds).
    "accent-border": "#bfdbfe",
    "success-soft": "#ecfdf5",
    "warning-soft": "#fffbeb",
    "warning-border": "#fde68a",
    "warning-text": "#92400e",
    "danger-soft": "#fef2f2",
    "violet-soft": "#f5f3ff",
}

# --- spacing / shape -------------------------------------------------------
# 4px grid. Everything is a multiple of 4.
SPACE: dict[str, str] = {
    "1": "4px", "2": "8px", "3": "12px", "4": "16px", "5": "24px", "6": "32px",
}
# Role-based radius (not a t-shirt scale): every element picks by its role.
RADIUS: dict[str, str] = {"control": "8px", "card": "10px", "pill": "999px", "sm": "6px"}
# Two elevation levels only. Level 0 = border. Level 1 = these (floating chrome).
SHADOW: dict[str, str] = {
    "1": "0 1px 2px rgba(15, 23, 42, 0.06)",
    "2": "0 16px 40px rgba(15, 23, 42, 0.12)",
}
# Layout + control sizing.
LAYOUT: dict[str, str] = {
    "sidebar-w": "232px",
    "rail-w": "320px",      # unified across Data / Results / Report
    "control-h": "34px",    # every button/input/select shares this height
    "header-h": "40px",     # card header height
}

# --- typography ------------------------------------------------------------
FONT = '"Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'
MONO = '"IBM Plex Mono", "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace'
# Absolute px sizes keyed by role (see the design system doc, §5).
TYPE: dict[str, str] = {
    "fs-display": "18px",
    "fs-title": "14px",
    "fs-eyebrow": "11px",
    "fs-label": "12px",
    "fs-body": "13px",     # base body size
    "fs-value": "15px",
    "fs-value-lg": "18px",
    "fs-caption": "11px",
}
# Misc tokens that aren't a single color/size.
EXTRA: dict[str, str] = {
    "ring": "0 0 0 3px rgba(37, 99, 235, 0.30)",  # focus ring
    "motion": "120ms ease",
    "scrim": "rgba(15, 23, 42, 0.40)",            # drawer/modal backdrop
}


def root_css() -> str:
    """Render the ``:root`` custom-property block from the token tables."""
    lines = ["  color-scheme: light only;"]
    lines += [f"  --qcm-{name}: {value};" for name, value in COLORS.items()]
    lines += [f"  --qcm-space-{k}: {v};" for k, v in SPACE.items()]
    lines += [f"  --qcm-radius-{k}: {v};" for k, v in RADIUS.items()]
    lines += [f"  --qcm-shadow-{k}: {v};" for k, v in SHADOW.items()]
    lines += [f"  --qcm-{k}: {v};" for k, v in LAYOUT.items()]
    lines += [f"  --qcm-{k}: {v};" for k, v in TYPE.items()]
    lines += [f"  --qcm-{k}: {v};" for k, v in EXTRA.items()]
    lines += [f"  --qcm-font: {FONT};", f"  --qcm-mono: {MONO};"]
    body = "\n".join(lines)
    return f":root {{\n{body}\n}}"


# --- Python constants for plot code (no CSS variables in Bokeh) ------------
ACCENT = COLORS["accent"]
ACCENT_STRONG = COLORS["accent-strong"]
INK = COLORS["text"]
INK_SOFT = COLORS["text-soft"]
MUTED = COLORS["muted"]
FAINT = COLORS["faint"]
SURFACE = COLORS["surface"]
AXIS_LINE = COLORS["border-strong"]
# Dark fill behind floating plot annotation labels.
HEADER_BG = COLORS["text"]
# Grid lines sit lighter than the hairline border so they recede.
GRID = "#eef2f7"

# --- plot sizing (kept here so pages stay consistent) ----------------------
HERO_HEIGHT = 380           # full-run QCM-D overview/reference plots
PLOT_HEIGHT = 340           # main analysis timelines
COMPACT_PLOT_HEIGHT = 220   # secondary/fingerprint plots
RESULTS_PLOT_HEIGHT = 420   # the single headline plot on the Results page
SWEEP_PANEL_HEIGHT = 260    # one raw sweep panel
WATERFALL_PANEL_HEIGHT = 320

SECTION_GAP = 8
CARD_PADDING = 8

# --- data colors -----------------------------------------------------------
# Reference-region (baseline) and event annotation colors.
BASELINE_COLOR = "#22c55e"
EVENT_COLOR = "#f97316"
# Faint band/boundary marking cycles on a time plot.
CYCLE_BAND_COLOR = MUTED

# Semantic phase/region palette (data, not chrome). Mirrors the region types in
# controls.py. Kept distinct and colorblind-aware.
PHASE_COLORS: dict[str, str] = {
    "baseline": BASELINE_COLOR,
    "phase": COLORS["violet"],
    "buffer": "#0ea5e9",
    "sample": "#f59e0b",
    "regeneration": "#ec4899",
    "artifact": "#ef4444",
    "exclude": MUTED,
    "note": "#14b8a6",
}
PHASE_DEFAULT = COLORS["violet"]

# Colorblind-safe line colors (Wong palette) assigned by overtone slot.
OVERTONE_PALETTE = [
    "#56b4e9",  # sky blue
    "#e69f00",  # orange
    "#009e73",  # bluish green
    "#cc79a7",  # reddish purple
    "#f0e442",  # yellow
    "#0072b2",  # blue
    "#d55e00",  # vermillion
    "#999999",  # grey
]


def color_for_slot(slot: int) -> str:
    """Stable color for the n-th selected overtone."""
    return OVERTONE_PALETTE[slot % len(OVERTONE_PALETTE)]
