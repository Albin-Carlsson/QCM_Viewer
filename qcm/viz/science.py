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

from .theme import (
    ALIGNMENT_MAX_LAG_S,
    CHARGE_EPS_C,
    DEFAULT_PARAMS,
    DESPIKE_THRESHOLD_SIGMA,
    DESPIKE_WINDOW_DEFAULT,
    DISSIPATION_SCALE,
    FARADAY_CONSTANT,
    FREQ_EPS_HZ,
    MAD_TO_SIGMA,
    MPE_SAVGOL_POLYORDER,
    MPE_SMOOTH_WINDOW_DEFAULT,
    NG_PER_CM2_TO_G,
    ExperimentParams,
    Quantity,
    quantity as get_quantity,
)

_KEEP = ("timestamp", "group")


def _raw_value(df: pl.DataFrame, q: Quantity) -> pl.Expr:
    """The per-row scalar for a quantity *before* referencing/normalization."""
    if q.kind == "dissipation":
        return (pl.col("fit_fwhm") / pl.col("fit_center") * DISSIPATION_SCALE)
    if q.kind == "ratio":  # quality factor
        return (pl.col("fit_center") / pl.col("fit_fwhm"))
    if q.kind in ("frequency", "mass", "mpe"):
        # MPE/mass start from Δf/n (referencing turns fit_center into Δf).
        return pl.col("fit_center")
    if q.kind == "echem_density":
        # Current density = current / electrode area. The area division is applied
        # in ``compute`` from the run's editable params, so the per-row raw value
        # here is just the current (keeps the configured area authoritative).
        return pl.col("current")
    if q.kind == "echem":  # potential, current, charge — straight passthrough
        return pl.col(q.sources[0])
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
    if q.kind in ("frequency", "mass", "mpe"):
        return "fit_center"
    if q.kind == "echem_density":
        # Area division happens in Python (see ``_raw_value``); current density is
        # not a referenced quantity, so this SQL path is unused but kept honest.
        return "current"
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
    params: ExperimentParams | None = None,
) -> pl.DataFrame:
    """Return a tidy frame ``[timestamp, group, value]`` for the given quantity.

    ``orders`` maps group -> overtone order n. ``params`` carries the editable
    experiment parameters (Sauerbrey sensitivity and electrode area) used by the
    mass and MPE quantities; it defaults to the standard 5 MHz / 1 cm² values.
    For referenced quantities the per-group baseline mean can be supplied two
    ways:

    - ``baseline_means_df``: a precomputed ``[group, baseline]`` frame (e.g. from
      :meth:`QCMRun.baseline_mean`), used as-is. This is the fast path — the
      baseline window never enters Python row-by-row.
    - ``baseline_df``: raw fit columns over the baseline window, reduced here.

    Without either, a referenced quantity falls back to each group's first sample.
    """
    params = params or DEFAULT_PARAMS
    q = get_quantity(quantity_key)
    if df.is_empty():
        return df.select([*_KEEP]).with_columns(pl.lit(None, dtype=pl.Float64).alias("value"))

    out = df.select([*_KEEP, *q.sources]).with_columns(_raw_value(df, q).alias("value"))

    if q.kind == "echem_density":
        # Current density honors the run's configured electrode area.
        out = out.with_columns((pl.col("value") / params.area_cm2).alias("value"))

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

    if q.kind in ("mass", "mpe"):  # Sauerbrey areal mass: m = -C * (Δf / n)
        out = out.with_columns((-params.sensitivity * pl.col("value")).alias("value"))

    if q.kind == "mpe":
        # Mass per electron = F · d(total mass)/d(charge). Areal mass (ng/cm²) is
        # converted to total mass in grams (× area cm² × 1e-9 ng→g) before the
        # Faraday slope, so the result is a molar mass (g/mol). Computed as a
        # finite difference per overtone over time; steps with no charge change
        # are left null instead of dividing by zero.
        out = out.sort(["group", "timestamp"]).with_columns(
            (pl.col("value") * params.area_cm2 * NG_PER_CM2_TO_G).alias("_mass_g")
        )
        dq = pl.col("charge").diff().over("group")
        dm = pl.col("_mass_g").diff().over("group")
        # Reported as a positive magnitude (g/mol) so it compares directly against
        # the theoretical M/z target. The leading minus cancels the cumulative
        # cathodic-charge sign (plating: Δm>0, Δq<0) that would otherwise make the
        # ratio negative.
        out = out.with_columns(
            pl.when(dq.abs() > CHARGE_EPS_C)
            .then(-FARADAY_CONSTANT * dm / dq)
            .otherwise(None)
            .alias("value")
        )

    return out.select([*_KEEP, "value"]).sort(["timestamp", "group"])


def smooth_clip_mpe(
    value_df: pl.DataFrame,
    *,
    clip: tuple[float, float] | None = None,
    smooth: bool = False,
    window: int = MPE_SMOOTH_WINDOW_DEFAULT,
    polyorder: int = MPE_SAVGOL_POLYORDER,
) -> pl.DataFrame:
    """Clip MPE outliers and optionally Savitzky–Golay smooth, per group.

    The dynamic MPE (Δf/ΔQ) is very noisy and spikes where the charge barely
    changes. ``clip`` first bounds values to ``(lo, hi)`` so those artifacts don't
    dominate; ``smooth`` then applies a Savgol filter along time within each group
    (window auto-shrunk to an odd value ≤ the group length). Input/return frames
    carry ``timestamp, group, value`` (plus any extra columns, preserved).
    """
    if value_df.is_empty() or "value" not in value_df.columns:
        return value_df
    out = value_df
    if clip is not None:
        lo, hi = sorted(clip)
        out = out.with_columns(pl.col("value").clip(lo, hi).alias("value"))
    if not smooth:
        return out

    import numpy as np
    from scipy.signal import savgol_filter

    out = out.sort(["group", "timestamp"])

    def _smooth_group(df: pl.DataFrame) -> pl.DataFrame:
        y = df["value"].to_numpy()
        mask = ~np.isnan(y)
        n = int(mask.sum())
        w = min(int(window), n)
        if w % 2 == 0:
            w -= 1
        if w >= 5 and w > polyorder:
            sm = y.copy()
            sm[mask] = savgol_filter(y[mask], w, polyorder)
            # ``y`` carried NaN where the source was null; keep those as nulls
            # (not NaN) so downstream drop_nulls/stats behave.
            df = df.with_columns(pl.Series("value", sm).fill_nan(None))
        return df

    return out.group_by("group", maintain_order=True).map_groups(_smooth_group)


def despike(
    value_df: pl.DataFrame,
    *,
    window: int = DESPIKE_WINDOW_DEFAULT,
    threshold: float = DESPIKE_THRESHOLD_SIGMA,
) -> pl.DataFrame:
    """Hampel filter on ``value`` per group: replace isolated spikes with the
    rolling median.

    A point is a spike when it deviates from the centred rolling median by more
    than ``threshold`` robust sigmas (MAD × 1.4826) of its window. Only those
    points are touched, so steps and genuine transitions survive — unlike a
    plain median filter or Savgol smooth, which blur everything. Input/return
    frames carry ``timestamp, group, value`` (extra columns preserved).
    """
    if value_df.is_empty() or "value" not in value_df.columns:
        return value_df
    w = max(3, int(window))
    if w % 2 == 0:
        w += 1

    import numpy as np

    out = value_df.sort(["group", "timestamp"]) if "group" in value_df.columns else value_df.sort("timestamp")

    def _despike_group(df: pl.DataFrame) -> pl.DataFrame:
        y = df["value"].to_numpy().astype(float)
        n = y.size
        if n < w:
            return df
        med = (
            pl.Series(y)
            .rolling_median(window_size=w, min_samples=1, center=True)
            .to_numpy()
        )
        dev = np.abs(y - med)
        mad = (
            pl.Series(dev)
            .rolling_median(window_size=w, min_samples=1, center=True)
            .to_numpy()
        )
        sigma = MAD_TO_SIGMA * mad
        # A locally-constant window has sigma 0; soften with the trace-typical
        # sigma, and where the whole trace is constant treat any deviation from
        # the local median as a spike.
        floor = np.nanmedian(sigma[sigma > 0]) if np.any(sigma > 0) else 0.0
        sigma = np.where(sigma > 0, sigma, floor)
        with np.errstate(invalid="ignore"):
            spikes = np.where(sigma > 0, dev > threshold * sigma, dev > 0)
            spikes &= np.isfinite(dev)
        if not spikes.any():
            return df
        fixed = y.copy()
        fixed[spikes] = med[spikes]
        return df.with_columns(pl.Series("value", fixed).fill_nan(None))

    if "group" not in out.columns:
        return _despike_group(out)
    return out.group_by("group", maintain_order=True).map_groups(_despike_group)


def stablest_window(
    t_s,
    y,
    *,
    width_s: float,
    search_end_s: float | None = None,
    n_positions: int = 240,
    min_points: int = 8,
) -> tuple[float, float] | None:
    """The ``width_s``-wide window whose signal is flattest (lowest variance).

    A QCM baseline/reference window should be a quiet stretch before anything
    happens — buffer flowing, no adsorption — where Δf and ΔD are flat. Sliding a
    fixed-width window across the run and taking the minimum-variance position
    finds that stretch automatically. ``search_end_s`` caps how far in to look
    (baselines sit early, so the default search is the caller's choice); the
    result is a *suggestion* the user can accept or nudge, never silently applied.

    ``t_s`` / ``y`` are elapsed seconds and a frequency-like signal (e.g. absolute
    resonance frequency — its local variance measures stability independent of
    any baseline). Returns ``(start_s, end_s)`` or ``None`` when there is too
    little data.
    """
    import numpy as np

    t = np.asarray(t_s, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(t) & np.isfinite(y)
    t, y = t[mask], y[mask]
    if t.size < min_points or width_s <= 0:
        return None
    order = np.argsort(t)
    t, y = t[order], y[order]
    t0 = float(t[0])
    t_last = float(t[-1])
    end_limit = t_last if search_end_s is None else min(float(search_end_s), t_last)
    max_start = max(end_limit - width_s, t0)
    starts = np.linspace(t0, max_start, num=max(1, int(n_positions)))
    best: tuple[float, float] | None = None
    best_var: float | None = None
    for s in starts:
        e = s + width_s
        sel = (t >= s) & (t <= e)
        if int(sel.sum()) < min_points:
            continue
        var = float(np.var(y[sel]))
        if best_var is None or var < best_var:
            best_var, best = var, (float(s), float(e))
    return best


def alignment_lag(df: pl.DataFrame, *, max_lag_s: float = ALIGNMENT_MAX_LAG_S) -> dict | None:
    """Estimate the PS↔QCM time offset from Faraday's law.

    ``df`` carries ``[t_s, mass, current]`` on the QCM time base (the PS stream
    was interpolated onto it at import). For an electrodeposition experiment the
    areal-mass *rate* is proportional to −current, so the cross-correlation of
    the two peaks at zero lag when the streams are aligned; the argmax lag is
    the residual offset. Returns ``{"lag_s", "corr"}``; a positive ``lag_s``
    means the EC features arrive *later* than the QCM response, so re-importing
    with ``ps_offset_s = -lag_s`` realigns them. ``None`` when there is too
    little overlapping signal to say.
    """
    import numpy as np

    need = {"t_s", "mass", "current"}
    if df is None or df.is_empty() or not need.issubset(df.columns):
        return None
    d = df.select(sorted(need)).drop_nulls().sort("t_s")
    if d.height < 64:
        return None
    t = d["t_s"].to_numpy()
    dt = float(np.median(np.diff(t)))
    if not np.isfinite(dt) or dt <= 0:
        return None
    grid = np.arange(t[0], t[-1], dt)
    if grid.size < 64:
        return None
    mass = np.interp(grid, t, d["mass"].to_numpy())
    cur = np.interp(grid, t, d["current"].to_numpy())
    rate = np.gradient(mass, dt)
    x = rate - rate.mean()
    y = -(cur - cur.mean())
    sx, sy = x.std(), y.std()
    if sx == 0 or sy == 0:
        return None
    x /= sx
    y /= sy
    max_lag = max(1, int(round(max_lag_s / dt)))
    lags = np.arange(-max_lag, max_lag + 1)
    corr = np.array([
        np.dot(x[max(0, -k):x.size - max(0, k)], y[max(0, k):y.size - max(0, -k)])
        for k in lags
    ]) / grid.size
    best = int(np.argmax(corr))
    return {"lag_s": float(lags[best] * dt), "corr": float(corr[best])}


def faraday_prediction(
    wf: pl.DataFrame,
    quantity_key: str,
    *,
    params: ExperimentParams | None = None,
    baseline_us: tuple[int, int] | None = None,
) -> pl.DataFrame:
    """Faraday's-law prediction of the QCM response from the measured charge.

    100 % current efficiency into the target species deposits
    ``m(t) = −Q(t)·M / (z·F·A)`` g/cm²; via the Sauerbrey sensitivity that is a
    predicted ``Δf/n = −m/C``. Overlaying this on the measured trace is the
    notebook's "theoretical Zn" line, generalized: it follows the *measured*
    current programme (any technique), so deviations read directly as
    non-faradaic mass, side reactions, or viscoelastic error.

    ``wf`` carries ``[timestamp, charge]``; returns ``[timestamp, value]`` for
    ``quantity_key`` in ``("sauerbrey_mass", "delta_f_norm")``. When
    ``baseline_us`` is given the prediction is re-zeroed on that window, the
    same referencing convention as the measured Δ quantities.
    """
    p = params or DEFAULT_PARAMS
    if (
        wf is None or wf.is_empty()
        or not {"timestamp", "charge"}.issubset(wf.columns)
        or quantity_key not in ("sauerbrey_mass", "delta_f_norm")
        or p.area_cm2 <= 0 or p.valency <= 0 or p.sensitivity <= 0
    ):
        return pl.DataFrame()
    out = (
        wf.select(["timestamp", "charge"]).drop_nulls().sort("timestamp")
        .with_columns(
            (
                -pl.col("charge") * p.molar_mass
                / (p.valency * FARADAY_CONSTANT * p.area_cm2)
                / NG_PER_CM2_TO_G  # g/cm² → ng/cm²
            ).alias("value")
        )
    )
    if quantity_key == "delta_f_norm":
        out = out.with_columns((-pl.col("value") / p.sensitivity).alias("value"))
    if baseline_us is not None:
        b0, b1 = baseline_us
        base = out.filter(pl.col("timestamp").is_between(b0, b1))["value"]
        if base.len():
            out = out.with_columns(pl.col("value") - float(base.mean()))
    return out.select(["timestamp", "value"])


def sauerbrey_check(summary: pl.DataFrame) -> dict | None:
    """Judge whether Sauerbrey mass is trustworthy over the analysed region.

    Reads a :func:`region_overtone_summary` frame and reports the two standard
    sanity checks:

    - **overtone spread** — Δf/n should collapse across overtones for a rigid
      film; the spread is ``(max − min) / |mean|`` of the per-group means, in %;
    - **viscoelastic ratio** — mean ΔD/(−Δf/n); above ~0.4 ×10⁻⁶/Hz the film
      is soft and Sauerbrey underestimates the mass.

    Returns ``{"spread_pct", "ratio", "verdict", "detail"}`` with verdict one of
    ``"ok" | "caution" | "poor"``, or ``None`` when the region carries no usable
    Δf/n signal (e.g. an empty range or a pure-echem run).
    """
    if summary is None or summary.is_empty() or "df_n" not in summary.columns:
        return None
    df_n = summary["df_n"].drop_nulls()
    if df_n.len() == 0:
        return None
    mean_df = float(df_n.mean())
    if abs(mean_df) <= FREQ_EPS_HZ:
        return None

    spread_pct = None
    if df_n.len() >= 2:
        spread_pct = 100.0 * (float(df_n.max()) - float(df_n.min())) / abs(mean_df)

    ratio = None
    if "dD_per_df" in summary.columns:
        r = summary["dD_per_df"].drop_nulls()
        if r.len():
            ratio = abs(float(r.mean()))

    from .theme import SAUERBREY_RATIO_MAX, SAUERBREY_SPREAD_MAX_PCT

    soft = ratio is not None and ratio > SAUERBREY_RATIO_MAX
    scattered = spread_pct is not None and spread_pct > SAUERBREY_SPREAD_MAX_PCT
    if soft:
        verdict, detail = "poor", "viscoelastic film — Sauerbrey underestimates mass"
    elif scattered:
        verdict, detail = "caution", "overtones disagree — check n or film homogeneity"
    else:
        verdict, detail = "ok", "rigid-film assumptions hold"
    return {"spread_pct": spread_pct, "ratio": ratio, "verdict": verdict, "detail": detail}


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


def region_overtone_summary(
    frames: dict[str, pl.DataFrame],
    orders: dict[int, int],
) -> pl.DataFrame:
    """Compact per-channel summary of several quantities over one region.

    ``frames`` maps a short column name (e.g. ``"df_n"``, ``"dD"``, ``"mass"``,
    ``"Q"``) to a computed ``[group, value]`` frame. Returns one row per group
    with the mean of each quantity, the overtone order ``n``, and — when both
    ``df_n`` and ``dD`` are present — the viscoelastic ratio ``ΔD / (-Δf/n)``
    (a higher ratio indicates a softer, more dissipative film for which the
    rigid Sauerbrey assumption is weaker). All frames share the same group set,
    so a left join from the first non-empty frame is sufficient.
    """
    out: pl.DataFrame | None = None
    for name, df in frames.items():
        if df is None or df.is_empty():
            continue
        agg = df.group_by("group").agg(pl.col("value").mean().alias(name))
        out = agg if out is None else out.join(agg, on="group", how="left")
    if out is None or out.is_empty():
        return pl.DataFrame()

    out = out.with_columns(
        pl.col("group").replace_strict(orders, default=1, return_dtype=pl.Int64).alias("n")
    )
    if "df_n" in out.columns and "dD" in out.columns:
        out = out.with_columns(
            pl.when(pl.col("df_n").abs() > FREQ_EPS_HZ)
            .then(pl.col("dD") / (-pl.col("df_n")))
            .otherwise(None)
            .alias("dD_per_df")
        )
    return out.sort("group")
