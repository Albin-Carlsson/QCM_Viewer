"""Unit tests for the pure plot helpers (decimation, cycle thinning, labels)."""
from __future__ import annotations

import numpy as np

from qcm.viz.plots import _decimate_xy, _thin_cycles, _thinned_title, series_labels
from qcm.viz.theme import MAX_PLOTTED_CYCLES


def test_decimate_passthrough_when_small():
    x = np.arange(10.0)
    y = x * 2
    dx, dy = _decimate_xy(x, y, max_points=100)
    assert np.array_equal(dx, x) and np.array_equal(dy, y)


def test_decimate_bounds_count_and_keeps_envelope():
    n = 50_000
    x = np.linspace(0, 1, n)
    y = np.sin(x * 40)
    # A single huge spike must survive min/max envelope decimation.
    y[31_337] = 99.0
    dx, dy = _decimate_xy(x, y, max_points=2000)
    assert len(dx) <= 2002 + 2  # buckets×2 + endpoints
    assert dy.max() == 99.0
    assert np.all(np.diff(dx) >= 0)  # still x-sorted
    # Endpoints survive.
    assert dx[0] == x[0] and dx[-1] == x[-1]


def test_thin_cycles_keeps_all_when_few():
    cycles = list(range(1, 9))
    kept, thinned = _thin_cycles(cycles)
    assert kept == cycles and not thinned


def test_thin_cycles_subsets_long_runs_keeping_ends():
    cycles = list(range(1, 201))
    kept, thinned = _thin_cycles(cycles)
    assert thinned
    assert len(kept) <= MAX_PLOTTED_CYCLES
    assert kept[0] == 1 and kept[-1] == 200


def test_thinned_title_mentions_counts():
    t = _thinned_title("CE per cycle", 12, 200)
    assert "12" in t and "200" in t


def test_series_labels_prefers_overtone_orders():
    labels = series_labels([0, 1, 2], {0: 1, 1: 3, 2: 5})
    assert labels == {0: "n = 1", 1: "n = 3", 2: "n = 5"}


def test_series_labels_falls_back_when_orders_collapse():
    labels = series_labels([0, 1], {0: 1, 1: 1})
    assert labels == {0: "Overtone 1", 1: "Overtone 2"}
