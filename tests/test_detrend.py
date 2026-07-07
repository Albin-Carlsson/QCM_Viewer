"""Baseline drift correction (science.detrend)."""
from __future__ import annotations

import numpy as np
import polars as pl

from qcm.viz import science

_US = 1_000_000


def _frame(t_s, value, group=0):
    return pl.DataFrame({
        "timestamp": (np.asarray(t_s) * _US).astype(np.int64),
        "group": np.full(len(t_s), group, dtype=np.int64),
        "value": np.asarray(value, dtype=float),
    })


def test_linear_drift_removed_across_whole_run():
    # Reference window 0–100 s carries a pure linear drift of 2 Hz/s.
    t_ref = np.arange(0, 100, 1.0)
    ref = _frame(t_ref, 2.0 * t_ref)
    # The full run continues the same drift plus a real step of +50 after 200 s.
    t = np.arange(0, 400, 1.0)
    signal = 2.0 * t + np.where(t >= 200, 50.0, 0.0)
    full = _frame(t, signal)

    out = science.detrend(full, ref, t0_us=0, order=1).sort("timestamp")
    y = out["value"].to_numpy()
    # The drift is gone: the pre-step region sits at ~0…
    assert abs(float(np.mean(y[t < 150]))) < 1e-6
    # …and the real +50 step survives (drift correction must not flatten signal).
    assert abs(float(np.mean(y[t >= 250])) - 50.0) < 1e-6


def test_quadratic_fit_removes_curvature():
    t_ref = np.arange(0, 100, 1.0)
    ref = _frame(t_ref, 0.01 * t_ref**2 + 3.0 * t_ref)
    t = np.arange(0, 100, 1.0)
    full = _frame(t, 0.01 * t**2 + 3.0 * t)
    out = science.detrend(full, ref, t0_us=0, order=2).sort("timestamp")
    assert float(np.max(np.abs(out["value"].to_numpy()))) < 1e-6


def test_per_group_independent_and_safe_on_short_window():
    # Group 1 drifts, group 0 is flat; each is corrected against its own fit.
    t = np.arange(0, 50, 1.0)
    g0 = _frame(t, np.full_like(t, 5.0), group=0)
    g1 = _frame(t, 4.0 * t, group=1)
    full = pl.concat([g0, g1])
    out = science.detrend(full, full, t0_us=0, order=1)
    r0 = out.filter(pl.col("group") == 0)["value"].to_numpy()
    r1 = out.filter(pl.col("group") == 1)["value"].to_numpy()
    assert float(np.max(np.abs(r0))) < 1e-6
    assert float(np.max(np.abs(r1))) < 1e-6

    # A reference window too short to fit the requested order leaves data untouched.
    tiny = _frame([0.0], [9.0])
    assert science.detrend(full, tiny, t0_us=0, order=1).equals(full)
    assert science.detrend(full, pl.DataFrame(), t0_us=0).equals(full)
