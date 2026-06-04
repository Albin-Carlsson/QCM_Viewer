"""Standardized QCM CSV profile.

The standardized export is one comma-separated, decimal-point row per time sample
with a ``Time_N, Fr_N, D_N`` triple per overtone order N:

    Time_1, Fr_1, D_1, Time_3, Fr_3, D_3, ... Time_13, Fr_13, D_13

``Fr_N`` is the absolute resonant frequency (Hz) of overtone N and ``D_N`` is the
dissipation in ppm. This maps to the canonical long-form QCM frame: each overtone
becomes a group, ``Fr_N`` becomes ``fit_center``, and the linewidth is recovered
from dissipation as ``fit_fwhm = D_ppm * fit_center / 1e6`` so the existing
dissipation/quality-factor math is unchanged.
"""
from __future__ import annotations

import re
from pathlib import Path

import polars as pl

_FR = re.compile(r"^Fr_(\d+)$")
_D = re.compile(r"^D_(\d+)$")
_TIME = re.compile(r"^Time_(\d+)$")

_US = 1_000_000


def _overtones(columns: list[str]) -> list[int]:
    """Overtone orders that have both a frequency and a dissipation column."""
    fr = {int(m.group(1)) for c in columns if (m := _FR.match(c))}
    d = {int(m.group(1)) for c in columns if (m := _D.match(c))}
    return sorted(fr & d)


def is_standardized_csv(path: str | Path) -> bool:
    """True when the file's header carries at least one ``Fr_N``/``D_N`` pair."""
    try:
        header = pl.read_csv(path, n_rows=0).columns
    except Exception:
        return False
    return bool(_overtones(header))


def read_standardized_csv(path: str | Path) -> pl.DataFrame:
    """Read a standardized QCM csv into the canonical long-form QCM frame.

    Returns columns ``timestamp, sequence, group, fit_center, fit_fwhm,
    frequency``. Raises ``ValueError`` when no ``Fr_N``/``D_N`` pairs are found.
    """
    raw = pl.read_csv(path, infer_schema_length=10_000)
    columns = raw.columns
    overtones = _overtones(columns)
    if not overtones:
        raise ValueError(f"No Fr_N/D_N overtone columns found in {path}")

    has_time = {int(m.group(1)) for c in columns if (m := _TIME.match(c))}
    # A shared fallback time column when an overtone lacks its own Time_N.
    fallback_time = f"Time_{sorted(has_time)[0]}" if has_time else None

    frames: list[pl.DataFrame] = []
    for n in overtones:
        time_col = f"Time_{n}" if n in has_time else fallback_time
        if time_col is None:
            raise ValueError(f"No Time column available for overtone {n} in {path}")
        fit_center = pl.col(f"Fr_{n}").cast(pl.Float64)
        sub = (
            raw.select(
                (pl.col(time_col).cast(pl.Float64) * _US).round().cast(pl.Int64).alias("timestamp"),
                pl.int_range(0, pl.len(), dtype=pl.Int64).alias("sequence"),
                pl.lit(n, dtype=pl.Int64).alias("group"),
                fit_center.alias("fit_center"),
                (pl.col(f"D_{n}").cast(pl.Float64) * fit_center / _US).alias("fit_fwhm"),
                fit_center.alias("frequency"),
            )
            .drop_nulls(subset=["timestamp", "fit_center"])
        )
        frames.append(sub)

    return pl.concat(frames, how="vertical").sort(["timestamp", "group"])
