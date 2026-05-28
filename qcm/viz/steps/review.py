"""Review step: full-run QCM-D overview and current-range selection."""
from __future__ import annotations

from dataclasses import replace

import panel as pn
from ..components import hint

from .. import plots
from ..theme import HERO_HEIGHT
from ._base import BaseStep


class ReviewStep(BaseStep):
    def hero_plot(self):
        try:
            state = self.controls.state()
            full = replace(state, t_range_s=(0.0, float(self.data.info.span_s)))
            norm_df, d_df = self.data.qcmd_frames(full)
            plot = plots.dual_axis_qcmd(
                norm_df,
                d_df,
                full.groups,
                full.orders,
                "QCM-D overview",
                baseline=state.baseline_s,
                annotation_spans=self.data.annotation_spans(state),
                window=state.t_range_s,
                select_x=True,
                height=HERO_HEIGHT,
            )
            plot = self.with_phase_labels(plot, norm_df, height=HERO_HEIGHT)
            return self.interactive_plot(self.force_plot_height(plot, HERO_HEIGHT))
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"QCM-D plot failed: {exc}", alert_type="danger")

    def compact_review_controls(self):
        return pn.Row(
            pn.Column(
                self.controls.plot_tools_row(include_quantity=False),
                self.controls.overview_range_controls(include_reset=False),
                margin=0,
                sizing_mode="stretch_width",
                css_classes=["review-range-stack"],
            ),
            pn.Column(
                pn.bind(lambda *_: self.current_range_summary_cards(), *self.controls.signal_inputs),
                width=430,
                sizing_mode="fixed",
                margin=0,
                css_classes=["review-summary-stack"],
            ),
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["compact-two-column", "review-controls-summary"],
        )

    def view(self):
        # Review only controls the current analysis range. Reference and phase
        # marking live on their own pages to keep this page visually focused.
        guidance = hint(
            "Inspect the full experiment and choose the time range you want to analyze.",
            tone="info",
        )
        return pn.Column(
            guidance,
            self.panel(
                self.hero_plot,
                *self.controls.signal_inputs,
                self.controls.plot_reset_version,
                title="QCM-D overview",
                controls=self.compact_review_controls(),
                controls_position="bottom",
                collapsible=False,
            ),
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["workbench-page", "viewer-page", "review-page"],
        )
