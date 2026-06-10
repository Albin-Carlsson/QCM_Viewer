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
from .theme import (
    AREA_MIN_CM2,
    AXES,
    DESPIKE_WINDOW_DEFAULT,
    MPE_CLIP_HI_DEFAULT,
    MPE_CLIP_LO_DEFAULT,
    MPE_SMOOTH_WINDOW_DEFAULT,
    QUANTITIES,
    ExperimentParams,
    area_to_diameter_mm,
    quantity,
)

_QUANTITY_OPTIONS = {q.label: key for key, q in QUANTITIES.items()}
_AXIS_OPTIONS = {a.label: key for key, a in AXES.items()}


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

# Styling for these widgets lives centrally in design.py (scoped by the
# css_classes applied below: "channel-toggles", "range-editor-card",
# "quantity-context", …). No per-widget stylesheets — one source of truth.

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
        # Only offer quantities/axes the run can actually compute, so a fit-only
        # or echem-light run never lists a column it doesn't have (which would
        # otherwise fail at query time with a DuckDB binder error).
        self._quantity_options = self._available_quantity_options()
        self._build_widgets()
        self._build_param_widgets()
        self._build_mpe_widgets()

    def _run_columns(self) -> set[str]:
        return set(getattr(self.info, "columns", []) or [])

    def _available_quantity_options(self) -> dict[str, str]:
        """Label→key for quantities whose source columns the run actually has."""
        cols = self._run_columns()
        if not cols:  # unknown columns (older RunInfo): keep everything
            return dict(_QUANTITY_OPTIONS)
        return {
            label: key for label, key in _QUANTITY_OPTIONS.items()
            if set(QUANTITIES[key].sources).issubset(cols)
        }

    def _available_axis_options(self) -> dict[str, str]:
        """Label→key for x-axes the run can plot (time always; others by column).

        ``cycle_number`` is available when a stored ``cycle`` exists *or* a
        ``current`` channel from which CP cycles are derived; ``cycle_time`` and
        the potential/charge axes require their stored column.
        """
        cols = self._run_columns()
        out: dict[str, str] = {}
        for label, key in _AXIS_OPTIONS.items():
            ax = AXES[key]
            if ax.is_time:
                out[label] = key
            elif key == "cycle_number":
                if "cycle" in cols or "current" in cols:
                    out[label] = key
            elif ax.source in cols:
                out[label] = key
        return out

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
        )
        self.group_select.param.watch(self._keep_one_channel_selected, "value")
        self.show_all_channels_button = pn.widgets.Button(
            name="Show all channels",
            button_type="default",
            icon="eye",
            sizing_mode="stretch_width",
        )
        self.show_all_channels_button.on_click(self.show_all_channels)
        self.overtone_frequency: dict[int, pn.widgets.Checkbox] = {}
        self.overtone_dissipation: dict[int, pn.widgets.Checkbox] = {}
        self.overtone_normalize: dict[int, pn.widgets.Checkbox] = {}
        self.overtone_frequency_all_button = pn.widgets.Button(
            name="All",
            button_type="default",
            width=46,
            height=26,
            css_classes=["overtone-all-toggle"],
        )
        self.overtone_dissipation_all_button = pn.widgets.Button(
            name="All",
            button_type="default",
            width=46,
            height=26,
            css_classes=["overtone-all-toggle"],
        )
        self.overtone_normalize_all_button = pn.widgets.Button(
            name="All",
            button_type="default",
            width=46,
            height=26,
            css_classes=["overtone-all-toggle"],
        )
        self.overtone_frequency_all_button.on_click(lambda _event: self.toggle_overtone_column("frequency"))
        self.overtone_dissipation_all_button.on_click(lambda _event: self.toggle_overtone_column("dissipation"))
        self.overtone_normalize_all_button.on_click(lambda _event: self.toggle_overtone_column("normalize"))
        saved_overtone_controls = self.saved.get("overtone_controls", {})
        for g in self.info.groups:
            n = int(self.info.orders.get(g, 1))
            key = str(g)
            saved_row = saved_overtone_controls.get(key, {}) if isinstance(saved_overtone_controls, dict) else {}
            # Names are intentionally empty: the column headers label these, so a
            # bare centered box per cell reads as a clean signal-selection table.
            self.overtone_frequency[g] = pn.widgets.Checkbox(
                name="",
                value=bool(saved_row.get("frequency", True)),
                sizing_mode="stretch_width",
            )
            self.overtone_dissipation[g] = pn.widgets.Checkbox(
                name="",
                value=bool(saved_row.get("dissipation", True)),
                sizing_mode="stretch_width",
            )
            self.overtone_normalize[g] = pn.widgets.Checkbox(
                name="",
                value=bool(saved_row.get("normalize_frequency", True)),
                sizing_mode="stretch_width",
            )

        current_default = self._clean_range(self.saved.get("t_range_s", [0.0, self.info.span_s]))
        reference_default = self._clean_range(
            self.saved.get("baseline_s", [0.0, min(self.info.span_s, self.info.span_s * 0.1)])
        )

        # Plain RangeSlider + explicit numeric inputs gives users both quick dragging
        # and precise entry without the cramped EditableRangeSlider boxes.
        self.t_range = pn.widgets.RangeSlider(
            name="Time window (s)",
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
            name="Reference window (s)",
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
            name="Mark window (s)",
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

        # Slider → numeric inputs: sync on ``value_throttled`` (fires once when the
        # drag settles), not the continuous ``value``. Watching ``value`` pushed two
        # FloatInput updates back to the browser on every pixel of a drag — the
        # round-trips were what made the sliders feel laggy. Programmatic range
        # changes (brush, full-range buttons) call ``_sync_inputs_from_slider``
        # directly, so the inputs still stay in sync outside of dragging.
        self.t_range.param.watch(lambda event: self._sync_inputs_from_slider("current", event.new), "value_throttled")
        self.baseline_range.param.watch(lambda event: self._sync_inputs_from_slider("reference", event.new), "value_throttled")
        self.t_range_start.param.watch(lambda event: self._sync_slider_from_input("current", "start", event.new), "value")
        self.t_range_end.param.watch(lambda event: self._sync_slider_from_input("current", "end", event.new), "value")
        self.baseline_start.param.watch(lambda event: self._sync_slider_from_input("reference", "start", event.new), "value")
        self.baseline_end.param.watch(lambda event: self._sync_slider_from_input("reference", "end", event.new), "value")
        self.mark_range.param.watch(lambda event: self._sync_inputs_from_slider("mark", event.new), "value_throttled")
        self.mark_start.param.watch(lambda event: self._sync_slider_from_input("mark", "start", event.new), "value")
        self.mark_end.param.watch(lambda event: self._sync_slider_from_input("mark", "end", event.new), "value")

        self.range_status = pn.pane.Alert("", alert_type="warning", visible=False, sizing_mode="stretch_width")

        self.brush_mode = pn.widgets.RadioButtonGroup(
            name="Draw on plot",
            options={"Analysis range": "current", "Reference range": "reference", "Mark range": "mark"},
            value="current",
            button_type="default",
            sizing_mode="stretch_width",
            description="Choose what dragging on the plot edits: the analysis range, "
                        "the reference (baseline) range, or a span to save as a phase.",
            css_classes=["range-mode-toggle"],
        )

        # The labeled eyebrow above each toolbar cell is the visible label, so
        # these widgets carry no built-in title (which Panel renders in a shadow
        # root that document CSS cannot reach — leaving it set produces a
        # duplicate label next to the eyebrow).
        # Offer only x-axes the run can actually plot (Time always; potential /
        # charge / cycle-time / cycle-number gated on the columns being present),
        # so no option silently fails with a missing-column query.
        x_options = self._available_axis_options()
        x_value = self.saved.get("x_axis", "time")
        if x_value not in x_options.values():
            x_value = "time"
        self.x_axis_select = pn.widgets.Select(
            name="",
            options=x_options,
            value=x_value,
            sizing_mode="stretch_width",
            css_classes=["compact-select", "x-axis-select"],
            description=("Drag-select a range on the Time or Cycle-number axis to set the "
                         "analysis window. Potential/charge axes sweep back and forth, so a "
                         "drag has no single window and selection is disabled there."),
        )
        q_options = self._quantity_options
        q_value = self.saved.get("quantity", "delta_f_norm")
        if q_value not in q_options.values():
            q_value = next(iter(q_options.values()))
        self.quantity_select = pn.widgets.Select(
            name="",
            options=q_options,
            value=q_value,
            sizing_mode="stretch_width",
            css_classes=["compact-select", "quantity-select"],
        )
        # --- redesign: top-of-plot toolbar widgets --------------------------
        qr_value = self.saved.get("quantity_right", "delta_D")
        if qr_value != "__none__" and qr_value not in q_options.values():
            qr_value = "__none__"
        self.quantity_select_right = pn.widgets.Select(
            name="",
            options={"None (single axis)": "__none__", **q_options},
            value=qr_value,
            sizing_mode="stretch_width",
            css_classes=["compact-select", "quantity-select-right"],
        )
        # NB: Panel's Checkbox has no `description`/tooltip, so the labels carry the
        # meaning ("y = 0 line" rather than the cryptic "Zero line").
        self.show_phases = pn.widgets.Checkbox(
            name="Show phases", value=bool(self.saved.get("show_phases", True)),
        )
        self.zero_line = pn.widgets.Checkbox(
            name="y = 0 line", value=bool(self.saved.get("zero_line", False)),
        )
        self.show_cycles = pn.widgets.Checkbox(
            name="Show cycles", value=bool(self.saved.get("show_cycles", False)),
        )
        # A second Y-axis only makes sense as a vs-time comparison of two distinct
        # signals: disable it on cross-plots (vs potential/charge/cycle) and never
        # let the right axis duplicate the left.
        self.quantity_select.param.watch(self._refresh_right_axis_options, "value")
        self.x_axis_select.param.watch(self._apply_right_axis_enabled, "value")
        self._refresh_right_axis_options()
        self._apply_right_axis_enabled()

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
            button_type="default",
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
            name="Save view",
            button_type="default",
            icon="device-floppy",
            description="Save the current selections, axes, and ranges to this run "
                        "so they're restored next time you open it.",
            sizing_mode="stretch_width",
        )

        self.annotation_version = pn.widgets.IntInput(value=0, visible=False)
        self.plot_reset_version = pn.widgets.IntInput(value=0, visible=False)
        # Bumped whenever the run set changes (run added, relabelled, or the
        # active run switched) so the hero overlay, run-manager card, and the
        # single-run pages rebuild against the new set.
        self.runset_version = pn.widgets.IntInput(value=0, visible=False)
        self.status = pn.pane.Alert("Workspace ready.", alert_type="light", sizing_mode="stretch_width")

    # ---------------------------------------------------------------------
    # Reactive inputs used by the pages
    # ---------------------------------------------------------------------
    @property
    def signal_inputs(self) -> tuple:
        # Range sliders trigger on ``value_throttled`` so dragging fires a single
        # query on release instead of one per mouse-move.  Numeric inputs are
        # included so precise edits also trigger bound plots/tables immediately.
        # Only the throttled sliders drive reactive rebuilds. The numeric inputs
        # sync into the sliders (``_sync_slider_from_input`` sets ``t_range.value``),
        # so a typed edit still updates plots/stats via the slider — but they are
        # intentionally NOT separate triggers, otherwise one slider drag fires up
        # to three full rebuilds (slider + both synced number boxes) and feels laggy.
        return (
            self.group_select,
            self.orders_text,
            *self.overtone_signal_inputs,
            *self.param_inputs,
            *self.mpe_inputs,
            self.t_range.param.value_throttled,
            self.baseline_range.param.value_throttled,
            self.annotation_version,
            self.analysis_region_select,
        )

    @property
    def overtone_signal_inputs(self) -> tuple:
        widgets = []
        for g in self.info.groups:
            widgets.extend([
                self.overtone_frequency[g],
                self.overtone_dissipation[g],
                self.overtone_normalize[g],
            ])
        return tuple(widgets)

    @property
    def explore_inputs(self) -> tuple:
        return (*self.signal_inputs, self.quantity_select, self.x_axis_select)

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

    def _overtone_column(self, column: str) -> dict[int, pn.widgets.Checkbox]:
        if column == "frequency":
            return self.overtone_frequency
        if column == "dissipation":
            return self.overtone_dissipation
        if column == "normalize":
            return self.overtone_normalize
        raise ValueError(f"Unknown overtone control column: {column}")

    def toggle_overtone_column(self, column: str) -> None:
        controls = self._overtone_column(column)
        target = not all(bool(widget.value) for widget in controls.values())
        for widget in controls.values():
            widget.value = target

    def overtone_controls_state(self) -> dict[str, dict[str, bool]]:
        return {
            str(g): {
                "frequency": bool(self.overtone_frequency[g].value),
                "dissipation": bool(self.overtone_dissipation[g].value),
                "normalize_frequency": bool(self.overtone_normalize[g].value),
            }
            for g in self.info.groups
        }

    def frequency_groups(self) -> list[int]:
        groups = [g for g in self.selected_groups() if bool(self.overtone_frequency[g].value)]
        return groups

    def dissipation_groups(self) -> list[int]:
        groups = [g for g in self.selected_groups() if bool(self.overtone_dissipation[g].value)]
        return groups

    def normalized_frequency_groups(self) -> set[int]:
        return {g for g in self.info.groups if bool(self.overtone_normalize[g].value)}

    # --- experiment parameters --------------------------------------------
    def _build_param_widgets(self) -> None:
        """Editable per-run experiment parameters, seeded from saved state."""
        p = ExperimentParams.from_dict(self.saved.get("params"))
        self.param_area = pn.widgets.FloatInput(
            name="Electrode area (cm²)", value=p.area_cm2, start=AREA_MIN_CM2, step=0.01,
            sizing_mode="stretch_width",
        )
        self.param_sensitivity = pn.widgets.FloatInput(
            name="Sauerbrey sensitivity (ng·cm⁻²·Hz⁻¹)", value=p.sensitivity, start=AREA_MIN_CM2,
            step=0.1, sizing_mode="stretch_width",
        )
        self.param_molar_mass = pn.widgets.FloatInput(
            name="Molar mass M (g/mol)", value=p.molar_mass, start=AREA_MIN_CM2, step=0.01,
            sizing_mode="stretch_width",
        )
        self.param_valency = pn.widgets.IntInput(
            name="Valency z", value=p.valency, start=1, step=1, sizing_mode="stretch_width",
        )

    def params(self) -> ExperimentParams:
        d = ExperimentParams()
        return ExperimentParams(
            area_cm2=self._safe_float(self.param_area.value, d.area_cm2),
            sensitivity=self._safe_float(self.param_sensitivity.value, d.sensitivity),
            molar_mass=self._safe_float(self.param_molar_mass.value, d.molar_mass),
            valency=max(1, int(self.param_valency.value or d.valency)),
        )

    @property
    def param_inputs(self) -> tuple:
        return (self.param_area, self.param_sensitivity, self.param_molar_mass, self.param_valency)

    def experiment_params_panel(self) -> pn.viewable.Viewable:
        """Editable parameter card with a live Target-MPE (= M/z) readout."""
        def target(*_):
            t = self.params().target_mpe
            txt = f"{t:,.2f} g/mol" if t is not None else "—"
            return pn.pane.HTML(
                f"<div class='param-target'><b>Target MPE (M / z):</b> {txt}</div>", margin=0,
            )
        def geom(*_):
            d_mm = area_to_diameter_mm(self._safe_float(self.param_area.value, 0.0))
            return pn.pane.HTML(
                f"<div class='param-geom'>= ⌀ {d_mm:.1f} mm disc</div>", margin=0,
            )
        return pn.Card(
            self.param_area, pn.bind(geom, self.param_area),
            self.param_sensitivity, self.param_molar_mass, self.param_valency,
            pn.bind(target, *self.param_inputs),
            title="Experiment parameters",
            collapsible=True, collapsed=True, margin=0, sizing_mode="stretch_width",
            css_classes=["experiment-params"],
        )

    # --- MPE display controls ---------------------------------------------
    def _build_mpe_widgets(self) -> None:
        """Display controls scoped to the mass-per-electron (MPE) quantity."""
        s = self.saved
        self.mpe_smooth = pn.widgets.Checkbox(
            name="Savitzky–Golay smoothing", value=bool(s.get("mpe_smooth", False)),
        )
        self.mpe_window = pn.widgets.IntInput(
            name="Smoothing window", value=int(s.get("mpe_window", MPE_SMOOTH_WINDOW_DEFAULT)),
            start=5, step=2, sizing_mode="stretch_width",
        )
        self.mpe_clip = pn.widgets.Checkbox(
            name="Clip outliers", value=bool(s.get("mpe_clip", True)),
        )
        self.mpe_clip_lo = pn.widgets.FloatInput(
            name="Clip min (g/mol)", value=float(s.get("mpe_clip_lo", MPE_CLIP_LO_DEFAULT)), step=10.0,
            sizing_mode="stretch_width",
        )
        self.mpe_clip_hi = pn.widgets.FloatInput(
            name="Clip max (g/mol)", value=float(s.get("mpe_clip_hi", MPE_CLIP_HI_DEFAULT)), step=10.0,
            sizing_mode="stretch_width",
        )
        self.mpe_target_show = pn.widgets.Checkbox(
            name="Show target line (M / z)", value=bool(s.get("mpe_target_show", True)),
        )
        self.despike = pn.widgets.Checkbox(
            name="Despike (Hampel)", value=bool(s.get("despike", False)),
        )
        self.despike_window = pn.widgets.IntInput(
            name="Despike window", value=int(s.get("despike_window", DESPIKE_WINDOW_DEFAULT)),
            start=3, step=2, sizing_mode="stretch_width",
        )

    @property
    def mpe_inputs(self) -> tuple:
        return (self.mpe_smooth, self.mpe_window, self.mpe_clip,
                self.mpe_clip_lo, self.mpe_clip_hi, self.mpe_target_show,
                self.despike, self.despike_window)

    def overtone_orders_panel(self) -> pn.viewable.Viewable:
        """Editable overtone-order map (n per channel).

        Orders are auto-inferred from the resonance frequencies; this lets you
        override them for channels that aren't true odd-multiple overtones (which
        is what makes Δf/n normalization a no-op when every channel reads n=1).
        """
        def readout(*_):
            return pn.pane.Markdown(
                " · ".join(f"**g{g} → n={n}**" for g, n in sorted(self.orders().items())),
                margin=0, sizing_mode="stretch_width",
            )
        return pn.Card(
            self.orders_text,
            pn.bind(readout, self.orders_text),
            title="Overtone orders (advanced)",
            collapsible=True, collapsed=True, margin=0,
            sizing_mode="stretch_width", css_classes=["qcm-card", "advanced-controls"],
        )

    def mpe_display_panel(self) -> pn.viewable.Viewable:
        return pn.Card(
            pn.pane.HTML("<small>Applies to the Mass-per-electron (MPE) quantity.</small>", margin=0),
            self.mpe_smooth, self.mpe_window,
            self.mpe_clip, self.mpe_clip_lo, self.mpe_clip_hi,
            self.mpe_target_show,
            title="MPE display", collapsible=True, collapsed=True, margin=0,
            sizing_mode="stretch_width", css_classes=["mpe-display"],
        )

    def signal_cleanup_panel(self) -> pn.viewable.Viewable:
        """Despike controls for the resonance traces (f, D, mass, MPE).

        Hampel: only points deviating > 5 robust sigmas from the local rolling
        median are replaced with that median, so steps and real transitions
        survive while relay/bubble spikes vanish.
        """
        return pn.Card(
            pn.pane.HTML("<small>Removes isolated spikes from the QCM traces "
                         "(relay switching, bubbles). Electrochemistry channels "
                         "are never modified.</small>", margin=0),
            self.despike, self.despike_window,
            title="Signal cleanup", collapsible=True, collapsed=True, margin=0,
            sizing_mode="stretch_width", css_classes=["signal-cleanup"],
        )

    def state(self) -> ViewState:
        # The sliders are the canonical source of truth; numeric inputs are kept
        # synchronized with them and are included in ``signal_inputs`` only to
        # trigger reactive updates.
        return ViewState(
            groups=self.selected_groups(),
            quantity=self.quantity_select.value,
            x_axis=self.x_axis_select.value,
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
            overtone_controls=self.overtone_controls_state(),
            params=self.params(),
            mpe_smooth=bool(self.mpe_smooth.value),
            mpe_window=int(self.mpe_window.value or MPE_SMOOTH_WINDOW_DEFAULT),
            mpe_clip=bool(self.mpe_clip.value),
            mpe_clip_lo=self._safe_float(self.mpe_clip_lo.value, MPE_CLIP_LO_DEFAULT),
            mpe_clip_hi=self._safe_float(self.mpe_clip_hi.value, MPE_CLIP_HI_DEFAULT),
            mpe_target_show=bool(self.mpe_target_show.value),
            despike=bool(self.despike.value),
            despike_window=int(self.despike_window.value or DESPIKE_WINDOW_DEFAULT),
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

    def current_range_controls(self, include_save: bool = False, with_slider: bool = True):
        children = []
        if with_slider:
            children.append(self.t_range)
        children += [
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

    def zero_reference_controls(self, with_slider: bool = True):
        children = [pn.bind(self.zero_reference_readout, self.t_range, self.baseline_range)]
        if with_slider:
            children.append(self.baseline_range)
        children.append(self._number_row("reference"))
        return pn.Card(
            *children,
            title="Reference range",
            collapsible=False,
            collapsed=False,
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["plot-controls", "range-editor-card", "reference-range-card"]
        )

    def mark_range_controls(self, with_slider: bool = True):
        children = []
        if with_slider:
            children.append(self.mark_range)
        children += [
            self._number_row("mark"),
            pn.Row(
                self.mark_full_range_button,
                margin=0,
                sizing_mode="stretch_width",
                css_classes=["range-actions"],
            ),
            self.phase_mark_controls(include_card=False),
        ]
        return pn.Card(
            *children,
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
            collapsible=False,
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["phase-mark-card"],
        )

    def active_range_editor(
        self,
        *,
        quantity_key: str | None = None,
        include_save: bool = False,
        with_slider: bool = True,
    ):
        """The single range editor selected by the draw-target control.

        When ``with_slider`` is False the drag handle is omitted here — used when
        the range slider is mounted separately (e.g. directly under the plot).
        """
        def _view(mode: str, qkey: str | None = None):
            if mode == "reference":
                return self.zero_reference_controls(with_slider=with_slider)
            if mode == "mark":
                return self.mark_range_controls(with_slider=with_slider)
            return self.current_range_controls(include_save=include_save, with_slider=with_slider)

        if quantity_key is not None:
            editor = pn.bind(_view, self.brush_mode, quantity_key)
        else:
            editor = pn.bind(_view, self.brush_mode)
        return pn.Column(
            editor,
            self.range_status,
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["plot-controls", "active-range-editor"],
        )

    def plot_range_slider(self):
        """The active-mode range slider, styled to sit flush under the plot.

        Only the slider for the current selection mode is mounted (so the
        ``t_range`` / ``baseline_range`` / ``mark_range`` singletons are never
        double-mounted). The numeric editor lives in the selection bar below.

        The analysis range is a *time* interval, so the slider is shown only on
        the Time axis. On other axes a scrubber would be misleading (potential and
        charge are non-monotonic — the same value recurs every cycle), so a short
        note replaces it: monotonic axes still support drag-to-select, others
        don't.
        """
        def pick(mode, x_axis, *_):
            if x_axis != "time":
                ax = AXES.get(x_axis)
                label = ax.label if ax else x_axis
                drag_ok = bool(ax and ax.monotonic)
                how = ("drag on the plot to select a range, or switch the X-axis to "
                       "Time to scrub here." if drag_ok else
                       f"selection isn't available on the {label} axis (it sweeps back "
                       "and forth); switch the X-axis to Time to set the range.")
                return pn.pane.HTML(
                    f"<div class='qcm-plot-rangenote'>Analysis range is a time window — {how}</div>",
                    margin=0, sizing_mode="stretch_width",
                )
            slider = {"reference": self.baseline_range, "mark": self.mark_range}.get(mode, self.t_range)
            return slider
        return pn.Column(
            pn.bind(pick, self.brush_mode, self.x_axis_select),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-plot-rangeslider"],
        )

    def overtone_controls(self):
        def header(label: str, action=None):
            items = [pn.pane.HTML(f"<span class='ot-col'>{label}</span>", margin=0)]
            if action is not None:
                items.append(action)
            return pn.Column(
                *items,
                margin=0,
                sizing_mode="stretch_width",
                css_classes=["overtone-controls-header-cell"],
            )

        rows = []
        rows.append(
            pn.Row(
                header("Channel"),
                header("Δf", self.overtone_frequency_all_button),
                header("ΔD", self.overtone_dissipation_all_button),
                header("Δf/n", self.overtone_normalize_all_button),
                margin=0,
                sizing_mode="stretch_width",
                css_classes=["overtone-controls-row", "overtone-controls-head"],
            )
        )
        multi_channel = len(self.info.groups) > 1
        for slot, g in enumerate(self.info.groups):
            n = self.info.orders.get(g, 1)
            row_label = f"Ch {slot + 1} · n={n}" if multi_channel else f"n = {n}"
            rows.append(
                pn.Row(
                    pn.pane.HTML(f"<span class='ot-n'>{row_label}</span>", margin=0),
                    self.overtone_frequency[g],
                    self.overtone_dissipation[g],
                    self.overtone_normalize[g],
                    margin=0,
                    sizing_mode="stretch_width",
                    css_classes=["overtone-controls-row"],
                )
            )
        return pn.Card(
            *rows,
            title="Signals",
            collapsible=False,
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["qcm-card", "overtone-controls"],
        )

    # ================================================ redesign: toolbar/selection
    def _refresh_right_axis_options(self, _event=None) -> None:
        """Right-axis menu = None + every available quantity except the left one."""
        left = self.quantity_select.value
        options = {"None (single axis)": "__none__"}
        options.update({label: key for label, key in self._quantity_options.items() if key != left})
        current = self.quantity_select_right.value
        self.quantity_select_right.options = options
        if current not in options.values():
            self.quantity_select_right.value = "__none__"

    def _apply_right_axis_enabled(self, _event=None) -> None:
        """The twin axis is a vs-time comparison; disable it on cross-plots."""
        is_time = self.x_axis_select.value == "time"
        self.quantity_select_right.disabled = not is_time
        if not is_time:
            self.quantity_select_right.value = "__none__"

    @staticmethod
    def _toolcell(eyebrow: str, widget, *, grow: bool = False):
        from html import escape
        classes = ["qcm-toolcell"] + (["grow"] if grow else [])
        return pn.Column(
            pn.pane.HTML(f"<div class='eyebrow'>{escape(eyebrow)}</div>", margin=0),
            widget,
            margin=0, sizing_mode="stretch_width", css_classes=classes,
        )

    def data_toolbar(self, include_cycles: bool = False):
        """Horizontal control strip shown above the hero plot on the Data page."""
        toggle_items = [self.show_phases, self.zero_line]
        if include_cycles:
            toggle_items.append(self.show_cycles)
        toggles = pn.Column(
            pn.pane.HTML("<div class='eyebrow'>Display</div>", margin=0),
            pn.Row(*toggle_items, margin=0, css_classes=["qcm-tooltoggles"]),
            margin=0, css_classes=["qcm-toolcell", "qcm-toolcell-display"],
        )
        return pn.Row(
            self._toolcell("X-axis", self.x_axis_select),
            self._toolcell("Y-axis (left)", self.quantity_select, grow=True),
            self._toolcell("Y-axis (right)", self.quantity_select_right, grow=True),
            toggles,
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-toolbar2"],
        )

    def selection_cards(self):
        """Bottom selection bar: mode buttons (left) + the editable range editor (right).

        The range is set/viewed in exactly two complementary places — the slider
        flush under the plot (drag) and this editor (precise entry) — so there is
        no read-only duplicate of Start/End.
        """
        explainer = pn.pane.HTML(
            "<div class='qcm-mode-help'>"
            "<div class='r'><span class='b'>Analysis range</span>"
            "<span>the window used for plots, statistics &amp; export.</span></div>"
            "<div class='r'><span class='b'>Reference range</span>"
            "<span>the baseline subtracted from Δ (referenced) signals.</span></div>"
            "<div class='r'><span class='b'>Mark range</span>"
            "<span>a span you can save as a labeled phase.</span></div>"
            "<div class='tip'>Set a range three ways — drag on the plot, the slider "
            "beneath it, or the Start / End boxes. They all edit the same window.</div>"
            "</div>",
            margin=0, sizing_mode="stretch_width",
        )
        left = pn.Column(
            pn.pane.HTML("<div class='eyebrow'>Selection mode</div>", margin=0),
            self.brush_mode,
            pn.bind(self.draw_mode_status, self.brush_mode),
            explainer,
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-selmode"],
        )
        # The editor already shows Start / End / Duration inline, so no separate
        # duration chip here (it was a redundant readout of the same value).
        right = pn.Column(
            pn.pane.HTML("<div class='eyebrow'>Selected range</div>", margin=0),
            self.active_range_editor(quantity_key=self.quantity_select, with_slider=False),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-selread-col"],
        )
        return pn.Column(
            pn.Row(left, right, margin=0, sizing_mode="stretch_width", css_classes=["qcm-selrow"]),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-selection"],
        )
