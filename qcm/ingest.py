from __future__ import annotations

import shutil
from pathlib import Path

import polars as pl

from .models import Manifest, TimeInfo, PathsInfo
from .timeutil import now_iso

REQUIRED = [
    "timestamp", "sequence", "group", "frequency", "raw_i", "raw_q",
    "conductance", "susceptance", "fit_center", "fit_gamma", "fit_fwhm",
]

LEVELS = {
    "100ms": "100ms",
    "1s": "1s",
    "10s": "10s",
    "1min": "1m",
    "10min": "10m",
    "1h": "1h",
}


def ingest(source: str | Path, dest: str | Path, overwrite: bool = False) -> Path:
    source = Path(source)
    dest = Path(dest)
    if dest.exists() and overwrite:
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    raw_out = dest / "raw"
    raw_out.mkdir(exist_ok=True)

    files = sorted(source.glob("*.parquet")) if source.is_dir() else [source]
    if not files:
        raise FileNotFoundError(f"No parquet files found in {source}")

    frames = [pl.scan_parquet(str(f)) for f in files]
    lf = pl.concat(frames).sort(["timestamp", "sequence", "group", "frequency"])
    cols = lf.collect_schema().names()
    missing = [c for c in REQUIRED if c not in cols]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df = lf.collect(streaming=True)
    df.write_parquet(raw_out / "data.parquet", compression="zstd")

    groups = sorted(df["group"].unique().to_list())
    t0 = int(df["timestamp"].min())
    t1 = int(df["timestamp"].max())

    build_sweep_index(df, dest)
    build_pyramid(df, dest)

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
        metadata={"rows": df.height},
    )
    manifest.save(dest)
    return dest


def build_sweep_index(df: pl.DataFrame, dest: Path) -> None:
    out = dest / "sweeps"
    out.mkdir(exist_ok=True)
    idx = (
        df.group_by(["sequence", "group"])
        .agg([
            pl.col("timestamp").first(),
            pl.col("frequency").min().alias("frequency_min"),
            pl.col("frequency").max().alias("frequency_max"),
            pl.col("fit_center").first(),
            pl.col("fit_gamma").first(),
            pl.col("fit_fwhm").first(),
            pl.len().alias("points"),
        ])
        .sort(["timestamp", "sequence", "group"])
    )
    idx.write_parquet(out / "index.parquet", compression="zstd")


def build_pyramid(df: pl.DataFrame, dest: Path) -> None:
    base = df.select([
        pl.from_epoch("timestamp", time_unit="us").alias("dt"),
        "timestamp", "group", "fit_center", "fit_gamma", "fit_fwhm",
        "conductance", "susceptance", "raw_i", "raw_q",
    ]).sort("dt")
    for name, every in LEVELS.items():
        out_dir = dest / "pyramid" / name
        out_dir.mkdir(parents=True, exist_ok=True)
        agg = (
            base.group_by_dynamic("dt", every=every, group_by="group")
            .agg([
                pl.col("timestamp").min().alias("timestamp"),
                pl.col("fit_center").mean().alias("fit_center"),
                pl.col("fit_center").min().alias("fit_center_min"),
                pl.col("fit_center").max().alias("fit_center_max"),
                pl.col("fit_fwhm").mean().alias("fit_fwhm"),
                pl.col("fit_gamma").mean().alias("fit_gamma"),
                pl.col("conductance").max().alias("conductance_peak"),
                pl.col("susceptance").mean().alias("susceptance_mean"),
                pl.len().alias("count"),
            ])
            .sort(["timestamp", "group"])
        )
        agg.write_parquet(out_dir / "data.parquet", compression="zstd")
