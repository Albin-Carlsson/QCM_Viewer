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
    src = next(p for p in case.iterdir()
               if p.name.startswith("input") and not p.name.startswith("input_ps"))
    ps = next((p for p in case.iterdir() if p.name.startswith("input_ps")), None)

    # Detection picks the recorded profile (for the PS sibling too, if any)…
    assert detect_profile(src) == expected["profile"]
    assert profile_kind(expected["profile"]) == expected["kind"]
    if ps is not None:
        assert detect_profile(ps) == expected["ps_profile"]
        assert profile_kind(expected["ps_profile"]) == "ps"

    # …and a full import reproduces the canonical run table exactly.
    import_run(src, tmp_path / "run", ps_source=ps)
    got = pl.read_parquet(str(tmp_path / "run" / "raw" / "*.parquet")).sort(["timestamp", "group"])
    want = pl.read_parquet(case / "expected.parquet")
    assert got.columns == want.columns
    assert got.equals(want), f"{case.name}: imported table drifted from golden"
    assert sorted(int(g) for g in got["group"].unique().to_list()) == expected["groups"]

    # Capability flags and the CP echem sidecar are part of the contract.
    if "capabilities" in expected:
        manifest = json.loads((tmp_path / "run" / "manifest.json").read_text())
        assert set(expected["capabilities"]) <= set(manifest["capabilities"]), case.name
    if expected.get("echem_sidecar"):
        assert (tmp_path / "run" / "echem.parquet").exists(), case.name
