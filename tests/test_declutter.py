"""Declutter defaults: visible-overtone subset + cycle thinning."""
from __future__ import annotations

import polars as pl

from qcm.viz import plots
from qcm.viz.controls import ViewerControls
from qcm.viz.state import RunInfo
from qcm.viz.theme import MAX_PLOTTED_CYCLES


def _info(orders: dict[int, int]) -> RunInfo:
    groups = sorted(orders)
    return RunInfo(
        run_id="t", groups=groups, orders=orders,
        t0_us=0, t1_us=10_000_000, span_s=10.0, fmin=4e6, fmax=4.1e8,
        seq_min=0, seq_max=9, n_sweeps=10,
    )


def test_fresh_run_defaults_to_357():
    orders = {g: n for g, n in zip(range(7), (1, 3, 5, 7, 9, 11, 13))}
    c = ViewerControls(_info(orders), {})
    selected = {orders[int(g)] for g in c.group_select.value}
    assert selected == {3, 5, 7}


def test_saved_selection_wins_over_default():
    orders = {g: n for g, n in zip(range(7), (1, 3, 5, 7, 9, 11, 13))}
    c = ViewerControls(_info(orders), {"groups": [0, 4]})
    assert c.group_select.value == ["0", "4"]


def test_run_without_357_keeps_all_channels():
    orders = {0: 1, 1: 1}  # e.g. demo data where every channel reads n=1
    c = ViewerControls(_info(orders), {})
    assert c.group_select.value == ["0", "1"]


def test_thin_cycles_passthrough_and_subset():
    few = list(range(1, MAX_PLOTTED_CYCLES + 1))
    out, thinned = plots._thin_cycles(few)
    assert out == few and not thinned

    many = list(range(1, 101))
    out, thinned = plots._thin_cycles(many)
    assert thinned
    assert len(out) == MAX_PLOTTED_CYCLES
    assert out[0] == 1 and out[-1] == 100  # endpoints always kept
    assert out == sorted(out)


def test_echem_curve_thins_title_and_traces():
    import numpy as np
    n_cycles = 60
    rows = []
    for c in range(1, n_cycles + 1):
        for t in range(5):
            rows.append({"cycle": c, "time_s": (c - 1) * 5.0 + t,
                         "potential": float(t), "current": 1.0})
    wf = pl.DataFrame(rows)
    plot = plots.echem_curve(wf, "time_s", "potential", "t", "E", "title",
                             by_cycle=True, monotonic=True)
    import holoviews as hv
    curves = [e for e in plot.values() if isinstance(e, hv.Curve)]
    assert len(curves) == MAX_PLOTTED_CYCLES


def test_checking_a_signals_box_restores_the_channel():
    """The Signals card is the single channel control: ticking Δf on an
    off-by-default channel must bring its group back into the query set
    (the old hidden group_select left the checkbox dead)."""
    orders = {g: n for g, n in zip(range(7), (1, 3, 5, 7, 9, 11, 13))}
    c = ViewerControls(_info(orders), {})
    g_fund = 0  # n = 1, off by default
    assert str(g_fund) not in c.group_select.value
    c.overtone_frequency[g_fund].value = True
    assert str(g_fund) in c.group_select.value
    # and unticking both boxes removes it again
    c.overtone_frequency[g_fund].value = False
    assert str(g_fund) not in c.group_select.value
