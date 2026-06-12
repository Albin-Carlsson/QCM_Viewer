"""Ingest hardening: failed imports clean up, multi-file schemas intersect,
and the DuckDB memory limit is validated before use."""
from __future__ import annotations

import polars as pl
import pytest

from qcm.ingest import _MEMORY_LIMIT_RE, ingest


def _frame(n=8, with_gamma=True) -> pl.DataFrame:
    cols = {
        "timestamp": [i * 1_000_000 for i in range(n)],
        "sequence": list(range(n)),
        "group": [1] * n,
        "fit_center": [5e6] * n,
        "fit_fwhm": [100.0] * n,
        "frequency": [5e6] * n,
    }
    if with_gamma:
        cols["fit_gamma"] = [50.0] * n
    return pl.DataFrame(cols)


def test_failed_ingest_cleans_destination(tmp_path):
    src = tmp_path / "src.parquet"
    _frame().write_parquet(src)
    dest = tmp_path / "run"
    # An invalid memory limit fails after the destination was created…
    with pytest.raises(ValueError, match="memory limit"):
        ingest(src, dest, memory_limit="lots")
    # …and must not leave a poisoned half-run behind.
    assert not dest.exists()
    # A retry with good settings now succeeds without --overwrite.
    ingest(src, dest, memory_limit="1GB")
    assert (dest / "manifest.json").exists()


def test_memory_limit_validation():
    for ok in ("2GB", "512 MB", "1.5GiB", "4G", "100kb"):
        assert _MEMORY_LIMIT_RE.match(ok), ok
    for bad in ("lots", "GB2", "2GB; DROP TABLE x", ""):
        assert not _MEMORY_LIMIT_RE.match(bad), bad


def test_multi_file_source_intersects_optional_columns(tmp_path):
    """A directory source whose files disagree on optional columns must import
    cleanly with the common columns (not crash mid-copy on the odd file)."""
    src = tmp_path / "parts"
    src.mkdir()
    _frame(with_gamma=True).write_parquet(src / "a.parquet")
    _frame(with_gamma=False).write_parquet(src / "b.parquet")
    dest = tmp_path / "run"
    ingest(src, dest)
    cols = pl.read_parquet(str(dest / "raw" / "*.parquet")).columns
    assert "fit_gamma" not in cols  # not common to all files
    assert {"timestamp", "sequence", "group", "fit_center", "fit_fwhm", "frequency"} <= set(cols)
