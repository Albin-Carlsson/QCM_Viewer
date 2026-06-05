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
from .pstrace_csv import attach_echem, is_pstrace_csv, read_pstrace_csv
from .pstrace_cv_csv import attach_cv_echem, is_cv_pstrace_csv, read_cv_pstrace_csv
from .qsoft_txt import is_qsoft_txt, read_qsoft_txt
from .standardized_csv import is_standardized_csv, read_standardized_csv

# Canonical column order for the long-form QCM frame.
CANONICAL_COLUMNS = ["timestamp", "sequence", "group", "fit_center", "fit_fwhm", "frequency"]

# Profile registry: ``(name, kind, predicate)`` in detection-priority order.
# ``kind`` is "qcm" (a resonance source that becomes the run) or "ps" (a
# potentiostat export merged onto a QCM source). Detection is signature-based so
# the importer stays tool-agnostic at the edge.
_PROFILE_REGISTRY: list[tuple[str, str, "callable"]] = [
    ("standardized_csv", "qcm", is_standardized_csv),
    ("qsoft_txt", "qcm", is_qsoft_txt),
    ("pstrace_cv", "ps", is_cv_pstrace_csv),
    ("pstrace_cp", "ps", is_pstrace_csv),
]


def profile_kind(name: str) -> str | None:
    """"qcm", "ps", or "parquet" for a profile name; None if unknown."""
    if name == "parquet":
        return "parquet"
    for n, kind, _ in _PROFILE_REGISTRY:
        if n == name:
            return kind
    return None


def detect_profile(source: str | Path) -> str | None:
    """Name of the profile that matches ``source`` by signature, else ``None``.

    Returns ``"parquet"`` for a directory or ``.parquet`` file (the raw-ingest
    path); otherwise the first registry profile whose predicate accepts the file.
    ``None`` means the file is unmappable — the caller should warn rather than
    silently partial-import.
    """
    source = Path(source)
    if source.is_dir() or source.suffix.lower() == ".parquet":
        return "parquet"
    for name, _kind, predicate in _PROFILE_REGISTRY:
        try:
            if predicate(source):
                return name
        except Exception:
            continue
    return None


def import_run(
    source: str | Path,
    dest: str | Path,
    *,
    profile: str | None = None,
    qcm_rename: dict[str, str] | None = None,
    ps_source: str | Path | None = None,
    ps_offset_s: float = 0.0,
    overwrite: bool = False,
    raw_part_rows: int = 1_000_000,
    memory_limit: str | None = "4GB",
) -> Path:
    """Import any supported source into a run directory.

    The matching profile is auto-detected from the file signature
    (:func:`detect_profile`); pass ``profile`` to override that choice. Parquet
    sources go straight through the existing raw-level ingest. A fitted QCM
    source — a standardized ``.csv`` (Time_N/Fr_N/D_N) or a Qsoft ``.txt`` — is
    read into the canonical frame, staged as a temporary parquet, and ingested as
    a fit-only run. ``qcm_rename`` maps a variant export's column names onto the
    canonical ones so renamed-column files import without code changes. When
    ``ps_source`` is given, a PSTrace export (CP time-indexed or CV scan-indexed)
    is attached to the QCM timestamps before ingest. An unrecognized source
    raises a clear error rather than partially importing.
    """
    source = Path(source)
    name = profile or detect_profile(source)
    if name is None:
        raise ValueError(
            f"Could not detect a profile for {source}. Supported: parquet (raw "
            f"runs), standardized QCM csv (Time_N/Fr_N/D_N), and Qsoft txt "
            f"(f{{n}}_/D{{n}}_). Pass profile=… to override, or qcm_rename=… to "
            f"map a variant export's columns."
        )

    if name == "parquet":
        if ps_source is not None:
            raise ValueError(
                "Merging a PSTrace file is supported with a fitted QCM csv/txt "
                "source, not a raw parquet source."
            )
        return ingest(source, dest, overwrite=overwrite,
                      raw_part_rows=raw_part_rows, memory_limit=memory_limit)

    if profile_kind(name) == "ps":
        raise ValueError(
            f"{source} looks like a potentiostat (PSTrace) export. Pass it as "
            f"ps_source alongside a QCM csv/txt source, not as the run source."
        )

    if name == "standardized_csv":
        frame = read_standardized_csv(source, rename=qcm_rename)
    elif name == "qsoft_txt":
        frame = read_qsoft_txt(source)
    else:
        raise ValueError(f"Unsupported QCM profile '{name}' for {source}.")

    if ps_source is not None:
        # A CV PSTrace export is potential/scan-indexed (per-scan i-vs-E blocks),
        # so it takes its own reader/attach; everything else is the time-indexed
        # CP path. Detecting CV first keeps the CP path untouched.
        if is_cv_pstrace_csv(ps_source):
            frame = attach_cv_echem(frame, read_cv_pstrace_csv(ps_source))
        else:
            frame = attach_echem(frame, read_pstrace_csv(ps_source), offset_s=ps_offset_s)
    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp) / "canonical.parquet"
        frame.write_parquet(staged)
        return ingest(staged, dest, overwrite=overwrite,
                      raw_part_rows=raw_part_rows, memory_limit=memory_limit,
                      source_label=str(source))
