"""Golden-file harness for import profiles + the plugin-registry contract.

Each ``tests/golden/<case>/`` holds an ``input.<ext>`` plus ``expected.parquet``
(the canonical frame a profile must produce) and ``expected.json`` (the detected
profile name/kind + frame shape). One parametrized test locks every case, so
adding a data source is "drop a folder" and any drift in a reader is caught.
"""
from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from qcm.profiles import (
    FunctionProfile,
    ProfileResult,
    _profile_by_name,
    detect_profile,
    detect_profiles,
    profile_kind,
    profiles,
)

_GOLDEN = Path(__file__).parent / "golden"
_CASES = sorted(p for p in _GOLDEN.iterdir() if p.is_dir()) if _GOLDEN.exists() else []


@pytest.mark.parametrize("case", _CASES, ids=lambda p: p.name)
def test_golden_profile_output_is_stable(case: Path):
    expected = json.loads((case / "expected.json").read_text())
    src = next(p for p in case.iterdir() if p.name.startswith("input"))

    # Detection picks the recorded profile…
    assert detect_profile(src) == expected["profile"]
    assert profile_kind(expected["profile"]) == expected["kind"]

    # …and its read() reproduces the canonical frame exactly.
    prof = _profile_by_name(expected["profile"])
    result = prof.read(src)
    assert isinstance(result, ProfileResult)
    got = result.frame.sort(["timestamp", "group"])
    want = pl.read_parquet(case / "expected.parquet")
    assert got.columns == want.columns
    assert got.equals(want), f"{case.name}: canonical frame drifted from golden"
    assert sorted(int(g) for g in got["group"].unique().to_list()) == expected["groups"]


def test_detect_profiles_is_confidence_ranked(tmp_path):
    # A clear standardized CSV ranks that profile first with positive confidence;
    # a nonsense file matches nothing.
    csv = tmp_path / "s.csv"
    pl.DataFrame({"Time_1": [0.0, 1.0], "Fr_1": [5e6, 5e6], "D_1": [1.0, 1.0]}).write_csv(csv)
    ranked = detect_profiles(csv)
    assert ranked and ranked[0][0] == "standardized_csv"
    assert all(c > 0 for _, c in ranked)
    junk = tmp_path / "junk.csv"
    junk.write_text("nothing,useful\n1,2\n")
    assert detect_profiles(junk) == []


def test_entry_point_plugin_is_discovered(monkeypatch):
    """A profile contributed via the ``qcm.profiles`` entry point is registered
    and wins detection when it claims a file with high confidence."""
    import qcm.profiles as P

    marker = {"read": 0}

    def _read(path, rename=None):
        marker["read"] += 1
        return ProfileResult(frame=pl.DataFrame({"timestamp": [0]}), metadata={"plugin": True})

    plugin = FunctionProfile("acme_format", "qcm", lambda path: 0.99, _read)

    class _EP:
        name = "acme"
        def load(self):
            return plugin

    monkeypatch.setattr(P, "_discover_entry_point_profiles", lambda: [plugin])
    monkeypatch.setattr(P, "_PROFILES_CACHE", None)  # force re-discovery

    assert plugin in profiles()
    assert _profile_by_name("acme_format") is plugin
    assert profile_kind("acme_format") == "qcm"
    # It outranks the built-ins on a file it claims with 0.99 confidence.
    f = Path("whatever.xyz")
    ranked = detect_profiles(f)
    assert ranked[0] == ("acme_format", 0.99)

    monkeypatch.setattr(P, "_PROFILES_CACHE", None)  # don't leak the plugin to other tests
