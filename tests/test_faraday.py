"""Faraday prediction overlay + sensitivity-from-f0 helper."""
from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from qcm.viz import science
from qcm.viz.theme import (
    DEFAULT_CRYSTAL_F0_MHZ,
    FARADAY_CONSTANT,
    ExperimentParams,
    sensitivity_from_f0,
)


def _wf(n=100, current=-1e-3, dt=1.0):
    t = np.arange(n) * dt
    charge = np.cumsum(np.full(n, current) * dt)
    return pl.DataFrame({
        "timestamp": (t * 1e6).astype(np.int64),
        "charge": charge,
    })


def test_prediction_mass_sign_and_magnitude():
    p = ExperimentParams(area_cm2=1.0, sensitivity=17.7, molar_mass=65.38, valency=2)
    wf = _wf(current=-1e-3)  # plating: negative current
    out = science.faraday_prediction(wf, "sauerbrey_mass", params=p)
    v = out.sort("timestamp")["value"].to_numpy()
    assert v[-1] > 0  # deposition adds mass
    # m = |Q|·M/(zF·A): cumsum over 100 samples × 1 mA × 1 s = 0.1 C → ng/cm²
    expected = 0.1 * 65.38 / (2 * FARADAY_CONSTANT) * 1e9
    assert abs(v[-1] - expected) / expected < 1e-6


def test_prediction_frequency_is_negative_mass_over_sensitivity():
    p = ExperimentParams(area_cm2=1.0, sensitivity=17.7, molar_mass=65.38, valency=2)
    wf = _wf(current=-1e-3)
    mass = science.faraday_prediction(wf, "sauerbrey_mass", params=p)["value"].to_numpy()
    freq = science.faraday_prediction(wf, "delta_f_norm", params=p)["value"].to_numpy()
    np.testing.assert_allclose(freq, -mass / 17.7)
    assert freq[-1] < 0  # deposition lowers frequency


def test_prediction_baseline_rezeroes():
    p = ExperimentParams(area_cm2=1.0, sensitivity=17.7, molar_mass=65.38, valency=2)
    wf = _wf(n=100, current=-1e-3)
    out = science.faraday_prediction(
        wf, "sauerbrey_mass", params=p, baseline_us=(0, int(10e6)),
    )
    base = out.filter(pl.col("timestamp") <= 10e6)["value"]
    assert abs(float(base.mean())) < 1e-9


def test_prediction_rejects_bad_input():
    assert science.faraday_prediction(pl.DataFrame(), "sauerbrey_mass").is_empty()
    assert science.faraday_prediction(_wf(), "potential").is_empty()
    p = ExperimentParams(area_cm2=0.0)
    assert science.faraday_prediction(_wf(), "sauerbrey_mass", params=p).is_empty()


def test_sensitivity_from_f0_matches_notebook():
    # f0 = 4.95 MHz with the notebook's quartz constants → ≈ 18.04 ng/Hz/cm²
    assert sensitivity_from_f0(DEFAULT_CRYSTAL_F0_MHZ) == pytest.approx(18.04, abs=0.05)
    # the classic 17.7 default corresponds to a 5.00 MHz crystal
    assert sensitivity_from_f0(5.0) == pytest.approx(17.7, abs=0.05)
    with pytest.raises(ValueError):
        sensitivity_from_f0(0.0)
