"""Profile auto-detection registry + column-mapping override (issue #11)."""
from __future__ import annotations

import polars as pl

from qcm.profiles import detect_profile


def _standardized_csv(path):
    pl.DataFrame({
        "Time_1": [0.0, 0.5], "Fr_1": [5e6, 5e6], "D_1": [500.0, 500.0],
    }).write_csv(path)
    return path


def test_detect_standardized_csv(tmp_path):
    assert detect_profile(_standardized_csv(tmp_path / "qcm.csv")) == "standardized_csv"


def test_detect_unmappable_returns_none(tmp_path):
    junk = tmp_path / "junk.csv"
    junk.write_text("alpha,beta\n1,2\n3,4\n", encoding="utf-8")
    assert detect_profile(junk) is None


def _cv_ps(path):
    rows = [
        "Date and time:,x", "Notes:", "," * 5,
        "Cyclic Voltammetry [1]: CV i vs E Scan 1,,Cyclic Voltammetry [1]: CV i vs E Scan 2,",
        "Date and time measurement:,x,Date and time measurement:,x",
        "V,µA,V,µA", "-0.20,100,-0.20,60", "-0.30,80,-0.30,55",
    ]
    path.write_text("\n".join(rows), encoding="utf-8")
    return path


def _cp_ps(path):
    text = "\n".join([
        "Date and time:,x", "Notes:", "s,µC,s,µA,s,V",
        "0,0,0,1000,0,0.1", "1,-10,1,1000,1,0.2",
    ])
    path.write_bytes(text.encode("utf-16"))
    return path


def test_detect_distinguishes_ps_cv_and_cp(tmp_path):
    assert detect_profile(_cv_ps(tmp_path / "cv_PS.csv")) == "pstrace_cv"
    assert detect_profile(_cp_ps(tmp_path / "cp_PS.csv")) == "pstrace_cp"


def test_detect_parquet_dir(tmp_path):
    (tmp_path / "run").mkdir()
    assert detect_profile(tmp_path / "run") == "parquet"
    pq = tmp_path / "raw.parquet"
    pq.write_text("", encoding="utf-8")
    assert detect_profile(pq) == "parquet"


def test_read_standardized_csv_with_rename(tmp_path):
    """A variant QCM export (renamed columns) imports by adjusting the mapping,
    with no code changes — acceptance: variant column mapping."""
    from qcm.profiles.standardized_csv import is_standardized_csv, read_standardized_csv

    p = tmp_path / "variant.csv"
    pl.DataFrame({
        "t_1": [0.0, 0.5], "Frequency_1": [5e6, 5e6], "Diss_1": [500.0, 500.0],
    }).write_csv(p)
    # As-is the variant is unmappable (no Fr_N/D_N signature).
    assert not is_standardized_csv(p)
    df = read_standardized_csv(
        p, rename={"t_1": "Time_1", "Frequency_1": "Fr_1", "Diss_1": "D_1"},
    )
    assert df.height == 2
    assert df["group"].unique().to_list() == [1]


def test_import_run_unmappable_clear_error(tmp_path):
    import pytest
    from qcm.profiles import import_run

    junk = tmp_path / "weird.dat"
    junk.write_text("alpha,beta\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        import_run(junk, tmp_path / "run")
    assert "weird.dat" in str(exc.value)  # actionable: names the offending file


def test_import_run_with_profile_override_and_rename(tmp_path):
    from qcm.profiles import import_run
    from qcm.run import open_run

    p = tmp_path / "variant.csv"
    pl.DataFrame({
        "t_1": [0.0, 0.5, 1.0], "Frequency_1": [5e6, 5e6, 5e6], "Diss_1": [500.0, 500.0, 500.0],
    }).write_csv(p)
    import_run(
        p, tmp_path / "run", profile="standardized_csv",
        qcm_rename={"t_1": "Time_1", "Frequency_1": "Fr_1", "Diss_1": "D_1"},
    )
    assert 1 in open_run(tmp_path / "run").groups
