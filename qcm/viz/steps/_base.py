"""Shared presentation helpers for stepper step views (copied from BasePage)."""
from __future__ import annotations

from dataclasses import replace
from math import isfinite

import holoviews as hv
import panel as pn
import polars as pl

from .. import plots
from .. import science  # noqa: F401  (kept for parity; used by subclasses)
from ..theme import HERO_HEIGHT, quantity
from ..actions import ViewerActions
from ..components import empty_state
from ..controls import ViewerControls
from ..data import QCMViewData

_US = 1_000_000


class BaseStep:
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
        collapsible: bool = False,
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
        return empty_state(text)

    def below_plot_panel(self):
        """Wide analysis area beneath the anchor plot. Empty by default; focuses
        with heavy tables/fingerprints (Quantify, Phases) override this."""
        return pn.Spacer(height=0)

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

    @staticmethod
    def _force_plot_height_hook(height: int):
        """Force the final Bokeh figure height after HoloViews overlay composition.

        HoloViews can lose height options when a plot is multiplied by labels or
        other overlays. This hook is deliberately applied last so Review,
        Reference, and Quantify render at the standardized sizes.
        """
        def hook(plot, _element):
            try:
                fig = plot.state
                fig.height = int(height)
                fig.min_height = int(height)
                fig.sizing_mode = "stretch_width"
            except Exception:
                pass
        return hook

    def force_plot_height(self, plot, height: int):
        try:
            return plot.opts(
                hv.opts.Overlay(height=height, responsive=True, hooks=[self._force_plot_height_hook(height)]),
                hv.opts.Curve(height=height, responsive=True),
            )
        except Exception:
            return plot

    def with_phase_labels(self, plot, df: pl.DataFrame | None = None, height: int | None = None):
        try:
            y = self._phase_label_y(df) if df is not None else 0.0
            labels = self.phase_label_overlay(y)
            out = plot * labels if labels is not None else plot
            return self.force_plot_height(out, height) if height is not None else out
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
        h = height or min(220, max(96, 34 + df.height * 26))
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

    def overview_anchor(self, window: str = "current"):
        """Full-run selected-quantity plot used as the anchor for Overview,
        Reference, and Report. ``window`` selects which range is highlighted."""
        try:
            state = self.controls.state()
            full = replace(state, t_range_s=(0.0, float(self.data.info.span_s)))
            value_df, elapsed = self.data.value_df(full)
            q = quantity(full.quantity)
            if window == "reference":
                win = state.baseline_s
            elif window == "mark":
                win = tuple(float(v) for v in self.controls.mark_range.value)
            else:
                win = state.t_range_s
            baseline = state.baseline_s if q.referenced and window != "reference" else None
            title = f"{q.label} overview · {value_df.height:,} points · {elapsed:.0f} ms"
            plot = plots.timeline(
                value_df,
                q,
                full.groups,
                full.orders,
                title,
                annotation_spans=self.data.annotation_spans(state),
                baseline=baseline,
                window=win,
                select_x=True,
                height=HERO_HEIGHT,
            )
            plot = self.with_phase_labels(plot, value_df, height=HERO_HEIGHT)
            return self.interactive_plot(self.force_plot_height(plot, HERO_HEIGHT))
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Overview plot failed: {exc}", alert_type="danger")

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
            table = pl.DataFrame(rows, schema=["Metric", "Value", "Range"], orient="row")
            return pn.widgets.Tabulator(
                table.to_pandas(),
                height=182,
                layout="fit_data_fill",
                show_index=False,
                sizing_mode="stretch_width",
                disabled=True,
                css_classes=["summary-table"],
            )
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Summary table failed: {exc}", alert_type="danger")
