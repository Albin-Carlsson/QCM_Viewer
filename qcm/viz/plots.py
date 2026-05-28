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
    BASELINE_COLOR,
    EVENT_COLOR,
    HERO_HEIGHT,
    MAX_PLOT_POINTS,
    PLOT_HEIGHT,
    Quantity,
    color_for_slot,
)

X = "elapsed_s"
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
):
    """Single flat overlay: per-group curves + optional baseline span + annotations."""
    labels = series_labels(groups, orders)
    elements = []
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
    return hv.Overlay(elements).opts(
        hv.opts.Overlay(
            title=title, height=height, responsive=True, legend_position="right",
            active_tools=["wheel_zoom"], tools=["hover", "box_zoom", "reset"],
            hooks=[_vline_hover_hook, _legend_mute_hook, _saved_region_label_hook(annotation_spans or [])], show_grid=True,
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
    baseline: tuple[float, float] | None = None,
    annotation_spans: list | None = None,
):
    """Canonical QCM-D plot: Δf/n (left, solid) and ΔD (right, dashed)."""
    labels = series_labels(groups, orders)
    left, right = [], []
    for slot, g in enumerate(groups):
        color = color_for_slot(slot)
        fx, fy = _xy(norm_df, g)
        if len(fx):
            left.append(
                hv.Curve((fx, fy), X_LABEL, "Δf / n  [Hz]", label=f"Δf/n {labels[g]}").opts(
                    color=color, line_width=2.0
                )
            )
        dx, dy = _xy(d_df, g)
        if len(dx):
            right.append(
                hv.Curve((dx, dy), X_LABEL, "Δf / n  [Hz]", label=f"ΔD {labels[g]}").opts(
                    color=color, line_width=1.4, line_dash=[6, 4]
                )
            )
    if not left and not right:
        return empty("No QCM-D data")

    d_vals = d_df.drop_nulls("value")["value"]
    d_lo = float(d_vals.min()) if d_vals.len() else 0.0
    d_hi = float(d_vals.max()) if d_vals.len() else 1.0

    elements = ([baseline_span(*baseline)] if baseline is not None else []) + annotation_elements(annotation_spans or []) + left + right
    return hv.Overlay(elements).opts(
        hv.opts.Overlay(
            title=title, height=HERO_HEIGHT, responsive=True, legend_position="right",
            active_tools=["wheel_zoom"], tools=["hover", "box_zoom", "reset"],
            hooks=[_twin_axis_hook(d_lo, d_hi, "ΔD  [×10⁻⁶]"), _vline_hover_hook, _legend_mute_hook, _saved_region_label_hook(annotation_spans or [])],
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
            height=PLOT_HEIGHT, responsive=True, legend_position="right",
            active_tools=["wheel_zoom"], tools=["hover", "box_zoom", "reset"],
            hooks=[_legend_mute_hook], show_grid=True,
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


SWEEP_PANEL_HEIGHT = 220


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
