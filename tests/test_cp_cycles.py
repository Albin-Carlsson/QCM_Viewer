"""Tests for current-sign cycle derivation and per-cycle CE (CP)."""
from __future__ import annotations

import numpy as np
import polars as pl

from qcm.viz import echem

_US = 1_000_000


def _cp_wf(n_cycles=3, plate_n=11, strip_n=6, dt=1.0, current=1.0, lead_strip=0):
    """CP waveform: plating (negative I) then stripping (positive I) per cycle.

    plate_n/strip_n are sample counts; with dt spacing a plating half spans
    (plate_n-1)*dt seconds. ``lead_strip`` prepends a partial stripping half so a
    mid-cycle start can be exercised.
    """
    times: list[float] = []
    cur: list[float] = []
    t = 0.0
    for _ in range(lead_strip):
        times.append(t); cur.append(+current); t += dt
    for _ in range(n_cycles):
        for _ in range(plate_n):
            times.append(t); cur.append(-current); t += dt
        for _ in range(strip_n):
            times.append(t); cur.append(+current); t += dt
    tarr = np.array(times)
    carr = np.array(cur)
    charge = np.cumsum(carr * dt)
    return pl.DataFrame({
        "timestamp": (tarr * _US).astype(np.int64),
        "time_s": tarr,
        "current": carr,
        "charge": charge,
        "potential": np.zeros_like(tarr),
    })


def test_derive_cycles_numbers_plating_pairs():
    wf = echem.derive_cycles(_cp_wf(n_cycles=3))
    assert sorted(wf["cycle"].unique().to_list()) == [1, 2, 3]
    # Plating rows are exactly the negative-current rows.
    plate = wf.filter(pl.col("_is_plate"))
    assert plate["current"].max() < 0
    strip = wf.filter(~pl.col("_is_plate"))
    assert strip["current"].min() > 0


def test_derive_cycles_no_current_is_noop():
    wf = pl.DataFrame({"timestamp": [0, 1], "time_s": [0.0, 1.0], "potential": [0.0, 0.1]})
    assert echem.derive_cycles(wf).equals(wf)


def test_cp_cycle_stats_has_coulombic_efficiency():
    wf = _cp_wf(n_cycles=3, plate_n=11, strip_n=6, dt=1.0)
    stats = echem.cycle_stats(wf, "cp")
    for col in ("t_plate_s", "t_strip_s", "Q_plate_C", "Q_strip_C", "CE_time", "CE_charge"):
        assert col in stats.columns
    assert stats.height == 3
    row = stats.sort("cycle").to_dicts()[1]  # a full middle cycle
    assert abs(row["t_plate_s"] - 10.0) < 1e-9   # (11-1)*dt
    assert abs(row["t_strip_s"] - 5.0) < 1e-9     # (6-1)*dt
    assert abs(row["CE_time"] - 0.5) < 1e-9
    assert abs(row["CE_charge"] - 0.5) < 1e-9


def test_mid_cycle_start_does_not_corrupt():
    # Data begins on a stripping half (no preceding plating).
    wf = echem.derive_cycles(_cp_wf(n_cycles=2, lead_strip=4))
    assert wf["cycle"].min() == 1            # leading strip folded into cycle 1
    stats = echem.cycle_stats(wf, "cp")
    assert not stats.is_empty()


def _joined_half_cycle():
    """One cycle: plating mass 0→20000 ng (charge 0→-0.06 C), stripping back to 6000."""
    return pl.DataFrame({
        "timestamp": [0, 1, 2, 3, 4, 5],
        "cycle": [1, 1, 1, 1, 1, 1],
        "_is_plate": [True, True, True, False, False, False],
        "charge": [0.0, -0.03, -0.06, -0.06, -0.03, 0.0],
        "_mass": [0.0, 10_000.0, 20_000.0, 20_000.0, 13_000.0, 6_000.0],
    })


def test_half_cycle_mpe_matches_faraday_slope():
    F = 96485.33212
    out = echem.half_cycle_mpe(_joined_half_cycle(), area=1.0)
    row = out.filter(pl.col("cycle") == 1).to_dicts()[0]
    # MPE is reported as a positive magnitude (sign flipped vs the raw slope).
    exp_plate = round(-F * (20_000 - 0) * 1e-9 / (-0.06), 2)
    exp_strip = round(-F * (6_000 - 20_000) * 1e-9 / (0.06), 2)
    assert abs(row["MPE_plating_g_per_mol"] - exp_plate) < 1e-6
    assert abs(row["MPE_stripping_g_per_mol"] - exp_strip) < 1e-6


def test_half_cycle_mpe_scales_with_area():
    a1 = echem.half_cycle_mpe(_joined_half_cycle(), area=1.0)["MPE_plating_g_per_mol"][0]
    a2 = echem.half_cycle_mpe(_joined_half_cycle(), area=2.0)["MPE_plating_g_per_mol"][0]
    assert abs(a2 - 2 * a1) < 1e-6


def test_half_cycle_mpe_without_halves_is_empty():
    no_half = _joined_half_cycle().drop("_is_plate")
    assert echem.half_cycle_mpe(no_half).is_empty()


def test_cycle_relative_resets_time_and_value():
    df = pl.DataFrame({
        "timestamp": [0, 1_000_000, 2_000_000, 10_000_000, 11_000_000],
        "cycle": [1, 1, 1, 2, 2],
        "value": [100.0, 90.0, 80.0, 50.0, 40.0],
    })
    rel = echem.cycle_relative(df, zero=True)
    c1 = rel.filter(pl.col("cycle") == 1).sort("t_rel_s")
    c2 = rel.filter(pl.col("cycle") == 2).sort("t_rel_s")
    assert c1["t_rel_s"][0] == 0.0 and c2["t_rel_s"][0] == 0.0   # each cycle starts at 0 s
    assert c1["t_rel_s"][-1] == 2.0                               # 2,000,000 µs
    assert c1["value"][0] == 0.0 and c2["value"][0] == 0.0        # zeroed at cycle start
    assert c1["value"][-1] == -20.0                               # 80 - 100


def test_cycle_relative_without_zero_keeps_value():
    df = pl.DataFrame({"timestamp": [0, 1_000_000], "cycle": [1, 1], "value": [5.0, 7.0]})
    rel = echem.cycle_relative(df, zero=False)
    assert rel.sort("t_rel_s")["value"].to_list() == [5.0, 7.0]


def test_cv_cycle_stats_has_no_ce_columns():
    # CV uses the recorded cycle column and gets no CE columns.
    n = 40
    seq = np.arange(n)
    cv = pl.DataFrame({
        "timestamp": (seq * _US).astype(np.int64),
        "time_s": seq.astype(float),
        "current": np.sin(seq / 5.0),
        "potential": np.cos(seq / 5.0),
        "cycle": (seq // 20).astype(np.int64),
    })
    stats = echem.cycle_stats(cv, "cv")
    assert "CE_time" not in stats.columns
    assert stats.height == 2
