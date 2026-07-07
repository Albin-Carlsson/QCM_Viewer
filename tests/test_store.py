"""Persistent run store: imports land in a stable dir and survive a reopen."""
from __future__ import annotations

import os
import time

import numpy as np
import polars as pl

from qcm.run import open_run
from qcm.store import import_or_reuse, persistent_run_dir, runs_dir


def _write_csv(path, *, n=12, base=5e6):
    t = np.round(np.arange(n) * 0.5, 3)
    pl.DataFrame({
        "Time_1": t, "Fr_1": np.full(n, base), "D_1": np.full(n, 100.0),
        "Time_3": t, "Fr_3": np.full(n, base * 3), "D_3": np.full(n, 60.0),
    }).write_csv(path)
    return path


def test_runs_dir_honours_override():
    assert str(runs_dir()).endswith("runs")  # conftest points it at the tmp store


def test_persistent_dir_is_stable_and_disambiguated(tmp_path):
    a = tmp_path / "a"; a.mkdir()
    b = tmp_path / "b"; b.mkdir()
    _write_csv(a / "mp.csv"); _write_csv(b / "mp.csv")
    # Same source → same dir; same stem in a different folder → different dir.
    assert persistent_run_dir(a / "mp.csv") == persistent_run_dir(a / "mp.csv")
    assert persistent_run_dir(a / "mp.csv") != persistent_run_dir(b / "mp.csv")


def test_import_then_reuse_preserves_user_work(tmp_path):
    src = _write_csv(tmp_path / "mp.csv")
    dest, reused = import_or_reuse(src)
    assert not reused and (dest / "manifest.json").exists()

    # A researcher's annotation written into the run dir…
    with open_run(dest) as run:
        run.add_annotation(type="range", t0=run.time_start, t1=run.time_end, label="plating")

    # …survives a reopen of the same source (the run is reused, not rebuilt).
    dest2, reused2 = import_or_reuse(src)
    assert dest2 == dest and reused2
    with open_run(dest2) as run:
        assert [a.label for a in run.annotations()] == ["plating"]


def test_changed_source_triggers_reimport(tmp_path):
    src = _write_csv(tmp_path / "mp.csv", base=5e6)
    dest, _ = import_or_reuse(src)
    # Touch the source newer than the run, then rewrite it.
    time.sleep(0.01)
    _write_csv(src, base=6e6)
    os.utime(src, None)
    dest2, reused = import_or_reuse(src)
    assert dest2 == dest and not reused  # stale run re-imported


def test_explicit_scan_rate_forces_fresh_import(tmp_path):
    src = _write_csv(tmp_path / "mp.csv")
    import_or_reuse(src)
    _, reused = import_or_reuse(src, cv_scan_rate=0.05)
    assert not reused


def test_runs_land_under_the_store(tmp_path):
    src = _write_csv(tmp_path / "mp.csv")
    dest, _ = import_or_reuse(src)
    assert runs_dir() in dest.parents
