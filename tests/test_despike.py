"""Hampel despike of resonance traces (science.despike + view-state wiring)."""
from __future__ import annotations

import numpy as np
import polars as pl

from qcm.viz import science


def _frame(values, group=1):
    n = len(values)
    return pl.DataFrame({
        "timestamp": np.arange(n, dtype=np.int64) * 1_000_000,
        "group": np.full(n, group, dtype=np.int64),
        "value": np.asarray(values, dtype=float),
    })


def test_despike_removes_isolated_spike():
    y = np.sin(np.linspace(0, 4 * np.pi, 200)) * 5.0
    y[50] += 400.0  # a relay spike
    y[120] -= 350.0
    out = science.despike(_frame(y), window=7)
    v = out.sort("timestamp")["value"].to_numpy()
    assert abs(v[50]) < 50.0
    assert abs(v[120]) < 50.0
    # untouched points are exactly preserved
    np.testing.assert_allclose(np.delete(v, [50, 120]), np.delete(y, [50, 120]))


def test_despike_preserves_steps():
    """A genuine step (deposition onset) must survive — that's the point of
    Hampel over a plain median filter."""
    y = np.concatenate([np.zeros(100), np.full(100, -200.0)])
    y += np.random.default_rng(0).normal(0, 0.5, y.size)
    out = science.despike(_frame(y), window=7)
    v = out.sort("timestamp")["value"].to_numpy()
    assert v[:95].mean() > -5.0
    assert v[105:].mean() < -195.0


def test_despike_per_group_independent():
    a = np.zeros(50)
    a[25] = 100.0
    clean = np.zeros(50)
    df = pl.concat([_frame(a, group=1), _frame(clean, group=3)])
    out = science.despike(df, window=5)
    g1 = out.filter(pl.col("group") == 1).sort("timestamp")["value"].to_numpy()
    g3 = out.filter(pl.col("group") == 3).sort("timestamp")["value"].to_numpy()
    assert abs(g1[25]) < 1.0
    np.testing.assert_allclose(g3, clean)


def test_despike_short_and_empty_frames_pass_through():
    short = _frame([1.0, 2.0, 3.0])
    assert science.despike(short, window=7).height == 3
    empty = pl.DataFrame()
    assert science.despike(empty).is_empty()


def test_viewstate_carries_despike_fields():
    from qcm.viz.state import ViewState

    s = ViewState(
        groups=[1], quantity="delta_f_norm", x_axis="time",
        t_range_s=(0.0, 1.0), baseline_s=(0.0, 0.1),
        orders={1: 1}, orders_text="", sequence=0, single_group=1,
        sweep_mode="all", frequency_band=(0.0, 1.0),
        despike=True, despike_window=9,
    )
    d = s.to_persisted_dict()
    assert d["despike"] is True
    assert d["despike_window"] == 9
