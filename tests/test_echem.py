"""Unit tests for the pure electrochemistry analysis module."""
from __future__ import annotations

import numpy as np
import polars as pl

from qcm.viz import echem

_US = 1_000_000


def _cv_frame(n_cycles=4, per_cycle=40):
    """Synthetic CV: triangular potential, sign-changing current, cycle column."""
    rows = per_cycle * n_cycles
    seq = np.arange(rows)
    frac = (seq % per_cycle) / per_cycle
    tri = 1 - np.abs(2 * frac - 1)
    potential = -0.5 + 1.0 * tri
    scan_sign = np.where(frac < 0.5, 1.0, -1.0)
    current = scan_sign * (1e-5 + 5e-5 * np.exp(-((potential - 0.1) / 0.08) ** 2))
    cycle = (seq // per_cycle).astype(np.int64)
    ts = (1_000_000 + seq * 100_000).astype(np.int64)  # 0.1 s spacing
    return pl.DataFrame({
        "timestamp": ts,
        "group": np.zeros(rows, dtype=np.int64),
        "potential": potential,
        "current": current,
        "charge": np.cumsum(np.abs(current) * 0.1),
        "cycle": cycle.astype(np.float64),
        "cycle_time": frac * per_cycle * 0.1,
    })


def _cp_frame(n_steps=8, per_step=30):
    """Synthetic CP: constant |current|, alternating sign, sawtooth potential."""
    rows = per_step * n_steps
    seq = np.arange(rows)
    step = seq // per_step
    sign = np.where(step % 2 == 0, 1.0, -1.0)
    current = sign * 5e-5
    step_time = (seq % per_step) * 0.1
    potential = 0.1 + sign * (5e-5 * 250 + 1e3 * 5e-5 * step_time)
    cycle = (seq // (2 * per_step)).astype(np.int64)
    ts = (1_000_000 + seq * 100_000).astype(np.int64)
    return pl.DataFrame({
        "timestamp": ts,
        "group": np.zeros(rows, dtype=np.int64),
        "potential": potential,
        "current": current,
        "charge": np.cumsum(np.abs(current) * 0.1),
        "cycle": cycle.astype(np.float64),
        "cycle_time": step_time,
    })


def test_detect_technique_cv_vs_cp():
    assert echem.detect_technique(_cv_frame()) == "cv"
    assert echem.detect_technique(_cp_frame()) == "cp"


def test_has_echem():
    assert echem.has_echem(["timestamp", "potential", "current"]) is True
    assert echem.has_echem(["timestamp", "fit_center"]) is False


def test_cv_metadata_values():
    meta = echem.cv_metadata(_cv_frame(n_cycles=4))
    assert meta["n_scans"] == 4
    assert meta["e_start"] == -0.5
    assert meta["e_vertex1"] > meta["e_vertex2"]
    assert meta["scan_rate"] > 0


def test_cp_metadata_values():
    meta = echem.cp_metadata(_cp_frame(n_steps=8))
    assert abs(meta["applied_current"] - 5e-5) < 1e-6
    # Area is 1 cm² by default, so density equals current.
    assert abs(meta["applied_current_density"] - meta["applied_current"]) < 1e-12
    assert meta["step_duration"] > 0
    assert meta["n_steps"] >= 1


def test_filter_cycles():
    df = _cv_frame(n_cycles=5, per_cycle=20)
    assert echem.cycle_values(df) == [0, 1, 2, 3, 4]
    assert echem.filter_cycles(df, "all").height == df.height
    one = echem.filter_cycles(df, "individual", cycle=2)
    assert one["cycle"].unique().to_list() == [2.0]
    rng = echem.filter_cycles(df, "range", lo=1, hi=3)
    assert sorted(int(c) for c in rng["cycle"].unique().to_list()) == [1, 2, 3]


def test_cycle_stats_shape():
    stats = echem.cycle_stats(_cv_frame(n_cycles=3), "cv")
    assert stats.height == 3
    for col in ("cycle", "duration_s", "E_min_V", "E_max_V", "I_anodic_A", "I_cathodic_A"):
        assert col in stats.columns
