"""Quantify step: selected-quantity timeline, statistics, and fingerprint."""
from __future__ import annotations

import panel as pn
import polars as pl

from .. import plots, science
from ..components import hint
from ..nav import needs_reference_hint
from ..theme import quantity
from ._base import BaseStep


class QuantifyStep(BaseStep):
    """Quantity plot, focused statistics, and fingerprint analysis."""

    def quantity_plot(self):
        try:
            state = self.controls.state()
            value_df, elapsed = self.data.value_df(state)
            q = quantity(state.quantity)
            title = f"{q.label} · {value_df.height:,} points · {elapsed:.0f} ms"
            plot = plots.timeline(
                value_df,
                q,
                state.groups,
                state.orders,
                title,
                height=300,
                annotation_spans=self.data.annotation_spans(state),
                baseline=state.baseline_s if q.referenced else None,
                select_x=True,
            )
            plot = self.with_phase_labels(plot, value_df)
            return self.interactive_plot(plot)
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Quantity plot failed: {exc}", alert_type="danger")

    def _stats(self):
        state = self.controls.state()
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
                height=min(320, max(120, 48 + stats.height * 34)),
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
                height=min(440, max(120, 48 + stats.height * 34)),
                layout="fit_data_fill",
                show_index=False,
                sizing_mode="stretch_width",
                disabled=True,
            )
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Advanced stats failed: {exc}", alert_type="danger")

    def stats_view(self):
        return pn.Column(
            pn.bind(lambda *_: self.summary_stats_table(), *self.controls.explore_inputs),
            pn.Card(
                pn.bind(lambda *_: self.full_stats_table(), *self.controls.explore_inputs),
                title="Advanced statistics",
                collapsible=True,
                collapsed=True,
                margin=0,
                sizing_mode="stretch_width",
            ),
            margin=0,
            sizing_mode="stretch_width",
        )

    def region_readout(self):
        try:
            state = self.controls.state()
            summary = self.data.region_summary(state)
            if summary.is_empty():
                return pn.pane.Markdown("No data in the current range.")
            return self._summary_tabulator(summary, ["group", "n", "df_n", "dD", "mass", "Q", "dD_per_df"])
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Readout failed: {exc}", alert_type="danger")

    def df_plot(self):
        try:
            state = self.controls.state()
            norm_df, d_df = self.data.qcmd_frames(state)
            return self.nearest_hover(plots.df_fingerprint(norm_df, d_df, state.groups, state.orders))
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Fingerprint plot failed: {exc}", alert_type="danger")

    def controls_for_quantity(self, quantity_key: str):
        return pn.Column(
            self.controls.quantity_select,
            self.controls.analyze_range_controls(quantity_key=quantity_key, include_save=False),
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["compact-section"],
        )

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

    def view(self):
        return pn.Column(
            pn.bind(lambda *_: self._reference_hint(), *self.controls.explore_inputs),
            self.panel(
                self.quantity_plot,
                *self.controls.explore_inputs,
                self.controls.plot_reset_version,
                title="Selected quantity",
                controls=pn.bind(self.controls_for_quantity, self.controls.quantity_select),
                controls_position="top",
            ),
            self.panel(self.current_range_summary_cards, *self.controls.explore_inputs, title="QCM-D summary"),
            self.panel(self.region_readout, *self.controls.explore_inputs, title="Per-channel readout"),
            self.panel(self.stats_view, *self.controls.explore_inputs, title="Statistics"),
            self.panel(self.df_plot, *self.controls.explore_inputs, self.controls.plot_reset_version, title="ΔD vs Δf/n"),
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["workbench-page", "viewer-page"],
        )
