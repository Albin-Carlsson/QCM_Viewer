"""Display constants and the QCM quantity registry.

Centralizing this keeps units, labels, and the set of plottable quantities in
one place so plots and controls never disagree about what a column means.
"""
from __future__ import annotations

from dataclasses import dataclass

# --- look and feel -----------------------------------------------------------

ACCENT = "#2563eb"
HEADER_BG = "#0f172a"
# Standardized plot sizing. Keep all plot dimensions here so pages stay consistent.
HERO_HEIGHT = 440          # full-run QCM-D overview/reference plots; compact enough for one-screen pages
PLOT_HEIGHT = 340           # main analysis timelines
COMPACT_PLOT_HEIGHT = 220   # secondary/fingerprint plots
SWEEP_PANEL_HEIGHT = 260    # one raw sweep panel
WATERFALL_PANEL_HEIGHT = 320

# Compact workbench spacing
SECTION_GAP = 8
CARD_PADDING = 8

# Max points sent to the browser *per line*. Pyramid frames can carry tens of
# thousands of points per group when the sweep rate is high; a plot is ~1200px
# wide, so anything beyond a couple thousand points per curve only slows Bokeh's
# redraw without adding visible detail. Curves are decimated with a min/max
# envelope (see plots._decimate_xy) so spikes/artifacts survive the downsample.
MAX_PLOT_POINTS = 2000

# Reference-region (baseline) and event annotation colors.
BASELINE_COLOR = "#22c55e"
EVENT_COLOR = "#f97316"

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

# Dissipation is dimensionless; QCM-D convention reports it in units of 1e-6.
DISSIPATION_SCALE = 1e6

# Sauerbrey constant (ng cm^-2 Hz^-1) for an AT-cut 5 MHz crystal.
SAUERBREY_CONSTANT = 17.7

# Faraday constant (C/mol) and electrode area (cm²) for the electrochemical
# (EQCM) channel. The area converts current to current density and areal mass to
# total mass for the mass-per-electron (MPE) Faraday slope.
FARADAY_CONSTANT = 96_485.332_12
ELECTRODE_AREA_CM2 = 1.0


def color_for_slot(slot: int) -> str:
    """Stable color for the n-th selected overtone."""
    return OVERTONE_PALETTE[slot % len(OVERTONE_PALETTE)]


@dataclass(frozen=True)
class Quantity:
    """A plottable physical quantity derived from the sweep-fit columns."""

    key: str
    label: str
    unit: str
    # "frequency" | "dissipation" | "mass" | "ratio" | "raw"  (QCM resonance family)
    # "echem" | "echem_density" | "mpe"                        (electrochemistry family)
    kind: str
    referenced: bool  # subtract the per-group baseline-window mean
    normalized: bool  # divide by the overtone order n
    sources: tuple[str, ...]  # raw timeline columns required

    @property
    def axis_label(self) -> str:
        return f"{self.label} [{self.unit}]" if self.unit else self.label

    @property
    def is_echem(self) -> bool:
        """True for cell-level electrochemistry quantities (shared across overtones)."""
        return self.kind in ("echem", "echem_density")

    @property
    def is_resonance(self) -> bool:
        """True for QCM resonance quantities (one curve per overtone)."""
        return self.kind in ("frequency", "dissipation", "mass", "ratio", "raw")


# Registry. Order matters: it drives the selector option order.
QUANTITIES: dict[str, Quantity] = {
    q.key: q
    for q in [
        Quantity("delta_f", "Δf", "Hz", "frequency", True, False, ("fit_center",)),
        Quantity("delta_f_norm", "Δf / n", "Hz", "frequency", True, True, ("fit_center",)),
        Quantity("delta_D", "ΔD", "×10⁻⁶", "dissipation", True, False, ("fit_center", "fit_fwhm")),
        Quantity("sauerbrey_mass", "Mass", "ng/cm²", "mass", True, True, ("fit_center",)),
        # Electrochemistry channel. These are cell-level signals (identical across
        # overtones) read straight from the EQCM columns; MPE is derived.
        Quantity("current", "Current", "A", "echem", False, False, ("current",)),
        Quantity("current_density", "Current density", "A/cm²", "echem_density", False, False, ("current",)),
        Quantity("potential", "Potential", "V", "echem", False, False, ("potential",)),
        Quantity("charge", "Charge", "C", "echem", False, False, ("charge",)),
        Quantity("mpe", "Mass per electron (MPE)", "g/mol", "mpe", True, True, ("fit_center", "charge")),
        # Extra QCM quantities kept selectable for power users.
        Quantity("dissipation", "Dissipation D", "×10⁻⁶", "dissipation", False, False, ("fit_center", "fit_fwhm")),
        Quantity("quality_factor", "Quality factor Q", "", "ratio", False, False, ("fit_center", "fit_fwhm")),
        Quantity("fit_center", "Resonance f (absolute)", "Hz", "raw", False, False, ("fit_center",)),
        Quantity("fit_fwhm", "FWHM (Γ·2)", "Hz", "raw", False, False, ("fit_fwhm",)),
        Quantity("fit_gamma", "HWHM (Γ)", "Hz", "raw", False, False, ("fit_gamma",)),
    ]
}

def quantity(key: str) -> Quantity:
    return QUANTITIES[key]


@dataclass(frozen=True)
class Axis:
    """A selectable x-axis dimension for the analysis plot.

    ``source`` is the raw timeline column the axis reads. ``time`` is special: it
    maps to the elapsed-seconds column the data service derives, not a stored
    column. ``monotonic`` marks axes whose values increase with the row order so
    decimation can use the time-style min/max envelope; non-monotonic axes (a CV
    potential sweep, charge that reverses sign, per-cycle time) are decimated with
    a plain stride instead.
    """

    key: str
    label: str
    unit: str
    source: str
    monotonic: bool

    @property
    def axis_label(self) -> str:
        return f"{self.label} [{self.unit}]" if self.unit else self.label

    @property
    def is_time(self) -> bool:
        return self.key == "time"


# The elapsed-seconds column derived by the data service for time-domain plots.
ELAPSED_COLUMN = "elapsed_s"

# Registry of x-axis options. Order drives the selector.
AXES: dict[str, Axis] = {
    a.key: a
    for a in [
        Axis("time", "Time", "s", ELAPSED_COLUMN, True),
        Axis("potential", "Potential", "V", "potential", False),
        Axis("cycle_time", "Cycle time", "s", "cycle_time", False),
        Axis("cycle_number", "Cycle number", "", "cycle", True),
        Axis("charge", "Charge", "C", "charge", False),
    ]
}


def axis(key: str) -> Axis:
    return AXES.get(key, AXES["time"])
