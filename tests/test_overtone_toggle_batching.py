"""The Signals card must funnel checkbox changes into one reactive event.

Binding the 3×N overtone checkboxes directly made the All buttons fire N
sequential full-figure rebuilds (~20 s perceived for 7 channels). The
overtone_version widget is the single dependency; these tests pin the
one-event-per-gesture contract.
"""
from __future__ import annotations

from qcm.viz.controls import ViewerControls
from qcm.viz.state import RunInfo


def _controls(n_groups=7):
    groups = list(range(n_groups))
    info = RunInfo(
        run_id="t", groups=groups, orders={g: 2 * g + 1 for g in groups},
        t0_us=0, t1_us=10_000_000, span_s=10.0, fmin=4e6, fmax=4.1e8,
        seq_min=0, seq_max=9, n_sweeps=10,
    )
    # Saved all-on state so these tests start from every box checked (fresh-run
    # defaults are the n=3,5,7 subset — covered in test_declutter).
    saved = {"overtone_controls": {
        str(g): {"frequency": True, "dissipation": True, "normalize_frequency": True}
        for g in groups
    }}
    return ViewerControls(info, saved)


def test_signal_inputs_contain_funnel_not_checkboxes():
    c = _controls()
    sig = c.signal_inputs
    assert c.overtone_version in sig
    for col in (c.overtone_frequency, c.overtone_dissipation, c.overtone_normalize):
        for cb in col.values():
            assert cb not in sig


def test_all_button_is_one_event():
    c = _controls()
    before = c.overtone_version.value
    c.toggle_overtone_column("frequency")
    assert c.overtone_version.value == before + 1
    # and the values actually flipped
    assert not any(cb.value for cb in c.overtone_frequency.values())
    c.toggle_overtone_column("frequency")
    assert c.overtone_version.value == before + 2
    assert all(cb.value for cb in c.overtone_frequency.values())


def test_single_checkbox_is_one_event():
    c = _controls()
    before = c.overtone_version.value
    g = c.info.groups[0]
    c.overtone_dissipation[g].value = False
    assert c.overtone_version.value == before + 1
    assert c.overtone_controls_state()[str(g)]["dissipation"] is False
