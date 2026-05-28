"""Review step: full-run QCM-D overview and range selection."""
from __future__ import annotations

from dataclasses import replace

import panel as pn

from .. import plots
from ._base import BaseStep


class ReviewStep(BaseStep):
    def hero_plot(self):
        try:
            state = self.controls.state()
            full = replace(state, t_range_s=(0.0, float(self.data.info.span_s)))
            norm_df, d_df = self.data.qcmd_frames(full)
            plot = plots.dual_axis_qcmd(
                norm_df, d_df, full.groups, full.orders, "QCM-D overview",
                baseline=state.baseline_s,
                annotation_spans=self.data.annotation_spans(state),
                window=state.t_range_s, select_x=True,
            )
            plot = self.with_phase_labels(plot, norm_df)
            return self.interactive_plot(plot)
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"QCM-D plot failed: {exc}", alert_type="danger")

    def view(self):
        controls = pn.Column(
            self.controls.overview_range_controls(),
            margin=0, sizing_mode="stretch_width", css_classes=["compact-section"],
        )
        return pn.Column(
            self.panel(
                self.hero_plot, *self.controls.signal_inputs, self.controls.plot_reset_version,
                title="QCM-D overview", controls=controls, controls_position="top",
            ),
            self.panel(self.current_range_summary_cards, *self.controls.signal_inputs, title="Current range"),
            margin=0, sizing_mode="stretch_width", css_classes=["workbench-page", "viewer-page"],
        )
