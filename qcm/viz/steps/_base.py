"""Shared presentation helpers for stepper step views (copied from BasePage)."""
from __future__ import annotations

from dataclasses import replace
from math import isfinite

import holoviews as hv
import panel as pn
import polars as pl

from .. import plots
from .. import science  # noqa: F401  (kept for parity; used by subclasses)
from ..theme import HERO_HEIGHT, axis, potential_axis_label, quantity
from ..tokens import FAINT, INK_SOFT
from ..actions import ViewerActions
from ..components import empty_state
from ..controls import ViewerControls
from ..data import QCMViewData
from ..errors import surface_error
from qcm.log import get_logger

_US = 1_000_000

_log = get_logger("viz.steps")


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
        classes = ["qcm-card"]
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
                # Do NOT force ``mode`` here: a vline-hover hook may have already
                # set ``vline`` (the multi-overtone readout), and this hook now runs
                # alongside it, so overriding to "mouse" would silently undo it.
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

    @staticmethod
    def _existing_hooks(plot) -> list:
        """Hooks already attached to an Overlay's plot options (empty on failure).

        Used so height/hover helpers *append* rather than overwrite — otherwise
        applying one hook silently drops the twin-axis, vline-hover, legend-mute,
        saved-region and drag-select hooks the plot builders attached.
        """
        try:
            return list(plot.opts.get("plot").kwargs.get("hooks", []) or [])
        except Exception:
            return []

    def nearest_hover(self, obj):
        try:
            hooks = self._existing_hooks(obj) + [self._nearest_hover_hook]
            return obj.opts(hooks=hooks)
        except Exception:
            return obj

    def attach_tap(self, obj):
        # A wiring failure here silently kills tap-to-jump — exactly the class
        # of invisible breakage the error policy (ADR 0006) exists for, so it is
        # always logged even though the plot itself still renders.
        try:
            tap = hv.streams.SingleTap(source=obj, transient=True)
            tap.add_subscriber(lambda x=None, y=None: self.actions.jump_to_seconds(x))
        except Exception:  # noqa: BLE001 — degrade to a non-interactive plot, loudly
            _log.exception("attach_tap: tap-to-jump wiring failed; plot is not tappable")
        return obj

    def attach_brush(self, obj):
        # Same policy as attach_tap: drag-select dying silently was the
        # historical box-select bug — log it, keep the plot.
        try:
            bounds = hv.streams.BoundsX(source=obj)
            bounds.add_subscriber(lambda boundsx=None: self.actions.apply_brush(boundsx))
        except Exception:  # noqa: BLE001 — degrade to a non-interactive plot, loudly
            _log.exception("attach_brush: drag-select wiring failed; brush is dead")
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
                text_color=INK_SOFT,
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
            hooks = self._existing_hooks(plot) + [self._force_plot_height_hook(height)]
            return plot.opts(
                hv.opts.Overlay(height=height, responsive=True, hooks=hooks),
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

    def csv_download(self, frame_fn, filename: str, label: str = "Download CSV"):
        """A download button for a results table.

        ``frame_fn`` is called at click time so the exported CSV always matches
        the current selection (cycles, range, params) rather than a stale render.
        """
        def _file():
            import io

            buf = io.BytesIO()
            try:
                df = frame_fn()
                if df is not None and not df.is_empty():
                    df.write_csv(buf)
            except Exception as exc:  # noqa: BLE001 — never hand the user a silently empty file
                _log.exception("csv_download(%s) failed", filename)
                buf.write(f"# export failed: {exc}\n".encode())
            buf.seek(0)
            return buf

        return pn.widgets.FileDownload(
            callback=_file, filename=filename, label=label,
            color="default", width=150, height=30,
            css_classes=["qcm-table-download"],
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

    def unified_anchor(self, window: str = "current", state=None, height: int = HERO_HEIGHT,
                       show_legend: bool = True):
        """The single configurable analysis plot shown on every page.

        Plots the selected y-quantity against the selected x-axis over the full
        run, highlighting ``window`` (current / reference / mark) when the x-axis
        is time. For QCM resonance quantities on the time axis it adds the ΔD twin
        axis so the default Δf/n-vs-time view reproduces the canonical QCM-D
        figure. Electrochemistry quantities (potential/current/charge/MPE) and
        non-time x-axes drop the twin axis and the time-based overlays.
        """
        try:
            state = state or self.controls.state()
            ax = axis(state.x_axis)
            q = quantity(state.quantity)
            full = replace(state, t_range_s=(0.0, float(self.data.info.span_s)))

            # Multi-run: overlay every loaded run on the same quantity timeline.
            # Single-run keeps the richer single-run path below (twin axis, etc.).
            runset = getattr(self.data, "runset", None)
            if runset is not None and runset.is_multi:
                return self._overlay_anchor(state, ax, q, full, window, height, show_legend)

            value_df, elapsed = self.data.value_df(full, state.quantity, state.x_axis)

            companion_df = None
            companion_groups = None
            companion_axis_label = None
            companion_prefix = None
            right_sel = getattr(self.controls, "quantity_select_right", None)
            right_key = right_sel.value if right_sel is not None else "delta_D"
            # The second axis is a vs-time comparison of two distinct signals:
            # drawn whenever a distinct right-axis quantity is chosen on the time
            # axis. "None (single axis)" gives a single-quantity plot. (The control
            # itself is disabled off the time axis, so this stays consistent.)
            want_twin = right_key not in (None, "__none__", state.quantity)
            if ax.is_time and want_twin:
                companion_df, _ = self.data.value_df(full, right_key, "time")
                rq = quantity(right_key)
                if right_key == "delta_D":
                    companion_groups = self.controls.dissipation_groups()
                elif rq.is_echem:
                    # Cell-level signals are identical across overtones — draw once.
                    companion_groups = full.groups[:1]
                else:
                    companion_groups = full.groups
                companion_axis_label = rq.axis_label
                companion_prefix = rq.label

            show_phases_w = getattr(self.controls, "show_phases", None)
            show_phases = bool(show_phases_w.value) if show_phases_w is not None else True
            spans = self.data.annotation_spans(state) if show_phases else []

            show_cycles_w = getattr(self.controls, "show_cycles", None)
            show_cycles = bool(show_cycles_w.value) if show_cycles_w is not None else False
            cycle_spans = self.data.cycle_spans() if (show_cycles and ax.is_time) else None

            visible_groups = self.controls.frequency_groups() if q.kind == "frequency" else full.groups

            if window == "reference":
                win = state.baseline_s
            elif window == "mark":
                win = tuple(float(v) for v in self.controls.mark_range.value)
            else:
                win = state.t_range_s

            title = f"{q.label} vs {ax.label} · {value_df.height:,} points · {elapsed:.0f} ms"
            title += self._quantity_caveats(state, q)
            plot = plots.analysis_timeline(
                value_df,
                q,
                ax,
                full.groups,
                full.orders,
                title,
                companion_df=companion_df,
                visible_groups=visible_groups,
                companion_groups=companion_groups,
                companion_axis_label=companion_axis_label,
                companion_prefix=companion_prefix,
                baseline=state.baseline_s if (q.referenced and window != "reference") else None,
                window=win,
                annotation_spans=spans,
                select_x=ax.monotonic,
                height=height,
                show_legend=show_legend,
                cycle_spans=cycle_spans,
                target=(state.params.target_mpe
                        if (q.kind == "mpe" and getattr(state, "mpe_target_show", False))
                        else None),
            )
            faraday = self._faraday_overlay(state, ax, q)
            if faraday is not None:
                plot = plot * faraday
            return self._finish_anchor(plot, ax, q, height, show_legend, label_df=value_df)
        except Exception as exc:  # pragma: no cover
            return surface_error("Plot", exc)

    @staticmethod
    def _quantity_caveats(state, q) -> str:
        """Honest footnotes for the plot title.

        Surfaces two things that would otherwise be silent: that the MPE shown is
        a clipped signal, and that Δf/n (or any overtone-normalized quantity) is a
        no-op when every selected channel is the fundamental (n=1).
        """
        notes: list[str] = []
        if q.kind == "mpe" and getattr(state, "mpe_clip", False):
            notes.append(f"clipped to [{state.mpe_clip_lo:g}, {state.mpe_clip_hi:g}] g/mol")
        if getattr(state, "detrend", False) and q.kind in ("frequency", "dissipation", "mass"):
            notes.append("drift-corrected (quadratic)" if int(getattr(state, "detrend_order", 1)) >= 2
                         else "drift-corrected (linear)")
        if q.normalized and state.groups:
            if all(int(state.orders.get(g, 1)) == 1 for g in state.groups):
                notes.append("n=1 (no normalization)")
        return ("  ·  " + " · ".join(notes)) if notes else ""

    def _faraday_overlay(self, state, ax, q):
        """Faraday's-law predicted trace (100 % CE) for the hero, or ``None``.

        Drawn for Δf/n and Sauerbrey mass on the time axis when the run has a
        charge channel and the user enabled the overlay in the params card.
        The gap between this dashed line and the measured curve reads directly
        as CE loss, side reactions, or viscoelastic error.
        """
        try:
            toggle = getattr(self.controls, "faraday_show", None)
            if (
                toggle is None or not bool(toggle.value)
                or not ax.is_time
                or q.key not in ("delta_f_norm", "sauerbrey_mass")
                or not self.data.has_echem()
            ):
                return None
            from .. import science

            wf = self.data.echem_waveform()
            pred = science.faraday_prediction(
                wf, q.key, params=state.params,
                baseline_us=state.baseline_us(self.data.info.t0_us),
            )
            if pred.is_empty():
                return None
            t = (pred["timestamp"].to_numpy() - self.data.info.t0_us) / 1e6
            x, y = plots._decimate_xy(t, pred["value"].to_numpy())
            return hv.Curve((x, y), label="Faraday (100% CE)").opts(
                color=INK_SOFT, line_dash="dashdot", line_width=2.0,
            )
        except Exception:
            return None

    def _anchor_window(self, state, window: str) -> tuple[float, float]:
        """The highlighted span for the hero plot in the active selection mode."""
        if window == "reference":
            return state.baseline_s
        if window == "mark":
            return tuple(float(v) for v in self.controls.mark_range.value)
        return state.t_range_s

    def _finish_anchor(self, plot, ax, q, height, show_legend, label_df=None):
        """Shared hero-plot tail: zero line, phase labels, legend, interactivity.

        Legend options must be set on the OUTERMOST overlay — composing the plot
        with the zero line / phase labels creates a new container that otherwise
        reverts to a default inside top-right legend, which overlaps the curves on
        the dense main graph and reads as missing.
        """
        zero_w = getattr(self.controls, "zero_line", None)
        if zero_w is not None and bool(zero_w.value):
            try:
                plot = plot * hv.HLine(0).opts(color=FAINT, line_dash="dashed", line_width=1)
            except Exception:
                pass
        if ax.is_time and label_df is not None:
            plot = self.with_phase_labels(plot, label_df, height=height)
        try:
            # Annotate potential axes with the run's reference electrode.
            ref = self.controls.params().reference_electrode
            xlabel = potential_axis_label(ref) if ax.key == "potential" else ax.axis_label
            ylabel = potential_axis_label(ref) if q.key == "potential" else q.axis_label
            outer = dict(
                show_legend=show_legend, legend_position="right",
                xlabel=xlabel, ylabel=ylabel,
            )
            ylim = self._manual_ylim()
            if ylim is not None:
                outer["ylim"] = ylim
            plot = plot.opts(hv.opts.Overlay(**outer))
        except Exception:
            pass
        sized = self.force_plot_height(plot, height)
        if ax.is_time:
            # Time gets the full interaction: drag-select a window + click-to-jump.
            return self.interactive_plot(sized)
        if ax.monotonic:
            # Other monotonic axes (cycle number) support drag-select only — a tap
            # maps to seconds, which is meaningless off the time axis.
            return self.attach_brush(self.nearest_hover(sized))
        return self.nearest_hover(sized)

    def _manual_ylim(self) -> tuple[float | None, float | None] | None:
        """User-pinned hero y-window from the toolbar inputs (blank = auto)."""
        lo_w = getattr(self.controls, "y_min", None)
        hi_w = getattr(self.controls, "y_max", None)
        lo = lo_w.value if lo_w is not None else None
        hi = hi_w.value if hi_w is not None else None
        if lo is None and hi is None:
            return None
        if lo is not None and hi is not None and lo >= hi:
            return None
        return (lo, hi)

    def _overlay_anchor(self, state, ax, q, full, window: str, height: int, show_legend: bool):
        """Hero plot for a multi-run set: every run overlaid on one quantity.

        The shared view selection (quantity, x-axis, time range, baseline) applies
        to every run; each run is aligned to its own start and referenced to its
        own baseline by :meth:`RunSet.overlay_value_df`. Window/baseline/cycle and
        phase context is drawn for the active run only.
        """
        runset = self.data.runset
        frame = runset.overlay_value_df(full, state.quantity, state.x_axis)
        if frame.is_empty():
            return self.empty_state(f"No {q.label} data in any loaded run.")

        show_cycles_w = getattr(self.controls, "show_cycles", None)
        show_cycles = bool(show_cycles_w.value) if show_cycles_w is not None else False
        cycle_spans = self.data.cycle_spans() if (show_cycles and ax.is_time) else None

        show_phases_w = getattr(self.controls, "show_phases", None)
        show_phases = bool(show_phases_w.value) if show_phases_w is not None else True
        spans = self.data.annotation_spans(state) if (show_phases and ax.is_time) else []

        visible_groups = self.controls.frequency_groups() if q.kind == "frequency" else full.groups
        win = self._anchor_window(state, window)

        title = (f"{q.label} vs {ax.label} · {len(runset.runs)} runs · "
                 f"{frame.height:,} points")
        title += self._quantity_caveats(state, q)
        plot = plots.overlay_timeline(
            frame, q, ax,
            run_labels=runset.labels(),
            run_orders=[d.info.orders for d in runset.runs],
            title=title,
            visible_groups=visible_groups,
            baseline=state.baseline_s if (q.referenced and window != "reference") else None,
            window=win,
            annotation_spans=spans,
            cycle_spans=cycle_spans,
            select_x=ax.monotonic,
            height=height,
            show_legend=show_legend,
            target=(state.params.target_mpe
                    if (q.kind == "mpe" and getattr(state, "mpe_target_show", False))
                    else None),
        )
        return self._finish_anchor(plot, ax, q, height, show_legend, label_df=frame)

    # Backward-compatible alias: the per-step anchors call this.
    def overview_anchor(self, window: str = "current"):
        return self.unified_anchor(window=window)
