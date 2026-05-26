from __future__ import annotations

from pathlib import Path
import numpy as np
import polars as pl


def make_demo_data(out_dir: str | Path, groups: int = 3, sequences: int = 250, points_per_sweep: int = 500) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    start = 1_779_716_807_778_141
    seq_gap_us = 150_000
    base_freq = 4_958_000.0
    rng = np.random.default_rng(7)
    for seq in range(sequences):
        ts = start + seq * seq_gap_us
        event = 1 / (1 + np.exp(-(seq - sequences * 0.45) / 18))
        for g in range(groups):
            center = base_freq + g * 22_000 - event * (250 + g * 60) + rng.normal(0, 3)
            gamma = 650 + g * 25 + event * 80 + rng.normal(0, 2)
            f = np.linspace(center - 3500, center + 3500, points_per_sweep)
            x = (f - center) / gamma
            conductance = 0.001 + 0.03 / (1 + x**2) + rng.normal(0, 0.0003, points_per_sweep)
            susceptance = -0.014 * x / (1 + x**2) + rng.normal(0, 0.0002, points_per_sweep)
            raw_i = conductance + rng.normal(0, 0.00015, points_per_sweep)
            raw_q = susceptance + rng.normal(0, 0.00015, points_per_sweep)
            for i in range(points_per_sweep):
                rows.append((ts, seq, g, float(f[i]), float(raw_i[i]), float(raw_q[i]), float(conductance[i]), float(susceptance[i]), float(center), float(gamma), float(gamma * 2)))
    df = pl.DataFrame(rows, schema=["timestamp", "sequence", "group", "frequency", "raw_i", "raw_q", "conductance", "susceptance", "fit_center", "fit_gamma", "fit_fwhm"], orient="row")
    path = out / "demo.parquet"
    df.write_parquet(path, compression="zstd")
    return path
