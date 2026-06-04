"""Instrument-format profiles for importing measurement data.

A *profile* reads one on-disk export format and maps it onto the single canonical
run frame that :func:`qcm.ingest.ingest` consumes. This keeps the run contract
tool-agnostic: formats vary only at the edge, and everything downstream sees the
same columns.

The canonical QCM frame is long-form, one row per (sweep, overtone):

    timestamp   int   microseconds
    sequence    int   sweep index (shared across overtones at one time)
    group       int   overtone order n (1, 3, 5, ...)
    fit_center  float resonant frequency of the overtone (Hz)
    fit_fwhm    float resonance linewidth (Hz); dissipation = fit_fwhm/fit_center*1e6
    frequency   float representative point (= fit_center for fit-only data)

Fit-only sources (Qsoft Fr/D per overtone) omit the raw frequency-point columns;
:func:`qcm.ingest.ingest` accepts that and marks the run as having no raw data.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from ..ingest import ingest
from .standardized_csv import is_standardized_csv, read_standardized_csv

# Canonical column order for the long-form QCM frame.
CANONICAL_COLUMNS = ["timestamp", "sequence", "group", "fit_center", "fit_fwhm", "frequency"]


def import_run(
    source: str | Path,
    dest: str | Path,
    *,
    overwrite: bool = False,
    raw_part_rows: int = 1_000_000,
    memory_limit: str | None = "4GB",
) -> Path:
    """Import any supported source into a run directory.

    Parquet sources go straight through the existing raw-level ingest. A
    standardized QCM ``.csv`` is read into the canonical frame, staged as a
    temporary parquet, and ingested as a fit-only run that records the original
    file as its source.
    """
    source = Path(source)

    if source.is_dir() or source.suffix.lower() == ".parquet":
        return ingest(source, dest, overwrite=overwrite,
                      raw_part_rows=raw_part_rows, memory_limit=memory_limit)

    if source.suffix.lower() == ".csv" and is_standardized_csv(source):
        frame = read_standardized_csv(source)
        with tempfile.TemporaryDirectory() as tmp:
            staged = Path(tmp) / "canonical.parquet"
            frame.write_parquet(staged)
            return ingest(staged, dest, overwrite=overwrite,
                          raw_part_rows=raw_part_rows, memory_limit=memory_limit,
                          source_label=str(source))

    raise ValueError(
        f"Unrecognized source format: {source}. Supported: parquet (raw runs) "
        f"and standardized QCM csv (Time_N/Fr_N/D_N)."
    )
