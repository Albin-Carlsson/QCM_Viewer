"""Golden-file harness for import profiles.

Each ``tests/golden/<case>/`` holds an ``input.<ext>`` plus ``expected.parquet``
(the canonical run table a full import must produce) and ``expected.json`` (the
detected profile + table shape). One parametrized test locks every case end to
end — detect → read → ingest — so adding a data source is "drop a folder" and any
drift in a reader is caught.
"""
from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from qcm.profiles import detect_profile, import_run, profile_kind

_GOLDEN = Path(__file__).parent / "golden"
_CASES = sorted(p for p in _GOLDEN.iterdir() if p.is_dir()) if _GOLDEN.exists() else []


@pytest.mark.parametrize("case", _CASES, ids=lambda p: p.name)
def test_golden_import_is_stable(case: Path, tmp_path):
    expected = json.loads((case / "expected.json").read_text())
    src = next(p for p in case.iterdir() if p.name.startswith("input"))

    # Detection picks the recorded profile…
    assert detect_profile(src) == expected["profile"]
    assert profile_kind(expected["profile"]) == expected["kind"]

    # …and a full import reproduces the canonical run table exactly.
    import_run(src, tmp_path / "run")
    got = pl.read_parquet(str(tmp_path / "run" / "raw" / "*.parquet")).sort(["timestamp", "group"])
    want = pl.read_parquet(case / "expected.parquet")
    assert got.columns == want.columns
    assert got.equals(want), f"{case.name}: imported table drifted from golden"
    assert sorted(int(g) for g in got["group"].unique().to_list()) == expected["groups"]
