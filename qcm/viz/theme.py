"""Display constants and the QCM quantity registry.

Centralizing this keeps units, labels, and the set of plottable quantities in
one place so plots and controls never disagree about what a column means.
"""
from __future__ import annotations

from dataclasses import dataclass

# --- look and feel -----------------------------------------------------------

ACCENT = "#7dd3fc"
HEADER_BG = "#0f172a"
PLOT_HEIGHT = 300
HERO_HEIGHT = 380

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


def color_for_slot(slot: int) -> str:
    """Stable color for the n-th selected overtone."""
    return OVERTONE_PALETTE[slot % len(OVERTONE_PALETTE)]


@dataclass(frozen=True)
class Quantity:
    """A plottable physical quantity derived from the sweep-fit columns."""

    key: str
    label: str
    unit: str
    kind: str  # "frequency" | "dissipation" | "mass" | "ratio" | "raw"
    referenced: bool  # subtract the per-group baseline-window mean
    normalized: bool  # divide by the overtone order n
    sources: tuple[str, ...]  # raw timeline columns required

    @property
    def axis_label(self) -> str:
        return f"{self.label} [{self.unit}]" if self.unit else self.label


# Registry. Order matters: it drives the selector option order.
QUANTITIES: dict[str, Quantity] = {
    q.key: q
    for q in [
        Quantity("delta_f_norm", "Δf / n", "Hz", "frequency", True, True, ("fit_center",)),
        Quantity("delta_D", "ΔD", "×10⁻⁶", "dissipation", True, False, ("fit_center", "fit_fwhm")),
        Quantity("sauerbrey_mass", "Areal mass (Sauerbrey)", "ng/cm²", "mass", True, True, ("fit_center",)),
        Quantity("delta_f", "Δf (not normalized)", "Hz", "frequency", True, False, ("fit_center",)),
        Quantity("dissipation", "Dissipation D", "×10⁻⁶", "dissipation", False, False, ("fit_center", "fit_fwhm")),
        Quantity("fit_center", "Resonance f (absolute)", "Hz", "raw", False, False, ("fit_center",)),
        Quantity("quality_factor", "Quality factor Q", "", "ratio", False, False, ("fit_center", "fit_fwhm")),
        Quantity("fit_fwhm", "FWHM (Γ·2)", "Hz", "raw", False, False, ("fit_fwhm",)),
        Quantity("fit_gamma", "HWHM (Γ)", "Hz", "raw", False, False, ("fit_gamma",)),
    ]
}

def quantity(key: str) -> Quantity:
    return QUANTITIES[key]
