"""Task-oriented pages for the QCM analysis workbench."""
from __future__ import annotations

from dataclasses import replace
from math import isfinite

import holoviews as hv
import panel as pn
import polars as pl

from . import plots, science
from .actions import ViewerActions
from .controls import ViewerControls
from .data import QCMViewData
from .design import metric_card, metric_table, section_header
from .theme import quantity

_US = 1_000_000


class BasePage:
    """Shared presentation helpers for workflow pages."""

    def __init__(self, controls: ViewerControls, data: QCMViewData, actions: ViewerActions):
        self.controls = controls
        self.data = data
        self.actions = actions

    def panel(
        self,
        render_fn,
        *dependencies,
        title: str,
        controls=None,
        collapsible: bool = True,
        collapsed: bool = False,
        controls_position: str = "top",
    ):
        body = pn.bind(lambda *_: render_fn(), *dependencies)
        if controls is None:
            children = [body]
        elif controls_position == "bottom":
            children = [body, controls]
        else:
            children = [controls, body]
        classes = ["viewer-card"]
        if controls_position == "bottom":
            classes.append("plot-first-card")
        return pn.Card(
            *children,
            title=title,
            collapsible=collapsible,
            collapsed=collapsed,
            margin=0,
            sizing_mode="stretch_width",
            css_classes=classes,
        )

    @staticmethod
    def empty_state(text: str):
        return pn.pane.Markdown(
            f"<div class='phase-empty-state'>{text}</div>", margin=0, sizing_mode="stretch_width"
        )

    @staticmethod
    def _nearest_hover_hook(plot, _element):
        """Consolidate Bokeh hover tools so overlays do not show one tooltip per line."""
        try:
            from bokeh.models import BoxSelectTool, HoverTool

            fig = plot.state
            hover_tools = [tool for tool in fig.tools if isinstance(tool, HoverTool)]
            if hover_tools:
                renderers = []
                for tool in hover_tools:
                    if getattr(tool, "renderers", None) and tool.renderers != "auto":
                        renderers.extend(list(tool.renderers))

                keep = hover_tools[0]
                # Keep the custom plot tooltip from plots.py.  The previous pass
                # accidentally replaced it with raw x/y values; this hook should
                # only consolidate duplicated hover tools, not redesign the tooltip.
                keep.mode = "mouse"
                keep.line_policy = "nearest"
                keep.point_policy = "snap_to_data"
                keep.attachment = "right"
                if renderers:
                    # Preserve order while dropping duplicates.
                    seen = set()
                    unique = []
                    for renderer in renderers:
                        key = id(renderer)
                        if key not in seen:
                            unique.append(renderer)
                            seen.add(key)
                    keep.renderers = unique
                fig.tools = [tool for tool in fig.tools if not isinstance(tool, HoverTool) or tool is keep]

            # Make drawing a time range immediate. BoundsX creates a BoxSelectTool
            # for the rendered object; keep it constrained to the x dimension and
            # active so a horizontal drag updates the selected range.
            box_tools = [tool for tool in fig.tools if isinstance(tool, BoxSelectTool)]
            for tool in box_tools:
                try:
                    tool.dimensions = "width"
                except Exception:
                    pass
            if box_tools:
                fig.toolbar.active_drag = box_tools[0]
        except Exception:
            pass

    def nearest_hover(self, obj):
        try:
            return obj.opts(hooks=[self._nearest_hover_hook])
        except Exception:
            return obj

    def attach_tap(self, obj):
        try:
            tap = hv.streams.SingleTap(source=obj, transient=True)
            tap.add_subscriber(lambda x=None, y=None: self.actions.jump_to_seconds(x))
        except Exception:
            pass
        return obj

    def attach_brush(self, obj):
        try:
            bounds = hv.streams.BoundsX(source=obj)
            bounds.add_subscriber(lambda boundsx=None: self.actions.apply_brush(boundsx))
        except Exception:
            pass
        return obj

    def interactive_plot(self, obj):
        # Apply styling/hooks first, then attach streams to the exact object that
        # Panel renders.  Attaching BoundsX before .opts() creates a clone and
        # leaves the brush stream connected to the non-rendered object, which is
        # why box-select range drawing appeared broken.
        styled = self.nearest_hover(obj)
        return self.attach_brush(self.attach_tap(styled))

    def _phase_label_y(self, df: pl.DataFrame, column: str = "value") -> float:
        """Place saved-phase labels near the top of a time plot without hard-coding axes."""
        try:
            if df.is_empty() or column not in df.columns:
                return 0.0
            vals = df.select([pl.col(column).min().alias("lo"), pl.col(column).max().alias("hi")]).to_dicts()[0]
            lo = float(vals.get("lo") or 0.0)
            hi = float(vals.get("hi") or 0.0)
            if not isfinite(lo) or not isfinite(hi):
                return 0.0
            span = hi - lo
            return hi if abs(span) < 1e-12 else hi - span * 0.06
        except Exception:
            return 0.0

    def phase_label_overlay(self, y: float):
        """Return an hv.Labels overlay for saved range annotations.

        The shaded region remains the main visual marker; the label is centered
        over it so users can identify baseline/sample/rinse regions directly on
        every time plot.
        """
        try:
            rows = []
            for ann in self.data.annotations():
                if ann.type != "range" or ann.t1 is None or not ann.label:
                    continue
                x0 = (ann.t0 - self.data.info.t0_us) / _US
                x1 = (ann.t1 - self.data.info.t0_us) / _US
                rows.append(((x0 + x1) / 2.0, float(y), ann.label))
            if not rows:
                return None
            return hv.Labels(rows, kdims=["x", "y"], vdims=["label"]).opts(
                text_font_size="8pt",
                text_color="#334155",
                text_align="center",
                text_baseline="bottom",
            )
        except Exception:
            return None

    def with_phase_labels(self, plot, df: pl.DataFrame | None = None):
        try:
            y = self._phase_label_y(df) if df is not None else 0.0
            labels = self.phase_label_overlay(y)
            return plot * labels if labels is not None else plot
        except Exception:
            return plot

    _SUMMARY_ROUND = {"df_n": 2, "dD": 3, "mass": 1, "Q": 0, "dD_per_df": 4, "duration_s": 2}
    _SUMMARY_RENAME = {
        "region": "phase",
        "duration_s": "duration [s]",
        "group": "channel",
        "n": "n",
        "df_n": "Δf/n [Hz]",
        "dD": "ΔD [×10⁻⁶]",
        "mass": "mass [ng/cm²]",
        "Q": "Q",
        "dD_per_df": "ΔD/Δf [×10⁻⁶/Hz]",
        "channel_count": "channels",
        "df_n_mean": "mean Δf/n [Hz]",
        "df_n_std": "sd Δf/n",
        "dD_mean": "mean ΔD [×10⁻⁶]",
        "dD_std": "sd ΔD",
        "mass_mean": "mean mass [ng/cm²]",
        "mass_std": "sd mass",
        "Q_mean": "mean Q",
        "dD_per_df_mean": "mean ΔD/Δf",
        "abs_df_n_mean": "mean |Δf/n| [Hz]",
        "response_rank": "response score",
    }

    def _summary_tabulator(self, df: pl.DataFrame, order: list[str], height: int | None = None):
        cols = [c for c in order if c in df.columns]
        df = df.select(cols).with_columns(
            [pl.col(c).round(r) for c, r in self._SUMMARY_ROUND.items() if c in cols]
        )
        for c in df.columns:
            if df[c].dtype in (pl.Float32, pl.Float64):
                df = df.with_columns(pl.col(c).round(4))
        df = df.rename({k: v for k, v in self._SUMMARY_RENAME.items() if k in df.columns})
        h = height or min(330, max(120, 48 + df.height * 34))
        return pn.widgets.Tabulator(
            df.to_pandas(),
            height=h,
            layout="fit_data_fill",
            show_index=False,
            sizing_mode="stretch_width",
            disabled=True,
        )

    @staticmethod
    def _fmt(value, digits: int = 2, suffix: str = "") -> str:
        if value is None:
            return "—"
        try:
            value = float(value)
        except (TypeError, ValueError):
            return "—"
        if not isfinite(value):
            return "—"
        return f"{value:,.{digits}f}{suffix}"

    def current_range_summary_cards(self):
        try:
            state = self.controls.state()
            summary = self.data.region_summary(state)
            if summary.is_empty():
                return self.empty_state("No data in the current analysis range.")

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
            return metric_table(rows)
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Summary cards failed: {exc}", alert_type="danger")


class RunReviewPage(BasePage):
    """Run-level overview and range navigation."""

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
            )
            plot = self.with_phase_labels(plot, norm_df)
            return self.interactive_plot(plot)
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"QCM-D plot failed: {exc}", alert_type="danger")

    def view(self):
        controls = pn.Column(
            self.controls.overview_range_controls(),
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["compact-section"],
        )
        return pn.Column(
            section_header("Review"),
            self.panel(self.hero_plot, *self.controls.signal_inputs, self.controls.plot_reset_version, title="QCM-D overview", controls=controls, controls_position="top"),
            self.panel(self.current_range_summary_cards, *self.controls.signal_inputs, title="Current range"),
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["workbench-page", "viewer-page"],
        )


class PhaseBuilderPage(BasePage):
    """Saved phase statistics and data-science tables."""

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
            height=min(420, max(150, 48 + len(rows) * 34)),
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
                height=min(520, max(150, 48 + df.height * 34)),
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
                height=min(420, max(150, 48 + out.height * 34)),
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
                height=min(360, max(140, 48 + out.height * 34)),
            )
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Phase ranking failed: {exc}", alert_type="danger")

    def view(self):
        return pn.Column(
            section_header("Phases & Compare"),
            self.panel(self.phases_table, self.controls.annotation_version, title="Saved phases"),
            self.panel(self.phase_rollup, *self.controls.explore_inputs, title="Phase rollup"),
            self.panel(self.phase_matrix, *self.controls.explore_inputs, title="Per-channel phase matrix"),
            self.panel(self.phase_response_ranking, *self.controls.explore_inputs, title="Response ranking"),
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["workbench-page", "viewer-page"],
        )


class QuantifyPage(BasePage):
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

    def view(self):
        return pn.Column(
            section_header("Quantify"),
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


class QCPage(BasePage):
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
        return pn.GridBox(
            metric_card("Sweep", str(int(state.sequence)), tone="accent"),
            metric_card("Channels", str(selected)),
            metric_card("Frequency band", f"{state.frequency_band[0]:,.1f}–{state.frequency_band[1]:,.1f} Hz"),
            ncols=3,
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["metric-grid"],
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
            self.controls.overview_range_controls(),
            title="Waterfall controls",
            collapsible=True,
            collapsed=False,
            margin=0,
            sizing_mode="stretch_width",
        )
        return pn.Column(
            section_header("QC & Raw Sweeps"),
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


class ReportPage(BasePage):
    """Simple report/export surface using existing export capabilities."""

    def view(self):
        return pn.Column(
            section_header("Report"),
            self.panel(self.current_range_summary_cards, *self.controls.explore_inputs, title="Summary"),
            pn.Card(
                self.controls.marker_select,
                self.actions.export_data_dl,
                self.actions.export_nb_dl,
                self.controls.save_state_button,
                self.controls.status,
                title="Export",
                collapsible=True,
                collapsed=False,
                margin=0,
                sizing_mode="stretch_width",
            ),
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["workbench-page", "viewer-page"],
        )


# Backward-compatible aliases for code that imports the old page names.
OverviewPage = RunReviewPage
ExplorePage = QuantifyPage
SweepPage = QCPage
