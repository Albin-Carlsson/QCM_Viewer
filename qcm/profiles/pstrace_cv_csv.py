"""PSTrace potentiostat CSV profile (cyclic voltammetry).

Unlike the time-indexed CP export (``s, µC, s, µA, s, V``), a CV PSTrace export
is *potential/scan-indexed*: the columns are grouped by curve type and scan, and
the voltammogram lives in the ``CV i vs E Scan N`` group — a ``(V, µA)`` pair per
scan (potential, current), with no time column. This profile maps the ``i vs E``
group into a tidy long frame ``[cycle, potential, current]`` (current in amperes,
potential in volts), one row per (scan, sample). :func:`attach_cv_echem` then
places those scans onto a QCM run's timestamps so the voltammogram views
populate.
"""
from __future__ import annotations

import io
import re
from pathlib import Path

import numpy as np
import polars as pl

from .pstrace_csv import _decode

# Current unit token -> scale to amperes. µ may be U+00B5, U+03BC, or ASCII 'u'.
_CURRENT_UNITS = {"µA": 1e-6, "μA": 1e-6, "uA": 1e-6, "mA": 1e-3, "A": 1.0}
_IVSE = "i vs E"
_SCAN_RE = re.compile(r"Scan\s+(\d+)")


def _find_cv_header(lines: list[str]) -> tuple[int, int, list[tuple[int, int, int, float]]]:
    """Return ``(header_idx, units_idx, pairs)`` for the ``i vs E`` group.

    ``pairs`` is ``[(scan, potential_col, current_col, current_scale), …]``. The
    units row is the first row after the labels that carries a current token (a
    metadata row may sit between the labels and the units).
    """
    for idx, line in enumerate(lines):
        if _IVSE not in line:
            continue
        labels = [c.strip() for c in line.split(",")]
        for u_idx in range(idx + 1, min(idx + 6, len(lines))):
            units = [c.strip() for c in lines[u_idx].split(",")]
            if not any(u in _CURRENT_UNITS for u in units):
                continue
            pairs: list[tuple[int, int, int, float]] = []
            for c, lab in enumerate(labels):
                if _IVSE in lab and c + 1 < len(units) and units[c + 1] in _CURRENT_UNITS:
                    m = _SCAN_RE.search(lab)
                    scan = int(m.group(1)) if m else len(pairs) + 1
                    pairs.append((scan, c, c + 1, _CURRENT_UNITS[units[c + 1]]))
            if pairs:
                return idx, u_idx, pairs
    raise ValueError("No CV PSTrace 'i vs E' header found")


def is_cv_pstrace_csv(path: str | Path) -> bool:
    """True when the file is a CV PSTrace export (per-scan ``i vs E`` blocks)."""
    try:
        _find_cv_header(_decode(path).splitlines()[:40])
        return True
    except Exception:
        return False


def read_cv_pstrace_csv(path: str | Path) -> pl.DataFrame:
    """Read a CV PSTrace export into long-form ``[cycle, potential, current]``.

    ``cycle`` is the scan number, ``potential`` in volts, ``current`` in amperes.
    """
    lines = _decode(path).splitlines()
    _hdr, u_idx, pairs = _find_cv_header(lines)
    body = "\n".join(lines[u_idx + 1:])
    raw = pl.read_csv(
        io.StringIO(body), has_header=False, infer_schema_length=0,
        truncate_ragged_lines=True,
    )
    frames: list[pl.DataFrame] = []
    for scan, vcol, icol, scale in pairs:
        if vcol >= raw.width or icol >= raw.width:
            continue
        sub = raw.select(
            pl.lit(scan, dtype=pl.Int64).alias("cycle"),
            pl.col(raw.columns[vcol]).cast(pl.Float64, strict=False).alias("potential"),
            (pl.col(raw.columns[icol]).cast(pl.Float64, strict=False) * scale).alias("current"),
        ).drop_nulls(["potential", "current"])
        if not sub.is_empty():
            frames.append(sub)
    if not frames:
        return pl.DataFrame()
    return pl.concat(frames, how="vertical")


_SCANRATE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*mVs", re.IGNORECASE)
_DEFAULT_SCAN_RATE = 0.025  # V/s — PSTrace's common default when none is known


def scan_rate_from_filename(path: str | Path) -> float | None:
    """Scan rate (V/s) parsed from a ``…25mVs…`` filename, else ``None``."""
    m = _SCANRATE_RE.search(Path(path).name)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ".")) / 1000.0
    except ValueError:
        return None


def attach_cv_echem(
    qcm_frame: pl.DataFrame, cv: pl.DataFrame, *, scan_rate: float | None = None,
) -> pl.DataFrame:
    """Place a potential-indexed CV dataset onto a QCM run's timestamps.

    A CV export has no time axis, so a time base is reconstructed from the scan
    rate: within each scan the time advances by ``dt = |ΔV| / scan_rate`` per
    sample (a constant-rate sweep), and scans are stitched sequentially from
    ``t=0``. ``potential``/``current`` are linearly interpolated onto each QCM
    timestamp and ``cycle`` is step-assigned from the real scan boundaries; QCM
    samples beyond the CV's reconstructed span get no echem (null) rather than a
    held value. ``scan_rate`` defaults to 0.025 V/s when unknown.
    """
    if qcm_frame.is_empty() or cv.is_empty():
        return qcm_frame
    rate = float(scan_rate) if scan_rate else _DEFAULT_SCAN_RATE

    # Per-sample dt from |ΔV|/rate (first sample of each scan = 0 so scans abut),
    # cumulated over the file order to give the stitched time base.
    cv = cv.with_columns(
        (pl.col("potential").diff().over("cycle").abs().fill_null(0.0) / rate).alias("_dt")
    ).with_columns(pl.col("_dt").cum_sum().alias("_t"))
    t_cv = cv["_t"].to_numpy()
    pot = cv["potential"].to_numpy()
    cur = cv["current"].to_numpy()
    cyc = cv["cycle"].to_numpy()
    t_end = float(t_cv[-1]) if len(t_cv) else 0.0

    ts = qcm_frame.select("timestamp").unique().sort("timestamp")["timestamp"]
    ts_us = ts.to_numpy()
    q = (ts_us - ts_us.min()) / 1_000_000.0
    inside = q <= t_end + 1e-9
    idx = np.clip(np.searchsorted(t_cv, q, side="right") - 1, 0, max(len(t_cv) - 1, 0))

    def _masked(values):
        return pl.Series(np.where(inside, values, np.nan))

    # NaN marks the out-of-span tail; convert to real nulls so downstream
    # drop_nulls / cycle_stats ignore it (NaN would survive a drop_nulls).
    echem_df = pl.DataFrame({
        "timestamp": ts,
        "potential": _masked(np.interp(q, t_cv, pot)),
        "current": _masked(np.interp(q, t_cv, cur)),
        "cycle": _masked(cyc[idx].astype(float)),
    }).with_columns(
        pl.col("potential").fill_nan(None),
        pl.col("current").fill_nan(None),
        pl.col("cycle").fill_nan(None).cast(pl.Int64, strict=False),
    )
    return qcm_frame.join(echem_df, on="timestamp", how="left")
