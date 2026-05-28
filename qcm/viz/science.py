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


def raw_value_sql(q: Quantity) -> str:
    """DuckDB scalar expression mirroring :func:`_raw_value`.

    Used to push the per-row baseline value into SQL so the per-group mean can be
    aggregated in DuckDB instead of pulling the whole baseline window into Python.
    Must stay in lockstep with ``_raw_value`` so the numbers are identical.
    """
    if q.kind == "dissipation":
        return f"(fit_fwhm / fit_center * {DISSIPATION_SCALE})"
    if q.kind == "ratio":  # quality factor
        return "(fit_center / fit_fwhm)"
    if q.kind in ("frequency", "mass"):
        return "fit_center"
    return q.sources[0]


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
    baseline_means_df: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Return a tidy frame ``[timestamp, group, value]`` for the given quantity.

    ``orders`` maps group -> overtone order n. For referenced quantities the
    per-group baseline mean can be supplied two ways:

    - ``baseline_means_df``: a precomputed ``[group, baseline]`` frame (e.g. from
      :meth:`QCMRun.baseline_mean`), used as-is. This is the fast path — the
      baseline window never enters Python row-by-row.
    - ``baseline_df``: raw fit columns over the baseline window, reduced here.

    Without either, a referenced quantity falls back to each group's first sample.
    """
    q = get_quantity(quantity_key)
    if df.is_empty():
        return df.select([*_KEEP]).with_columns(pl.lit(None, dtype=pl.Float64).alias("value"))

    out = df.select([*_KEEP, *q.sources]).with_columns(_raw_value(df, q).alias("value"))

    if q.referenced:
        if baseline_means_df is not None and not baseline_means_df.is_empty():
            base = baseline_means_df
        elif baseline_df is not None and not baseline_df.is_empty():
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
    """Comprehensive per-group statistics for a computed value frame.

    The input is expected to contain ``timestamp``, ``group``, and ``value``.
    Timestamps are stored in microseconds. The returned table is intentionally
    wide because it is used as an analysis/export table, not just a tiny UI card.
    """
    if value_df.is_empty():
        return pl.DataFrame()

    clean = value_df.sort(["group", "timestamp"]).with_columns(
        ((pl.col("timestamp") - pl.col("timestamp").min().over("group")) / 1_000_000).alias("elapsed_s"),
    )

    return (
        clean.group_by("group")
        .agg(
            pl.len().alias("rows"),
            pl.col("value").count().alias("valid"),
            pl.col("value").null_count().alias("missing"),
            pl.col("timestamp").min().alias("start_us"),
            pl.col("timestamp").max().alias("end_us"),
            ((pl.col("timestamp").max() - pl.col("timestamp").min()) / 1_000_000).alias("duration_s"),
            pl.col("value").first().alias("first"),
            pl.col("value").last().alias("last"),
            (pl.col("value").last() - pl.col("value").first()).alias("net_change"),
            (pl.col("value").last() - pl.col("value").first()).abs().alias("abs_net_change"),
            pl.col("value").mean().alias("mean"),
            pl.col("value").median().alias("median"),
            pl.col("value").std().alias("std"),
            pl.col("value").var().alias("variance"),
            pl.col("value").min().alias("min"),
            pl.col("value").quantile(0.01).alias("q01"),
            pl.col("value").quantile(0.05).alias("q05"),
            pl.col("value").quantile(0.10).alias("q10"),
            pl.col("value").quantile(0.25).alias("q25"),
            pl.col("value").quantile(0.75).alias("q75"),
            pl.col("value").quantile(0.90).alias("q90"),
            pl.col("value").quantile(0.95).alias("q95"),
            pl.col("value").quantile(0.99).alias("q99"),
            pl.col("value").max().alias("max"),
            pl.col("value").abs().mean().alias("mean_abs"),
            (pl.col("value") ** 2).mean().sqrt().alias("rms"),
            pl.col("value").diff().abs().mean().alias("mean_abs_step"),
            pl.col("value").diff().std().alias("step_std"),
            (pl.col("value").abs().sum()).alias("sum_abs"),
            pl.col("value").sum().alias("sum"),
        )
        .with_columns(
            (pl.col("max") - pl.col("min")).alias("range"),
            (pl.col("q75") - pl.col("q25")).alias("iqr"),
            pl.when(pl.col("valid") > 0).then(pl.col("std") / pl.col("valid").sqrt()).otherwise(None).alias("sem"),
            pl.when(pl.col("duration_s") > 0).then(pl.col("net_change") / pl.col("duration_s")).otherwise(None).alias("slope_per_s"),
            pl.when(pl.col("mean").abs() > 0).then(pl.col("std") / pl.col("mean").abs()).otherwise(None).alias("cv"),
            pl.when(pl.col("duration_s") > 0).then(pl.col("sum") / pl.col("duration_s")).otherwise(None).alias("time_average_proxy"),
        )
        .sort("group")
    )
