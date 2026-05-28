"""Panel controls for the simplified QCM viewer."""
from __future__ import annotations

import panel as pn

from .state import RunInfo, ViewState, parse_orders
from .theme import QUANTITIES, quantity

_QUANTITY_OPTIONS = {q.label: key for key, q in QUANTITIES.items()}
_REGION_TYPES = {
    "Artifact / bad data": "artifact",
    "Experiment step": "phase",
    "Interesting region": "note",
    "Exclude later": "exclude",
}

_CHANNEL_TOGGLE_CSS = """
.bk-btn-group {
  display: grid !important;
  grid-template-columns: 1fr !important;
  gap: 6px !important;
  width: 100% !important;
}
.bk-btn {
  width: 100% !important;
  justify-content: flex-start !important;
  text-align: left !important;
  white-space: normal !important;
  border: 1px solid #334155 !important;
  background-color: #111827 !important;
  background-image: none !important;
  color: #64748b !important;
  opacity: 1 !important;
  box-shadow: none !important;
  filter: grayscale(1) saturate(0.15) !important;
}
.bk-btn:hover {
  border-color: #64748b !important;
  color: #cbd5e1 !important;
}
.bk-btn.bk-active {
  border-color: #7dd3fc !important;
  background-color: #0284c7 !important;
  background-image: none !important;
  color: #f8fafc !important;
  opacity: 1 !important;
  font-weight: 700 !important;
  filter: none !important;
  box-shadow: inset 3px 0 0 #bae6fd, 0 0 0 1px rgba(125, 211, 252, 0.35) !important;
}
"""


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
        self._build_widgets()

    def _build_widgets(self) -> None:
        group_options = {
            _channel_label(slot, g, self.info.orders.get(g, 1)): str(g)
            for slot, g in enumerate(self.info.groups)
        }
        saved_groups = [str(g) for g in self.saved.get("groups", self.info.groups) if g in self.info.groups]
        default_orders = ", ".join(f"g{g}:n={n}" for g, n in sorted(self.info.orders.items()))
        step = max(self.info.span_s / 10_000, 0.001)
        fmt = "0,0.000" if self.info.span_s >= 1000 else "0.000"

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
            name="Show all",
            button_type="default",
            icon="eye",
            sizing_mode="stretch_width",
        )
        self.show_all_channels_button.on_click(self.show_all_channels)
        self.t_range = pn.widgets.EditableRangeSlider(
            name="Current range (s)",
            start=0.0,
            end=self.info.span_s,
            value=tuple(self.saved.get("t_range_s", [0.0, self.info.span_s])),
            step=step,
            format=fmt,
            sizing_mode="stretch_width",
        )
        self.baseline_range = pn.widgets.EditableRangeSlider(
            name="Zero/reference range (s)",
            start=0.0,
            end=self.info.span_s,
            value=tuple(self.saved.get("baseline_s", [0.0, min(self.info.span_s, self.info.span_s * 0.1)])),
            step=step,
            format=fmt,
            sizing_mode="stretch_width",
        )
        self.quantity_select = pn.widgets.Select(
            name="Quantity",
            options=_QUANTITY_OPTIONS,
            value=self.saved.get("quantity", "sauerbrey_mass"),
            sizing_mode="stretch_width",
        )

        self.sequence = pn.widgets.IntSlider(
            name="Sweep number",
            start=self.info.seq_min,
            end=max(self.info.seq_max, self.info.seq_min),
            value=int(self.saved.get("sequence", self.info.seq_min)),
            step=1,
            sizing_mode="stretch_width",
        )
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
            name="Type",
            options=_REGION_TYPES,
            value="artifact",
            sizing_mode="stretch_width",
        )
        self.region_label = pn.widgets.TextInput(
            name="Name",
            placeholder="artifact / rinse / sample added",
            sizing_mode="stretch_width",
        )
        # Backward-compatible aliases for older action/page code.
        self.marker_type = self.region_type
        self.marker_label = self.region_label

        self.mark_point_button = pn.widgets.Button(
            name="Mark current time",
            button_type="default",
            icon="map-pin",
            sizing_mode="stretch_width",
        )
        self.mark_window_button = pn.widgets.Button(
            name="Save current range",
            button_type="primary",
            icon="brackets-contain",
            sizing_mode="stretch_width",
        )
        self.marker_select = pn.widgets.Select(
            name="Notebook region",
            options={"Current range": "__current__"},
            value="__current__",
            sizing_mode="stretch_width",
        )

        self.use_selection_as_baseline = pn.widgets.Button(
            name="Set zero = current range",
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
        self.status = pn.pane.Alert("Ready.", alert_type="light", sizing_mode="stretch_width")

    @property
    def signal_inputs(self) -> tuple:
        # Range sliders trigger on ``value_throttled`` so dragging fires a single
        # query on release instead of one per mouse-move. ``state()`` still reads
        # each widget's live ``.value`` at render time, so the snapshot is current.
        return (
            self.group_select,
            self.orders_text,
            self.t_range.param.value_throttled,
            self.baseline_range.param.value_throttled,
            self.annotation_version,
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

    def orders_readout(self, *_):
        return pn.pane.Markdown(" · ".join(f"**g{g} → n={n}**" for g, n in sorted(self.orders().items())))

    def current_range_controls(self):
        return pn.Column(
            pn.pane.Markdown(
                "<small><b>Current range</b> is the time span you are working on. "
                "Plots, statistics, data export, and notebook export use this range.</small>",
                margin=0,
                sizing_mode="stretch_width",
            ),
            self.t_range,
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["plot-controls"],
        )

    def current_range_compact(self):
        return pn.Column(
            self.t_range,
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["plot-controls", "compact-range-controls"],
        )

    def zero_reference_readout(self, *_):
        c0, c1 = (float(v) for v in self.t_range.value)
        z0, z1 = (float(v) for v in self.baseline_range.value)
        same = abs(c0 - z0) < 1e-9 and abs(c1 - z1) < 1e-9
        suffix = " <b>(same as current range)</b>" if same else ""
        return pn.pane.Markdown(
            f"<small>Current range: <b>{c0:,.3f}–{c1:,.3f} s</b><br>"
            f"Zero/reference: <b>{z0:,.3f}–{z1:,.3f} s</b>{suffix}<br>"
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
            f"<small>Current: <b>{c0:,.3f}–{c1:,.3f} s</b> · "
            f"Zero/reference: <b>{z0:,.3f}–{z1:,.3f} s</b>{suffix}</small>",
            margin=0,
            sizing_mode="stretch_width",
        )

    def zero_reference_controls(self):
        return pn.Column(
            pn.pane.Markdown(
                "<small><b>Zero/reference range</b> is the quiet interval that should count as zero "
                "for Δ-values. "
                "It does <b>not</b> move, crop, save, or label the current range.</small>",
                margin=0,
                sizing_mode="stretch_width",
            ),
            pn.bind(self.zero_reference_readout, self.t_range, self.baseline_range),
            self.baseline_range,
            pn.Row(
                self.use_selection_as_baseline,
                self.revert_baseline,
                margin=0,
                sizing_mode="stretch_width",
            ),
            pn.pane.Markdown(
                "<small>Press <b>Set zero = current range</b> after selecting a stable reference period. "
                "Then move the current range anywhere else to inspect the experiment relative to that zero."
                "</small>",
                margin=0,
                sizing_mode="stretch_width",
            ),
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["plot-controls"],
        )

    def zero_reference_compact(self, quantity_key: str | None = None):
        key = quantity_key or self.quantity_select.value
        if not quantity(key).referenced:
            return pn.pane.Markdown(
                "<small>Absolute quantity; no zero/reference range is used.</small>",
                margin=0,
                sizing_mode="stretch_width",
            )
        return pn.Column(
            self.baseline_range,
            pn.Row(
                self.use_selection_as_baseline,
                self.revert_baseline,
                margin=0,
                sizing_mode="stretch_width",
                css_classes=["range-actions"],
            ),
            pn.bind(self.zero_reference_summary, self.t_range, self.baseline_range),
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["plot-controls", "compact-reference-controls"],
        )

    def paired_range_controls(self, extra_class: str):
        """Compact range block with current and zero/reference sliders side by side."""
        return pn.Column(
            pn.Row(
                self.t_range,
                self.baseline_range,
                margin=0,
                sizing_mode="stretch_width",
                css_classes=["range-row"],
            ),
            pn.Row(
                self.use_selection_as_baseline,
                self.revert_baseline,
                margin=0,
                sizing_mode="stretch_width",
                css_classes=["range-actions"],
            ),
            pn.bind(self.zero_reference_summary, self.t_range, self.baseline_range),
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["plot-controls", "paired-ranges", extra_class],
        )

    def overview_range_controls(self):
        return self.paired_range_controls("overview-ranges")

    def analyze_range_controls(self):
        return self.paired_range_controls("analyze-ranges")

    def zero_reference_if_needed(self, quantity_key: str | None = None):
        key = quantity_key or self.quantity_select.value
        if not quantity(key).referenced:
            return pn.pane.Markdown(
                "<small>This quantity is absolute/raw, so no zero/reference range is needed.</small>",
                margin=0,
                sizing_mode="stretch_width",
            )
        return self.zero_reference_controls()

    def window_controls(self, include_zero_reference: bool = True):
        items = [self.current_range_controls()]
        if include_zero_reference:
            items.append(self.zero_reference_controls())
        return pn.Column(*items, margin=0, sizing_mode="stretch_width", css_classes=["plot-controls"])
