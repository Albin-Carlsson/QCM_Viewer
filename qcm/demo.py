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
    # Electrochemistry (EQCM) channel. Cell-level signals shared across overtones.
    "potential",
    "current",
    "charge",
    "cycle",
    "cycle_time",
]

# --- simulated cyclic-voltammetry parameters -------------------------------
_V_LO = -0.5            # lower potential limit (V)
_V_HI = 0.5            # upper potential limit (V)
_N_CYCLES = 10          # triangular CV cycles over the intended run
_C_DL = 2.0e-5          # double-layer capacitance term -> capacitive current (A per V/s)
_FARADAIC_AMP = 8.0e-5  # peak faradaic current (A)
_V_PEAK = 0.15          # potential of the redox peak (V)
_PEAK_WIDTH = 0.08      # gaussian half-width of the redox peak (V)
# Resonance shift per coulomb of deposited (faradaic) charge. Couples Δf to the
# electrochemistry so areal mass tracks charge and the mass-per-electron (MPE)
# Faraday slope is a meaningful, roughly constant molar mass.
_DEP_HZ_PER_C = 9.0e5

# --- simulated chronopotentiometry (galvanostatic CP) parameters -----------
_CP_I_APP = 5.0e-5      # applied current magnitude (A); sign alternates each step
_CP_OCV = 0.10          # open-circuit / rest potential (V)
_CP_R = 250.0           # ohmic resistance -> IR jump at each step transition (V = I·R)
_CP_V_PER_C = 9.0e3     # potential ramp per coulomb passed within a step (V/C)
_CP_N_CYCLES = 10       # charge+discharge cycles over the intended run

Technique = Literal["cv", "cp"]
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


def _cv_channel(
    seqs: np.ndarray,
    *,
    seq_gap_us: int,
    total_sequences_for_event: int,
    charge_offset: float,
    faradaic_offset: float,
    rng: np.random.Generator,
) -> dict[str, np.ndarray]:
    """Vectorized cyclic-voltammetry signals for a block of sweep indices.

    A triangular potential sweep between ``_V_LO`` and ``_V_HI`` repeats over
    ``_N_CYCLES`` cycles. Current is capacitive (proportional to the scan rate,
    flipping sign at each apex) plus a faradaic redox peak. Charge is the running
    integral of current; ``charge_offset``/``faradaic_offset`` carry the totals
    across chunks so the cumulative columns stay continuous. ``deposition_hz`` is
    a resonance shift proportional to deposited (faradaic) charge, returned so the
    caller can couple Δf to the electrochemistry.
    """
    dt_s = seq_gap_us / 1e6
    seq_per_cycle = max(1.0, total_sequences_for_event / _N_CYCLES)
    phase = seqs / seq_per_cycle
    cycle = np.floor(phase).astype(np.int64)
    frac = phase - cycle
    tri = 1.0 - np.abs(2.0 * frac - 1.0)  # 0 -> 1 -> 0 over a cycle
    potential = _V_LO + (_V_HI - _V_LO) * tri

    scan_sign = np.where(frac < 0.5, 1.0, -1.0)  # +1 rising (anodic), -1 falling
    dphase_dt = 1.0 / (seq_per_cycle * dt_s)
    dV_dt = (_V_HI - _V_LO) * 2.0 * scan_sign * dphase_dt
    i_cap = _C_DL * dV_dt
    i_far = _FARADAIC_AMP * np.exp(-(((potential - _V_PEAK) / _PEAK_WIDTH) ** 2)) * scan_sign
    current = i_cap + i_far + rng.normal(0, 1e-6, len(seqs))

    charge = charge_offset + np.cumsum(current * dt_s)
    faradaic_cum = faradaic_offset + np.cumsum(np.abs(i_far) * dt_s)
    cycle_time = frac * seq_per_cycle * dt_s
    deposition_hz = _DEP_HZ_PER_C * faradaic_cum

    return {
        "potential": potential,
        "current": current,
        "charge": charge,
        "cycle": cycle.astype(np.float64),
        "cycle_time": cycle_time,
        "deposition_hz": deposition_hz,
        "_charge_end": charge[-1] if len(charge) else charge_offset,
        "_faradaic_end": faradaic_cum[-1] if len(faradaic_cum) else faradaic_offset,
    }


def _cp_channel(
    seqs: np.ndarray,
    *,
    seq_gap_us: int,
    total_sequences_for_event: int,
    charge_offset: float,
    faradaic_offset: float,
    rng: np.random.Generator,
) -> dict[str, np.ndarray]:
    """Vectorized galvanostatic chronopotentiometry signals for a block of sweeps.

    A constant current is applied with the sign alternating every half-step
    (charge then discharge); a charge+discharge pair is one cycle. The potential
    is the rest potential plus an ohmic IR jump (sign of the current) and a linear
    ramp proportional to the charge passed within the current step, so it draws
    the characteristic CP sawtooth. ``charge`` is the running signed integral of
    current (continuous across chunks via the offsets); ``deposition_hz`` couples
    Δf to the cumulative charge passed.
    """
    dt_s = seq_gap_us / 1e6
    seq_per_halfstep = max(1.0, total_sequences_for_event / (2 * _CP_N_CYCLES))
    seq_per_cycle = 2.0 * seq_per_halfstep

    step_index = np.floor(seqs / seq_per_halfstep)
    sign = np.where(np.mod(step_index, 2) == 0, 1.0, -1.0)  # +charge / -discharge
    step_time = (seqs - step_index * seq_per_halfstep) * dt_s
    current = sign * _CP_I_APP + rng.normal(0, 5e-7, len(seqs))

    charge_in_step = _CP_I_APP * step_time  # magnitude of charge passed this step
    potential = _CP_OCV + sign * (_CP_I_APP * _CP_R + _CP_V_PER_C * charge_in_step)
    potential = potential + rng.normal(0, 1e-3, len(seqs))

    charge = charge_offset + np.cumsum(current * dt_s)
    faradaic_cum = faradaic_offset + np.cumsum(np.abs(current) * dt_s)
    cycle = np.floor(seqs / seq_per_cycle).astype(np.int64)
    cycle_time = (seqs - cycle.astype(np.float64) * seq_per_cycle) * dt_s
    deposition_hz = _DEP_HZ_PER_C * faradaic_cum

    return {
        "potential": potential,
        "current": current,
        "charge": charge,
        "cycle": cycle.astype(np.float64),
        "cycle_time": cycle_time,
        "deposition_hz": deposition_hz,
        "_charge_end": charge[-1] if len(charge) else charge_offset,
        "_faradaic_end": faradaic_cum[-1] if len(faradaic_cum) else faradaic_offset,
    }


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
    technique: str = "cv",
    charge_offset: float = 0.0,
    faradaic_offset: float = 0.0,
) -> tuple[pa.Table, float, float]:
    """Build one vectorized parquet chunk without keeping the full run in RAM.

    Returns the chunk table plus the running charge / faradaic totals so the next
    chunk continues the cumulative electrochemistry columns.
    """
    parts: dict[str, list[np.ndarray]] = {name: [] for name in COLUMNS}

    seqs = np.arange(start_sequence, start_sequence + sequences, dtype=np.int64)
    channel_fn = _cp_channel if technique == "cp" else _cv_channel
    cv = channel_fn(
        seqs,
        seq_gap_us=seq_gap_us,
        total_sequences_for_event=total_sequences_for_event,
        charge_offset=charge_offset,
        faradaic_offset=faradaic_offset,
        rng=rng,
    )

    for i, seq in enumerate(range(start_sequence, start_sequence + sequences)):
        ts = np.int64(base_timestamp_us + seq * seq_gap_us)
        # Smooth event in the middle of the intended run. For target-size long
        # generation, this still gives a useful simulated adsorption/rinse shape.
        event = 1 / (1 + np.exp(-(seq - total_sequences_for_event * 0.45) / 18))
        deposition = float(cv["deposition_hz"][i])

        for g in range(groups):
            # Δf is driven by the adsorption event *and* by electrochemical
            # deposition (faradaic charge), so QCM mass tracks the EQCM channel.
            center = base_freq + g * 22_000 - event * (250 + g * 60) - deposition + rng.normal(0, 3)
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
            # Cell-level EQCM signals: identical for every overtone of this sweep.
            parts["potential"].append(np.full(n, cv["potential"][i], dtype=np.float64))
            parts["current"].append(np.full(n, cv["current"][i], dtype=np.float64))
            parts["charge"].append(np.full(n, cv["charge"][i], dtype=np.float64))
            parts["cycle"].append(np.full(n, cv["cycle"][i], dtype=np.float64))
            parts["cycle_time"].append(np.full(n, cv["cycle_time"][i], dtype=np.float64))

    arrays = [pa.array(np.concatenate(parts[name])) for name in COLUMNS]
    return pa.table(arrays, names=COLUMNS), cv["_charge_end"], cv["_faradaic_end"]


def make_demo_data(
    out_dir: str | Path,
    *,
    preset: Preset = "small",
    technique: Technique = "cv",
    groups: int | None = None,
    sequences: int | None = None,
    points_per_sweep: int | None = None,
    target_mb: int | None = None,
    compression: str | None = None,
    chunk_sequences: int | None = None,
    seed: int = 7,
) -> Path:
    """Create synthetic QCM-D parquet data with an electrochemistry channel.

    Parameters
    ----------
    preset:
        ``small`` creates a quick development dataset. ``long`` streams chunks
        until the parquet file is roughly ``target_mb`` MB, defaulting to 500 MB.
    technique:
        ``cv`` simulates cyclic voltammetry (triangular potential sweep); ``cp``
        simulates galvanostatic chronopotentiometry (alternating constant current
        with a stepped potential response).
    target_mb:
        Optional on-disk target size. Mostly useful with ``preset='long'``.
    compression:
        Parquet compression. Use ``none`` for predictable large files.
    """
    if technique not in ("cv", "cp"):
        raise ValueError(f"Unknown technique {technique!r}. Choose 'cv' or 'cp'.")
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
    charge_offset = 0.0
    faradaic_offset = 0.0
    try:
        while seq < sequences:
            n_seq = min(chunk_sequences, sequences - seq)
            table, charge_offset, faradaic_offset = _chunk_table(
                start_sequence=seq,
                sequences=n_seq,
                groups=groups,
                points_per_sweep=points_per_sweep,
                seq_gap_us=seq_gap_us,
                base_timestamp_us=base_timestamp_us,
                base_freq=base_freq,
                rng=rng,
                total_sequences_for_event=sequences if target_bytes is None else max(10_000, sequences),
                technique=technique,
                charge_offset=charge_offset,
                faradaic_offset=faradaic_offset,
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
