"""Tests for editable experiment parameters and their effect on mass/MPE."""
from __future__ import annotations

import polars as pl

from qcm.viz import science
from qcm.viz.controls import ViewerControls
from qcm.viz.state import RunInfo, ViewState
from qcm.viz.theme import ExperimentParams


def test_target_mpe_is_molar_mass_over_valency():
    assert abs(ExperimentParams(molar_mass=65.38, valency=2).target_mpe - 32.69) < 1e-9
    assert ExperimentParams(molar_mass=65.38, valency=0).target_mpe is None


def test_params_dict_roundtrip_and_junk():
    p = ExperimentParams(area_cm2=1.13, sensitivity=12.5, molar_mass=58.69, valency=2)
    assert ExperimentParams.from_dict(p.to_dict()) == p
    # Partial dict keeps defaults; junk falls back entirely.
    assert ExperimentParams.from_dict({"valency": 3}).valency == 3
    assert ExperimentParams.from_dict("nonsense") == ExperimentParams()


def _mass_frame():
    return pl.DataFrame({
        "timestamp": [0, 1, 2],
        "group": [0, 0, 0],
        "fit_center": [5_000_000.0, 4_999_900.0, 4_999_800.0],  # Δf = 0, -100, -200
    })


def test_mass_scales_with_sensitivity():
    orders = {0: 1}
    base = science.compute(_mass_frame(), "sauerbrey_mass", orders,
                           params=ExperimentParams(sensitivity=17.7))
    doubled = science.compute(_mass_frame(), "sauerbrey_mass", orders,
                              params=ExperimentParams(sensitivity=35.4))
    b_last = base.sort("timestamp")["value"][-1]
    d_last = doubled.sort("timestamp")["value"][-1]
    assert abs(b_last - 17.7 * 200) < 1e-6   # -C * (Δf/n) = -17.7 * -200
    assert abs(d_last - 2 * b_last) < 1e-6


def _mpe_frame():
    return pl.DataFrame({
        "timestamp": [0, 1, 2, 3],
        "group": [0, 0, 0, 0],
        "fit_center": [5_000_000.0, 4_999_900.0, 4_999_800.0, 4_999_700.0],
        "charge": [0.0, 1.0, 2.0, 3.0],
    })


def test_mpe_scales_with_area():
    orders = {0: 1}
    a1 = science.compute(_mpe_frame(), "mpe", orders, params=ExperimentParams(area_cm2=1.0))
    a2 = science.compute(_mpe_frame(), "mpe", orders, params=ExperimentParams(area_cm2=2.0))
    v1 = a1.drop_nulls("value")["value"][-1]
    v2 = a2.drop_nulls("value")["value"][-1]
    assert abs(v2 - 2 * v1) < 1e-6


def test_viewstate_persists_params():
    p = ExperimentParams(area_cm2=1.13, sensitivity=12.5, molar_mass=58.69, valency=2)
    state = ViewState(
        groups=[0], quantity="sauerbrey_mass", x_axis="time",
        t_range_s=(0.0, 1.0), baseline_s=(0.0, 0.1), orders={0: 1}, orders_text="",
        sequence=0, single_group=0, sweep_mode="selected overtones",
        frequency_band=(0.0, 1.0), params=p,
    )
    assert state.to_persisted_dict()["params"] == p.to_dict()


def _info():
    return RunInfo(run_id="t", groups=[0], orders={0: 1}, t0_us=0, t1_us=1_000_000,
                   span_s=1.0, fmin=0.0, fmax=1.0, seq_min=0, seq_max=0, n_sweeps=1)


def test_controls_roundtrip_params():
    saved = {"params": {"area_cm2": 1.13, "sensitivity": 12.5, "molar_mass": 58.69, "valency": 2}}
    controls = ViewerControls(_info(), saved)
    p = controls.params()
    assert abs(p.area_cm2 - 1.13) < 1e-9
    assert abs(p.sensitivity - 12.5) < 1e-9
    assert p.valency == 2
    assert controls.state().params == p
