"""Auto-suggested baseline window (science.stablest_window)."""
from __future__ import annotations

import numpy as np

from qcm.viz import science


def test_picks_the_flat_stretch_not_the_noisy_ramp():
    # First 100 s: flat + tiny noise (a clean baseline). After: a noisy ramp.
    rng = np.random.default_rng(0)
    t = np.arange(0, 300, 0.5)
    y = np.where(t < 100, 5_000_000.0 + rng.normal(0, 0.2, t.size),
                 5_000_000.0 - (t - 100) * 50 + rng.normal(0, 50, t.size))
    win = science.stablest_window(t, y, width_s=20.0, search_end_s=300.0)
    assert win is not None
    lo, hi = win
    assert hi - lo == 20.0
    assert lo < 100 and hi <= 100  # the chosen window sits in the flat region


def test_search_end_limits_where_it_looks():
    t = np.arange(0, 200, 1.0)
    # Flat late, ramp early — but search_end forces the early region.
    y = np.concatenate([np.linspace(0, 100, 100), np.full(100, 100.0)])
    win = science.stablest_window(t, y, width_s=10.0, search_end_s=50.0)
    assert win is not None
    assert win[0] <= 50.0


def test_too_little_data_returns_none():
    assert science.stablest_window([0, 1, 2], [1, 1, 1], width_s=1.0) is None
    assert science.stablest_window([], [], width_s=1.0) is None
    # Non-finite values are dropped; all-NaN yields nothing usable.
    assert science.stablest_window(np.arange(20.0), np.full(20, np.nan), width_s=2.0) is None
