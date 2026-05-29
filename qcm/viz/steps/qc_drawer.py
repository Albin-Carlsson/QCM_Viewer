"""QC drawer: raw-sweep, I/Q, and waterfall inspection (overlay)."""
from __future__ import annotations

import panel as pn

from .. import plots
from ..components import stat_badge
from ._base import BaseStep


class QCDrawer(BaseStep):
    """Raw sweep inspection for fits and artifact checks."""

    def sweep_readout(self):
        return pn.pane.Markdown(self.data.sequence_readout(self.controls.sequence.value))

    def sweep_plot(self):
        try:
            state = self.controls.state()
            panels = [self.nearest_hover(p) for p in plots.sweep_curves(self.data.sweep_df(state), orders=state.orders)]
            return pn.Column(*panels, sizing_mode="stretch_width")
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Sweep failed: {exc}", alert_type="danger")

    def iq_plot(self):
        try:
            state = self.controls.state()
            return self.nearest_hover(plots.iq_scatter(self.data.sweep_df(state), f"I/Q at sweep {state.sequence}"))
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"I/Q failed: {exc}", alert_type="danger")

    def waterfall_plot(self):
        try:
            state = self.controls.state()
            panels = [self.interactive_plot(p) for p in plots.waterfall(self.data.waterfall_df(state), orders=state.orders)]
            return pn.Column(*panels, sizing_mode="stretch_width")
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Waterfall failed: {exc}", alert_type="danger")

    def qc_cards(self):
        state = self.controls.state()
        selected = len(state.selected_sweep_groups())
        return pn.Row(
            stat_badge("Sweep", str(int(state.sequence)), tone="accent"),
            stat_badge("Channels", str(selected)),
            stat_badge("Frequency band", f"{state.frequency_band[0]:,.1f}–{state.frequency_band[1]:,.1f} Hz"),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-metric-strip"],
        )

    def view(self):
        controls = pn.Card(
            self.controls.sequence,
            pn.Row(self.controls.previous_sweep_button, self.controls.next_sweep_button, margin=0, sizing_mode="stretch_width"),
            pn.bind(lambda *_: self.sweep_readout(), self.controls.sequence),
            self.controls.sweep_mode,
            self.controls.group_for_single,
            self.controls.plot_reset_button(),
            title="Sweep controls",
            collapsible=True,
            collapsed=False,
            margin=0,
            sizing_mode="stretch_width",
        )
        waterfall_controls = pn.Card(
            self.controls.frequency_band,
            title="Waterfall controls",
            collapsible=True,
            collapsed=False,
            margin=0,
            sizing_mode="stretch_width",
        )
        return pn.Column(
            controls,
            pn.bind(lambda *_: self.qc_cards(), *self.controls.sweep_inputs, self.controls.waterfall_band_input),
            self.panel(self.sweep_plot, *self.controls.sweep_inputs, self.controls.plot_reset_version, title="Resonance curves"),
            self.panel(self.iq_plot, *self.controls.sweep_inputs, self.controls.plot_reset_version, title="I/Q scatter"),
            self.panel(
                self.waterfall_plot,
                *self.controls.signal_inputs,
                self.controls.waterfall_band_input,
                self.controls.plot_reset_version,
                title="Waterfall",
                controls=waterfall_controls,
            ),
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["workbench-page", "viewer-page"],
        )
