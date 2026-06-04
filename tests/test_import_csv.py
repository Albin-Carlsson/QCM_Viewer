"""Tests for the standardized-QCM-csv import path and the relaxed run contract."""
from __future__ import annotations

import numpy as np
import polars as pl

from qcm.profiles import import_run
from qcm.profiles.standardized_csv import is_standardized_csv, read_standardized_csv
from qcm.run import open_run

_US = 1_000_000


def _write_standardized_csv(path, *, n_rows=20):
    """Two overtones (n=1 at 5 MHz, n=3 at 15 MHz) with constant dissipation."""
    t = np.round(np.arange(n_rows) * 0.5, 3)  # seconds
    df = pl.DataFrame({
        "Time_1": t, "Fr_1": np.full(n_rows, 5_000_000.0), "D_1": np.full(n_rows, 500.0),
        "Time_3": t, "Fr_3": np.full(n_rows, 15_000_000.0), "D_3": np.full(n_rows, 200.0),
    })
    df.write_csv(path)
    return path


def _write_raw_parquet(path, *, n_rows=10):
    """A minimal full raw-sweep parquet (one frequency point per sweep/group)."""
    seq = np.arange(n_rows)
    pl.DataFrame({
        "timestamp": (seq * _US).astype(np.int64),
        "sequence": seq.astype(np.int64),
        "group": np.zeros(n_rows, dtype=np.int64),
        "frequency": np.full(n_rows, 5_000_000.0),
        "raw_i": np.ones(n_rows), "raw_q": np.ones(n_rows),
        "conductance": np.ones(n_rows), "susceptance": np.ones(n_rows),
        "fit_center": np.full(n_rows, 5_000_000.0),
        "fit_gamma": np.full(n_rows, 100.0),
        "fit_fwhm": np.full(n_rows, 2_500.0),
    }).write_parquet(path)
    return path


def test_is_standardized_csv(tmp_path):
    csv = _write_standardized_csv(tmp_path / "qcm.csv")
    assert is_standardized_csv(csv) is True
    other = tmp_path / "other.csv"
    pl.DataFrame({"a": [1, 2], "b": [3, 4]}).write_csv(other)
    assert is_standardized_csv(other) is False


def test_read_standardized_csv_maps_overtones(tmp_path):
    csv = _write_standardized_csv(tmp_path / "qcm.csv", n_rows=8)
    frame = read_standardized_csv(csv)
    assert set(frame.columns) == {"timestamp", "sequence", "group", "fit_center", "fit_fwhm", "frequency"}
    # Each overtone order becomes a group.
    assert sorted(frame["group"].unique().to_list()) == [1, 3]
    g1 = frame.filter(pl.col("group") == 1)
    assert g1["fit_center"][0] == 5_000_000.0
    # dissipation = fit_fwhm / fit_center * 1e6 must recover the source D (ppm).
    diss = g1["fit_fwhm"][0] / g1["fit_center"][0] * _US
    assert abs(diss - 500.0) < 1e-6
    # Time (s) becomes integer microseconds.
    assert g1["timestamp"][1] == 500_000


def test_import_csv_produces_fit_only_run(tmp_path):
    csv = _write_standardized_csv(tmp_path / "qcm.csv", n_rows=30)
    run_dir = tmp_path / "run"
    import_run(csv, run_dir)

    run = open_run(run_dir)
    assert run.has_raw is False
    assert sorted(run.groups) == [1, 3]
    # Overtone orders are inferred from the resonance ratio and match the labels.
    assert run.overtone_orders() == {1: 1, 3: 3}
    # The fitted timeline is readable for both channels.
    tl = run.timeline(["fit_center"], level="raw")
    assert tl.height > 0
    assert sorted(tl["group"].unique().to_list()) == [1, 3]
    # Source path records the original csv, not the staging parquet.
    assert run.manifest.source_path.endswith("qcm.csv")


def test_import_parquet_still_produces_raw_run(tmp_path):
    pq = _write_raw_parquet(tmp_path / "raw.parquet")
    run_dir = tmp_path / "run"
    import_run(pq, run_dir)
    run = open_run(run_dir)
    assert run.has_raw is True
    assert run.groups == [0]
