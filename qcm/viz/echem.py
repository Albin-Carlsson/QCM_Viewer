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

from .theme import ELECTRODE_AREA_CM2, FARADAY_CONSTANT

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


def derive_cycles(wf: pl.DataFrame) -> pl.DataFrame:
    """Add current-sign half-cycles and a derived ``cycle`` column to a waveform.

    Plating is the negative-current segment, stripping the positive-current one;
    a full cycle is a plating+stripping pair. Cycle numbering increments at each
    plating-half start, so data that begins mid-cycle (e.g. on a stripping half)
    is folded into cycle 1 rather than corrupting the table. Adds:

    - ``_half``: contiguous same-sign segment id,
    - ``_is_plate``: True on plating (negative-current) rows,
    - ``cycle``: 1-based full-cycle index.

    Returns the frame unchanged when there is no current channel.
    """
    if wf.is_empty() or "current" not in wf.columns:
        return wf
    order = "time_s" if "time_s" in wf.columns else "timestamp"
    w = wf.sort(order)
    w = w.with_columns(
        pl.col("current").sign()
        .replace(0, None).fill_null(strategy="forward").fill_null(strategy="backward")
        .alias("_sgn")
    )
    w = w.with_columns(
        (pl.col("_sgn") != pl.col("_sgn").shift(1)).fill_null(True).alias("_newhalf"),
        (pl.col("_sgn") < 0).alias("_is_plate"),
    )
    w = w.with_columns(pl.col("_newhalf").cum_sum().alias("_half"))
    # A new cycle starts at the beginning of each plating half; leading rows
    # before the first plating half belong to cycle 1.
    w = w.with_columns((pl.col("_newhalf") & pl.col("_is_plate")).cum_sum().alias("_cyc"))
    w = w.with_columns(
        pl.when(pl.col("_cyc") < 1).then(1).otherwise(pl.col("_cyc")).cast(pl.Int64).alias("cycle")
    )
    return w.drop(["_sgn", "_newhalf", "_cyc"])


def _cp_cycle_ce(wf: pl.DataFrame) -> pl.DataFrame:
    """Per-cycle coulombic efficiency from plating/stripping half-cycles.

    Expects the ``_half``/``_is_plate``/``cycle`` markers from
    :func:`derive_cycles`. Returns one row per cycle with plating/stripping
    durations and charges, time-based CE (t_strip / t_plate), and charge-based
    CE (|Q_strip / Q_plate|). Charge passed per half is ``|Δcharge|`` over that
    half (charge is the cumulative cell charge).
    """
    half_aggs = [
        pl.col("_is_plate").first().alias("is_plate"),
        (pl.col("time_s").max() - pl.col("time_s").min()).alias("dur"),
    ]
    if "charge" in wf.columns:
        half_aggs.append(
            (pl.col("charge").sort_by("time_s").last() - pl.col("charge").sort_by("time_s").first())
            .abs().alias("q")
        )
    halves = wf.group_by(["cycle", "_half"]).agg(half_aggs)

    cyc_aggs = [
        pl.col("dur").filter(pl.col("is_plate")).sum().alias("t_plate_s"),
        pl.col("dur").filter(~pl.col("is_plate")).sum().alias("t_strip_s"),
    ]
    if "q" in halves.columns:
        cyc_aggs += [
            pl.col("q").filter(pl.col("is_plate")).sum().alias("Q_plate_C"),
            pl.col("q").filter(~pl.col("is_plate")).sum().alias("Q_strip_C"),
        ]
    per = halves.group_by("cycle").agg(cyc_aggs).with_columns(
        pl.when(pl.col("t_plate_s") > 0)
        .then(pl.col("t_strip_s") / pl.col("t_plate_s"))
        .otherwise(None).alias("CE_time"),
    )
    if "Q_plate_C" in per.columns:
        per = per.with_columns(
            pl.when(pl.col("Q_plate_C").abs() > 1e-15)
            .then((pl.col("Q_strip_C") / pl.col("Q_plate_C")).abs())
            .otherwise(None).alias("CE_charge"),
        )
    return per.sort("cycle")


def half_cycle_mpe(joined: pl.DataFrame, area: float = ELECTRODE_AREA_CM2) -> pl.DataFrame:
    """Static plating/stripping MPE per cycle = ``F · Δm(g) / Δq`` over each half.

    ``joined`` carries one row per timestamp with ``cycle``, ``_is_plate`` (from
    :func:`derive_cycles`), the cumulative ``charge`` (C), and ``_mass`` (areal
    Sauerbrey mass in ng/cm²). Δm and Δq are endpoint differences over each half;
    ``area`` converts areal mass to total grams. Returns ``[cycle,
    MPE_plating_g_per_mol, MPE_stripping_g_per_mol]``. Sign follows the cumulative
    charge convention, matching the app's other MPE figures.
    """
    if joined.is_empty() or "_is_plate" not in joined.columns:
        return pl.DataFrame(schema={"cycle": pl.Int64})
    dm = (pl.col("_mass").sort_by("timestamp").last()
          - pl.col("_mass").sort_by("timestamp").first()).alias("_dm_ng")
    dq = (pl.col("charge").sort_by("timestamp").last()
          - pl.col("charge").sort_by("timestamp").first()).alias("_dq")
    mpe = (
        pl.when(pl.col("_dq").abs() > 1e-15)
        .then(-FARADAY_CONSTANT * (pl.col("_dm_ng") * area * 1e-9) / pl.col("_dq"))
        .otherwise(None).round(2)
    )
    half = joined.group_by(["cycle", "_is_plate"]).agg([dm, dq]).with_columns(mpe.alias("_mpe"))
    plating = half.filter(pl.col("_is_plate")).select(
        ["cycle", pl.col("_mpe").alias("MPE_plating_g_per_mol")])
    stripping = half.filter(~pl.col("_is_plate")).select(
        ["cycle", pl.col("_mpe").alias("MPE_stripping_g_per_mol")])
    return plating.join(stripping, on="cycle", how="full", coalesce=True).sort("cycle")


def cycle_relative(df: pl.DataFrame, *, zero: bool = False) -> pl.DataFrame:
    """Re-reference rows to each cycle's own start for overlay comparison.

    ``df`` carries ``timestamp``, ``cycle``, and ``value``. Adds ``t_rel_s`` =
    seconds since the cycle's first sample (so every cycle starts at 0). When
    ``zero`` is set, ``value`` is also shifted to start at 0 within each cycle —
    used for frequency/dissipation, never for an absolute signal like potential.
    """
    if df.is_empty() or "cycle" not in df.columns or "timestamp" not in df.columns:
        return df
    out = df.sort(["cycle", "timestamp"]).with_columns(
        ((pl.col("timestamp") - pl.col("timestamp").min().over("cycle")) / 1_000_000).alias("t_rel_s")
    )
    if zero and "value" in out.columns:
        out = out.with_columns((pl.col("value") - pl.col("value").first().over("cycle")).alias("value"))
    return out


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


# Human-readable column titles for the per-cycle table (the raw frame keeps
# machine names so keys/sorting stay stable; these are display-only).
CYCLE_COLUMN_TITLES: dict[str, str] = {
    "cycle": "Cycle",
    "samples": "Samples",
    "duration_s": "Duration (s)",
    "E_min_V": "E min (V)",
    "E_max_V": "E max (V)",
    "I_anodic_A": "I anodic (A)",
    "I_cathodic_A": "I cathodic (A)",
    "charge_C": "Charge (C)",
    "MPE_g_per_mol": "MPE (g/mol)",
    "step_duration": "Step duration (s)",
    "n_steps": "Steps",
    "t_plate_s": "Plating time (s)",
    "t_strip_s": "Stripping time (s)",
    "Q_plate_C": "Plating charge (C)",
    "Q_strip_C": "Stripping charge (C)",
    "CE_time": "CE (time)",
    "CE_charge": "CE (charge)",
    "mass_accum_ng_cm2": "Mass accumulation (ng/cm²)",
    "MPE_plating_g_per_mol": "MPE plating (g/mol)",
    "MPE_stripping_g_per_mol": "MPE stripping (g/mol)",
}


def pretty_column_titles(columns) -> dict[str, str]:
    """Map raw cycle-table column names to display titles for ``Tabulator(titles=...)``.

    Unknown columns fall back to a sensible ``snake_case`` → ``Title case``.
    """
    out: dict[str, str] = {}
    for c in columns:
        out[c] = CYCLE_COLUMN_TITLES.get(c) or c.replace("_", " ").strip().capitalize()
    return out


def cycle_stats(df: pl.DataFrame, technique: str = "cv") -> pl.DataFrame:
    """Per-cycle summary table for the selected cycles.

    Reports duration, potential window, current extremes, and charge passed per
    cycle. For CV the current extremes are the anodic (max) and cathodic (min)
    peak currents; for CP the potential window is the working range.
    """
    wf = waveform(df) if "time_s" not in df.columns else df
    if wf.is_empty():
        return pl.DataFrame()
    # CP cycles are derived from the current sign (the instrument cycle column, if
    # any, is overridden); CV uses the cycle column as recorded.
    if technique == "cp" and "current" in wf.columns:
        wf = derive_cycles(wf)
    if "cycle" not in wf.columns:
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
    base = (
        wf.group_by("cycle")
        .agg(agg)
        .with_columns(pl.col("cycle").cast(pl.Int64))
        .sort("cycle")
    )
    if technique == "cp" and "_half" in wf.columns:
        base = base.join(_cp_cycle_ce(wf), on="cycle", how="left").sort("cycle")
    return base
