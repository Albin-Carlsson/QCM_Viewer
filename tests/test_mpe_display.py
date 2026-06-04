"""Tests for the MPE display path: positive sign, clipping, smoothing."""
from __future__ import annotations

import numpy as np
import polars as pl

from qcm.viz import science


def test_mpe_reported_as_positive_for_plating():
    # Plating: frequency drops (mass rises) while charge goes more negative.
    n = 6
    df = pl.DataFrame({
        "timestamp": (np.arange(n) * 1_000_000).astype(np.int64),
        "group": np.zeros(n, dtype=np.int64),
        "fit_center": 5_000_000.0 - np.arange(n) * 100.0,
        "charge": -np.arange(n) * 1.0,
    })
    out = science.compute(df, "mpe", {0: 1})
    vals = out["value"].drop_nulls().to_list()
    assert vals and all(v > 0 for v in vals)


def _noisy_mpe(n=200):
    rng = np.random.default_rng(0)
    base = 30.0 + np.zeros(n)
    noise = rng.normal(0, 8.0, n)
    spikes = np.zeros(n)
    if n > 50:
        spikes[50] = 5000.0
    if n > 120:
        spikes[120] = -4000.0
    return pl.DataFrame({
        "timestamp": (np.arange(n) * 1_000_000).astype(np.int64),
        "group": np.zeros(n, dtype=np.int64),
        "value": base + noise + spikes,
    })


def test_clip_bounds_outliers():
    out = science.smooth_clip_mpe(_noisy_mpe(), clip=(-100.0, 150.0))
    assert out["value"].max() <= 150.0 + 1e-9
    assert out["value"].min() >= -100.0 - 1e-9


def test_smoothing_reduces_variation():
    raw = _noisy_mpe()
    clipped = science.smooth_clip_mpe(raw, clip=(-100.0, 150.0))
    smoothed = science.smooth_clip_mpe(raw, clip=(-100.0, 150.0), smooth=True, window=21)
    assert smoothed["value"].std() < clipped["value"].std()


def test_smooth_clip_noop_without_flags():
    raw = _noisy_mpe(20)
    assert science.smooth_clip_mpe(raw).equals(raw)
