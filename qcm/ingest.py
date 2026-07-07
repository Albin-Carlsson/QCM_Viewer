from __future__ import annotations

import re
import shutil
from pathlib import Path
import pyarrow as pa
import duckdb
import pyarrow.parquet as pq

from .models import Manifest, PathsInfo, TimeInfo
from .sqlutil import sql_path as _sql_path
from .timeutil import now_iso

# The minimal contract every run must satisfy: a timestamp, a sweep id, an
# overtone group, and the fitted resonance (centre + linewidth) the science layer
# turns into Δf/n, dissipation, mass, etc. Everything else is optional so that
# fit-level instrument exports (Qsoft Fr/D per overtone) are first-class without
# the raw frequency-point columns.
CORE_REQUIRED = [
    "timestamp", "sequence", "group", "fit_center", "fit_fwhm",
]

# Raw resonance columns. Present for full raw-sweep runs (raw I/Q, conductance/
# susceptance traces, per-point frequency, fit gamma); absent for fit-only runs,
# in which case raw-only views (sweep inspector, waterfall) degrade gracefully.
RAW_OPTIONAL = ["frequency", "fit_gamma", "conductance", "susceptance", "raw_i", "raw_q"]

# Optional electrochemistry (EQCM) columns. Carried through when present so old
# QCM-only parquet still ingests, while EQCM runs keep their cell-level channel.
ECHEM_OPTIONAL = ["potential", "current", "charge", "cycle", "cycle_time"]

# All optional columns, in copy order.
OPTIONAL = RAW_OPTIONAL + ECHEM_OPTIONAL

# A run carries raw frequency-point *sweep* data when it has per-point measured
# signals — the I/Q pair and/or the conductance/susceptance traces — not just the
# fitted resonance. Any of these enables the sweep/waterfall inspector (the I/Q
# scatter additionally needs raw_i/raw_q and degrades gracefully without them).
# Tools that export resonance sweeps without I/Q (e.g. conductance-only) are still
# recognised as raw, instead of being mistaken for fit-only.
RAW_MARKER = "raw_i"  # legacy single marker; see RAW_SWEEP_MARKERS
RAW_SWEEP_MARKERS = ("raw_i", "raw_q", "conductance", "susceptance")

# Backwards-compatible alias.
REQUIRED = CORE_REQUIRED

# Source unit per canonical column, persisted in the manifest (``units``) so a
# run stays self-describing once exported — CSV without units is future pain.
# Dimensionless columns (sequence, group, cycle) are deliberately absent.
CANONICAL_UNITS = {
    "timestamp": "us",
    "fit_center": "Hz",
    "fit_fwhm": "Hz",
    "fit_gamma": "Hz",
    "frequency": "Hz",
    "conductance": "S",
    "susceptance": "S",
    "raw_i": "a.u.",
    "raw_q": "a.u.",
    "potential": "V",
    "current": "A",
    "charge": "C",
    "cycle_time": "s",
    "time_s": "s",
    "temperature": "degC",
}


def derive_capabilities(columns, *, echem_sidecar: bool = False) -> list[str]:
    """Capability flags ("raw", "echem", "temperature") for a run's columns.

    These are persisted in the manifest so UI surfaces and the CLI key off
    explicit flags instead of sniffing marker columns. ``echem_sidecar`` covers
    CP runs whose cell channels live in the retained potentiostat stream rather
    than inline columns.
    """
    cols = set(columns)
    caps = []
    if any(m in cols for m in RAW_SWEEP_MARKERS):
        caps.append("raw")
    if echem_sidecar or {"potential", "current"}.issubset(cols):
        caps.append("echem")
    if "temperature" in cols:
        caps.append("temperature")
    return caps


def units_for(columns) -> dict[str, str]:
    """column → source unit for the known canonical columns present."""
    return {c: CANONICAL_UNITS[c] for c in columns if c in CANONICAL_UNITS}

# UI overview levels. These are deliberately tiny compared with the raw table;
# the app should use these for plots and only touch raw data for individual sweeps
# or explicit exports.
LEVELS = {
    "100ms": 100_000,
    "1s": 1_000_000,
    "10s": 10_000_000,
    "1min": 60_000_000,
    "10min": 600_000_000,
    "1h": 3_600_000_000,
}


def _source_files(source: Path) -> list[Path]:
    files = sorted(source.glob("*.parquet")) if source.is_dir() else [source]
    if not files:
        raise FileNotFoundError(f"No parquet files found in {source}")
    return files


def _validate_schema(files: list[Path]) -> list[str]:
    schema = pq.read_schema(files[0])
    cols = list(schema.names)
    missing = [c for c in REQUIRED if c not in cols]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    for f in files[1:]:
        these = set(pq.read_schema(f).names)
        missing_here = [c for c in REQUIRED if c not in these]
        if missing_here:
            raise ValueError(f"{f} is missing required columns: {missing_here}")
    return cols


def _copy_raw_in_parts(files: list[Path], raw_out: Path, *, rows_per_part: int) -> int:
    """Copy input parquet into many raw parquet parts without loading the full run.

    This is the critical scalability change: a 1 GB input file is streamed through
    Arrow batches into ``raw/part-XXXXX.parquet`` files. Later DuckDB queries can
    prune columns and row groups instead of forcing the UI to scan one giant in-
    memory frame.

    Optional columns are copied only when **every** source file carries them —
    reading per-file would either crash mid-copy (a later file missing the
    column) or produce parts with mismatched schemas.
    """
    raw_out.mkdir(parents=True, exist_ok=True)
    part = 0
    rows = 0
    schema_names = set(pq.read_schema(files[0]).names)
    for f in files[1:]:
        schema_names &= set(pq.read_schema(f).names)
    copy_columns = REQUIRED + [c for c in OPTIONAL if c in schema_names]
    for src in files:
        pf = pq.ParquetFile(src)
        for batch in pf.iter_batches(batch_size=rows_per_part, columns=copy_columns):
            table = pa.Table.from_batches([batch])
            out = raw_out / f"part-{part:05d}.parquet"
            pq.write_table(
                table,
                out,
                compression="zstd",
                row_group_size=min(rows_per_part, 250_000),
            )
            rows += table.num_rows
            part += 1
    return rows


# Accepted memory-limit spellings: "2GB", "512 MB", "1.5GiB", "4G" …
_MEMORY_LIMIT_RE = re.compile(r"^\s*\d+(\.\d+)?\s*(B|[KMGT]i?B?)?\s*$", re.IGNORECASE)


def _duckdb_conn(memory_limit: str | None = None) -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(database=":memory:")
    conn.execute("PRAGMA threads = 4")
    if memory_limit:
        # Example: "2GB", "8GB". DuckDB spills when needed instead of letting
        # a large import exhaust the Python process. Validated before being
        # embedded in the SET statement (no parameter binding for pragmas) so a
        # typo fails with a clear message rather than a SQL parser error.
        if not _MEMORY_LIMIT_RE.match(str(memory_limit)):
            raise ValueError(
                f"Invalid memory limit {memory_limit!r}; expected e.g. '2GB', '512MB'."
            )
        conn.execute(f"SET memory_limit = '{memory_limit}'")
    return conn


def _raw_glob(dest: Path) -> str:
    return _sql_path(dest / "raw" / "*.parquet")


def _metadata(conn: duckdb.DuckDBPyConnection, dest: Path) -> tuple[int, int, list[int], int]:
    raw = _raw_glob(dest)
    row = conn.execute(
        f"""
        SELECT min(timestamp)::BIGINT, max(timestamp)::BIGINT, count(*)::BIGINT
        FROM read_parquet('{raw}')
        """
    ).fetchone()
    if row is None or row[0] is None:
        raise ValueError(f"Source contains no rows: {dest}")
    t0, t1, rows = row
    groups = [int(r[0]) for r in conn.execute(
        f"SELECT DISTINCT \"group\" FROM read_parquet('{raw}') ORDER BY \"group\""
    ).fetchall()]
    return int(t0), int(t1), groups, int(rows)


def _raw_columns(conn: duckdb.DuckDBPyConnection, dest: Path) -> set[str]:
    raw = _raw_glob(dest)
    return {
        r[0] for r in conn.execute(
            f"SELECT column_name FROM (DESCRIBE SELECT * FROM read_parquet('{raw}'))"
        ).fetchall()
    }


def build_sweep_index(conn: duckdb.DuckDBPyConnection, dest: Path) -> None:
    """Build one row per sequence/group from raw parts using DuckDB SQL.

    Optional raw columns (per-point ``frequency``, ``fit_gamma``) are only
    aggregated when present, so a fit-only run produces a valid index without
    them.
    """
    out = dest / "sweeps"
    out.mkdir(exist_ok=True)
    raw = _raw_glob(dest)
    present = _raw_columns(conn, dest)
    target = _sql_path(out / "index.parquet")
    optional_aggs = ""
    if "frequency" in present:
        optional_aggs += (
            "\n                min(frequency)::DOUBLE AS frequency_min,"
            "\n                max(frequency)::DOUBLE AS frequency_max,"
        )
    if "fit_gamma" in present:
        optional_aggs += "\n                avg(fit_gamma)::DOUBLE AS fit_gamma,"
    conn.execute(
        f"""
        COPY (
            SELECT
                sequence::BIGINT AS sequence,
                \"group\"::BIGINT AS \"group\",
                min(timestamp)::BIGINT AS timestamp,{optional_aggs}
                avg(fit_center)::DOUBLE AS fit_center,
                avg(fit_fwhm)::DOUBLE AS fit_fwhm,
                count(*)::BIGINT AS points
            FROM read_parquet('{raw}')
            GROUP BY sequence, \"group\"
            ORDER BY timestamp, sequence, \"group\"
        ) TO '{target}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )


def build_pyramid(conn: duckdb.DuckDBPyConnection, dest: Path) -> None:
    """Precompute compact time buckets for fast overview plotting.

    The viewer reads these tables for broad time windows. This is what keeps the
    app responsive with 1 GB+ raw imports.
    """
    raw = _raw_glob(dest)
    raw_columns = _raw_columns(conn, dest)
    echem_present = [c for c in ECHEM_OPTIONAL if c in raw_columns]
    # Aggregate the cell-level EQCM channel per bucket. cycle is monotonic over
    # time, so its bucket max is the last (integer-like) cycle index.
    echem_agg_parts = []
    for c in echem_present:
        agg = f"max({c})" if c == "cycle" else f"avg({c})"
        echem_agg_parts.append(f"{agg}::DOUBLE AS {c}")
    echem_agg = "".join(f"\n                    {p}," for p in echem_agg_parts)
    # Raw-trace summaries only exist when the raw columns are present.
    raw_agg = ""
    if "fit_gamma" in raw_columns:
        raw_agg += "\n                    avg(fit_gamma)::DOUBLE AS fit_gamma,"
    if "conductance" in raw_columns:
        raw_agg += "\n                    max(conductance)::DOUBLE AS conductance_peak,"
    if "susceptance" in raw_columns:
        raw_agg += "\n                    avg(susceptance)::DOUBLE AS susceptance_mean,"
    for name, bucket_us in LEVELS.items():
        out_dir = dest / "pyramid" / name
        out_dir.mkdir(parents=True, exist_ok=True)
        target = _sql_path(out_dir / "data.parquet")
        conn.execute(
            f"""
            COPY (
                WITH bucketed AS (
                    SELECT
                        (floor(timestamp / {bucket_us}) * {bucket_us})::BIGINT AS bucket_ts,
                        *
                    FROM read_parquet('{raw}')
                )
                SELECT
                    min(timestamp)::BIGINT AS timestamp,
                    \"group\"::BIGINT AS \"group\",
                    avg(fit_center)::DOUBLE AS fit_center,
                    min(fit_center)::DOUBLE AS fit_center_min,
                    max(fit_center)::DOUBLE AS fit_center_max,
                    avg(fit_fwhm)::DOUBLE AS fit_fwhm,{raw_agg}{echem_agg}
                    count(*)::BIGINT AS count
                FROM bucketed
                GROUP BY bucket_ts, \"group\"
                ORDER BY timestamp, \"group\"
            ) TO '{target}' (FORMAT PARQUET, COMPRESSION ZSTD)
            """
        )


def ingest(
    source: str | Path,
    dest: str | Path,
    overwrite: bool = False,
    *,
    raw_part_rows: int = 1_000_000,
    memory_limit: str | None = "4GB",
    source_label: str | None = None,
    extra_metadata: dict | None = None,
) -> Path:
    """Import parquet into an optimized run folder.

    Designed for large files: the raw data is copied in batches, then compact
    sweep/pyramid tables are created for the UI. The full raw dataset is never
    materialized as a single Polars DataFrame.
    """
    source = Path(source)
    dest = Path(dest)
    if dest.exists() and overwrite:
        shutil.rmtree(dest)
    if dest.exists() and any(dest.iterdir()):
        raise FileExistsError(f"Destination exists and is not empty: {dest}. Use --overwrite to replace it.")
    dest.mkdir(parents=True, exist_ok=True)

    files = _source_files(source)
    cols = _validate_schema(files)

    # A failure below must not leave a half-written run: it would poison the
    # destination (subsequent imports refuse it without --overwrite) and could
    # be mistaken for a real run. Remove what we created and re-raise.
    try:
        rows_copied = _copy_raw_in_parts(files, dest / "raw", rows_per_part=max(50_000, int(raw_part_rows)))

        conn = _duckdb_conn(memory_limit)
        try:
            t0, t1, groups, rows = _metadata(conn, dest)
            build_sweep_index(conn, dest)
            build_pyramid(conn, dest)
        finally:
            conn.close()

        (dest / "annotations.json").write_text("[]")
        (dest / "expressions.json").write_text("{}")

        metadata = {
            "rows": rows,
            "raw_parts": len(list((dest / "raw").glob("*.parquet"))),
            "raw_part_rows": int(raw_part_rows),
            "rows_copied": rows_copied,
            "optimized_for_large_files": True,
            "raw_columns_present": [c for c in RAW_OPTIONAL if c in cols],
        }
        if extra_metadata:
            metadata.update(extra_metadata)
        manifest = Manifest(
            run_id=dest.name,
            created_at=now_iso(),
            source_path=source_label or str(source),
            time=TimeInfo(start=t0, end=t1),
            columns=cols,
            groups=[int(g) for g in groups],
            pyramid_levels=list(LEVELS.keys()),
            paths=PathsInfo(),
            metadata=metadata,
            capabilities=derive_capabilities(cols),
            units=units_for(cols),
        )
        manifest.save(dest)
    except BaseException:
        shutil.rmtree(dest, ignore_errors=True)
        raise
    return dest
