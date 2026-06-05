"""CV PSTrace import: potential/scan-indexed adapter (issue #12).

The CV export is a per-scan ``i vs E`` block — pairs of (potential V, current µA)
columns, one pair per scan — with no time column (unlike the CP export). The
reader maps the ``i vs E`` group into a tidy ``[cycle, potential, current]``
frame; detection must not collide with the time-indexed CP profile.
"""
from __future__ import annotations

import polars as pl

from qcm.profiles.pstrace_cv_csv import (
    attach_cv_echem,
    is_cv_pstrace_csv,
    read_cv_pstrace_csv,
)


def _cv_csv(path, *, scans=2):
    cols_hdr = []
    cols_units = []
    for s in range(1, scans + 1):
        cols_hdr += [f"Cyclic Voltammetry [1]: CV i vs E Scan {s}", ""]
        cols_units += ["V", "µA"]
    rows = [
        "Date and time:,2026-05-28 10:38:50",
        "Notes:",
        "," * 5,
        ",".join(cols_hdr),
        ",".join(["Date and time measurement:,2026-05-27"] * scans),
        ",".join(cols_units),
    ]
    # three potential samples per scan; current decreases per scan so scans differ
    for k, e in enumerate((-0.20, -0.30, -0.40)):
        row = []
        for s in range(1, scans + 1):
            row += [f"{e}", f"{100 - 10 * (s - 1) - 5 * k}"]
        rows.append(",".join(row))
    path.write_text("\n".join(rows), encoding="utf-8")
    return path


def _cv_csv_with_extra_groups(path):
    """A CV export carrying Cell-potential (V,V) and WE-potential groups around
    the i-vs-E (V,µA) group — the layout PSTrace actually emits."""
    hdr = [
        "Cyclic Voltammetry [1]: CV Cell potential Scan 1", "",
        "Cyclic Voltammetry [1]: CV i vs E Scan 1", "",
        "Cyclic Voltammetry [1]: CV Measured WE potential Scan 1", "",
    ]
    units = ["V", "V", "V", "µA", "V", "V"]
    rows = [
        "Date and time:,x", "Notes:", "," * 5,
        ",".join(hdr),
        "Date and time measurement:,x,Date and time measurement:,x,Date and time measurement:,x",
        ",".join(units),
        "-0.20,-0.20,-0.20,100,-0.20,-0.199",
        "-0.30,-0.30,-0.30,80,-0.30,-0.299",
    ]
    path.write_text("\n".join(rows), encoding="utf-8")
    return path


def test_read_cv_pstrace_per_scan(tmp_path):
    df = read_cv_pstrace_csv(_cv_csv(tmp_path / "cv_PS.csv", scans=2))
    assert {"cycle", "potential", "current"}.issubset(df.columns)
    assert sorted(df["cycle"].unique().to_list()) == [1, 2]
    s1 = df.filter(pl.col("cycle") == 1)
    assert s1.height == 3
    # current converted µA -> A
    assert abs(s1["current"].max() - 100e-6) < 1e-12


def test_read_cv_pstrace_reads_only_i_vs_e_group(tmp_path):
    df = read_cv_pstrace_csv(_cv_csv_with_extra_groups(tmp_path / "cv_PS.csv"))
    # Only the (V, µA) i-vs-E pair becomes a row set; the V/V potential groups
    # are ignored, so current is real (not a mis-read potential column).
    assert df["cycle"].unique().to_list() == [1]
    assert df.height == 2
    assert abs(df["current"].max() - 100e-6) < 1e-12
    assert df["potential"].to_list() == [-0.20, -0.30]


def test_attach_cv_echem_maps_onto_timestamps():
    qcm = pl.DataFrame({
        "timestamp": [i * 1_000_000 for i in range(12)],
        "group": [1] * 12,
    })
    cv = pl.DataFrame({
        "cycle": [1, 1, 1, 2, 2, 2],
        "potential": [-0.2, -0.3, -0.4, -0.2, -0.3, -0.4],
        "current": [1e-4, 8e-5, 7e-5, 6e-5, 5e-5, 4e-5],
    })
    out = attach_cv_echem(qcm, cv)
    assert out.height == qcm.height
    assert {"potential", "current", "cycle"}.issubset(out.columns)
    # Both scans land somewhere on the run's timeline.
    assert sorted(out["cycle"].drop_nulls().unique().to_list()) == [1, 2]
    # Interpolated signals stay within the source range.
    assert out["current"].min() >= 4e-5 - 1e-12
    assert out["potential"].min() >= -0.4 - 1e-12


def _qcm_csv(path, n=40):
    import numpy as np
    t = np.round(np.arange(n) * 0.5, 3)
    pl.DataFrame({
        "Time_1": t, "Fr_1": np.full(n, 5_000_000.0), "D_1": np.full(n, 500.0),
    }).write_csv(path)
    return path


def _cv_csv_sweep(path, scans=3, n=24):
    import numpy as np
    hdr, units = [], []
    for s in range(1, scans + 1):
        hdr += [f"Cyclic Voltammetry [1]: CV i vs E Scan {s}", ""]
        units += ["V", "µA"]
    rows = ["Date and time:,x", "Notes:", "," * 5, ",".join(hdr),
            ",".join(["Date and time measurement:,x"] * scans), ",".join(units)]
    pots = np.linspace(-0.2, -0.4, n)
    for k in range(n):
        row = []
        for s in range(1, scans + 1):
            cur = 120.0 * np.sin(2 * np.pi * k / n) * s  # sign-changing sweep
            row += [f"{pots[k]:.4f}", f"{cur:.3f}"]
        rows.append(",".join(row))
    path.write_text("\n".join(rows), encoding="utf-8")
    return path


def test_import_qcm_plus_cv_ps_populates_cv_run(tmp_path):
    from qcm.profiles import import_run
    from qcm.run import open_run
    from qcm.viz import echem

    qcm = _qcm_csv(tmp_path / "qcm.csv")
    cv = _cv_csv_sweep(tmp_path / "cv_PS.csv", scans=3)
    run_dir = tmp_path / "run"
    import_run(qcm, run_dir, ps_source=cv)

    run = open_run(run_dir)
    for col in ("potential", "current", "cycle"):
        assert col in run.columns
    wf = run.timeline(["timestamp", "group", "potential", "current", "cycle"],
                      t0=run.time_start, t1=run.time_end)
    assert echem.detect_technique(echem.waveform(wf)) == "cv"
    assert wf["cycle"].drop_nulls().n_unique() >= 2  # multiple scans land


def test_cv_detection_rejects_cp_export(tmp_path):
    """A time-indexed CP export must not be picked up by the CV adapter, so the
    dispatch keeps routing it to the CP path (acceptance: CP unaffected)."""
    cp = tmp_path / "cp_PS.csv"
    text = "\n".join([
        "Date and time:,x", "Notes:", "s,µC,s,µA,s,V",
        "0,0,0,1000,0,0.1", "1,-10,1,1000,1,0.2", "2,-20,2,1000,2,0.3",
    ])
    cp.write_bytes(text.encode("utf-16"))
    assert not is_cv_pstrace_csv(cp)
