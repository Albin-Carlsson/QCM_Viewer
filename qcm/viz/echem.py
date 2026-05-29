"""Pure electrochemistry analysis for the EQCM viewer.

Side-effect-free Polars/Python helpers that turn the cell-level electrochemistry
columns (``potential``, ``current``, ``charge``, ``cycle``, ``cycle_time``) into:

- a technique guess (cyclic voltammetry vs chronopotentiometry),
- technique-specific metadata (CV: E start / vertices / scan rate / scans;
  CP: applied current / current density / step durations),
- cycle selection, and
- a per-cycle statistics summary.

No Panel imports, so everything here is unit-testable plain Python. ``current``
is in amperes, ``potential`` in volts, ``charge`` in coulombs, timestamps in
microseconds.
"""
from __future__ import annotations

import polars as pl

from .theme import ELECTRODE_AREA_CM2

_US = 1_000_000

# Columns the electrochemistry views rely on.
ECHEM_COLUMNS = ("potential", "current", "charge", "cycle", "cycle_time")


def has_echem(columns) -> bool:
    """True when a run carries the electrochemistry channel."""
    cols = set(columns)
    return {"potential", "current"}.issubset(cols)


def waveform(df: pl.DataFrame) -> pl.DataFrame:
    """One row per sweep (timestamp) with the cell-level signals + ``time_s``.

    The electrochemistry columns are identical across overtones and repeated
    across the frequency points of a sweep, so collapse to one row per timestamp
    to recover the underlying waveform. ``time_s`` is elapsed seconds from the
    first sample.
    """
    cols = [c for c in ECHEM_COLUMNS if c in df.columns]
    if df.is_empty() or "timestamp" not in df.columns or not cols:
        return pl.DataFrame()
    wf = (
        df.select(["timestamp", *cols])
        .unique(subset=["timestamp"], keep="first")
        .sort("timestamp")
    )
    t0 = wf["timestamp"].min()
    return wf.with_columns(((pl.col("timestamp") - t0) / _US).alias("time_s"))


def detect_technique(df: pl.DataFrame) -> str:
    """Guess the technique from the current waveform.

    Galvanostatic CP holds ``|current|`` nearly constant (low coefficient of
    variation), while a CV sweep produces a strongly varying, sign-changing
    current. Returns ``"cp"`` when the applied current looks held constant,
    otherwise ``"cv"``. Defaults to ``"cv"`` when there is too little data.
    """
    wf = waveform(df) if "time_s" not in df.columns else df
    if wf.is_empty() or "current" not in wf.columns or wf.height < 8:
        return "cv"
    abs_i = wf["current"].abs().drop_nulls()
    mean_abs = float(abs_i.mean() or 0.0)
    if mean_abs <= 0:
        return "cv"
    cov = float(abs_i.std() or 0.0) / mean_abs
    return "cp" if cov < 0.5 else "cv"


def _scan_rate_v_per_s(wf: pl.DataFrame) -> float:
    """Median |dV/dt| over the sweep, ignoring the near-zero turning points."""
    if wf.height < 2:
        return 0.0
    rates = (
        wf.select(
            (pl.col("potential").diff() / (pl.col("time_s").diff()))
            .abs()
            .alias("rate")
        )
        .drop_nulls()
        .filter(pl.col("rate") > 1e-9)
    )
    if rates.is_empty():
        return 0.0
    return float(rates["rate"].median() or 0.0)


def cv_metadata(df: pl.DataFrame) -> dict[str, float | int]:
    """Cyclic-voltammetry metadata: E start, vertices, scan rate, scan count."""
    wf = waveform(df) if "time_s" not in df.columns else df
    if wf.is_empty() or "potential" not in wf.columns:
        return {}
    pot = wf["potential"]
    n_scans = int(wf["cycle"].n_unique()) if "cycle" in wf.columns else 0
    return {
        "e_start": float(pot[0]),
        "e_vertex1": float(pot.max()),
        "e_vertex2": float(pot.min()),
        "scan_rate": _scan_rate_v_per_s(wf),
        "n_scans": n_scans,
    }


def _step_durations_s(wf: pl.DataFrame) -> list[float]:
    """Durations (s) of constant-current steps, split at current sign changes."""
    if wf.height < 2 or "current" not in wf.columns:
        return []
    signed = wf.with_columns(pl.col("current").sign().alias("_sgn"))
    # A new step starts where the sign changes from the previous sample.
    signed = signed.with_columns(
        (pl.col("_sgn") != pl.col("_sgn").shift(1)).fill_null(True).alias("_new_step")
    ).with_columns(pl.col("_new_step").cum_sum().alias("_step"))
    per_step = signed.group_by("_step").agg(
        (pl.col("time_s").max() - pl.col("time_s").min()).alias("dur")
    )
    return [float(d) for d in per_step["dur"].drop_nulls().to_list() if d > 0]


def cp_metadata(df: pl.DataFrame) -> dict[str, float]:
    """Chronopotentiometry metadata: applied current/density, step durations."""
    wf = waveform(df) if "time_s" not in df.columns else df
    if wf.is_empty() or "current" not in wf.columns:
        return {}
    applied = float(wf["current"].abs().median() or 0.0)
    durations = _step_durations_s(wf)
    median_step = sorted(durations)[len(durations) // 2] if durations else 0.0
    return {
        "applied_current": applied,
        "applied_current_density": applied / ELECTRODE_AREA_CM2,
        "step_duration": float(median_step),
        "n_steps": float(len(durations)),
    }


def metadata(df: pl.DataFrame, technique: str) -> dict:
    return cp_metadata(df) if technique == "cp" else cv_metadata(df)


def cycle_values(df: pl.DataFrame) -> list[int]:
    """Sorted distinct cycle indices present in the data."""
    if df.is_empty() or "cycle" not in df.columns:
        return []
    return sorted(int(c) for c in df["cycle"].unique().drop_nulls().to_list())


def filter_cycles(
    df: pl.DataFrame,
    mode: str,
    *,
    cycle: int | None = None,
    lo: int | None = None,
    hi: int | None = None,
) -> pl.DataFrame:
    """Restrict rows to the selected cycle(s).

    ``mode`` is ``"all"`` (no filtering), ``"individual"`` (just ``cycle``), or
    ``"range"`` (``lo``..``hi`` inclusive). Unknown modes or a missing cycle
    column return the frame unchanged.
    """
    if df.is_empty() or "cycle" not in df.columns or mode == "all":
        return df
    if mode == "individual" and cycle is not None:
        return df.filter(pl.col("cycle") == int(cycle))
    if mode == "range" and lo is not None and hi is not None:
        a, b = sorted((int(lo), int(hi)))
        return df.filter((pl.col("cycle") >= a) & (pl.col("cycle") <= b))
    return df


def cycle_stats(df: pl.DataFrame, technique: str = "cv") -> pl.DataFrame:
    """Per-cycle summary table for the selected cycles.

    Reports duration, potential window, current extremes, and charge passed per
    cycle. For CV the current extremes are the anodic (max) and cathodic (min)
    peak currents; for CP the potential window is the working range.
    """
    wf = waveform(df) if "time_s" not in df.columns else df
    if wf.is_empty() or "cycle" not in wf.columns:
        return pl.DataFrame()
    agg = [
        pl.len().alias("samples"),
        (pl.col("time_s").max() - pl.col("time_s").min()).alias("duration_s"),
        pl.col("potential").min().alias("E_min_V"),
        pl.col("potential").max().alias("E_max_V"),
        pl.col("current").max().alias("I_anodic_A"),
        pl.col("current").min().alias("I_cathodic_A"),
    ]
    if "charge" in wf.columns:
        agg.append((pl.col("charge").max() - pl.col("charge").min()).alias("charge_C"))
    return (
        wf.group_by("cycle")
        .agg(agg)
        .with_columns(pl.col("cycle").cast(pl.Int64))
        .sort("cycle")
    )
