"""One-click PS↔QCM alignment: echem derived from a retained stream at an
editable, persisted offset (no re-import)."""
from __future__ import annotations

import numpy as np
import polars as pl

from qcm.profiles import import_run
from qcm.run import open_run
from qcm.viz.data import QCMViewData
from qcm.viz.state import RunInfo


def _write_pstrace_csv(path, *, n=21):
    t = np.arange(n)
    rows = [
        "Date and time:,2026-04-29 17:19:45", "Notes:", ",,,,",
        "MultiStep Potentiometry: charge,,current,,E vs t",
        "Date,:,x,Date,:,x,Date,:,x,", "s,µC,s,µA,s,V",
    ]
    for ti in t:
        rows.append(f"{ti},{-10*ti},{ti},1000,{ti},{0.1*ti}")
    path.write_bytes(("\n".join(rows) + "\n").encode("utf-16"))
    return path


def _write_standardized_csv(path, *, times):
    n = len(times)
    pl.DataFrame({
        "Time_1": times, "Fr_1": np.full(n, 5_000_000.0), "D_1": np.full(n, 500.0),
        "Time_3": times, "Fr_3": np.full(n, 15_000_000.0), "D_3": np.full(n, 200.0),
    }).write_csv(path)
    return path


def _open(tmp_path):
    times = list(np.round(np.arange(21) * 1.0, 3))
    csv = _write_standardized_csv(tmp_path / "qcm.csv", times=times)
    ps = _write_pstrace_csv(tmp_path / "ps.csv", n=21)
    run_dir = tmp_path / "run"
    import_run(csv, run_dir, ps_source=ps)
    run = open_run(run_dir)
    info = RunInfo(run_id=run.id, groups=run.groups, orders=run.overtone_orders(),
                   t0_us=run.time_start, t1_us=run.time_end, span_s=20.0,
                   fmin=0, fmax=1, seq_min=0, seq_max=20, n_sweeps=21, has_echem=True)
    return run, QCMViewData(run, info)


def test_import_writes_stream_not_baked_columns(tmp_path):
    run, _ = _open(tmp_path)
    # Echem lives in the sidecar stream, not the main fit table…
    assert run.has_echem_stream
    assert "potential" not in run.manifest.columns
    # …but is advertised as an available column (derived on read).
    assert "potential" in run.columns
    assert run.ps_offset_s == 0.0


def test_offset_persists_and_shifts_derived_echem(tmp_path):
    run, data = _open(tmp_path)

    def potential_at(seconds):
        wf = data.echem_waveform()
        row = wf.sort("time_s").filter(pl.col("time_s") >= seconds)
        return float(row["potential"][0])

    # At t=5 s with no offset, potential ≈ 0.1*5 = 0.5 V.
    assert abs(potential_at(5.0) - 0.5) < 0.02

    # Apply +2 s: QCM t=5 s now samples PS at elapsed 3 s -> potential ≈ 0.3 V.
    run.set_ps_offset(2.0)
    data.clear_echem_cache()
    assert abs(potential_at(5.0) - 0.3) < 0.02

    # Persisted to the manifest; a freshly opened run keeps the offset.
    reopened = open_run(run.path)
    assert reopened.ps_offset_s == 2.0

    # Reset restores the as-imported alignment.
    run.set_ps_offset(0.0)
    data.clear_echem_cache()
    assert abs(potential_at(5.0) - 0.5) < 0.02


def test_qcm_tail_beyond_ps_span_is_null_not_frozen(tmp_path):
    """A QCM run longer than the PS recording must get nulls past the PS end.

    ``np.interp`` clamps at the endpoints; un-masked that freezes the last
    current across the tail — a phantom applied current that corrupts cycle
    detection and CE. Regression for the held-endpoint bug.
    """
    # QCM records 40 s, the potentiostat only 20 s.
    times = list(np.round(np.arange(41) * 1.0, 3))
    csv = _write_standardized_csv(tmp_path / "qcm.csv", times=times)
    ps = _write_pstrace_csv(tmp_path / "ps.csv", n=21)
    run_dir = tmp_path / "run"
    import_run(csv, run_dir, ps_source=ps)
    run = open_run(run_dir)
    info = RunInfo(run_id=run.id, groups=run.groups, orders=run.overtone_orders(),
                   t0_us=run.time_start, t1_us=run.time_end, span_s=40.0,
                   fmin=0, fmax=1, seq_min=0, seq_max=40, n_sweeps=41, has_echem=True)
    data = QCMViewData(run, info)

    wf = data.echem_waveform().sort("time_s")
    inside = wf.filter(pl.col("time_s") <= 20.0)
    tail = wf.filter(pl.col("time_s") > 20.5)
    assert inside["current"].null_count() == 0
    assert tail.height > 0
    # The tail carries no fabricated (held) current/potential/charge.
    assert tail["current"].null_count() == tail.height
    assert tail["potential"].null_count() == tail.height
