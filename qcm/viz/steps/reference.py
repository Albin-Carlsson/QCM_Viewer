"""Reference step: define the zero/reference window for Δ quantities."""
from __future__ import annotations

from dataclasses import replace

import panel as pn

from .. import plots
from ..components import hint
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
            )
            return self.interactive_plot(plot)
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Reference plot failed: {exc}", alert_type="danger")

    def view(self):
        guidance = hint(
            "Drag on the plot or edit the numbers to choose a quiet, stable window. "
            "Δf, Δf/n, ΔD and Sauerbrey mass are measured relative to this window.",
            tone="info",
        )
        controls = pn.Column(
            self.controls.zero_reference_controls(),
            margin=0, sizing_mode="stretch_width", css_classes=["compact-section"],
        )
        return pn.Column(
            guidance,
            self.panel(
                self.reference_plot, *self.controls.signal_inputs, self.controls.plot_reset_version,
                title="Reference window", controls=controls, controls_position="top",
            ),
            margin=0, sizing_mode="stretch_width", css_classes=["workbench-page", "viewer-page"],
        )
