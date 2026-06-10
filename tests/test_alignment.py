"""PS↔QCM alignment lag estimate (science.alignment_lag)."""
from __future__ import annotations

import numpy as np
import polars as pl

from qcm.viz import science


def _cp_like(n=2000, dt=0.5, shift_s=0.0, seed=0):
    """Mass + current obeying Faraday (rate ∝ −I), with the EC stream shifted
    ``shift_s`` later on the shared time base."""
    rng = np.random.default_rng(seed)
    t = np.arange(n) * dt
    # square-wave current: plate (−) / strip (+), 60 s half-cycles
    current = np.where((t // 60).astype(int) % 2 == 0, -1e-3, 1e-3)
    mass = -np.cumsum(current) * dt * 1e5
    mass += rng.normal(0, 0.05 * np.abs(mass).max() / 100, n)
    # the EC stream arrives shift_s late: its value at time t belongs to t-shift
    cur_shifted = np.interp(t - shift_s, t, current)
    return pl.DataFrame({"t_s": t, "mass": mass, "current": cur_shifted})


def test_aligned_streams_report_zero_lag():
    out = science.alignment_lag(_cp_like(shift_s=0.0))
    assert out is not None
    assert abs(out["lag_s"]) <= 1.0
    assert out["corr"] > 0.8


def test_shifted_stream_lag_detected_with_sign():
    out = science.alignment_lag(_cp_like(shift_s=5.0))
    assert out is not None
    # EC features arrive 5 s late -> positive lag, fix = --ps-offset -5
    assert 3.5 <= out["lag_s"] <= 6.5


def test_insufficient_data_returns_none():
    assert science.alignment_lag(pl.DataFrame()) is None
    tiny = pl.DataFrame({"t_s": [0.0, 1.0], "mass": [0.0, 1.0], "current": [0.0, 1.0]})
    assert science.alignment_lag(tiny) is None


def test_constant_signal_returns_none():
    n = 500
    df = pl.DataFrame({
        "t_s": np.arange(n) * 1.0,
        "mass": np.zeros(n),
        "current": np.zeros(n),
    })
    assert science.alignment_lag(df) is None
