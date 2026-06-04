"""PSTrace potentiostat CSV profile (chronopotentiometry / galvanostatic).

PSTrace exports are UTF-16 with a multi-line preamble. The real column header
sits a few lines down and, for a galvanostatic run, carries three independent
time/value pairs:

    s, µC, s, µA, s, V

i.e. charge (µC), current (µA), and potential (V), each paired with its own time
column (all three time columns are identical). This profile parses that into a
tidy frame ``[time_s, potential, current, charge]`` with charge in coulombs and
current in amperes (matching :mod:`qcm.viz.echem`), then :func:`attach_echem`
interpolates those signals onto a QCM run's timestamps.
"""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import polars as pl

# Unit token -> (canonical role, scale to SI). µ may arrive as 'µ' (U+00B5),
# 'μ' (U+03BC), or an ASCII 'u' depending on the export.
_UNIT_ROLE = {
    "µC": ("charge", 1e-6), "μC": ("charge", 1e-6), "uC": ("charge", 1e-6), "C": ("charge", 1.0),
    "µA": ("current", 1e-6), "μA": ("current", 1e-6), "uA": ("current", 1e-6), "A": ("current", 1.0),
    "V": ("potential", 1.0),
}
_TIME = "s"


def _decode(path: str | Path) -> str:
    """Decode a PSTrace file, honoring a UTF-16 BOM and falling back to UTF-8."""
    data = Path(path).read_bytes()
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-16", errors="replace")


def _find_header(lines: list[str]) -> tuple[int, dict[str, tuple[int, int]]]:
    """Return (header row index, {role: (time_col, value_col)}).

    Scans for the first row that pairs a time column ``s`` with at least one
    recognized value unit. Each value column binds to the most recent ``s``.
    """
    for idx, line in enumerate(lines):
        cells = [c.strip().lstrip("﻿") for c in line.split(",")]
        if _TIME not in cells:
            continue
        roles: dict[str, tuple[int, int]] = {}
        last_time: int | None = None
        for i, cell in enumerate(cells):
            if cell == _TIME:
                last_time = i
            elif cell in _UNIT_ROLE and last_time is not None:
                role, _scale = _UNIT_ROLE[cell]
                roles.setdefault(role, (last_time, i))
        if roles:
            return idx, roles
    raise ValueError("No PSTrace data header (s + µC/µA/V) found")


def is_pstrace_csv(path: str | Path) -> bool:
    """True when the file looks like a PSTrace export with a time/value header."""
    try:
        text = _decode(path)
        _find_header(text.splitlines()[:40])
        return True
    except Exception:
        return False


def read_pstrace_csv(path: str | Path) -> pl.DataFrame:
    """Read a PSTrace CP export into ``[time_s, potential, current, charge]``.

    Charge is returned in coulombs and current in amperes; potential in volts.
    """
    text = _decode(path)
    lines = text.splitlines()
    header_idx, roles = _find_header(lines)
    header_cells = [c.strip().lstrip("﻿") for c in lines[header_idx].split(",")]

    body = "\n".join(lines[header_idx + 1:])
    # Read every column as text (infer_schema_length=0) and cast below with
    # strict=False. PSTrace bodies can carry ragged rows or trailing non-numeric
    # blocks that would otherwise abort type inference; those become nulls and
    # are dropped.
    raw = pl.read_csv(
        io.StringIO(body), has_header=False, infer_schema_length=0,
        truncate_ragged_lines=True,
    )

    time_col, _ = next(iter(roles.values()))  # all time columns are identical
    out = {"time_s": pl.col(raw.columns[time_col]).cast(pl.Float64, strict=False)}
    for role in ("potential", "current", "charge"):
        if role not in roles:
            continue
        _t, vcol = roles[role]
        _r, scale = _UNIT_ROLE[header_cells[vcol]]
        out[role] = pl.col(raw.columns[vcol]).cast(pl.Float64, strict=False) * scale

    return raw.select(**out).drop_nulls(subset=["time_s"]).sort("time_s")


def attach_echem(qcm_frame: pl.DataFrame, ps: pl.DataFrame, offset_s: float = 0.0) -> pl.DataFrame:
    """Interpolate PS signals onto a QCM run's timestamps and join them in.

    Both streams are zeroed at their first sample; ``offset_s`` then shifts the
    PS stream before interpolation (positive = PS later). Each unique QCM
    timestamp gets potential/current/charge by linear interpolation (clamped at
    the ends, like ``numpy.interp``), broadcast across all overtone groups.
    """
    if qcm_frame.is_empty() or ps.is_empty():
        return qcm_frame

    ts = qcm_frame.select("timestamp").unique().sort("timestamp")["timestamp"]
    ts_us = ts.to_numpy()
    q_elapsed = (ts_us - ts_us.min()) / 1_000_000.0

    ps = ps.sort("time_s")
    ps_t = ps["time_s"].to_numpy()
    ps_elapsed = ps_t - ps_t.min() + float(offset_s)

    echem = {"timestamp": ts}
    for role in ("potential", "current", "charge"):
        if role in ps.columns:
            echem[role] = pl.Series(role, np.interp(q_elapsed, ps_elapsed, ps[role].to_numpy()))
    echem_df = pl.DataFrame(echem)

    return qcm_frame.join(echem_df, on="timestamp", how="left")
