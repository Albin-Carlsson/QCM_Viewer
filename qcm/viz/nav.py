"""Pure navigation and guidance logic for the stepper shell.

No Panel imports: everything here is unit-testable plain Python.
"""
from __future__ import annotations

from dataclasses import dataclass

_EPS = 1e-9


@dataclass(frozen=True)
class Step:
    id: str
    label: str


STEPS: tuple[Step, ...] = (
    Step("review", "Overview"),
    Step("reference", "Reference"),
    Step("phases", "Phases"),
    Step("quantify", "Quantify"),
    Step("report", "Report"),
)

_BRUSH_BY_STEP = {
    "review": "current",
    "reference": "reference",
    "phases": "mark",
    "quantify": "current",
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
