from __future__ import annotations

from pathlib import Path
from typing import Literal

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

COLUMNS = [
    "timestamp",
    "sequence",
    "group",
    "frequency",
    "raw_i",
    "raw_q",
    "conductance",
    "susceptance",
    "fit_center",
    "fit_gamma",
    "fit_fwhm",
]

Preset = Literal["small", "long"]


PRESETS: dict[str, dict[str, int | float | str | None]] = {
    # Quick smoke-test dataset. Good for UI development.
    "small": {
        "groups": 3,
        "sequences": 250,
        "points_per_sweep": 500,
        "target_mb": None,
        "compression": "zstd",
        "chunk_sequences": 25,
    },
    # Large stress-test dataset. The writer streams parquet chunks until the
    # on-disk file is roughly target_mb. Uncompressed output makes the target
    # predictable and avoids spending most of the time in compression.
    "long": {
        "groups": 5,
        "sequences": 10_000_000,  # practical stop is target_mb, not this cap
        "points_per_sweep": 500,
        "target_mb": 500,
        "compression": "none",
        "chunk_sequences": 50,
    },
}


def _compression_value(name: str | None) -> str | None:
    if name is None or name.lower() in {"none", "uncompressed", "false", "0"}:
        return None
    return name


def _chunk_table(
    *,
    start_sequence: int,
    sequences: int,
    groups: int,
    points_per_sweep: int,
    seq_gap_us: int,
    base_timestamp_us: int,
    base_freq: float,
    rng: np.random.Generator,
    total_sequences_for_event: int,
) -> pa.Table:
    """Build one vectorized parquet chunk without keeping the full run in RAM."""
    parts: dict[str, list[np.ndarray]] = {name: [] for name in COLUMNS}

    for seq in range(start_sequence, start_sequence + sequences):
        ts = np.int64(base_timestamp_us + seq * seq_gap_us)
        # Smooth event in the middle of the intended run. For target-size long
        # generation, this still gives a useful simulated adsorption/rinse shape.
        event = 1 / (1 + np.exp(-(seq - total_sequences_for_event * 0.45) / 18))

        for g in range(groups):
            center = base_freq + g * 22_000 - event * (250 + g * 60) + rng.normal(0, 3)
            gamma = 650 + g * 25 + event * 80 + rng.normal(0, 2)

            frequency = np.linspace(center - 3500, center + 3500, points_per_sweep, dtype=np.float64)
            x = (frequency - center) / gamma
            conductance = 0.001 + 0.03 / (1 + x**2) + rng.normal(0, 0.0003, points_per_sweep)
            susceptance = -0.014 * x / (1 + x**2) + rng.normal(0, 0.0002, points_per_sweep)
            raw_i = conductance + rng.normal(0, 0.00015, points_per_sweep)
            raw_q = susceptance + rng.normal(0, 0.00015, points_per_sweep)

            n = points_per_sweep
            parts["timestamp"].append(np.full(n, ts, dtype=np.int64))
            parts["sequence"].append(np.full(n, seq, dtype=np.int64))
            parts["group"].append(np.full(n, g, dtype=np.int64))
            parts["frequency"].append(frequency)
            parts["raw_i"].append(raw_i.astype(np.float64, copy=False))
            parts["raw_q"].append(raw_q.astype(np.float64, copy=False))
            parts["conductance"].append(conductance.astype(np.float64, copy=False))
            parts["susceptance"].append(susceptance.astype(np.float64, copy=False))
            parts["fit_center"].append(np.full(n, center, dtype=np.float64))
            parts["fit_gamma"].append(np.full(n, gamma, dtype=np.float64))
            parts["fit_fwhm"].append(np.full(n, gamma * 2, dtype=np.float64))

    arrays = [pa.array(np.concatenate(parts[name])) for name in COLUMNS]
    return pa.table(arrays, names=COLUMNS)


def make_demo_data(
    out_dir: str | Path,
    *,
    preset: Preset = "small",
    groups: int | None = None,
    sequences: int | None = None,
    points_per_sweep: int | None = None,
    target_mb: int | None = None,
    compression: str | None = None,
    chunk_sequences: int | None = None,
    seed: int = 7,
) -> Path:
    """Create synthetic QCM-D parquet data.

    Parameters
    ----------
    preset:
        ``small`` creates a quick development dataset. ``long`` streams chunks
        until the parquet file is roughly ``target_mb`` MB, defaulting to 500 MB.
    target_mb:
        Optional on-disk target size. Mostly useful with ``preset='long'``.
    compression:
        Parquet compression. Use ``none`` for predictable large files.
    """
    if preset not in PRESETS:
        raise ValueError(f"Unknown demo preset {preset!r}. Choose one of: {', '.join(PRESETS)}")

    cfg = PRESETS[preset]
    groups = int(groups if groups is not None else cfg["groups"])
    sequences = int(sequences if sequences is not None else cfg["sequences"])
    points_per_sweep = int(points_per_sweep if points_per_sweep is not None else cfg["points_per_sweep"])
    target_mb = int(target_mb if target_mb is not None else cfg["target_mb"] or 0) or None
    compression = compression if compression is not None else str(cfg["compression"])
    chunk_sequences = int(chunk_sequences if chunk_sequences is not None else cfg["chunk_sequences"])

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "demo.parquet"
    if path.exists():
        path.unlink()

    base_timestamp_us = 1_779_716_807_778_141
    seq_gap_us = 150_000
    base_freq = 4_958_000.0
    rng = np.random.default_rng(seed)
    parquet_compression = _compression_value(compression)
    target_bytes = target_mb * 1024 * 1024 if target_mb is not None else None

    writer: pq.ParquetWriter | None = None
    seq = 0
    try:
        while seq < sequences:
            n_seq = min(chunk_sequences, sequences - seq)
            table = _chunk_table(
                start_sequence=seq,
                sequences=n_seq,
                groups=groups,
                points_per_sweep=points_per_sweep,
                seq_gap_us=seq_gap_us,
                base_timestamp_us=base_timestamp_us,
                base_freq=base_freq,
                rng=rng,
                total_sequences_for_event=sequences if target_bytes is None else max(10_000, sequences),
            )
            if writer is None:
                writer = pq.ParquetWriter(path, table.schema, compression=parquet_compression)
            writer.write_table(table)
            seq += n_seq

            # File size is approximate until close, but good enough to stop long
            # streaming near the requested target.
            if target_bytes is not None and path.exists() and path.stat().st_size >= target_bytes:
                break
    finally:
        if writer is not None:
            writer.close()

    return path
