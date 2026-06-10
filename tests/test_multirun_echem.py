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


def test_cycle_overlay_runs_curve_per_run_and_cycle():
    import holoviews as hv
    from qcm.viz.theme import quantity

    rows = []
    for slot, run in [(0, "A"), (1, "B")]:
        for c in (1, 2):
            for t in range(3):
                rows.append({"run": run, "run_slot": slot, "cycle": c,
                             "t_rel_s": float(t), "value": float(t + c + slot)})
    frame = pl.DataFrame(rows)
    plot = plots.cycle_overlay_runs(frame, quantity("delta_f_norm"), "cycles")
    curves = [e for e in plot.values() if isinstance(e, hv.Curve)]
    assert len(curves) == 4  # 2 runs x 2 cycles


def test_cycle_trend_marker_per_run_and_series():
    import holoviews as hv
    rows = []
    for slot, run in [(0, "A"), (1, "B")]:
        for c in (1, 2, 3):
            rows.append({"run": run, "run_slot": slot, "cycle": c,
                         "MPE_plating_g_per_mol": 32.0 + c, "MPE_stripping_g_per_mol": 31.0 + c})
    frame = pl.DataFrame(rows)
    plot = plots.cycle_trend(
        frame,
        series=[("MPE_plating_g_per_mol", "plating", "circle"),
                ("MPE_stripping_g_per_mol", "stripping", "triangle")],
        ylabel="MPE (g/mol)", title="MPE vs cycle", target=32.69,
    )
    scatters = [e for e in plot.values() if isinstance(e, hv.Scatter)]
    assert len(scatters) == 4  # 2 runs x 2 series
    # target line present
    assert any(isinstance(e, hv.HLine) for e in plot.values())


def test_multi_augmented_has_mpe_and_ce(tmp_path):
    # Build two CP runs via the viewer and check the augmented frame the trend reads.
    import json, shutil
    from qcm.viz.app import QCMViewer
    src = "/tmp/real-echem-run"
    import os
    if not os.path.isfile(os.path.join(src, "manifest.json")):
        import pytest; pytest.skip("real CP run missing")
    d2 = tmp_path / "run2"
    shutil.copytree(src, d2)
    m = d2 / "manifest.json"; j = json.load(open(m)); j["run_id"] = "run2"; json.dump(j, open(m, "w"))
    v = QCMViewer([src, str(d2)])
    f = v.shell._results._multi_augmented(filtered=False)
    assert {"run", "cycle", "MPE_plating_g_per_mol", "MPE_stripping_g_per_mol", "CE_time"}.issubset(f.columns)
    assert f["run"].n_unique() == 2


def test_time_window_for_x_cycle_number(tmp_path):
    import os
    if not os.path.isfile("/tmp/real-echem-run/manifest.json"):
        import pytest; pytest.skip("real CP run missing")
    from qcm.viz.runset import load_run
    d = load_run("/tmp/real-echem-run")
    # time axis is identity
    assert d.time_window_for_x("time", 10.0, 20.0) == (10.0, 20.0)
    # cycle-number axis maps a cycle range to the enclosing time window
    win = d.time_window_for_x("cycle_number", 5, 8)
    assert win is not None
    lo, hi = win
    assert 0.0 <= lo < hi <= d.info.span_s
    # a higher cycle range starts later in time
    win2 = d.time_window_for_x("cycle_number", 20, 23)
    assert win2 is not None and win2[0] > lo
