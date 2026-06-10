"""Sauerbrey validity check (overtone collapse + viscoelastic ratio)."""
from __future__ import annotations

import polars as pl

from qcm.viz import science


def _summary(df_n, dd_per_df=None):
    data = {"group": list(range(len(df_n))), "df_n": df_n}
    if dd_per_df is not None:
        data["dD_per_df"] = dd_per_df
    return pl.DataFrame(data)


def test_rigid_film_is_ok():
    out = science.sauerbrey_check(_summary([-100.0, -101.0, -99.5], [0.05, 0.06, 0.05]))
    assert out["verdict"] == "ok"
    assert out["spread_pct"] < 10
    assert out["ratio"] < 0.4


def test_soft_film_is_poor():
    out = science.sauerbrey_check(_summary([-100.0, -80.0], [1.5, 2.0]))
    assert out["verdict"] == "poor"
    assert "viscoelastic" in out["detail"]


def test_overtone_scatter_is_caution():
    # Ratio fine, but Δf/n disagrees by ~40 % across overtones.
    out = science.sauerbrey_check(_summary([-100.0, -140.0], [0.1, 0.1]))
    assert out["verdict"] == "caution"


def test_no_signal_returns_none():
    assert science.sauerbrey_check(pl.DataFrame()) is None
    assert science.sauerbrey_check(_summary([0.0, 0.0])) is None
    assert science.sauerbrey_check(None) is None


def test_single_overtone_skips_spread():
    out = science.sauerbrey_check(_summary([-50.0], [0.2]))
    assert out["spread_pct"] is None
    assert out["verdict"] == "ok"
