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
import polars as pl

from .theme import (
    BASELINE_COLOR,
    EVENT_COLOR,
    HERO_HEIGHT,
    PLOT_HEIGHT,
    Quantity,
    color_for_slot,
)

X = "elapsed_s"
X_LABEL = "Time [s]"


# --------------------------------------------------------------------- helpers
def empty(title: str):
    return hv.Curve([]).opts(title=title, height=PLOT_HEIGHT, responsive=True)


def series_labels(groups: list[int], orders: dict[int, int]) -> dict[int, str]:
    """Legend label per group: use ``n=…`` when overtone orders are distinct."""
    ns = [orders.get(g, 1) for g in groups]
    if len(set(ns)) == len(ns) and any(n > 1 for n in ns):
        return {g: f"n={orders.get(g, 1)}" for g in groups}
    return {g: f"group {g}" for g in groups}


def _xy(value_df: pl.DataFrame, group: int):
    sub = value_df.filter(pl.col("group") == group).drop_nulls("value")
    return sub[X].to_numpy(), sub["value"].to_numpy()


def _legend_mute_hook(plot, _element):
    """Click a legend entry to mute/unmute its trace."""
    try:
        for legend in plot.state.legend:
            legend.click_policy = "mute"
            legend.label_text_font_size = "9pt"
    except Exception:
        pass


def annotation_elements(spans) -> list:
    """``spans`` is a list of (kind, x0_s, x1_s) tuples already in seconds."""
    elements = []
    for kind, x0, x1 in spans:
        if kind in {"range", "reference_region", "excluded_region"} and x1 is not None and x1 != x0:
            color = BASELINE_COLOR if kind == "reference_region" else EVENT_COLOR
            elements.append(hv.VSpan(x0, x1).opts(color=color, alpha=0.12))
        else:
            elements.append(hv.VLine(x0).opts(color=EVENT_COLOR, line_dash="dashed", line_width=1))
    return elements


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
            active_tools=["wheel_zoom"], tools=["crosshair"],
            hooks=[_legend_mute_hook], show_grid=True,
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

    elements = ([baseline_span(*baseline)] if baseline is not None else []) + left + right
    return hv.Overlay(elements).opts(
        hv.opts.Overlay(
            title=title, height=HERO_HEIGHT, responsive=True, legend_position="right",
            active_tools=["wheel_zoom"], tools=["crosshair"],
            hooks=[_twin_axis_hook(d_lo, d_hi, "ΔD  [×10⁻⁶]"), _legend_mute_hook],
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
        paths.append(
            hv.Curve((sub["df"].to_numpy(), sub["dD"].to_numpy()), "Δf / n  [Hz]", "ΔD  [×10⁻⁶]", label=labels[g]).opts(
                color=color_for_slot(slot), line_width=1.6
            )
        )
    if not paths:
        return empty("No Df data")
    return hv.Overlay(paths).opts(
        hv.opts.Overlay(
            title="Df plot — ΔD vs Δf/n (viscoelastic fingerprint)",
            height=PLOT_HEIGHT, responsive=True, legend_position="right",
            active_tools=["wheel_zoom"], tools=["crosshair"],
            hooks=[_legend_mute_hook], show_grid=True,
        ),
        hv.opts.Curve(tools=["hover"]),
    )


def waterfall(df: pl.DataFrame, title: str):
    if df.is_empty():
        return empty("No waterfall data")
    # Datashader rejects uint timestamps; we plot elapsed seconds anyway.
    return df.hvplot.scatter(
        x=X, y="frequency", c="conductance",
        rasterize=True, dynspread=False, cmap="viridis",
        responsive=True, height=PLOT_HEIGHT, title=title,
        xlabel=X_LABEL, ylabel="Frequency [Hz]", clabel="Conductance",
    ).opts(active_tools=["wheel_zoom"], tools=["hover", "crosshair"], show_grid=True)


def sweep_curves(df: pl.DataFrame, title: str):
    if df.is_empty():
        return empty("No sweep")
    return df.hvplot.line(
        x="frequency", y=["conductance", "susceptance"], by="group",
        responsive=True, height=PLOT_HEIGHT, title=title,
        xlabel="Frequency [Hz]", ylabel="Signal [a.u.]",
    ).opts(active_tools=["wheel_zoom"], tools=["hover", "crosshair"], legend_position="right", show_grid=True)


def iq_scatter(df: pl.DataFrame, title: str):
    if df.is_empty():
        return empty("No I/Q")
    return df.hvplot.scatter(
        x="raw_i", y="raw_q", by="group", rasterize=True,
        responsive=True, height=PLOT_HEIGHT, title=title,
        xlabel="Raw I [a.u.]", ylabel="Raw Q [a.u.]",
    ).opts(active_tools=["wheel_zoom"], tools=["hover", "crosshair"], show_grid=True)
