"""Runs opened from read-only locations (network shares, archives) must read fine.

Regression: ``load_annotations`` used to *write* an empty annotations file on
its read path, which crashed every annotation read on a read-only run dir.
Also locks the atomic-write helper used by the manifest/annotation/state savers.
"""
from __future__ import annotations

import json
import os
import stat

import numpy as np
import polars as pl
import pytest

from qcm.fileio import write_text_atomic
from qcm.profiles import import_run
from qcm.run import open_run


def _make_run(tmp_path):
    n = 10
    t = np.arange(n) * 0.5
    pl.DataFrame({
        "Time_1": t, "Fr_1": np.full(n, 5e6), "D_1": np.full(n, 100.0),
    }).write_csv(tmp_path / "q.csv")
    dest = tmp_path / "run"
    import_run(tmp_path / "q.csv", dest)
    return dest


def _chmod_tree(root, mode):
    for p in [root, *root.rglob("*")]:
        os.chmod(p, mode)


def test_annotations_read_on_readonly_run(tmp_path):
    dest = _make_run(tmp_path)
    (dest / "annotations.json").unlink()  # the case that used to trigger a write
    _chmod_tree(dest, stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP)
    try:
        with open_run(dest) as run:
            assert run.annotations() == []
            assert run.timeline(["fit_center"]).height > 0
            assert run.load_view_state() == {}
    finally:
        _chmod_tree(dest, stat.S_IRWXU)


def test_write_text_atomic_replaces_and_cleans_up(tmp_path):
    target = tmp_path / "deep" / "file.json"
    write_text_atomic(target, json.dumps({"a": 1}))
    write_text_atomic(target, json.dumps({"a": 2}))
    assert json.loads(target.read_text()) == {"a": 2}
    # No stray temp files left behind.
    assert [p.name for p in target.parent.iterdir()] == ["file.json"]


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission semantics")
def test_write_text_atomic_raises_cleanly_on_readonly_dir(tmp_path):
    ro = tmp_path / "ro"
    ro.mkdir()
    os.chmod(ro, stat.S_IRUSR | stat.S_IXUSR)
    try:
        with pytest.raises(OSError):
            write_text_atomic(ro / "x.json", "{}")
    finally:
        os.chmod(ro, stat.S_IRWXU)
