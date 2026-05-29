"""Typed view state for the QCM Panel UI."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

_US = 1_000_000


@dataclass(frozen=True)
class RunInfo:
    """Stable facts about a run used by controls and page headers."""

    run_id: str
    groups: list[int]
    orders: dict[int, int]
    t0_us: int
    t1_us: int
    span_s: float
    fmin: float
    fmax: float
    seq_min: int
    seq_max: int
    n_sweeps: int
    rows: int | str = "?"
    has_echem: bool = False


@dataclass(frozen=True)
class ViewState:
    """Complete UI state needed to render plots/tables/export data."""

    groups: list[int]
    quantity: str  # selected y-axis quantity key
    x_axis: str  # selected x-axis dimension key (see theme.AXES)
    t_range_s: tuple[float, float]
    baseline_s: tuple[float, float]
    orders: dict[int, int]
    orders_text: str
    sequence: int
    single_group: int
    sweep_mode: str
    frequency_band: tuple[float, float]
    annotation_label: str = ""
    annotation_version: int = 0
    overtone_controls: dict[str, dict[str, bool]] = field(default_factory=dict)

    def t_us(self, t0_us: int) -> tuple[int, int]:
        start, end = self.t_range_s
        return int(t0_us + start * _US), int(t0_us + end * _US)

    def baseline_us(self, t0_us: int) -> tuple[int, int]:
        start, end = self.baseline_s
        return int(t0_us + start * _US), int(t0_us + end * _US)

    def selected_sweep_groups(self) -> list[int]:
        if self.sweep_mode == "single group":
            return [int(self.single_group)]
        return list(self.groups)

    def to_persisted_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["t_range_s"] = list(self.t_range_s)
        data["baseline_s"] = list(self.baseline_s)
        data["frequency_band"] = list(self.frequency_band)
        data.pop("annotation_label", None)
        data.pop("annotation_version", None)
        return data


def parse_orders(text: str, defaults: dict[int, int], groups: list[int]) -> dict[int, int]:
    """Parse ``g0:n=1, g1:n=3`` style text into a complete order map."""
    parsed: dict[int, int] = {}
    for chunk in text.replace(";", ",").split(","):
        if ":" not in chunk:
            continue
        g, _, n = chunk.partition(":")
        try:
            parsed[int(g.strip().lstrip("g"))] = max(1, int(n.strip().lstrip("n=")))
        except ValueError:
            continue
    return {g: parsed.get(g, defaults.get(g, 1)) for g in groups}
