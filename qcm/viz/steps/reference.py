"""Reference step: define the zero/reference window for Δ quantities."""
from __future__ import annotations

from dataclasses import replace

import panel as pn

from .. import plots
from ..components import hint
from ..theme import HERO_HEIGHT
from ._base import BaseStep


class ReferenceStep(BaseStep):
    def reference_plot(self):
        try:
            state = self.controls.state()
            full = replace(state, t_range_s=(0.0, float(self.data.info.span_s)))
            norm_df, d_df = self.data.qcmd_frames(full)
            plot = plots.dual_axis_qcmd(
                norm_df, d_df, full.groups, full.orders, "Pick the reference window",
                baseline=state.baseline_s,
                annotation_spans=self.data.annotation_spans(state),
                window=state.baseline_s, select_x=True,
                height=HERO_HEIGHT,
            )
            return self.interactive_plot(self.force_plot_height(plot, HERO_HEIGHT))
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Reference plot failed: {exc}", alert_type="danger")

    def compact_reference_controls(self):
        return pn.Row(
            pn.Column(
                self.controls.plot_tools_row(include_quantity=False),
                self.controls.zero_reference_controls(),
                margin=0,
                sizing_mode="stretch_width",
            ),
            width_policy="max",
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["compact-two-column", "reference-controls-row"],
        )

    def view(self):
        guidance = hint(
            "Drag on the plot or edit the numbers to choose a quiet, stable reference window.",
            tone="info",
        )
        return pn.Column(
            guidance,
            self.panel(
                self.reference_plot, *self.controls.signal_inputs, self.controls.plot_reset_version,
                title="Reference window", controls=self.compact_reference_controls(),
                controls_position="bottom", collapsible=False,
            ),
            margin=0, sizing_mode="stretch_width", css_classes=["workbench-page", "viewer-page"],
        )
