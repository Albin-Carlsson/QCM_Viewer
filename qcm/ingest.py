from __future__ import annotations

import shutil
from pathlib import Path
import pyarrow as pa
import duckdb
import pyarrow.parquet as pq

from .models import Manifest, PathsInfo, TimeInfo
from .timeutil import now_iso

REQUIRED = [
    "timestamp", "sequence", "group", "frequency", "raw_i", "raw_q",
    "conductance", "susceptance", "fit_center", "fit_gamma", "fit_fwhm",
]

# Optional electrochemistry (EQCM) columns. Carried through when present so old
# QCM-only parquet still ingests, while EQCM runs keep their cell-level channel.
OPTIONAL = ["potential", "current", "charge", "cycle", "cycle_time"]

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


def _sql_path(path: str | Path) -> str:
    """DuckDB SQL string literal for a filesystem path/glob."""
    return str(path).replace("'", "''")


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
    """
    raw_out.mkdir(parents=True, exist_ok=True)
    part = 0
    rows = 0
    schema_names = set(pq.read_schema(files[0]).names)
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


def _duckdb_conn(memory_limit: str | None = None) -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(database=":memory:")
    conn.execute("PRAGMA threads = 4")
    if memory_limit:
        # Example: "2GB", "8GB". DuckDB spills when needed instead of letting
        # a large import exhaust the Python process.
        conn.execute(f"SET memory_limit = '{memory_limit}'")
    return conn


def _raw_glob(dest: Path) -> str:
    return _sql_path(dest / "raw" / "*.parquet")


def _metadata(conn: duckdb.DuckDBPyConnection, dest: Path) -> tuple[int, int, list[int], int]:
    raw = _raw_glob(dest)
    t0, t1, rows = conn.execute(
        f"""
        SELECT min(timestamp)::BIGINT, max(timestamp)::BIGINT, count(*)::BIGINT
        FROM read_parquet('{raw}')
        """
    ).fetchone()
    groups = [int(r[0]) for r in conn.execute(
        f"SELECT DISTINCT \"group\" FROM read_parquet('{raw}') ORDER BY \"group\""
    ).fetchall()]
    return int(t0), int(t1), groups, int(rows)


def build_sweep_index(conn: duckdb.DuckDBPyConnection, dest: Path) -> None:
    """Build one row per sequence/group from raw parts using DuckDB SQL."""
    out = dest / "sweeps"
    out.mkdir(exist_ok=True)
    raw = _raw_glob(dest)
    target = _sql_path(out / "index.parquet")
    conn.execute(
        f"""
        COPY (
            SELECT
                sequence::BIGINT AS sequence,
                \"group\"::BIGINT AS \"group\",
                min(timestamp)::BIGINT AS timestamp,
                min(frequency)::DOUBLE AS frequency_min,
                max(frequency)::DOUBLE AS frequency_max,
                avg(fit_center)::DOUBLE AS fit_center,
                avg(fit_gamma)::DOUBLE AS fit_gamma,
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
    raw_columns = {
        r[0] for r in conn.execute(
            f"SELECT column_name FROM (DESCRIBE SELECT * FROM read_parquet('{raw}'))"
        ).fetchall()
    }
    echem_present = [c for c in OPTIONAL if c in raw_columns]
    # Aggregate the cell-level EQCM channel per bucket. cycle is monotonic over
    # time, so its bucket max is the last (integer-like) cycle index.
    echem_select = "".join(f"\n                        {c}," for c in echem_present)
    echem_agg_parts = []
    for c in echem_present:
        agg = f"max({c})" if c == "cycle" else f"avg({c})"
        echem_agg_parts.append(f"{agg}::DOUBLE AS {c}")
    echem_agg = "".join(f"\n                    {p}," for p in echem_agg_parts)
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
                        timestamp,
                        \"group\",
                        fit_center,
                        fit_gamma,
                        fit_fwhm,
                        conductance,
                        susceptance,
                        raw_i,
                        raw_q,{echem_select}
                        timestamp AS _ts_keep
                    FROM read_parquet('{raw}')
                )
                SELECT
                    min(timestamp)::BIGINT AS timestamp,
                    \"group\"::BIGINT AS \"group\",
                    avg(fit_center)::DOUBLE AS fit_center,
                    min(fit_center)::DOUBLE AS fit_center_min,
                    max(fit_center)::DOUBLE AS fit_center_max,
                    avg(fit_fwhm)::DOUBLE AS fit_fwhm,
                    avg(fit_gamma)::DOUBLE AS fit_gamma,
                    max(conductance)::DOUBLE AS conductance_peak,
                    avg(susceptance)::DOUBLE AS susceptance_mean,{echem_agg}
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

    rows_copied = _copy_raw_in_parts(files, dest / "raw", rows_per_part=max(50_000, int(raw_part_rows)))

    conn = _duckdb_conn(memory_limit)
    t0, t1, groups, rows = _metadata(conn, dest)
    build_sweep_index(conn, dest)
    build_pyramid(conn, dest)
    conn.close()

    (dest / "annotations.json").write_text("[]")
    (dest / "expressions.json").write_text("{}")

    manifest = Manifest(
        run_id=dest.name,
        created_at=now_iso(),
        source_path=str(source),
        time=TimeInfo(start=t0, end=t1),
        columns=cols,
        groups=[int(g) for g in groups],
        pyramid_levels=list(LEVELS.keys()),
        paths=PathsInfo(),
        metadata={
            "rows": rows,
            "raw_parts": len(list((dest / "raw").glob("*.parquet"))),
            "raw_part_rows": int(raw_part_rows),
            "rows_copied": rows_copied,
            "optimized_for_large_files": True,
        },
    )
    manifest.save(dest)
    return dest
