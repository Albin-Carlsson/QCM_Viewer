"""Tests for the PSTrace potentiostat import + PS↔QCM alignment."""
from __future__ import annotations

import numpy as np
import polars as pl

from qcm.profiles import import_run
from qcm.profiles.pstrace_csv import attach_echem, is_pstrace_csv, read_pstrace_csv
from qcm.run import open_run
from qcm.viz import echem

_US = 1_000_000


def _write_pstrace_csv(path, *, n=11):
    """UTF-16 PSTrace CP export: potential=0.1*t V, current=1000 µA, charge=-10*t µC."""
    t = np.arange(n)
    rows = [
        "Date and time:,2026-04-29 17:19:45",
        "Notes:",
        ",,,,",
        "MultiStep Potentiometry: charge,,current,,E vs t",
        "Date and time measurement:,x,Date and time measurement:,x,Date and time measurement:,x,",
        "s,µC,s,µA,s,V",
    ]
    for ti in t:
        rows.append(f"{ti},{-10*ti},{ti},1000,{ti},{0.1*ti}")
    text = "\n".join(rows) + "\n"
    path.write_bytes(text.encode("utf-16"))
    return path


def _write_standardized_csv(path, *, times):
    n = len(times)
    pl.DataFrame({
        "Time_1": times, "Fr_1": np.full(n, 5_000_000.0), "D_1": np.full(n, 500.0),
        "Time_3": times, "Fr_3": np.full(n, 15_000_000.0), "D_3": np.full(n, 200.0),
    }).write_csv(path)
    return path


def test_is_pstrace_csv(tmp_path):
    ps = _write_pstrace_csv(tmp_path / "ps.csv")
    assert is_pstrace_csv(ps) is True
    other = tmp_path / "q.csv"
    pl.DataFrame({"Time_1": [0.0], "Fr_1": [5e6], "D_1": [1.0]}).write_csv(other)
    assert is_pstrace_csv(other) is False


def test_read_pstrace_csv_units(tmp_path):
    ps = read_pstrace_csv(_write_pstrace_csv(tmp_path / "ps.csv", n=6))
    assert ps.columns == ["time_s", "potential", "current", "charge"]
    # µA -> A and µC -> C conversion.
    assert abs(ps["current"][0] - 1e-3) < 1e-12          # 1000 µA
    assert abs(ps["charge"][5] - (-10 * 5 * 1e-6)) < 1e-12  # -50 µC
    assert abs(ps["potential"][2] - 0.2) < 1e-12          # 0.1 * 2 V


def test_attach_echem_interpolates_and_broadcasts():
    # Two overtone groups sharing timestamps at 0,1,2 s (in µs).
    ts = [0, 1 * _US, 2 * _US]
    qcm = pl.DataFrame({
        "timestamp": ts * 2,
        "group": [1, 1, 1, 3, 3, 3],
        "fit_center": [5e6, 5e6, 5e6, 15e6, 15e6, 15e6],
    })
    ps = pl.DataFrame({
        "time_s": [0.0, 1.0, 2.0, 3.0, 4.0],
        "potential": [0.0, 0.1, 0.2, 0.3, 0.4],
        "current": [1e-3] * 5,
        "charge": [0.0, -1e-5, -2e-5, -3e-5, -4e-5],
    })
    out = attach_echem(qcm, ps)
    assert {"potential", "current", "charge"}.issubset(out.columns)
    # Echem broadcast to both groups at t=1 s, interpolated to potential 0.1 V.
    at1 = out.filter(pl.col("timestamp") == _US)
    assert sorted(at1["group"].to_list()) == [1, 3]
    assert all(abs(p - 0.1) < 1e-9 for p in at1["potential"].to_list())


def test_attach_echem_offset_shifts_ps():
    qcm = pl.DataFrame({"timestamp": [0, 1 * _US], "group": [1, 1], "fit_center": [5e6, 5e6]})
    ps = pl.DataFrame({
        "time_s": [0.0, 1.0, 2.0],
        "potential": [0.0, 0.1, 0.2],
        "current": [0.0, 0.0, 0.0],
        "charge": [0.0, 0.0, 0.0],
    })
    # Offset +1 s: QCM elapsed 1 s now samples PS at elapsed 0 s -> potential 0.0.
    out = attach_echem(qcm, ps, offset_s=1.0)
    at1 = out.filter(pl.col("timestamp") == _US)
    assert abs(at1["potential"][0] - 0.0) < 1e-9


def test_import_csv_with_ps_produces_echem_run(tmp_path):
    times = list(np.round(np.arange(11) * 1.0, 3))
    csv = _write_standardized_csv(tmp_path / "qcm.csv", times=times)
    ps = _write_pstrace_csv(tmp_path / "ps.csv", n=11)
    run_dir = tmp_path / "run"
    import_run(csv, run_dir, ps_source=ps)

    run = open_run(run_dir)
    assert echem.has_echem(run.columns) is True
    for c in ("potential", "current", "charge"):
        assert c in run.columns
    # The cell-level waveform carries the interpolated signals.
    from qcm.viz.data import QCMViewData
    from qcm.viz.state import RunInfo
    info = RunInfo(run_id=run.id, groups=run.groups, orders=run.overtone_orders(),
                   t0_us=run.time_start, t1_us=run.time_end, span_s=1.0,
                   fmin=0, fmax=1, seq_min=0, seq_max=0, n_sweeps=0,
                   has_echem=True)
    wf = QCMViewData(run, info).echem_waveform()
    assert {"potential", "current", "charge"}.issubset(wf.columns)
    assert wf.height > 0


def test_import_csv_without_ps_has_no_echem(tmp_path):
    csv = _write_standardized_csv(tmp_path / "qcm.csv", times=[0.0, 1.0, 2.0])
    run_dir = tmp_path / "run"
    import_run(csv, run_dir)
    run = open_run(run_dir)
    assert echem.has_echem(run.columns) is False
