"""Panel controls for the simplified QCM viewer.

This module keeps the original public widget attributes used by the rest of the
viewer, but restructures the range UI around two explicit concepts:

- Current range: what is inspected, plotted, saved, and exported.
- Zero/reference range: what defines zero for referenced/Δ quantities.

The old ``EditableRangeSlider`` widgets exposed small inline number boxes that
were hard to scan and easy to confuse.  The replacement keeps a normal range
slider for fast interaction and adds labeled, unit-aware numeric inputs for
precise edits.
"""
from __future__ import annotations

from typing import Literal

import panel as pn

from .state import RunInfo, ViewState, parse_orders
from .theme import QUANTITIES, quantity

_QUANTITY_OPTIONS = {q.label: key for key, q in QUANTITIES.items()}
_REGION_TYPES = {
    "Experiment phase": "phase",
    "Baseline / reference": "baseline",
    "Buffer / rinse": "buffer",
    "Sample addition": "sample",
    "Regeneration": "regeneration",
    "Artifact / bad data": "artifact",
    "Exclude from analysis": "exclude",
    "Note / observation": "note",
}

_CHANNEL_TOGGLE_CSS = """
.bk-btn-group {
  display: grid !important;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)) !important;
  gap: 6px !important;
  width: 100% !important;
}
.bk-btn {
  width: 100% !important;
  justify-content: flex-start !important;
  text-align: left !important;
  white-space: normal !important;
  border: 1px solid #cbd5e1 !important;
  background-color: #ffffff !important;
  background-image: none !important;
  color: #475569 !important;
  opacity: 1 !important;
  box-shadow: none !important;
}
.bk-btn:hover {
  border-color: #94a3b8 !important;
  color: #0f172a !important;
}
.bk-btn.bk-active {
  border-color: #2563eb !important;
  background-color: #eff6ff !important;
  background-image: none !important;
  color: #1d4ed8 !important;
  opacity: 1 !important;
  font-weight: 700 !important;
  box-shadow: inset 3px 0 0 #2563eb !important;
}
"""

_RANGE_EDITOR_CSS = """
.range-editor-card {
  border-radius: 12px;
}
.range-editor-card .bk-card-header {
  font-weight: 700;
}
.range-number-row {
  gap: 8px !important;
}
.range-number-row .bk-input {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.range-duration {
  min-height: 34px;
  display: flex;
  align-items: center;
}
.range-actions {
  gap: 8px !important;
}
.quantity-context {
  border-left: 4px solid #2563eb;
  padding-left: 10px;
}
.controls-muted {
  color: #64748b;
}
"""


RangeKind = Literal["current", "reference", "mark"]
RangeEdge = Literal["start", "end"]


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _channel_label(slot: int, group: int, order: int) -> str:
    channel = f"Channel {slot + 1}"
    if order == 1:
        harmonic = "fundamental"
    else:
        harmonic = f"{_ordinal(order)} harmonic"
    return f"{channel} · {harmonic} (n={order}, group {group})"


class ViewerControls:
    """Owns widgets and converts them into a typed :class:`ViewState` snapshot.

    User-facing model:
    - Current range: the one time range used for plots, statistics, and exports.
    - Zero/reference range: optional helper for Δ quantities only.
    - Saved regions: named ranges or points shown on plots and reusable for notebook export.
    """

    def __init__(self, info: RunInfo, saved: dict):
        self.info = info
        self.saved = saved or {}
        self._last_baseline: tuple[float, float] | None = None
        self._syncing_ranges = False
        self._build_widgets()

    def _build_widgets(self) -> None:
        self._time_step = max(self.info.span_s / 10_000, 0.001)
        self._time_fmt = "0,0.000" if self.info.span_s >= 1000 else "0.000"
        group_options = {
            _channel_label(slot, g, self.info.orders.get(g, 1)): str(g)
            for slot, g in enumerate(self.info.groups)
        }
        self.group_options = group_options
        saved_groups = [str(g) for g in self.saved.get("groups", self.info.groups) if g in self.info.groups]
        default_orders = ", ".join(f"g{g}:n={n}" for g, n in sorted(self.info.orders.items()))

        self.group_select = pn.widgets.CheckButtonGroup(
            name="Visible channels",
            options=group_options,
            value=saved_groups or [str(g) for g in self.info.groups],
            button_type="default",
            orientation="vertical",
            sizing_mode="stretch_width",
            css_classes=["channel-toggles"],
            stylesheets=[_CHANNEL_TOGGLE_CSS],
        )
        self.group_select.param.watch(self._keep_one_channel_selected, "value")
        self.show_all_channels_button = pn.widgets.Button(
            name="Show all channels",
            button_type="default",
            icon="eye",
            sizing_mode="stretch_width",
        )
        self.show_all_channels_button.on_click(self.show_all_channels)

        current_default = self._clean_range(self.saved.get("t_range_s", [0.0, self.info.span_s]))
        reference_default = self._clean_range(
            self.saved.get("baseline_s", [0.0, min(self.info.span_s, self.info.span_s * 0.1)])
        )

        # Plain RangeSlider + explicit numeric inputs gives users both quick dragging
        # and precise entry without the cramped EditableRangeSlider boxes.
        self.t_range = pn.widgets.RangeSlider(
            name="Current range",
            start=0.0,
            end=self.info.span_s,
            value=current_default,
            step=self._time_step,
            format=self._time_fmt,
            sizing_mode="stretch_width",
        )
        self.t_range_start = pn.widgets.FloatInput(
            name="Start (s)",
            value=current_default[0],
            start=0.0,
            end=self.info.span_s,
            step=self._time_step,
            sizing_mode="stretch_width",
        )
        self.t_range_end = pn.widgets.FloatInput(
            name="End (s)",
            value=current_default[1],
            start=0.0,
            end=self.info.span_s,
            step=self._time_step,
            sizing_mode="stretch_width",
        )
        self.t_full_range_button = pn.widgets.Button(
            name="Full range",
            button_type="default",
            icon="arrows-maximize",
            sizing_mode="stretch_width",
        )
        self.t_full_range_button.on_click(self.set_full_current_range)

        self.baseline_range = pn.widgets.RangeSlider(
            name="Zero/reference range",
            start=0.0,
            end=self.info.span_s,
            value=reference_default,
            step=self._time_step,
            format=self._time_fmt,
            sizing_mode="stretch_width",
        )
        self.baseline_start = pn.widgets.FloatInput(
            name="Start (s)",
            value=reference_default[0],
            start=0.0,
            end=self.info.span_s,
            step=self._time_step,
            sizing_mode="stretch_width",
        )
        self.baseline_end = pn.widgets.FloatInput(
            name="End (s)",
            value=reference_default[1],
            start=0.0,
            end=self.info.span_s,
            step=self._time_step,
            sizing_mode="stretch_width",
        )
        self.baseline_full_range_button = pn.widgets.Button(
            name="Use full run as zero",
            button_type="default",
            icon="arrows-maximize",
            sizing_mode="stretch_width",
        )
        self.baseline_full_range_button.on_click(self.set_full_reference_range)

        self.mark_range = pn.widgets.RangeSlider(
            name="Mark range",
            start=0.0,
            end=self.info.span_s,
            value=current_default,
            step=self._time_step,
            format=self._time_fmt,
            sizing_mode="stretch_width",
        )
        self.mark_start = pn.widgets.FloatInput(
            name="Start (s)",
            value=current_default[0],
            start=0.0,
            end=self.info.span_s,
            step=self._time_step,
            sizing_mode="stretch_width",
        )
        self.mark_end = pn.widgets.FloatInput(
            name="End (s)",
            value=current_default[1],
            start=0.0,
            end=self.info.span_s,
            step=self._time_step,
            sizing_mode="stretch_width",
        )
        self.mark_full_range_button = pn.widgets.Button(
            name="Use full run",
            button_type="default",
            icon="arrows-maximize",
            sizing_mode="stretch_width",
        )
        self.mark_full_range_button.on_click(self.set_full_mark_range)

        self.t_range.param.watch(lambda event: self._sync_inputs_from_slider("current", event.new), "value")
        self.baseline_range.param.watch(lambda event: self._sync_inputs_from_slider("reference", event.new), "value")
        self.t_range_start.param.watch(lambda event: self._sync_slider_from_input("current", "start", event.new), "value")
        self.t_range_end.param.watch(lambda event: self._sync_slider_from_input("current", "end", event.new), "value")
        self.baseline_start.param.watch(lambda event: self._sync_slider_from_input("reference", "start", event.new), "value")
        self.baseline_end.param.watch(lambda event: self._sync_slider_from_input("reference", "end", event.new), "value")
        self.mark_range.param.watch(lambda event: self._sync_inputs_from_slider("mark", event.new), "value")
        self.mark_start.param.watch(lambda event: self._sync_slider_from_input("mark", "start", event.new), "value")
        self.mark_end.param.watch(lambda event: self._sync_slider_from_input("mark", "end", event.new), "value")

        self.range_status = pn.pane.Alert("", alert_type="warning", visible=False, sizing_mode="stretch_width")

        self.brush_mode = pn.widgets.RadioButtonGroup(
            name="Draw on plot",
            options={"Analysis range": "current", "Reference range": "reference", "Mark range": "mark"},
            value="current",
            button_type="primary",
            sizing_mode="stretch_width",
            css_classes=["range-mode-toggle", "draw-mode-toggle"],
        )

        self.quantity_select = pn.widgets.Select(
            name="Quantity",
            options=_QUANTITY_OPTIONS,
            value=self.saved.get("quantity", "sauerbrey_mass"),
            sizing_mode="stretch_width",
            css_classes=["compact-select", "quantity-select"],
        )

        self.sequence = pn.widgets.IntSlider(
            name="Sweep number",
            start=self.info.seq_min,
            end=max(self.info.seq_max, self.info.seq_min),
            value=int(self.saved.get("sequence", self.info.seq_min)),
            step=1,
            sizing_mode="stretch_width",
        )
        self.previous_sweep_button = pn.widgets.Button(
            name="Previous",
            button_type="default",
            icon="chevron-left",
            sizing_mode="stretch_width",
        )
        self.next_sweep_button = pn.widgets.Button(
            name="Next",
            button_type="default",
            icon="chevron-right",
            sizing_mode="stretch_width",
        )
        self.previous_sweep_button.on_click(self.previous_sweep)
        self.next_sweep_button.on_click(self.next_sweep)

        self.sweep_mode = pn.widgets.RadioButtonGroup(
            name="Show",
            options={
                "Selected channels": "selected overtones",
                "One channel": "single group",
            },
            value=self.saved.get("sweep_mode", "selected overtones"),
            button_type="primary",
            sizing_mode="stretch_width",
        )
        self.group_for_single = pn.widgets.Select(
            name="Single channel",
            options=group_options,
            value=str(self.saved.get("single_group", self.info.groups[0])),
            sizing_mode="stretch_width",
        )
        self.frequency_band = pn.widgets.EditableRangeSlider(
            name="Waterfall frequency band (Hz)",
            start=self.info.fmin,
            end=self.info.fmax,
            value=tuple(self.saved.get("frequency_band", [self.info.fmin, self.info.fmax])),
            step=max((self.info.fmax - self.info.fmin) / 20_000, 1e-6),
            format="0,0.000",
            sizing_mode="stretch_width",
        )

        self.orders_text = pn.widgets.TextInput(
            name="Overtone orders",
            value=self.saved.get("orders_text", default_orders),
            placeholder="g0:n=1, g1:n=3, g2:n=5",
            sizing_mode="stretch_width",
        )

        self.region_type = pn.widgets.Select(
            name="Phase type",
            options=_REGION_TYPES,
            value="phase",
            sizing_mode="stretch_width",
        )
        self.region_label = pn.widgets.TextInput(
            name="Phase / event name",
            placeholder="baseline / rinse / sample added",
            sizing_mode="stretch_width",
        )
        # Backward-compatible aliases for older action/page code.
        self.marker_type = self.region_type
        self.marker_label = self.region_label

        self.mark_point_button = pn.widgets.Button(
            name="Mark event",
            button_type="default",
            icon="map-pin",
            sizing_mode="stretch_width",
        )
        self.mark_window_button = pn.widgets.Button(
            name="Save phase",
            button_type="primary",
            icon="brackets-contain",
            sizing_mode="stretch_width",
        )
        self.marker_select = pn.widgets.Select(
            name="Report/export region",
            options={"Current range": "__current__"},
            value="__current__",
            sizing_mode="stretch_width",
        )
        self.analysis_region_select = pn.widgets.Select(
            name="Analysis target",
            options={"Current range": "__current__"},
            value="__current__",
            sizing_mode="stretch_width",
            css_classes=["compact-select", "analysis-target-select"],
        )

        self.use_selection_as_baseline = pn.widgets.Button(
            name="Set reference = current range",
            button_type="primary",
            icon="anchor",
            sizing_mode="stretch_width",
        )
        self.revert_baseline = pn.widgets.Button(
            name="Undo zero change",
            button_type="default",
            icon="history",
            disabled=True,
            sizing_mode="stretch_width",
        )
        self.save_state_button = pn.widgets.Button(
            name="Save workspace",
            button_type="success",
            icon="device-floppy",
            sizing_mode="stretch_width",
        )

        self.annotation_version = pn.widgets.IntInput(value=0, visible=False)
        self.plot_reset_version = pn.widgets.IntInput(value=0, visible=False)
        self.status = pn.pane.Alert("Workspace ready.", alert_type="light", sizing_mode="stretch_width")

    # ---------------------------------------------------------------------
    # Reactive inputs used by the pages
    # ---------------------------------------------------------------------
    @property
    def signal_inputs(self) -> tuple:
        # Range sliders trigger on ``value_throttled`` so dragging fires a single
        # query on release instead of one per mouse-move.  Numeric inputs are
        # included so precise edits also trigger bound plots/tables immediately.
        return (
            self.group_select,
            self.orders_text,
            self.t_range.param.value_throttled,
            self.t_range_start,
            self.t_range_end,
            self.baseline_range.param.value_throttled,
            self.baseline_start,
            self.baseline_end,
            self.annotation_version,
            self.analysis_region_select,
        )

    @property
    def explore_inputs(self) -> tuple:
        return (*self.signal_inputs, self.quantity_select)

    @property
    def waterfall_band_input(self):
        """Throttled trigger for the waterfall frequency-band slider."""
        return self.frequency_band.param.value_throttled

    @property
    def sweep_inputs(self) -> tuple:
        return (
            self.sequence.param.value_throttled,
            self.group_select,
            self.group_for_single,
            self.sweep_mode,
        )

    # ---------------------------------------------------------------------
    # State and validation
    # ---------------------------------------------------------------------
    def selected_groups(self) -> list[int]:
        groups = [int(v) for v in self.group_select.value]
        return groups or [self.info.groups[0]]

    def _keep_one_channel_selected(self, event) -> None:
        if event.new:
            return
        self.group_select.value = [str(self.info.groups[0])]

    def show_all_channels(self, _event=None) -> None:
        self.group_select.value = [str(g) for g in self.info.groups]

    def orders(self) -> dict[int, int]:
        return parse_orders(self.orders_text.value, self.info.orders, self.info.groups)

    def state(self) -> ViewState:
        # The sliders are the canonical source of truth; numeric inputs are kept
        # synchronized with them and are included in ``signal_inputs`` only to
        # trigger reactive updates.
        return ViewState(
            groups=self.selected_groups(),
            quantity=self.quantity_select.value,
            t_range_s=tuple(float(v) for v in self.t_range.value),
            baseline_s=tuple(float(v) for v in self.baseline_range.value),
            orders=self.orders(),
            orders_text=self.orders_text.value,
            sequence=int(self.sequence.value),
            single_group=int(self.group_for_single.value),
            sweep_mode=self.sweep_mode.value,
            frequency_band=tuple(float(v) for v in self.frequency_band.value),
            annotation_label=self.region_label.value,
            annotation_version=int(self.annotation_version.value),
        )

    def _safe_float(self, value, fallback: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    def _clean_range(self, values) -> tuple[float, float]:
        try:
            start, end = values
        except Exception:
            start, end = 0.0, self.info.span_s
        return self._clamp_range(float(start), float(end))

    def _clamp_range(self, start: float, end: float) -> tuple[float, float]:
        lo, hi = 0.0, float(self.info.span_s)
        start = max(lo, min(hi, self._safe_float(start, lo)))
        end = max(lo, min(hi, self._safe_float(end, hi)))
        if start > end:
            start, end = end, start
        if hi > lo and abs(end - start) < 1e-12:
            if end < hi:
                end = min(hi, start + self._time_step)
            else:
                start = max(lo, end - self._time_step)
        return (float(start), float(end))

    def _clamp_edge(self, kind: RangeKind, edge: RangeEdge, value) -> tuple[float, float]:
        if kind == "current":
            current = self.t_range.value
        elif kind == "reference":
            current = self.baseline_range.value
        else:
            current = self.mark_range.value
        start, end = (float(v) for v in current)
        new_value = self._safe_float(value, start if edge == "start" else end)
        lo, hi = 0.0, float(self.info.span_s)
        new_value = max(lo, min(hi, new_value))

        if edge == "start":
            start = min(new_value, end)
        else:
            end = max(new_value, start)
        return self._clamp_range(start, end)

    def _sync_inputs_from_slider(self, kind: RangeKind, value) -> None:
        if self._syncing_ranges:
            return
        start, end = self._clamp_range(*value)
        self._syncing_ranges = True
        try:
            if kind == "current":
                self.t_range_start.value = start
                self.t_range_end.value = end
            elif kind == "reference":
                self.baseline_start.value = start
                self.baseline_end.value = end
            else:
                self.mark_start.value = start
                self.mark_end.value = end
        finally:
            self._syncing_ranges = False

    def _sync_slider_from_input(self, kind: RangeKind, edge: RangeEdge, value) -> None:
        if self._syncing_ranges:
            return
        start, end = self._clamp_edge(kind, edge, value)
        self._syncing_ranges = True
        try:
            if kind == "current":
                self.t_range.value = (start, end)
                self.t_range_start.value = start
                self.t_range_end.value = end
            elif kind == "reference":
                self.baseline_range.value = (start, end)
                self.baseline_start.value = start
                self.baseline_end.value = end
            else:
                self.mark_range.value = (start, end)
                self.mark_start.value = start
                self.mark_end.value = end
        finally:
            self._syncing_ranges = False

    def set_current_range_values(self, x0: float, x1: float) -> None:
        """Set the current range from arbitrary values (e.g. a plot brush)."""
        start, end = self._clamp_range(x0, x1)
        self.t_range.value = (start, end)
        self._sync_inputs_from_slider("current", (start, end))

    def set_reference_range_values(self, x0: float, x1: float) -> None:
        """Set the zero/reference range from arbitrary values (e.g. a plot brush)."""
        start, end = self._clamp_range(x0, x1)
        self.baseline_range.value = (start, end)
        self._sync_inputs_from_slider("reference", (start, end))

    def set_mark_range_values(self, x0: float, x1: float) -> None:
        """Set the draft phase-mark range from a plot brush."""
        start, end = self._clamp_range(x0, x1)
        self.mark_range.value = (start, end)
        self._sync_inputs_from_slider("mark", (start, end))

    def set_full_current_range(self, _event=None) -> None:
        self.t_range.value = (0.0, float(self.info.span_s))
        self._sync_inputs_from_slider("current", self.t_range.value)

    def set_full_reference_range(self, _event=None) -> None:
        self.baseline_range.value = (0.0, float(self.info.span_s))
        self._sync_inputs_from_slider("reference", self.baseline_range.value)

    def set_full_mark_range(self, _event=None) -> None:
        self.mark_range.value = (0.0, float(self.info.span_s))
        self._sync_inputs_from_slider("mark", self.mark_range.value)

    def previous_sweep(self, _event=None) -> None:
        self.sequence.value = max(int(self.sequence.start), int(self.sequence.value) - 1)

    def next_sweep(self, _event=None) -> None:
        self.sequence.value = min(int(self.sequence.end), int(self.sequence.value) + 1)

    def reset_plot_scale(self, _event=None) -> None:
        """Request plots to re-render with their default axis ranges."""
        self.plot_reset_version.value += 1

    def plot_reset_button(self, name: str = "Reset plot scale"):
        """Return a fresh reset button so the same widget is not mounted twice."""
        button = pn.widgets.Button(
            name=name,
            button_type="default",
            icon="refresh",
            sizing_mode="stretch_width",
        )
        button.on_click(self.reset_plot_scale)
        return button

    # ---------------------------------------------------------------------
    # Reusable readouts
    # ---------------------------------------------------------------------
    def _duration_markdown(self, kind: RangeKind, *_):
        if kind == "current":
            start, end = self.t_range.value
        elif kind == "reference":
            start, end = self.baseline_range.value
        else:
            start, end = self.mark_range.value
        duration = max(0.0, float(end) - float(start))
        return pn.pane.Markdown(
            f"<div class='range-duration'><b>{duration:,.3f} s</b></div>",
            margin=0,
            sizing_mode="stretch_width",
        )

    def _range_summary(self, start: float, end: float) -> str:
        return f"{start:,.3f}–{end:,.3f} s"

    def orders_readout(self, *_):
        return pn.pane.Markdown(
            " · ".join(f"**g{g} → n={n}**" for g, n in sorted(self.orders().items())),
            margin=0,
            sizing_mode="stretch_width",
        )

    def channels_readout(self, *_):
        total = len(self.info.groups)
        selected = len(self.selected_groups())
        return pn.pane.Markdown(
            f"<small><b>{selected}</b> / <b>{total}</b> channels visible</small>",
            margin=0,
            sizing_mode="stretch_width",
        )

    def draw_mode_status(self, *_):
        mode = self.brush_mode.value
        labels = {
            "current": "Drawing updates the analysis range",
            "reference": "Drawing updates the reference range",
            "mark": "Drawing prepares a phase to save",
        }
        return pn.pane.Markdown(
            f"<div class='draw-mode-status'>{labels.get(mode, labels['current'])}</div>",
            margin=0,
            sizing_mode="stretch_width",
        )

    def quantity_context(self, quantity_key: str | None = None):
        key = quantity_key or self.quantity_select.value
        q = quantity(key)
        unit = f" ({q.unit})" if q.unit else ""
        if q.referenced:
            text = (
                f"<b>{q.label}{unit}</b><br>"
                "Referenced quantity: values are calculated relative to the zero/reference range."
            )
        else:
            text = (
                f"<b>{q.label}{unit}</b><br>"
                "Absolute/raw quantity: the zero/reference range is shown only for context and is not applied."
            )
        return pn.pane.Markdown(
            f"<small>{text}</small>",
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["quantity-context"],
        )

    def zero_reference_readout(self, *_):
        c0, c1 = (float(v) for v in self.t_range.value)
        z0, z1 = (float(v) for v in self.baseline_range.value)
        same = abs(c0 - z0) < 1e-9 and abs(c1 - z1) < 1e-9
        suffix = " <b>(same as current range)</b>" if same else ""
        return pn.pane.Markdown(
            f"<small>Current range: <b>{self._range_summary(c0, c1)}</b><br>"
            f"Zero/reference: <b>{self._range_summary(z0, z1)}</b>{suffix}<br>"
            "Δ-values are computed relative to the average signal in the zero/reference range.</small>",
            margin=0,
            sizing_mode="stretch_width",
        )

    def zero_reference_summary(self, *_):
        c0, c1 = (float(v) for v in self.t_range.value)
        z0, z1 = (float(v) for v in self.baseline_range.value)
        same = abs(c0 - z0) < 1e-9 and abs(c1 - z1) < 1e-9
        suffix = " · same range" if same else ""
        return pn.pane.Markdown(
            f"<small>Current: <b>{self._range_summary(c0, c1)}</b> · "
            f"Zero/reference: <b>{self._range_summary(z0, z1)}</b>{suffix}</small>",
            margin=0,
            sizing_mode="stretch_width",
        )

    def sweep_context(self, *_):
        mode = "selected channels" if self.sweep_mode.value == "selected overtones" else "one channel"
        selected = ", ".join(str(g) for g in self.selected_groups())
        start, end = (float(v) for v in self.t_range.value)
        return pn.pane.Markdown(
            f"<small><b>Sweep {int(self.sequence.value)}</b> · {mode}<br>"
            f"Current range: <b>{self._range_summary(start, end)}</b><br>"
            f"Visible groups: <b>{selected}</b></small>",
            margin=0,
            sizing_mode="stretch_width",
        )

    # ---------------------------------------------------------------------
    # Control blocks
    # ---------------------------------------------------------------------
    def _number_row(self, kind: RangeKind):
        if kind == "current":
            start_input = self.t_range_start
            end_input = self.t_range_end
            deps = (self.t_range, self.t_range_start, self.t_range_end)
        elif kind == "reference":
            start_input = self.baseline_start
            end_input = self.baseline_end
            deps = (self.baseline_range, self.baseline_start, self.baseline_end)
        else:
            start_input = self.mark_start
            end_input = self.mark_end
            deps = (self.mark_range, self.mark_start, self.mark_end)
        return pn.Row(
            start_input,
            end_input,
            pn.Column(
                pn.pane.Markdown("<small>Duration</small>", margin=0),
                pn.bind(lambda *_: self._duration_markdown(kind), *deps),
                margin=0,
                sizing_mode="stretch_width",
            ),
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["range-number-row"],
        )

    def current_range_controls(self, include_save: bool = False):
        children = [
            self.t_range,
            self._number_row("current"),
            pn.Row(
                self.t_full_range_button,
                margin=0,
                sizing_mode="stretch_width",
                css_classes=["range-actions"],
            ),
        ]
        if include_save:
            children.append(self.phase_mark_controls(include_card=False))
        return pn.Card(
            *children,
            title="Analysis range",
            collapsible=False,
            collapsed=False,
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["plot-controls", "range-editor-card", "current-range-card"]
        )

    def current_range_compact(self):
        return self.current_range_controls(include_save=False)

    def analysis_region_controls(self, summary=None):
        """Compact Quantify target selector.

        The selector no longer mutates the saved current range. Quantify reads
        the selected target directly, so choosing a marker zooms that page to
        the marker while choosing Current range returns to the live range.
        """
        target_stack = pn.Column(
            self.analysis_region_select,
            summary if summary is not None else pn.Spacer(height=0),
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["analysis-target-stack", "compact-panel"],
        )
        return pn.Row(
            target_stack,
            self.current_range_controls(include_save=False),
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["analysis-region-row", "compact-two-column", "analysis-target-row"],
        )

    def zero_reference_controls(self):
        return pn.Card(
            pn.bind(self.zero_reference_readout, self.t_range, self.baseline_range),
            self.baseline_range,
            self._number_row("reference"),
            pn.Row(
                self.use_selection_as_baseline,
                self.revert_baseline,
                self.baseline_full_range_button,
                margin=0,
                sizing_mode="stretch_width",
                css_classes=["range-actions"],
            ),
            title="Reference range",
            collapsible=False,
            collapsed=False,
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["plot-controls", "range-editor-card", "reference-range-card"]
        )

    def zero_reference_compact(self, quantity_key: str | None = None):
        key = quantity_key or self.quantity_select.value
        if not quantity(key).referenced:
            return pn.pane.Markdown(
                "<small>Absolute/raw quantity: the zero/reference range is ignored.</small>",
                margin=0,
                sizing_mode="stretch_width",
            )
        return self.zero_reference_controls()

    def mark_range_controls(self):
        return pn.Card(
            self.mark_range,
            self._number_row("mark"),
            pn.Row(
                self.mark_full_range_button,
                margin=0,
                sizing_mode="stretch_width",
                css_classes=["range-actions"],
            ),
            self.phase_mark_controls(include_card=False),
            title="Mark range",
            collapsible=False,
            collapsed=False,
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["plot-controls", "range-editor-card", "mark-range-card"],
        )

    def phase_mark_controls(self, include_card: bool = True):
        block = pn.Column(
            pn.Row(
                self.region_label,
                self.region_type,
                margin=0,
                sizing_mode="stretch_width",
            ),
            pn.Row(
                self.mark_point_button,
                self.mark_window_button,
                margin=0,
                sizing_mode="stretch_width",
                css_classes=["range-actions"],
            ),
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["phase-mark-controls"],
        )
        if not include_card:
            return block
        return pn.Card(
            block,
            title="Mark phase",
            collapsible=True,
            collapsed=False,
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["phase-mark-card"],
        )

    def active_range_controls(
        self,
        *,
        extra_class: str = "",
        quantity_key: str | None = None,
        include_save: bool = False,
    ):
        def _view(mode: str, qkey: str | None = None):
            key = qkey or self.quantity_select.value
            if mode == "reference":
                if quantity(key).referenced:
                    return self.zero_reference_controls()
                return pn.Card(
                    pn.pane.Markdown("<small>Reference is not used for this raw/absolute quantity.</small>", margin=0),
                    title="Reference range",
                    collapsible=True,
                    collapsed=False,
                    margin=0,
                    sizing_mode="stretch_width",
                    css_classes=["plot-controls", "range-editor-card", "reference-range-card", "is-disabled"],
                )
            if mode == "mark":
                return self.mark_range_controls()
            return self.current_range_controls(include_save=include_save)

        deps = [self.brush_mode]
        if quantity_key is not None:
            return pn.Column(
                self.brush_mode,
                pn.Row(self.plot_reset_button(), margin=0, sizing_mode="stretch_width", css_classes=["range-actions"]),
                pn.bind(_view, self.brush_mode, quantity_key),
                self.range_status,
                margin=0,
                sizing_mode="stretch_width",
                css_classes=["plot-controls", "paired-ranges", extra_class],
            )
        return pn.Column(
            self.brush_mode,
            pn.Row(self.plot_reset_button(), margin=0, sizing_mode="stretch_width", css_classes=["range-actions"]),
            pn.bind(_view, self.brush_mode),
            self.range_status,
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["plot-controls", "paired-ranges", extra_class],
        )

    def paired_range_controls(
        self,
        extra_class: str,
        quantity_key: str | None = None,
        include_save: bool = False,
    ):
        # Backward-compatible name: now shows only the selected range editor.
        return self.active_range_controls(
            extra_class=extra_class,
            quantity_key=quantity_key,
            include_save=include_save,
        )

    def overview_range_controls(self, include_reset: bool = True):
        # Review is only for selecting the current analysis range. Reference and
        # phase marking happen on their own pages, so no range-target switch is
        # shown here.
        self.brush_mode.value = "current"
        children = [self.current_range_controls(include_save=False)]
        if include_reset:
            children.insert(0, self.plot_tools_row(include_quantity=False))
        children.append(self.range_status)
        return pn.Column(
            *children,
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["plot-controls", "overview-ranges"],
        )

    def analyze_range_controls(self, quantity_key: str | None = None, include_save: bool = True, include_reset: bool = True):
        # Quantify is also current-range only; reference and marking are handled
        # by the dedicated Reference and Phases steps.
        self.brush_mode.value = "current"
        children = [self.current_range_controls(include_save=include_save)]
        if include_reset:
            children.insert(0, self.plot_tools_row(include_quantity=True))
        children.append(self.range_status)
        return pn.Column(
            *children,
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["plot-controls", "analyze-ranges"],
        )

    def zero_reference_if_needed(self, quantity_key: str | None = None):
        key = quantity_key or self.quantity_select.value
        if not quantity(key).referenced:
            return pn.pane.Markdown(
                "<small>This quantity is absolute/raw, so no reference range is needed.</small>",
                margin=0,
                sizing_mode="stretch_width",
            )
        return self.zero_reference_controls()

    def window_controls(self, include_zero_reference: bool = True):
        items = [self.current_range_controls()]
        if include_zero_reference:
            items.append(self.zero_reference_controls())
        return pn.Column(*items, margin=0, sizing_mode="stretch_width", css_classes=["plot-controls"])


    def compact_channel_controls(self):
        """Compact, collapsed channel chooser for placement next to plot reset."""
        card = self.channel_controls()
        card.collapsed = True
        card.width = 280
        card.sizing_mode = "fixed"
        return card

    def plot_tools_row(self, *, include_quantity: bool = False):
        """Small per-plot toolbar: reset scale, optional quantity selector, channels."""
        items = [self.plot_reset_button()]
        if include_quantity:
            items.append(self.quantity_select)
        items.append(self.compact_channel_controls())
        return pn.Row(
            *items,
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["plot-tools-row"],
        )

    def channel_controls(self):
        return pn.Card(
            pn.bind(self.channels_readout, self.group_select),
            self.group_select,
            self.show_all_channels_button,
            title="Channels",
            collapsible=True,
            collapsed=False,
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["channel-controls"],
        )

    def advanced_controls(self):
        return pn.Card(
            self.orders_text,
            pn.bind(self.orders_readout, self.orders_text),
            title="Advanced: overtone orders",
            collapsible=True,
            collapsed=True,
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["advanced-controls"],
        )

    def workspace_controls(self):
        return pn.Card(
            self.save_state_button,
            self.status,
            title="Workspace",
            collapsible=True,
            collapsed=True,
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["workspace-controls"],
        )
