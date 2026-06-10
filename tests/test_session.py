"""Workspace session persistence (RunSet save/peek/load)."""
from __future__ import annotations

import json
import os
import shutil

import pytest

from qcm.viz import runset as rs

_REAL_RUN = "/tmp/real-echem-run"


def _needs_real_run():
    if not os.path.isfile(os.path.join(_REAL_RUN, "manifest.json")):
        pytest.skip("real CP run missing")


def test_session_roundtrip(tmp_path):
    _needs_real_run()
    d2 = tmp_path / "run2"
    shutil.copytree(_REAL_RUN, d2)
    m = d2 / "manifest.json"
    j = json.load(open(m))
    j["run_id"] = "run2"
    json.dump(j, open(m, "w"))

    session = tmp_path / "session.json"
    src = rs.RunSet.from_paths([_REAL_RUN, str(d2)], active=1)
    src.set_label(0, "baseline")
    src.set_label(1, "with TU")
    assert src.save_session(session) == session

    entries = rs.peek_session(session)
    assert [e["label"] for e in entries] == ["baseline", "with TU"]

    loaded = rs.load_session(session)
    assert loaded is not None
    assert loaded.labels() == ["baseline", "with TU"]
    assert loaded.active_index == 1
    assert str(loaded.active.run.path) == str(d2)


def test_session_skips_vanished_runs(tmp_path):
    _needs_real_run()
    session = tmp_path / "session.json"
    payload = {
        "version": 1,
        "active": 0,
        "runs": [
            {"path": str(tmp_path / "gone"), "label": "gone"},
            {"path": _REAL_RUN, "label": "still here"},
        ],
    }
    session.write_text(json.dumps(payload))
    entries = rs.peek_session(session)
    assert [e["label"] for e in entries] == ["still here"]
    loaded = rs.load_session(session)
    assert loaded is not None and len(loaded.runs) == 1
    assert loaded.labels() == ["still here"]


def test_no_session_is_none(tmp_path):
    missing = tmp_path / "nope.json"
    assert rs.peek_session(missing) == []
    assert rs.load_session(missing) is None
    corrupt = tmp_path / "bad.json"
    corrupt.write_text("{not json")
    assert rs.load_session(corrupt) is None


def test_viewer_records_session(tmp_path, monkeypatch):
    _needs_real_run()
    session = tmp_path / "auto.json"
    monkeypatch.setenv("QCM_SESSION_FILE", str(session))
    from qcm.viz.app import QCMViewer

    QCMViewer([_REAL_RUN])
    assert session.exists()
    assert rs.peek_session(session)[0]["path"] == _REAL_RUN
