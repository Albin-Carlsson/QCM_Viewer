"""CSV export of the derived results tables (per-cycle + per-channel comparison)."""
from __future__ import annotations

import os

import pytest

_REAL_RUN = "/tmp/real-echem-run"


def _viewer(paths):
    from qcm.viz.app import QCMViewer

    return QCMViewer(paths)


def _needs_real_run():
    if not os.path.isfile(os.path.join(_REAL_RUN, "manifest.json")):
        pytest.skip("real CP run missing")


def test_per_cycle_frame_and_csv_roundtrip():
    _needs_real_run()
    step = _viewer([_REAL_RUN]).shell._results
    frame = step._per_cycle_frame()
    assert not frame.is_empty()
    assert "cycle" in frame.columns

    dl = step.csv_download(step._per_cycle_frame, "per_cycle_summary.csv")
    text = dl.callback().read().decode()
    header = text.splitlines()[0]
    assert "cycle" in header
    # one CSV row per table row
    assert len(text.strip().splitlines()) == frame.height + 1


def test_comparison_frame_csv_multi_run(tmp_path):
    _needs_real_run()
    import json
    import shutil

    d2 = tmp_path / "run2"
    shutil.copytree(_REAL_RUN, d2)
    m = d2 / "manifest.json"
    j = json.load(open(m))
    j["run_id"] = "run2"
    json.dump(j, open(m, "w"))

    step = _viewer([_REAL_RUN, str(d2)]).shell._results
    frame = step._comparison_frame()
    assert not frame.is_empty()
    assert frame["run"].n_unique() == 2

    dl = step.csv_download(step._comparison_frame, "per_channel_comparison.csv")
    text = dl.callback().read().decode()
    assert text.splitlines()[0].startswith("run")


def test_csv_download_empty_frame_is_safe():
    """The button must not raise when there is nothing to export."""
    import polars as pl

    _needs_real_run()
    step = _viewer([_REAL_RUN]).shell._results
    dl = step.csv_download(lambda: pl.DataFrame(), "empty.csv")
    assert dl.callback().read() == b""
