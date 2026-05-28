"""Small, task-oriented pages for the QCM viewer."""
from __future__ import annotations

import holoviews as hv
import panel as pn
import polars as pl

from . import plots, science
from .actions import ViewerActions
from .controls import ViewerControls
from .data import QCMViewData
from .theme import quantity

_US = 1_000_000


class BasePage:
    def __init__(self, controls: ViewerControls, data: QCMViewData, actions: ViewerActions):
        self.controls = controls
        self.data = data
        self.actions = actions

    def panel(self, render_fn, *dependencies, title: str, controls=None):
        body = pn.bind(lambda *_: render_fn(), *dependencies)
        children = []
        if controls is not None:
            children.append(controls)
        children.append(body)
        return pn.Card(
            *children,
            title=title,
            collapsible=False,
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["viewer-card"],
        )

    def attach_tap(self, obj):
        try:
            tap = hv.streams.SingleTap(source=obj, transient=True)
            tap.add_subscriber(lambda x=None, y=None: self.actions.jump_to_seconds(x))
        except Exception:
            pass
        return obj

    @staticmethod
    def hint(text: str):
        return pn.pane.Markdown(f"<small>{text}</small>", margin=0, sizing_mode="stretch_width")


class OverviewPage(BasePage):
    """The main workflow: one canonical QCM-D plot."""

    def hero_plot(self):
        try:
            state = self.controls.state()
            norm_df, d_df = self.data.qcmd_frames(state)
            title = "QCM-D overview — Δf/n and ΔD"
            plot = plots.dual_axis_qcmd(
                norm_df,
                d_df,
                state.groups,
                state.orders,
                title,
                baseline=state.baseline_s,
                annotation_spans=self.data.annotation_spans(state),
            )
            return self.attach_tap(plot)
        except Exception as exc:  # pragma: no cover - UI guard
            return pn.pane.Alert(f"QCM-D plot failed: {exc}", alert_type="danger")

    def view(self):
        controls = pn.Column(
            pn.pane.Markdown("**Ranges**", margin=0, sizing_mode="stretch_width"),
            self.controls.overview_range_controls(),
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["compact-section"],
        )
        return pn.Column(
            self.panel(
                self.hero_plot,
                *self.controls.signal_inputs,
                title="QCM-D overview",
                controls=controls,
            ),
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["viewer-page", "overview-page"],
        )


class ExplorePage(BasePage):
    """Quantity plot, comprehensive statistics, and saved regions for export."""

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
                height=240,
                annotation_spans=self.data.annotation_spans(state),
                baseline=state.baseline_s if q.referenced else None,
            )
            return self.attach_tap(plot)
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Quantity plot failed: {exc}", alert_type="danger")

    def full_stats_table(self):
        try:
            state = self.controls.state()
            value_df, elapsed = self.data.value_df(state)
            stats = science.summary_stats(value_df.select(["timestamp", "group", "value"]))
            if stats.is_empty():
                return pn.pane.Markdown("No statistics for the current range.")
            q = quantity(state.quantity)
            stats = stats.with_columns(
                pl.lit(q.label).alias("quantity"),
                pl.lit(q.unit or "—").alias("unit"),
                pl.lit(round(elapsed, 1)).alias("compute_ms"),
            )
            ordered = [
                "group", "quantity", "unit", "rows", "valid", "missing", "duration_s",
                "first", "last", "net_change", "abs_net_change", "slope_per_s",
                "mean", "median", "std", "variance", "sem", "cv", "min", "q01", "q05", "q10",
                "q25", "q75", "q90", "q95", "q99", "max", "range", "iqr",
                "mean_abs", "rms", "mean_abs_step", "step_std", "sum", "sum_abs", "compute_ms",
            ]
            stats = stats.select([c for c in ordered if c in stats.columns])
            table_height = min(360, max(116, 46 + stats.height * 34))
            return pn.widgets.Tabulator(
                stats.to_pandas(),
                height=table_height,
                layout="fit_data_fill",
                show_index=False,
                sizing_mode="stretch_width",
                disabled=True,
            )
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Stats failed: {exc}", alert_type="danger")

    def regions_table(self):
        _ = self.controls.annotation_version.value
        anns = self.data.annotations()
        self.actions.refresh_marker_options()
        if not anns:
            return pn.pane.Markdown(
                "_No saved regions yet._ Choose a current range, type a name, then click "
                "**Save current range**."
            )
        rows = []
        for a in anns:
            start_s = (a.t0 - self.data.info.t0_us) / _US
            end_s = ((a.t1 or a.t0) - self.data.info.t0_us) / _US
            rows.append(
                {
                    "name": a.label,
                    "type": a.tags[0] if a.tags else "region",
                    "shape": "range" if a.type == "range" else "time point",
                    "start_s": round(start_s, 3),
                    "end_s": round(end_s, 3),
                    "duration_s": round(max(0.0, end_s - start_s), 3),
                    "groups": ", ".join(str(g) for g in (a.groups or [])) or "all",
                }
            )
        table = pn.widgets.Tabulator(
            pl.DataFrame(rows).to_pandas(),
            height=260,
            show_index=False,
            layout="fit_data_fill",
            buttons={"delete": '<i class="fa fa-trash"></i>'},
            sizing_mode="stretch_width",
        )
        table.on_click(self._on_region_action)
        return table

    def _on_region_action(self, event) -> None:
        if getattr(event, "column", None) == "delete":
            self.actions.delete_annotation_by_row(event.row)

    def controls_for_quantity(self, quantity_key: str):
        _ = quantity_key  # Keep this reactive dependency for quantity changes.
        return pn.Column(
            self.controls.analyze_range_controls(),
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["compact-section"],
        )

    def view(self):
        range_controls = pn.bind(self.controls_for_quantity, self.controls.quantity_select)
        analyze_controls = pn.Column(
            self.controls.quantity_select,
            range_controls,
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["compact-section", "analyze-controls"],
        )
        save_region_controls = pn.Card(
            pn.pane.Markdown(
                "**3. Optional: save the current range.** Saved regions appear as overlays on plots "
                "and can be exported to a notebook. "
                "Use them for artifacts, rinse/sample steps, or any interval you want to return to later.",
                margin=0,
                sizing_mode="stretch_width",
            ),
            self.controls.region_type,
            self.controls.region_label,
            pn.Row(
                self.controls.mark_point_button,
                self.controls.mark_window_button,
                margin=0,
                sizing_mode="stretch_width",
            ),
            title="Save a region",
            collapsible=False,
            margin=0,
            sizing_mode="stretch_width",
        )
        notebook_controls = pn.Card(
            pn.pane.Markdown(
                "Choose **Current range** or a saved range. The notebook opens directly on that interval.",
                margin=0,
                sizing_mode="stretch_width",
            ),
            self.controls.marker_select,
            self.actions.export_nb_dl,
            title="Export notebook",
            collapsible=False,
            margin=0,
            sizing_mode="stretch_width",
        )
        saved_regions = pn.Card(
            pn.bind(lambda *_: self.regions_table(), self.controls.annotation_version),
            notebook_controls,
            title="Saved regions",
            collapsible=False,
            margin=0,
            sizing_mode="stretch_width",
        )
        return pn.Column(
            self.hint(
                "Mental model: Current range = what you inspect. Zero/reference range = zero "
                "for Δ-values only. "
                "Saved regions = named intervals you can see again or export."
            ),
            self.panel(
                self.quantity_plot,
                *self.controls.explore_inputs,
                title="Plot for the current range",
                controls=analyze_controls,
            ),
            self.panel(
                self.full_stats_table,
                *self.controls.explore_inputs,
                title="Statistics for the current range",
            ),
            save_region_controls,
            saved_regions,
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["viewer-page"],
        )


class SweepPage(BasePage):
    """Raw sweep inspection for debugging fits and artifacts."""

    def sweep_readout(self):
        return pn.pane.Markdown(self.data.sequence_readout(self.controls.sequence.value))

    def sweep_plot(self):
        try:
            state = self.controls.state()
            panels = plots.sweep_curves(self.data.sweep_df(state), orders=state.orders)
            return pn.Column(*panels, sizing_mode="stretch_width")
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Sweep failed: {exc}", alert_type="danger")

    def iq_plot(self):
        try:
            state = self.controls.state()
            return plots.iq_scatter(self.data.sweep_df(state), f"I/Q at sweep {state.sequence}")
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"I/Q failed: {exc}", alert_type="danger")

    def waterfall_plot(self):
        try:
            state = self.controls.state()
            panels = plots.waterfall(self.data.waterfall_df(state), orders=state.orders)
            return pn.Column(*panels, sizing_mode="stretch_width")
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Waterfall failed: {exc}", alert_type="danger")

    def view(self):
        controls = pn.Card(
            self.controls.sequence,
            pn.bind(lambda *_: self.sweep_readout(), self.controls.sequence),
            self.controls.sweep_mode,
            self.controls.group_for_single,
            self.controls.frequency_band,
            title="Sweep controls",
            collapsible=False,
            margin=0,
            sizing_mode="stretch_width",
        )
        return pn.Column(
            self.hint(
                "Raw sweep tools live here. The sweep number also updates when you click a timeline plot."
            ),
            controls,
            self.panel(self.sweep_plot, *self.controls.sweep_inputs, title="Resonance curves"),
            self.panel(self.iq_plot, *self.controls.sweep_inputs, title="I/Q scatter"),
            self.panel(
                self.waterfall_plot,
                *self.controls.signal_inputs,
                self.controls.waterfall_band_input,
                title="Waterfall",
            ),
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["viewer-page"],
        )
