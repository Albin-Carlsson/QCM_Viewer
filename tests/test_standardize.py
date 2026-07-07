"""Tests for standardized-csv export (the notebook's data-standardization step)."""
from __future__ import annotations

import polars as pl
from typer.testing import CliRunner

from qcm.cli import app
from qcm.profiles.qsoft_txt import read_qsoft_txt
from qcm.profiles.standardized_csv import read_standardized_csv, write_standardized_csv

_US = 1_000_000


def _cd(x: float) -> str:
    return f"{x}".replace(".", ",")  # decimal comma


def _write_qsoft_txt(path, *, n_rows=10):
    header = "\t".join(["Time_1 (s)", "f1_1 (Hz)", "D1_1 (ppm)", "f3_1 (Hz)", "D3_1 (ppm)"])
    rows = [header]
    for i in range(n_rows):
        t = round(i * 0.5, 3)
        rows.append("\t".join([
            _cd(t), _cd(5_000_000.0 - i), _cd(500.0 + i), _cd(15_000_000.0 - 3 * i), _cd(200.0 + i),
        ]))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


def test_write_standardized_csv_round_trips(tmp_path):
    frame = read_qsoft_txt(_write_qsoft_txt(tmp_path / "q.txt", n_rows=12))
    out = write_standardized_csv(frame, tmp_path / "q_std.csv")

    # The written file is the wide lab exchange shape…
    header = pl.read_csv(out, n_rows=0).columns
    assert header == ["Time_1", "Fr_1", "D_1", "Time_3", "Fr_3", "D_3"]

    # …and re-importing it reproduces the canonical frame.
    back = read_standardized_csv(out)
    cols = ["timestamp", "group", "fit_center", "fit_fwhm"]
    a = frame.select(cols).sort(["timestamp", "group"])
    b = back.select(cols).sort(["timestamp", "group"])
    assert a["timestamp"].equals(b["timestamp"])
    assert a["group"].equals(b["group"])
    assert (a["fit_center"] - b["fit_center"]).abs().max() < 1e-6
    assert (a["fit_fwhm"] - b["fit_fwhm"]).abs().max() < 1e-6


def test_standardize_cli_defaults_output_next_to_source(tmp_path):
    src = _write_qsoft_txt(tmp_path / "mp_cycling.txt")
    result = CliRunner().invoke(app, ["standardize", str(src)])
    assert result.exit_code == 0, result.output
    out = tmp_path / "mp_cycling.csv"
    assert out.exists()
    assert sorted(read_standardized_csv(out)["group"].unique().to_list()) == [1, 3]


def test_standardize_cli_refuses_overwriting_source(tmp_path):
    src = _write_qsoft_txt(tmp_path / "q.txt")
    csv = write_standardized_csv(read_qsoft_txt(src), tmp_path / "q.csv")
    result = CliRunner().invoke(app, ["standardize", str(csv)])
    assert result.exit_code != 0
    assert "already a csv" in result.output
