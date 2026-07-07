"""Mutation paths in ViewerActions: phase markers and baseline sync.

These write to the run directory, so each test gets its own copy of the
synthesized EQCM run.
"""
from __future__ import annotations

import shutil

import pytest

from qcm.viz.app import QCMViewer


@pytest.fixture()
def viewer(real_echem_run, tmp_path):
    run_dir = tmp_path / "run"
    shutil.copytree(real_echem_run, run_dir)
    return QCMViewer(str(run_dir))


def test_add_window_marker_persists_annotation(viewer):
    actions = viewer.actions
    actions.controls.region_label.value = "plating phase"
    before = len(viewer.runset.active.run.annotations())
    actions.add_window_marker()
    anns = viewer.runset.active.run.annotations()
    assert len(anns) == before + 1
    added = anns[-1]
    assert added.label == "plating phase"
    assert added.type == "range"
    assert added.t1 is not None and added.t1 > added.t0


def test_add_point_marker_uses_marker_midpoint(viewer):
    actions = viewer.actions
    actions.controls.region_label.value = ""
    actions.add_point_marker()
    added = viewer.runset.active.run.annotations()[-1]
    assert added.type == "point"
    assert added.t1 is None
    assert added.label  # falls back to the region-type title, never empty


def test_remove_annotation_round_trip(viewer):
    run = viewer.runset.active.run
    viewer.actions.add_point_marker()
    added = run.annotations()[-1]
    run.remove_annotation(added.id)
    assert all(a.id != added.id for a in run.annotations())


def test_sync_baseline_to_selection_and_revert(viewer):
    controls = viewer.controls
    original = tuple(controls.baseline_range.value)
    controls.t_range.value = (100.0, 200.0)
    viewer.actions.sync_baseline_to_selection()
    assert tuple(controls.baseline_range.value) == (100.0, 200.0)
    viewer.actions.revert_baseline()
    assert tuple(controls.baseline_range.value) == original
