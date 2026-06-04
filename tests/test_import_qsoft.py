"""Tests for the Qsoft .txt import profile (tab + decimal comma)."""
from __future__ import annotations

import numpy as np
import polars as pl

from qcm.profiles import import_run
from qcm.profiles.qsoft_txt import is_qsoft_txt, read_qsoft_txt
from qcm.run import open_run

_US = 1_000_000


def _cd(x: float) -> str:
    return f"{x}".replace(".", ",")  # decimal comma


def _write_qsoft_txt(path, *, n_rows=10):
    """Two overtones (1 @ 5 MHz, 3 @ 15 MHz) with unit-suffixed, comma-decimal cols."""
    header = "\t".join(["Time_1 (s)", "f1_1 (Hz)", "D1_1 (ppm)", "f3_1 (Hz)", "D3_1 (ppm)"])
    rows = [header]
    for i in range(n_rows):
        t = round(i * 0.5, 3)
        rows.append("\t".join([_cd(t), _cd(5_000_000.0), _cd(500.0), _cd(15_000_000.0), _cd(200.0)]))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


def _write_standardized_csv(path, *, n_rows=10):
    t = np.round(np.arange(n_rows) * 0.5, 3)
    pl.DataFrame({
        "Time_1": t, "Fr_1": np.full(n_rows, 5_000_000.0), "D_1": np.full(n_rows, 500.0),
        "Time_3": t, "Fr_3": np.full(n_rows, 15_000_000.0), "D_3": np.full(n_rows, 200.0),
    }).write_csv(path)
    return path


def test_is_qsoft_txt(tmp_path):
    assert is_qsoft_txt(_write_qsoft_txt(tmp_path / "q.txt")) is True
    csv = tmp_path / "s.csv"
    _write_standardized_csv(csv)
    assert is_qsoft_txt(csv) is False


def test_read_qsoft_txt_maps_overtones(tmp_path):
    frame = read_qsoft_txt(_write_qsoft_txt(tmp_path / "q.txt", n_rows=8))
    assert sorted(frame["group"].unique().to_list()) == [1, 3]
    g1 = frame.filter(pl.col("group") == 1)
    assert abs(g1["fit_center"][0] - 5_000_000.0) < 1e-6        # decimal-comma parsed
    diss = g1["fit_fwhm"][0] / g1["fit_center"][0] * _US
    assert abs(diss - 500.0) < 1e-6                              # dissipation preserved
    assert g1["timestamp"][1] == 500_000                        # 0.5 s -> µs


def test_qsoft_txt_matches_standardized_csv(tmp_path):
    a = read_qsoft_txt(_write_qsoft_txt(tmp_path / "q.txt", n_rows=12))
    from qcm.profiles.standardized_csv import read_standardized_csv
    b = read_standardized_csv(_write_standardized_csv(tmp_path / "s.csv", n_rows=12))
    cols = ["timestamp", "group", "fit_center", "fit_fwhm"]
    a = a.select(cols).sort(["timestamp", "group"])
    b = b.select(cols).sort(["timestamp", "group"])
    assert a.equals(b)


def test_import_qsoft_txt_produces_fit_only_run(tmp_path):
    run_dir = tmp_path / "run"
    import_run(_write_qsoft_txt(tmp_path / "q.txt", n_rows=30), run_dir)
    run = open_run(run_dir)
    assert run.has_raw is False
    assert sorted(run.groups) == [1, 3]
    assert run.overtone_orders() == {1: 1, 3: 3}
