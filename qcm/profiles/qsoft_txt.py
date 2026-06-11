"""Qsoft / Biolin raw .txt profile.

The Qsoft export is UTF-8, **tab-separated**, with a **decimal comma**, and a
single shared time column plus an ``f{n}_… (Hz)`` / ``D{n}_… (ppm)`` pair per
overtone order n:

    Time_1 (s)	f1_1 (Hz)	D1_1 (ppm)	f3_1 (Hz)	D3_1 (ppm)	...	f13_1 (Hz)	D13_1 (ppm)

``f{n}`` is the absolute resonant frequency (Hz) of overtone n and ``D{n}`` is the
dissipation in ppm — the same physical content as the standardized csv, just a
different on-disk shape. It maps to the canonical long-form QCM frame exactly like
:mod:`qcm.profiles.standardized_csv`: each overtone becomes a group, ``f{n}`` →
``fit_center``, and ``fit_fwhm = D_ppm * fit_center / 1e6``.
"""
from __future__ import annotations

import re
from pathlib import Path

import polars as pl

_F = re.compile(r"^f(\d+)_")
_D = re.compile(r"^D(\d+)_")
_TIME = re.compile(r"^Time", re.IGNORECASE)

_US = 1_000_000


def _overtones(columns: list[str]) -> list[int]:
    f = {int(m.group(1)) for c in columns if (m := _F.match(c.strip()))}
    d = {int(m.group(1)) for c in columns if (m := _D.match(c.strip()))}
    return sorted(f & d)


def is_qsoft_txt(path: str | Path) -> bool:
    """True when the file is tab-separated with ``f{n}_``/``D{n}_`` headers."""
    try:
        header = pl.read_csv(path, separator="\t", n_rows=0).columns
    except Exception:
        return False
    return bool(_overtones(header))


def read_qsoft_txt(path: str | Path) -> pl.DataFrame:
    """Read a Qsoft .txt into the canonical long-form QCM frame.

    Returns ``timestamp, sequence, group, fit_center, fit_fwhm, frequency``.
    """
    raw = pl.read_csv(path, separator="\t", decimal_comma=True, infer_schema_length=10_000)
    columns = raw.columns
    overtones = _overtones(columns)
    if not overtones:
        raise ValueError(f"No f{{n}}_/D{{n}}_ overtone columns found in {path}")
    fmap = {int(m.group(1)): c for c in columns if (m := _F.match(c.strip()))}
    dmap = {int(m.group(1)): c for c in columns if (m := _D.match(c.strip()))}
    time_cols = [c for c in columns if _TIME.match(c.strip())]
    if not time_cols:
        raise ValueError(f"No Time column found in {path}")
    time_col = time_cols[0]

    frames: list[pl.DataFrame] = []
    for n in overtones:
        fit_center = pl.col(fmap[n]).cast(pl.Float64)
        sub = (
            raw.select(
                (pl.col(time_col).cast(pl.Float64) * _US).round().cast(pl.Int64).alias("timestamp"),
                pl.int_range(0, pl.len(), dtype=pl.Int64).alias("sequence"),
                pl.lit(n, dtype=pl.Int64).alias("group"),
                fit_center.alias("fit_center"),
                (pl.col(dmap[n]).cast(pl.Float64) * fit_center / _US).alias("fit_fwhm"),
                fit_center.alias("frequency"),
            )
            .drop_nulls(subset=["timestamp", "fit_center"])
        )
        frames.append(sub)

    return pl.concat(frames, how="vertical").sort(["timestamp", "group"])


from .base import FunctionProfile  # noqa: E402

PROFILE = FunctionProfile(
    "qsoft_txt", "qcm", is_qsoft_txt,
    lambda path, rename=None: read_qsoft_txt(path),
)
