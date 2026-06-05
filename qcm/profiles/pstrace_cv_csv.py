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


def attach_cv_echem(qcm_frame: pl.DataFrame, cv: pl.DataFrame) -> pl.DataFrame:
    """Place a potential-indexed CV dataset onto a QCM run's timestamps.

    A CV export has no time axis, so the scans are laid out in acquisition order
    (scan ascending, samples in file order) and spread evenly across the QCM
    run's elapsed span. ``potential``/``current`` are linearly interpolated onto
    each QCM timestamp; ``cycle`` is taken as a step function (nearest preceding
    sample) so scan boundaries stay crisp. Signals are broadcast across overtone
    groups by the timestamp join.
    """
    if qcm_frame.is_empty() or cv.is_empty():
        return qcm_frame

    ts = qcm_frame.select("timestamp").unique().sort("timestamp")["timestamp"]
    ts_us = ts.to_numpy()
    q_elapsed = (ts_us - ts_us.min()) / 1_000_000.0
    span = float(q_elapsed.max()) or 1.0

    n = cv.height
    t_cv = np.linspace(0.0, span, n)
    pot = cv["potential"].to_numpy()
    cur = cv["current"].to_numpy()
    cyc = cv["cycle"].to_numpy()
    # Step-assign the cycle (an integer label can't be linearly interpolated).
    idx = np.clip(np.searchsorted(t_cv, q_elapsed, side="right") - 1, 0, n - 1)

    echem_df = pl.DataFrame({
        "timestamp": ts,
        "potential": pl.Series("potential", np.interp(q_elapsed, t_cv, pot)),
        "current": pl.Series("current", np.interp(q_elapsed, t_cv, cur)),
        "cycle": pl.Series("cycle", cyc[idx]),
    })
    return qcm_frame.join(echem_df, on="timestamp", how="left")
