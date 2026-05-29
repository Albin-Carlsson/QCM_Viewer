"""Pure navigation and guidance logic for the workbench.

The viewer is organized as three top-level *modes* — Data (explore &
visualize), Results (mass/charge/MPE dashboard), and Report (export). The older
six-step "focus" model is kept as ``STEPS`` plus its helpers so existing tests
and the QC drawer keep working, but the shell now drives everything from
``MODES``.

No Panel imports: everything here is unit-testable plain Python.
"""
from __future__ import annotations

from dataclasses import dataclass

_EPS = 1e-9


# --------------------------------------------------------------------- modes
@dataclass(frozen=True)
class Mode:
    id: str
    label: str
    sublabel: str
    icon: str  # Tabler icon name (used by the sidebar buttons)


MODES: tuple[Mode, ...] = (
    Mode("data", "Data", "Explore & visualize", "chart-line"),
    Mode("results", "Results", "Mass, charge, MPE", "chart-histogram"),
    Mode("report", "Report", "Export & report", "file-text"),
)


def clamp_mode(index: int) -> int:
    return max(0, min(len(MODES) - 1, int(index)))


def mode_id(index: int) -> str:
    return MODES[clamp_mode(index)].id


def mode_index(mode_key: str) -> int:
    for i, mode in enumerate(MODES):
        if mode.id == mode_key:
            return i
    return 0


# ------------------------------------------------------------- legacy steps
@dataclass(frozen=True)
class Step:
    id: str
    label: str


STEPS: tuple[Step, ...] = (
    Step("review", "Overview"),
    Step("reference", "Reference"),
    Step("phases", "Phases"),
    Step("quantify", "Quantify"),
    Step("echem", "Electrochemistry"),
    Step("report", "Report"),
)

_BRUSH_BY_STEP = {
    "review": "current",
    "reference": "reference",
    "phases": "mark",
    "quantify": "current",
    "echem": "current",
    "report": "current",
}


def clamp_step(index: int) -> int:
    return max(0, min(len(STEPS) - 1, int(index)))


def step_id(index: int) -> str:
    return STEPS[clamp_step(index)].id


def next_step(index: int) -> int:
    return clamp_step(index + 1)


def prev_step(index: int) -> int:
    return clamp_step(index - 1)


def brush_target_for_step(step_key: str) -> str:
    """Which range a plot box-drag should set, given the active step."""
    return _BRUSH_BY_STEP.get(step_key, "current")


# ----------------------------------------------------------------- guidance
def needs_reference_hint(
    quantity_referenced: bool,
    baseline_s: tuple[float, float],
    span_s: float,
) -> bool:
    """True when a Δ quantity is selected but no real reference window is set.

    "No real reference" means the reference range still spans the whole run.
    """
    if not quantity_referenced:
        return False
    lo, hi = baseline_s
    return abs(float(lo)) < _EPS and abs(float(hi) - float(span_s)) < _EPS
