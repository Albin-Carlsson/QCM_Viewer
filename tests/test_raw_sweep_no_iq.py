"""Raw resonance sweeps without I/Q (conductance/susceptance-only exports).

Some acquisition tools export per-point resonance sweeps (frequency +
conductance/susceptance + fits) but no raw I/Q pair. Such a run must still be
recognised as *raw* (so the sweep/waterfall inspector is available), and the I/Q
view must degrade gracefully rather than error.
"""
from __future__ import annotations

import numpy as np
import polars as pl

from qcm.profiles import import_run
from qcm.run import open_run
from qcm.viz import plots


def _conductance_only_sweep(path):
    """A 2-group run with ~9 frequency points per sweep, no raw_i/raw_q."""
    rows = []
    for seq in range(3):
        for g, f0 in ((0, 5_000_000.0), (1, 15_000_000.0)):
            for k in range(9):
                f = f0 + (k - 4) * 50.0
                rows.append({
                    "timestamp": 1_000_000 * seq, "sequence": seq, "group": g,
                    "frequency": f, "conductance": np.exp(-((k - 4) ** 2) / 4.0),
                    "susceptance": (k - 4) * 0.01,
                    "fit_center": f0, "fit_fwhm": 100.0, "fit_gamma": 50.0,
                })
    pl.DataFrame(rows).write_parquet(path)
    return path


def test_conductance_only_export_is_recognised_as_raw(tmp_path):
    src = _conductance_only_sweep(tmp_path / "full.parquet")
    run_dir = tmp_path / "run"
    import_run(src, run_dir)
    run = open_run(run_dir)
    # No I/Q, but the conductance/susceptance sweep makes this a raw run.
    assert "raw_i" not in run.columns
    assert run.has_raw is True
    assert run.manifest.metadata["has_raw"] is True


def test_iq_scatter_degrades_without_iq():
    df = pl.DataFrame({"group": [0, 0], "frequency": [5e6, 5e6], "conductance": [0.1, 0.2]})
    out = plots.iq_scatter(df, "iq")  # must not raise (no raw_i/raw_q)
    # The empty placeholder carries the explanatory title.
    assert "No I/Q" in out.opts.get("plot").kwargs.get("title", "")
