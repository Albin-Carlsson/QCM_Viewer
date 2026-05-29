"""Quantify step: selected-quantity timeline, statistics, and fingerprint."""
from __future__ import annotations

from dataclasses import replace

import panel as pn
import polars as pl

from .. import plots, science
from ..components import hint
from ..nav import needs_reference_hint
from ..theme import COMPACT_PLOT_HEIGHT, PLOT_HEIGHT, quantity
from ._base import BaseStep


class QuantifyStep(BaseStep):
    """Quantity plot, focused statistics, and fingerprint analysis."""

    def target_state(self):
        """Return the ViewState for the selected Quantify analysis target.

        Current range uses the live slider. A saved marker produces a temporary
        state whose time range is exactly the marker. This keeps target switching
        local to Quantify and avoids permanently overwriting the current range.
        """
        state = self.controls.state()
        selected = self.controls.analysis_region_select.value
        if not selected or selected == "__current__":
            return state
        for ann in self.data.annotations():
            if ann.id == selected and ann.type == "range" and ann.t1 is not None:
                start_s = (ann.t0 - self.data.info.t0_us) / 1_000_000
                end_s = (ann.t1 - self.data.info.t0_us) / 1_000_000
                return replace(state, t_range_s=(float(start_s), float(end_s)))
        return state

    def selected_target_summary_table(self):
        try:
            state = self.target_state()
            summary = self.data.region_summary(state)
            if summary.is_empty():
                return self.empty_state("No data in the selected analysis target.")
            cols = [c for c in ["df_n", "dD", "mass", "Q", "dD_per_df"] if c in summary.columns]
            means = summary.select([pl.col(c).mean().alias(c) for c in cols]).to_dicts()[0]
            start, end = state.t_range_s
            duration = max(0.0, float(end) - float(start))
            rows = [
                ("Range", f"{duration:,.2f} s", f"{start:,.2f}–{end:,.2f} s"),
                ("Mean Δf/n", self._fmt(means.get("df_n"), 2, " Hz"), ""),
                ("Mean ΔD", self._fmt(means.get("dD"), 3, " ×10⁻⁶"), ""),
                ("Mass", self._fmt(means.get("mass"), 1, " ng/cm²"), ""),
                ("Mean Q", self._fmt(means.get("Q"), 0), ""),
                ("ΔD/Δf", self._fmt(means.get("dD_per_df"), 4), ""),
            ]
            table = pl.DataFrame(rows, schema=["Metric", "Value", "Range"], orient="row")
            return pn.widgets.Tabulator(
                table.to_pandas(),
                height=168,
                layout="fit_data_fill",
                show_index=False,
                sizing_mode="stretch_width",
                disabled=True,
                css_classes=["summary-table", "target-summary-table"],
            )
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Target summary failed: {exc}", alert_type="danger")

    def quantity_plot(self):
        try:
            state = self.target_state()
            value_df, elapsed = self.data.value_df(state)
            q = quantity(state.quantity)
            title = f"{q.label} · {value_df.height:,} points · {elapsed:.0f} ms"
            plot = plots.timeline(
                value_df,
                q,
                state.groups,
                state.orders,
                title,
                height=PLOT_HEIGHT,
                annotation_spans=self.data.annotation_spans(state),
                baseline=state.baseline_s if q.referenced else None,
                select_x=True,
            )
            plot = self.with_phase_labels(plot, value_df, height=PLOT_HEIGHT)
            return self.interactive_plot(self.force_plot_height(plot, PLOT_HEIGHT))
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Quantity plot failed: {exc}", alert_type="danger")

    def _stats(self):
        state = self.target_state()
        value_df, elapsed = self.data.value_df(state)
        stats = science.summary_stats(value_df.select(["timestamp", "group", "value"]))
        if stats.is_empty():
            return stats, quantity(state.quantity), elapsed
        q = quantity(state.quantity)
        stats = stats.with_columns(
            pl.lit(q.label).alias("quantity"),
            pl.lit(q.unit or "—").alias("unit"),
            pl.lit(round(elapsed, 1)).alias("compute_ms"),
        )
        return stats, q, elapsed

    def summary_stats_table(self):
        try:
            stats, _q, _elapsed = self._stats()
            if stats.is_empty():
                return pn.pane.Markdown("No statistics for the current range.")
            ordered = [
                "group", "quantity", "unit", "rows", "valid", "duration_s",
                "first", "last", "net_change", "slope_per_s",
                "mean", "median", "std", "min", "max", "range",
            ]
            stats = stats.select([c for c in ordered if c in stats.columns])
            return pn.widgets.Tabulator(
                stats.to_pandas(),
                height=min(170, max(90, 34 + stats.height * 24)),
                layout="fit_data_fill",
                show_index=False,
                sizing_mode="stretch_width",
                disabled=True,
            )
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Stats failed: {exc}", alert_type="danger")

    def full_stats_table(self):
        try:
            stats, _q, _elapsed = self._stats()
            if stats.is_empty():
                return pn.pane.Markdown("No statistics for the current range.")
            ordered = [
                "group", "quantity", "unit", "rows", "valid", "missing", "duration_s",
                "first", "last", "net_change", "abs_net_change", "slope_per_s",
                "mean", "median", "std", "variance", "sem", "cv", "min", "q01", "q05", "q10",
                "q25", "q75", "q90", "q95", "q99", "max", "range", "iqr",
                "mean_abs", "rms", "mean_abs_step", "step_std", "sum", "sum_abs", "compute_ms",
            ]
            stats = stats.select([c for c in ordered if c in stats.columns])
            return pn.widgets.Tabulator(
                stats.to_pandas(),
                height=min(210, max(100, 34 + stats.height * 24)),
                layout="fit_data_fill",
                show_index=False,
                sizing_mode="stretch_width",
                disabled=True,
            )
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Advanced stats failed: {exc}", alert_type="danger")

    def region_readout(self):
        try:
            state = self.target_state()
            summary = self.data.region_summary(state)
            if summary.is_empty():
                return pn.pane.Markdown("No data in the current range.")
            return self._summary_tabulator(summary, ["group", "n", "df_n", "dD", "mass", "Q", "dD_per_df"])
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Readout failed: {exc}", alert_type="danger")

    def df_plot(self):
        try:
            state = self.target_state()
            norm_df, d_df = self.data.qcmd_frames(state)
            return self.nearest_hover(self.force_plot_height(plots.df_fingerprint(norm_df, d_df, state.groups, state.orders), COMPACT_PLOT_HEIGHT))
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Fingerprint plot failed: {exc}", alert_type="danger")

    def _reference_hint(self):
        state = self.controls.state()
        q = quantity(state.quantity)
        if needs_reference_hint(q.referenced, state.baseline_s, float(self.data.info.span_s)):
            return hint(
                "This is a Δ quantity but no reference window is set yet — "
                "go to <b>② Reference</b> to define zero.",
                tone="warning",
            )
        return pn.Spacer(height=0)

    def anchor_plot(self):
        return self.quantity_plot()

    def secondary_panel(self):
        hint_block = pn.bind(lambda *_: self._reference_hint(), *self.controls.explore_inputs)
        target = pn.Column(
            self.controls.analysis_region_select,
            pn.bind(lambda *_: self.selected_target_summary_table(),
                    *self.controls.explore_inputs,
                    self.controls.analysis_region_select, self.controls.annotation_version),
            margin=0, sizing_mode="stretch_width", css_classes=["analysis-target-stack"],
        )
        stats = pn.Column(
            self.panel(self.summary_stats_table, *self.controls.explore_inputs, title="Statistics"),
            self.panel(self.region_readout, *self.controls.explore_inputs, title="Per-channel readout"),
            self.panel(self.df_plot, *self.controls.explore_inputs,
                       self.controls.plot_reset_version, title="ΔD vs Δf/n"),
            self.panel(self.full_stats_table, *self.controls.explore_inputs, title="Advanced statistics"),
            margin=0, sizing_mode="stretch_width",
        )
        return pn.Column(hint_block, target, stats, margin=0,
                         sizing_mode="stretch_width", css_classes=["qcm-secondary"])
