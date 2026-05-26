"""Pure Polars transforms that turn fit columns into displayable QCM quantities.

The viewer thinks in *shifts relative to a baseline* and *overtone-normalized*
signals, so this module:

1. derives a per-row scalar ``value`` for any registered quantity,
2. subtracts the per-group mean over a chosen baseline window, and
3. divides frequency-like shifts by the overtone order n.

All functions are side-effect free and return new frames.
"""
from __future__ import annotations

import polars as pl

from .theme import DISSIPATION_SCALE, SAUERBREY_CONSTANT, Quantity, quantity as get_quantity

_KEEP = ("timestamp", "group")


def _raw_value(df: pl.DataFrame, q: Quantity) -> pl.Expr:
    """The per-row scalar for a quantity *before* referencing/normalization."""
    if q.kind == "dissipation":
        return (pl.col("fit_fwhm") / pl.col("fit_center") * DISSIPATION_SCALE)
    if q.kind == "ratio":  # quality factor
        return (pl.col("fit_center") / pl.col("fit_fwhm"))
    if q.kind in ("frequency", "mass"):
        return pl.col("fit_center")  # referencing turns this into Δf
    # raw passthrough (fit_center absolute, fit_fwhm, fit_gamma)
    return pl.col(q.sources[0])


def baseline_means(baseline_df: pl.DataFrame, quantity_key: str) -> pl.DataFrame:
    """Per-group mean of a quantity's raw value over the baseline window."""
    q = get_quantity(quantity_key)
    if baseline_df.is_empty():
        return pl.DataFrame({"group": [], "baseline": []})
    return (
        baseline_df.with_columns(_raw_value(baseline_df, q).alias("_v"))
        .group_by("group")
        .agg(pl.col("_v").mean().alias("baseline"))
    )


def compute(
    df: pl.DataFrame,
    quantity_key: str,
    orders: dict[int, int],
    baseline_df: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Return a tidy frame ``[timestamp, group, value]`` for the given quantity.

    ``orders`` maps group -> overtone order n. ``baseline_df`` (raw fit columns
    over the baseline window) is required for referenced quantities; without it
    a referenced quantity falls back to using each group's first sample.
    """
    q = get_quantity(quantity_key)
    if df.is_empty():
        return df.select([*_KEEP]).with_columns(pl.lit(None, dtype=pl.Float64).alias("value"))

    out = df.select([*_KEEP, *q.sources]).with_columns(_raw_value(df, q).alias("value"))

    if q.referenced:
        if baseline_df is not None and not baseline_df.is_empty():
            base = baseline_means(baseline_df, quantity_key)
        else:  # fallback: first sample per group
            base = out.group_by("group").agg(pl.col("value").first().alias("baseline"))
        out = out.join(base, on="group", how="left").with_columns(
            (pl.col("value") - pl.col("baseline").fill_null(0.0)).alias("value")
        )

    if q.normalized:
        n_expr = pl.col("group").replace_strict(orders, default=1, return_dtype=pl.Int64)
        out = out.with_columns((pl.col("value") / n_expr).alias("value"))

    if q.kind == "mass":  # Sauerbrey: m = -C * (Δf / n)
        out = out.with_columns((-SAUERBREY_CONSTANT * pl.col("value")).alias("value"))

    return out.select([*_KEEP, "value"]).sort(["timestamp", "group"])


def summary_stats(value_df: pl.DataFrame) -> pl.DataFrame:
    """Per-group mean/std/min/max and net change for a computed value frame."""
    if value_df.is_empty():
        return pl.DataFrame()
    return (
        value_df.group_by("group")
        .agg(
            pl.col("value").mean().alias("mean"),
            pl.col("value").std().alias("std"),
            pl.col("value").min().alias("min"),
            pl.col("value").max().alias("max"),
            (pl.col("value").last() - pl.col("value").first()).alias("net_change"),
            pl.len().alias("points"),
        )
        .sort("group")
    )
