"""HoloViews/Bokeh plot builders for the QCM viewer.

All time-domain plots use *elapsed seconds* on the x-axis (not raw microsecond
timestamps), so axes and hover read like a human expects. The hero
``dual_axis_qcmd`` renders the canonical QCM-D figure: Δf/n on the left axis and
ΔD on a twin right axis, one trace per overtone, with an interactive mute
legend and a vertical-line hover that reports every overtone at the cursor.
"""
from __future__ import annotations

import holoviews as hv
import hvplot.polars  # noqa: F401  (registers .hvplot on Polars frames)
import numpy as np
import polars as pl

from .theme import (
    ACCENT,
    BASELINE_COLOR,
    ELAPSED_COLUMN,
    EVENT_COLOR,
    HERO_HEIGHT,
    MAX_PLOT_POINTS,
    PLOT_HEIGHT,
    COMPACT_PLOT_HEIGHT,
    SWEEP_PANEL_HEIGHT,
    WATERFALL_PANEL_HEIGHT,
    Axis,
    Quantity,
    color_for_slot,
)

X = ELAPSED_COLUMN
X_LABEL = "Time [s]"


def _decimate_xy(x: np.ndarray, y: np.ndarray, max_points: int = MAX_PLOT_POINTS):
    """Min/max envelope decimation of a single x-monotonic series.

    Splits the series into ``max_points // 2`` contiguous buckets and keeps the
    minimum and maximum sample of each (plus the endpoints), so the curve's
    visual envelope — including spikes and artifacts — is preserved while the
    point count sent to Bokeh is bounded. Returns the inputs unchanged when they
    are already small enough.
    """
    n = len(x)
    if max_points <= 0 or n <= max_points:
        return x, y
    buckets = max(1, max_points // 2)
    bins = (np.arange(n) * buckets // n)
    # Sort by bucket, then value: the first index in each bucket is its min, the
    # last is its max. One vectorized pass, no Python loop over buckets.
    order = np.lexsort((y, bins))
    sorted_bins = bins[order]
    bucket_ids = np.arange(buckets)
    first = np.searchsorted(sorted_bins, bucket_ids, side="left")
    last = np.searchsorted(sorted_bins, bucket_ids, side="right") - 1
    valid = last >= first
    lo = order[first[valid]]
    hi = order[last[valid]]
    keep = np.unique(np.concatenate([lo, hi, [0, n - 1]]))
    return x[keep], y[keep]


# --------------------------------------------------------------------- helpers
def empty(title: str):
    return hv.Curve([]).opts(title=title, height=PLOT_HEIGHT, responsive=True)


def series_labels(groups: list[int], orders: dict[int, int]) -> dict[int, str]:
    """Legend label per group: use ``n=…`` when overtone orders are distinct."""
    ns = [orders.get(g, 1) for g in groups]
    if len(set(ns)) == len(ns) and any(n > 1 for n in ns):
        return {g: f"n={orders.get(g, 1)}" for g in groups}
    return {g: f"group {g}" for g in groups}


def _xy(value_df: pl.DataFrame, group: int, max_points: int = MAX_PLOT_POINTS):
    sub = value_df.filter(pl.col("group") == group).drop_nulls("value")
    return _decimate_xy(sub[X].to_numpy(), sub["value"].to_numpy(), max_points)


def _legend_mute_hook(plot, _element):
    """Click a legend entry to mute/unmute its trace and hover target.

    Bokeh's legend ``mute`` policy only changes renderer opacity. HoverTool
    still includes muted renderers unless we explicitly keep its renderer list
    in sync with the active legend entries.
    """
    try:
        from bokeh.models import CustomJS, HoverTool

        fig = plot.state
        hover_renderers = []
        seen = set()
        for legend in plot.state.legend:
            legend.click_policy = "mute"
            legend.label_text_font_size = "9pt"
            for item in legend.items:
                for renderer in item.renderers:
                    if getattr(renderer, "glyph", None) is None:
                        continue
                    if id(renderer) in seen:
                        continue
                    hover_renderers.append(renderer)
                    seen.add(id(renderer))

        hovers = list(fig.select(HoverTool))
        if not hover_renderers or not hovers:
            return

        for hover in hovers:
            hover.renderers = [
                renderer
                for renderer in hover_renderers
                if not renderer.muted and renderer.visible
            ]

        sync_hover = CustomJS(
            args={"hovers": hovers, "renderers": hover_renderers},
            code="""
                const active = renderers.filter((renderer) => {
                    return !renderer.muted && renderer.visible !== false
                })
                for (const hover of hovers) {
                    hover.renderers = active
                    hover.change.emit()
                }
            """,
        )
        for renderer in hover_renderers:
            renderer.js_on_change("muted", sync_hover)
            renderer.js_on_change("visible", sync_hover)
    except Exception:
        pass


def _vline_hover_hook(plot, _element):
    """Switch the shared hover to vertical-line mode.

    Default ``mouse`` hover does a 2-D hit test against every line on each mouse
    move; with several decimated overtone traces that cost is what makes hover
    feel laggy. ``vline`` mode tests only the cursor's x position once and
    reports each trace's value there — cheaper per move and the multi-overtone
    readout QCM users expect. Only meaningful for overlays whose traces share
    the x-axis (time-domain and frequency-sweep plots).
    """
    try:
        from bokeh.models import HoverTool

        for tool in plot.state.select(HoverTool):
            tool.mode = "vline"
    except Exception:
        pass


def _xbox_select_hook(plot, _element):
    """Add an x-only box-select tool and make it the active drag gesture.

    Selection tools attach to glyphs, so a ``box_select`` string on an Overlay's
    options is dropped. Adding the tool here guarantees it exists; constraining it
    to ``dimensions='width'`` turns a horizontal drag into a time-range selection,
    which the BoundsX stream reads to set the analysis window. The scroll wheel
    stays the active zoom, so drag = select, scroll = zoom.
    """
    try:
        from bokeh.models import BoxSelectTool

        fig = plot.state
        existing = fig.select(BoxSelectTool)
        tool = existing[0] if existing else BoxSelectTool()
        if not existing:
            fig.add_tools(tool)
        tool.dimensions = "width"
        fig.toolbar.active_drag = tool
    except Exception:
        pass


def annotation_elements(spans) -> list:
    """Return saved-region overlays.

    Labels are drawn by ``_saved_region_label_hook`` so they appear inside the
    plot area instead of only in a legend.
    """
    elements = []
    for item in spans:
        plot_type, x0, x1 = item[:3]
        is_interval = plot_type in {"range", "reference_region", "excluded_region"} and x1 is not None and x1 != x0
        color = BASELINE_COLOR if plot_type == "reference_region" else EVENT_COLOR
        if is_interval:
            elements.append(hv.VSpan(x0, x1).opts(color=color, alpha=0.11))
            elements.append(hv.VLine(x0).opts(color=color, line_dash="dotted", line_width=1))
            elements.append(hv.VLine(x1).opts(color=color, line_dash="dotted", line_width=1))
        else:
            elements.append(hv.VLine(x0).opts(color=color, line_dash="dashed", line_width=1.4))
    return elements


def _saved_region_label_hook(spans):
    """Draw saved region names inside Bokeh plots.

    HoloViews spans/lines do not reliably render text labels in the data area,
    so this hook adds lightweight Bokeh labels near the bottom of the viewport.
    The label follows the x data coordinate and stays readable when zooming.
    """
    def hook(plot, _element):
        if not spans:
            return
        try:
            from bokeh.models import Label

            fig = plot.state
            for item in spans:
                plot_type, x0, x1 = item[:3]
                label = item[3] if len(item) > 3 else ""
                marker_kind = item[4] if len(item) > 4 else "region"
                if not label:
                    continue
                is_interval = plot_type in {"range", "reference_region", "excluded_region"} and x1 is not None and x1 != x0
                x = (float(x0) + float(x1)) / 2 if is_interval else float(x0)
                text = f"{marker_kind}: {label}"
                fig.add_layout(Label(
                    x=x,
                    y=8,
                    x_units="data",
                    y_units="screen",
                    text=text,
                    text_font_size="9pt",
                    text_color=EVENT_COLOR,
                    background_fill_color="#0f172a",
                    background_fill_alpha=0.75,
                    border_line_alpha=0.0,
                    text_baseline="bottom",
                    text_align="center",
                ))
        except Exception:
            pass
    return hook


def baseline_span(x0: float, x1: float) -> hv.VSpan:
    return hv.VSpan(x0, x1).opts(color=BASELINE_COLOR, alpha=0.10)


def window_elements(window: tuple[float, float] | None) -> list:
    """Shade the active analysis window (the 'current range') on a full-run plot.

    Drawn in the accent color with dashed edges so it reads as the selected
    interval, distinct from the green zero/reference span and orange saved
    regions. Returned as a list so callers can splice it in before the curves.
    """
    if window is None:
        return []
    x0, x1 = float(window[0]), float(window[1])
    if x1 <= x0:
        return []
    return [
        hv.VSpan(x0, x1).opts(color=ACCENT, alpha=0.14),
        hv.VLine(x0).opts(color=ACCENT, line_dash="solid", line_width=1.4),
        hv.VLine(x1).opts(color=ACCENT, line_dash="solid", line_width=1.4),
    ]


def _time_tools(select_x: bool) -> tuple[list[str], list[str]]:
    """Tool list + active tools for a time-domain overlay.

    The x-only box-select used for range brushing is added by
    ``_xbox_select_hook`` (selection tools must attach to glyphs, so a string in
    the Overlay options is dropped). Here we only keep the scroll wheel as the
    active zoom; ``select_x`` is accepted for symmetry with the plot builders.
    """
    return ["hover", "box_zoom", "reset"], ["wheel_zoom"]


# ----------------------------------------------------------------------- plots
def timeline(
    value_df: pl.DataFrame,
    q: Quantity,
    groups: list[int],
    orders: dict[int, int],
    title: str,
    height: int = PLOT_HEIGHT,
    annotation_spans: list | None = None,
    baseline: tuple[float, float] | None = None,
    window: tuple[float, float] | None = None,
    select_x: bool = False,
):
    """Single flat overlay: per-group curves + optional baseline span + annotations."""
    labels = series_labels(groups, orders)
    elements = list(window_elements(window))
    if baseline is not None:
        elements.append(baseline_span(*baseline))
    for slot, g in enumerate(groups):
        x, y = _xy(value_df, g)
        if len(x) == 0:
            continue
        elements.append(
            hv.Curve((x, y), kdims=X_LABEL, vdims=q.axis_label, label=labels[g]).opts(
                color=color_for_slot(slot), line_width=1.8
            )
        )
    elements.extend(annotation_elements(annotation_spans or []))
    if not any(isinstance(e, hv.Curve) for e in elements):
        return empty(f"No {q.label} data")
    tools, active = _time_tools(select_x)
    hooks = [_vline_hover_hook, _legend_mute_hook, _saved_region_label_hook(annotation_spans or [])]
    if select_x:
        hooks.append(_xbox_select_hook)
    return hv.Overlay(elements).opts(
        hv.opts.Overlay(
            title=title, height=height, responsive=True, legend_position="right",
            active_tools=active, tools=tools,
            hooks=hooks, show_grid=True,
        ),
        hv.opts.Curve(tools=["hover"]),
    )


def _xy_axis(value_df: pl.DataFrame, group: int, monotonic: bool, max_points: int = MAX_PLOT_POINTS):
    """Per-group (x, y) pair for the configurable analysis plot.

    Reads the generic ``x`` column (set by the data service for the chosen
    x-axis) and ``value`` (y). Monotonic axes (time, cumulative cycle number) use
    the time-style min/max envelope after sorting by x; non-monotonic axes (a CV
    potential sweep, charge that reverses, per-cycle time) keep their measurement
    order and are capped with a uniform stride so the trajectory survives.
    """
    sub = value_df.filter(pl.col("group") == group).drop_nulls(["value", "x"])
    if sub.is_empty():
        return sub["x"].to_numpy(), sub["value"].to_numpy()
    if monotonic:
        sub = sub.sort("x")
        return _decimate_xy(sub["x"].to_numpy(), sub["value"].to_numpy(), max_points)
    sub = sub.sort("timestamp")
    x = sub["x"].to_numpy()
    y = sub["value"].to_numpy()
    if max_points > 0 and len(x) > max_points:
        step = len(x) // max_points + 1
        x, y = x[::step], y[::step]
    return x, y


def analysis_timeline(
    value_df: pl.DataFrame,
    q: Quantity,
    ax: Axis,
    groups: list[int],
    orders: dict[int, int],
    title: str,
    *,
    companion_df: pl.DataFrame | None = None,
    visible_groups: list[int] | None = None,
    companion_groups: list[int] | None = None,
    baseline: tuple[float, float] | None = None,
    window: tuple[float, float] | None = None,
    annotation_spans: list | None = None,
    select_x: bool = False,
    height: int = PLOT_HEIGHT,
):
    """Unified analysis plot: selected y-quantity vs selected x-axis.

    One curve per visible overtone for QCM resonance quantities; a single curve
    for cell-level electrochemistry quantities (potential/current/charge) since
    those are shared across overtones. When ``companion_df`` (ΔD) is supplied it
    is drawn on a twin right axis — this reproduces the canonical QCM-D figure for
    the default Δf/n-vs-time view.

    Time-based overlays (analysis window, reference span, saved-region markers,
    and the x box-select brush) are only meaningful on the time axis, so they are
    drawn only when ``ax`` is time.
    """
    on_time = ax.is_time
    labels = series_labels(groups, orders)
    visible_groups = list(groups if visible_groups is None else visible_groups)
    elements: list = list(window_elements(window)) if on_time else []
    if on_time and baseline is not None:
        elements.append(baseline_span(*baseline))

    left_curves: list = []
    if q.is_echem:
        # Cell-level signal: identical across overtones, so draw it once.
        g0 = groups[0] if groups else 0
        x, y = _xy_axis(value_df, g0, ax.monotonic)
        if len(x):
            left_curves.append(
                hv.Curve((x, y), ax.axis_label, q.axis_label, label=q.label).opts(
                    color=ACCENT, line_width=1.9
                )
            )
    else:
        for slot, g in enumerate(groups):
            if g not in visible_groups:
                continue
            x, y = _xy_axis(value_df, g, ax.monotonic)
            if not len(x):
                continue
            left_curves.append(
                hv.Curve((x, y), ax.axis_label, q.axis_label, label=labels[g]).opts(
                    color=color_for_slot(slot), line_width=1.8
                )
            )

    right_curves: list = []
    d_lo, d_hi = 0.0, 1.0
    companion_label = "ΔD  [×10⁻⁶]"
    if companion_df is not None and not companion_df.is_empty():
        comp_groups = list(groups if companion_groups is None else companion_groups)
        d_vals = companion_df.filter(pl.col("group").is_in(comp_groups)).drop_nulls("value")["value"]
        if d_vals.len():
            d_lo, d_hi = float(d_vals.min()), float(d_vals.max())
        for slot, g in enumerate(groups):
            if g not in comp_groups:
                continue
            x, y = _xy_axis(companion_df, g, ax.monotonic)
            if not len(x):
                continue
            right_curves.append(
                hv.Curve((x, y), ax.axis_label, companion_label, label=f"ΔD {labels[g]}").opts(
                    color=color_for_slot(slot), line_width=1.4, line_dash=[6, 4]
                )
            )

    elements.extend(left_curves)
    elements.extend(right_curves)
    if on_time:
        elements.extend(annotation_elements(annotation_spans or []))
    if not left_curves and not right_curves:
        return empty(f"No {q.label} data")

    tools, active = _time_tools(select_x)
    hooks: list = []
    if right_curves:
        hooks.append(_twin_axis_hook(d_lo, d_hi, companion_label))
    # Vertical-line hover only makes sense when traces share a monotonic x.
    if ax.monotonic:
        hooks.append(_vline_hover_hook)
    hooks.append(_legend_mute_hook)
    if on_time:
        hooks.append(_saved_region_label_hook(annotation_spans or []))
        if select_x:
            hooks.append(_xbox_select_hook)
    return hv.Overlay(elements).opts(
        hv.opts.Overlay(
            title=title, height=height, responsive=True, legend_position="right",
            active_tools=active, tools=tools, hooks=hooks, show_grid=True,
        ),
        hv.opts.Curve(tools=["hover"]),
    )


def _twin_axis_hook(d_lo: float, d_hi: float, axis_label: str):
    """Route dashed (ΔD) glyphs to a second right-hand y-axis."""
    def hook(plot, _element):
        from bokeh.models import LinearAxis, Range1d

        fig = plot.state
        pad = (d_hi - d_lo) * 0.08 or 1.0
        if "rhs" not in fig.extra_y_ranges:
            fig.extra_y_ranges = {**fig.extra_y_ranges, "rhs": Range1d(d_lo - pad, d_hi + pad)}
            fig.add_layout(LinearAxis(y_range_name="rhs", axis_label=axis_label), "right")
        for r in fig.renderers:
            glyph = getattr(r, "glyph", None)
            dash = getattr(glyph, "line_dash", None) if glyph is not None else None
            if list(dash or []) == [6, 4]:
                r.y_range_name = "rhs"
    return hook


def dual_axis_qcmd(
    norm_df: pl.DataFrame,
    d_df: pl.DataFrame,
    groups: list[int],
    orders: dict[int, int],
    title: str,
    raw_f_df: pl.DataFrame | None = None,
    frequency_groups: list[int] | None = None,
    dissipation_groups: list[int] | None = None,
    normalized_frequency_groups: set[int] | None = None,
    baseline: tuple[float, float] | None = None,
    annotation_spans: list | None = None,
    window: tuple[float, float] | None = None,
    select_x: bool = False,
    height: int = HERO_HEIGHT,
):
    """Canonical QCM-D plot: Δf/n (left, solid) and ΔD (right, dashed)."""
    labels = series_labels(groups, orders)
    frequency_groups = list(groups if frequency_groups is None else frequency_groups)
    dissipation_groups = list(groups if dissipation_groups is None else dissipation_groups)
    normalized_frequency_groups = set(groups if normalized_frequency_groups is None else normalized_frequency_groups)
    mixed_frequency_scale = any(g not in normalized_frequency_groups for g in frequency_groups)
    left_axis = "Δf / n or Δf  [Hz]" if mixed_frequency_scale else "Δf / n  [Hz]"
    left, right = [], []
    for slot, g in enumerate(groups):
        color = color_for_slot(slot)
        if g in frequency_groups:
            use_norm = g in normalized_frequency_groups or raw_f_df is None
            f_df = norm_df if use_norm else raw_f_df
            f_label = "Δf/n" if use_norm else "Δf"
            fx, fy = _xy(f_df, g)
        else:
            fx, fy = [], []
        if len(fx):
            left.append(
                hv.Curve((fx, fy), X_LABEL, left_axis, label=f"{f_label} {labels[g]}").opts(
                    color=color, line_width=2.0
                )
            )
        if g in dissipation_groups:
            dx, dy = _xy(d_df, g)
        else:
            dx, dy = [], []
        if len(dx):
            right.append(
                hv.Curve((dx, dy), X_LABEL, "ΔD  [×10⁻⁶]", label=f"ΔD {labels[g]}").opts(
                    color=color, line_width=1.4, line_dash=[6, 4]
                )
            )
    if not left and not right:
        return empty("No QCM-D data")

    d_vals = d_df.filter(pl.col("group").is_in(dissipation_groups)).drop_nulls("value")["value"]
    d_lo = float(d_vals.min()) if d_vals.len() else 0.0
    d_hi = float(d_vals.max()) if d_vals.len() else 1.0

    elements = (
        list(window_elements(window))
        + ([baseline_span(*baseline)] if baseline is not None else [])
        + annotation_elements(annotation_spans or [])
        + left
        + right
    )
    tools, active = _time_tools(select_x)
    hooks = [_twin_axis_hook(d_lo, d_hi, "ΔD  [×10⁻⁶]"), _vline_hover_hook, _legend_mute_hook, _saved_region_label_hook(annotation_spans or [])]
    if select_x:
        hooks.append(_xbox_select_hook)
    return hv.Overlay(elements).opts(
        hv.opts.Overlay(
            title=title, height=height, responsive=True, legend_position="right",
            active_tools=active, tools=tools,
            hooks=hooks,
            show_grid=True,
        ),
        hv.opts.Curve(tools=["hover"]),
    )


def df_fingerprint(norm_df: pl.DataFrame, d_df: pl.DataFrame, groups: list[int], orders: dict[int, int]):
    """ΔD-vs-Δf/n viscoelastic fingerprint (the 'Df plot'), per overtone."""
    labels = series_labels(groups, orders)
    joined = norm_df.rename({"value": "df"}).join(
        d_df.rename({"value": "dD"}), on=["timestamp", "group"], how="inner"
    ).sort("timestamp")
    if joined.is_empty():
        return empty("No Df data")
    paths = []
    for slot, g in enumerate(groups):
        sub = joined.filter(pl.col("group") == g)
        if sub.is_empty():
            continue
        dfx = sub["df"].to_numpy()
        dDy = sub["dD"].to_numpy()
        # Phase portrait: x is not time-monotonic, so envelope decimation does not
        # apply. Cap the trajectory with a uniform stride to bound browser cost.
        if len(dfx) > MAX_PLOT_POINTS:
            step = len(dfx) // MAX_PLOT_POINTS + 1
            dfx, dDy = dfx[::step], dDy[::step]
        paths.append(
            hv.Curve((dfx, dDy), "Δf / n  [Hz]", "ΔD  [×10⁻⁶]", label=labels[g]).opts(
                color=color_for_slot(slot), line_width=1.6
            )
        )
    if not paths:
        return empty("No Df data")
    return hv.Overlay(paths).opts(
        hv.opts.Overlay(
            title="Df plot — ΔD vs Δf/n (viscoelastic fingerprint)",
            height=COMPACT_PLOT_HEIGHT, responsive=True, legend_position="right",
            active_tools=["wheel_zoom"], tools=["hover", "box_zoom", "reset"],
            hooks=[_legend_mute_hook], show_grid=True,
        ),
        hv.opts.Curve(tools=["hover"]),
    )


def echem_curve(
    wf: pl.DataFrame,
    xcol: str,
    ycol: str,
    xlabel: str,
    ylabel: str,
    title: str,
    *,
    by_cycle: bool = True,
    monotonic: bool = False,
    height: int = PLOT_HEIGHT,
):
    """One line plot of an electrochemistry waveform (one row per sweep).

    When ``by_cycle`` is set each cycle is drawn as its own colored trace, which
    gives the familiar per-cycle overlay for an i–E voltammogram or a CP
    capacity curve. ``monotonic`` selects the time-style min/max envelope
    decimation for axes that increase with time (vs a uniform stride for phase
    portraits whose x reverses, like i–E or E–charge loops).
    """
    if wf.is_empty() or xcol not in wf.columns or ycol not in wf.columns:
        return empty(f"No {ylabel} data")
    sort_col = "time_s" if "time_s" in wf.columns else xcol

    def _decimate(x, y):
        if monotonic:
            return _decimate_xy(x, y)
        if len(x) > MAX_PLOT_POINTS:
            step = len(x) // MAX_PLOT_POINTS + 1
            return x[::step], y[::step]
        return x, y

    curves: list = []
    if by_cycle and "cycle" in wf.columns:
        cycles = sorted(int(c) for c in wf["cycle"].unique().drop_nulls().to_list())
        for slot, cyc in enumerate(cycles):
            sub = wf.filter(pl.col("cycle") == cyc).sort(sort_col).drop_nulls([xcol, ycol])
            if sub.is_empty():
                continue
            x, y = _decimate(sub[xcol].to_numpy(), sub[ycol].to_numpy())
            if not len(x):
                continue
            curves.append(
                hv.Curve((x, y), xlabel, ylabel, label=f"cycle {cyc}").opts(
                    color=color_for_slot(slot), line_width=1.5
                )
            )
    else:
        sub = wf.sort(sort_col).drop_nulls([xcol, ycol])
        if not sub.is_empty():
            x, y = _decimate(sub[xcol].to_numpy(), sub[ycol].to_numpy())
            if len(x):
                curves.append(
                    hv.Curve((x, y), xlabel, ylabel).opts(color=ACCENT, line_width=1.7)
                )

    if not curves:
        return empty(f"No {ylabel} data")
    hooks = [_legend_mute_hook]
    if monotonic:
        hooks.insert(0, _vline_hover_hook)
    return hv.Overlay(curves).opts(
        hv.opts.Overlay(
            title=title, height=height, responsive=True, legend_position="right",
            active_tools=["wheel_zoom"], tools=["hover", "box_zoom", "reset"],
            hooks=hooks, show_grid=True,
        ),
        hv.opts.Curve(tools=["hover"]),
    )


WATERFALL_PANEL_HEIGHT = 240


def waterfall(df: pl.DataFrame, orders: dict[int, int] | None = None) -> list:
    """One conductance-over-time heatmap per overtone.

    Overtones sit megahertz apart while each resonance band is only ~kHz wide,
    so a single shared frequency axis squashes every band into an unreadable
    stripe. Splitting into one rasterized panel per group gives each overtone
    its own tight frequency axis. Time (elapsed seconds) is on x because
    Datashader rejects uint timestamps; conductance is the color.
    """
    if df.is_empty():
        return [empty("No waterfall data")]
    orders = orders or {}
    groups = sorted(int(g) for g in df["group"].unique().to_list())
    panels = []
    for g in groups:
        sub = df.filter(pl.col("group") == g)
        if sub.is_empty():
            continue
        n = orders.get(g)
        who = f"n={n}" if n and n > 1 else f"group {g}"
        fcenter = float(sub["frequency"].median())
        panels.append(
            sub.hvplot.scatter(
                x=X, y="frequency", c="conductance",
                rasterize=True, dynspread=True, cmap="viridis",
                responsive=True, height=WATERFALL_PANEL_HEIGHT,
                title=f"{who} · f ≈ {fcenter:,.0f} Hz",
                xlabel=X_LABEL, ylabel="Frequency [Hz]", clabel="Conductance",
            ).opts(
                active_tools=["wheel_zoom"], tools=["hover", "box_zoom", "reset"],
                show_grid=True, axiswise=True, shared_axes=False,
            )
        )
    return panels or [empty("No waterfall data")]



def _sweep_center(sub: pl.DataFrame, f: "np.ndarray") -> float:
    """Best resonance center for a single-overtone sweep."""
    if "fit_center" in sub.columns:
        c = sub["fit_center"].drop_nulls()
        if c.len():
            center = float(c[0])
            if f.min() <= center <= f.max():
                return center

    if "conductance" in sub.columns and sub.height:
        return float(f[int(sub["conductance"].arg_max() or 0)])

    return float(f[len(f) // 2])


def _force_x_range_hook(lo: float, hi: float):
    """Force Bokeh to render each sweep panel tightly around its own data."""
    def hook(plot, _element):
        try:
            fig = plot.state
            pad = (hi - lo) * 0.02 or 1.0
            start = lo - pad
            end = hi + pad

            fig.x_range.start = start
            fig.x_range.end = end
            fig.x_range.reset_start = start
            fig.x_range.reset_end = end
        except Exception:
            pass

    return hook


def _numeric_fit_columns(sub: pl.DataFrame) -> list[str]:
    """Return saved numeric fit columns, excluding scalar fit parameters."""
    excluded = {
        "fit_center",
        "fit_width",
        "fit_gamma",
        "fit_amplitude",
        "fit_offset",
        "fit_phase",
        "fit_quality",
        "fit_error",
        "fit_rmse",
        "fit_r2",
    }

    cols = []
    for c in sub.columns:
        cl = c.lower()
        if "fit" not in cl:
            continue
        if cl in excluded:
            continue
        if not sub[c].dtype.is_numeric():
            continue
        if sub[c].null_count() >= sub.height:
            continue
        if sub[c].n_unique() <= 1:
            continue
        cols.append(c)

    return cols


def sweep_curves(df: pl.DataFrame, orders: dict[int, int] | None = None) -> list:
    """One zoomed resonance panel per overtone, including saved fit curves.

    Each overtone gets its own independent Bokeh x-range. This prevents high
    overtones that are MHz apart from forcing every resonance to look like a
    narrow spike.

    Any numeric saved curve column containing "fit" is plotted as a fit curve,
    except scalar fit-parameter columns such as fit_center.
    """
    if df.is_empty():
        return [empty("No sweep")]

    orders = orders or {}
    groups = sorted(int(g) for g in df["group"].unique().to_list())
    panels = []

    for slot, g in enumerate(groups):
        sub = df.filter(pl.col("group") == g).sort("frequency")
        if sub.is_empty():
            continue

        f = sub["frequency"].to_numpy()
        gcond = sub["conductance"].to_numpy()
        bsusc = sub["susceptance"].to_numpy()

        lo = float(np.nanmin(f))
        hi = float(np.nanmax(f))

        color = color_for_slot(slot)
        n = orders.get(g)
        who = f"n={n}" if n and n > 1 else f"group {g}"
        center = _sweep_center(sub, f)

        curves = [
            hv.Curve(
                (f, gcond),
                "Frequency [Hz]",
                "Signal [a.u.]",
                label="G data",
            ).opts(
                color=color,
                line_width=1.9,
            ),
            hv.Curve(
                (f, bsusc),
                "Frequency [Hz]",
                "Signal [a.u.]",
                label="B data",
            ).opts(
                color=color,
                line_width=1.3,
                line_dash="dashed",
                alpha=0.8,
            ),
        ]

        for fit_col in _numeric_fit_columns(sub):
            curves.append(
                hv.Curve(
                    (f, sub[fit_col].to_numpy()),
                    "Frequency [Hz]",
                    "Signal [a.u.]",
                    label=fit_col,
                ).opts(
                    color=color,
                    line_width=2.1,
                    line_dash="dotdash",
                    alpha=0.95,
                )
            )

        panels.append(
            hv.Overlay(curves).opts(
                hv.opts.Overlay(
                    title=f"{who} · f₀ ≈ {center:,.0f} Hz",
                    height=SWEEP_PANEL_HEIGHT,
                    responsive=True,
                    framewise=True,
                    axiswise=True,
                    shared_axes=False,
                    legend_position="top_right",
                    active_tools=["wheel_zoom"],
                    tools=["hover", "box_zoom", "reset"],
                    hooks=[_force_x_range_hook(lo, hi), _vline_hover_hook, _legend_mute_hook],
                    show_grid=True,
                ),
                hv.opts.Curve(tools=["hover"]),
            )
        )

    return panels or [empty("No sweep")]


def _zoom_scale_markers_hook(ref_x_span: float, ref_y_span: float, max_scale: float = 12.0):
    """Grow scatter markers as the view zooms in.

    Bokeh marker ``size`` is in screen pixels, so points stay the same size at
    every zoom level — zooming into a sparse cloud feels like it reveals less.
    This attaches a JS callback that rescales every marker glyph by how far the
    current view is zoomed in relative to the full data extent, so points get
    bigger the closer you look (clamped to ``max_scale``×). Kept client-side so
    it costs nothing on the server and stays smooth.
    """
    def hook(plot, _element):
        try:
            from bokeh.models import CustomJS

            fig = plot.state
            glyphs = [
                r.glyph for r in fig.renderers
                if hasattr(getattr(r, "glyph", None), "size")
            ]
            if not glyphs:
                return
            base = float(getattr(glyphs[0], "size", 4) or 4)
            callback = CustomJS(
                args=dict(
                    glyphs=glyphs, xr=fig.x_range, yr=fig.y_range,
                    base=base, refx=ref_x_span, refy=ref_y_span, maxs=max_scale,
                ),
                code="""
                    const xs = xr.end - xr.start
                    const ys = yr.end - yr.start
                    if (!(xs > 0) || !(ys > 0)) { return }
                    let scale = Math.sqrt((refx / xs) * (refy / ys))
                    if (!(scale > 0)) { scale = 1 }
                    scale = Math.min(Math.max(scale, 1.0), maxs)
                    const size = base * scale
                    for (const glyph of glyphs) { glyph.size = size }
                """,
            )
            for rng in (fig.x_range, fig.y_range):
                rng.js_on_change("start", callback)
                rng.js_on_change("end", callback)
        except Exception:
            pass

    return hook


def iq_scatter(df: pl.DataFrame, title: str):
    if df.is_empty():
        return empty("No I/Q")
    # Native (non-rasterized) markers so each point stays crisp and inspectable;
    # the I/Q cloud is small (tens of points per sweep). Markers are pixel-sized,
    # so _zoom_scale_markers_hook grows them as you zoom in to keep the cloud
    # readable instead of shrinking into specks.
    ix = df["raw_i"].drop_nulls()
    iy = df["raw_q"].drop_nulls()
    ref_x = float(ix.max() - ix.min()) if ix.len() else 1.0
    ref_y = float(iy.max() - iy.min()) if iy.len() else 1.0
    return df.hvplot.scatter(
        x="raw_i", y="raw_q", by="group",
        responsive=True, height=PLOT_HEIGHT, title=title, size=5, alpha=0.65,
        xlabel="Raw I [a.u.]", ylabel="Raw Q [a.u.]",
    ).opts(
        active_tools=["wheel_zoom"], tools=["hover", "box_zoom", "reset"], show_grid=True,
        hooks=[_zoom_scale_markers_hook(ref_x or 1.0, ref_y or 1.0)],
    )
