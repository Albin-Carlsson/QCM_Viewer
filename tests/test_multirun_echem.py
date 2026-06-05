"""Multi-run echem overlay + cross-run cycle comparison (issue #15).

The aggregation functions are pure over a list of ``(label, waveform)`` pairs so
they can be exercised with synthetic CP/CV waveforms, independent of the run I/O.
"""
from __future__ import annotations

import numpy as np
import polars as pl

from qcm.viz import echem, plots

_US = 1_000_000


def _cp_wf(n_cycles=3, plate_n=11, strip_n=6, dt=1.0, current=1.0):
    """CP waveform: plating (negative I) then stripping (positive I) per cycle."""
    times: list[float] = []
    cur: list[float] = []
    t = 0.0
    for _ in range(n_cycles):
        for _ in range(plate_n):
            times.append(t); cur.append(-current); t += dt
        for _ in range(strip_n):
            times.append(t); cur.append(+current); t += dt
    tarr = np.array(times)
    carr = np.array(cur)
    charge = np.cumsum(carr * dt)
    return pl.DataFrame({
        "timestamp": (tarr * _US).astype(np.int64),
        "time_s": tarr,
        "current": carr,
        "charge": charge,
        "potential": np.zeros_like(tarr),
    })


def test_overlay_cycle_stats_stacks_runs():
    a = _cp_wf(n_cycles=3)
    b = _cp_wf(n_cycles=3)
    out = echem.overlay_cycle_stats([("runA", a), ("runB", b)], technique="cp")
    assert {"run", "run_slot"}.issubset(out.columns)
    assert sorted(out["run"].unique().to_list()) == ["runA", "runB"]
    assert sorted(out["run_slot"].unique().to_list()) == [0, 1]


def test_overlay_cycle_stats_selects_same_cycle_across_runs():
    a = _cp_wf(n_cycles=4)
    b = _cp_wf(n_cycles=4)
    out = echem.overlay_cycle_stats(
        [("runA", a), ("runB", b)], technique="cp", mode="individual", cycle=2,
    )
    # Each run contributes exactly cycle 2 — the same selection across runs.
    assert out["cycle"].unique().to_list() == [2]
    assert out.filter(pl.col("run") == "runA").height == 1
    assert out.filter(pl.col("run") == "runB").height == 1


def test_overlay_selected_waveforms_tags_runs():
    a = _cp_wf(n_cycles=3)
    b = _cp_wf(n_cycles=3)
    out = echem.overlay_selected_waveforms([("runA", a), ("runB", b)], technique="cp")
    assert {"run", "run_slot"}.issubset(out.columns)
    assert sorted(out["run"].unique().to_list()) == ["runA", "runB"]
    # Cell-level signals are preserved for the plot.
    assert {"potential", "time_s", "current"}.issubset(out.columns)
    # Both runs contribute their full waveform.
    assert out.filter(pl.col("run") == "runA").height == a.height


def test_echem_overlay_one_curve_per_run():
    import holoviews as hv

    a = _cp_wf(n_cycles=2)
    b = _cp_wf(n_cycles=2)
    frame = echem.overlay_selected_waveforms([("runA", a), ("runB", b)], technique="cp")
    plot = plots.echem_overlay(
        frame, "time_s", "potential", "Time [s]", "Potential [V]", "E vs t",
        by_cycle=False, monotonic=True,
    )
    curves = [e for e in plot.values() if isinstance(e, hv.Curve)]
    assert len(curves) == 2  # one per run


def test_echem_overlay_by_cycle_splits_per_run_and_cycle():
    import holoviews as hv

    a = _cp_wf(n_cycles=2)
    b = _cp_wf(n_cycles=2)
    frame = echem.overlay_selected_waveforms([("runA", a), ("runB", b)], technique="cp")
    plot = plots.echem_overlay(
        frame, "time_s", "potential", "Time [s]", "Potential [V]", "E vs t",
        by_cycle=True, monotonic=True,
    )
    curves = [e for e in plot.values() if isinstance(e, hv.Curve)]
    assert len(curves) == 4  # 2 runs x 2 cycles
