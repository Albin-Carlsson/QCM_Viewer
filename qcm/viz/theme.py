"""Display constants and the QCM quantity registry.

Centralizing this keeps units, labels, and the set of plottable quantities in
one place so plots and controls never disagree about what a column means.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# --- look and feel -----------------------------------------------------------
# The visual identity lives in tokens.py (the single source of truth). These are
# re-exported here so existing ``from .theme import …`` call sites keep working.
from .tokens import (  # noqa: F401  (re-export)
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

# --- science constants -------------------------------------------------------
# Dissipation is dimensionless; QCM-D convention reports it in units of 1e-6.
DISSIPATION_SCALE = 1e6

# Sauerbrey constant (ng cm^-2 Hz^-1) for an AT-cut 5 MHz crystal.
SAUERBREY_CONSTANT = 17.7

# Faraday constant (C/mol) and electrode area (cm²) for the electrochemical
# (EQCM) channel. The area converts current to current density and areal mass to
# total mass for the mass-per-electron (MPE) Faraday slope.
FARADAY_CONSTANT = 96_485.332_12
# Default working-electrode area: a disc of radius 0.6 cm (⌀ 12 mm), the standard
# EQCM sensor geometry. A wrong area silently scales areal mass, MPE, and current
# density, so the default matches the real cell rather than a bare 1 cm².
ELECTRODE_DISC_RADIUS_CM = 0.6
ELECTRODE_AREA_CM2 = math.pi * ELECTRODE_DISC_RADIUS_CM ** 2  # ≈ 1.1310 cm²

# Default deposited species for mass-per-electron: zinc (the lab's reference system).
DEFAULT_MOLAR_MASS_G_PER_MOL = 65.38
DEFAULT_VALENCY = 2

# Unit conversions used by the science layer.
NG_PER_CM2_TO_G = 1e-9          # areal mass (ng/cm²) × area(cm²) × this → grams
MM_PER_CM = 10.0               # cm → mm for the disc-diameter sanity cue

# Numerical guards (kept here so every consumer uses the same tolerances).
CHARGE_EPS_C = 1e-15           # |Δq| below this ⇒ MPE undefined (avoid /0)
FREQ_EPS_HZ = 1e-12            # |Δf/n| below this ⇒ viscoelastic ratio undefined
AREA_MIN_CM2 = 1e-6           # smallest meaningful electrode area

# Technique auto-detection: galvanostatic CP holds |I| nearly constant, so a low
# coefficient of variation marks CP; anything noisier/sign-changing reads as CV.
CP_CURRENT_COV_THRESHOLD = 0.5

# Mass-per-electron (MPE) display defaults. The dynamic MPE (Δf/ΔQ) spikes where
# the charge barely moves, so clipping is on by default to a physically generous
# band; smoothing is opt-in.
MPE_CLIP_LO_DEFAULT = -100.0   # g/mol
MPE_CLIP_HI_DEFAULT = 150.0    # g/mol
MPE_SMOOTH_WINDOW_DEFAULT = 51 # Savitzky–Golay window (samples, auto-shrunk to odd ≤ n)
MPE_SAVGOL_POLYORDER = 2
# Hampel despike of the resonance traces (f/D spikes from relay switching,
# bubbles, brief fit glitches). Threshold is in robust sigmas (MAD-scaled).
DESPIKE_WINDOW_DEFAULT = 7
DESPIKE_THRESHOLD_SIGMA = 5.0


def area_to_diameter_mm(area_cm2: float) -> float:
    """Diameter (mm) of the disc with this area — a sanity cue for the area field."""
    try:
        return 2.0 * math.sqrt(max(0.0, float(area_cm2)) / math.pi) * MM_PER_CM
    except (TypeError, ValueError):
        return 0.0


@dataclass(frozen=True)
class ExperimentParams:
    """Editable per-run experiment parameters for mass/MPE calculations.

    These replace hardcoded science constants so a run can describe its own
    sensor and deposited species:

    - ``area_cm2``: electrode area (cm²); converts areal mass to total mass and
      current to current density.
    - ``sensitivity``: Sauerbrey integral sensitivity (ng cm⁻² Hz⁻¹). Drives both
      Sauerbrey areal mass and the MPE mass term so the two stay consistent.
    - ``molar_mass``: molar mass M of the deposited species (g/mol).
    - ``valency``: number of electrons z transferred per deposited atom.

    The theoretical mass-per-electron target is ``M / z`` (g/mol) — e.g. zinc
    (65.38 / 2 = 32.69).
    """

    area_cm2: float = ELECTRODE_AREA_CM2
    sensitivity: float = SAUERBREY_CONSTANT
    molar_mass: float = DEFAULT_MOLAR_MASS_G_PER_MOL
    valency: int = DEFAULT_VALENCY

    @property
    def target_mpe(self) -> float | None:
        """Theoretical MPE (g/mol) = molar mass / valency, or None if z is 0."""
        return self.molar_mass / self.valency if self.valency else None

    def to_dict(self) -> dict:
        return {
            "area_cm2": self.area_cm2,
            "sensitivity": self.sensitivity,
            "molar_mass": self.molar_mass,
            "valency": self.valency,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "ExperimentParams":
        """Build params from a (possibly partial) persisted dict, ignoring junk."""
        if not isinstance(data, dict):
            return cls()
        d = cls()
        try:
            return cls(
                area_cm2=float(data.get("area_cm2", d.area_cm2)),
                sensitivity=float(data.get("sensitivity", d.sensitivity)),
                molar_mass=float(data.get("molar_mass", d.molar_mass)),
                valency=int(data.get("valency", d.valency)),
            )
        except (TypeError, ValueError):
            return d


DEFAULT_PARAMS = ExperimentParams()


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
