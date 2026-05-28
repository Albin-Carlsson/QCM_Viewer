"""Phases step: mark, save, and compare experiment phases."""
from __future__ import annotations

from dataclasses import replace

import panel as pn
import polars as pl
from ..components import hint

from .. import plots
from ..theme import PLOT_HEIGHT, quantity
from ._base import BaseStep

_US = 1_000_000


class PhasesStep(BaseStep):
    """Saved phase statistics and data-science tables."""

    def phase_plot(self):
        try:
            state = self.controls.state()
            full = replace(state, t_range_s=(0.0, float(self.data.info.span_s)))
            value_df, elapsed = self.data.value_df(full)
            q = quantity(full.quantity)
            title = f"Mark phases on {q.label} · {value_df.height:,} points · {elapsed:.0f} ms"
            plot = plots.timeline(
                value_df,
                q,
                full.groups,
                full.orders,
                title,
                height=PLOT_HEIGHT,
                annotation_spans=self.data.annotation_spans(state),
                baseline=state.baseline_s if q.referenced else None,
                window=tuple(float(v) for v in self.controls.mark_range.value),
                select_x=True,
            )
            plot = self.with_phase_labels(plot, value_df, height=PLOT_HEIGHT)
            return self.interactive_plot(self.force_plot_height(plot, PLOT_HEIGHT))
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Phase plot failed: {exc}", alert_type="danger")

    def phases_table(self):
        _ = self.controls.annotation_version.value
        anns = self.data.annotations()
        self.actions.refresh_marker_options()
        if not anns:
            return self.empty_state("No phases saved.")
        rows = []
        for a in anns:
            start_s = (a.t0 - self.data.info.t0_us) / _US
            end_s = ((a.t1 or a.t0) - self.data.info.t0_us) / _US
            rows.append(
                {
                    "name": a.label,
                    "type": a.tags[0] if a.tags else "phase",
                    "shape": "range" if a.type == "range" else "event",
                    "start_s": round(start_s, 3),
                    "end_s": round(end_s, 3),
                    "duration_s": round(max(0.0, end_s - start_s), 3),
                    "channels": ", ".join(str(g) for g in (a.groups or [])) or "all",
                }
            )
        table = pn.widgets.Tabulator(
            pl.DataFrame(rows).to_pandas(),
            height=min(300, max(120, 42 + len(rows) * 30)),
            show_index=False,
            layout="fit_data_fill",
            buttons={"delete": '<i class="fa fa-trash"></i>'},
            sizing_mode="stretch_width",
        )
        table.on_click(self._on_phase_action)
        return table

    def _on_phase_action(self, event) -> None:
        if getattr(event, "column", None) == "delete":
            self.actions.delete_annotation_by_row(event.row)

    def phase_matrix(self):
        try:
            df = self.data.regions_comparison(self.controls.state())
            if df.is_empty():
                return self.empty_state("No range phases to analyze.")
            return self._summary_tabulator(
                df,
                ["region", "duration_s", "group", "n", "df_n", "dD", "mass", "Q", "dD_per_df"],
                height=min(360, max(120, 42 + df.height * 30)),
            )
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Phase matrix failed: {exc}", alert_type="danger")

    def phase_rollup(self):
        try:
            df = self.data.regions_comparison(self.controls.state())
            if df.is_empty():
                return self.empty_state("No range phases to summarize.")
            aggs = [
                pl.col("duration_s").first().alias("duration_s"),
                pl.col("group").n_unique().alias("channel_count"),
            ]
            for col in ["df_n", "dD", "mass", "Q", "dD_per_df"]:
                if col in df.columns:
                    aggs.extend([
                        pl.col(col).mean().alias(f"{col}_mean"),
                        pl.col(col).std().alias(f"{col}_std"),
                    ])
            out = df.group_by("region").agg(aggs).sort("region")
            return self._summary_tabulator(
                out,
                [
                    "region", "duration_s", "channel_count",
                    "df_n_mean", "df_n_std", "dD_mean", "dD_std",
                    "mass_mean", "mass_std", "Q_mean", "dD_per_df_mean",
                ],
                height=min(300, max(120, 42 + out.height * 30)),
            )
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Phase rollup failed: {exc}", alert_type="danger")

    def phase_response_ranking(self):
        try:
            df = self.data.regions_comparison(self.controls.state())
            if df.is_empty() or "df_n" not in df.columns:
                return self.empty_state("No response ranking available.")
            out = (
                df.group_by("region")
                .agg(
                    pl.col("duration_s").first().alias("duration_s"),
                    pl.col("df_n").abs().mean().alias("abs_df_n_mean"),
                    pl.col("mass").abs().mean().alias("mass_mean") if "mass" in df.columns else pl.lit(None).alias("mass_mean"),
                    pl.col("dD").mean().alias("dD_mean") if "dD" in df.columns else pl.lit(None).alias("dD_mean"),
                )
                .with_columns((pl.col("abs_df_n_mean") * pl.col("duration_s")).alias("response_rank"))
                .sort("response_rank", descending=True)
            )
            return self._summary_tabulator(
                out,
                ["region", "duration_s", "abs_df_n_mean", "mass_mean", "dD_mean", "response_rank"],
                height=min(300, max(120, 42 + out.height * 30)),
            )
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Phase ranking failed: {exc}", alert_type="danger")

    def compact_phase_controls(self):
        # Saved phases used to sit in a narrow right column, which made the
        # table feel detached from the phase-marking workflow. Keep everything
        # left-to-right and then place the saved-phase table directly below the
        # mark controls so the reading order is: tools -> mark -> saved phases.
        return pn.Column(
            self.controls.plot_tools_row(include_quantity=True),
            self.controls.mark_range_controls(),
            pn.bind(lambda *_: self.phases_table(), self.controls.annotation_version),
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["phase-control-stack", "phase-controls-saved", "compact-panel"],
        )

    def view(self):
        guidance = hint(
            "Mark important experimental regions such as injections, rinses, equilibrations, or artifacts. Saved phases can later be analyzed individually in Quantify and included in reports/exported notebooks.",
            tone="info",
        )
        lower = pn.Row(
            self.panel(self.phase_rollup, *self.controls.explore_inputs, title="Phase rollup", collapsible=False),
            self.panel(self.phase_response_ranking, *self.controls.explore_inputs, title="Response ranking", collapsible=False),
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["compact-two-column", "phase-analysis-row"],
        )
        return pn.Column( guidance,
            self.panel(
                self.phase_plot,
                *self.controls.explore_inputs,
                self.controls.mark_range.param.value_throttled,
                self.controls.mark_start,
                self.controls.mark_end,
                self.controls.annotation_version,
                self.controls.plot_reset_version,
                title="Phase marking plot",
                controls=self.compact_phase_controls(),
                controls_position="bottom",
                collapsible=False,
            ),
            lower,
            self.panel(self.phase_matrix, *self.controls.explore_inputs, title="Per-channel phase matrix", collapsible=False),
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["workbench-page", "viewer-page", "phases-page"],
        )
