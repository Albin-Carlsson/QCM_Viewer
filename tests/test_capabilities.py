"""The manifest's explicit capability flags and column→unit map.

A run declares what it carries (``capabilities``: raw / echem / temperature)
and the source unit of every known column, so UI surfaces and the CLI key off
the manifest instead of sniffing marker columns.
"""
from __future__ import annotations

import polars as pl

from qcm.ingest import derive_capabilities, units_for
from qcm.profiles import import_run
from qcm.run import open_run


def test_derive_capabilities():
    assert derive_capabilities(["timestamp", "fit_center"]) == []
    assert derive_capabilities(["fit_center", "conductance"]) == ["raw"]
    assert derive_capabilities(["raw_i", "potential", "current"]) == ["raw", "echem"]
    # cell channels in the sidecar stream, not inline columns
    assert derive_capabilities(["fit_center"], echem_sidecar=True) == ["echem"]
    assert derive_capabilities(["fit_center", "temperature"]) == ["temperature"]
    # a stray cycle column alone is not an echem channel
    assert derive_capabilities(["fit_center", "cycle"]) == []


def test_units_for_known_columns_only():
    units = units_for(["timestamp", "fit_center", "potential", "group", "mystery"])
    assert units == {"timestamp": "us", "fit_center": "Hz", "potential": "V"}


def test_fit_only_import_writes_capabilities_and_units(tmp_path):
    frame = pl.DataFrame({
        "timestamp": [0, 0, 1_000_000, 1_000_000],
        "sequence": [0, 0, 1, 1],
        "group": [1, 3, 1, 3],
        "fit_center": [5e6, 15e6, 5e6, 15e6],
        "fit_fwhm": [100.0, 300.0, 100.0, 300.0],
        "frequency": [5e6, 15e6, 5e6, 15e6],
    })
    src = tmp_path / "fit_only.parquet"
    frame.write_parquet(src)
    run = open_run(import_run(src, tmp_path / "run"))
    assert run.manifest.schema_version == "1.1"
    assert run.capabilities == []
    assert run.has_raw is False
    assert run.manifest.units["fit_center"] == "Hz"
    assert run.manifest.units["timestamp"] == "us"


def test_cp_import_records_echem_capability_and_sidecar_units(real_echem_run):
    run = open_run(real_echem_run)
    assert "echem" in run.capabilities
    assert run.has_raw is False
    # units cover the sidecar stream's roles, not just inline columns
    assert run.manifest.units["potential"] == "V"
    assert run.manifest.units["current"] == "A"
    assert run.manifest.units["time_s"] == "s"
