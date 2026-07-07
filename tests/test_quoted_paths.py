"""Regression: run directories under quoted paths must work end to end.

Folder names with apostrophes (``viktor's data``) are routine on macOS. DuckDB
cannot bind the ``read_parquet('…')`` path as a parameter, so every embedded
path must be escaped as a SQL literal (qcm.sqlutil.sql_path) — this suite locks
that for ingest *and* every QCMRun query path.
"""
from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from qcm.profiles import import_run
from qcm.run import open_run


@pytest.fixture()
def quoted_run(tmp_path):
    base = tmp_path / "viktor's data"
    base.mkdir()
    n = 20
    t = np.arange(n) * 0.5
    pl.DataFrame({
        "Time_1": t, "Fr_1": np.full(n, 5e6), "D_1": np.full(n, 100.0),
        "Time_3": t, "Fr_3": np.full(n, 15e6), "D_3": np.full(n, 60.0),
    }).write_csv(base / "q.csv")
    import_run(base / "q.csv", base / "run")
    with open_run(base / "run") as run:
        yield run


def test_timeline_on_quoted_path(quoted_run):
    df = quoted_run.timeline(["fit_center"], level="raw")
    assert df.height > 0


def test_sweep_index_and_orders_on_quoted_path(quoted_run):
    idx = quoted_run.sweep_index()
    assert idx.height > 0
    assert quoted_run.overtone_orders() == {1: 1, 3: 3}


def test_baseline_and_sweeps_on_quoted_path(quoted_run):
    base = quoted_run.baseline_mean("fit_center")
    assert base.height == 2
    sweeps = quoted_run.sweeps_at(sequence=int(idx0 := quoted_run.sweep_index()["sequence"][0]))
    assert sweeps.height > 0
    one = quoted_run.sweep(sequence=int(idx0), group=1)
    assert set(one["group"].unique().to_list()) == {1}


def test_close_is_idempotent(quoted_run):
    quoted_run.close()
    quoted_run.close()  # double close must not raise
